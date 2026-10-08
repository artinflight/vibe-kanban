use chrono::{DateTime, Utc};
use db::models::{
    agent_delivery::{AgentDelivery, DeliveryClaim},
    scratch::DraftFollowUpData,
};
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use ts_rs::TS;
use uuid::Uuid;

/// Represents a queued follow-up message for a session
#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct QueuedMessage {
    /// The session this message is queued for
    pub session_id: Uuid,
    /// The most recent follow-up data. Kept for API compatibility and edit restore.
    pub data: DraftFollowUpData,
    /// Ordered follow-up messages queued while the agent was running.
    pub messages: Vec<DraftFollowUpData>,
    /// Timestamp when the message was queued
    pub queued_at: DateTime<Utc>,
    /// True when this message is waiting for global executor capacity rather than
    /// a currently running turn in the same session to finish.
    #[serde(default)]
    pub wait_for_capacity: bool,
}

impl QueuedMessage {
    /// Collapse queued follow-ups into one prompt for the next agent turn.
    pub fn into_follow_up_data(self) -> DraftFollowUpData {
        let fallback_executor_config = self.data.executor_config.clone();
        let messages = if self.messages.is_empty() {
            vec![self.data]
        } else {
            self.messages
        };
        let executor_config = messages
            .last()
            .map(|data| data.executor_config.clone())
            .unwrap_or(fallback_executor_config);

        let message = if messages.len() == 1 {
            messages
                .into_iter()
                .next()
                .map(|data| data.message)
                .unwrap_or_default()
        } else {
            let mut prompt = String::from(
                "The user sent these follow-up messages while the previous turn was still running. Address them in order.\n\n",
            );
            for (index, data) in messages.into_iter().enumerate() {
                if index > 0 {
                    prompt.push_str("\n\n");
                }
                prompt.push_str(&format!("Follow-up {}:\n{}", index + 1, data.message));
            }
            prompt
        };

        DraftFollowUpData {
            message,
            executor_config,
        }
    }
}

/// Status of the queue for a session (for frontend display)
#[derive(Debug, Clone, Serialize, Deserialize, TS)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum QueueStatus {
    /// No message queued
    Empty,
    /// Message is queued and waiting for execution to complete
    Queued { message: QueuedMessage },
}

/// The legacy queue DTO is a projection of the shared durable delivery ledger.
/// Claims keep their rows until process admission; there is no second consumer.
#[derive(Clone)]
pub struct QueuedMessageService {
    pool: SqlitePool,
}

#[derive(Debug, Clone)]
pub struct ClaimedQueuedMessage {
    pub message: QueuedMessage,
    pub claim: DeliveryClaim,
}

impl QueuedMessageService {
    pub fn new(pool: SqlitePool) -> Self {
        Self { pool }
    }

    pub async fn queue_message(
        &self,
        session_id: Uuid,
        data: DraftFollowUpData,
    ) -> Result<QueuedMessage, sqlx::Error> {
        self.queue_with_key(session_id, data, false, Uuid::new_v4())
            .await
    }

    pub async fn queue_for_capacity(
        &self,
        session_id: Uuid,
        data: DraftFollowUpData,
    ) -> Result<QueuedMessage, sqlx::Error> {
        self.queue_with_key(session_id, data, true, Uuid::new_v4())
            .await
    }

    pub async fn queue_with_key(
        &self,
        session_id: Uuid,
        data: DraftFollowUpData,
        capacity: bool,
        key: Uuid,
    ) -> Result<QueuedMessage, sqlx::Error> {
        let accepted = AgentDelivery::enqueue(&self.pool, session_id, data, capacity, key).await?;
        Self::project(&accepted).ok_or(sqlx::Error::RowNotFound)
    }

    pub async fn cancel_queued(&self, session_id: Uuid) -> Result<(), sqlx::Error> {
        AgentDelivery::cancel(&self.pool, session_id).await?;
        Ok(())
    }

    pub async fn get_queued(&self, session_id: Uuid) -> Result<Option<QueuedMessage>, sqlx::Error> {
        Ok(Self::project(
            &AgentDelivery::queued(&self.pool, session_id).await?,
        ))
    }

    pub async fn take_queued(
        &self,
        session_id: Uuid,
    ) -> Result<Option<ClaimedQueuedMessage>, sqlx::Error> {
        Ok(AgentDelivery::claim(&self.pool, session_id)
            .await?
            .map(|claim| ClaimedQueuedMessage {
                message: Self::project(&claim.deliveries).expect("nonempty delivery claim"),
                claim,
            }))
    }

    pub async fn take_oldest_capacity_queued(
        &self,
    ) -> Result<Option<ClaimedQueuedMessage>, sqlx::Error> {
        match AgentDelivery::oldest_capacity_session(&self.pool).await? {
            Some(session_id) => self.take_queued(session_id).await,
            None => Ok(None),
        }
    }

    pub async fn has_queued(&self, session_id: Uuid) -> Result<bool, sqlx::Error> {
        Ok(self.get_queued(session_id).await?.is_some())
    }

    pub async fn get_status(&self, session_id: Uuid) -> Result<QueueStatus, sqlx::Error> {
        Ok(match self.get_queued(session_id).await? {
            Some(message) => QueueStatus::Queued { message },
            None => QueueStatus::Empty,
        })
    }

    fn project(deliveries: &[AgentDelivery]) -> Option<QueuedMessage> {
        let first = deliveries.first()?;
        let last = deliveries.last()?;
        Some(QueuedMessage {
            session_id: first.session_id,
            data: last.data.0.clone(),
            messages: deliveries.iter().map(|d| d.data.0.clone()).collect(),
            queued_at: first.queued_at,
            wait_for_capacity: first.wait_for_capacity,
        })
    }
}

#[cfg(test)]
mod tests;
