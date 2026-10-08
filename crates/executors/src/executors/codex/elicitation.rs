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

/// Consent is based on invocation metadata, never on the provider's fallback
/// question or monitor reason. Reject incomplete/oversized context rather than
/// truncating the consequential part of an action. Render this as plain text.
pub fn consent_summary(params: &McpServerElicitationRequestParams) -> Option<String> {
    supported_message(params)?;
    let McpServerElicitationRequest::Form { meta, .. } = &params.request else {
        return None;
    };
    let meta = meta.as_ref()?;
    fn identity(value: &serde_json::Value) -> Option<&str> {
        let text = value.as_str()?;
        (!text.trim().is_empty()
            && text.len() <= 256
            && !text.chars().any(char::is_control)
            && !unsafe_text(text))
        .then_some(text)
    }
    let tool = identity(meta.get("tool_title")?)?;
    let connector = if params.server_name == "codex_apps" {
        // App calls need an actual connector identity, not "this app".
        format!(
            "{} ({})",
            identity(meta.get("connector_name")?)?,
            identity(meta.get("connector_id")?)?
        )
    } else {
        params.server_name.clone()
    };
    let arguments = meta.get("tool_params")?.as_object()?;
    if arguments.is_empty()
        || arguments.keys().all(|key| sensitive(key))
        || serde_json::to_vec(arguments).ok()?.len() > 65_536
    {
        // Without arguments we cannot distinguish consequential targets.
        return None;
    }
    fn sensitive(key: &str) -> bool {
        let key = key.to_ascii_lowercase().replace(['-', '_', ' '], "");
        // Token budgets/counts are consequential action parameters, not secrets.
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
    ) -> Option<serde_json::Value> {
        *nodes += 1;
        if depth > 8 || *nodes > 128 {
            return None;
        }
        Some(match value {
            serde_json::Value::Object(map) => {
                let mut output = serde_json::Map::new();
                for (key, value) in map {
                    if key.len() > 256 || key.chars().any(char::is_control) || unsafe_text(key) {
                        return None;
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
                    .collect::<Option<Vec<_>>>()?,
            ),
            serde_json::Value::String(text) => {
                // Secrets embedded in free text/URLs cannot be safely summarized
                // without interpreting the action; fail closed, never log them.
                let lower = text.to_ascii_lowercase();
                static KEY_PATTERN: std::sync::LazyLock<regex::Regex> =
                    std::sync::LazyLock::new(|| {
                        regex::Regex::new(r"(?:^|[\s\x22\x27])sk-[a-zA-Z0-9_-]{16,}")
                            .expect("constant regex")
                    });
                if text.len() > 4096
                    || unsafe_text(text)
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
                        && text.split("://").nth(1)?.split('/').next()?.contains('@'))
                {
                    return None;
                }
                value.clone()
            }
            _ => value.clone(),
        })
    }
    let safe = sanitize(&serde_json::Value::Object(arguments.clone()), 0, &mut 0)?;
    // Container names and display labels cannot make redaction-only leaves
    // meaningful. Check the surviving invocation values at every depth.
    if !has_meaningful_value(&safe) {
        return None;
    }
    let mut summary = format!(
        "Tool: {tool}\nConnector: {connector}\nMCP server: {}\nParameters (including target):\n{}",
        params.server_name,
        serde_json::to_string_pretty(&safe).ok()?
    );
    // Retain upstream display labels, but require their values to match the
    // actual invocation. They may label a target; they cannot replace it.
    if let Some(display) = meta.get("tool_params_display") {
        let display = display.as_array()?;
        if display.len() > 128 {
            return None;
        }
        for item in display {
            let name = identity(item.get("name")?)?;
            let label = identity(item.get("display_name")?)?;
            if arguments.get(name)? != item.get("value")? {
                return None;
            }
            summary.push_str(&format!("\n{label} ({name}): {}", safe.get(name)?));
            if summary.len() > 8192 {
                return None;
            }
        }
    }
    summary.push_str("\n\nApprove this call only.");
    (summary.len() <= 8192).then_some(summary)
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
            "x".repeat(4097),
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
