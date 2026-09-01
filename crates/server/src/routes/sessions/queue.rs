use axum::{
    Extension, Json, Router,
    extract::{DefaultBodyLimit, State},
    middleware::from_fn_with_state,
    response::Json as ResponseJson,
    routing::get,
};
use db::models::{
    execution_process::ExecutionProcess, scratch::DraftFollowUpData, session::Session,
};
use deployment::Deployment;
use executors::{executors::BaseCodingAgent, profile::ExecutorConfig};
use serde::Deserialize;
use services::services::{container::ContainerService, queued_message::QueueStatus};
use ts_rs::TS;
use utils::response::ApiResponse;

use crate::{DeploymentImpl, error::ApiError, middleware::load_session_middleware};

const PROMPT_JSON_BODY_LIMIT_BYTES: usize = 100 * 1024 * 1024;

/// Request body for queueing a follow-up message
#[derive(Debug, Deserialize, TS)]
struct QueueMessageRequest {
    pub message: String,
    pub executor_config: ExecutorConfig,
}

/// Steer an active Codex turn, or queue the message for agents without steering.
async fn queue_message(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
    Json(payload): Json<QueueMessageRequest>,
) -> Result<ResponseJson<ApiResponse<QueueStatus>>, ApiError> {
    if !ExecutionProcess::has_running_queue_consumer_for_session(&deployment.db().pool, session.id)
        .await?
    {
        deployment
            .queued_message_service()
            .cancel_queued(session.id);
        return Err(ApiError::Conflict(
            "Cannot queue a follow-up because this session is not currently running".to_string(),
        ));
    }

    let may_fall_back_to_queue =
        should_queue_when_steer_is_unavailable(&payload.executor_config.executor);
    let data = DraftFollowUpData {
        message: payload.message,
        executor_config: payload.executor_config,
    };

    if deployment
        .container()
        .try_steer_active_turn(&session, &data)
        .await?
    {
        deployment
            .track_if_analytics_allowed(
                "active_turn_steered",
                serde_json::json!({
                    "session_id": session.id.to_string(),
                    "workspace_id": session.workspace_id.to_string(),
                }),
            )
            .await;

        return Ok(ResponseJson(ApiResponse::success(QueueStatus::Empty)));
    }

    if !may_fall_back_to_queue {
        return Err(ApiError::Conflict(
            "The active Codex turn is not ready to accept a correction. Retry while the agent is working."
                .to_string(),
        ));
    }

    let queued = deployment
        .queued_message_service()
        .queue_message(session.id, data);

    deployment
        .track_if_analytics_allowed(
            "follow_up_queued",
            serde_json::json!({
                "session_id": session.id.to_string(),
                "workspace_id": session.workspace_id.to_string(),
            }),
        )
        .await;

    Ok(ResponseJson(ApiResponse::success(QueueStatus::Queued {
        message: queued,
    })))
}

fn should_queue_when_steer_is_unavailable(executor: &BaseCodingAgent) -> bool {
    executor != &BaseCodingAgent::Codex
}

/// Cancel a queued follow-up message
async fn cancel_queued_message(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<QueueStatus>>, ApiError> {
    deployment
        .queued_message_service()
        .cancel_queued(session.id);

    deployment
        .track_if_analytics_allowed(
            "follow_up_queue_cancelled",
            serde_json::json!({
                "session_id": session.id.to_string(),
                "workspace_id": session.workspace_id.to_string(),
            }),
        )
        .await;

    Ok(ResponseJson(ApiResponse::success(QueueStatus::Empty)))
}

/// Get the current queue status for a session's workspace
async fn get_queue_status(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<QueueStatus>>, ApiError> {
    let status = deployment.queued_message_service().get_status(session.id);

    Ok(ResponseJson(ApiResponse::success(status)))
}

pub(super) fn router(deployment: &DeploymentImpl) -> Router<DeploymentImpl> {
    Router::new()
        .route(
            "/",
            get(get_queue_status)
                .post(queue_message)
                .delete(cancel_queued_message)
                .layer(DefaultBodyLimit::max(PROMPT_JSON_BODY_LIMIT_BYTES)),
        )
        .layer(from_fn_with_state(
            deployment.clone(),
            load_session_middleware,
        ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unavailable_codex_steer_never_falls_back_to_queue() {
        assert!(!should_queue_when_steer_is_unavailable(
            &BaseCodingAgent::Codex
        ));
    }

    #[test]
    fn non_codex_follow_up_keeps_queue_fallback() {
        assert!(should_queue_when_steer_is_unavailable(
            &BaseCodingAgent::ClaudeCode
        ));
    }
}
