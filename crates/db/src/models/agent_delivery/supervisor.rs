//! Revalidate immutable supervisor authorization at the shared execution seam.
//! Direct workspace deliveries do not depend on supervisor records or memory.
use executors::{
    actions::{ExecutorAction, ExecutorActionType},
    profile::ExecutorConfig,
};
use sqlx::SqliteConnection;

use super::*;
use crate::models::conversation::{
    ConversationError,
    actions::{self, AgentMessage},
    records::ConversationAction,
};

pub(super) fn executor_config(action: &ExecutorAction) -> Option<&ExecutorConfig> {
    match action.typ() {
        ExecutorActionType::CodingAgentInitialRequest(r) => Some(&r.executor_config),
        ExecutorActionType::CodingAgentFollowUpRequest(r) => Some(&r.executor_config),
        _ => None,
    }
}

pub(super) async fn validate(
    conn: &mut SqliteConnection,
    delivery: &AgentDelivery,
) -> Result<(), ExecutionProcessError> {
    if delivery.source_kind != "supervisor" {
        return Ok(());
    }
    let action:ConversationAction=sqlx::query_as("SELECT * FROM conversation_actions WHERE id=? AND conversation_id=? AND intent_kind='agent_message' AND state IN ('dispatching','unknown_delivery') AND authorisation_source IS NOT NULL")
        .bind(delivery.action_id).bind(delivery.source_id).fetch_optional(&mut *conn).await?.ok_or(ExecutionProcessError::DeliveryRejected)?;
    let message: AgentMessage = serde_json::from_value(action.payload.0)
        .map_err(|_| ExecutionProcessError::DeliveryRejected)?;
    let expected = message
        .targets
        .iter()
        .find(|t| t.session_id == delivery.session_id)
        .ok_or(ExecutionProcessError::DeliveryRejected)?;
    if expected.workspace_id != delivery.workspace_id
        || expected.executor_config != delivery.data.executor_config
        || message.message != delivery.data.message
    {
        return Err(ExecutionProcessError::DeliveryRejected);
    }
    let current =
        actions::target(conn, delivery.session_id)
            .await
            .map_err(|error| match error {
                ConversationError::Database(e) => ExecutionProcessError::Database(e),
                _ => ExecutionProcessError::DeliveryRejected,
            })?;
    if current != *expected {
        return Err(ExecutionProcessError::DeliveryRejected);
    }
    Ok(())
}

impl AgentDelivery {
    pub async fn supervisor_for_process(
        pool: &SqlitePool,
        process: Uuid,
    ) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as("SELECT * FROM agent_deliveries WHERE execution_process_id=? AND source_kind='supervisor' AND state='started'")
            .bind(process).fetch_all(pool).await
    }

    /// Recheck the authorised target immediately before an external delivery.
    /// Receipt identity cannot be substituted for another claimed recipient.
    pub async fn validate_supervisor_delivery(
        pool: &SqlitePool,
        expected: &AgentDelivery,
    ) -> Result<(), ExecutionProcessError> {
        let mut tx = pool.begin().await?;
        let delivery: Self = sqlx::query_as("SELECT * FROM agent_deliveries WHERE id=? AND claim_id=? AND state IN ('dispatching','started') AND source_kind='supervisor'")
            .bind(expected.id).bind(expected.claim_id).fetch_optional(&mut *tx).await?
            .ok_or(ExecutionProcessError::DeliveryRejected)?;
        if delivery.session_id != expected.session_id
            || delivery.execution_process_id != expected.execution_process_id
            || delivery.data.message != expected.data.message
            || delivery.data.executor_config != expected.data.executor_config
            || delivery.workspace_id != expected.workspace_id
        {
            return Err(ExecutionProcessError::DeliveryRejected);
        }
        validate(&mut tx, &delivery).await?;
        tx.commit().await?;
        Ok(())
    }

    /// Early check before workspace preparation. Admission repeats it under its
    /// writer lock, so a subsequent configuration change cannot launch stale work.
    pub async fn validate_supervisor_claim(
        pool: &SqlitePool,
        claim: &DeliveryClaim,
    ) -> Result<(), ExecutionProcessError> {
        let mut tx = pool.begin().await?;
        for expected in &claim.deliveries {
            let delivery:Self=sqlx::query_as("SELECT * FROM agent_deliveries WHERE id=? AND claim_id=? AND session_id=? AND state='dispatching' AND lease_until>unixepoch() AND execution_process_id IS NULL")
                .bind(expected.id).bind(claim.id).bind(claim.session_id).fetch_optional(&mut *tx).await?.ok_or(sqlx::Error::RowNotFound)?;
            validate(&mut tx, &delivery).await?;
        }
        tx.commit().await?;
        Ok(())
    }
}
