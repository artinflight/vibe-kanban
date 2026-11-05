//! Deliberately narrow consent bridge. Form input and persistent grants are not inferred.
use codex_app_server_protocol::{
    McpServerElicitationAction, McpServerElicitationRequest, McpServerElicitationRequestParams,
    McpServerElicitationRequestResponse,
};
use serde_json::json;
use workspace_utils::approvals::ApprovalStatus;

use crate::approvals::ExecutorApprovalError;

pub const TOOL: &str = "codex.mcp_approval";
const REDACTED_SECRET: &str = "[secret redacted]";

fn has_meaningful_value(value: &serde_json::Value) -> bool {
    match value {
        serde_json::Value::Object(values) => values.values().any(has_meaningful_value),
        serde_json::Value::Array(values) => values.iter().any(has_meaningful_value),
        serde_json::Value::String(text) => {
            !text.trim().is_empty() && text.trim() != REDACTED_SECRET
        }
        serde_json::Value::Number(_) | serde_json::Value::Bool(_) => true,
        serde_json::Value::Null => false,
    }
}

fn unsafe_text(text: &str) -> bool {
    // Invisible direction overrides can change the apparent target/action.
    text.chars()
        .any(|c| matches!(c, '\u{202a}'..='\u{202e}' | '\u{2066}'..='\u{2069}'))
}

// The deployed Vibe connector accepts 60,000 Unicode characters per prompt.
// UTF-8 can use four bytes per character. JSON escaping/formatting and verified
// display labels have separate bounded budgets; none is a truncation budget.
pub const MAX_STRING_CHARS: usize = 60_000;
pub const MAX_STRING_BYTES: usize = MAX_STRING_CHARS * 4;
pub const MAX_ARGUMENT_BYTES: usize = 512 * 1024;
pub const MAX_DISPLAY_BYTES: usize = MAX_ARGUMENT_BYTES + 128 * 1024;
pub const MAX_SUMMARY_BYTES: usize = 1024 * 1024;

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ConsentValidationError {
    pub reason: &'static str,
    pub message: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observed: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<usize>,
}

impl ConsentValidationError {
    fn invalid(reason: &'static str, message: &'static str) -> Self {
        Self {
            reason,
            message,
            observed: None,
            limit: None,
        }
    }

    fn limit(reason: &'static str, observed: usize, limit: usize) -> Self {
        Self {
            reason,
            message: "Complete approval context exceeds the supported review limit. No approval was requested or granted.",
            observed: Some(observed),
            limit: Some(limit),
        }
    }
}

type ConsentResult<T> = Result<T, ConsentValidationError>;

/// Compatibility wrapper for existing context readers. The bridge uses the
/// detailed result so validation is never reported as an operator decision.
pub fn consent_summary(params: &McpServerElicitationRequestParams) -> Option<String> {
    validate_consent(params).ok()
}

/// Invocation metadata is authoritative. Every nonsecret value is presented
/// once, in full, as literal text. Provider questions cannot replace a target.
pub fn validate_consent(params: &McpServerElicitationRequestParams) -> ConsentResult<String> {
    let incomplete = || {
        ConsentValidationError::invalid(
            "missing_context",
            "Complete tool identity and invocation arguments are required. No approval was requested or granted.",
        )
    };
    supported_message(params).ok_or_else(|| {
        ConsentValidationError::invalid(
            "unsupported_request",
            "This approval form is unsupported. No approval was requested or granted.",
        )
    })?;
    let McpServerElicitationRequest::Form { meta, .. } = &params.request else {
        return Err(incomplete());
    };
    let meta = meta.as_ref().ok_or_else(incomplete)?;
    fn identity(value: &serde_json::Value) -> Option<&str> {
        let text = value.as_str()?;
        (!text.trim().is_empty()
            && text.len() <= 256
            && !text.chars().any(char::is_control)
            && !unsafe_text(text))
        .then_some(text)
    }
    let tool = meta
        .get("tool_title")
        .and_then(identity)
        .ok_or_else(incomplete)?;
    let connector = if params.server_name == "codex_apps" {
        format!(
            "{} ({})",
            meta.get("connector_name")
                .and_then(identity)
                .ok_or_else(incomplete)?,
            meta.get("connector_id")
                .and_then(identity)
                .ok_or_else(incomplete)?
        )
    } else {
        params.server_name.clone()
    };
    let arguments = meta
        .get("tool_params")
        .and_then(serde_json::Value::as_object)
        .ok_or_else(incomplete)?;
    let arguments_bytes = serde_json::to_vec(arguments)
        .map_err(|_| incomplete())?
        .len();
    if arguments_bytes > MAX_ARGUMENT_BYTES {
        return Err(ConsentValidationError::limit(
            "arguments_bytes",
            arguments_bytes,
            MAX_ARGUMENT_BYTES,
        ));
    }
    if arguments.is_empty() || arguments.keys().all(|key| sensitive(key)) {
        return Err(incomplete());
    }
    fn sensitive(key: &str) -> bool {
        let key = key.to_ascii_lowercase().replace(['-', '_', ' '], "");
        if [
            "maxtokens",
            "tokencount",
            "tokenlimit",
            "inputtokens",
            "outputtokens",
            "maxoutputtokens",
            "maxcompletiontokens",
        ]
        .contains(&key.as_str())
        {
            return false;
        }
        [
            "password",
            "passwd",
            "secret",
            "token",
            "apikey",
            "authorization",
            "cookie",
            "credential",
            "privatekey",
        ]
        .iter()
        .any(|part| key.contains(part))
    }
    fn sanitize(
        value: &serde_json::Value,
        depth: usize,
        nodes: &mut usize,
    ) -> ConsentResult<serde_json::Value> {
        *nodes += 1;
        if depth > 8 || *nodes > 128 {
            return Err(ConsentValidationError::invalid(
                "structure_limit",
                "Approval arguments exceed the supported depth or node limit. No approval was requested or granted.",
            ));
        }
        let unsafe_value = || {
            ConsentValidationError::invalid(
                "unsafe_context",
                "Approval context contains unsafe text or embedded credentials. No approval was requested or granted.",
            )
        };
        Ok(match value {
            serde_json::Value::Object(map) => {
                let mut output = serde_json::Map::new();
                for (key, value) in map {
                    if key.len() > 256 || key.chars().any(char::is_control) || unsafe_text(key) {
                        return Err(unsafe_value());
                    }
                    output.insert(
                        key.clone(),
                        if sensitive(key) {
                            serde_json::json!(REDACTED_SECRET)
                        } else {
                            sanitize(value, depth + 1, nodes)?
                        },
                    );
                }
                serde_json::Value::Object(output)
            }
            serde_json::Value::Array(values) => serde_json::Value::Array(
                values
                    .iter()
                    .map(|v| sanitize(v, depth + 1, nodes))
                    .collect::<ConsentResult<Vec<_>>>()?,
            ),
            serde_json::Value::String(text) => {
                if text.len() > MAX_STRING_BYTES {
                    return Err(ConsentValidationError::limit(
                        "string_utf8_bytes",
                        text.len(),
                        MAX_STRING_BYTES,
                    ));
                }
                let chars = text.chars().count();
                if chars > MAX_STRING_CHARS {
                    return Err(ConsentValidationError::limit(
                        "string_characters",
                        chars,
                        MAX_STRING_CHARS,
                    ));
                }
                let lower = text.to_ascii_lowercase();
                static KEY_PATTERN: std::sync::LazyLock<regex::Regex> =
                    std::sync::LazyLock::new(|| {
                        regex::Regex::new(r"(?:^|[\s\x22\x27])sk-[a-zA-Z0-9_-]{16,}")
                            .expect("constant regex")
                    });
                if unsafe_text(text)
                    || KEY_PATTERN.is_match(text)
                    || text
                        .chars()
                        .any(|c| c.is_control() && c != '\n' && c != '\t')
                    || [
                        "bearer ",
                        "password=",
                        "token=",
                        "api_key=",
                        "apikey=",
                        "secret=",
                        "-----begin",
                        "ghp_",
                    ]
                    .iter()
                    .any(|s| lower.contains(s))
                    || (text.contains("://")
                        && text.split("://").nth(1).is_some_and(|rest| {
                            rest.split('/')
                                .next()
                                .is_some_and(|host| host.contains('@'))
                        }))
                {
                    return Err(unsafe_value());
                }
                value.clone()
            }
            _ => value.clone(),
        })
    }
    let safe = sanitize(&serde_json::Value::Object(arguments.clone()), 0, &mut 0)?;
    if !has_meaningful_value(&safe) {
        return Err(ConsentValidationError::invalid(
            "redacted_only",
            "Approval arguments contain no reviewable nonsecret invocation values. No approval was requested or granted.",
        ));
    }
    // Display metadata is verified against the actual invocation, then used
    // only as labels. Repeating a full prompt here wasted the old 8 KiB budget.
    let mut labels = std::collections::BTreeMap::<&str, Vec<&str>>::new();
    if let Some(display) = meta.get("tool_params_display") {
        let display_bytes = serde_json::to_vec(display).map_err(|_| incomplete())?.len();
        if display_bytes > MAX_DISPLAY_BYTES {
            return Err(ConsentValidationError::limit(
                "display_bytes",
                display_bytes,
                MAX_DISPLAY_BYTES,
            ));
        }
        let display = display.as_array().ok_or_else(incomplete)?;
        if display.len() > 128 {
            return Err(incomplete());
        }
        for item in display {
            let name = item.get("name").and_then(identity).ok_or_else(incomplete)?;
            let label = item
                .get("display_name")
                .and_then(identity)
                .ok_or_else(incomplete)?;
            if arguments.get(name).is_none() || arguments.get(name) != item.get("value") {
                return Err(ConsentValidationError::invalid(
                    "display_mismatch",
                    "Displayed parameters do not match the invocation. No approval was requested or granted.",
                ));
            }
            let entry = labels.entry(name).or_default();
            if !entry.contains(&label) {
                entry.push(label);
            }
        }
    }
    let mut summary = format!(
        "Tool: {tool}\nConnector: {connector}\nMCP server: {}\nParameters (complete nonsecret invocation):",
        params.server_name
    );
    for (name, value) in safe.as_object().expect("sanitized object") {
        let label = labels
            .get(name.as_str())
            .map(|values| format!(" — {}", values.join("; ")))
            .unwrap_or_default();
        let name = serde_json::to_string(name).map_err(|_| incomplete())?;
        if let Some(text) = value.as_str() {
            // Literal multiline strings retain paragraph breaks for review.
            summary.push_str(&format!("\n\nParameter {name}{label} (string, {} UTF-8 bytes):\n{text}\nEnd parameter {name}.", text.len()));
        } else {
            summary.push_str(&format!(
                "\n\nParameter {name}{label} (JSON):\n{}",
                serde_json::to_string_pretty(value).map_err(|_| incomplete())?
            ));
        }
    }
    summary.push_str("\n\nApprove this call only.");
    if summary.len() > MAX_SUMMARY_BYTES {
        return Err(ConsentValidationError::limit(
            "summary_bytes",
            summary.len(),
            MAX_SUMMARY_BYTES,
        ));
    }
    Ok(summary)
}

/// The native protocol only has accept/decline/cancel. Validation uses Cancel
/// with a bounded structured reason, never a fabricated user decision. Native
/// Codex currently discards this detail; Vibe persists and displays it as well.
pub fn validation_response(error: &ConsentValidationError) -> McpServerElicitationRequestResponse {
    McpServerElicitationRequestResponse {
        action: McpServerElicitationAction::Cancel,
        content: Some(
            json!({"error": {"code":"mcp_consent_validation", "details":error}, "review_requested":false, "dispatch_allowed":false}),
        ),
        meta: None,
    }
}

pub fn supported_message(params: &McpServerElicitationRequestParams) -> Option<&str> {
    if params.server_name.trim().is_empty()
        || params.server_name.len() > 256
        || params.server_name.chars().any(char::is_control)
        || unsafe_text(&params.server_name)
    {
        return None;
    }
    match &params.request {
        McpServerElicitationRequest::Form {
            meta,
            message,
            requested_schema,
        } if meta.as_ref()?.get("codex_approval_kind")?.as_str()? == "mcp_tool_call"
            && requested_schema.properties.is_empty()
            && requested_schema.required.as_ref().is_none_or(Vec::is_empty)
            && !message.trim().is_empty()
            && message.len() <= 16_384 =>
        {
            Some(message)
        }
        _ => None,
    }
}

pub fn response(action: McpServerElicitationAction) -> McpServerElicitationRequestResponse {
    McpServerElicitationRequestResponse {
        action,
        content: (action == McpServerElicitationAction::Accept).then(|| json!({})),
        // Never echo request metadata or request a persistent/session grant.
        meta: None,
    }
}

pub fn outcome(
    result: Result<ApprovalStatus, ExecutorApprovalError>,
) -> (McpServerElicitationAction, &'static str) {
    use McpServerElicitationAction::*;
    match result {
        Ok(ApprovalStatus::Approved) => (Accept, "human_approved"),
        Ok(ApprovalStatus::Denied { .. }) => (Decline, "human_declined"),
        Ok(ApprovalStatus::TimedOut) => (Cancel, "timeout"),
        Ok(ApprovalStatus::Pending) => (Cancel, "unexpected_pending"),
        Err(ExecutorApprovalError::Cancelled) => (Cancel, "cancelled"),
        Err(
            ExecutorApprovalError::ServiceUnavailable | ExecutorApprovalError::SessionNotRegistered,
        ) => (Cancel, "service_unavailable"),
        Err(ExecutorApprovalError::RequestFailed(_)) => (Cancel, "bridge_error"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params() -> McpServerElicitationRequestParams {
        serde_json::from_value(
            json!({"threadId":"synthetic","turnId":null,"serverName":"codex_apps",
                "mode":"form","message":"Allow run_session_prompt for synthetic Reporting?",
                "requestedSchema":{"type":"object","properties":{}},
                "_meta":{"codex_approval_kind":"mcp_tool_call","persist":["session","always"]}
            }),
        )
        .unwrap()
    }

    fn upstream_context(message: &str, target: &str) -> McpServerElicitationRequestParams {
        serde_json::from_value(json!({
            "threadId":"synthetic", "turnId":null, "serverName":"codex_apps",
            "mode":"form", "message":message,
            "requestedSchema":{"type":"object","properties":{}},
            "_meta":{"codex_approval_kind":"mcp_tool_call", "tool_title":"run_session_prompt",
                "source":"connector", "connector_id":"synthetic-vk", "connector_name":"Synthetic VK",
                "tool_params":{"session_id":target,"prompt":"Resume Reporting with synthetic task-target instructions",
                    "max_tokens":1234,"credentials":{"access_token":"private-sentinel"}},
                "tool_params_display":[{"name":"session_id","display_name":"Reporting session target","value":target}]}
        })).unwrap()
    }

    #[test]
    fn upstream_fallback_and_monitor_reason_preserve_distinct_action_targets() {
        // Actual upstream build_mcp_tool_approval_fallback_message and
        // mcp_tool_approval_question_text shapes, not a target-bearing question.
        let a = consent_summary(&upstream_context(
            "Allow this app to run tool \"run_session_prompt\"?",
            "target-A",
        ))
        .unwrap();
        let b = consent_summary(&upstream_context(
            "Tool call needs your approval. Reason: This action requires confirmation",
            "target-B",
        ))
        .unwrap();
        for (summary, target) in [(&a, "target-A"), (&b, "target-B")] {
            assert!(summary.contains("Tool: run_session_prompt"));
            assert!(summary.contains("Connector: Synthetic VK (synthetic-vk)"));
            assert!(summary.contains(target));
            assert!(summary.contains("Resume Reporting with synthetic task-target instructions"));
            assert!(summary.contains("Reporting session target"));
            assert!(summary.contains("[secret redacted]"));
            assert!(summary.contains("1234"));
            assert!(!summary.contains("private-sentinel"));
        }
        assert!(!a.contains("target-B"));
        assert!(!b.contains("target-A"));
    }

    #[test]
    fn inadequate_or_unsafe_context_fails_closed_without_truncating_targets() {
        let source =
            serde_json::to_value(upstream_context("Generic approval reason", "target-A")).unwrap();
        for key in [
            "tool_title",
            "connector_id",
            "connector_name",
            "tool_params",
        ] {
            let mut value = source.clone();
            value["_meta"].as_object_mut().unwrap().remove(key);
            assert!(consent_summary(&serde_json::from_value(value).unwrap()).is_none());
        }
        for target in [
            "bad\u{202e}target".into(),
            "sk-abcdefghijklmnopqsecret".into(),
            "x".repeat(MAX_STRING_CHARS + 1),
            "https://user:password@example.invalid/target".into(),
            "https://example.invalid/target?token=secret".into(),
        ] {
            assert!(
                consent_summary(&upstream_context("Generic approval reason", &target)).is_none()
            );
        }
        for arguments in [json!({}), json!({"access_token":"private-sentinel"})] {
            let mut value = source.clone();
            value["_meta"]["tool_params"] = arguments;
            value["_meta"]
                .as_object_mut()
                .unwrap()
                .remove("tool_params_display");
            assert!(consent_summary(&serde_json::from_value(value).unwrap()).is_none());
        }
        let mut value = source;
        value["_meta"]["tool_params_display"][0]["value"] = json!("different-target");
        assert!(consent_summary(&serde_json::from_value(value).unwrap()).is_none());
    }

    #[test]
    fn reporting_empty_form_is_supported_without_persistent_grants() {
        assert!(supported_message(&params()).is_some());
        // This was the old defect: null cannot deserialize as a typed result.
        assert!(
            serde_json::from_value::<McpServerElicitationRequestResponse>(serde_json::Value::Null)
                .is_err()
        );
        for action in [
            McpServerElicitationAction::Accept,
            McpServerElicitationAction::Decline,
            McpServerElicitationAction::Cancel,
        ] {
            let value = serde_json::to_value(response(action)).unwrap();
            let decoded: McpServerElicitationRequestResponse =
                serde_json::from_value(value).unwrap();
            assert_eq!(decoded.action, action);
            assert!(decoded.meta.is_none());
            assert_eq!(
                decoded.content,
                (action == McpServerElicitationAction::Accept).then(|| json!({}))
            );
        }
    }

    #[test]
    fn no_input_or_permission_is_invented() {
        let mut value = serde_json::to_value(params()).unwrap();
        for meta in [
            json!(null),
            json!({"codex_approval_kind":"userVerification"}),
        ] {
            value["_meta"] = meta;
            assert!(supported_message(&serde_json::from_value(value.clone()).unwrap()).is_none());
        }
        value["_meta"] = json!({"codex_approval_kind":"mcp_tool_call"});
        value["requestedSchema"]["required"] = json!(["unprovided"]);
        assert!(supported_message(&serde_json::from_value(value).unwrap()).is_none());
    }

    #[test]
    fn failures_are_cancelled_with_truthful_origins() {
        use McpServerElicitationAction::*;
        for (input, expected) in [
            (Ok(ApprovalStatus::Approved), (Accept, "human_approved")),
            (
                Ok(ApprovalStatus::Denied {
                    reason: Some("private reason".into()),
                }),
                (Decline, "human_declined"),
            ),
            (Ok(ApprovalStatus::TimedOut), (Cancel, "timeout")),
            (Ok(ApprovalStatus::Pending), (Cancel, "unexpected_pending")),
            (Err(ExecutorApprovalError::Cancelled), (Cancel, "cancelled")),
            (
                Err(ExecutorApprovalError::ServiceUnavailable),
                (Cancel, "service_unavailable"),
            ),
            (
                Err(ExecutorApprovalError::SessionNotRegistered),
                (Cancel, "service_unavailable"),
            ),
            (
                Err(ExecutorApprovalError::RequestFailed("private error".into())),
                (Cancel, "bridge_error"),
            ),
        ] {
            assert_eq!(outcome(input), expected);
        }
    }

    #[tokio::test]
    async fn noninteractive_services_cannot_approve_mcp() {
        use crate::approvals::ExecutorApprovalService;
        assert!(
            crate::approvals::NoopExecutorApprovalService
                .create_mcp_tool_approval("synthetic consent")
                .await
                .is_err()
        );
    }
}
