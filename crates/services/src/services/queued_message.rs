use std::sync::Arc;

use chrono::{DateTime, Utc};
use dashmap::DashMap;
use db::models::scratch::DraftFollowUpData;
use serde::{Deserialize, Serialize};
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

/// In-memory service for managing queued follow-up messages.
/// One queued message per session.
#[derive(Clone)]
pub struct QueuedMessageService {
    queue: Arc<DashMap<Uuid, QueuedMessage>>,
}

impl QueuedMessageService {
    pub fn new() -> Self {
        Self {
            queue: Arc::new(DashMap::new()),
        }
    }

    /// Queue a message for a session. Appends to any existing queued messages.
    pub fn queue_message(&self, session_id: Uuid, data: DraftFollowUpData) -> QueuedMessage {
        if let Some(mut existing) = self.queue.get_mut(&session_id) {
            existing.data = data.clone();
            existing.messages.push(data);
            return existing.clone();
        }

        let queued = QueuedMessage {
            session_id,
            data: data.clone(),
            messages: vec![data],
            queued_at: Utc::now(),
            wait_for_capacity: false,
        };
        self.queue.insert(session_id, queued.clone());
        queued
    }

    /// Queue a message that should start when global executor capacity opens.
    pub fn queue_for_capacity(&self, session_id: Uuid, data: DraftFollowUpData) -> QueuedMessage {
        let queued = QueuedMessage {
            session_id,
            data: data.clone(),
            messages: vec![data],
            queued_at: Utc::now(),
            wait_for_capacity: true,
        };
        self.queue.insert(session_id, queued.clone());
        queued
    }

    /// Cancel/remove a queued message for a session
    pub fn cancel_queued(&self, session_id: Uuid) -> Option<QueuedMessage> {
        self.queue.remove(&session_id).map(|(_, v)| v)
    }

    /// Get the queued message for a session (if any)
    pub fn get_queued(&self, session_id: Uuid) -> Option<QueuedMessage> {
        self.queue.get(&session_id).map(|r| r.clone())
    }

    /// Take (remove and return) the queued message for a session.
    /// Used by finalization flow to consume the queued message.
    pub fn take_queued(&self, session_id: Uuid) -> Option<QueuedMessage> {
        self.queue.remove(&session_id).map(|(_, v)| v)
    }

    /// Take the oldest message waiting for global executor capacity.
    pub fn take_oldest_capacity_queued(&self) -> Option<QueuedMessage> {
        let session_id = self
            .queue
            .iter()
            .filter(|entry| entry.value().wait_for_capacity)
            .min_by_key(|entry| entry.value().queued_at)
            .map(|entry| *entry.key())?;

        self.take_queued(session_id)
    }

    /// Check if a session has a queued message
    pub fn has_queued(&self, session_id: Uuid) -> bool {
        self.queue.contains_key(&session_id)
    }

    /// Get queue status for frontend display
    pub fn get_status(&self, session_id: Uuid) -> QueueStatus {
        match self.get_queued(session_id) {
            Some(msg) => QueueStatus::Queued { message: msg },
            None => QueueStatus::Empty,
        }
    }
}

impl Default for QueuedMessageService {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use chrono::Duration;
    use executors::{executors::BaseCodingAgent, profile::ExecutorConfig};

    use super::*;

    fn draft(message: &str) -> DraftFollowUpData {
        DraftFollowUpData {
            message: message.to_string(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        }
    }

    #[test]
    fn takes_oldest_capacity_queue_without_consuming_normal_queue() {
        let service = QueuedMessageService::new();
        let normal_session_id = Uuid::new_v4();
        let newer_capacity_session_id = Uuid::new_v4();
        let older_capacity_session_id = Uuid::new_v4();

        service.queue_message(normal_session_id, draft("normal"));
        service.queue_for_capacity(newer_capacity_session_id, draft("newer"));
        service.queue_for_capacity(older_capacity_session_id, draft("older"));

        {
            let mut newer = service
                .queue
                .get_mut(&newer_capacity_session_id)
                .expect("newer capacity message exists");
            newer.queued_at = Utc::now();
        }
        {
            let mut older = service
                .queue
                .get_mut(&older_capacity_session_id)
                .expect("older capacity message exists");
            older.queued_at = Utc::now() - Duration::minutes(1);
        }

        let taken = service
            .take_oldest_capacity_queued()
            .expect("capacity message exists");

        assert_eq!(taken.session_id, older_capacity_session_id);
        assert_eq!(taken.data.message, "older");
        assert!(taken.wait_for_capacity);
        assert!(service.get_queued(normal_session_id).is_some());
        assert!(service.get_queued(newer_capacity_session_id).is_some());
        assert!(service.get_queued(older_capacity_session_id).is_none());
    }
}
