pub mod queue;
pub mod review;

use std::{
    path::{Path, PathBuf},
    time::SystemTime,
};

use axum::{
    Extension, Json, Router,
    extract::{DefaultBodyLimit, Query, State},
    middleware::from_fn_with_state,
    response::Json as ResponseJson,
    routing::{get, post},
};
use db::models::{
    coding_agent_turn::CodingAgentTurn,
    execution_process::{ExecutionProcess, ExecutionProcessRunReason},
    requests::UpdateSession,
    scratch::{Scratch, ScratchType},
    session::{CreateSession, Session, SessionError},
    workspace::{Workspace, WorkspaceError},
    workspace_repo::WorkspaceRepo,
};
use deployment::Deployment;
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_follow_up::CodingAgentFollowUpRequest,
        coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::BaseCodingAgent,
    profile::ExecutorConfig,
};
use serde::Deserialize;
use services::services::{
    container::ContainerService,
    events::{execution_process_patch, workspace_patch},
};
use sqlx::{Row, SqlitePool};
use ts_rs::TS;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{
    DeploymentImpl, error::ApiError, middleware::load_session_middleware,
    routes::workspaces::execution::RunScriptError,
};

const PROMPT_JSON_BODY_LIMIT_BYTES: usize = 100 * 1024 * 1024;
const CODEX_USAGE_SAFE_STATE_RELATIVE_PATH: &str = ".vibe/current-state.md";
const DEFAULT_CODEX_RESUME_HISTORY_LIMIT_BYTES: u64 = 8 * 1024 * 1024;
const RECENT_STATE_TURN_LIMIT: i64 = 6;
const STATE_FIELD_CHAR_LIMIT: usize = 4096;

#[derive(Debug, Deserialize)]
pub struct SessionQuery {
    pub workspace_id: Uuid,
}

#[derive(Debug, Deserialize, TS)]
pub struct CreateSessionRequest {
    pub workspace_id: Uuid,
    pub executor: Option<String>,
    pub name: Option<String>,
}

pub async fn get_sessions(
    State(deployment): State<DeploymentImpl>,
    Query(query): Query<SessionQuery>,
) -> Result<ResponseJson<ApiResponse<Vec<Session>>>, ApiError> {
    let pool = &deployment.db().pool;
    let sessions = Session::find_by_workspace_id(pool, query.workspace_id).await?;
    Ok(ResponseJson(ApiResponse::success(sessions)))
}

pub async fn get_session(
    Extension(session): Extension<Session>,
) -> Result<ResponseJson<ApiResponse<Session>>, ApiError> {
    Ok(ResponseJson(ApiResponse::success(session)))
}

pub async fn create_session(
    State(deployment): State<DeploymentImpl>,
    Json(payload): Json<CreateSessionRequest>,
) -> Result<ResponseJson<ApiResponse<Session>>, ApiError> {
    let pool = &deployment.db().pool;

    // Verify workspace exists
    let _workspace = Workspace::find_by_id(pool, payload.workspace_id)
        .await?
        .ok_or(ApiError::Workspace(WorkspaceError::ValidationError(
            "Workspace not found".to_string(),
        )))?;

    let session = Session::create(
        pool,
        &CreateSession {
            executor: payload.executor,
            name: payload.name,
        },
        Uuid::new_v4(),
        payload.workspace_id,
    )
    .await?;

    Ok(ResponseJson(ApiResponse::success(session)))
}

pub async fn update_session(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
    Json(request): Json<UpdateSession>,
) -> Result<ResponseJson<ApiResponse<Session>>, ApiError> {
    let pool = &deployment.db().pool;

    Session::update(pool, session.id, request.name.as_deref()).await?;

    let updated = Session::find_by_id(pool, session.id)
        .await?
        .ok_or(ApiError::Session(SessionError::NotFound))?;

    Ok(ResponseJson(ApiResponse::success(updated)))
}

#[derive(Debug, Deserialize, TS)]
pub struct CreateFollowUpAttempt {
    pub prompt: String,
    pub executor_config: ExecutorConfig,
    pub retry_process_id: Option<Uuid>,
    pub force_when_dirty: Option<bool>,
    pub perform_git_reset: Option<bool>,
}

#[derive(Debug, Deserialize, TS)]
pub struct ResetProcessRequest {
    pub process_id: Uuid,
    pub force_when_dirty: Option<bool>,
    pub perform_git_reset: Option<bool>,
}

#[derive(Debug)]
struct RecentCodingTurn {
    created_at: String,
    prompt: Option<String>,
    summary: Option<String>,
}

#[derive(Debug)]
struct CodexUsageSafeResume {
    state_path: PathBuf,
    previous_session_bytes: u64,
    recent_turns: Vec<RecentCodingTurn>,
}

async fn prepare_codex_usage_safe_resume(
    pool: &SqlitePool,
    workspace: &Workspace,
    session: &Session,
    agent_session_id: &str,
) -> Result<Option<CodexUsageSafeResume>, ApiError> {
    if !codex_usage_safe_resume_enabled() {
        return Ok(None);
    }

    let Some(previous_session_bytes) = find_codex_session_size(agent_session_id).await else {
        tracing::debug!(
            "Codex usage-safe resume skipped: could not find session JSONL for {}",
            agent_session_id
        );
        return Ok(None);
    };

    let limit = codex_resume_history_limit_bytes();
    if previous_session_bytes <= limit {
        return Ok(None);
    }

    let workspace_root = workspace.container_ref.as_ref().ok_or_else(|| {
        ApiError::BadRequest("Workspace container path is not available".to_string())
    })?;
    let state_path = PathBuf::from(workspace_root).join(CODEX_USAGE_SAFE_STATE_RELATIVE_PATH);
    let recent_turns = load_recent_coding_turns(pool, session.id, RECENT_STATE_TURN_LIMIT).await?;

    Ok(Some(CodexUsageSafeResume {
        state_path,
        previous_session_bytes,
        recent_turns,
    }))
}

async fn write_codex_usage_safe_state(
    resume: &CodexUsageSafeResume,
    workspace: &Workspace,
    user_prompt: &str,
) -> Result<(), ApiError> {
    if let Some(parent) = resume.state_path.parent() {
        tokio::fs::create_dir_all(parent).await.map_err(|e| {
            ApiError::BadRequest(format!("Failed to create compact state directory: {e}"))
        })?;
    }

    let content = build_codex_usage_safe_state(
        workspace,
        user_prompt,
        resume.previous_session_bytes,
        &resume.recent_turns,
    );

    tokio::fs::write(&resume.state_path, content)
        .await
        .map_err(|e| ApiError::BadRequest(format!("Failed to write compact state file: {e}")))?;

    Ok(())
}

fn build_codex_usage_safe_prompt(
    user_prompt: &str,
    state_path: &Path,
    previous_session_bytes: u64,
) -> String {
    format!(
        r#"Vibe Kanban is starting a fresh Codex thread for this follow-up because the previous Codex thread history is too large to resume safely ({previous_session_bytes} bytes).

Use the compact current-state file instead of asking for or reloading the old chat:
{state_path}

Rules for this turn:
- Read the compact state file first, then inspect only the files needed for the user's request.
- Do not re-read old conversation logs, large handoff ledgers, evidence folders, or screenshots unless the current request explicitly requires them.
- Continue within this turn until the requested objective is complete or you are blocked by a concrete missing input.
- Before ending, update the compact state file with the current status, changed files, validation, blockers, and next action.
- Keep status reporting short and avoid duplicate summaries.

User request:
{user_prompt}"#,
        state_path = state_path.display()
    )
}

fn build_codex_usage_safe_state(
    workspace: &Workspace,
    user_prompt: &str,
    previous_session_bytes: u64,
    turns: &[RecentCodingTurn],
) -> String {
    let mut content = format!(
        r#"# Vibe Kanban Current State

Workspace: {workspace_name}
Workspace ID: {workspace_id}
Updated by VK: {updated_at}
Previous Codex thread bytes: {previous_session_bytes}

Purpose: compact continuity for usage-safe Codex follow-ups. Agents should resume from this file and the repository state, not from old chat history.

## Current User Request

{user_prompt}

## Operating Rules

- Prefer this file plus direct repo inspection over old chat/history replay.
- Do not repeatedly scan evidence, screenshots, logs, or handoff files unless they are directly needed.
- Persist in one managed objective until done or concretely blocked.
- Before ending a long-running turn, update this file with current status, changed files, validation, blockers, and next action.

## Recent Agent Turns
"#,
        workspace_name = workspace.name.as_deref().unwrap_or("(unnamed)"),
        workspace_id = workspace.id,
        updated_at = chrono::Utc::now().to_rfc3339(),
        user_prompt = truncate_state_field(user_prompt),
    );

    if turns.is_empty() {
        content.push_str("\nNo previous coding-agent summaries were available.\n");
    } else {
        for turn in turns {
            content.push_str(&format!(
                r#"
### {created_at}

Prompt:
{prompt}

Summary:
{summary}
"#,
                created_at = turn.created_at,
                prompt = turn
                    .prompt
                    .as_deref()
                    .map(truncate_state_field)
                    .unwrap_or_else(|| "(not recorded)".to_string()),
                summary = turn
                    .summary
                    .as_deref()
                    .map(truncate_state_field)
                    .unwrap_or_else(|| "(not recorded)".to_string()),
            ));
        }
    }

    content
}

async fn load_recent_coding_turns(
    pool: &SqlitePool,
    session_id: Uuid,
    limit: i64,
) -> Result<Vec<RecentCodingTurn>, sqlx::Error> {
    let rows = sqlx::query(
        r#"SELECT cat.created_at, cat.prompt, cat.summary
           FROM coding_agent_turns cat
           JOIN execution_processes ep ON ep.id = cat.execution_process_id
           WHERE ep.session_id = ?
             AND ep.run_reason = 'codingagent'
             AND ep.dropped = 0
           ORDER BY ep.created_at DESC
           LIMIT ?"#,
    )
    .bind(session_id)
    .bind(limit)
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| RecentCodingTurn {
            created_at: row.get::<String, _>("created_at"),
            prompt: row.get::<Option<String>, _>("prompt"),
            summary: row.get::<Option<String>, _>("summary"),
        })
        .collect())
}

async fn find_codex_session_size(agent_session_id: &str) -> Option<u64> {
    let session_id = agent_session_id.to_string();
    tokio::task::spawn_blocking(move || {
        let codex_home = std::env::var("CODEX_HOME")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var("HOME")
                    .ok()
                    .map(|home| PathBuf::from(home).join(".codex"))
            })?;
        let sessions_root = codex_home.join("sessions");
        find_session_jsonl_size_in_root(&sessions_root, &session_id)
    })
    .await
    .ok()
    .flatten()
}

fn find_session_jsonl_size_in_root(root: &Path, agent_session_id: &str) -> Option<u64> {
    let mut stack = vec![root.to_path_buf()];
    let mut newest_match: Option<(SystemTime, u64)> = None;

    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let Ok(metadata) = entry.metadata() else {
                continue;
            };
            if metadata.is_dir() {
                stack.push(path);
                continue;
            }

            let Some(file_name) = path.file_name().and_then(|name| name.to_str()) else {
                continue;
            };
            if !file_name.ends_with(".jsonl") || !file_name.contains(agent_session_id) {
                continue;
            }

            let modified = metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH);
            if newest_match
                .as_ref()
                .map(|(existing_modified, _)| modified > *existing_modified)
                .unwrap_or(true)
            {
                newest_match = Some((modified, metadata.len()));
            }
        }
    }

    newest_match.map(|(_, len)| len)
}

fn codex_usage_safe_resume_enabled() -> bool {
    !env_flag_is_false("VK_CODEX_USAGE_SAFE_RESUME")
}

fn codex_resume_history_limit_bytes() -> u64 {
    std::env::var("VK_CODEX_RESUME_HISTORY_LIMIT_BYTES")
        .ok()
        .and_then(|value| value.trim().parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(DEFAULT_CODEX_RESUME_HISTORY_LIMIT_BYTES)
}

fn env_flag_is_false(name: &str) -> bool {
    std::env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "0" | "false" | "no" | "off"
            )
        })
        .unwrap_or(false)
}

fn truncate_state_field(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.chars().count() <= STATE_FIELD_CHAR_LIMIT {
        return trimmed.to_string();
    }

    let mut truncated = trimmed
        .chars()
        .take(STATE_FIELD_CHAR_LIMIT)
        .collect::<String>();
    truncated.push_str("\n...[truncated]");
    truncated
}

pub async fn follow_up(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
    Json(payload): Json<CreateFollowUpAttempt>,
) -> Result<ResponseJson<ApiResponse<ExecutionProcess>>, ApiError> {
    let pool = &deployment.db().pool;

    // Load workspace from session
    let workspace = Workspace::find_by_id(pool, session.workspace_id)
        .await?
        .ok_or(ApiError::Workspace(WorkspaceError::ValidationError(
            "Workspace not found".to_string(),
        )))?;

    tracing::info!("{:?}", workspace);

    deployment
        .container()
        .ensure_container_exists(&workspace)
        .await?;

    let executor_profile_id = payload.executor_config.profile_id();

    // Validate executor matches session if session has prior executions
    let expected_executor: Option<String> =
        ExecutionProcess::latest_executor_profile_for_session(pool, session.id)
            .await?
            .map(|profile| profile.executor.to_string())
            .or_else(|| session.executor.clone());

    if let Some(expected) = expected_executor {
        let actual = executor_profile_id.executor.to_string();
        if expected != actual {
            return Err(ApiError::Session(SessionError::ExecutorMismatch {
                expected,
                actual,
            }));
        }
    }

    if session.executor.is_none() {
        Session::update_executor(pool, session.id, &executor_profile_id.executor.to_string())
            .await?;
    }

    if let Some(proc_id) = payload.retry_process_id {
        let force_when_dirty = payload.force_when_dirty.unwrap_or(false);
        let perform_git_reset = payload.perform_git_reset.unwrap_or(true);
        deployment
            .container()
            .reset_session_to_process(session.id, proc_id, perform_git_reset, force_when_dirty)
            .await?;
    }

    let latest_session_info = CodingAgentTurn::find_latest_session_info(pool, session.id).await?;

    let prompt = payload.prompt;

    let repos = WorkspaceRepo::find_repos_for_workspace(pool, workspace.id).await?;
    let cleanup_action = deployment.container().cleanup_actions_for_repos(&repos);

    let working_dir = session
        .agent_working_dir
        .as_ref()
        .filter(|dir| !dir.is_empty())
        .cloned();

    let action_type = if let Some(info) = latest_session_info {
        let is_reset = payload.retry_process_id.is_some();
        if !is_reset
            && payload.executor_config.executor == BaseCodingAgent::Codex
            && let Some(usage_safe_resume) =
                prepare_codex_usage_safe_resume(pool, &workspace, &session, &info.session_id)
                    .await?
        {
            write_codex_usage_safe_state(&usage_safe_resume, &workspace, &prompt).await?;
            tracing::warn!(
                session_id = %session.id,
                workspace_id = %workspace.id,
                agent_session_id = %info.session_id,
                previous_session_bytes = usage_safe_resume.previous_session_bytes,
                state_path = %usage_safe_resume.state_path.display(),
                "Starting usage-safe fresh Codex thread instead of resuming oversized history"
            );
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: build_codex_usage_safe_prompt(
                    &prompt,
                    &usage_safe_resume.state_path,
                    usage_safe_resume.previous_session_bytes,
                ),
                executor_config: payload.executor_config.clone(),
                working_dir: working_dir.clone(),
            })
        } else {
            ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                prompt: prompt.clone(),
                session_id: info.session_id,
                reset_to_message_id: if is_reset { info.message_id } else { None },
                executor_config: payload.executor_config.clone(),
                working_dir: working_dir.clone(),
            })
        }
    } else {
        ExecutorActionType::CodingAgentInitialRequest(
            executors::actions::coding_agent_initial::CodingAgentInitialRequest {
                prompt,
                executor_config: payload.executor_config.clone(),
                working_dir,
            },
        )
    };

    let action = ExecutorAction::new(action_type, cleanup_action.map(Box::new));

    let execution_process = deployment
        .container()
        .start_execution(
            &workspace,
            &session,
            &action,
            &ExecutionProcessRunReason::CodingAgent,
        )
        .await?;

    // Push immediate live updates for the session/workspace streams.
    // The DB hook path can lag or miss the very first process add on some
    // follow-up sends, which leaves the open workspace looking idle until a
    // later refresh. Emit the source-of-truth process/workspace updates here
    // right after spawn so the existing websocket subscribers update at once.
    deployment
        .events()
        .msg_store()
        .push_patch(execution_process_patch::add(&execution_process));
    if let Some(workspace_with_status) =
        Workspace::find_by_id_with_status(pool, workspace.id).await?
    {
        deployment
            .events()
            .msg_store()
            .push_patch(workspace_patch::replace(&workspace_with_status));
    }

    // Clear the draft follow-up scratch on successful spawn
    // This ensures the scratch is wiped even if the user navigates away quickly
    if let Err(e) = Scratch::delete(pool, session.id, &ScratchType::DraftFollowUp).await {
        // Log but don't fail the request - scratch deletion is best-effort
        tracing::debug!(
            "Failed to delete draft follow-up scratch for session {}: {}",
            session.id,
            e
        );
    }

    Ok(ResponseJson(ApiResponse::success(execution_process)))
}

pub async fn reset_process(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
    Json(payload): Json<ResetProcessRequest>,
) -> Result<ResponseJson<ApiResponse<()>>, ApiError> {
    let force_when_dirty = payload.force_when_dirty.unwrap_or(false);
    let perform_git_reset = payload.perform_git_reset.unwrap_or(true);

    deployment
        .container()
        .reset_session_to_process(
            session.id,
            payload.process_id,
            perform_git_reset,
            force_when_dirty,
        )
        .await?;

    Ok(ResponseJson(ApiResponse::success(())))
}

pub async fn run_setup_script(
    Extension(session): Extension<Session>,
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<ExecutionProcess, RunScriptError>>, ApiError> {
    let pool = &deployment.db().pool;

    let workspace = Workspace::find_by_id(pool, session.workspace_id)
        .await?
        .ok_or(ApiError::Workspace(WorkspaceError::ValidationError(
            "Workspace not found".to_string(),
        )))?;

    if ExecutionProcess::has_running_non_dev_server_processes_for_workspace(pool, workspace.id)
        .await?
    {
        return Ok(ResponseJson(ApiResponse::error_with_data(
            RunScriptError::ProcessAlreadyRunning,
        )));
    }

    deployment
        .container()
        .ensure_container_exists(&workspace)
        .await?;

    let repos = WorkspaceRepo::find_repos_for_workspace(pool, workspace.id).await?;
    let executor_action = match deployment.container().setup_actions_for_repos(&repos) {
        Some(action) => action,
        None => {
            return Ok(ResponseJson(ApiResponse::error_with_data(
                RunScriptError::NoScriptConfigured,
            )));
        }
    };

    let execution_process = deployment
        .container()
        .start_execution(
            &workspace,
            &session,
            &executor_action,
            &ExecutionProcessRunReason::SetupScript,
        )
        .await?;

    deployment
        .track_if_analytics_allowed(
            "setup_script_executed",
            serde_json::json!({
                "workspace_id": workspace.id.to_string(),
            }),
        )
        .await;

    Ok(ResponseJson(ApiResponse::success(execution_process)))
}

pub fn router(deployment: &DeploymentImpl) -> Router<DeploymentImpl> {
    let session_id_router = Router::new()
        .route("/", get(get_session).put(update_session))
        .route(
            "/follow-up",
            post(follow_up).layer(DefaultBodyLimit::max(PROMPT_JSON_BODY_LIMIT_BYTES)),
        )
        .route("/reset", post(reset_process))
        .route("/setup", post(run_setup_script))
        .route("/review", post(review::start_review))
        .layer(from_fn_with_state(
            deployment.clone(),
            load_session_middleware,
        ));

    let sessions_router = Router::new()
        .route("/", get(get_sessions).post(create_session))
        .nest("/{session_id}", session_id_router)
        .nest("/{session_id}/queue", queue::router(deployment));

    Router::new().nest("/sessions", sessions_router)
}

#[cfg(test)]
mod tests {
    use std::{fs, time::Duration};

    use db::models::workspace::Workspace;
    use tempfile::tempdir;
    use uuid::Uuid;

    use super::{
        RecentCodingTurn, STATE_FIELD_CHAR_LIMIT, build_codex_usage_safe_prompt,
        build_codex_usage_safe_state, find_session_jsonl_size_in_root, truncate_state_field,
    };

    #[test]
    fn finds_newest_codex_session_jsonl_size() {
        let dir = tempdir().expect("tempdir");
        let day = dir.path().join("2026/05/19");
        fs::create_dir_all(&day).expect("create sessions day");

        let session_id = "019e4115-2e07-7343-884e-449117c2d718";
        let older = day.join(format!("rollout-old-{session_id}.jsonl"));
        let newer = day.join(format!("rollout-new-{session_id}.jsonl"));
        fs::write(&older, "small").expect("write older");
        std::thread::sleep(Duration::from_millis(5));
        fs::write(&newer, "much larger").expect("write newer");

        assert_eq!(
            find_session_jsonl_size_in_root(dir.path(), session_id),
            Some("much larger".len() as u64)
        );
    }

    #[test]
    fn usage_safe_prompt_points_to_compact_state_not_history() {
        let prompt = build_codex_usage_safe_prompt(
            "continue mobile parity",
            std::path::Path::new("/tmp/workspace/.vibe/current-state.md"),
            9_000_000,
        );

        assert!(prompt.contains("fresh Codex thread"));
        assert!(prompt.contains("/tmp/workspace/.vibe/current-state.md"));
        assert!(prompt.contains("Do not re-read old conversation logs"));
        assert!(prompt.contains("continue mobile parity"));
    }

    #[test]
    fn usage_safe_state_is_compact_and_includes_recent_turns() {
        let workspace = Workspace {
            id: Uuid::new_v4(),
            task_id: None,
            container_ref: Some("/tmp/workspace".to_string()),
            branch: "vk/test".to_string(),
            setup_completed_at: None,
            created_at: chrono::Utc::now(),
            updated_at: chrono::Utc::now(),
            archived: false,
            pinned: false,
            name: Some("Mobile parity".to_string()),
            worktree_deleted: false,
        };
        let long_summary = "x".repeat(STATE_FIELD_CHAR_LIMIT + 50);
        let state = build_codex_usage_safe_state(
            &workspace,
            "next step",
            9_000_000,
            &[RecentCodingTurn {
                created_at: "2026-05-19T20:00:00Z".to_string(),
                prompt: Some("old prompt".to_string()),
                summary: Some(long_summary),
            }],
        );

        assert!(state.contains("Mobile parity"));
        assert!(state.contains("next step"));
        assert!(state.contains("old prompt"));
        assert!(state.contains("...[truncated]"));
        assert!(state.contains("Do not repeatedly scan evidence"));
    }

    #[test]
    fn state_field_truncation_preserves_short_values() {
        assert_eq!(truncate_state_field("  short value  "), "short value");
    }
}
