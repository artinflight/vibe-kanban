//! Shared database admission for direct and durable queued launches. The first
//! statement takes SQLite's writer lock, so two callers cannot both observe idle.
use sqlx::SqliteConnection;

use super::*;

impl ExecutionProcess {
    pub(crate) async fn insert_admitted(
        conn: &mut SqliteConnection,
        data: &CreateExecutionProcess,
        process_id: Uuid,
        repo_states: &[CreateExecutionProcessRepoState],
        queued: bool,
    ) -> Result<Self, ExecutionProcessError> {
        let workspace: Uuid = sqlx::query_scalar(
            "UPDATE sessions SET updated_at=updated_at WHERE id=? RETURNING workspace_id",
        )
        .bind(data.session_id)
        .fetch_one(&mut *conn)
        .await?;
        let available: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspaces WHERE id=? AND worktree_deleted=0 AND (?=0 OR archived=0))")
            .bind(workspace).bind(queued).fetch_one(&mut *conn).await?;
        if !available {
            return Err(ExecutionProcessError::AdmissionConflict);
        }
        let running: Vec<ExecutionProcess> = sqlx::query_as("SELECT * FROM execution_processes WHERE session_id IN (SELECT id FROM sessions WHERE workspace_id=?) AND status='running' AND dropped=0 AND run_reason!='devserver'")
            .bind(workspace).fetch_all(&mut *conn).await?;
        // Queued work waits for all workspace finalisation. Direct launches keep
        // VK's intentional parallel setup/dev-server behavior. A standalone setup
        // may overlap coding; a sequential setup owns its forthcoming coding turn.
        let conflict = if queued {
            !running.is_empty()
        } else {
            match data.run_reason {
                ExecutionProcessRunReason::DevServer => false,
                ExecutionProcessRunReason::SetupScript
                    if data.executor_action.next_action().is_none() =>
                {
                    false
                }
                _ => running.iter().any(|p| {
                    p.run_reason != ExecutionProcessRunReason::SetupScript
                        || p.executor_action()
                            .map_or(true, |a| a.next_action().is_some())
                }),
            }
        };
        if conflict {
            return Err(ExecutionProcessError::AdmissionConflict);
        }
        let process: Self = sqlx::query_as("INSERT INTO execution_processes (id,session_id,run_reason,executor_action,status) VALUES (?,?,?,?,'running') RETURNING *")
            .bind(process_id).bind(data.session_id).bind(&data.run_reason).bind(sqlx::types::Json(&data.executor_action)).fetch_one(&mut *conn).await?;
        for entry in repo_states {
            sqlx::query("INSERT INTO execution_process_repo_states (id,execution_process_id,repo_id,before_head_commit,after_head_commit,merge_commit) VALUES (?,?,?,?,?,?)")
                .bind(Uuid::new_v4()).bind(process_id).bind(entry.repo_id).bind(&entry.before_head_commit).bind(&entry.after_head_commit).bind(&entry.merge_commit).execute(&mut *conn).await?;
        }
        let prompt = match data.executor_action.typ() {
            ExecutorActionType::CodingAgentInitialRequest(r) => Some(&r.prompt),
            ExecutorActionType::CodingAgentFollowUpRequest(r) => Some(&r.prompt),
            ExecutorActionType::ReviewRequest(r) => Some(&r.prompt),
            ExecutorActionType::ScriptRequest(_) => None,
        };
        if let Some(prompt) = prompt {
            sqlx::query(
                "INSERT INTO coding_agent_turns (id,execution_process_id,prompt) VALUES (?,?,?)",
            )
            .bind(Uuid::new_v4())
            .bind(process_id)
            .bind(prompt)
            .execute(&mut *conn)
            .await?;
        }
        if data.run_reason != ExecutionProcessRunReason::ArchiveScript {
            sqlx::query(
                "UPDATE workspaces SET archived=0,updated_at=datetime('now','subsec') WHERE id=?",
            )
            .bind(workspace)
            .execute(conn)
            .await?;
        }
        Ok(process)
    }
}

#[cfg(test)]
mod tests;
