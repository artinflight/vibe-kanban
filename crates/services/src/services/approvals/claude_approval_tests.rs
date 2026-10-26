//! Offline production Claude -> Vibe bridge tests. No CLI/model or outbound call.
use std::{sync::Arc, time::Duration};

use executors::{
    approvals::ExecutorApprovalService,
    env::RepoContext,
    executors::{
        claude::{client::ClaudeAgentClient, types::PermissionResult},
        codex::client::LogWriter,
    },
};
use serde_json::json;
use tokio::sync::RwLock;
use tokio_util::sync::CancellationToken;
use utils::approvals::{ApprovalResponse, ApprovalStatus};
use uuid::Uuid;

use super::{Approvals, executor_approvals::ExecutorApprovalBridge};
use crate::services::{config::Config, notification::NotificationService};

async fn bridge() -> (Approvals, Arc<ExecutorApprovalBridge>, Uuid) {
    let approvals = Approvals::new();
    let execution = Uuid::new_v4();
    let mut config = Config::default();
    config.notifications.sound_enabled = false;
    config.notifications.push_enabled = false;
    let bridge = ExecutorApprovalBridge::new(
        approvals.clone(),
        db::DBService {
            pool: sqlx::sqlite::SqlitePoolOptions::new()
                .connect("sqlite::memory:")
                .await
                .unwrap(),
        },
        NotificationService::new(Arc::new(RwLock::new(config))),
        execution,
    );
    (approvals, bridge, execution)
}

#[tokio::test]
async fn claude_preview_keeps_real_approve_deny_and_timeout_request_bound() {
    for status in [
        ApprovalStatus::Approved,
        ApprovalStatus::Denied {
            reason: Some("Outside authorization".into()),
        },
        ApprovalStatus::TimedOut,
    ] {
        let (approvals, bridge, execution) = bridge().await;
        let cancel = CancellationToken::new();
        let client = ClaudeAgentClient::new(
            LogWriter::new(tokio::io::sink()),
            Some(bridge),
            RepoContext::default(),
            String::new(),
            cancel,
        );
        let input = json!({"command":"ls -lh ./art-candidates", "description":"Read existing review files"});
        let original_input = input.clone();
        let task =
            tokio::spawn(async move {
                client
                .on_can_use_tool(
                    "Bash".into(),
                    input,
                    Some(serde_json::from_value(json!([{
                        "type":"setMode", "mode":"bypassPermissions", "destination":"session"
                    }])).unwrap()),
                    Some("synthetic-tool-call".into()),
                )
                .await
            });
        let pending = tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                let infos = approvals.pending_infos();
                if infos.len() == 1 {
                    break infos[0].clone();
                }
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
        assert!(!task.is_finished(), "A preview must never grant permission");
        assert_eq!(pending.tool_name, "Bash");
        assert_eq!(pending.execution_process_id, execution);
        assert!(
            pending
                .mcp_consent
                .unwrap()
                .contains("ls -lh ./art-candidates")
        );
        assert!(
            approvals
                .respond(
                    &pending.approval_id,
                    ApprovalResponse {
                        execution_process_id: Uuid::new_v4(),
                        status: utils::approvals::ApprovalOutcome::Approved
                    }
                )
                .await
                .is_err()
        );
        assert!(!task.is_finished());
        let outcome = serde_json::from_value(serde_json::to_value(&status).unwrap()).unwrap();
        approvals
            .respond(
                &pending.approval_id,
                ApprovalResponse {
                    execution_process_id: execution,
                    status: outcome,
                },
            )
            .await
            .unwrap();
        let result = tokio::time::timeout(Duration::from_secs(5), task)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        match (&status, result) {
            (
                ApprovalStatus::Approved,
                PermissionResult::Allow {
                    updated_input,
                    updated_permissions,
                },
            ) => {
                assert_eq!(updated_input, original_input);
                assert!(
                    updated_permissions.is_none(),
                    "No persistent/native permission rule may be inferred"
                );
            }
            (ApprovalStatus::Denied { .. }, PermissionResult::Deny { .. })
            | (ApprovalStatus::TimedOut, PermissionResult::Deny { .. }) => {}
            _ => panic!("Unexpected permission result"),
        }
        assert!(approvals.pending_infos().is_empty());
    }
}

#[tokio::test]
async fn claude_sensitive_preview_is_withheld_without_altering_invocation_or_review() {
    let (approvals, bridge, execution) = bridge().await;
    let client = ClaudeAgentClient::new(
        LogWriter::new(tokio::io::sink()),
        Some(bridge),
        RepoContext::default(),
        String::new(),
        CancellationToken::new(),
    );
    let task = tokio::spawn(async move {
        client.on_can_use_tool("Bash".into(), json!({"command":"curl -H 'Authorization: Bearer test-only-private-value' https://example.test"}), None, Some("synthetic-private".into())).await
    });
    let pending = tokio::time::timeout(Duration::from_secs(5), async {
        loop {
            if let Some(info) = approvals.pending_infos().into_iter().next() {
                break info;
            }
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    let preview = pending.mcp_consent.unwrap();
    assert!(!preview.contains("test-only-private-value"));
    assert!(preview.contains("withheld"));
    assert!(!task.is_finished());
    approvals
        .respond(
            &pending.approval_id,
            ApprovalResponse {
                execution_process_id: execution,
                status: utils::approvals::ApprovalOutcome::Denied { reason: None },
            },
        )
        .await
        .unwrap();
    assert!(matches!(
        task.await.unwrap().unwrap(),
        PermissionResult::Deny { .. }
    ));
}

#[tokio::test]
async fn claude_preview_bridge_rejects_invalid_context_before_creating_request() {
    let (approvals, bridge, _) = bridge().await;
    for context in ["".to_owned(), "x".repeat(16_385)] {
        assert!(
            bridge
                .create_tool_approval_with_context("Bash", &context)
                .await
                .is_err()
        );
    }
    assert!(approvals.pending_infos().is_empty());
}

#[tokio::test]
async fn claude_supervised_missing_tool_id_never_grants_permission() {
    let (approvals, bridge, _) = bridge().await;
    let client = ClaudeAgentClient::new(
        LogWriter::new(tokio::io::sink()),
        Some(bridge),
        RepoContext::default(),
        String::new(),
        CancellationToken::new(),
    );
    let result = client
        .on_can_use_tool("Bash".into(), json!({"command":"ls ./docs"}), None, None)
        .await
        .unwrap();
    assert!(matches!(
        result,
        PermissionResult::Deny {
            interrupt: Some(false),
            ..
        }
    ));
    assert!(
        approvals.pending_infos().is_empty(),
        "Do not create an uncorrelated request or job"
    );
    let hook = client
        .on_hook_callback("tool_approval".into(), json!({}), None)
        .await
        .unwrap();
    assert_eq!(
        hook["hookSpecificOutput"]["permissionDecision"], "ask",
        "Questions and plan exits retain explicit owner interaction"
    );
}

#[tokio::test]
async fn claude_native_fallback_without_interactive_owner_fails_closed() {
    for service in [
        None,
        Some(Arc::new(executors::approvals::NoopExecutorApprovalService)
            as Arc<dyn ExecutorApprovalService>),
    ] {
        let client = ClaudeAgentClient::new(
            LogWriter::new(tokio::io::sink()),
            service,
            RepoContext::default(),
            String::new(),
            CancellationToken::new(),
        );
        for tool in ["Bash", "AskUserQuestion", "ExitPlanMode"] {
            assert!(
                client
                    .on_can_use_tool(tool.into(), json!({}), None, Some("fixture".into()))
                    .await
                    .is_err()
            );
        }
        for hook in ["AUTO_APPROVE_CALLBACK_ID", "unknown"] {
            assert_eq!(
                client
                    .on_hook_callback(hook.into(), json!({}), None)
                    .await
                    .unwrap(),
                json!({})
            );
        }
    }
}

#[tokio::test]
async fn claude_plan_approval_exits_to_native_default_not_bypass() {
    let (approvals, bridge, execution) = bridge().await;
    let client = ClaudeAgentClient::new(
        LogWriter::new(tokio::io::sink()),
        Some(bridge),
        RepoContext::default(),
        String::new(),
        CancellationToken::new(),
    );
    let task = tokio::spawn(async move {
        client
            .on_can_use_tool(
                "ExitPlanMode".into(),
                json!({"plan":"synthetic"}),
                None,
                Some("plan-exit".into()),
            )
            .await
    });
    let pending = tokio::time::timeout(Duration::from_secs(5), async {
        loop {
            if let Some(info) = approvals.pending_infos().into_iter().next() {
                break info;
            }
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    assert!(!task.is_finished());
    approvals
        .respond(
            &pending.approval_id,
            ApprovalResponse {
                execution_process_id: execution,
                status: utils::approvals::ApprovalOutcome::Approved,
            },
        )
        .await
        .unwrap();
    let result = tokio::time::timeout(Duration::from_secs(5), task)
        .await
        .unwrap()
        .unwrap()
        .unwrap();
    let value = serde_json::to_value(result).unwrap();
    assert_eq!(value["updatedPermissions"][0]["mode"], "default");
    assert_eq!(value["updatedPermissions"][0]["destination"], "session");
    assert!(!value.to_string().contains("bypassPermissions"));
    assert!(approvals.pending_infos().is_empty());
}

#[tokio::test]
async fn claude_workspace_hook_never_bypasses_native_owner_fallback() {
    for status in [
        ApprovalStatus::Approved,
        ApprovalStatus::Denied { reason: None },
        ApprovalStatus::TimedOut,
    ] {
        let (approvals, bridge, execution) = bridge().await;
        let root = tempfile::tempdir().unwrap();
        let client = ClaudeAgentClient::new_scoped(
            LogWriter::new(tokio::io::sink()),
            Some(bridge),
            RepoContext::default(),
            String::new(),
            CancellationToken::new(),
            Some(root.path().to_path_buf()),
        );
        client.observe_runtime_version(Some("2.1.77"));
        let input = json!({"file_path":root.path().join("new.txt"),"content":"synthetic"});
        let hook = client
            .on_hook_callback(
                "workspace_edit_boundary".into(),
                json!({
                    "permission_mode":"default", "tool_name":"Write", "tool_input":input,
                    "tool_use_id":"file-call"
                }),
                Some("file-call".into()),
            )
            .await
            .unwrap();
        assert_eq!(hook["hookSpecificOutput"]["permissionDecision"], "allow");
        assert!(approvals.pending_infos().is_empty());
        // A native ask rule still reaches this callback after the scoped hook.
        let original = input.clone();
        let task = tokio::spawn(async move {
            client
                .on_can_use_tool("Write".into(), input, None, Some("file-call".into()))
                .await
        });
        let pending = tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                if let Some(info) = approvals.pending_infos().into_iter().next() {
                    break info;
                }
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
        assert!(!task.is_finished());
        assert_eq!(approvals.pending_infos().len(), 1);
        let outcome = serde_json::from_value(serde_json::to_value(&status).unwrap()).unwrap();
        approvals
            .respond(
                &pending.approval_id,
                ApprovalResponse {
                    execution_process_id: execution,
                    status: outcome,
                },
            )
            .await
            .unwrap();
        let result = tokio::time::timeout(Duration::from_secs(5), task)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        if matches!(status, ApprovalStatus::Approved) {
            if let PermissionResult::Allow {
                updated_input,
                updated_permissions,
            } = result
            {
                assert_eq!(updated_input, original);
                assert!(updated_permissions.is_none());
            } else {
                panic!("Owner approval lost");
            }
        } else {
            assert!(matches!(result, PermissionResult::Deny { .. }));
        }
        assert!(approvals.pending_infos().is_empty());
    }
}

#[tokio::test]
async fn claude_workspace_hook_refuses_uncorrelated_calls_and_unknown_scope() {
    let root = tempfile::tempdir().unwrap();
    let client = ClaudeAgentClient::new_scoped(
        LogWriter::new(tokio::io::sink()),
        None,
        RepoContext::default(),
        String::new(),
        CancellationToken::new(),
        Some(root.path().to_path_buf()),
    );
    let event = json!({"permission_mode":"default", "tool_name":"Write", "tool_input":{"file_path":root.path().join("new.txt")}});
    let missing = client
        .on_hook_callback("workspace_edit_boundary".into(), event.clone(), None)
        .await
        .unwrap();
    assert_eq!(missing["hookSpecificOutput"]["permissionDecision"], "deny");
    let mut mismatch = event.clone();
    mismatch["tool_use_id"] = json!("other");
    let result = client
        .on_hook_callback(
            "workspace_edit_boundary".into(),
            mismatch,
            Some("actual".into()),
        )
        .await
        .unwrap();
    assert_eq!(result["hookSpecificOutput"]["permissionDecision"], "deny");
    let unknown = ClaudeAgentClient::new(
        LogWriter::new(tokio::io::sink()),
        None,
        RepoContext::default(),
        String::new(),
        CancellationToken::new(),
    );
    assert_eq!(
        unknown
            .on_hook_callback(
                "workspace_edit_boundary".into(),
                event,
                Some("actual".into())
            )
            .await
            .unwrap(),
        json!({})
    );
    assert!(
        unknown
            .on_can_use_tool("Write".into(), json!({}), None, Some("actual".into()))
            .await
            .is_err()
    );
}

#[tokio::test]
async fn claude_workspace_authorization_requires_exact_qualified_runtime() {
    let root = tempfile::tempdir().unwrap();
    let client = ClaudeAgentClient::new_scoped(
        LogWriter::new(tokio::io::sink()),
        None,
        RepoContext::default(),
        String::new(),
        CancellationToken::new(),
        Some(root.path().to_path_buf()),
    );
    let event = json!({"permission_mode":"default", "tool_name":"Write", "tool_input":{"file_path":root.path().join("new.txt")}, "tool_use_id":"version-bound"});
    for version in [None, Some("2.1.62"), Some("2.1.303"), Some("unknown")] {
        client.observe_runtime_version(version);
        assert_eq!(
            client
                .on_hook_callback(
                    "workspace_edit_boundary".into(),
                    event.clone(),
                    Some("version-bound".into())
                )
                .await
                .unwrap(),
            json!({})
        );
    }
    client.observe_runtime_version(Some("2.1.77"));
    assert_eq!(
        client
            .on_hook_callback(
                "workspace_edit_boundary".into(),
                event,
                Some("version-bound".into())
            )
            .await
            .unwrap()["hookSpecificOutput"]["permissionDecision"],
        "allow"
    );
}
