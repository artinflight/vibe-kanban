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

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct OwnerRegistry {
    version: u32,
    owners: Vec<OwnerBinding>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum OwnerFile {
    Legacy(OwnerBinding),
    Registry(OwnerRegistry),
}

// Additive configuration only: use the existing route, receipt ledger, owner
// lock and native launch. This is an allowlist, not new authentication.
fn select_binding(
    bytes: &[u8],
    workspace: Uuid,
    session: Uuid,
) -> Result<OwnerBinding, &'static str> {
    if bytes.len() > 65536 {
        return Err("Storage alert binding exceeds limit");
    }
    let file: OwnerFile =
        serde_json::from_slice(bytes).map_err(|_| "Invalid storage alert binding")?;
    let owners = match file {
        OwnerFile::Legacy(binding) => vec![binding],
        OwnerFile::Registry(registry) if registry.version == 1 => registry.owners,
        OwnerFile::Registry(_) => return Err("Unsupported storage alert registry version"),
    };
    if owners.is_empty() || owners.len() > 16 {
        return Err("Invalid storage alert owner count");
    }
    let mut seen = std::collections::HashSet::new();
    if owners.iter().any(|b| {
        b.workspace_id.is_nil()
            || b.session_id.is_nil()
            || !seen.insert((b.workspace_id, b.session_id))
    }) {
        return Err("Invalid or duplicate storage alert owner");
    }
    owners
        .into_iter()
        .find(|b| b.workspace_id == workspace && b.session_id == session)
        .ok_or("Storage alert owner is not configured")
}

fn configured(workspace: Uuid, session: Uuid) -> Result<OwnerBinding, &'static str> {
    let path = std::env::var_os("VK_STORAGE_ALERT_OWNER_FILE")
        .ok_or("Storage alert admission is disabled")?;
    // Bound the read before allocation, including an accidentally replaced file.
    use std::io::Read;
    let mut bytes = Vec::new();
    std::fs::File::open(path)
        .map_err(|_| "Storage alert binding unavailable")?
        .take(65537)
        .read_to_end(&mut bytes)
        .map_err(|_| "Storage alert binding unavailable")?;
    let binding = select_binding(&bytes, workspace, session)?;
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
    let binding = configured(request.intent.workspace_id, request.intent.session_id)
        .map_err(|reason| ApiError::Conflict(reason.into()))?;
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
            watcher_owner_idle(&deployment.db().pool, binding).await?;
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
            // Recover ordinary interrupted instructions exactly as native user
            // follow-up does. The immutable submitted intent stays unchanged;
            // the effective prompt is persisted with this execution's action.
            let interrupted_context =
                CodingAgentTurn::find_interrupted_context_since_latest_success(
                    &deployment.db().pool,
                    session.id,
                )
                .await?;
            let prompt = CodingAgentTurn::prompt_with_interrupted_context(
                request.intent.prompt.clone(),
                &interrupted_context,
            );
            let action = ExecutorAction::new(
                ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                    capacity: None,
                    prompt,
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

/// Parent status alone does not close its capture or descendant producers.
/// This runs while the native workspace admission lock/reservation is held.
/// The durable service also checks every workspace session and both user queues.
async fn watcher_owner_idle(
    pool: &sqlx::SqlitePool,
    binding: &OwnerBinding,
) -> Result<(), ContainerError> {
    let workspace = binding.workspace_id;
    let registered = executors::executors::codex::client::AppServerClient::registered_executions()
        .map_err(|_| {
            ContainerError::StorageAdmissionDeferred("native_producer_inventory_unknown")
        })?;
    for id in registered {
        let owned:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.id=? AND s.workspace_id=?)")
            .bind(id).bind(workspace).fetch_one(pool).await?;
        if owned {
            return Err(ContainerError::StorageAdmissionDeferred(
                "native_root_producer_still_registered",
            ));
        }
    }
    watcher_delegation_journals_closed(pool, binding).await?;
    let unclosed: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.run_reason='codingagent' AND NOT EXISTS(SELECT 1 FROM workspace_review_log_finalized f WHERE f.execution_id=e.id) AND NOT EXISTS(SELECT 1 FROM execution_processes newer JOIN coding_agent_turns n ON n.execution_process_id=newer.id JOIN coding_agent_turns old ON old.execution_process_id=e.id WHERE newer.session_id=e.session_id AND newer.created_at > e.created_at AND n.agent_session_id=old.agent_session_id AND old.agent_session_id IS NOT NULL))",
    ).bind(workspace).fetch_one(pool).await?;
    if unclosed {
        return Err(ContainerError::StorageAdmissionDeferred(
            "owner_capture_not_closed",
        ));
    }
    let sessions: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM sessions WHERE workspace_id=?")
        .bind(workspace)
        .fetch_all(pool)
        .await?;
    let counts =
        db::models::subagent_job::SubagentJob::active_counts_by_session_ids_with_codex_threads(
            pool, &sessions,
        )
        .await
        .map_err(|_| {
            ContainerError::StorageAdmissionDeferred("independent_job_inventory_unknown")
        })?;
    if counts.values().any(|c| c.running > 0) {
        return Err(ContainerError::StorageAdmissionDeferred(
            "owner_independent_jobs_active",
        ));
    }
    if counts.values().any(|c| c.unresolved > 0) {
        return Err(ContainerError::StorageAdmissionDeferred(
            "independent_job_inventory_unknown",
        ));
    }
    if !db::models::subagent_job::SubagentJob::watcher_producers_closed(pool, &sessions)
        .await
        .map_err(|_| {
            ContainerError::StorageAdmissionDeferred("independent_job_inventory_unknown")
        })?
    {
        return Err(ContainerError::StorageAdmissionDeferred(
            "independent_job_producers_not_closed",
        ));
    }
    Ok(())
}

/// Legacy controlled children need custody as well as the new pre-inference
/// leases. Read the existing bounded journals; never erase uncertain entries.
/// Reviewed binding is configuration, not a new access-control boundary.
async fn watcher_delegation_journals_closed(
    pool: &sqlx::SqlitePool,
    binding: &OwnerBinding,
) -> Result<(), ContainerError> {
    use std::io::Read;
    let unknown =
        || ContainerError::StorageAdmissionDeferred("delegation_producer_inventory_unknown");
    let dir = binding
        .delegation_journal_dir
        .as_ref()
        .ok_or_else(unknown)?;
    if !dir.is_absolute() || !dir.is_dir() {
        return Err(unknown());
    }
    if let Some(availability) = std::env::var_os("VK_CODEX_ROUTING_AVAILABILITY") {
        let expected = std::path::PathBuf::from(availability)
            .parent()
            .ok_or_else(unknown)?
            .join("delegation");
        if expected.canonicalize().map_err(|_| unknown())?
            != dir.canonicalize().map_err(|_| unknown())?
        {
            return Err(unknown());
        }
    }
    let threads:Vec<String>=sqlx::query_scalar("SELECT DISTINCT cat.agent_session_id FROM coding_agent_turns cat JOIN execution_processes e ON e.id=cat.execution_process_id JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND cat.agent_session_id IS NOT NULL LIMIT 4097")
        .bind(binding.workspace_id).fetch_all(pool).await?;
    if threads.len() > 4096 {
        return Err(unknown());
    }
    let mut remaining_bytes = 16 * 1024 * 1024_u64;
    for thread in threads {
        if thread.is_empty()
            || thread.len() > 128
            || !thread
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
        {
            return Err(unknown());
        }
        let path = dir.join(format!("{thread}.json"));
        let metadata = match std::fs::symlink_metadata(&path) {
            Ok(value) => value,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
            Err(_) => return Err(unknown()),
        };
        if !metadata.is_file()
            || metadata.len() > 2 * 1024 * 1024
            || metadata.len() > remaining_bytes
        {
            return Err(unknown());
        }
        remaining_bytes -= metadata.len();
        let mut bytes = Vec::new();
        std::fs::File::open(path)
            .map_err(|_| unknown())?
            .take(2 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| unknown())?;
        if bytes.len() > 2 * 1024 * 1024 {
            return Err(unknown());
        }
        let records: std::collections::BTreeMap<String, serde_json::Value> =
            serde_json::from_slice(&bytes).map_err(|_| unknown())?;
        if records.len() > 4096
            || records.values().any(|r| {
                !matches!(
                    r["status"].as_str(),
                    Some("completed" | "failed" | "interrupted" | "blocked" | "cancelled")
                )
            })
        {
            return Err(ContainerError::StorageAdmissionDeferred(
                "delegation_job_lifetime_unsettled",
            ));
        }
    }
    Ok(())
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

#[cfg(test)]
mod registry_tests;
