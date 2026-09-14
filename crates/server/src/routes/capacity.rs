//! Private CU-to-VK scheduling control plane. No endpoint can redeem a reset.
use axum::{
    Json, Router,
    extract::{DefaultBodyLimit, State},
    http::HeaderMap,
    routing::{get, post},
};
use db::models::{
    coding_agent_turn::CodingAgentTurn,
    execution_process::{ExecutionProcess, ExecutionProcessRunReason},
    session::Session,
    workspace::Workspace,
};
use deployment::Deployment;
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_follow_up::CodingAgentFollowUpRequest,
    },
    capacity::{
        controller::{self, ManagedGoal},
        wall_ms,
    },
    executors::{
        BaseCodingAgent,
        codex::{
            client::AppServerClient,
            goals::{Progress, progress_path},
        },
    },
};
use serde::Deserialize;
use serde_json::{Value, json};
use services::services::container::ContainerService;
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

// Keep the shared HTTP error contract; this helper never constructs its large WebRTC variant.
#[allow(clippy::result_large_err)]
fn authorize(headers: &HeaderMap) -> Result<(), ApiError> {
    let path = std::env::var("VK_CAPACITY_TOKEN_FILE").map_err(|_| ApiError::Unauthorized)?;
    if !std::path::Path::new(&path).is_absolute() {
        return Err(ApiError::Unauthorized);
    }
    let metadata = std::fs::symlink_metadata(&path)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if metadata.permissions().mode() & 0o077 != 0 {
            return Err(ApiError::Unauthorized);
        }
    }
    if !metadata.is_file() || metadata.len() > 1024 {
        return Err(ApiError::Unauthorized);
    }
    let expected = std::fs::read_to_string(path)?;
    let supplied = headers
        .get("authorization")
        .and_then(|h| h.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(ApiError::Unauthorized)?;
    if expected.trim().len() < 32 {
        return Err(ApiError::Unauthorized);
    }
    let a = Sha256::digest(expected.trim().as_bytes());
    let b = Sha256::digest(supplied.as_bytes());
    if a.iter()
        .zip(b.iter())
        .fold(0u8, |diff, (x, y)| diff | (x ^ y))
        != 0
    {
        return Err(ApiError::Unauthorized);
    }
    Ok(())
}
// Preserve the shared conflict/I/O conversion without changing unrelated API errors.
#[allow(clippy::result_large_err)]
fn controller() -> Result<&'static tokio::sync::Mutex<controller::Controller>, ApiError> {
    controller::configured()?
        .ok_or_else(|| ApiError::Conflict("Unused capacity integration is not configured".into()))
}
fn conflict(error: std::io::Error) -> ApiError {
    ApiError::Conflict(error.to_string())
}
async fn foreground(
    deployment: &DeploymentImpl,
    state: &controller::State,
) -> Result<bool, ApiError> {
    Ok(ExecutionProcess::find_running(&deployment.db().pool)
        .await?
        .iter()
        .any(|p| {
            p.run_reason == ExecutionProcessRunReason::CodingAgent
                && !state.goals.values().any(|g| {
                    g.grant
                        .as_ref()
                        .is_some_and(|x| x.execution_id == Some(p.id))
                })
        }))
}
async fn status(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let state = controller()?.lock().await.state.clone();
    let running = ExecutionProcess::find_running(&deployment.db().pool).await?;
    let mut execution_states = serde_json::Map::new();
    for goal in state.goals.values() {
        if let Some(id) = goal.grant.as_ref().and_then(|g| g.execution_id)
            && let Some(process) = ExecutionProcess::find_by_id(&deployment.db().pool, id).await?
        {
            execution_states.insert(
                id.to_string(),
                serde_json::to_value(process.status).unwrap(),
            );
        }
    }
    Ok(Json(
        json!({"state":state, "foregroundActive":foreground(&deployment, &state).await?, "runningExecutionIds":running.iter().map(|p|p.id).collect::<Vec<_>>(), "executionStates":execution_states, "checkedAtMs":wall_ms()}),
    ))
}
async fn candidate(
    deployment: &DeploymentImpl,
    session: &Session,
) -> Result<ManagedGoal, ApiError> {
    let info = CodingAgentTurn::find_latest_session_info(&deployment.db().pool, session.id)
        .await?
        .ok_or_else(|| ApiError::BadRequest("No existing native thread".into()))?;
    let progress: Progress =
        serde_json::from_slice(&tokio::fs::read(progress_path(&info.session_id)?).await?)
            .map_err(|e| ApiError::BadRequest(e.to_string()))?;
    if progress.objective.trim().is_empty()
        || progress.all_complete()
        || progress.pause_reason.is_some()
    {
        return Err(ApiError::BadRequest(
            "No unfinished goal available without user input".into(),
        ));
    }
    Ok(ManagedGoal {
        session_id: session.id,
        thread_id: info.session_id,
        objective: progress.objective,
        created_at: progress.created_at,
        eligible: true,
        reason: String::new(),
        grant: None,
    })
}
async fn candidates(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    controller()?;
    let sessions = sqlx::query_as::<_, Session>("SELECT s.* FROM sessions s JOIN workspaces w ON w.id = s.workspace_id WHERE lower(s.executor) = 'codex' AND w.archived = 0 ORDER BY s.updated_at DESC LIMIT 100").fetch_all(&deployment.db().pool).await?;
    let mut values = vec![];
    for session in sessions {
        if let Ok(goal) = candidate(&deployment, &session).await {
            values.push(json!({"sessionId":session.id, "workspaceId":session.workspace_id, "name":session.name, "goal":goal}));
        }
    }
    Ok(Json(json!({"candidates":values})))
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Enrollment {
    epoch: String,
    revision: u64,
    session_id: Uuid,
    eligible: bool,
}
async fn enroll(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Enrollment>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let session = Session::find_by_id(&deployment.db().pool, input.session_id)
        .await?
        .ok_or(ApiError::BadRequest("Unknown session".into()))?;
    let mut goal = if input.eligible {
        candidate(&deployment, &session).await?
    } else {
        controller()?
            .lock()
            .await
            .state
            .goals
            .get(&session.id)
            .cloned()
            .ok_or(ApiError::BadRequest("Session is not managed".into()))?
    };
    goal.eligible = input.eligible;
    if ExecutionProcess::has_running_coding_agent_for_session(&deployment.db().pool, session.id)
        .await?
    {
        return Err(ApiError::Conflict(
            "Pause the existing goal before changing eligibility".into(),
        ));
    }
    let mut c = controller()?.lock().await;
    c.check_revision(&input.epoch, input.revision)
        .map_err(conflict)?;
    c.enroll(goal).map_err(conflict)?;
    Ok(Json(json!({"state":c.state})))
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Start {
    epoch: String,
    revision: u64,
    session_id: Uuid,
    grant_id: Uuid,
    allocation_id: String,
    expires_at_ms: u64,
    stop_at_ms: u64,
}
async fn start(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Start>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let session = Session::find_by_id(&deployment.db().pool, input.session_id)
        .await?
        .ok_or(ApiError::BadRequest("Unknown session".into()))?;
    let workspace = Workspace::find_by_id(&deployment.db().pool, session.workspace_id)
        .await?
        .filter(|w| !w.archived)
        .ok_or(ApiError::BadRequest("Workspace is unavailable".into()))?;
    let profile =
        ExecutionProcess::latest_executor_profile_for_session(&deployment.db().pool, session.id)
            .await?
            .filter(|p| p.executor == BaseCodingAgent::Codex)
            .ok_or(ApiError::BadRequest("Codex profile required".into()))?;
    let info = CodingAgentTurn::find_latest_session_info(&deployment.db().pool, session.id)
        .await?
        .ok_or(ApiError::BadRequest("Existing goal required".into()))?;
    deployment
        .container()
        .ensure_container_exists(&workspace)
        .await?;
    // Creation/migration can update container_ref. Launch with the persisted
    // workspace rather than the stale record read before preparation.
    let workspace = Workspace::find_by_id(&deployment.db().pool, workspace.id)
        .await?
        .filter(|w| !w.archived)
        .ok_or(ApiError::BadRequest("Workspace is unavailable".into()))?;
    let capacity = {
        let mut c = controller()?.lock().await;
        c.check_revision(&input.epoch, input.revision)
            .map_err(conflict)?;
        if foreground(&deployment, &c.state).await? {
            return Err(ApiError::Conflict("Interactive work takes priority".into()));
        }
        c.issue(
            session.id,
            input.grant_id,
            input.allocation_id,
            input.expires_at_ms,
            input.stop_at_ms,
            wall_ms(),
        )
        .map_err(conflict)?
    };
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
            capacity: Some(Box::new(capacity)),
            prompt: "/goal resume".into(),
            session_id: info.session_id,
            reset_to_message_id: None,
            executor_config: profile.into(),
            working_dir: session.agent_working_dir.clone(),
        }),
        None,
    );
    // Never use the normal capacity queue: a delayed request has no permission.
    match deployment
        .container()
        .start_execution(
            &workspace,
            &session,
            &action,
            &ExecutionProcessRunReason::CodingAgent,
        )
        .await
    {
        Ok(process) => Ok(Json(
            json!({"executionId":process.id, "state":controller()?.lock().await.state}),
        )),
        Err(error) => {
            controller()?
                .lock()
                .await
                .revoke_all("Launch failed; reconciling", None)?;
            Err(error.into())
        }
    }
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Renew {
    epoch: String,
    revision: u64,
    session_id: Uuid,
    grant_id: Uuid,
    allocation_id: String,
    sequence: u64,
    expires_at_ms: u64,
}
async fn renew(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Renew>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let mut c = controller()?.lock().await;
    c.check_revision(&input.epoch, input.revision)
        .map_err(conflict)?;
    if foreground(&deployment, &c.state).await? {
        c.revoke_all("Interactive work takes priority", Some(wall_ms() + 600_000))?;
        return Err(ApiError::Conflict("Interactive work takes priority".into()));
    }
    c.renew(
        input.session_id,
        input.grant_id,
        &input.allocation_id,
        input.sequence,
        input.expires_at_ms,
        wall_ms(),
    )
    .map_err(conflict)?;
    Ok(Json(json!({"state":c.state})))
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Stop {
    epoch: String,
    revision: u64,
    reason: String,
}
async fn stop(
    State(_deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Stop>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let grants = {
        let mut c = controller()?.lock().await;
        c.check_revision(&input.epoch, input.revision)
            .map_err(conflict)?;
        if input.reason.len() > 500 {
            return Err(ApiError::BadRequest("Stop reason too long".into()));
        }
        c.revoke_all(&input.reason, None)?;
        c.state
            .goals
            .values()
            .filter_map(|g| g.grant.clone().map(|x| (g.session_id, x)))
            .collect::<Vec<_>>()
    };
    for (session, grant) in grants {
        if let Some(execution) = grant.execution_id {
            let _ =
                AppServerClient::suspend_capacity_execution(execution, input.reason.clone()).await;
            if !stop_unit(execution).await? {
                continue;
            }
        }
        controller()?
            .lock()
            .await
            .stopped(session, grant.id, input.reason.clone())
            .map_err(conflict)?;
    }
    Ok(Json(json!({"state":controller()?.lock().await.state})))
}
async fn stop_unit(execution: Uuid) -> Result<bool, ApiError> {
    let unit = executors::capacity::unit_name(execution);
    let _ = tokio::time::timeout(
        std::time::Duration::from_secs(3),
        tokio::process::Command::new("systemctl")
            .args(["--user", "stop", &unit])
            .kill_on_drop(true)
            .output(),
    )
    .await;
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(2),
        tokio::process::Command::new("systemctl")
            .args([
                "--user",
                "show",
                &unit,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=ControlGroup",
            ])
            .kill_on_drop(true)
            .output(),
    )
    .await
    .map_err(|_| ApiError::Conflict("Cannot verify execution shutdown".into()))??;
    let text = String::from_utf8_lossy(&output.stdout);
    let values: std::collections::HashMap<_, _> =
        text.lines().filter_map(|l| l.split_once('=')).collect();
    if values.get("LoadState") == Some(&"not-found") {
        return Ok(true);
    }
    if !matches!(values.get("ActiveState"), Some(&"inactive" | &"failed")) {
        return Ok(false);
    }
    let Some(group) = values.get("ControlGroup") else {
        return Ok(false);
    };
    if group.is_empty() {
        return Ok(true);
    }
    if !group.starts_with('/') || group.contains("..") {
        return Ok(false);
    }
    match tokio::fs::read_to_string(format!("/sys/fs/cgroup{group}/cgroup.events")).await {
        Ok(events) => Ok(events.lines().any(|l| l == "populated 0")),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(true),
        Err(e) => Err(e.into()),
    }
}
pub fn router() -> Router<DeploymentImpl> {
    Router::new()
        .route("/capacity", get(status))
        .route("/capacity/candidates", get(candidates))
        .route("/capacity/eligibility", post(enroll))
        .route("/capacity/start", post(start))
        .route("/capacity/renew", post(renew))
        .route("/capacity/stop", post(stop))
        .layer(DefaultBodyLimit::max(16_384))
}
