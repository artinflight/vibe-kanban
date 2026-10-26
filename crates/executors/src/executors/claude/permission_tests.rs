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
            (PermissionPolicy::Auto, PermissionMode::AcceptEdits),
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
            assert_eq!(pre.len(), 1);
            assert_eq!(pre[0]["matcher"], "^(ExitPlanMode|AskUserQuestion)$");
            assert!(hooks["Stop"].is_array());
        }
    }
}

#[test]
fn native_permissions_preserve_legacy_selection_and_plan_precedence() {
    for (value, expected) in [
        (json!({}), PermissionMode::AcceptEdits),
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
