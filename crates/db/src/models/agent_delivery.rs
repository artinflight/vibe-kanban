//! Durable delivery admission shared by direct session queues and orchestration.
//! A claim may be retried only before atomic process correlation. Once correlated,
//! process/runtime evidence determines the outcome; lease expiry never resends it.
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

use super::{
    execution_process::{CreateExecutionProcess, ExecutionProcess},
    execution_process_repo_state::CreateExecutionProcessRepoState,
    scratch::DraftFollowUpData,
};

#[derive(Debug, Clone, FromRow, Serialize, Deserialize)]
pub struct AgentDelivery {
    pub id: Uuid,
    pub position: i64,
    pub source_kind: String,
    pub source_id: Uuid,
    pub idempotency_key: Uuid,
    pub session_id: Uuid,
    pub workspace_id: Uuid,
    pub data: sqlx::types::Json<DraftFollowUpData>,
    pub state: String,
    pub requested_capacity: bool,
    pub wait_for_capacity: bool,
    pub predecessor_process_id: Option<Uuid>,
    pub claim_id: Option<Uuid>,
    pub lease_until: Option<i64>,
    pub execution_process_id: Option<Uuid>,
    pub error: Option<String>,
    pub queued_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct DeliveryClaim {
    pub id: Uuid,
    pub session_id: Uuid,
    pub deliveries: Vec<AgentDelivery>,
}

impl AgentDelivery {
    pub async fn enqueue(
        pool: &SqlitePool,
        session_id: Uuid,
        data: DraftFollowUpData,
        capacity: bool,
        request_id: Uuid,
    ) -> Result<Vec<Self>, sqlx::Error> {
        let mut tx = pool.begin().await?;
        // First statement is a write: no deferred read/write upgrade races.
        let workspace_id: Uuid = sqlx::query_scalar(
            "UPDATE sessions SET updated_at = updated_at WHERE id = ? RETURNING workspace_id",
        )
        .bind(session_id)
        .fetch_one(&mut *tx)
        .await?;
        let old = sqlx::query_as::<_, Self>(
            "SELECT * FROM agent_deliveries WHERE source_kind = 'session' AND source_id = ? AND idempotency_key = ? AND session_id = ?",
        ).bind(session_id).bind(request_id).bind(session_id).fetch_optional(&mut *tx).await?;
        if let Some(old) = old {
            let value =
                serde_json::to_value(&data).map_err(|e| sqlx::Error::Encode(Box::new(e)))?;
            if serde_json::to_value(&old.data.0).map_err(|e| sqlx::Error::Encode(Box::new(e)))?
                != value
                || old.requested_capacity != capacity
            {
                return Err(sqlx::Error::Protocol(
                    "Delivery idempotency key reused with different input".into(),
                ));
            }
            let queued = sqlx::query_as::<_, Self>("SELECT * FROM agent_deliveries WHERE session_id = ? AND state IN ('queued','waiting_capacity') ORDER BY position")
                .bind(session_id).fetch_all(&mut *tx).await?;
            tx.commit().await?;
            return Ok(if queued.is_empty() { vec![old] } else { queued });
        }
        let predecessor: Option<Uuid> = sqlx::query_scalar(
            "SELECT id FROM execution_processes WHERE session_id = ? AND dropped = 0 AND run_reason != 'devserver' ORDER BY created_at DESC, rowid DESC LIMIT 1",
        ).bind(session_id).fetch_optional(&mut *tx).await?;
        if capacity {
            // Preserve existing capacity queue replacement, retaining cancelled receipts.
            sqlx::query("UPDATE agent_deliveries SET state = 'cancelled', error = 'replaced_capacity_request', updated_at = datetime('now','subsec') WHERE session_id = ? AND state IN ('queued','waiting_capacity')")
                .bind(session_id).execute(&mut *tx).await?;
        }
        let waiting: bool = if capacity {
            true
        } else {
            sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM agent_deliveries WHERE session_id = ? AND state = 'waiting_capacity')")
                .bind(session_id).fetch_one(&mut *tx).await?
        };
        sqlx::query("INSERT INTO agent_deliveries (id, source_kind, source_id, idempotency_key, session_id, workspace_id, data, state, requested_capacity, wait_for_capacity, predecessor_process_id) VALUES (?, 'session', ?, ?, ?, ?, ?, ?, ?, ?, ?)")
            .bind(Uuid::new_v4()).bind(session_id).bind(request_id).bind(session_id).bind(workspace_id)
            .bind(sqlx::types::Json(data)).bind(if waiting { "waiting_capacity" } else { "queued" })
            .bind(capacity).bind(waiting).bind(predecessor).execute(&mut *tx).await?;
        let queued = sqlx::query_as::<_, Self>("SELECT * FROM agent_deliveries WHERE session_id = ? AND state IN ('queued','waiting_capacity') ORDER BY position")
            .bind(session_id).fetch_all(&mut *tx).await?;
        tx.commit().await?;
        Ok(queued)
    }

    pub async fn queued(pool: &SqlitePool, session_id: Uuid) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as("SELECT * FROM agent_deliveries WHERE session_id = ? AND state IN ('queued','waiting_capacity') ORDER BY position")
            .bind(session_id).fetch_all(pool).await
    }

    pub async fn cancel(pool: &SqlitePool, session_id: Uuid) -> Result<u64, sqlx::Error> {
        Ok(sqlx::query("UPDATE agent_deliveries SET state = 'cancelled', error = 'user_cancelled', updated_at = datetime('now','subsec') WHERE session_id = ? AND state IN ('queued','waiting_capacity')")
            .bind(session_id).execute(pool).await?.rows_affected())
    }

    pub async fn claim(
        pool: &SqlitePool,
        session_id: Uuid,
    ) -> Result<Option<DeliveryClaim>, sqlx::Error> {
        let mut tx = pool.begin().await?;
        sqlx::query("UPDATE agent_deliveries SET updated_at = updated_at WHERE session_id = ? AND state IN ('queued','waiting_capacity')")
            .bind(session_id).execute(&mut *tx).await?;
        let claimed: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM agent_deliveries WHERE session_id = ? AND state = 'dispatching')")
            .bind(session_id).fetch_one(&mut *tx).await?;
        if claimed {
            tx.commit().await?;
            return Ok(None);
        }
        let claim_id = Uuid::new_v4();
        let mut deliveries = sqlx::query_as::<_, Self>("UPDATE agent_deliveries SET state = 'dispatching', claim_id = ?, lease_until = unixepoch() + 300, attempt_count = attempt_count + 1, updated_at = datetime('now','subsec') WHERE session_id = ? AND state IN ('queued','waiting_capacity') RETURNING *")
            .bind(claim_id).bind(session_id).fetch_all(&mut *tx).await?;
        deliveries.sort_by_key(|d| d.position);
        tx.commit().await?;
        Ok((!deliveries.is_empty()).then_some(DeliveryClaim {
            id: claim_id,
            session_id,
            deliveries,
        }))
    }

    pub async fn oldest_capacity_session(pool: &SqlitePool) -> Result<Option<Uuid>, sqlx::Error> {
        sqlx::query_scalar("SELECT d.session_id FROM agent_deliveries d WHERE d.state = 'waiting_capacity' AND NOT EXISTS(SELECT 1 FROM agent_deliveries a WHERE a.session_id = d.session_id AND a.state = 'dispatching') AND NOT EXISTS(SELECT 1 FROM execution_processes p WHERE p.session_id IN (SELECT id FROM sessions WHERE workspace_id = d.workspace_id) AND p.status = 'running' AND p.run_reason != 'devserver' AND p.dropped = 0) ORDER BY d.position LIMIT 1")
            .fetch_optional(pool).await
    }

    /// Release only a still-unadmitted claim. New messages enqueued while it was
    /// claimed remain separate and cannot be overwritten by this retry.
    pub async fn release(
        pool: &SqlitePool,
        claim: &DeliveryClaim,
        capacity: bool,
    ) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE agent_deliveries SET state = CASE WHEN ? THEN 'waiting_capacity' ELSE CASE WHEN wait_for_capacity THEN 'waiting_capacity' ELSE 'queued' END END, wait_for_capacity = CASE WHEN ? THEN 1 ELSE wait_for_capacity END, claim_id = NULL, lease_until = NULL, updated_at = datetime('now','subsec') WHERE claim_id = ? AND session_id = ? AND state = 'dispatching' AND execution_process_id IS NULL")
            .bind(capacity).bind(capacity).bind(claim.id).bind(claim.session_id).execute(pool).await?;
        Ok(())
    }

    pub async fn fail_claim(
        pool: &SqlitePool,
        claim: &DeliveryClaim,
        reason: &str,
    ) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE agent_deliveries SET state = 'failed', lease_until = NULL, error = ?, updated_at = datetime('now','subsec') WHERE claim_id = ? AND session_id = ? AND state = 'dispatching' AND execution_process_id IS NULL")
            .bind(reason).bind(claim.id).bind(claim.session_id).execute(pool).await?;
        Ok(())
    }

    /// Persist process identity and all contributing message receipts in the same
    /// transaction. Callers must emit process updates after commit, not DB hooks.
    pub async fn admit(
        pool: &SqlitePool,
        claim: &DeliveryClaim,
        data: &CreateExecutionProcess,
        process_id: Uuid,
        repo_states: &[CreateExecutionProcessRepoState],
    ) -> Result<ExecutionProcess, sqlx::Error> {
        if data.session_id != claim.session_id {
            return Err(sqlx::Error::RowNotFound);
        }
        let mut tx = pool.begin().await?;
        let count = sqlx::query("UPDATE agent_deliveries SET state = 'started', execution_process_id = ?, lease_until = NULL, updated_at = datetime('now','subsec') WHERE claim_id = ? AND session_id = ? AND state = 'dispatching' AND lease_until > unixepoch() AND execution_process_id IS NULL")
            .bind(process_id).bind(claim.id).bind(claim.session_id).execute(&mut *tx).await?.rows_affected();
        if count == 0 || count as usize != claim.deliveries.len() {
            return Err(sqlx::Error::RowNotFound);
        }
        let valid: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM sessions s JOIN workspaces w ON w.id = s.workspace_id WHERE s.id = ? AND w.archived = 0 AND w.worktree_deleted = 0 AND NOT EXISTS(SELECT 1 FROM execution_processes p WHERE p.session_id IN (SELECT id FROM sessions WHERE workspace_id = w.id) AND p.status = 'running' AND p.run_reason != 'devserver' AND p.dropped = 0))")
            .bind(data.session_id).fetch_one(&mut *tx).await?;
        if !valid {
            return Err(sqlx::Error::Protocol(
                "Queued target changed or is already running".into(),
            ));
        }
        sqlx::query("INSERT INTO execution_processes (id, session_id, run_reason, executor_action, status) VALUES (?, ?, ?, ?, 'running')")
            .bind(process_id).bind(data.session_id).bind(&data.run_reason).bind(sqlx::types::Json(&data.executor_action)).execute(&mut *tx).await?;
        for entry in repo_states {
            sqlx::query("INSERT INTO execution_process_repo_states (id, execution_process_id, repo_id, before_head_commit, after_head_commit, merge_commit) VALUES (?, ?, ?, ?, ?, ?)")
                .bind(Uuid::new_v4()).bind(process_id).bind(entry.repo_id).bind(&entry.before_head_commit).bind(&entry.after_head_commit).bind(&entry.merge_commit).execute(&mut *tx).await?;
        }
        tx.commit().await?;
        ExecutionProcess::find_by_id(pool, process_id)
            .await?
            .ok_or(sqlx::Error::RowNotFound)
    }

    /// Only the pre-launch capacity denial permits a correlated attempt to queue
    /// again. Arbitrary failed/unknown starts are never automatically retried.
    pub async fn capacity_denied(pool: &SqlitePool, process_id: Uuid) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE agent_deliveries SET state = 'waiting_capacity', wait_for_capacity = 1, execution_process_id = NULL, claim_id = NULL, lease_until = NULL, error = NULL, updated_at = datetime('now','subsec') WHERE execution_process_id = ? AND state = 'started'")
            .bind(process_id).execute(pool).await?;
        Ok(())
    }

    pub async fn reconcile(pool: &SqlitePool) -> Result<(), sqlx::Error> {
        let mut tx = pool.begin().await?;
        // No spawn can occur before atomic admission, so only unadmitted leases retry.
        sqlx::query("UPDATE agent_deliveries SET state = CASE WHEN wait_for_capacity THEN 'waiting_capacity' ELSE 'queued' END, claim_id = NULL, lease_until = NULL, updated_at = datetime('now','subsec') WHERE state = 'dispatching' AND execution_process_id IS NULL AND lease_until <= unixepoch()")
            .execute(&mut *tx).await?;
        sqlx::query("UPDATE agent_deliveries SET state = CASE WHEN (SELECT status FROM execution_processes WHERE id = execution_process_id) = 'completed' AND (SELECT dropped FROM execution_processes WHERE id = execution_process_id) = 0 THEN 'completed' ELSE 'failed' END, error = CASE WHEN (SELECT status FROM execution_processes WHERE id = execution_process_id) = 'completed' AND (SELECT dropped FROM execution_processes WHERE id = execution_process_id) = 0 THEN NULL ELSE 'execution_failed_or_interrupted' END, updated_at = datetime('now','subsec') WHERE state = 'started' AND EXISTS(SELECT 1 FROM execution_processes p WHERE p.id = execution_process_id AND (p.status != 'running' OR p.dropped != 0))")
            .execute(&mut *tx).await?;
        sqlx::query("UPDATE agent_deliveries SET state = 'unknown_delivery', error = 'correlated_process_missing', updated_at = datetime('now','subsec') WHERE state = 'started' AND NOT EXISTS(SELECT 1 FROM execution_processes p WHERE p.id = execution_process_id)")
            .execute(&mut *tx).await?;
        sqlx::query("UPDATE agent_deliveries SET state = 'failed', error = 'target_unavailable', updated_at = datetime('now','subsec') WHERE state IN ('queued','waiting_capacity') AND NOT EXISTS(SELECT 1 FROM sessions s JOIN workspaces w ON s.workspace_id = w.id WHERE s.id = agent_deliveries.session_id AND w.archived = 0 AND w.worktree_deleted = 0)")
            .execute(&mut *tx).await?;
        sqlx::query("UPDATE agent_deliveries SET state = 'failed', error = 'predecessor_failed_or_interrupted', updated_at = datetime('now','subsec') WHERE state = 'queued' AND predecessor_process_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM execution_processes p WHERE p.id = predecessor_process_id AND p.dropped = 0 AND p.status IN ('running','completed'))")
            .execute(&mut *tx).await?;
        tx.commit().await
    }

    pub async fn recoverable_sessions(pool: &SqlitePool) -> Result<Vec<Uuid>, sqlx::Error> {
        sqlx::query_scalar("SELECT DISTINCT d.session_id FROM agent_deliveries d WHERE d.state IN ('queued','waiting_capacity') AND NOT EXISTS(SELECT 1 FROM execution_processes p WHERE p.session_id IN (SELECT id FROM sessions WHERE workspace_id = d.workspace_id) AND p.status = 'running' AND p.run_reason != 'devserver' AND p.dropped = 0) ORDER BY d.position LIMIT 32")
            .fetch_all(pool).await
    }
}
