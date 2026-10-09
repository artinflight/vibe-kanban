//! Compiled regressions for consent after recursive secret redaction.
use codex_app_server_protocol::McpServerElicitationRequestParams;
use executors::executors::codex::elicitation::consent_summary;
use serde_json::{Value, json};

fn with_matching_display(arguments: Value) -> McpServerElicitationRequestParams {
    let display = arguments
        .as_object()
        .unwrap()
        .iter()
        .map(|(name, value)| json!({"name":name,"display_name":name,"value":value}))
        .collect::<Vec<_>>();
    serde_json::from_value(json!({
        "threadId":"synthetic-thread", "turnId":null, "serverName":"codex_apps",
        "mode":"form", "message":"Allow this app to run tool \"run_session_prompt\"?",
        "requestedSchema":{"type":"object","properties":{}},
        "_meta":{"codex_approval_kind":"mcp_tool_call", "tool_title":"run_session_prompt",
            "source":"connector", "connector_id":"synthetic-vk", "connector_name":"Synthetic VK",
            "tool_params":arguments, "tool_params_display":display}
    }))
    .unwrap()
}

#[test]
fn wholly_redacted_nested_object_cannot_present_consent() {
    for credential in ["synthetic-A", "synthetic-B"] {
        let exact_review_case =
            with_matching_display(json!({"payload":{"access_token":credential}}));
        assert!(consent_summary(&exact_review_case).is_none());
        let params = with_matching_display(json!({"payload":{
            "nested":{"access_token":credential}, "empty":{}, "absent":null, "blank":" "
        }}));
        assert!(consent_summary(&params).is_none());
    }
}

#[test]
fn wholly_redacted_nested_array_cannot_present_consent() {
    for credential in ["synthetic-A", "synthetic-B"] {
        let params = with_matching_display(json!({"payload":[
            [{"access_token":credential}], {}, [], null, " "
        ]}));
        assert!(consent_summary(&params).is_none());
    }
}

#[test]
fn mixed_nested_context_retains_nonsecret_target_and_redaction() {
    let params = with_matching_display(json!({"payload":[
        {"access_token":"synthetic-private-credential"},
        {"target":{"session_id":"synthetic-reporting-session", "workspace":"synthetic-workspace"}},
        {"max_tokens":0, "enabled":false}
    ]}));
    let summary = consent_summary(&params).unwrap();
    assert!(summary.contains("synthetic-reporting-session"));
    assert!(summary.contains("synthetic-workspace"));
    assert!(summary.contains("[secret redacted]"));
    assert!(!summary.contains("synthetic-private-credential"));
    assert!(summary.contains("Approve this call only"));
}
