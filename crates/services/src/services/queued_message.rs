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
    use db::models::scratch::DraftFollowUpData;
    use executors::{executors::BaseCodingAgent, profile::ExecutorConfig};
    use uuid::Uuid;

    use super::*;

    fn follow_up(message: &str) -> DraftFollowUpData {
        DraftFollowUpData {
            message: message.to_string(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        }
    }

    #[test]
    fn queue_message_appends_follow_ups_for_session() {
        let service = QueuedMessageService::new();
        let session_id = Uuid::new_v4();

        service.queue_message(session_id, follow_up("first"));
        let queued = service.queue_message(session_id, follow_up("second"));

        assert_eq!(queued.messages.len(), 2);
        assert_eq!(queued.messages[0].message, "first");
        assert_eq!(queued.messages[1].message, "second");
        assert_eq!(queued.data.message, "second");
    }

    #[test]
    fn queued_message_collapses_multiple_follow_ups_in_order() {
        let session_id = Uuid::new_v4();
        let queued = QueuedMessage {
            session_id,
            data: follow_up("second"),
            messages: vec![follow_up("first"), follow_up("second")],
            queued_at: Utc::now(),
        };

        let data = queued.into_follow_up_data();

        assert!(data.message.contains("Follow-up 1:\nfirst"));
        assert!(data.message.contains("Follow-up 2:\nsecond"));
        assert!(
            data.message.find("Follow-up 1").unwrap() < data.message.find("Follow-up 2").unwrap()
        );
    }
}
