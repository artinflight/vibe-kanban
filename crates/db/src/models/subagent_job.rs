use std::{collections::HashMap, str::FromStr, time::Duration};

use chrono::{DateTime, Duration as ChronoDuration, TimeZone, Utc};
use executors::executors::codex::codex_home;
use serde::{Deserialize, Serialize};
use sqlx::{
    ConnectOptions, FromRow, QueryBuilder, Sqlite, SqlitePool, Type,
    sqlite::{SqliteConnectOptions, SqlitePoolOptions},
};
use ts_rs::TS;
use uuid::Uuid;

#[derive(Debug, Clone, Type, Serialize, Deserialize, PartialEq, Eq, TS)]
#[sqlx(type_name = "subagent_job_status", rename_all = "snake_case")]
#[serde(rename_all = "snake_case")]
#[ts(use_ts_enum)]
pub enum SubagentJobStatus {
    Unresolved,
    Running,
    Completed,
    NotFound,
    Failed,
}

#[derive(Debug, Clone, FromRow, Serialize, Deserialize, TS)]
pub struct SubagentJob {
    pub id: Uuid,
    pub session_id: Uuid,
    pub execution_process_id: Uuid,
    pub agent_id: String,
    pub nickname: Option<String>,
    pub status: SubagentJobStatus,
    pub completed_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Default)]
pub struct SubagentJobCounts {
    pub running: usize,
    pub unresolved: usize,
}

#[derive(Debug, FromRow)]
struct SessionAgentThreadRow {
    session_id: Uuid,
    execution_process_id: Uuid,
    agent_session_id: String,
    parent_completed_at: Option<DateTime<Utc>>,
}

#[derive(Debug, FromRow)]
struct CodexThreadSpawnRow {
    root_thread_id: String,
    child_thread_id: String,
    edge_status: String,
    nickname: Option<String>,
    created_at_ms: Option<i64>,
    updated_at_ms: Option<i64>,
}

impl SubagentJobStatus {
    fn is_terminal(&self) -> bool {
        matches!(
            self,
            SubagentJobStatus::Completed | SubagentJobStatus::Failed
        )
    }
}

impl SubagentJob {
    pub async fn find_by_session_id(
        pool: &SqlitePool,
        session_id: Uuid,
    ) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as::<_, SubagentJob>(
            r#"SELECT
                id,
                session_id,
                execution_process_id,
                agent_id,
                nickname,
                status,
                completed_at,
                created_at,
                updated_at
               FROM subagent_jobs
               WHERE session_id = ?
               ORDER BY created_at ASC, updated_at ASC"#,
        )
        .bind(session_id)
        .fetch_all(pool)
        .await
    }

    pub async fn find_by_session_id_with_codex_threads(
        pool: &SqlitePool,
        session_id: Uuid,
    ) -> Result<Vec<Self>, sqlx::Error> {
        let mut jobs = Self::find_by_session_id(pool, session_id).await?;
        let mut codex_jobs = find_codex_thread_jobs(pool, &[session_id]).await?;
        jobs.append(&mut codex_jobs);
        jobs.sort_by_key(|job| (job.created_at, job.updated_at));
        Ok(deduplicate_jobs(jobs))
    }

    pub async fn active_counts_by_session_ids_with_codex_threads(
        pool: &SqlitePool,
        session_ids: &[Uuid],
    ) -> Result<HashMap<Uuid, SubagentJobCounts>, sqlx::Error> {
        if session_ids.is_empty() {
            return Ok(HashMap::new());
        }

        let mut jobs = find_jobs_for_sessions(pool, session_ids).await?;
        jobs.append(&mut find_codex_thread_jobs(pool, session_ids).await?);

        let mut counts = HashMap::<Uuid, SubagentJobCounts>::new();
        for job in deduplicate_jobs(jobs) {
            increment_active_count(&mut counts, job.session_id, &job.status);
        }

        Ok(counts)
    }

    pub async fn upsert_spawned(
        pool: &SqlitePool,
        session_id: Uuid,
        execution_process_id: Uuid,
        agent_id: &str,
        nickname: Option<&str>,
    ) -> Result<(), sqlx::Error> {
        let id = Uuid::new_v4();
        let now = Utc::now();

        sqlx::query(
            r#"INSERT INTO subagent_jobs (
                id, session_id, execution_process_id, agent_id, nickname, status,
                completed_at, created_at, updated_at
               )
               VALUES (?, ?, ?, ?, ?, 'unresolved', NULL, ?, ?)
               ON CONFLICT(execution_process_id, agent_id) DO UPDATE SET
                nickname = COALESCE(excluded.nickname, subagent_jobs.nickname),
                updated_at = excluded.updated_at"#,
        )
        .bind(id)
        .bind(session_id)
        .bind(execution_process_id)
        .bind(agent_id)
        .bind(nickname)
        .bind(now)
        .bind(now)
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn update_status(
        pool: &SqlitePool,
        session_id: Uuid,
        execution_process_id: Uuid,
        agent_id: &str,
        status: SubagentJobStatus,
    ) -> Result<(), sqlx::Error> {
        let id = Uuid::new_v4();
        let now = Utc::now();
        let completed_at = status.is_terminal().then_some(now);

        sqlx::query(
            r#"INSERT INTO subagent_jobs (
                id, session_id, execution_process_id, agent_id, nickname, status,
                completed_at, created_at, updated_at
               )
               VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)
               ON CONFLICT(execution_process_id, agent_id) DO UPDATE SET
                status = CASE
                    WHEN subagent_jobs.status IN ('completed','failed')
                    THEN subagent_jobs.status
                    ELSE excluded.status
                END,
                completed_at = CASE
                    WHEN subagent_jobs.status IN ('completed','failed')
                    THEN subagent_jobs.completed_at
                    ELSE excluded.completed_at
                END,
                updated_at = excluded.updated_at"#,
        )
        .bind(id)
        .bind(session_id)
        .bind(execution_process_id)
        .bind(agent_id)
        .bind(status)
        .bind(completed_at)
        .bind(now)
        .bind(now)
        .execute(pool)
        .await?;

        Ok(())
    }
}

async fn find_jobs_for_sessions(
    pool: &SqlitePool,
    session_ids: &[Uuid],
) -> Result<Vec<SubagentJob>, sqlx::Error> {
    let mut builder = QueryBuilder::<Sqlite>::new(
        r#"SELECT
            id,
            session_id,
            execution_process_id,
            agent_id,
            nickname,
            status,
            completed_at,
            created_at,
            updated_at
           FROM subagent_jobs
           WHERE session_id IN ("#,
    );
    let mut separated = builder.separated(", ");
    for session_id in session_ids {
        separated.push_bind(*session_id);
    }
    separated.push_unseparated(")");
    builder
        .build_query_as::<SubagentJob>()
        .fetch_all(pool)
        .await
}

async fn find_agent_threads_for_sessions(
    pool: &SqlitePool,
    session_ids: &[Uuid],
) -> Result<Vec<SessionAgentThreadRow>, sqlx::Error> {
    let mut builder = QueryBuilder::<Sqlite>::new(
        r#"SELECT
            ep.session_id,
            cat.execution_process_id,
            cat.agent_session_id,
            ep.completed_at AS parent_completed_at
           FROM coding_agent_turns cat
           JOIN execution_processes ep ON ep.id = cat.execution_process_id
           WHERE ep.dropped = FALSE
             AND cat.agent_session_id IS NOT NULL
             AND ep.session_id IN ("#,
    );
    let mut separated = builder.separated(", ");
    for session_id in session_ids {
        separated.push_bind(*session_id);
    }
    separated.push_unseparated(
        r#")
           ORDER BY ep.created_at DESC"#,
    );
    builder
        .build_query_as::<SessionAgentThreadRow>()
        .fetch_all(pool)
        .await
}

async fn find_codex_thread_jobs(
    pool: &SqlitePool,
    session_ids: &[Uuid],
) -> Result<Vec<SubagentJob>, sqlx::Error> {
    let thread_rows = find_agent_threads_for_sessions(pool, session_ids).await?;
    if thread_rows.is_empty() {
        return Ok(Vec::new());
    }

    let codex_pool = match codex_state_pool().await {
        Some(pool) => pool,
        None => return Ok(Vec::new()),
    };

    let mut thread_context = HashMap::<String, (Uuid, Uuid, Option<DateTime<Utc>>)>::new();
    for row in thread_rows {
        thread_context.entry(row.agent_session_id).or_insert((
            row.session_id,
            row.execution_process_id,
            row.parent_completed_at,
        ));
    }

    let mut builder = QueryBuilder::<Sqlite>::new(
        r#"WITH RECURSIVE descendants(
              root_thread_id,
              parent_thread_id,
              child_thread_id,
              edge_status,
              depth
           ) AS (
              SELECT
                parent_thread_id,
                parent_thread_id,
                child_thread_id,
                status,
                1
              FROM thread_spawn_edges
              WHERE parent_thread_id IN ("#,
    );
    let mut separated = builder.separated(", ");
    for thread_id in thread_context.keys() {
        separated.push_bind(thread_id);
    }
    separated.push_unseparated(
        r#")
              UNION ALL
              SELECT
                d.root_thread_id,
                e.parent_thread_id,
                e.child_thread_id,
                e.status,
                d.depth + 1
              FROM thread_spawn_edges e
              JOIN descendants d ON e.parent_thread_id = d.child_thread_id
              WHERE d.depth < 4
           )
           SELECT
             d.root_thread_id,
             d.child_thread_id,
             d.edge_status,
             t.agent_nickname AS nickname,
             t.created_at_ms,
             t.updated_at_ms
           FROM descendants d
           LEFT JOIN threads t ON t.id = d.child_thread_id
           ORDER BY COALESCE(t.created_at_ms, 0) ASC"#,
    );

    let rows = builder
        .build_query_as::<CodexThreadSpawnRow>()
        .fetch_all(&codex_pool)
        .await?;

    let now = Utc::now();
    Ok(rows
        .into_iter()
        .filter_map(|row| {
            let (session_id, execution_process_id, parent_completed_at) =
                thread_context.get(&row.root_thread_id).copied()?;
            let created_at = ms_to_utc(row.created_at_ms).unwrap_or(now);
            let updated_at = ms_to_utc(row.updated_at_ms).unwrap_or(created_at);
            let status = codex_edge_status(
                &row.edge_status,
                ms_to_utc(row.updated_at_ms),
                parent_completed_at,
            );
            Some(SubagentJob {
                id: Uuid::parse_str(&row.child_thread_id).unwrap_or_else(|_| Uuid::new_v4()),
                session_id,
                execution_process_id,
                agent_id: row.child_thread_id,
                nickname: row.nickname,
                completed_at: status.is_terminal().then_some(updated_at),
                status,
                created_at,
                updated_at,
            })
        })
        .collect())
}

async fn codex_state_pool() -> Option<SqlitePool> {
    let state_path = codex_home()?.join("state_5.sqlite");
    if !state_path.exists() {
        return None;
    }

    let database_url = format!("sqlite://{}", state_path.to_string_lossy());
    let options = SqliteConnectOptions::from_str(&database_url)
        .ok()?
        .read_only(true)
        .create_if_missing(false)
        .busy_timeout(Duration::from_secs(2))
        .disable_statement_logging();

    match SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(options)
        .await
    {
        Ok(pool) => Some(pool),
        Err(e) => {
            tracing::warn!(
                "Failed to open Codex state DB at {} for sub-agent status: {}",
                state_path.display(),
                e
            );
            None
        }
    }
}

fn ms_to_utc(ms: Option<i64>) -> Option<DateTime<Utc>> {
    Utc.timestamp_millis_opt(ms?).single()
}

fn codex_edge_status(
    edge_status: &str,
    child_updated_at: Option<DateTime<Utc>>,
    parent_completed_at: Option<DateTime<Utc>>,
) -> SubagentJobStatus {
    match edge_status {
        "closed" => SubagentJobStatus::Completed,
        "open" => {
            if let Some(parent_completed_at) = parent_completed_at {
                let stale_cutoff = parent_completed_at + ChronoDuration::seconds(30);
                if child_updated_at.map_or(true, |updated_at| updated_at <= stale_cutoff) {
                    return SubagentJobStatus::Completed;
                }
            }
            SubagentJobStatus::Running
        }
        _ => SubagentJobStatus::Unresolved,
    }
}

fn increment_active_count(
    counts: &mut HashMap<Uuid, SubagentJobCounts>,
    session_id: Uuid,
    status: &SubagentJobStatus,
) {
    let count = counts.entry(session_id).or_default();
    match status {
        SubagentJobStatus::Running => count.running += 1,
        SubagentJobStatus::Unresolved | SubagentJobStatus::NotFound => count.unresolved += 1,
        SubagentJobStatus::Completed | SubagentJobStatus::Failed => {}
    }
}

fn deduplicate_jobs(jobs: Vec<SubagentJob>) -> Vec<SubagentJob> {
    let mut by_agent = HashMap::<String, SubagentJob>::new();
    for job in jobs {
        by_agent
            .entry(job.agent_id.clone())
            .and_modify(|existing| {
                if status_rank(&job.status) >= status_rank(&existing.status) {
                    *existing = job.clone();
                }
            })
            .or_insert(job);
    }
    let mut jobs = by_agent.into_values().collect::<Vec<_>>();
    jobs.sort_by_key(|job| (job.created_at, job.updated_at));
    jobs
}

fn status_rank(status: &SubagentJobStatus) -> u8 {
    match status {
        SubagentJobStatus::Running => 4,
        SubagentJobStatus::Unresolved => 3,
        SubagentJobStatus::NotFound => 2,
        SubagentJobStatus::Failed => 1,
        SubagentJobStatus::Completed => 0,
    }
}

#[cfg(test)]
mod tests {
    use chrono::{Duration as ChronoDuration, Utc};
    use sqlx::{Row, sqlite::SqlitePoolOptions};
    use uuid::Uuid;

    use super::{SubagentJob, SubagentJobStatus, codex_edge_status};

    #[test]
    fn completed_parent_codex_open_edge_is_not_counted_as_running_when_stale() {
        let completed_at = Utc::now();

        assert_eq!(
            codex_edge_status("open", Some(completed_at), Some(completed_at)),
            SubagentJobStatus::Completed
        );
        assert_eq!(
            codex_edge_status("open", None, Some(completed_at)),
            SubagentJobStatus::Completed
        );
        assert_eq!(
            codex_edge_status(
                "open",
                Some(completed_at + ChronoDuration::seconds(31)),
                Some(completed_at)
            ),
            SubagentJobStatus::Running
        );
        assert_eq!(
            codex_edge_status("open", Some(completed_at), None),
            SubagentJobStatus::Running
        );
    }

    #[tokio::test]
    async fn not_found_subagent_status_remains_recoverable() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .expect("create in-memory sqlite pool");

        sqlx::query(
            r#"
            CREATE TABLE subagent_jobs (
                id BLOB PRIMARY KEY,
                session_id BLOB NOT NULL,
                execution_process_id BLOB NOT NULL,
                agent_id TEXT NOT NULL,
                nickname TEXT,
                status TEXT NOT NULL,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (execution_process_id, agent_id)
            );
            "#,
        )
        .execute(&pool)
        .await
        .expect("create subagent_jobs test table");

        let session_id = Uuid::new_v4();
        let execution_id = Uuid::new_v4();
        let agent_id = "019e0d97-27ff-7c43-b252-28979c51d3e9";

        SubagentJob::update_status(
            &pool,
            session_id,
            execution_id,
            agent_id,
            SubagentJobStatus::Running,
        )
        .await
        .expect("insert running subagent");

        SubagentJob::update_status(
            &pool,
            session_id,
            execution_id,
            agent_id,
            SubagentJobStatus::NotFound,
        )
        .await
        .expect("mark registry miss");

        assert_eq!(status_for(&pool, execution_id, agent_id).await, "not_found");
        assert!(
            completed_at_for(&pool, execution_id, agent_id)
                .await
                .is_none()
        );

        SubagentJob::update_status(
            &pool,
            session_id,
            execution_id,
            agent_id,
            SubagentJobStatus::Running,
        )
        .await
        .expect("recover after registry miss");

        assert_eq!(status_for(&pool, execution_id, agent_id).await, "running");

        SubagentJob::update_status(
            &pool,
            session_id,
            execution_id,
            agent_id,
            SubagentJobStatus::Completed,
        )
        .await
        .expect("complete subagent");
        SubagentJob::update_status(
            &pool,
            session_id,
            execution_id,
            agent_id,
            SubagentJobStatus::Running,
        )
        .await
        .expect("ignore non-terminal update after completion");

        assert_eq!(status_for(&pool, execution_id, agent_id).await, "completed");
        assert!(
            completed_at_for(&pool, execution_id, agent_id)
                .await
                .is_some()
        );
    }

    async fn status_for(pool: &sqlx::SqlitePool, execution_id: Uuid, agent_id: &str) -> String {
        sqlx::query(
            r#"SELECT status
               FROM subagent_jobs
               WHERE execution_process_id = ? AND agent_id = ?"#,
        )
        .bind(execution_id)
        .bind(agent_id)
        .fetch_one(pool)
        .await
        .expect("fetch subagent status")
        .get::<String, _>("status")
    }

    async fn completed_at_for(
        pool: &sqlx::SqlitePool,
        execution_id: Uuid,
        agent_id: &str,
    ) -> Option<String> {
        sqlx::query(
            r#"SELECT completed_at
               FROM subagent_jobs
               WHERE execution_process_id = ? AND agent_id = ?"#,
        )
        .bind(execution_id)
        .bind(agent_id)
        .fetch_one(pool)
        .await
        .expect("fetch subagent completed_at")
        .get::<Option<String>, _>("completed_at")
    }
}
