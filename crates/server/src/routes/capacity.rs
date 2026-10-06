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
    scratch::{Scratch, ScratchPayload, ScratchType},
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
        first_run::{self, FirstRun, InitializationState},
        wall_ms,
    },
    executors::{BaseCodingAgent, codex::client::AppServerClient},
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
// HTTP protocol version stays compatible with CU's version-1 parser. The
// independently versioned durable ledger remains v2 so old VK binaries cannot
// discard initialization receipts or holds on rollback.
fn wire_state(state: &controller::State) -> controller::State {
    let mut wire = state.clone();
    wire.version = 1;
    wire
}

async fn status(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let state = {
        let c = controller()?.lock().await;
        c.ensure_owner().map_err(conflict)?;
        c.state.clone()
    };
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
    let mut workspace_ids = serde_json::Map::new();
    for goal in state.goals.values() {
        if let Some(session) = Session::find_by_id(&deployment.db().pool, goal.session_id).await? {
            workspace_ids.insert(goal.session_id.to_string(), json!(session.workspace_id));
        }
    }
    Ok(Json(
        json!({"workspaceIds":workspace_ids,"capabilities":{"maxConcurrentGoals":2,"targetedStop":true,"scheduledGoalInitialization":if first_run::enabled() {1} else {0}},"state":wire_state(&state), "foregroundActive":foreground(&deployment, &state).await?, "runningExecutionIds":running.iter().map(|p|p.id).collect::<Vec<_>>(), "executionStates":execution_states, "checkedAtMs":wall_ms()}),
    ))
}
async fn candidate(
    deployment: &DeploymentImpl,
    session: &Session,
) -> Result<ManagedGoal, ApiError> {
    let info = CodingAgentTurn::find_latest_session_info(&deployment.db().pool, session.id)
        .await?
        .ok_or_else(|| ApiError::BadRequest("No existing native thread".into()))?;
    let native = first_run::native(&info.session_id)
        .await
        .map_err(conflict)?;
    let progress = first_run::read_progress(&native).map_err(conflict)?;
    let initialization_state = first_run::classify(&native, progress.as_ref()).map_err(conflict)?;
    let binding = first_run::binding(
        &utils::assets::asset_dir().join("db.v2.sqlite"),
        session.id,
        &info.session_id,
        None,
    )
    .await
    .map_err(conflict)?;
    Ok(ManagedGoal {
        goal_id: native.goal_id,
        initialization_state,
        binding: Some(binding),
        initialization_receipt: None,
        session_id: session.id,
        thread_id: info.session_id,
        objective: native.objective,
        created_at: native.created_at,
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
    let c = controller()?.lock().await;
    c.ensure_owner().map_err(conflict)?;
    let sessions = sqlx::query_as::<_, Session>("SELECT s.* FROM sessions s JOIN workspaces w ON w.id = s.workspace_id WHERE lower(s.executor) = 'codex' AND w.archived = 0 ORDER BY s.updated_at DESC LIMIT 100").fetch_all(&deployment.db().pool).await?;
    let mut values = vec![];
    for session in sessions {
        if c.state
            .goals
            .get(&session.id)
            .is_some_and(|g| g.grant.is_some())
        {
            continue;
        }
        if let Ok(goal) = candidate(&deployment, &session).await {
            if c.state.goals.get(&session.id).is_some_and(|old| {
                old.same_native_identity(&goal)
                    && (old.initialization_state != goal.initialization_state
                        || old.initialization_state == InitializationState::Held
                        || (old.initialization_state == InitializationState::Pending
                            && old.initialization_receipt.is_some()))
            }) {
                continue;
            }
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
    first_run: Option<FirstRun>,
}
async fn enroll(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Enrollment>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    // Discovery and enrollment share the same epoch/revision fence. Discovery
    // never loads the native engine or creates a checkpoint.
    let mut c = controller()?.lock().await;
    c.check_revision(&input.epoch, input.revision)
        .map_err(conflict)?;
    let mut goal = if input.eligible {
        let session = Session::find_by_id(&deployment.db().pool, input.session_id)
            .await?
            .ok_or(ApiError::BadRequest("Unknown session".into()))?;
        let goal = candidate(&deployment, &session).await?;
        goal.check_first_run(input.first_run.as_ref())
            .map_err(conflict)?;
        goal.revalidate(None, false).await.map_err(conflict)?;
        goal
    } else {
        if input.first_run.is_some() {
            return Err(ApiError::BadRequest("Removal must omit firstRun".into()));
        }
        c.state
            .goals
            .get(&input.session_id)
            .cloned()
            .ok_or(ApiError::BadRequest("Session is not managed".into()))?
    };
    goal.eligible = input.eligible;
    c.enroll(goal).map_err(conflict)?;
    Ok(Json(json!({"state":wire_state(&c.state)})))
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
    first_run: Option<FirstRun>,
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
        .filter(|w| !w.archived && !w.worktree_deleted)
        .ok_or(ApiError::BadRequest("Workspace is unavailable".into()))?;
    let (mut executor_config, selected_at) =
        ExecutionProcess::latest_executor_config_for_session(&deployment.db().pool, session.id)
            .await?
            .ok_or(ApiError::BadRequest(
                "Existing executor configuration required".into(),
            ))?;
    // A saved per-chat selection made since that execution is the user's newer
    // intent. Keep its draft text untouched; scheduling only resumes the goal.
    if let Some(scratch) = Scratch::find_by_id(
        &deployment.db().pool,
        session.id,
        &ScratchType::DraftFollowUp,
    )
    .await?
        && scratch.updated_at >= selected_at
        && let ScratchPayload::DraftFollowUp(draft) = scratch.payload
    {
        executor_config = draft.executor_config;
    }
    if executor_config.executor != BaseCodingAgent::Codex {
        return Err(ApiError::BadRequest("Codex configuration required".into()));
    }
    let info = CodingAgentTurn::find_latest_session_info(&deployment.db().pool, session.id)
        .await?
        .ok_or(ApiError::BadRequest("Existing goal required".into()))?;
    // Scheduled authority cannot recreate a removed workspace. Admission and
    // the worker require its existing directory and completed native anchor.
    let capacity = {
        let mut c = controller()?.lock().await;
        c.check_revision(&input.epoch, input.revision)
            .map_err(conflict)?;
        let ready = candidate(&deployment, &session).await?;
        let selected = c
            .state
            .goals
            .get(&session.id)
            .ok_or_else(|| ApiError::BadRequest("Select this goal first".into()))?;
        if selected.thread_id != ready.thread_id
            || selected.objective != ready.objective
            || selected.created_at != ready.created_at
            || (!selected.goal_id.is_empty() && selected.goal_id != ready.goal_id)
            || selected.initialization_state != ready.initialization_state
            || (selected.initialization_state == InitializationState::Pending
                && selected.binding != ready.binding)
        {
            return Err(ApiError::BadRequest(
                "Selected goal changed; select its new objective explicitly".into(),
            ));
        }
        selected
            .check_first_run(input.first_run.as_ref())
            .map_err(conflict)?;
        ready.revalidate(None, false).await.map_err(conflict)?;
        if foreground(&deployment, &c.state).await? {
            return Err(ApiError::Conflict("Interactive work takes priority".into()));
        }
        for other in c.state.goals.values().filter(|g| g.grant.is_some()) {
            let other_session = Session::find_by_id(&deployment.db().pool, other.session_id)
                .await?
                .ok_or(ApiError::Conflict(
                    "Existing background session is unavailable".into(),
                ))?;
            if other_session.workspace_id == session.workspace_id {
                return Err(ApiError::Conflict(
                    "Only one background agent may write to a workspace at a time".into(),
                ));
            }
        }
        // Checkpointed resumes advance the completed anchor only after checking
        // the enrolled native identity; first runs require the original anchor.
        c.issue_with_first_run(
            session.id,
            input.grant_id,
            input.allocation_id,
            input.expires_at_ms,
            input.stop_at_ms,
            wall_ms(),
            input.first_run,
            ready.binding,
        )
        .map_err(conflict)?
    };
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
            capacity: Some(Box::new(capacity)),
            prompt: "/goal resume".into(),
            session_id: info.session_id,
            reset_to_message_id: None,
            executor_config,
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
            json!({"executionId":process.id, "state":wire_state(&controller()?.lock().await.state)}),
        )),
        Err(error) => {
            controller()?
                .lock()
                .await
                .revoke_session(session.id, "Launch failed; reconciling")?;
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
    Ok(Json(json!({"state":wire_state(&c.state)})))
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Stop {
    epoch: String,
    revision: u64,
    reason: String,
    #[serde(default)]
    session_id: Option<Uuid>,
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
        if let Some(session) = input.session_id {
            c.revoke_session(session, &input.reason)?;
        } else {
            c.revoke_all(&input.reason, None)?;
        }
        c.state
            .goals
            .values()
            .filter(|g| input.session_id.is_none_or(|id| g.session_id == id))
            .filter_map(|g| g.grant.clone().map(|x| (g.session_id, x)))
            .collect::<Vec<_>>()
    };
    for (session, grant) in grants {
        if let Some(execution) = grant.execution_id {
            let _ =
                AppServerClient::suspend_capacity_execution(execution, input.reason.clone()).await;
            if !controller::stop_execution_unit(execution).await? {
                continue;
            }
        }
        controller()?
            .lock()
            .await
            .stopped(session, grant.id, input.reason.clone())
            .map_err(conflict)?;
    }
    Ok(Json(
        json!({"state":wire_state(&controller()?.lock().await.state)}),
    ))
}
pub fn router() -> Router<DeploymentImpl> {
    Router::new()
        .route("/capacity", get(status))
        .route("/capacity/candidates", get(candidates))
        .route("/capacity/eligibility", post(enroll))
        .route("/capacity/start", post(start))
        .route("/capacity/renew", post(renew))
        .route("/capacity/stop", post(stop))
        .route("/capacity/ownership", get(ownership))
        .route("/capacity/ownership/release", post(release_ownership))
        .route("/capacity/ownership/acquire", post(acquire_ownership))
        .layer(DefaultBodyLimit::max(16_384))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Ownership {
    epoch: String,
    revision: u64,
}

async fn ownership(headers: HeaderMap) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let c = controller()?.lock().await;
    Ok(Json(json!({"protocolVersion":1,"owned":c.is_owner(),
        "state":if c.is_owner() { Some(wire_state(&c.state)) } else { None }})))
}

async fn release_ownership(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Ownership>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let mut c = controller()?.lock().await;
    if !ExecutionProcess::find_running(&deployment.db().pool)
        .await?
        .is_empty()
    {
        return Err(ApiError::Conflict(
            "Drain executions before releasing capacity ownership".into(),
        ));
    }
    let state = c.release(&input.epoch, input.revision).map_err(conflict)?;
    Ok(Json(
        json!({"protocolVersion":1,"owned":false,"state":wire_state(&state)}),
    ))
}

async fn acquire_ownership(
    State(deployment): State<DeploymentImpl>,
    headers: HeaderMap,
    Json(input): Json<Ownership>,
) -> Result<Json<Value>, ApiError> {
    authorize(&headers)?;
    let mut c = controller()?.lock().await;
    if !ExecutionProcess::find_running(&deployment.db().pool)
        .await?
        .is_empty()
    {
        return Err(ApiError::Conflict(
            "Drain executions before acquiring capacity ownership".into(),
        ));
    }
    c.acquire(&input.epoch, input.revision).map_err(conflict)?;
    Ok(Json(
        json!({"protocolVersion":1,"owned":true,"state":wire_state(&c.state)}),
    ))
}
