use axum::{
    Extension, Json,
    extract::{Query, State},
    http::StatusCode,
    response::Json as ResponseJson,
};
use db::models::{
    execution_process::{ExecutionProcess, ExecutionProcessStatus},
    workspace::{Workspace, WorkspaceError},
};
use deployment::Deployment;
use serde::Deserialize;
use services::services::{container::ContainerService, diff_stream, remote_sync};
use sqlx::Error as SqlxError;
use utils::response::ApiResponse;
use workspace_manager::WorkspaceManager;

use super::workspace_summary::invalidate_workspace_summary_cache;
use crate::{DeploymentImpl, error::ApiError};

#[derive(Debug, Deserialize)]
pub struct DeleteWorkspaceQuery {
    #[serde(default)]
    pub delete_remote: bool,
    #[serde(default)]
    pub delete_branches: bool,
}

pub async fn get_workspaces(
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<Vec<Workspace>>>, ApiError> {
    let pool = &deployment.db().pool;
    let workspaces = Workspace::fetch_all(pool).await?;
    Ok(ResponseJson(ApiResponse::success(workspaces)))
}

pub async fn get_workspace(
    Extension(workspace): Extension<Workspace>,
) -> Result<ResponseJson<ApiResponse<Workspace>>, ApiError> {
    Ok(ResponseJson(ApiResponse::success(workspace)))
}

/// Sanitized durable status. Source bytes, prompts, policy and private inventory
/// remain outside this API; full evidence belongs in the private helper ledger.
pub async fn github_sync_status(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<serde_json::Value>>, ApiError> {
    let jobs = db::models::turn_github_sync::TurnGithubSync::for_workspace(
        &deployment.db().pool,
        workspace.id,
    )
    .await?;
    let statuses = jobs
        .into_iter()
        .map(|job| {
            let report = job
                .report
                .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok());
            serde_json::json!({"execution_process_id": job.execution_process_id,
            "state": job.state, "attempts": job.attempts,
            "observation_state": job.observation_state,
            "admission_reason": job.observation_report.as_ref().and_then(|text| serde_json::from_str::<serde_json::Value>(text).ok()).and_then(|r| r.get("admission_failure").cloned()),
            "observation_reason": job.observation_report.as_ref().and_then(|text| serde_json::from_str::<serde_json::Value>(text).ok()).map(|r| r["reason"].clone()),
            "reason": report.as_ref().and_then(|r| r["reason"].as_str()),
            "remote": report.as_ref().and_then(|r| r["repositories"].as_array()).map(|repos|
                repos.iter().map(|r| serde_json::json!({"commit": r["receipt"]["commit"],
                    "pr": r["receipt"]["pr"]["url"]})).collect::<Vec<_>>())})
        })
        .collect::<Vec<_>>();
    let pending_inputs =
        services::services::queued_message::QueuedMessageService::pending_incoming(
            &deployment.db().pool,
            workspace.id,
        )
        .await?;
    let pending_queues =
        services::services::queued_message::QueuedMessageService::pending_user_queue(
            &deployment.db().pool,
            workspace.id,
        )
        .await?;
    Ok(ResponseJson(ApiResponse::success(
        serde_json::json!({"checkpoints": statuses, "pending_input_ids": pending_inputs,
            "pending_queue_session_ids": pending_queues}),
    )))
}

pub async fn update_workspace(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
    Json(request): Json<db::models::requests::UpdateWorkspace>,
) -> Result<ResponseJson<ApiResponse<Workspace>>, ApiError> {
    let pool = &deployment.db().pool;
    let is_archiving = request.archived == Some(true) && !workspace.archived;
    let is_unarchiving = request.archived == Some(false) && workspace.archived;

    if is_archiving {
        Workspace::request_worktree_cleanup(pool, workspace.id).await?;
    } else if is_unarchiving {
        Workspace::clear_worktree_cleanup_request(pool, workspace.id).await?;
    }

    Workspace::update(
        pool,
        workspace.id,
        request.archived,
        request.pinned,
        request.name.as_deref(),
    )
    .await?;
    let updated = Workspace::find_by_id(pool, workspace.id)
        .await?
        .ok_or(WorkspaceError::WorkspaceNotFound)?;

    if (request.archived.is_some() || request.name.is_some())
        && let Ok(client) = deployment.remote_client()
    {
        let ws = updated.clone();
        let name = request.name.clone();
        let archived = request.archived;
        let stats =
            diff_stream::compute_diff_stats(&deployment.db().pool, deployment.git(), &ws).await;
        tokio::spawn(async move {
            remote_sync::sync_workspace_to_remote(
                &client,
                ws.id,
                name.map(Some),
                archived,
                stats.as_ref(),
            )
            .await;
        });
    }

    if is_archiving {
        if let Err(e) = deployment.container().archive_workspace(workspace.id).await {
            tracing::error!("Failed to archive workspace {}: {}", workspace.id, e);
        } else if let Err(e) = deployment
            .container()
            .retry_archived_workspace_cleanup_after_execution(
                workspace.id,
                &db::models::execution_process::ExecutionProcessRunReason::CleanupScript,
            )
            .await
        {
            tracing::error!(
                "Failed to start guarded cleanup for archived workspace {}: {}",
                workspace.id,
                e
            );
        }
    }

    Ok(ResponseJson(ApiResponse::success(updated)))
}

/// Explicit, exact-ID dismissal after reconciliation. Keep the private original;
/// never infer user-input handling from idle or a successful executor outcome.
pub async fn dismiss_github_sync_input(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
    Query(ResolveCheckpointInput { input_id }): Query<ResolveCheckpointInput>,
) -> Result<ResponseJson<ApiResponse<serde_json::Value>>, ApiError> {
    let dismissed = services::services::queued_message::QueuedMessageService::dismiss_incoming(
        &deployment.db().pool,
        workspace.id,
        input_id,
    )
    .await?;
    Ok(ResponseJson(ApiResponse::success(
        serde_json::json!({"dismissed": dismissed}),
    )))
}

#[derive(Deserialize)]
pub struct ResolveCheckpointInput {
    pub input_id: uuid::Uuid,
}

pub async fn get_first_user_message(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<Option<String>>>, ApiError> {
    let pool = &deployment.db().pool;
    let message = Workspace::get_first_user_message(pool, workspace.id).await?;
    Ok(ResponseJson(ApiResponse::success(message)))
}

pub async fn delete_workspace(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
    Query(query): Query<DeleteWorkspaceQuery>,
) -> Result<(StatusCode, ResponseJson<ApiResponse<()>>), ApiError> {
    let pool = &deployment.db().pool;
    let workspace_manager = deployment.workspace_manager();
    let workspace_id = workspace.id;

    if ExecutionProcess::has_running_non_dev_server_processes_for_workspace(pool, workspace_id)
        .await?
    {
        return Err(ApiError::Conflict(
            "Cannot delete workspace while processes are running. Stop all processes first."
                .to_string(),
        ));
    }

    let dev_servers =
        ExecutionProcess::find_running_dev_servers_by_workspace(pool, workspace_id).await?;

    for dev_server in dev_servers {
        tracing::info!(
            "Stopping dev server {} before deleting workspace {}",
            dev_server.id,
            workspace_id
        );

        if let Err(e) = deployment
            .container()
            .stop_execution(&dev_server, ExecutionProcessStatus::Killed)
            .await
        {
            tracing::error!(
                "Failed to stop dev server {} for workspace {}: {}",
                dev_server.id,
                workspace_id,
                e
            );
        }
    }

    let managed_workspace = workspace_manager.load_managed_workspace(workspace).await?;
    let deletion_context = managed_workspace.prepare_deletion_context().await?;
    let rows_affected = managed_workspace.delete_record().await?;

    if rows_affected == 0 {
        return Err(ApiError::Database(SqlxError::RowNotFound));
    }

    deployment
        .track_if_analytics_allowed(
            "workspace_deleted",
            serde_json::json!({
                "workspace_id": workspace_id.to_string(),
            }),
        )
        .await;

    if query.delete_remote {
        if let Ok(client) = deployment.remote_client() {
            match client.delete_workspace(workspace_id).await {
                Ok(()) => {
                    tracing::info!("Deleted remote workspace for {}", workspace_id);
                }
                Err(e) => {
                    tracing::warn!(
                        "Failed to delete remote workspace for {}: {}",
                        workspace_id,
                        e
                    );
                }
            }
        } else {
            tracing::debug!(
                "Remote client not available, skipping remote deletion for {}",
                workspace_id
            );
        }
    }

    WorkspaceManager::spawn_workspace_deletion_cleanup(deletion_context, query.delete_branches);

    Ok((StatusCode::ACCEPTED, ResponseJson(ApiResponse::success(()))))
}

#[axum::debug_handler]
pub async fn mark_seen(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<()>>, ApiError> {
    super::report_review::manual_intent(&deployment, workspace.id, true).await?;
    invalidate_workspace_summary_cache();
    Ok(ResponseJson(ApiResponse::success(())))
}

#[axum::debug_handler]
pub async fn mark_unread(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<()>>, ApiError> {
    super::report_review::manual_intent(&deployment, workspace.id, false).await?;
    invalidate_workspace_summary_cache();
    Ok(ResponseJson(ApiResponse::success(())))
}
