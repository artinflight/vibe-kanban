//! Policy/profile regressions; no CLI, provider account or inference.
use serde_json::json;

use super::{ClaudeCode, PermissionMode};
use crate::{
    executors::{BaseCodingAgent, StandardCodingAgentExecutor},
    model_selector::PermissionPolicy,
    profile::ExecutorConfig,
};

#[tokio::test]
async fn native_permissions_cover_existing_profiles_and_resume_without_bypass() {
    let defaults: serde_json::Value =
        serde_json::from_str(include_str!("../../../default_profiles.json")).unwrap();
    let profiles = [
        json!({}),
        defaults["executors"]["CLAUDE_CODE"]["DEFAULT"]["CLAUDE_CODE"].clone(),
        json!({"approvals": true}),
        json!({"plan": true}),
        json!({"plan": true, "approvals": true, "dangerously_skip_permissions": true}),
        json!({"dangerously_skip_permissions": false}),
    ];
    for profile in profiles {
        for (policy, mode) in [
            (PermissionPolicy::Auto, PermissionMode::Default),
            (PermissionPolicy::Supervised, PermissionMode::Default),
            (PermissionPolicy::Plan, PermissionMode::Plan),
        ] {
            let mut agent: ClaudeCode = serde_json::from_value(profile.clone()).unwrap();
            let mut config = ExecutorConfig::new(BaseCodingAgent::ClaudeCode);
            config.permission_policy = Some(policy);
            config.model_id = Some("sonnet".into());
            config.reasoning_id = Some("high".into());
            agent.apply_overrides(&config);
            assert_eq!(agent.permission_mode(), mode);
            agent.cmd.base_command_override = Some("synthetic-claude".into());
            let builder = agent.build_command_builder().await.unwrap();
            let initial = builder.build_initial().unwrap().args().to_vec();
            let resume = ["--resume".to_owned(), "existing-native-session".to_owned()];
            let follow_up = builder.build_follow_up(&resume).unwrap().args().to_vec();
            assert_eq!(&follow_up[..initial.len()], &initial);
            assert_eq!(&follow_up[initial.len()..], &resume);
            assert!(initial.contains(&format!("--permission-mode={mode}")));
            assert!(initial.contains(&"--permission-prompt-tool=stdio".into()));
            assert!(
                !initial
                    .iter()
                    .any(|s| s.contains("bypass") || s.contains("skip-permissions"))
            );
            assert!(initial.windows(2).any(|p| p == ["--model", "sonnet"]));
            assert!(initial.windows(2).any(|p| p == ["--effort", "high"]));
            let hooks = agent.get_hooks(true).unwrap();
            let pre = hooks["PreToolUse"].as_array().unwrap();
            assert_eq!(pre.len(), 2);
            assert_eq!(
                pre[1]["hookCallbackIds"][0],
                super::permission_boundary::CALLBACK_ID
            );
            assert!(!initial.iter().any(|arg| arg.starts_with("--allowedTools")));
            assert_eq!(pre[0]["matcher"], "^(ExitPlanMode|AskUserQuestion)$");
            assert!(hooks["Stop"].is_array());
        }
    }
}

#[test]
fn native_permissions_preserve_legacy_selection_and_plan_precedence() {
    for (value, expected) in [
        (json!({}), PermissionMode::Default),
        (
            json!({"approvals":true,"dangerously_skip_permissions":true}),
            PermissionMode::Default,
        ),
        (json!({"plan":true,"approvals":true}), PermissionMode::Plan),
    ] {
        let agent: ClaudeCode = serde_json::from_value(value).unwrap();
        assert_eq!(agent.permission_mode(), expected);
    }
}

#[tokio::test]
async fn native_permissions_keep_custom_rules_but_refuse_conflicting_controls() {
    let mut agent: ClaudeCode = serde_json::from_value(json!({
        "model":"custom-model", "effort":"medium", "agent":"reviewer",
        "base_command_override":"synthetic-claude",
        "additional_params":["--allowedTools", "\"Bash(ls:*)\"", "--disallowedTools", "\"Bash(rm:*)\""],
        "env":{"TASK_FIXTURE":"unchanged"}
    }))
    .unwrap();
    let before = agent.clone();
    let builder = agent.build_command_builder().await.unwrap();
    let args = builder.build_initial().unwrap().args().to_vec();
    for value in [
        "custom-model",
        "medium",
        "reviewer",
        "Bash(ls:*)",
        "Bash(rm:*)",
    ] {
        assert!(args.contains(&value.to_string()));
    }
    assert_eq!(
        agent, before,
        "Command preparation must not rewrite a profile"
    );
    for flag in [
        "--permission-mode=bypassPermissions",
        "--permission-mode plan",
        "--dangerously-skip-permissions",
        "--allow-dangerously-skip-permissions",
        "--permission-prompt-tool=other",
    ] {
        agent.cmd.additional_params = Some(vec![flag.into()]);
        assert!(agent.build_command_builder().await.is_err(), "{flag}");
        agent.cmd.additional_params = None;
        agent.cmd.base_command_override = Some(format!("synthetic-claude {flag}"));
        assert!(agent.build_command_builder().await.is_err(), "base {flag}");
        agent.cmd.base_command_override = Some("synthetic-claude".into());
    }
}

#[test]
fn native_permission_wire_preserves_qualified_version_and_blocked_path_aliases() {
    use super::types::{CLIMessage, ControlRequestType};
    assert!(super::base_command(false).ends_with(super::permission_boundary::QUALIFIED_VERSION));
    let init: CLIMessage = serde_json::from_value(json!({
        "type":"system", "subtype":"init", "claude_code_version":"2.1.77", "session_id":"unchanged"
    }))
    .unwrap();
    assert!(
        matches!(init, CLIMessage::System { subtype, claude_code_version:Some(version) } if subtype == "init" && version == super::permission_boundary::QUALIFIED_VERSION)
    );
    for field in ["blocked_path", "blocked_paths"] {
        let mut request = json!({"type":"control_request", "request_id":"native-correlation", "request":{
            "subtype":"can_use_tool", "tool_name":"Write", "input":{"file_path":"/outside/new.txt"}, "tool_use_id":"tool-id"
        }});
        request["request"][field] = json!("/outside/new.txt");
        let decoded: CLIMessage = serde_json::from_value(request).unwrap();
        assert!(
            matches!(decoded, CLIMessage::ControlRequest { request_id, request:ControlRequestType::CanUseTool { blocked_paths:Some(path), tool_use_id:Some(id), .. } } if request_id == "native-correlation" && id == "tool-id" && path == "/outside/new.txt")
        );
    }
}
