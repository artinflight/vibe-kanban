use executors::executors::BaseCodingAgent;
use sqlx::types::Json;

use super::*;

#[derive(Debug, thiserror::Error)]
pub enum SteeringStoreError {
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error("Delivery identity already has different content")]
    IdempotencyConflict,
}

#[derive(Debug)]
pub enum SteeringAdmission {
    Unavailable,
    Attempt(AgentDelivery),
    Replay(AgentDelivery),
}

#[derive(Debug, Clone, Copy)]
pub enum SteeringResult {
    Acknowledged,
    Unavailable,
    Uncertain,
}

impl AgentDelivery {
    /// Records the exact process before an external RPC. A repeat request never
    /// starts another RPC, including a repeat while the original is in flight.
    pub async fn begin_steering(
        pool: &SqlitePool,
        session_id: Uuid,
        data: &DraftFollowUpData,
        request_id: Uuid,
    ) -> Result<SteeringAdmission, SteeringStoreError> {
        let mut tx = pool.begin().await?;
        let workspace_id: Uuid = sqlx::query_scalar(
            "UPDATE sessions SET updated_at = updated_at WHERE id = ? RETURNING workspace_id",
        )
        .bind(session_id)
        .fetch_one(&mut *tx)
        .await?;
        if let Some(old) = sqlx::query_as::<_, Self>("SELECT * FROM agent_deliveries WHERE source_kind = 'session' AND source_id = ? AND idempotency_key = ? AND session_id = ?")
            .bind(session_id).bind(request_id).bind(session_id).fetch_optional(&mut *tx).await? {
            if old.delivery_mode != "steer" || serde_json::to_value(&old.data.0).map_err(encode)? != serde_json::to_value(data).map_err(encode)? {
                return Err(SteeringStoreError::IdempotencyConflict);
            }
            tx.commit().await?;
            return Ok(SteeringAdmission::Replay(old));
        }
        if data.executor_config.executor != BaseCodingAgent::Codex {
            tx.commit().await?;
            return Ok(SteeringAdmission::Unavailable);
        }
        let available: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspaces WHERE id = ? AND archived = 0 AND worktree_deleted = 0)")
            .bind(workspace_id).fetch_one(&mut *tx).await?;
        if !available {
            tx.commit().await?;
            return Ok(SteeringAdmission::Unavailable);
        }
        // Never route to another process based on session state after this point.
        let process = sqlx::query_as::<_, ExecutionProcess>("SELECT * FROM execution_processes WHERE session_id = ? AND status = 'running' AND run_reason = 'codingagent' AND dropped = 0 ORDER BY created_at DESC,rowid DESC LIMIT 1")
            .bind(session_id).fetch_optional(&mut *tx).await?;
        let Some(process) = process else {
            tx.commit().await?;
            return Ok(SteeringAdmission::Unavailable);
        };
        if process
            .executor_action()
            .ok()
            .and_then(|a| a.base_executor())
            != Some(BaseCodingAgent::Codex)
        {
            tx.commit().await?;
            return Ok(SteeringAdmission::Unavailable);
        }
        let record = sqlx::query_as::<_, Self>("INSERT INTO agent_deliveries (id,source_kind,source_id,idempotency_key,session_id,workspace_id,data,state,requested_capacity,wait_for_capacity,claim_id,lease_until,attempt_count,execution_process_id,delivery_mode) VALUES (?, 'session', ?, ?, ?, ?, ?, 'dispatching', 0, 0, ?, unixepoch()+60, 1, ?, 'steer') RETURNING *")
            .bind(Uuid::new_v4()).bind(session_id).bind(request_id).bind(session_id).bind(workspace_id)
            .bind(Json(data)).bind(Uuid::new_v4()).bind(process.id).fetch_one(&mut *tx).await?;
        tx.commit().await?;
        Ok(SteeringAdmission::Attempt(record))
    }

    /// A late acknowledgement can resolve this exact attempt's uncertainty. It
    /// cannot change another attempt or turn a known rejection into success.
    pub async fn finish_steering(
        pool: &SqlitePool,
        attempt: &AgentDelivery,
        result: SteeringResult,
    ) -> Result<AgentDelivery, sqlx::Error> {
        let (state, error, ack) = match result {
            SteeringResult::Acknowledged => ("started", None, true),
            SteeringResult::Unavailable => ("failed", Some("steering_unavailable"), false),
            SteeringResult::Uncertain => (
                "unknown_delivery",
                Some("steering_acknowledgement_uncertain"),
                false,
            ),
        };
        sqlx::query_as("UPDATE agent_deliveries SET state = ?, error = ?, steering_acknowledged_at = CASE WHEN ? THEN datetime('now','subsec') ELSE NULL END, lease_until = NULL, updated_at = datetime('now','subsec') WHERE id = ? AND claim_id = ? AND session_id = ? AND execution_process_id = ? AND delivery_mode = 'steer' AND state IN ('dispatching','unknown_delivery') RETURNING *")
            .bind(state).bind(error).bind(ack).bind(attempt.id).bind(attempt.claim_id).bind(attempt.session_id).bind(attempt.execution_process_id)
            .fetch_optional(pool).await?.ok_or(sqlx::Error::RowNotFound)
    }
}

fn encode(error: serde_json::Error) -> sqlx::Error {
    sqlx::Error::Encode(Box::new(error))
}
