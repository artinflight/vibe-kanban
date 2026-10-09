//! Compiled regressions for consent after recursive secret redaction.
use codex_app_server_protocol::McpServerElicitationRequestParams;
use executors::executors::codex::elicitation::{
    MAX_ARGUMENT_BYTES, MAX_DISPLAY_BYTES, MAX_STRING_BYTES, MAX_STRING_CHARS, consent_summary,
    validate_consent, validation_response,
};
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

#[test]
fn supported_unicode_prompt_boundaries_are_not_utf8_truncation_limits() {
    // Python connector len() counts Unicode scalars; Rust str::len() counts bytes.
    for prompt in [
        "a".repeat(4096),
        "a".repeat(4097),
        "é".repeat(4096),
        "🧭".repeat(MAX_STRING_CHARS),
    ] {
        let summary = validate_consent(&with_matching_display(json!({"prompt":prompt}))).unwrap();
        assert!(summary.contains(&prompt));
        assert_eq!(summary.matches(&prompt).count(), 1);
    }
    assert_eq!("🧭".repeat(MAX_STRING_CHARS).len(), MAX_STRING_BYTES);
    for (prompt, reason, observed, limit) in [
        (
            "a".repeat(MAX_STRING_CHARS + 1),
            "string_characters",
            MAX_STRING_CHARS + 1,
            MAX_STRING_CHARS,
        ),
        (
            "🧭".repeat(MAX_STRING_CHARS + 1),
            "string_utf8_bytes",
            MAX_STRING_BYTES + 4,
            MAX_STRING_BYTES,
        ),
    ] {
        let error = validate_consent(&with_matching_display(json!({"prompt":prompt}))).unwrap_err();
        assert_eq!(error.reason, reason);
        assert_eq!(error.observed, Some(observed));
        assert_eq!(error.limit, Some(limit));
        let result = serde_json::to_value(validation_response(&error)).unwrap();
        assert_eq!(result["action"], "cancel");
        assert_eq!(result["content"]["error"]["code"], "mcp_consent_validation");
        assert_eq!(result["content"]["error"]["details"]["reason"], reason);
        assert_eq!(result["content"]["review_requested"], false);
        assert_eq!(result["content"]["dispatch_allowed"], false);
        assert!(result["_meta"].is_null()); // no persistent or session grants
        assert!(!result.to_string().contains("user cancelled"));
    }
}

#[test]
fn actual_dispatch_sizes_and_duplicated_display_budget_keep_complete_content() {
    // Reproduce the observed lengths with synthetic instructions, not private logs.
    for length in [3857, 5820, 7904, 10_200, MAX_STRING_CHARS] {
        let suffix = "\nNo Figma until THIS Visily view has owner signoff.\nEND-OF-EXACT-PROMPT";
        let prompt = format!("{}{}", "x".repeat(length - suffix.len()), suffix);
        let params =
            with_matching_display(json!({"session_id":"synthetic-target", "prompt":prompt}));
        let summary = validate_consent(&params).unwrap();
        assert_eq!(summary.matches(&prompt).count(), 1);
        assert!(summary.contains(suffix));
        assert!(summary.contains("synthetic-target"));
        assert!(summary.contains("Parameter \"prompt\" — prompt"));
        assert!(!summary.contains("\\nNo Figma")); // paragraphs remain readable
    }
    // Two 4 KiB strings passed the old string check but duplicated pretty JSON
    // and display values exceeded its 8 KiB rendered-summary limit.
    let a = format!("A{}", "a".repeat(4095));
    let b = format!("B{}", "b".repeat(4095));
    let summary = validate_consent(&with_matching_display(json!({"first":a, "second":b}))).unwrap();
    assert!(summary.len() > 8192);
    assert_eq!(summary.matches(&a).count(), 1);
    assert_eq!(summary.matches(&b).count(), 1);
}

#[test]
fn aggregate_and_display_budgets_remain_bounded() {
    let args: serde_json::Map<String, Value> = (0..9)
        .map(|i| (format!("field{i}"), json!("x".repeat(MAX_STRING_CHARS))))
        .collect();
    let error = validate_consent(&with_matching_display(Value::Object(args))).unwrap_err();
    assert_eq!(error.reason, "arguments_bytes");
    assert_eq!(error.limit, Some(MAX_ARGUMENT_BYTES));
    let mut params = serde_json::to_value(with_matching_display(
        json!({"prompt":"x".repeat(MAX_STRING_CHARS)}),
    ))
    .unwrap();
    let display = params["_meta"]["tool_params_display"][0].clone();
    params["_meta"]["tool_params_display"] = json!(vec![display; 11]);
    let error = validate_consent(&serde_json::from_value(params).unwrap()).unwrap_err();
    assert_eq!(error.reason, "display_bytes");
    assert_eq!(error.limit, Some(MAX_DISPLAY_BYTES));
}

#[test]
fn long_prompt_does_not_weaken_unsafe_text_mismatch_or_structural_guards() {
    for suffix in [
        "\u{202e}wrong-target",
        "https://user:password@example.invalid",
        " token=private",
    ] {
        let params =
            with_matching_display(json!({"prompt":format!("{}{}", "x".repeat(7904), suffix)}));
        assert_eq!(
            validate_consent(&params).unwrap_err().reason,
            "unsafe_context"
        );
    }
    let mut params =
        serde_json::to_value(with_matching_display(json!({"prompt":"x".repeat(7904)}))).unwrap();
    params["_meta"]["tool_params_display"][0]["value"] = json!("different-target");
    assert_eq!(
        validate_consent(&serde_json::from_value(params).unwrap())
            .unwrap_err()
            .reason,
        "display_mismatch"
    );
    let mut nested = json!("synthetic-target");
    for _ in 0..9 {
        nested = json!([nested]);
    }
    assert_eq!(
        validate_consent(&with_matching_display(json!({"nested":nested})))
            .unwrap_err()
            .reason,
        "structure_limit"
    );
    assert_eq!(
        validate_consent(&with_matching_display(json!({"many":vec![true;128]})))
            .unwrap_err()
            .reason,
        "structure_limit"
    );
}
