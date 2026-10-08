pub mod client;
pub mod delegation;
pub mod elicitation;
pub mod goals;
pub mod jsonrpc;
pub mod normalize_logs;
#[cfg(any(target_os = "linux", test))]
mod process_capacity;
pub mod review;
pub mod slash_commands;
use std::{
    collections::HashMap,
    env,
    path::{Path, PathBuf},
    str::FromStr,
    sync::Arc,
};

/// Returns the Codex home directory.
///
/// Checks the `CODEX_HOME` environment variable first, then falls back to `~/.codex`.
/// This allows users to configure a custom location for Codex configuration and state.
pub fn codex_home() -> Option<PathBuf> {
    if let Ok(codex_home) = env::var("CODEX_HOME")
        && !codex_home.trim().is_empty()
    {
        return Some(PathBuf::from(codex_home));
    }
    dirs::home_dir().map(|home| home.join(".codex"))
}

pub(crate) fn resolve_model(model: Option<&str>) -> (Option<&str>, bool) {
    match model.and_then(|m| m.strip_suffix("-fast")) {
        Some(base) => (Some(base), true),
        None => (model, false),
    }
}

fn host_blocks_unprivileged_userns() -> bool {
    if let Ok(value) = env::var("VK_ASSUME_USERNS_BLOCKED") {
        let value = value.trim().to_ascii_lowercase();
        if matches!(value.as_str(), "1" | "true" | "yes" | "on") {
            return true;
        }
        if matches!(value.as_str(), "0" | "false" | "no" | "off") {
            return false;
        }
    }

    std::fs::read_to_string("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
        .map(|value| value.trim() == "1")
        .unwrap_or(false)
}

fn effective_sandbox_mode(requested: Option<&SandboxMode>) -> Option<V2SandboxMode> {
    let requested = match requested {
        None | Some(SandboxMode::Auto) => V2SandboxMode::WorkspaceWrite,
        Some(SandboxMode::ReadOnly) => V2SandboxMode::ReadOnly,
        Some(SandboxMode::WorkspaceWrite) => V2SandboxMode::WorkspaceWrite,
        Some(SandboxMode::DangerFullAccess) => V2SandboxMode::DangerFullAccess,
    };

    if host_blocks_unprivileged_userns() && requested != V2SandboxMode::DangerFullAccess {
        tracing::warn!(
            "Host blocks unprivileged user namespaces; forcing Codex sandbox to danger-full-access"
        );
        Some(V2SandboxMode::DangerFullAccess)
    } else {
        Some(requested)
    }
}

pub(crate) fn fork_params_from(thread_id: String, params: ThreadStartParams) -> ThreadForkParams {
    ThreadForkParams {
        thread_id,
        model: params.model,
        model_provider: params.model_provider,
        cwd: params.cwd,
        approval_policy: params.approval_policy,
        sandbox: params.sandbox,
        config: params.config,
        base_instructions: params.base_instructions,
        developer_instructions: params.developer_instructions,
        service_tier: params.service_tier,
        ..Default::default()
    }
}

pub(crate) fn resume_params_from(
    thread_id: String,
    params: ThreadStartParams,
) -> ThreadResumeParams {
    ThreadResumeParams {
        thread_id,
        model: params.model,
        model_provider: params.model_provider,
        cwd: params.cwd,
        approval_policy: params.approval_policy,
        sandbox: params.sandbox,
        config: params.config,
        base_instructions: params.base_instructions,
        developer_instructions: params.developer_instructions,
        service_tier: params.service_tier,
        ..Default::default()
    }
}

pub(crate) fn is_unforkable_rollout_error(err: &ExecutorError) -> bool {
    let message = err.to_string();
    message.contains("no rollout found for thread id")
        || message.contains("empty session file")
        || message.contains("session not found")
}

fn env_flag_enabled(name: &str) -> bool {
    std::env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
}

pub(crate) fn codex_execution_disabled() -> bool {
    env_flag_enabled("VK_DISABLE_CODEX_EXECUTIONS")
        || env_flag_enabled("VK_LAB_DISABLE_CODEX_EXECUTIONS")
}

const DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS: usize = 8;

fn parse_codex_max_active_executions(value: Option<String>) -> Option<usize> {
    value
        .and_then(|value| value.trim().parse::<usize>().ok())
        .filter(|value| *value > 0)
}

fn codex_max_active_executions() -> usize {
    parse_codex_max_active_executions(std::env::var("VK_CODEX_MAX_ACTIVE_EXECUTIONS").ok())
        .or_else(|| {
            parse_codex_max_active_executions(
                std::env::var("VK_LAB_CODEX_MAX_ACTIVE_EXECUTIONS").ok(),
            )
        })
        .unwrap_or(DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS)
}

fn active_codex_execution_count() -> usize {
    if systemd_run::enabled() {
        return std::process::Command::new("systemctl")
            .args([
                "--user",
                "list-units",
                "vk-exec-codex-*.service",
                "--state=running",
                "--no-legend",
                "--no-pager",
                "--plain",
            ])
            .output()
            .ok()
            .filter(|output| output.status.success())
            .map(|output| {
                String::from_utf8_lossy(&output.stdout)
                    .lines()
                    .filter(|line| !line.trim().is_empty())
                    .count()
            })
            .unwrap_or(0);
    }

    #[cfg(target_os = "linux")]
    return process_capacity::app_server_count();

    #[cfg(not(target_os = "linux"))]
    std::process::Command::new("pgrep")
        .args(["-fc", "codex app-server"])
        .output()
        .ok()
        .filter(|output| output.status.success())
        .and_then(|output| {
            String::from_utf8_lossy(&output.stdout)
                .trim()
                .parse::<usize>()
                .ok()
        })
        .unwrap_or(0)
}

pub fn codex_execution_limit_error() -> Option<ExecutorError> {
    let max_active = codex_max_active_executions();
    let active = active_codex_execution_count().saturating_add(delegation::active_count());
    if active >= max_active {
        Some(ExecutorError::ExecutionLimitReached {
            active,
            limit: max_active,
        })
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        executors::{BaseCodingAgent, StandardCodingAgentExecutor},
        model_selector::PermissionPolicy,
        profile::ExecutorConfig,
    };

    #[test]
    fn codex_max_active_execution_parser_requires_positive_integer() {
        assert_eq!(
            parse_codex_max_active_executions(Some("12".into())),
            Some(12)
        );
        assert_eq!(
            parse_codex_max_active_executions(Some(" 8 ".into())),
            Some(8)
        );
        assert_eq!(parse_codex_max_active_executions(Some("0".into())), None);
        assert_eq!(parse_codex_max_active_executions(Some("-1".into())), None);
        assert_eq!(
            parse_codex_max_active_executions(Some("invalid".into())),
            None
        );
        assert_eq!(parse_codex_max_active_executions(None), None);
    }

    #[test]
    fn routed_overrides_reach_start_and_resume_parameters() {
        use crate::executors::StandardCodingAgentExecutor;
        let mut codex: Codex = serde_json::from_value(serde_json::json!({})).unwrap();
        let mut config = ExecutorConfig::new(crate::executors::BaseCodingAgent::Codex);
        config.model_id = Some("gpt-6.1-sol".into());
        config.reasoning_id = Some("medium".into());
        codex.apply_overrides(&config);
        let start = codex.build_thread_start_params(std::path::Path::new("/workspace"));
        assert_eq!(start.model.as_deref(), Some("gpt-6.1-sol"));
        assert_eq!(
            start.config.as_ref().unwrap()["model_reasoning_effort"],
            "medium"
        );
        let resumed = super::resume_params_from("existing-thread".into(), start);
        assert_eq!(resumed.thread_id, "existing-thread");
        assert_eq!(resumed.model.as_deref(), Some("gpt-6.1-sol"));
        assert_eq!(
            resumed.config.as_ref().unwrap()["model_reasoning_effort"],
            "medium"
        );
    }

    #[tokio::test]
    #[ignore = "One bounded real inference; requires explicit routing verification environment"]
    async fn routed_native_follow_up_acceptance() {
        use tokio::io::AsyncReadExt;

        use crate::{
            actions::{
                Executable, ExecutorAction, ExecutorActionType,
                coding_agent_follow_up::CodingAgentFollowUpRequest,
            },
            env::{ExecutionEnv, RepoContext},
            executors::{BaseCodingAgent, ExecutorExitResult},
            routing::{CapabilityFloor, RoutingMode, RoutingPolicy},
        };
        let dir = std::path::PathBuf::from(
            std::env::var("VK_ROUTING_TEST_DIR").expect("isolated fixture directory"),
        );
        let thread = std::env::var("VK_ROUTING_TEST_THREAD").expect("existing fixture thread");
        let before = std::fs::read(dir.join("dirty.txt")).unwrap();
        let mut config = ExecutorConfig::new(BaseCodingAgent::Codex);
        config.permission_policy = Some(crate::model_selector::PermissionPolicy::Supervised);
        config.routing = Some(Box::new(RoutingPolicy {
            mode: RoutingMode::Auto,
            floor: CapabilityFloor::Workhorse,
            denied_models: vec![],
            allow_escalation: false,
        }));
        let mut action = ExecutorAction::new(
            ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                capacity: None,
                prompt: "Use no tools and change no files. Reply exactly ROUTING_OK glacier spoon."
                    .into(),
                session_id: thread,
                reset_to_message_id: None,
                executor_config: config,
                working_dir: None,
            }),
            None,
        );
        crate::routing::resolve_action(&mut action, None, false).unwrap();
        assert_eq!(
            action
                .routing_decision
                .as_ref()
                .unwrap()
                .selected_model
                .as_deref(),
            Some("gpt-6.1-sol")
        );
        let env = ExecutionEnv::new(RepoContext::new(dir.clone(), vec![]), false, String::new());
        let mut child = action
            .spawn(
                &dir,
                std::sync::Arc::new(crate::approvals::NoopExecutorApprovalService {}),
                &env,
            )
            .await
            .unwrap();
        let mut stdout = child.child.inner().stdout.take().unwrap();
        let output = tokio::spawn(async move {
            let mut text = String::new();
            let _ = stdout.read_to_string(&mut text).await;
            text
        });
        let result = tokio::time::timeout(
            std::time::Duration::from_secs(90),
            child.exit_signal.take().unwrap(),
        )
        .await;
        if let Some(cancel) = child.cancel {
            cancel.cancel();
        }
        let _ = child.child.kill().await;
        let text = output.await.unwrap();
        std::fs::write(dir.join("vk-executor-protocol.jsonl"), &text).unwrap();
        assert!(
            matches!(result, Ok(Ok(ExecutorExitResult::Success))),
            "executor failed; inspect fixture protocol log"
        );
        assert!(text.contains("vk/routing") && text.contains("ROUTING_OK"));
        assert_eq!(std::fs::read(dir.join("dirty.txt")).unwrap(), before);
    }

    #[test]
    fn codex_auto_permission_override_exits_plan_mode() {
        let mut codex = Codex {
            append_prompt: AppendPrompt::default(),
            sandbox: None,
            ask_for_approval: Some(AskForApproval::OnRequest),
            oss: None,
            model: None,
            model_reasoning_effort: None,
            model_reasoning_summary: None,
            model_reasoning_summary_format: None,
            profile: None,
            base_instructions: None,
            include_apply_patch_tool: None,
            model_provider: None,
            compact_prompt: None,
            developer_instructions: None,
            plan: true,
            cmd: CmdOverrides::default(),
            approvals: None,
        };

        codex.apply_overrides(&ExecutorConfig {
            routing: None,
            executor: BaseCodingAgent::Codex,
            variant: Some("PLAN".to_string()),
            model_id: None,
            agent_id: None,
            reasoning_id: None,
            permission_policy: Some(PermissionPolicy::Auto),
        });

        assert!(!codex.plan);
        assert_eq!(codex.ask_for_approval, Some(AskForApproval::Never));
    }
}

use async_trait::async_trait;
use codex_app_server_protocol::{
    AskForApproval as V2AskForApproval, ReviewTarget, SandboxMode as V2SandboxMode,
    ThreadForkParams, ThreadResumeParams, ThreadStartParams, UserInput,
};
use codex_protocol::config_types::ServiceTier;
use derivative::Derivative;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use strum_macros::{AsRefStr, EnumString};
use tokio::process::Command;
use ts_rs::TS;
use uuid::Uuid;
use workspace_utils::{command_ext::GroupSpawnNoWindowExt, msg_store::MsgStore};

use self::{
    client::{AppServerClient, LogWriter},
    jsonrpc::{ExitSignalSender, JsonRpcPeer},
    normalize_logs::{Error, normalize_logs},
};
use crate::{
    approvals::ExecutorApprovalService,
    command::{CmdOverrides, CommandBuildError, CommandBuilder, CommandParts, apply_overrides},
    env::ExecutionEnv,
    executor_discovery::ExecutorDiscoveredOptions,
    executors::{
        AppendPrompt, AvailabilityInfo, BaseCodingAgent, ExecutorError, ExecutorExitResult,
        SlashCommandDescription, SpawnedChild, StandardCodingAgentExecutor,
    },
    logs::utils::patch,
    model_selector::{ModelInfo, ModelSelectorConfig, PermissionPolicy, ReasoningOption},
    profile::ExecutorConfig,
    stdout_dup::create_stdout_pipe_writer,
    systemd_run::{self, StdinMode},
};

/// Sandbox policy modes for Codex
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS, JsonSchema, AsRefStr)]
#[serde(rename_all = "kebab-case")]
#[strum(serialize_all = "kebab-case")]
pub enum SandboxMode {
    Auto,
    ReadOnly,
    WorkspaceWrite,
    DangerFullAccess,
}

/// Determines when the user is consulted to approve Codex actions.
///
/// - `UnlessTrusted`: Read-only commands are auto-approved. Everything else will
///   ask the user to approve.
/// - `OnFailure`: All commands run in a restricted sandbox initially. If a
///   command fails, the user is asked to approve execution without the sandbox.
/// - `OnRequest`: The model decides when to ask the user for approval.
/// - `Never`: Commands never ask for approval. Commands that fail in the
///   restricted sandbox are not retried.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS, JsonSchema, AsRefStr)]
#[serde(rename_all = "kebab-case")]
#[strum(serialize_all = "kebab-case")]
pub enum AskForApproval {
    UnlessTrusted,
    OnFailure,
    OnRequest,
    Never,
}

/// Reasoning effort for the underlying model
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS, JsonSchema, AsRefStr, EnumString)]
#[serde(rename_all = "kebab-case")]
#[strum(serialize_all = "kebab-case")]
pub enum ReasoningEffort {
    Low,
    Medium,
    High,
    Xhigh,
    Max,
}

/// Model reasoning summary style
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS, JsonSchema, AsRefStr)]
#[serde(rename_all = "kebab-case")]
#[strum(serialize_all = "kebab-case")]
pub enum ReasoningSummary {
    Auto,
    Concise,
    Detailed,
    None,
}

/// Format for model reasoning summaries
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS, JsonSchema, AsRefStr)]
#[serde(rename_all = "kebab-case")]
#[strum(serialize_all = "kebab-case")]
pub enum ReasoningSummaryFormat {
    None,
    Experimental,
}

enum CodexSessionAction {
    Chat { prompt: String },
    Review { target: ReviewTarget },
}

#[derive(Derivative, Clone, Serialize, Deserialize, TS, JsonSchema)]
#[derivative(Debug, PartialEq)]
pub struct Codex {
    #[serde(default)]
    pub append_prompt: AppendPrompt,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sandbox: Option<SandboxMode>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ask_for_approval: Option<AskForApproval>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub oss: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_reasoning_effort: Option<ReasoningEffort>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_reasoning_summary: Option<ReasoningSummary>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_reasoning_summary_format: Option<ReasoningSummaryFormat>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub base_instructions: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include_apply_patch_tool: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_provider: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub compact_prompt: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub developer_instructions: Option<String>,
    #[serde(default)]
    pub plan: bool,
    #[serde(flatten)]
    pub cmd: CmdOverrides,

    #[serde(skip)]
    #[ts(skip)]
    #[derivative(Debug = "ignore", PartialEq = "ignore")]
    approvals: Option<Arc<dyn ExecutorApprovalService>>,
}

#[async_trait]
impl StandardCodingAgentExecutor for Codex {
    fn apply_overrides(&mut self, executor_config: &ExecutorConfig) {
        if let Some(model_id) = &executor_config.model_id {
            self.model = Some(model_id.clone());
        }
        if let Some(reasoning_id) = &executor_config.reasoning_id
            && let Ok(reasoning_effort) = ReasoningEffort::from_str(reasoning_id)
        {
            self.model_reasoning_effort = Some(reasoning_effort)
        }
        if let Some(permission_policy) = &executor_config.permission_policy {
            match permission_policy {
                crate::model_selector::PermissionPolicy::Auto => {
                    self.ask_for_approval = Some(AskForApproval::Never);
                    self.plan = false;
                }
                crate::model_selector::PermissionPolicy::Supervised => {
                    if matches!(self.ask_for_approval, None | Some(AskForApproval::Never)) {
                        self.ask_for_approval = Some(AskForApproval::UnlessTrusted);
                    }
                    self.plan = false;
                }
                crate::model_selector::PermissionPolicy::Plan => {
                    self.plan = true;
                }
            }
        }
    }

    fn use_approvals(&mut self, approvals: Arc<dyn ExecutorApprovalService>) {
        self.approvals = Some(approvals);
    }

    async fn spawn(
        &self,
        current_dir: &Path,
        prompt: &str,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        self.spawn_slash_command(current_dir, prompt, None, env)
            .await
    }

    async fn spawn_follow_up(
        &self,
        current_dir: &Path,
        prompt: &str,
        session_id: &str,
        _reset_to_message_id: Option<&str>,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        self.spawn_slash_command(current_dir, prompt, Some(session_id), env)
            .await
    }

    fn normalize_logs(
        &self,
        msg_store: Arc<MsgStore>,
        worktree_path: &Path,
    ) -> Vec<tokio::task::JoinHandle<()>> {
        normalize_logs(msg_store, worktree_path)
    }

    fn default_mcp_config_path(&self) -> Option<PathBuf> {
        codex_home().map(|home| home.join("config.toml"))
    }

    fn get_availability_info(&self) -> AvailabilityInfo {
        if let Some(timestamp) = codex_home()
            .and_then(|home| std::fs::metadata(home.join("auth.json")).ok())
            .and_then(|m| m.modified().ok())
            .and_then(|modified| modified.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs() as i64)
        {
            return AvailabilityInfo::LoginDetected {
                last_auth_timestamp: timestamp,
            };
        }

        let mcp_config_found = self
            .default_mcp_config_path()
            .map(|p| p.exists())
            .unwrap_or(false);

        let installation_indicator_found = codex_home()
            .map(|home| home.join("version.json").exists())
            .unwrap_or(false);

        if mcp_config_found || installation_indicator_found {
            AvailabilityInfo::InstallationFound
        } else {
            AvailabilityInfo::NotFound
        }
    }

    fn get_preset_options(&self) -> ExecutorConfig {
        use crate::model_selector::*;
        let permission_policy = if self.plan {
            PermissionPolicy::Plan
        } else if matches!(self.ask_for_approval, None | Some(AskForApproval::Never)) {
            PermissionPolicy::Auto
        } else {
            PermissionPolicy::Supervised
        };

        ExecutorConfig {
            routing: None,
            executor: BaseCodingAgent::Codex,
            variant: None,
            model_id: self.model.clone(),
            agent_id: None,
            reasoning_id: self
                .model_reasoning_effort
                .as_ref()
                .map(|e| e.as_ref().to_string()),
            permission_policy: Some(permission_policy),
        }
    }

    async fn discover_options(
        &self,
        _workdir: Option<&std::path::Path>,
        _repo_path: Option<&std::path::Path>,
    ) -> Result<futures::stream::BoxStream<'static, json_patch::Patch>, ExecutorError> {
        let max_reasoning_options = ReasoningOption::from_names(
            [
                ReasoningEffort::Low,
                ReasoningEffort::Medium,
                ReasoningEffort::High,
                ReasoningEffort::Xhigh,
                ReasoningEffort::Max,
            ]
            .map(|e| e.as_ref().to_string()),
        );

        let mut options = ExecutorDiscoveredOptions {
            model_selector: ModelSelectorConfig {
                supports_routing: Some(true),
                models: vec![
                    ModelInfo {
                        id: "gpt-5.6-sol".to_string(),
                        name: "GPT-5.6 Sol".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.6-terra".to_string(),
                        name: "GPT-5.6 Terra".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.6-luna".to_string(),
                        name: "GPT-5.6 Luna".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.5".to_string(),
                        name: "GPT-5.5".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.5-fast".to_string(),
                        name: "GPT-5.5 Fast".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.4".to_string(),
                        name: "GPT-5.4".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.4-mini".to_string(),
                        name: "GPT-5.4 Mini".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.4-fast".to_string(),
                        name: "GPT-5.4 Fast".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.3-codex-spark".to_string(),
                        name: "GPT-5.3 Codex Spark".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.3-codex".to_string(),
                        name: "GPT-5.3 Codex".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.2-codex".to_string(),
                        name: "GPT-5.2 Codex".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.2".to_string(),
                        name: "GPT-5.2".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options.clone(),
                    },
                    ModelInfo {
                        id: "gpt-5.1-codex-max".to_string(),
                        name: "GPT-5.1 Codex Max".to_string(),
                        provider_id: None,
                        reasoning_options: max_reasoning_options,
                    },
                ],
                permissions: vec![
                    PermissionPolicy::Auto,
                    PermissionPolicy::Supervised,
                    PermissionPolicy::Plan,
                ],
                ..Default::default()
            },
            slash_commands: vec![
                SlashCommandDescription {
                    name: "goal".to_string(),
                    description: Some("autonomous objective; /goal status, pause, or resume".to_string()),
                },
                SlashCommandDescription {
                    name: "compact".to_string(),
                    description: Some(
                        "summarize conversation to prevent hitting the context limit".to_string(),
                    ),
                },
                SlashCommandDescription {
                    name: "init".to_string(),
                    description: Some(
                        "create an AGENTS.md file with instructions for Codex".to_string(),
                    ),
                },
                SlashCommandDescription {
                    name: "status".to_string(),
                    description: Some(
                        "show current session configuration and token usage".to_string(),
                    ),
                },
                SlashCommandDescription {
                    name: "mcp".to_string(),
                    description: Some("list configured MCP tools".to_string()),
                },
                SlashCommandDescription {
                    name: "fast".to_string(),
                    description: Some(
                        "toggle fast mode for highest speed inference (2× plan usage). Use `/fast on` or `/fast off` to set explicitly".to_string(),
                    ),
                },
            ],
            ..Default::default()
        };
        // Released/represented entries are visible even during an account rollout.
        // Discovery is advisory; only verified entries can be selected automatically.
        if let Ok(models) = crate::routing::model_policies() {
            let availability = crate::routing::load_availability().ok();
            for model in models {
                if options
                    .model_selector
                    .models
                    .iter()
                    .any(|m| m.id == model.id)
                {
                    continue;
                }
                let efforts = availability
                    .as_ref()
                    .and_then(|a| a.models.iter().find(|m| m.id == model.id))
                    .map(|m| {
                        if m.discovered {
                            m.supported_efforts.clone()
                        } else {
                            m.verified_efforts.clone()
                        }
                    })
                    .unwrap_or_else(|| model.efforts.clone());
                options.model_selector.models.push(ModelInfo {
                    name: model.id.clone(),
                    id: model.id,
                    provider_id: None,
                    reasoning_options: ReasoningOption::from_names(
                        efforts
                            .into_iter()
                            .filter(|e| ReasoningEffort::from_str(e).is_ok()),
                    ),
                });
            }
        }
        Ok(Box::pin(futures::stream::once(async move {
            patch::executor_discovered_options(options)
        })))
    }

    async fn spawn_review(
        &self,
        current_dir: &Path,
        prompt: &str,
        session_id: Option<&str>,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        let command_parts = self.build_command_builder()?.build_initial()?;
        let review_target = ReviewTarget::Custom {
            instructions: prompt.to_string(),
        };
        let action = CodexSessionAction::Review {
            target: review_target,
        };
        self.spawn_inner(current_dir, command_parts, action, session_id, env)
            .await
    }
}

impl Codex {
    pub fn base_command() -> String {
        std::env::var("VK_CODEX_BASE_COMMAND")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "codex".to_string())
    }

    fn build_command_builder(&self) -> Result<CommandBuilder, CommandBuildError> {
        let mut builder = CommandBuilder::new(Self::base_command());
        builder = builder.extend_params(["app-server"]);
        if self.oss.unwrap_or(false) {
            builder = builder.extend_params(["--oss"]);
        }

        apply_overrides(builder, &self.cmd)
    }

    fn build_thread_start_params(&self, cwd: &Path) -> ThreadStartParams {
        let sandbox = effective_sandbox_mode(self.sandbox.as_ref());

        let approval_policy = match self.ask_for_approval.as_ref() {
            None if matches!(self.sandbox.as_ref(), None | Some(SandboxMode::Auto)) => {
                // match the Auto preset in codex
                Some(V2AskForApproval::OnRequest)
            }
            None => None,
            Some(AskForApproval::UnlessTrusted) => Some(V2AskForApproval::UnlessTrusted),
            Some(AskForApproval::OnFailure) => Some(V2AskForApproval::OnFailure),
            Some(AskForApproval::OnRequest) => Some(V2AskForApproval::OnRequest),
            Some(AskForApproval::Never) => Some(V2AskForApproval::Never),
        };

        let mut config = self.build_config_overrides();
        // V1 top-level params that moved into config overrides in v2
        if let Some(profile) = &self.profile {
            config
                .get_or_insert_with(HashMap::new)
                .insert("profile".to_string(), Value::String(profile.clone()));
        }
        if let Some(include) = self.include_apply_patch_tool {
            config
                .get_or_insert_with(HashMap::new)
                .insert("include_apply_patch_tool".to_string(), Value::Bool(include));
        }
        if let Some(compact) = &self.compact_prompt {
            config
                .get_or_insert_with(HashMap::new)
                .insert("compact_prompt".to_string(), Value::String(compact.clone()));
        }
        if !matches!(approval_policy, None | Some(V2AskForApproval::Never)) {
            let map = config.get_or_insert_with(HashMap::new);
            map.insert(
                "features.default_mode_request_user_input".to_string(),
                Value::Bool(true),
            );
            map.insert(
                "suppress_unstable_features_warning".to_string(),
                Value::Bool(true),
            );
        }

        let (model, is_fast) = resolve_model(self.model.as_deref());
        let service_tier = if is_fast {
            Some(Some(ServiceTier::Fast))
        } else {
            None
        };

        ThreadStartParams {
            model: model.map(|m| m.to_string()),
            cwd: Some(cwd.to_string_lossy().to_string()),
            approval_policy,
            sandbox,
            config,
            base_instructions: self.base_instructions.clone(),
            model_provider: self.model_provider.clone(),
            developer_instructions: Some(format!(
                "{}\n\n{}",
                self.developer_instructions.as_deref().unwrap_or_default(),
                goals::INSTRUCTIONS
            )),
            dynamic_tools: Some(vec![goals::tool_spec()]),
            service_tier,
            ..Default::default()
        }
    }

    fn build_config_overrides(&self) -> Option<HashMap<String, Value>> {
        let mut overrides = HashMap::new();

        if let Some(effort) = &self.model_reasoning_effort {
            overrides.insert(
                "model_reasoning_effort".to_string(),
                Value::String(effort.as_ref().to_string()),
            );
        }

        if let Some(summary) = &self.model_reasoning_summary {
            overrides.insert(
                "model_reasoning_summary".to_string(),
                Value::String(summary.as_ref().to_string()),
            );
        }

        if let Some(format) = &self.model_reasoning_summary_format
            && format != &ReasoningSummaryFormat::None
        {
            overrides.insert(
                "model_reasoning_summary_format".to_string(),
                Value::String(format.as_ref().to_string()),
            );
        }

        if overrides.is_empty() {
            None
        } else {
            Some(overrides)
        }
    }

    async fn spawn_inner(
        &self,
        current_dir: &Path,
        command_parts: CommandParts,
        action: CodexSessionAction,
        resume_session: Option<&str>,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        let mut params = self.build_thread_start_params(current_dir);
        let routing = env
            .get("VK_ROUTING_DECISION")
            .map(|json| serde_json::from_str::<crate::routing::RoutingDecision>(json))
            .transpose()?;
        if routing
            .as_ref()
            .is_some_and(|d| d.mode == crate::routing::RoutingMode::Auto)
        {
            params.service_tier = Some(None); // Explicitly clear a resumed Fast setting.
        }
        if routing
            .as_ref()
            .is_some_and(|d| d.mode != crate::routing::RoutingMode::Manual)
            && env.capacity.is_none()
        {
            for feature in ["multi_agent", "multi_agent_v2"] {
                params
                    .config
                    .get_or_insert_default()
                    .insert(format!("features.{feature}"), serde_json::json!(false));
            }
            params
                .dynamic_tools
                .get_or_insert_default()
                .push(delegation::tool_spec());
            params.developer_instructions = Some(format!(
                "{}\n\n{}",
                params.developer_instructions.as_deref().unwrap_or_default(),
                delegation::INSTRUCTIONS
            ));
        }
        let resume_session = resume_session.map(|s| s.to_string());
        let telemetry_env = env.clone();

        self.spawn_app_server(
            current_dir,
            command_parts,
            env,
            move |client, _| async move {
                match action {
                    CodexSessionAction::Chat { prompt } => {
                        Self::launch_codex_agent(
                            params,
                            resume_session,
                            prompt,
                            client,
                            routing,
                            &telemetry_env,
                        )
                        .await
                    }
                    CodexSessionAction::Review { target } => {
                        review::launch_codex_review(params, resume_session, target, client).await
                    }
                }
            },
        )
        .await
    }

    async fn launch_codex_agent(
        thread_start_params: ThreadStartParams,
        resume_session: Option<String>,
        combined_prompt: String,
        client: Arc<AppServerClient>,
        routing: Option<crate::routing::RoutingDecision>,
        telemetry_env: &ExecutionEnv,
    ) -> Result<(), ExecutorError> {
        let child_params = thread_start_params.clone();
        let account = client.get_account().await?;
        if account.requires_openai_auth && account.account.is_none() {
            return Err(ExecutorError::AuthRequired(
                "Codex authentication required".to_string(),
            ));
        }

        if let Some(decision) = &routing
            && decision.mode == crate::routing::RoutingMode::Auto
        {
            client.lock_routed_model();
            let identity = serde_json::to_value(&account.account)?;
            if identity["type"] != "chatgpt" || identity["email"].as_str().is_none_or(str::is_empty)
            {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Automatic routing requires a verifiable signed-in Work/Codex account",
                )));
            }
            let fingerprint = crate::routing::account_fingerprint(&identity);
            if decision.account_fingerprint.as_deref() != Some(fingerprint.as_str()) {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Routing account changed; refresh executable-model verification",
                )));
            }
        }
        let (thread_id, resolved_model, resolved_effort, resolved_tier, resolved_provider) =
            match resume_session {
                None => {
                    let response = client.thread_start(thread_start_params).await?;
                    (
                        response.thread.id,
                        response.model,
                        response.reasoning_effort,
                        response.service_tier,
                        response.model_provider,
                    )
                }
                Some(session_id) => {
                    let response = client
                        .thread_resume(resume_params_from(session_id, thread_start_params))
                        .await?;
                    tracing::debug!("resumed thread_id={}", response.thread.id);
                    (
                        response.thread.id,
                        response.model,
                        response.reasoning_effort,
                        response.service_tier,
                        response.model_provider,
                    )
                }
            };

        if let Some(decision) = &routing
            && decision.mode == crate::routing::RoutingMode::Auto
        {
            let effort = serde_json::to_value(resolved_effort)?;
            if decision.selected_model.as_deref() != Some(resolved_model.as_str())
                || decision.selected_effort.as_deref() != effort.as_str()
                || resolved_tier.is_some()
                || resolved_provider != "openai"
            {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Codex did not apply routed model/effort/standard tier; stopped before inference",
                )));
            }
            if let Some(effort) = resolved_effort {
                client.set_routed_effort(effort);
            }
            tracing::info!(routing_decision_id = %decision.id, native_thread_id = %thread_id,
                model = %resolved_model, effort = %effort, "Routed Codex settings verified");
        }
        if let Some(decision) = &routing {
            client
                .log_writer()
                .log_raw(
                    &serde_json::json!({
                        "method": "vk/routing",
                        "params": { "decision": decision, "native_thread_id": thread_id,
                            "resolved_model": resolved_model, "resolved_effort": resolved_effort,
                            "resolved_service_tier": resolved_tier }
                    })
                    .to_string(),
                )
                .await?;
        }
        if let Some(effort) = resolved_effort {
            client.set_routed_effort(effort);
        }
        if let Some(binding) = crate::routing_telemetry::NativeBinding::new(
            telemetry_env,
            routing.as_ref(),
            serde_json::json!({
                "model": resolved_model, "reasoningEffort": resolved_effort,
                "serviceTier": resolved_tier,
            }),
        ) {
            client.set_routing_telemetry(binding);
        }
        if let Some(decision) = routing
            .as_ref()
            .filter(|d| d.mode != crate::routing::RoutingMode::Manual)
            && telemetry_env.capacity.is_none()
            && let Some(policy) = telemetry_env.get("VK_ROUTING_POLICY")
        {
            let config = client
                .goal_request("config/read", serde_json::json!({"includeLayers": false}))
                .await?;
            let max = config
                .pointer("/config/agents/max_concurrent_threads_per_session")
                .and_then(serde_json::Value::as_u64)
                .unwrap_or(4)
                .saturating_sub(1) as usize;
            let max = std::env::var("VK_CODEX_MAX_CHILDREN")
                .ok()
                .and_then(|v| v.parse::<usize>().ok())
                .map_or(max, |n| n.min(max));
            let inherited = serde_json::json!({"model": resolved_model, "reasoningEffort":resolved_effort,"accountFingerprint":crate::routing::account_fingerprint(&serde_json::to_value(&account.account)?)});
            match delegation::Delegation::new(
                serde_json::from_str(policy)?,
                decision.clone(),
                thread_id.clone(),
                child_params,
                telemetry_env.clone(),
                inherited,
                max,
            )
            .await
            {
                Ok(control) => client.set_delegation(control),
                Err(error) => {
                    tracing::warn!(%error, "Delegation unavailable; parent execution remains usable");
                    slash_commands::log_event_raw(
                        client.log_writer(),
                        format!("AutoSwitch delegation unavailable: {error}"),
                    )
                    .await?;
                }
            }
        }
        client.set_resolved_model(resolved_model);
        client.register_session(&thread_id).await?;
        client.refresh_goal().await?;
        let collaboration_mode = client.initial_collaboration_mode()?;
        client
            .turn_start_with_mode(
                thread_id.to_string(),
                vec![UserInput::Text {
                    text: combined_prompt,
                    text_elements: vec![],
                }],
                Some(collaboration_mode),
            )
            .await?;

        Ok(())
    }

    /// Common boilerplate for spawning a Codex app server process
    /// Handles process spawning, stdout/stderr piping, exit signal handling, client initialization, and error logging.
    /// Delegates the actual Codex session logic to the provided `task` closure.
    async fn spawn_app_server<F, Fut>(
        &self,
        current_dir: &Path,
        command_parts: CommandParts,
        env: &ExecutionEnv,
        task: F,
    ) -> Result<SpawnedChild, ExecutorError>
    where
        F: FnOnce(Arc<AppServerClient>, ExitSignalSender) -> Fut + Send + 'static,
        Fut: std::future::Future<Output = Result<(), ExecutorError>> + Send + 'static,
    {
        if codex_execution_disabled() {
            return Err(ExecutorError::Io(std::io::Error::other(
                "Codex executions are disabled by VK_DISABLE_CODEX_EXECUTIONS",
            )));
        }

        if let Some(error) = codex_execution_limit_error() {
            return Err(error);
        }

        let (program_path, mut args) = command_parts.into_resolved().await?;
        if env
            .get("VK_ROUTING_DECISION")
            .and_then(|v| serde_json::from_str::<crate::routing::RoutingDecision>(v).ok())
            .is_some_and(|d| d.mode != crate::routing::RoutingMode::Manual)
        {
            for feature in ["multi_agent", "multi_agent_v2"] {
                args.extend(["-c".into(), format!("features.{feature}=false")]);
            }
        }
        if env.capacity.is_some() {
            crate::capacity::policy::verify_launcher(
                self.cmd.base_command_override.as_deref(),
                &Self::base_command(),
            )?;
            // Some native tool families are initialized at process startup,
            // before thread config overrides. Restrict both layers.
            for feature in crate::capacity::policy::DISABLED_FEATURES {
                args.extend(["-c".to_string(), format!("features.{feature}=false")]);
            }
            args.extend([
                "-c".into(),
                "agents.max_depth=0".into(),
                "-c".into(),
                "agents.max_concurrent_threads_per_session=1".into(),
            ]);
        }

        let mut effective_env = env.clone().with_profile(&self.cmd);
        if let Some(capacity) = effective_env.capacity.clone() {
            if let Some(root) = crate::capacity::policy::configured_build_roots(&capacity)?.first()
            {
                // Compilers need a writable temporary directory too. Only the
                // scheduled process receives this override, never ordinary work.
                effective_env.insert("TMPDIR", root.clone());
            }
            if let Some(home) = effective_env.get("CODEX_HOME") {
                let expected = codex_home().ok_or_else(|| {
                    ExecutorError::Io(std::io::Error::other("Codex home is unavailable"))
                })?;
                if std::fs::canonicalize(home)? != std::fs::canonicalize(expected)? {
                    return Err(ExecutorError::Io(std::io::Error::other(
                        "Scheduled goals must use the supervised Codex account home",
                    )));
                }
            }
            if effective_env
                .get("VK_EXECUTION_PROCESS_ID")
                .map(String::as_str)
                != Some(capacity.lease.execution_id.as_str())
            {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Capacity execution identity cannot be overridden by a profile",
                )));
            }
        }
        let mut transient_unit_name = None;
        let mut child = if systemd_run::enabled() {
            let mut env_vars = effective_env.vars.clone();
            for key in [
                "PATH",
                "HOME",
                "CODEX_HOME",
                "SHELL",
                "BASH_ENV",
                "VK_CODEX_BASE_COMMAND",
            ] {
                if !env_vars.contains_key(key)
                    && let Ok(value) = std::env::var(key)
                {
                    env_vars.insert(key.to_string(), value);
                }
            }
            env_vars.insert("NPM_CONFIG_LOGLEVEL".to_string(), "error".to_string());
            env_vars.insert("NODE_NO_WARNINGS".to_string(), "1".to_string());
            env_vars.insert("NO_COLOR".to_string(), "1".to_string());
            env_vars.insert("RUST_LOG".to_string(), "error".to_string());
            let unit_name = if let Some(capacity) = &effective_env.capacity {
                crate::capacity::unit_name(
                    Uuid::parse_str(&capacity.lease.execution_id).map_err(std::io::Error::other)?,
                )
            } else {
                systemd_run::build_unit_name("codex")
            };
            transient_unit_name = Some(unit_name.clone());
            if let Some(capacity) = &effective_env.capacity {
                systemd_run::spawn_capacity_unit(
                    &unit_name,
                    current_dir,
                    &program_path,
                    &args,
                    &env_vars,
                    capacity,
                )?
            } else {
                systemd_run::spawn_transient_unit(
                    &unit_name,
                    "VK Codex execution",
                    current_dir,
                    &program_path,
                    &args,
                    &env_vars,
                    StdinMode::Piped,
                )?
            }
        } else {
            if effective_env.capacity.is_some() {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Capacity execution requires systemd",
                )));
            }
            let mut process = Command::new(program_path);
            process
                .kill_on_drop(true)
                .stdin(std::process::Stdio::piped())
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped())
                .current_dir(current_dir)
                .env("NPM_CONFIG_LOGLEVEL", "error")
                .env("NODE_NO_WARNINGS", "1")
                .env("NO_COLOR", "1")
                .env("RUST_LOG", "error")
                .args(&args);

            effective_env.apply_to_command(&mut process);

            process.group_spawn_no_window()?
        };

        let child_stdout = child.inner().stdout.take().ok_or_else(|| {
            ExecutorError::Io(std::io::Error::other("Codex app server missing stdout"))
        })?;
        let child_stdin = child.inner().stdin.take().ok_or_else(|| {
            ExecutorError::Io(std::io::Error::other("Codex app server missing stdin"))
        })?;

        let new_stdout = create_stdout_pipe_writer(&mut child)?;
        let (exit_signal_tx, exit_signal_rx) = tokio::sync::oneshot::channel();
        let cancel = tokio_util::sync::CancellationToken::new();

        let auto_approve = matches!(
            (&self.sandbox, &self.ask_for_approval),
            (Some(SandboxMode::DangerFullAccess), None)
        );
        let plan_mode = self.plan;
        let approvals = self.approvals.clone();
        let repo_context = env.repo_context.clone();
        let commit_reminder = env.commit_reminder;
        let commit_reminder_prompt = env.commit_reminder_prompt.clone();
        let execution_process_id = effective_env
            .get("VK_EXECUTION_PROCESS_ID")
            .and_then(|value| Uuid::parse_str(value).ok());
        let cancel_for_task = cancel.clone();
        let capacity_for_task = effective_env.capacity.clone();

        tokio::spawn(async move {
            let exit_signal_tx = ExitSignalSender::new(exit_signal_tx);
            let log_writer = LogWriter::new(new_stdout);

            // Initialize the AppServerClient
            let client = AppServerClient::new(
                log_writer.clone(),
                approvals,
                auto_approve,
                plan_mode,
                repo_context,
                commit_reminder,
                commit_reminder_prompt,
                cancel_for_task.clone(),
            );
            let rpc_peer = JsonRpcPeer::spawn(
                child_stdin,
                child_stdout,
                client.clone(),
                exit_signal_tx.clone(),
                cancel_for_task,
            );
            client.connect(rpc_peer);
            if let Some(execution_process_id) = execution_process_id {
                AppServerClient::register_active_execution(execution_process_id, &client);
            }

            let scheduled = capacity_for_task.is_some();
            let result = async {
                client.initialize().await?;
                client.set_exit_signal(exit_signal_tx.clone());
                if let Some(capacity) = capacity_for_task {
                    client.watch_capacity(capacity);
                }
                task(client, exit_signal_tx.clone()).await
            }
            .await;
            if result.is_err()
                && let Some(execution_process_id) = execution_process_id
            {
                AppServerClient::unregister_active_execution(execution_process_id);
            }

            if let Err(err) = result {
                if scheduled && let Some(execution) = execution_process_id {
                    crate::capacity::controller::record_launch_failure(execution, &err.to_string())
                        .await;
                }
                match &err {
                    ExecutorError::Io(io_err)
                        if io_err.kind() == std::io::ErrorKind::BrokenPipe =>
                    {
                        // Broken pipe likely means the parent process exited, so we can ignore it
                        return;
                    }
                    ExecutorError::AuthRequired(message) => {
                        log_writer
                            .log_raw(&Error::auth_required(message.clone()).raw())
                            .await
                            .ok();
                        exit_signal_tx
                            .send_exit_signal(ExecutorExitResult::Failure)
                            .await;
                        return;
                    }
                    _ => {
                        tracing::error!("Codex spawn error: {}", err);
                        log_writer
                            .log_raw(&Error::launch_error(err.to_string()).raw())
                            .await
                            .ok();
                    }
                }
                exit_signal_tx
                    .send_exit_signal(ExecutorExitResult::Failure)
                    .await;
            }
        });

        Ok(SpawnedChild {
            child,
            transient_unit_name,
            exit_signal: Some(exit_signal_rx),
            cancel: Some(cancel),
        })
    }
}
