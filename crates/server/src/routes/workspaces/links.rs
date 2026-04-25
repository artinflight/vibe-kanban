use api_types::{CreateWorkspaceRequest, PullRequestStatus, UpsertPullRequestRequest};
use axum::{
    Extension, Json, Router,
    extract::{Path as AxumPath, State},
    middleware::from_fn_with_state,
    response::Json as ResponseJson,
    routing::{delete, post},
};
use db::models::{
    merge::MergeStatus, project::Project, pull_request::PullRequest, repo::Repo, task::Task,
    workspace::Workspace, workspace_repo::WorkspaceRepo,
};
use deployment::Deployment;
use git_host::{GitHostProvider, GitHostService};
use serde::Deserialize;
use services::services::{diff_stream, remote_client::RemoteClientError, remote_sync};
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError, middleware::load_workspace_middleware};

#[derive(Debug, Deserialize)]
pub struct LinkWorkspaceRequest {
    pub project_id: Uuid,
    pub issue_id: Uuid,
}

async fn backfill_local_pr_rows_for_workspace(
    deployment: &DeploymentImpl,
    workspace: &Workspace,
) -> Result<(), ApiError> {
    let pool = &deployment.db().pool;
    let workspace_repos = WorkspaceRepo::find_by_workspace_id(pool, workspace.id).await?;
    let git = deployment.git();

    for workspace_repo in workspace_repos {
        if !PullRequest::find_by_workspace_and_repo_id(pool, workspace.id, workspace_repo.repo_id)
            .await?
            .is_empty()
        {
            continue;
        }

        let Some(repo) = Repo::find_by_id(pool, workspace_repo.repo_id).await? else {
            continue;
        };

        let remote = match git.resolve_remote_for_branch(&repo.path, &workspace_repo.target_branch)
        {
            Ok(remote) => remote,
            Err(err) => {
                tracing::warn!(
                    "Skipping PR backfill for workspace {} repo {}: failed to resolve remote for {}: {}",
                    workspace.id,
                    workspace_repo.repo_id,
                    workspace_repo.target_branch,
                    err
                );
                continue;
            }
        };

        let git_host = match GitHostService::from_url(&remote.url) {
            Ok(host) => host,
            Err(err) => {
                tracing::warn!(
                    "Skipping PR backfill for workspace {} repo {}: failed to initialize git host for {}: {}",
                    workspace.id,
                    workspace_repo.repo_id,
                    remote.url,
                    err
                );
                continue;
            }
        };

        let prs = match git_host
            .list_prs_for_branch(&repo.path, &remote.url, &workspace.branch)
            .await
        {
            Ok(prs) => prs,
            Err(err) => {
                tracing::warn!(
                    "Skipping PR backfill for workspace {} repo {} branch {}: {}",
                    workspace.id,
                    workspace_repo.repo_id,
                    workspace.branch,
                    err
                );
                continue;
            }
        };

        let Some(pr_info) = prs.into_iter().next() else {
            continue;
        };

        PullRequest::create_for_workspace(
            pool,
            workspace.id,
            workspace_repo.repo_id,
            &workspace_repo.target_branch,
            pr_info.number,
            &pr_info.url,
        )
        .await?;

        if !matches!(pr_info.status, MergeStatus::Open) {
            let merged_at = if matches!(&pr_info.status, MergeStatus::Merged) {
                pr_info.merged_at
            } else {
                None
            };

            PullRequest::update_status(
                pool,
                &pr_info.url,
                &pr_info.status,
                merged_at,
                pr_info.merge_commit_sha.clone(),
            )
            .await?;
        }
    }

    Ok(())
}

pub async fn link_workspace(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
    Json(payload): Json<LinkWorkspaceRequest>,
) -> Result<ResponseJson<ApiResponse<()>>, ApiError> {
    let project = Project::find_by_id(&deployment.db().pool, payload.project_id).await?;

    if project.remote_project_id.is_none() {
        let task = Task::find_by_id(&deployment.db().pool, payload.issue_id).await?;
        if task.as_ref().map(|task| task.project_id) == Some(payload.project_id) {
            Workspace::update_task_id(&deployment.db().pool, workspace.id, Some(payload.issue_id))
                .await?;
            if let Err(err) = backfill_local_pr_rows_for_workspace(&deployment, &workspace).await {
                tracing::error!(
                    "Failed to backfill local PR rows for workspace {} after linking: {}",
                    workspace.id,
                    err
                );
            }
            return Ok(ResponseJson(ApiResponse::success(())));
        }
    }

    let client = deployment.remote_client()?;

    let stats =
        diff_stream::compute_diff_stats(&deployment.db().pool, deployment.git(), &workspace).await;

    client
        .create_workspace(CreateWorkspaceRequest {
            project_id: payload.project_id,
            local_workspace_id: workspace.id,
            issue_id: payload.issue_id,
            name: workspace.name.clone(),
            archived: Some(workspace.archived),
            files_changed: stats.as_ref().map(|s| s.files_changed as i32),
            lines_added: stats.as_ref().map(|s| s.lines_added as i32),
            lines_removed: stats.as_ref().map(|s| s.lines_removed as i32),
        })
        .await?;

    {
        let pool = deployment.db().pool.clone();
        let ws_id = workspace.id;
        let client = client.clone();
        tokio::spawn(async move {
            let pull_requests = match PullRequest::find_by_workspace_id(&pool, ws_id).await {
                Ok(prs) => prs,
                Err(e) => {
                    tracing::error!(
                        "Failed to fetch PRs for workspace {} during link: {}",
                        ws_id,
                        e
                    );
                    return;
                }
            };
            for pr in pull_requests {
                let pr_status = match pr.pr_status {
                    MergeStatus::Open => PullRequestStatus::Open,
                    MergeStatus::Merged => PullRequestStatus::Merged,
                    MergeStatus::Closed => PullRequestStatus::Closed,
                    MergeStatus::Unknown => continue,
                };
                remote_sync::sync_pr_to_remote(
                    &client,
                    UpsertPullRequestRequest {
                        url: pr.pr_url,
                        number: pr.pr_number as i32,
                        status: pr_status,
                        merged_at: pr.merged_at,
                        merge_commit_sha: pr.merge_commit_sha,
                        target_branch_name: pr.target_branch_name,
                        local_workspace_id: ws_id,
                    },
                )
                .await;
            }
        });
    }

    Ok(ResponseJson(ApiResponse::success(())))
}

pub async fn unlink_workspace(
    AxumPath(workspace_id): AxumPath<uuid::Uuid>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<()>>, ApiError> {
    let client = deployment.remote_client()?;

    match client.delete_workspace(workspace_id).await {
        Ok(()) => Ok(ResponseJson(ApiResponse::success(()))),
        Err(RemoteClientError::Http { status: 404, .. }) => {
            Ok(ResponseJson(ApiResponse::success(())))
        }
        Err(e) => Err(e.into()),
    }
}

pub fn router(deployment: &DeploymentImpl) -> Router<DeploymentImpl> {
    let post_router = Router::new()
        .route("/", post(link_workspace))
        .layer(from_fn_with_state(
            deployment.clone(),
            load_workspace_middleware,
        ));

    let delete_router = Router::new().route("/", delete(unlink_workspace));

    post_router.merge(delete_router)
}
