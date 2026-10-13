//! Durable per-execution checkpoint queue; publication evidence stays in private receipts.
use serde::Serialize;
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

#[derive(Debug, FromRow, Serialize)]
pub struct TurnGithubSync {
    pub execution_process_id: Uuid,
    pub workspace_id: Uuid,
    pub request: String,
    pub writer_group: Option<i64>,
    pub state: String,
    pub attempts: i64,
    pub report: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn owner_identity_retry_and_completion_survive_queue_reopen() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        sqlx::raw_sql("CREATE TABLE execution_processes (id BLOB PRIMARY KEY, status TEXT); CREATE TABLE workspaces (id BLOB PRIMARY KEY);")
            .execute(&pool).await.unwrap();
        sqlx::raw_sql(include_str!(
            "../../migrations/20261013120000_turn_github_sync.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        let workspace = Uuid::new_v4();
        let owner = Uuid::new_v4();
        sqlx::query("INSERT INTO workspaces VALUES (?)")
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO execution_processes VALUES (?, 'running')")
            .bind(owner)
            .execute(&pool)
            .await
            .unwrap();
        TurnGithubSync::enqueue(&pool, owner, workspace, "immutable-owner")
            .await
            .unwrap();
        TurnGithubSync::enqueue(&pool, owner, workspace, "duplicate-must-not-replace")
            .await
            .unwrap();
        assert!(TurnGithubSync::ready(&pool).await.unwrap().is_empty());
        TurnGithubSync::bind_group(&pool, owner, 123).await.unwrap();
        sqlx::query("UPDATE execution_processes SET status = 'completed'")
            .execute(&pool)
            .await
            .unwrap();
        let job = TurnGithubSync::ready(&pool).await.unwrap().remove(0);
        assert_eq!(job.request, "immutable-owner");
        assert_eq!(job.writer_group, Some(123));
        job.record(&pool, "blocked", "remote-unavailable")
            .await
            .unwrap();
        assert!(
            TurnGithubSync::ready(&pool).await.unwrap().is_empty(),
            "retry must back off"
        );
        sqlx::query("UPDATE turn_github_sync SET retry_at = 0")
            .execute(&pool)
            .await
            .unwrap();
        let restored = TurnGithubSync::ready(&pool).await.unwrap().remove(0);
        assert_eq!(restored.state, "blocked");
        assert_eq!(restored.attempts, 1);
        restored
            .record(&pool, "verified", "exact-remote-proof")
            .await
            .unwrap();
        assert!(TurnGithubSync::ready(&pool).await.unwrap().is_empty());
        job.record(&pool, "blocked", "stale-retry").await.unwrap();
        let status = TurnGithubSync::for_workspace(&pool, workspace)
            .await
            .unwrap();
        assert_eq!(status.len(), 1);
        assert_eq!(
            status[0].state, "verified",
            "stale completion must not overwrite success"
        );
    }
}

impl TurnGithubSync {
    pub async fn enqueue(
        pool: &SqlitePool,
        execution: Uuid,
        workspace: Uuid,
        request: &str,
    ) -> Result<(), sqlx::Error> {
        sqlx::query("INSERT INTO turn_github_sync (execution_process_id, workspace_id, request) VALUES (?, ?, ?) ON CONFLICT(execution_process_id) DO NOTHING")
            .bind(execution).bind(workspace).bind(request).execute(pool).await?;
        Ok(())
    }

    pub async fn ready(pool: &SqlitePool) -> Result<Vec<Self>, sqlx::Error> {
        // Persisted executor completion, rather than a transient callback, makes restart
        // recovery possible. A missing completion remains waiting, never successful.
        sqlx::query_as("SELECT j.execution_process_id, j.workspace_id, j.request, j.writer_group, j.state, j.attempts, j.report FROM turn_github_sync j LEFT JOIN execution_processes e ON e.id = j.execution_process_id WHERE j.state != 'verified' AND (e.id IS NULL OR e.status != 'running') AND j.retry_at <= unixepoch() ORDER BY j.retry_at, j.created_at, j.rowid LIMIT 64")
            .fetch_all(pool).await
    }

    pub async fn defer(&self, pool: &SqlitePool) -> Result<(), sqlx::Error> {
        // Fairness across a page of busy owners without counting a sync attempt.
        sqlx::query("UPDATE turn_github_sync SET retry_at = unixepoch() + 5 WHERE execution_process_id = ? AND state != 'verified'")
            .bind(self.execution_process_id).execute(pool).await?;
        Ok(())
    }

    pub async fn bind_group(
        pool: &SqlitePool,
        execution: Uuid,
        group: u32,
    ) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE turn_github_sync SET writer_group = ? WHERE execution_process_id = ? AND writer_group IS NULL")
            .bind(i64::from(group)).bind(execution).execute(pool).await?;
        Ok(())
    }

    pub async fn record(
        &self,
        pool: &SqlitePool,
        state: &str,
        report: &str,
    ) -> Result<(), sqlx::Error> {
        // No in-flight state to strand after a crash. Retry reconciles the helper's
        // existing receipt and exact remote witness before another commit/push.
        sqlx::query("UPDATE turn_github_sync SET state = ?, report = ?, attempts = attempts + 1, retry_at = unixepoch() + min(3600, 30 * (1 << min(attempts, 7))), updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE execution_process_id = ? AND state != 'verified'")
            .bind(state).bind(report).bind(self.execution_process_id).execute(pool).await?;
        Ok(())
    }

    pub async fn for_workspace(
        pool: &SqlitePool,
        workspace: Uuid,
    ) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as("SELECT execution_process_id, workspace_id, request, writer_group, state, attempts, report FROM turn_github_sync WHERE workspace_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 64")
            .bind(workspace).fetch_all(pool).await
    }
}
