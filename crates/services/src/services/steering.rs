//! Durable wrapper around the executor's non-idempotent steering RPC. This is a
//! shared messaging primitive, independent of supervisor prompts or memory.
use std::{future::Future, time::Duration};

use db::models::{
    agent_delivery::{
        AgentDelivery,
        steering::{SteeringAdmission, SteeringResult, SteeringStoreError},
    },
    scratch::DraftFollowUpData,
};
use sqlx::SqlitePool;
use uuid::Uuid;

#[derive(Debug, PartialEq, Eq)]
pub enum SteeringOutcome {
    Unavailable,
    Acknowledged { delivery_id: Uuid, process_id: Uuid },
}

#[derive(Debug, thiserror::Error)]
pub enum SteeringError {
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error("Message ID already has different content")]
    IdempotencyConflict,
    #[error(
        "The agent may have received this message, but its acknowledgement is uncertain. Check its conversation before sending it again."
    )]
    Uncertain,
}

pub async fn steer<F, Fut, E>(
    pool: &SqlitePool,
    session_id: Uuid,
    data: &DraftFollowUpData,
    request_id: Uuid,
    send: F,
) -> Result<SteeringOutcome, SteeringError>
where
    F: FnOnce(Uuid) -> Fut,
    Fut: Future<Output = Result<bool, E>>,
{
    let attempt = match AgentDelivery::begin_steering(pool, session_id, data, request_id)
        .await
        .map_err(|error| match error {
            SteeringStoreError::IdempotencyConflict => SteeringError::IdempotencyConflict,
            SteeringStoreError::Database(error) => SteeringError::Database(error),
        })? {
        SteeringAdmission::Unavailable => return Ok(SteeringOutcome::Unavailable),
        SteeringAdmission::Replay(receipt) => return outcome(&receipt),
        SteeringAdmission::Attempt(receipt) => receipt,
    };
    send_attempt(pool, attempt, send).await
}

/// Consume the one owned attempt returned by atomic delivery admission. Never
/// reconstruct an attempt from a replayed receipt; receipt recovery is read-only.
pub(crate) async fn send_attempt<F, Fut, E>(
    pool: &SqlitePool,
    attempt: AgentDelivery,
    send: F,
) -> Result<SteeringOutcome, SteeringError>
where
    F: FnOnce(Uuid) -> Fut,
    Fut: Future<Output = Result<bool, E>>,
{
    let current: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM agent_deliveries WHERE id=? AND claim_id=? AND state='dispatching' AND delivery_mode='steer' AND steering_acknowledged_at IS NULL AND lease_until>unixepoch())")
        .bind(attempt.id).bind(attempt.claim_id).fetch_one(pool).await?;
    if !current {
        return Err(SteeringError::Uncertain);
    }
    let process_id = attempt
        .execution_process_id
        .ok_or(SteeringError::Uncertain)?;
    let result = match tokio::time::timeout(Duration::from_secs(30), send(process_id)).await {
        Ok(Ok(true)) => SteeringResult::Acknowledged,
        Ok(Ok(false)) => SteeringResult::Unavailable,
        Ok(Err(_)) | Err(_) => SteeringResult::Uncertain,
    };
    // A failed receipt write after an RPC is also ambiguous to the caller. Do not
    // turn it into an ordinary retryable DB error that might send the input again.
    let receipt = AgentDelivery::finish_steering(pool, &attempt, result)
        .await
        .map_err(|_| SteeringError::Uncertain)?;
    outcome(&receipt)
}

fn outcome(receipt: &AgentDelivery) -> Result<SteeringOutcome, SteeringError> {
    if receipt.steering_acknowledged_at.is_some() {
        return Ok(SteeringOutcome::Acknowledged {
            delivery_id: receipt.id,
            process_id: receipt
                .execution_process_id
                .ok_or(SteeringError::Uncertain)?,
        });
    }
    if receipt.state == "failed" && receipt.error.as_deref() == Some("steering_unavailable") {
        return Ok(SteeringOutcome::Unavailable);
    }
    Err(SteeringError::Uncertain)
}

#[cfg(test)]
mod tests;
