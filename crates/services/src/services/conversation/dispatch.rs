//! Executes already-authorised action proposals through the existing delivery
//! ledger and exact-process transport. This service never grants authorization.
use std::{future::Future, sync::Arc};

use async_trait::async_trait;
use db::models::{
    agent_delivery::AgentDelivery,
    conversation::{
        ConversationError, ConversationStore, actions::AgentMessage, records::ConversationAction,
    },
    session::Session,
};
use sqlx::SqlitePool;
use uuid::Uuid;

use super::dispatch_gate::{DispatchBlock, DispatchGate};
use crate::services::{
    container::{ContainerError, ContainerService},
    steering,
};

#[derive(Debug, thiserror::Error)]
pub enum DispatchError {
    #[error(transparent)]
    Store(#[from] ConversationError),
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error(transparent)]
    Blocked(#[from] DispatchBlock),
}

#[async_trait]
pub trait AgentTransport: Send + Sync {
    async fn steer(&self, delivery: AgentDelivery) -> Result<bool, ContainerError>;
}
pub struct ContainerTransport<C>(pub C);
#[async_trait]
impl<C: ContainerService + Send + Sync> AgentTransport for ContainerTransport<C> {
    async fn steer(&self, delivery: AgentDelivery) -> Result<bool, ContainerError> {
        let session = Session::find_by_id(&self.0.db().pool, delivery.session_id)
            .await?
            .ok_or(sqlx::Error::RowNotFound)?;
        self.0
            .try_steer_process(
                &session,
                &delivery.data,
                delivery
                    .execution_process_id
                    .ok_or(sqlx::Error::RowNotFound)?,
            )
            .await
    }
}

pub struct ActionDispatcher {
    pub store: ConversationStore,
    pool: SqlitePool,
    gate: DispatchGate,
}
impl ActionDispatcher {
    pub fn new(pool: SqlitePool, store: ConversationStore, gate: DispatchGate) -> Self {
        Self { pool, store, gate }
    }

    pub async fn via_transport(
        &self,
        id: Uuid,
        action: Uuid,
        transport: Arc<dyn AgentTransport>,
    ) -> Result<ConversationAction, DispatchError> {
        self.dispatch_with(id, action, |delivery| {
            let transport = transport.clone();
            async move { transport.steer(delivery).await }
        })
        .await
    }

    pub async fn dispatch<C: ContainerService + Sync>(
        &self,
        id: Uuid,
        action: Uuid,
        container: &C,
    ) -> Result<ConversationAction, DispatchError> {
        self.dispatch_with(id, action, |delivery| async move {
            let session = Session::find_by_id(&self.pool, delivery.session_id)
                .await?
                .ok_or(sqlx::Error::RowNotFound)?;
            container
                .try_steer_process(
                    &session,
                    &delivery.data,
                    delivery
                        .execution_process_id
                        .ok_or(sqlx::Error::RowNotFound)?,
                )
                .await
        })
        .await
    }

    async fn dispatch_with<F, Fut>(
        &self,
        id: Uuid,
        action_id: Uuid,
        mut send: F,
    ) -> Result<ConversationAction, DispatchError>
    where
        F: FnMut(AgentDelivery) -> Fut,
        Fut: Future<Output = Result<bool, ContainerError>>,
    {
        let action = self.store.action(id, action_id).await?;
        // A retry reads existing receipts regardless of subsequent lifecycle
        // changes. It never calls the transport again or resolves new recipients.
        if self
            .store
            .action_deliveries(id, action_id)
            .await?
            .is_empty()
        {
            if action.state != "approved" {
                return Err(ConversationError::InvalidRecord.into());
            }
            let message: AgentMessage = serde_json::from_value(action.payload.0)
                .map_err(|_| ConversationError::InvalidRecord)?;
            self.gate.message(&message).await?;
        }
        let admission = self.store.admit_agent_message(id, action_id).await?;
        for attempt in admission.steering_attempts {
            // Native goal, approvals and target scope can change during admission.
            // A known preflight rejection proves no RPC occurred. It is terminal
            // for this recipient and cannot silently fall back to a queue.
            let blocked = if AgentDelivery::validate_supervisor_delivery(&self.pool, &attempt)
                .await
                .is_err()
            {
                Some(DispatchBlock::TargetUnavailable)
            } else {
                self.gate.delivery(&attempt).await.err()
            };
            if let Some(block) = blocked {
                sqlx::query("UPDATE agent_deliveries SET state='failed',error=?,lease_until=NULL,updated_at=datetime('now','subsec') WHERE id=? AND claim_id=? AND state IN ('dispatching','unknown_delivery') AND steering_acknowledged_at IS NULL")
                    .bind(block.to_string()).bind(attempt.id).bind(attempt.claim_id).execute(&self.pool).await?;
                continue;
            }
            let payload = attempt.clone();
            // The primitive records acknowledged/unavailable/unknown. A failed
            // receipt write leaves the attempt for crash reconciliation, not retry.
            let _ = steering::send_attempt(&self.pool, attempt, |_| send(payload)).await;
        }
        self.store
            .reconcile_action(id, action_id)
            .await
            .map_err(Into::into)
    }
}

#[cfg(test)]
mod tests;
