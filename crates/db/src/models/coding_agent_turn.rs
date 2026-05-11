use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, SqlitePool};
use ts_rs::TS;
use uuid::Uuid;

use super::execution_process::ExecutionProcessStatus;

#[derive(Debug, Clone, FromRow, Serialize, Deserialize, TS)]
pub struct CodingAgentTurn {
    pub id: Uuid,
    pub execution_process_id: Uuid,
    pub agent_session_id: Option<String>,
    pub agent_message_id: Option<String>,
    pub prompt: Option<String>,  // The prompt sent to the executor
    pub summary: Option<String>, // Final assistant message/summary
    pub seen: bool,              // Whether user has viewed this turn
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize, TS)]
pub struct CreateCodingAgentTurn {
    pub execution_process_id: Uuid,
    pub prompt: Option<String>,
}

/// Session info from a coding agent turn, used for follow-up requests
#[derive(Debug)]
pub struct CodingAgentResumeInfo {
    pub session_id: String,
    pub message_id: Option<String>,
}

/// Prompt context from turns that happened after the latest safe resume anchor
/// but did not produce durable resumable state.
#[derive(Debug, FromRow)]
pub struct CodingAgentInterruptedContext {
    pub status: ExecutionProcessStatus,
    pub exit_code: Option<i64>,
    pub prompt: Option<String>,
    pub summary: Option<String>,
    pub created_at: DateTime<Utc>,
}

impl CodingAgentTurn {
    /// Find the workspace affected by a coding-agent turn row update.
    pub async fn find_workspace_id_by_rowid(
        pool: &SqlitePool,
        rowid: i64,
    ) -> Result<Option<Uuid>, sqlx::Error> {
        sqlx::query_scalar(
            r#"SELECT s.workspace_id
               FROM coding_agent_turns cat
               JOIN execution_processes ep ON cat.execution_process_id = ep.id
               JOIN sessions s ON ep.session_id = s.id
               WHERE cat.rowid = ?"#,
        )
        .bind(rowid)
        .fetch_optional(pool)
        .await
    }

    /// Find resumable session info from the latest successful coding agent turn for a session.
    /// Failed launches can still emit an agent_session_id before Codex has persisted a usable
    /// rollout file, so only completed turns with a final summary are safe continuity anchors.
    pub async fn find_latest_session_info(
        pool: &SqlitePool,
        session_id: Uuid,
    ) -> Result<Option<CodingAgentResumeInfo>, sqlx::Error> {
        sqlx::query_as!(
            CodingAgentResumeInfo,
            r#"SELECT
                cat.agent_session_id as "session_id!",
                cat.agent_message_id as "message_id"
               FROM execution_processes ep
               JOIN coding_agent_turns cat ON ep.id = cat.execution_process_id
               WHERE ep.session_id = $1
                 AND ep.run_reason = 'codingagent'
                 AND ep.dropped = FALSE
                 AND ep.status = 'completed'
                 AND ep.exit_code = 0
                 AND cat.agent_session_id IS NOT NULL
                 AND cat.summary IS NOT NULL
                 AND trim(cat.summary) != ''
               ORDER BY ep.created_at DESC
               LIMIT 1"#,
            session_id
        )
        .fetch_optional(pool)
        .await
    }

    /// Find prompts from later turns that cannot be used as resume anchors.
    ///
    /// A service restart or app-server rollout failure can leave the latest user
    /// instruction in a killed/failed turn with no final summary. The executor
    /// cannot safely fork those sessions, but dropping their prompts makes a
    /// later "resume" continue from stale context. These rows are injected into
    /// the next prompt as explicit recovery context.
    pub async fn find_interrupted_context_since_latest_success(
        pool: &SqlitePool,
        session_id: Uuid,
    ) -> Result<Vec<CodingAgentInterruptedContext>, sqlx::Error> {
        sqlx::query_as::<_, CodingAgentInterruptedContext>(
            r#"WITH latest_success AS (
                SELECT ep.created_at
                FROM execution_processes ep
                JOIN coding_agent_turns cat ON ep.id = cat.execution_process_id
                WHERE ep.session_id = $1
                  AND ep.run_reason = 'codingagent'
                  AND ep.dropped = FALSE
                  AND ep.status = 'completed'
                  AND ep.exit_code = 0
                  AND cat.agent_session_id IS NOT NULL
                  AND cat.summary IS NOT NULL
                  AND trim(cat.summary) != ''
                ORDER BY ep.created_at DESC
                LIMIT 1
               )
               SELECT
                ep.status as status,
                ep.exit_code,
                cat.prompt,
                cat.summary,
                ep.created_at as created_at
               FROM execution_processes ep
               JOIN coding_agent_turns cat ON ep.id = cat.execution_process_id
               WHERE ep.session_id = $1
                 AND ep.run_reason = 'codingagent'
                 AND ep.dropped = FALSE
                 AND ((SELECT created_at FROM latest_success) IS NULL
                      OR ep.created_at > (SELECT created_at FROM latest_success))
                 AND (
                    ep.status != 'completed'
                    OR ep.exit_code IS NULL
                    OR ep.exit_code != 0
                    OR cat.summary IS NULL
                    OR trim(cat.summary) = ''
                 )
                 AND cat.prompt IS NOT NULL
                 AND trim(cat.prompt) != ''
               ORDER BY ep.created_at ASC
               LIMIT 10"#,
        )
        .bind(session_id)
        .fetch_all(pool)
        .await
    }

    pub fn prompt_with_interrupted_context(
        prompt: String,
        interrupted_context: &[CodingAgentInterruptedContext],
    ) -> String {
        if interrupted_context.is_empty() {
            return prompt;
        }

        let mut recovered = String::from(
            "Context recovery: one or more previous agent turns in this session were interrupted or did not produce a durable final summary. Do not assume the resumed thread contains these instructions. Treat the interrupted turn prompts below as required continuity before answering the current prompt.\n\nInterrupted turn(s), oldest to newest:\n",
        );

        for (index, context) in interrupted_context.iter().enumerate() {
            recovered.push_str(&format!(
                "\n{}. [{} status={:?} exit_code={}] Prompt:\n{}\n",
                index + 1,
                context.created_at,
                context.status,
                context
                    .exit_code
                    .map(|code| code.to_string())
                    .unwrap_or_else(|| "none".to_string()),
                truncate_recovery_text(context.prompt.as_deref().unwrap_or(""))
            ));

            if let Some(summary) = context.summary.as_deref().filter(|s| !s.trim().is_empty()) {
                recovered.push_str("Partial/final text captured from that turn:\n");
                recovered.push_str(&truncate_recovery_text(summary));
                recovered.push('\n');
            }
        }

        recovered.push_str("\nCurrent user prompt:\n");
        recovered.push_str(&prompt);
        recovered
    }

    /// Find coding agent turn by execution process ID
    pub async fn find_by_execution_process_id(
        pool: &SqlitePool,
        execution_process_id: Uuid,
    ) -> Result<Option<Self>, sqlx::Error> {
        sqlx::query_as!(
            CodingAgentTurn,
            r#"SELECT
                id as "id!: Uuid",
                execution_process_id as "execution_process_id!: Uuid",
                agent_session_id,
                agent_message_id,
                prompt,
                summary,
                seen as "seen!: bool",
                created_at as "created_at!: DateTime<Utc>",
                updated_at as "updated_at!: DateTime<Utc>"
               FROM coding_agent_turns
               WHERE execution_process_id = $1"#,
            execution_process_id
        )
        .fetch_optional(pool)
        .await
    }

    /// Create a new coding agent turn
    pub async fn create(
        pool: &SqlitePool,
        data: &CreateCodingAgentTurn,
        id: Uuid,
    ) -> Result<Self, sqlx::Error> {
        let now = Utc::now();

        tracing::debug!(
            "Creating coding agent turn: id={}, execution_process_id={}, agent_session_id=None (will be set later)",
            id,
            data.execution_process_id
        );

        sqlx::query_as!(
            CodingAgentTurn,
            r#"INSERT INTO coding_agent_turns (
                id, execution_process_id, agent_session_id, agent_message_id, prompt, summary, seen,
                created_at, updated_at
               )
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING
                id as "id!: Uuid",
                execution_process_id as "execution_process_id!: Uuid",
                agent_session_id,
                agent_message_id,
                prompt,
                summary,
                seen as "seen!: bool",
                created_at as "created_at!: DateTime<Utc>",
                updated_at as "updated_at!: DateTime<Utc>""#,
            id,
            data.execution_process_id,
            None::<String>, // agent_session_id initially None until parsed from output
            None::<String>, // agent_message_id initially None until parsed from output
            data.prompt,
            None::<String>, // summary initially None
            false,          // seen - defaults to unseen
            now,            // created_at
            now             // updated_at
        )
        .fetch_one(pool)
        .await
    }

    /// Update coding agent turn with agent session ID
    pub async fn update_agent_session_id(
        pool: &SqlitePool,
        execution_process_id: Uuid,
        agent_session_id: &str,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now();
        sqlx::query!(
            r#"UPDATE coding_agent_turns
               SET agent_session_id = $1, updated_at = $2
               WHERE execution_process_id = $3"#,
            agent_session_id,
            now,
            execution_process_id
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Update coding agent turn with agent message ID (for --resume-session-at)
    pub async fn update_agent_message_id(
        pool: &SqlitePool,
        execution_process_id: Uuid,
        agent_message_id: &str,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now();
        sqlx::query!(
            r#"UPDATE coding_agent_turns
               SET agent_message_id = $1, updated_at = $2
               WHERE execution_process_id = $3"#,
            agent_message_id,
            now,
            execution_process_id
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Update coding agent turn summary
    pub async fn update_summary(
        pool: &SqlitePool,
        execution_process_id: Uuid,
        summary: &str,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now();
        sqlx::query!(
            r#"UPDATE coding_agent_turns
               SET summary = $1, updated_at = $2
               WHERE execution_process_id = $3"#,
            summary,
            now,
            execution_process_id
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Mark a coding agent turn as unseen by execution process ID.
    pub async fn mark_unseen_by_execution_process_id(
        pool: &SqlitePool,
        execution_process_id: Uuid,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now();
        sqlx::query(
            r#"UPDATE coding_agent_turns
               SET seen = 0, updated_at = ?
               WHERE execution_process_id = ?
                 AND seen = 1"#,
        )
        .bind(now)
        .bind(execution_process_id)
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Mark a completed coding agent turn as unseen by execution process ID.
    ///
    /// This is used when the user viewed a workspace while the agent was still
    /// running. The turn should become reviewable again once a final summary
    /// exists, but only for successful completions.
    pub async fn mark_completed_unseen_by_execution_process_id(
        pool: &SqlitePool,
        execution_process_id: Uuid,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now();
        sqlx::query(
            r#"UPDATE coding_agent_turns
               SET seen = 0, updated_at = ?
               WHERE execution_process_id = ?
                 AND seen = 1
                 AND EXISTS (
                   SELECT 1
                   FROM execution_processes ep
                   WHERE ep.id = coding_agent_turns.execution_process_id
                     AND ep.run_reason = 'codingagent'
                     AND ep.status = 'completed'
                 )"#,
        )
        .bind(now)
        .bind(execution_process_id)
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Mark all coding agent turns for a workspace as seen
    pub async fn mark_seen_by_workspace_id(
        pool: &SqlitePool,
        workspace_id: Uuid,
    ) -> Result<(), sqlx::Error> {
        let now = Utc::now();
        sqlx::query!(
            r#"UPDATE coding_agent_turns
               SET seen = 1, updated_at = $1
               WHERE execution_process_id IN (
                   SELECT ep.id FROM execution_processes ep
                   JOIN sessions s ON ep.session_id = s.id
                   WHERE s.workspace_id = $2
               ) AND seen = 0"#,
            now,
            workspace_id
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    /// Mark the latest coding agent turn for a workspace as unseen.
    pub async fn mark_latest_unseen_by_workspace_id(
        pool: &SqlitePool,
        workspace_id: Uuid,
    ) -> Result<bool, sqlx::Error> {
        let now = Utc::now();
        let result = sqlx::query(
            r#"UPDATE coding_agent_turns
               SET seen = 0, updated_at = ?
               WHERE execution_process_id = (
                   SELECT ep.id
                   FROM execution_processes ep
                   JOIN sessions s ON ep.session_id = s.id
                   WHERE s.workspace_id = ?
                     AND ep.run_reason = 'codingagent'
                     AND ep.dropped = 0
                   ORDER BY ep.created_at DESC
                   LIMIT 1
               )"#,
        )
        .bind(now)
        .bind(workspace_id)
        .execute(pool)
        .await?;

        Ok(result.rows_affected() > 0)
    }

    /// Check if a workspace has any unseen coding agent turns
    /// Find all workspaces that have unseen coding agent turns, filtered by archived status
    pub async fn find_workspaces_with_unseen(
        pool: &SqlitePool,
        archived: bool,
    ) -> Result<std::collections::HashSet<Uuid>, sqlx::Error> {
        let result: Vec<Uuid> = sqlx::query_scalar!(
            r#"SELECT DISTINCT s.workspace_id as "workspace_id!: Uuid"
               FROM coding_agent_turns cat
               JOIN execution_processes ep ON cat.execution_process_id = ep.id
               JOIN sessions s ON ep.session_id = s.id
               JOIN workspaces w ON s.workspace_id = w.id
               WHERE cat.seen = 0 AND w.archived = $1"#,
            archived
        )
        .fetch_all(pool)
        .await?;

        Ok(result.into_iter().collect())
    }
}

#[cfg(test)]
mod tests {
    use sqlx::{Row, sqlite::SqlitePoolOptions};
    use uuid::Uuid;

    use super::CodingAgentTurn;

    #[tokio::test]
    async fn latest_workspace_turn_can_be_marked_unseen() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .expect("create in-memory sqlite pool");

        sqlx::query(
            r#"
            CREATE TABLE sessions (
                id BLOB PRIMARY KEY,
                workspace_id BLOB NOT NULL
            );

            CREATE TABLE execution_processes (
                id BLOB PRIMARY KEY,
                session_id BLOB NOT NULL,
                run_reason TEXT NOT NULL,
                dropped INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE coding_agent_turns (
                execution_process_id BLOB NOT NULL,
                seen INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            "#,
        )
        .execute(&pool)
        .await
        .expect("create test schema");

        let workspace_id = Uuid::new_v4();
        let other_workspace_id = Uuid::new_v4();
        let session_id = Uuid::new_v4();
        let other_session_id = Uuid::new_v4();
        let older_id = Uuid::new_v4();
        let latest_id = Uuid::new_v4();
        let setup_id = Uuid::new_v4();
        let dropped_id = Uuid::new_v4();
        let other_id = Uuid::new_v4();

        for (id, workspace_id) in [
            (session_id, workspace_id),
            (other_session_id, other_workspace_id),
        ] {
            sqlx::query("INSERT INTO sessions (id, workspace_id) VALUES (?, ?)")
                .bind(id)
                .bind(workspace_id)
                .execute(&pool)
                .await
                .expect("insert session");
        }

        for (id, session_id, run_reason, dropped, created_at) in [
            (
                older_id,
                session_id,
                "codingagent",
                0,
                "2026-05-11T00:00:00Z",
            ),
            (
                latest_id,
                session_id,
                "codingagent",
                0,
                "2026-05-11T01:00:00Z",
            ),
            (
                setup_id,
                session_id,
                "setupscript",
                0,
                "2026-05-11T02:00:00Z",
            ),
            (
                dropped_id,
                session_id,
                "codingagent",
                1,
                "2026-05-11T03:00:00Z",
            ),
            (
                other_id,
                other_session_id,
                "codingagent",
                0,
                "2026-05-11T04:00:00Z",
            ),
        ] {
            sqlx::query(
                r#"INSERT INTO execution_processes
                   (id, session_id, run_reason, dropped, created_at)
                   VALUES (?, ?, ?, ?, ?)"#,
            )
            .bind(id)
            .bind(session_id)
            .bind(run_reason)
            .bind(dropped)
            .bind(created_at)
            .execute(&pool)
            .await
            .expect("insert execution process");

            sqlx::query(
                r#"INSERT INTO coding_agent_turns (execution_process_id, seen, updated_at)
                   VALUES (?, 1, 'before')"#,
            )
            .bind(id)
            .execute(&pool)
            .await
            .expect("insert coding agent turn");
        }

        let changed = CodingAgentTurn::mark_latest_unseen_by_workspace_id(&pool, workspace_id)
            .await
            .expect("mark latest workspace turn unseen");

        assert!(changed);
        assert_eq!(seen_for(&pool, older_id).await, 1);
        assert_eq!(seen_for(&pool, latest_id).await, 0);
        assert_eq!(seen_for(&pool, setup_id).await, 1);
        assert_eq!(seen_for(&pool, dropped_id).await, 1);
        assert_eq!(seen_for(&pool, other_id).await, 1);
    }

    #[tokio::test]
    async fn completed_coding_agent_turns_are_marked_unseen_by_uuid_blob() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .expect("create in-memory sqlite pool");

        sqlx::query(
            r#"
            CREATE TABLE execution_processes (
                id BLOB PRIMARY KEY,
                run_reason TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE coding_agent_turns (
                execution_process_id BLOB NOT NULL,
                seen INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            "#,
        )
        .execute(&pool)
        .await
        .expect("create test schema");

        let completed_coding_id = Uuid::new_v4();
        let running_coding_id = Uuid::new_v4();
        let completed_setup_id = Uuid::new_v4();

        for (id, run_reason, status) in [
            (completed_coding_id, "codingagent", "completed"),
            (running_coding_id, "codingagent", "running"),
            (completed_setup_id, "setupscript", "completed"),
        ] {
            sqlx::query(
                r#"INSERT INTO execution_processes (id, run_reason, status)
                   VALUES (?, ?, ?)"#,
            )
            .bind(id)
            .bind(run_reason)
            .bind(status)
            .execute(&pool)
            .await
            .expect("insert execution process");

            sqlx::query(
                r#"INSERT INTO coding_agent_turns (execution_process_id, seen, updated_at)
                   VALUES (?, 1, 'before')"#,
            )
            .bind(id)
            .execute(&pool)
            .await
            .expect("insert coding agent turn");
        }

        CodingAgentTurn::mark_completed_unseen_by_execution_process_id(&pool, completed_coding_id)
            .await
            .expect("mark completed coding turn unseen");
        CodingAgentTurn::mark_completed_unseen_by_execution_process_id(&pool, running_coding_id)
            .await
            .expect("ignore running coding turn");
        CodingAgentTurn::mark_completed_unseen_by_execution_process_id(&pool, completed_setup_id)
            .await
            .expect("ignore completed non-coding turn");

        let completed_seen = seen_for(&pool, completed_coding_id).await;
        let running_seen = seen_for(&pool, running_coding_id).await;
        let setup_seen = seen_for(&pool, completed_setup_id).await;

        assert_eq!(completed_seen, 0);
        assert_eq!(running_seen, 1);
        assert_eq!(setup_seen, 1);

        CodingAgentTurn::mark_unseen_by_execution_process_id(&pool, running_coding_id)
            .await
            .expect("mark running coding turn unseen by uuid");

        assert_eq!(seen_for(&pool, running_coding_id).await, 0);
    }

    async fn seen_for(pool: &sqlx::SqlitePool, execution_process_id: Uuid) -> i64 {
        sqlx::query(
            r#"SELECT seen
               FROM coding_agent_turns
               WHERE execution_process_id = ?"#,
        )
        .bind(execution_process_id)
        .fetch_one(pool)
        .await
        .expect("fetch seen flag")
        .get::<i64, _>("seen")
    }
}
