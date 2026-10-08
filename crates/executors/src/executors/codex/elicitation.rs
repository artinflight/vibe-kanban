//! Deliberately narrow consent bridge. Form input and persistent grants are not inferred.
use codex_app_server_protocol::{
    McpServerElicitationAction, McpServerElicitationRequest, McpServerElicitationRequestParams,
    McpServerElicitationRequestResponse,
};
use serde_json::json;
use workspace_utils::approvals::ApprovalStatus;

use crate::approvals::ExecutorApprovalError;

pub const TOOL: &str = "codex.mcp_approval";

pub fn supported_message(params: &McpServerElicitationRequestParams) -> Option<&str> {
    if params.server_name.trim().is_empty() || params.server_name.len() > 256 {
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
                .create_mcp_tool_approval()
                .await
                .is_err()
        );
    }
}
