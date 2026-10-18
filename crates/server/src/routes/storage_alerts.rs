//! Disabled until a private reviewed owner/configuration binding is supplied.
use axum::{
    Json, Router,
    extract::{DefaultBodyLimit, Path, Query, State},
    routing::{get, post},
};
use db::models::{
    coding_agent_turn::CodingAgentTurn,
    execution_process::{ExecutionProcess, ExecutionProcessRunReason},
    session::Session,
    workspace::Workspace,
    workspace_repo::WorkspaceRepo,
};
use deployment::Deployment;
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_follow_up::CodingAgentFollowUpRequest,
    },
    executors::BaseCodingAgent,
    routing::RoutingMode,
};
use serde::Deserialize;
use services::services::{
    container::{ContainerError, ContainerService},
    storage_admission::{self as admission, OwnerBinding, Request, Response},
};
use uuid::Uuid;

use crate::error::ApiError;

fn configured() -> Result<OwnerBinding, &'static str> {
    let path = std::env::var_os("VK_STORAGE_ALERT_OWNER_FILE")
        .ok_or("Storage alert admission is disabled")?;
    let bytes = std::fs::read(path).map_err(|_| "Storage alert binding unavailable")?;
    let binding: OwnerBinding =
        serde_json::from_slice(&bytes).map_err(|_| "Invalid storage alert binding")?;
    if binding.executor_config.executor != BaseCodingAgent::Codex
        || binding
            .executor_config
            .variant
            .as_deref()
            .is_some_and(|s| s != "DEFAULT")
        || !binding
            .executor_config
            .routing
            .as_ref()
            .is_some_and(|p| p.mode == RoutingMode::Shadow)
        || binding.max_validation_age_seconds == 0
        || binding.max_validation_age_seconds > 300
    {
        return Err(
            "Storage admission requires the saved CODEX DEFAULT Recommend configuration and reviewed freshness",
        );
    }
    Ok(binding)
}

async fn submit<D: Deployment>(
    State(deployment): State<D>,
    Json(request): Json<Request>,
) -> Result<Json<Response>, ApiError> {
    let binding = configured().map_err(|reason| ApiError::Conflict(reason.into()))?;
    Ok(Json(submit_bound(&deployment, &binding, &request).await?))
}

pub(crate) async fn submit_bound<D: Deployment>(
    deployment: &D,
    binding: &OwnerBinding,
    request: &Request,
) -> Result<Response, sqlx::Error> {
    admission::submit(
        &deployment.db().pool,
        deployment.queued_message_service(),
        binding,
        request,
        |config| async move {
            if let Some(ledger) = services::services::original_worker::current()
                && (binding.session_id == ledger.contract.worker.session
                    || binding.session_id == ledger.contract.manager.session)
                && !ledger.terminal().await.map_err(|_| {
                    ContainerError::StorageAdmissionDeferred("native_owner_observation_hold")
                })?
            {
                return Err(ContainerError::StorageAdmissionDeferred(
                    "native_bound_owner_hold",
                ));
            }
            // Read the existing selection; do not synthesize or resolve a model.
            let saved = ExecutionProcess::latest_executor_config_for_session(
                &deployment.db().pool,
                binding.session_id,
            )
            .await?
            .ok_or_else(|| ContainerError::Other(anyhow::anyhow!("No saved owner configuration")))?
            .0;
            if saved != config {
                return Err(ContainerError::Other(anyhow::anyhow!(
                    "Saved owner configuration changed"
                )));
            }
            let session = Session::find_by_id(&deployment.db().pool, binding.session_id)
                .await?
                .ok_or(sqlx::Error::RowNotFound)?;
            let workspace = Workspace::find_by_id(&deployment.db().pool, binding.workspace_id)
                .await?
                .ok_or(sqlx::Error::RowNotFound)?;
            // This is a continuation of the existing native owner, never a new agent.
            let info = CodingAgentTurn::find_latest_session_info(&deployment.db().pool, session.id)
                .await?
                .ok_or_else(|| {
                    ContainerError::Other(anyhow::anyhow!(
                        "Existing native owner has no continuation binding"
                    ))
                })?;
            executors::capacity::first_run::storage_alert_ready(&info.session_id)
                .await
                .map_err(|_| {
                    ContainerError::StorageAdmissionDeferred("native_goal_or_observation_hold")
                })?;
            deployment
                .container()
                .ensure_container_exists(&workspace)
                .await?;
            let repos =
                WorkspaceRepo::find_repos_for_workspace(&deployment.db().pool, workspace.id)
                    .await?;
            let action = ExecutorAction::new(
                ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                    capacity: None,
                    prompt: request.intent.prompt.clone(),
                    session_id: info.session_id,
                    reset_to_message_id: None,
                    executor_config: config,
                    working_dir: session.agent_working_dir.clone(),
                }),
                deployment
                    .container()
                    .cleanup_actions_for_repos(&repos)
                    .map(Box::new),
            );
            executors::capacity::controller::storage_alert_scope(async {
                // Fail closed for configured controller errors, without revoking or
                // stopping unrelated owners. Local start repeats its native check.
                executors::capacity::controller::before_launch(session.id, false)
                    .await
                    .map_err(|_| {
                        ContainerError::StorageAdmissionDeferred("native_owner_or_capacity_hold")
                    })?;
                let age = chrono::Utc::now().signed_duration_since(request.validation.observed_at);
                if age.num_milliseconds() < 0
                    || age.num_seconds() > i64::from(binding.max_validation_age_seconds)
                {
                    return Err(ContainerError::StorageAdmissionDeferred(
                        "fresh_validation_required",
                    ));
                }
                deployment
                    .container()
                    .start_execution(
                        &workspace,
                        &session,
                        &action,
                        &ExecutionProcessRunReason::CodingAgent,
                    )
                    .await?;
                Ok(())
            })
            .await
        },
    )
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct BindingQuery {
    intent_sha256: String,
}

async fn lookup<D: Deployment>(
    State(deployment): State<D>,
    Path(batch): Path<Uuid>,
    Query(query): Query<BindingQuery>,
) -> Result<Json<Response>, ApiError> {
    // Reconciliation remains available when submission is disabled or binding
    // changes. The normal API authentication/origin rules still apply.
    Ok(Json(
        admission::lookup(&deployment.db().pool, batch, &query.intent_sha256).await?,
    ))
}

async fn cancel<D: Deployment>(
    State(deployment): State<D>,
    Path(batch): Path<Uuid>,
    Query(query): Query<BindingQuery>,
) -> Result<Json<Response>, ApiError> {
    Ok(Json(
        admission::cancel(&deployment.db().pool, batch, &query.intent_sha256).await?,
    ))
}

pub fn router<D: Deployment>() -> Router<D> {
    Router::new()
        .route(
            "/storage-alerts/batches",
            post(submit::<D>).layer(DefaultBodyLimit::max(65536)),
        )
        .route(
            "/storage-alerts/batches/{batch_id}",
            get(lookup::<D>).delete(cancel::<D>),
        )
        .layer(axum::middleware::from_fn(no_store))
}

async fn no_store(
    request: axum::extract::Request,
    next: axum::middleware::Next,
) -> axum::response::Response {
    let mut response = next.run(request).await;
    response.headers_mut().insert(
        axum::http::header::CACHE_CONTROL,
        axum::http::HeaderValue::from_static("no-store"),
    );
    response
}

#[cfg(test)]
mod tests;
