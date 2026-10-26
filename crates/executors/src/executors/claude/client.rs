use std::{
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
};

use tokio_util::sync::CancellationToken;
use workspace_utils::approvals::{ApprovalStatus, QuestionStatus};

use super::types::PermissionMode;
use crate::{
    approvals::{ExecutorApprovalError, ExecutorApprovalService},
    env::RepoContext,
    executors::{
        ExecutorError,
        claude::{
            ClaudeJson,
            types::{
                PermissionResult, PermissionUpdate, PermissionUpdateDestination,
                PermissionUpdateType,
            },
        },
        codex::client::LogWriter,
    },
};

const EXIT_PLAN_MODE_NAME: &str = "ExitPlanMode";
const ASK_USER_QUESTION_NAME: &str = "AskUserQuestion";
pub const STOP_GIT_CHECK_CALLBACK_ID: &str = "STOP_GIT_CHECK_CALLBACK_ID";
// Prefix for denial messages from the user, mirrors claude code CLI behavior
const TOOL_DENY_PREFIX: &str = "The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). To tell you how to proceed, the user said: ";

/// Claude Agent client with control protocol support
pub struct ClaudeAgentClient {
    log_writer: LogWriter,
    approvals: Option<Arc<dyn ExecutorApprovalService>>,
    repo_context: RepoContext,
    commit_reminder_prompt: String,
    cancel: CancellationToken,
    permission_root: Option<PathBuf>,
    native_permissions_qualified: AtomicBool,
}

impl ClaudeAgentClient {
    /// Create a new client with optional approval service
    pub fn new(
        log_writer: LogWriter,
        approvals: Option<Arc<dyn ExecutorApprovalService>>,
        repo_context: RepoContext,
        commit_reminder_prompt: String,
        cancel: CancellationToken,
    ) -> Arc<Self> {
        Self::new_scoped(
            log_writer,
            approvals,
            repo_context,
            commit_reminder_prompt,
            cancel,
            None,
        )
    }

    pub fn new_scoped(
        log_writer: LogWriter,
        approvals: Option<Arc<dyn ExecutorApprovalService>>,
        repo_context: RepoContext,
        commit_reminder_prompt: String,
        cancel: CancellationToken,
        permission_root: Option<PathBuf>,
    ) -> Arc<Self> {
        Arc::new(Self {
            log_writer,
            approvals,
            repo_context,
            commit_reminder_prompt,
            cancel,
            permission_root: permission_root.and_then(|root| root.canonicalize().ok()),
            native_permissions_qualified: AtomicBool::new(false),
        })
    }

    pub fn observe_runtime_version(&self, version: Option<&str>) {
        let qualified = version == Some(super::permission_boundary::QUALIFIED_VERSION);
        self.native_permissions_qualified
            .store(qualified, Ordering::Release);
        if !qualified {
            tracing::warn!(
                "Claude runtime not qualified for scoped edit authorization; retaining native Default owner fallback"
            );
        }
    }

    async fn handle_approval(
        &self,
        tool_use_id: String,
        tool_name: String,
        tool_input: serde_json::Value,
    ) -> Result<PermissionResult, ExecutorError> {
        let approval_service = self
            .approvals
            .as_ref()
            .filter(|service| service.supports_interactive_approvals())
            .ok_or(ExecutorApprovalError::ServiceUnavailable)?;

        let context = super::approval_context::summary(&tool_name, &tool_input);
        let approval_id = match approval_service
            .create_tool_approval_with_context(&tool_name, &context)
            .await
        {
            Ok(id) => id,
            Err(err) => {
                self.handle_approval_error(&tool_name, &tool_use_id, &err)
                    .await?;
                return Err(err.into());
            }
        };

        let _ = self
            .log_writer
            .log_raw(&serde_json::to_string(&ClaudeJson::ApprovalRequested {
                tool_call_id: tool_use_id.clone(),
                tool_name: tool_name.clone(),
                approval_id: approval_id.clone(),
            })?)
            .await;

        let status = match approval_service
            .wait_tool_approval(&approval_id, self.cancel.clone())
            .await
        {
            Ok(s) => s,
            Err(err) => {
                self.handle_approval_error(&tool_name, &tool_use_id, &err)
                    .await?;
                return Err(err.into());
            }
        };

        self.log_writer
            .log_raw(&serde_json::to_string(&ClaudeJson::ApprovalResponse {
                tool_call_id: tool_use_id.clone(),
                tool_name: tool_name.clone(),
                approval_status: status.clone(),
            })?)
            .await?;

        match status {
            ApprovalStatus::Approved => {
                if tool_name == EXIT_PLAN_MODE_NAME {
                    Ok(PermissionResult::Allow {
                        updated_input: tool_input,
                        updated_permissions: Some(vec![PermissionUpdate {
                            update_type: PermissionUpdateType::SetMode,
                            mode: Some(PermissionMode::Default),
                            destination: Some(PermissionUpdateDestination::Session),
                            rules: None,
                            behavior: None,
                            directories: None,
                        }]),
                    })
                } else {
                    Ok(PermissionResult::Allow {
                        updated_input: tool_input,
                        updated_permissions: None,
                    })
                }
            }
            ApprovalStatus::Denied { reason } => Ok(PermissionResult::Deny {
                message: format!("{}{}", TOOL_DENY_PREFIX, reason.unwrap_or_default()),
                interrupt: Some(false),
            }),
            ApprovalStatus::TimedOut => Ok(PermissionResult::Deny {
                message: "Approval request timed out".to_string(),
                interrupt: Some(true),
            }),
            ApprovalStatus::Pending => Ok(PermissionResult::Deny {
                message: "Approval still pending (unexpected)".to_string(),
                interrupt: Some(false),
            }),
        }
    }

    async fn handle_question(
        &self,
        tool_use_id: String,
        tool_name: String,
        tool_input: serde_json::Value,
    ) -> Result<PermissionResult, ExecutorError> {
        let approval_service = self
            .approvals
            .as_ref()
            .filter(|service| service.supports_interactive_approvals())
            .ok_or(ExecutorApprovalError::ServiceUnavailable)?;

        let question_count = tool_input
            .get("questions")
            .and_then(|q| q.as_array())
            .map(|a| a.len())
            .unwrap_or(1);

        let approval_id = match approval_service
            .create_question_approval(&tool_name, question_count)
            .await
        {
            Ok(id) => id,
            Err(err) => {
                self.handle_question_error(&tool_use_id, &tool_name, &err)
                    .await?;
                return Err(err.into());
            }
        };

        let _ = self
            .log_writer
            .log_raw(&serde_json::to_string(&ClaudeJson::ApprovalRequested {
                tool_call_id: tool_use_id.clone(),
                tool_name: tool_name.clone(),
                approval_id: approval_id.clone(),
            })?)
            .await;

        let status = match approval_service
            .wait_question_answer(&approval_id, self.cancel.clone())
            .await
        {
            Ok(s) => s,
            Err(err) => {
                self.handle_question_error(&tool_use_id, &tool_name, &err)
                    .await?;
                return Err(err.into());
            }
        };

        self.log_writer
            .log_raw(&serde_json::to_string(&ClaudeJson::QuestionResponse {
                tool_call_id: tool_use_id.clone(),
                tool_name: tool_name.clone(),
                question_status: status.clone(),
            })?)
            .await?;

        match status {
            QuestionStatus::Answered { answers } => {
                let answers_map: serde_json::Map<String, serde_json::Value> = answers
                    .iter()
                    .map(|qa| {
                        (
                            qa.question.clone(),
                            serde_json::Value::String(qa.answer.join(", ")),
                        )
                    })
                    .collect();
                let mut updated = tool_input.clone();
                if let Some(obj) = updated.as_object_mut() {
                    obj.insert(
                        "answers".to_string(),
                        serde_json::Value::Object(answers_map),
                    );
                }
                Ok(PermissionResult::Allow {
                    updated_input: updated,
                    updated_permissions: None,
                })
            }
            QuestionStatus::TimedOut => Ok(PermissionResult::Deny {
                message: "Question request timed out".to_string(),
                interrupt: Some(true),
            }),
        }
    }

    async fn handle_approval_error(
        &self,
        tool_name: &str,
        tool_use_id: &str,
        err: &ExecutorApprovalError,
    ) -> Result<(), ExecutorError> {
        if !matches!(err, ExecutorApprovalError::Cancelled) {
            tracing::error!(
                "Claude approval failed for tool={} call_id={}: {err}",
                tool_name,
                tool_use_id
            );
        }
        let _ = self
            .log_writer
            .log_raw(&serde_json::to_string(&ClaudeJson::ApprovalResponse {
                tool_call_id: tool_use_id.to_string(),
                tool_name: tool_name.to_string(),
                approval_status: ApprovalStatus::Denied {
                    reason: Some(format!("Approval service error: {err}")),
                },
            })?)
            .await;
        Ok(())
    }

    async fn handle_question_error(
        &self,
        tool_use_id: &str,
        tool_name: &str,
        err: &ExecutorApprovalError,
    ) -> Result<(), ExecutorError> {
        if !matches!(err, ExecutorApprovalError::Cancelled) {
            tracing::error!("Claude question failed {err}",);
        }
        let _ = self
            .log_writer
            .log_raw(&serde_json::to_string(&ClaudeJson::QuestionResponse {
                tool_call_id: tool_use_id.to_string(),
                tool_name: tool_name.to_string(),
                question_status: QuestionStatus::TimedOut,
            })?)
            .await;
        Ok(())
    }

    pub async fn on_can_use_tool(
        &self,
        tool_name: String,
        input: serde_json::Value,
        _permission_suggestions: Option<Vec<PermissionUpdate>>,
        tool_use_id: Option<String>,
    ) -> Result<PermissionResult, ExecutorError> {
        let tool_use_id = tool_use_id.filter(|id| !id.trim().is_empty());
        if tool_name == ASK_USER_QUESTION_NAME {
            if let Some(latest_tool_use_id) = tool_use_id {
                return self
                    .handle_question(latest_tool_use_id, tool_name, input)
                    .await;
            } else {
                tracing::warn!("AskUserQuestion without tool_use_id, cannot route to approval");
                return Ok(PermissionResult::Deny {
                    message:
                        "AskUserQuestion requires user interaction but no tool_use_id was provided"
                            .to_string(),
                    interrupt: Some(false),
                });
            }
        }
        if let Some(latest_tool_use_id) = tool_use_id {
            self.handle_approval(latest_tool_use_id, tool_name, input)
                .await
        } else {
            // Missing correlation cannot establish permission for a supervised
            // call. Keep it denied instead of silently bypassing the bridge.
            tracing::warn!(
                "No tool_use_id available for tool '{}', cannot request approval",
                tool_name
            );
            Ok(PermissionResult::Deny {
                message: "Cannot request approval without a tool_use_id".to_string(),
                interrupt: Some(false),
            })
        }
    }

    pub async fn on_hook_callback(
        &self,
        callback_id: String,
        input: serde_json::Value,
        tool_use_id: Option<String>,
    ) -> Result<serde_json::Value, ExecutorError> {
        // Stop hook git check - uses `decision` (approve/block) and `reason` fields
        if callback_id == STOP_GIT_CHECK_CALLBACK_ID {
            if input
                .get("stop_hook_active")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
            {
                return Ok(serde_json::json!({"decision": "approve"}));
            }
            let status = self.repo_context.check_uncommitted_changes().await;
            return Ok(if status.is_empty() {
                serde_json::json!({"decision": "approve"})
            } else {
                serde_json::json!({
                    "decision": "block",
                    "reason": format!("{}\n{}", self.commit_reminder_prompt, status)
                })
            });
        }

        if callback_id == super::permission_boundary::CALLBACK_ID {
            let event_id = input.get("tool_use_id").and_then(serde_json::Value::as_str);
            let correlated = tool_use_id
                .as_deref()
                .or(event_id)
                .is_some_and(|id| !id.trim().is_empty())
                && tool_use_id
                    .as_deref()
                    .zip(event_id)
                    .is_none_or(|(a, b)| a == b);
            if !correlated {
                return Ok(serde_json::json!({"hookSpecificOutput": {
                    "hookEventName":"PreToolUse", "permissionDecision":"deny",
                    "permissionDecisionReason":"Cannot correlate workspace edit authorization"
                }}));
            }
            if !self.native_permissions_qualified.load(Ordering::Acquire) {
                return Ok(serde_json::json!({}));
            }
            // This is a fast per-call scope check, never an owner wait or native
            // allow rule. Native explicit deny/ask evaluation still follows it.
            return Ok(
                if super::permission_boundary::allows_workspace_edit(
                    self.permission_root.as_deref(),
                    &input,
                ) {
                    serde_json::json!({"hookSpecificOutput": {
                        "hookEventName":"PreToolUse", "permissionDecision":"allow",
                        "permissionDecisionReason":"Routine edit within this execution's canonical workspace"
                    }})
                } else {
                    // Default mode will consult native rules/the owner. If this
                    // callback fails, the CLI also abstains: no grant remains behind.
                    serde_json::json!({})
                },
            );
        }
        if callback_id == "tool_approval" {
            // Registered only for questions and plan exits. Ordinary native
            // decisions are not promoted to manual approval by a blanket hook.
            Ok(serde_json::json!({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": "User interaction required"
                }
            }))
        } else {
            // Abstain, including obsolete auto-approve callbacks. Never grant
            // permission or override native deny/ask rules from an unknown hook.
            Ok(serde_json::json!({}))
        }
    }

    pub async fn log_message(&self, line: &str) -> Result<(), ExecutorError> {
        self.log_writer.log_raw(line).await
    }
}
