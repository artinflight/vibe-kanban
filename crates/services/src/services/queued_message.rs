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
    recovery_holds: Arc<DashMap<Uuid, ()>>,
}

impl QueuedMessageService {
    pub fn new() -> Self {
        Self {
            queue: Arc::new(DashMap::new()),
            recovery_holds: Arc::new(DashMap::new()),
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
        if self.has_queued(session_id) {
            let mut queued = self.queue_message(session_id, data);
            queued.wait_for_capacity = true;
            if let Some(mut entry) = self.queue.get_mut(&session_id) {
                entry.wait_for_capacity = true;
                return entry.clone();
            }
            return queued;
        }
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
        self.recovery_holds.remove(&session_id);
        self.queue.remove(&session_id).map(|(_, v)| v)
    }

    /// Explicit cancellation retires restored input even with scheduling disabled.
    /// Keep the visible batch and recovery hold if durable cancellation fails.
    pub async fn cancel_durable(
        &self,
        pool: &sqlx::SqlitePool,
        session_id: Uuid,
    ) -> Result<Option<QueuedMessage>, sqlx::Error> {
        sqlx::query("DELETE FROM turn_github_sync_user_queue WHERE session_id = ?")
            .bind(session_id)
            .execute(pool)
            .await?;
        Ok(self.cancel_queued(session_id))
    }

    /// Get the queued message for a session (if any)
    pub fn get_queued(&self, session_id: Uuid) -> Option<QueuedMessage> {
        self.queue.get(&session_id).map(|r| r.clone())
    }

    /// Take (remove and return) the queued message for a session.
    /// Used by finalization flow to consume the queued message.
    pub fn take_queued(&self, session_id: Uuid) -> Option<QueuedMessage> {
        if self.recovery_holds.contains_key(&session_id) {
            return None;
        }
        self.queue.remove(&session_id).map(|(_, v)| v)
    }

    /// Take the oldest message waiting for global executor capacity.
    pub fn take_oldest_capacity_queued(&self) -> Option<QueuedMessage> {
        let session_id = self
            .queue
            .iter()
            .filter(|entry| {
                entry.value().wait_for_capacity && !self.recovery_holds.contains_key(entry.key())
            })
            .min_by_key(|entry| entry.value().queued_at)
            .map(|entry| *entry.key())?;

        self.take_queued(session_id)
    }

    /// Snapshot used under shared execution admission for worktree ownership.
    pub fn session_ids(&self) -> Vec<Uuid> {
        self.queue.iter().map(|entry| *entry.key()).collect()
    }

    /// Requeue an admitted batch intact, preserving every message and routing choice.
    pub fn restore_message(&self, queued: QueuedMessage) {
        self.queue.insert(queued.session_id, queued);
    }

    pub async fn persist(
        &self,
        pool: &sqlx::SqlitePool,
        session_id: Uuid,
    ) -> Result<(), sqlx::Error> {
        if let Some(queued) = self.get_queued(session_id) {
            let old_owner: Option<Uuid> = sqlx::query_scalar(
                "SELECT workspace_id FROM turn_github_sync_user_queue WHERE session_id = ?",
            )
            .bind(session_id)
            .fetch_optional(pool)
            .await?;
            let workspace: Uuid = match old_owner {
                Some(owner) => owner,
                None => {
                    sqlx::query_scalar("SELECT workspace_id FROM sessions WHERE id = ?")
                        .bind(session_id)
                        .fetch_one(pool)
                        .await?
                }
            };
            let data = serde_json::to_string(&queued)
                .map_err(|_| sqlx::Error::Protocol("queue serialization failed".into()))?;
            let state = if self.recovery_holds.contains_key(&session_id) {
                "dispatching"
            } else {
                "queued"
            };
            sqlx::query("INSERT INTO turn_github_sync_user_queue VALUES (?, ?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET data = excluded.data, state = excluded.state")
                .bind(session_id).bind(workspace).bind(data).bind(state).execute(pool).await?;
        } else {
            sqlx::query("DELETE FROM turn_github_sync_user_queue WHERE session_id = ?")
                .bind(session_id)
                .execute(pool)
                .await?;
        }
        Ok(())
    }

    pub async fn restore(&self, pool: &sqlx::SqlitePool) -> Result<(), sqlx::Error> {
        let rows: Vec<(Uuid, String, String)> =
            sqlx::query_as("SELECT session_id, data, state FROM turn_github_sync_user_queue")
                .fetch_all(pool)
                .await?;
        for (session_id, data, state) in rows {
            let queued: QueuedMessage = serde_json::from_str(&data).map_err(|_| {
                sqlx::Error::Protocol("invalid durable queue; input retained".into())
            })?;
            if queued.session_id != session_id {
                return Err(sqlx::Error::Protocol("durable queue owner mismatch".into()));
            }
            if state == "dispatching" || !super::admission::automatic_git_sync() {
                self.recovery_holds.insert(session_id, ());
            }
            self.queue.insert(session_id, queued);
        }
        Ok(())
    }

    pub async fn begin_dispatch(
        &self,
        pool: &sqlx::SqlitePool,
        session_id: Uuid,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            "UPDATE turn_github_sync_user_queue SET state = 'dispatching' WHERE session_id = ?",
        )
        .bind(session_id)
        .execute(pool)
        .await?;
        Ok(())
    }

    pub async fn receive(
        pool: &sqlx::SqlitePool,
        session_id: Uuid,
        data: serde_json::Value,
    ) -> Result<Option<Uuid>, sqlx::Error> {
        if !super::admission::automatic_git_sync() {
            return Ok(None);
        }
        let id = Uuid::new_v4();
        let workspace: Uuid = sqlx::query_scalar("SELECT workspace_id FROM sessions WHERE id = ?")
            .bind(session_id)
            .fetch_one(pool)
            .await?;
        sqlx::query(
            "INSERT INTO turn_github_sync_incoming (id, session_id, workspace_id, data) VALUES (?, ?, ?, ?)",
        )
        .bind(id)
        .bind(session_id)
        .bind(workspace)
        .bind(data.to_string())
        .execute(pool)
        .await?;
        Ok(Some(id))
    }

    pub async fn acknowledge(pool: &sqlx::SqlitePool, id: Option<Uuid>) -> Result<(), sqlx::Error> {
        if let Some(id) = id {
            sqlx::query("UPDATE turn_github_sync_incoming SET state = 'handled' WHERE id = ? AND state = 'received'")
                .bind(id)
                .execute(pool)
                .await?;
        }
        Ok(())
    }

    pub async fn pending_incoming(
        pool: &sqlx::SqlitePool,
        workspace: Uuid,
    ) -> Result<Vec<Uuid>, sqlx::Error> {
        sqlx::query_scalar("SELECT id FROM turn_github_sync_incoming WHERE workspace_id = ? AND state = 'received'")
            .bind(workspace).fetch_all(pool).await
    }

    pub async fn dismiss_incoming(
        pool: &sqlx::SqlitePool,
        workspace: Uuid,
        id: Uuid,
    ) -> Result<bool, sqlx::Error> {
        let result = sqlx::query("UPDATE turn_github_sync_incoming SET state = 'dismissed' WHERE id = ? AND state = 'received' AND workspace_id = ?")
            .bind(id).bind(workspace).execute(pool).await?;
        Ok(result.rows_affected() == 1)
    }

    pub async fn pending_user_queue(
        pool: &sqlx::SqlitePool,
        workspace: Uuid,
    ) -> Result<Vec<Uuid>, sqlx::Error> {
        sqlx::query_scalar(
            "SELECT session_id FROM turn_github_sync_user_queue WHERE workspace_id = ?",
        )
        .bind(workspace)
        .fetch_all(pool)
        .await
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

    #[tokio::test]
    async fn restored_batches_preserve_order_and_uncertain_dispatch_never_replays() {
        let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261013120000_turn_github_sync.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        let session = Uuid::new_v4();
        let workspace = Uuid::new_v4();
        sqlx::query("CREATE TABLE sessions (id BLOB PRIMARY KEY, workspace_id BLOB)")
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO sessions VALUES (?, ?)")
            .bind(session)
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        let service = QueuedMessageService::new();
        service.queue_message(session, draft("first user message"));
        service.queue_for_capacity(session, draft("second user message"));
        service.persist(&pool, session).await.unwrap();
        let reopened = QueuedMessageService::new();
        reopened.restore(&pool).await.unwrap();
        let data = reopened.get_queued(session).unwrap();
        assert_eq!(data.messages.len(), 2);
        assert_eq!(data.messages[0].message, "first user message");
        assert_eq!(data.messages[1].message, "second user message");
        if super::super::admission::automatic_git_sync() {
            assert!(
                reopened.take_queued(session).is_some(),
                "known queued input can resume normally"
            );
        } else {
            assert!(
                reopened.take_queued(session).is_none(),
                "disabled rollback holds restored work"
            );
        }
        sqlx::query("DELETE FROM sessions")
            .execute(&pool)
            .await
            .unwrap();
        assert_eq!(
            QueuedMessageService::pending_user_queue(&pool, workspace)
                .await
                .unwrap(),
            vec![session]
        );
        reopened.begin_dispatch(&pool, session).await.unwrap();
        let interrupted = QueuedMessageService::new();
        interrupted.restore(&pool).await.unwrap();
        assert!(interrupted.has_queued(session));
        assert!(interrupted.take_queued(session).is_none());
        assert!(interrupted.take_oldest_capacity_queued().is_none());
        // A failed durable cancellation must keep the held batch visible.
        let unavailable = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        assert!(
            interrupted
                .cancel_durable(&unavailable, session)
                .await
                .is_err()
        );
        assert!(interrupted.has_queued(session));
        assert!(interrupted.take_queued(session).is_none());
        // The same cancellation used by the API must survive another restart,
        // including disabled scheduling and deleted session metadata.
        let cancelled = interrupted
            .cancel_durable(&pool, session)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(cancelled.messages.len(), 2);
        let empty = QueuedMessageService::new();
        empty.restore(&pool).await.unwrap();
        assert!(!empty.has_queued(session));
    }

    #[tokio::test]
    async fn incoming_input_survives_cancelled_handler_and_missing_session_with_exact_scope() {
        let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261013120000_turn_github_sync.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        sqlx::query("CREATE TABLE sessions (id BLOB PRIMARY KEY, workspace_id BLOB)")
            .execute(&pool)
            .await
            .unwrap();
        let session = Uuid::new_v4();
        let workspace = Uuid::new_v4();
        sqlx::query("INSERT INTO sessions VALUES (?, ?)")
            .bind(session)
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        let input = QueuedMessageService::receive(
            &pool,
            session,
            serde_json::json!({"message": "Synthetic private input"}),
        )
        .await
        .unwrap();
        if !super::super::admission::automatic_git_sync() {
            assert!(input.is_none());
            return;
        }
        let input = input.unwrap();
        // Handler never acquired checkpoint admission or dispatched the action.
        sqlx::query("DELETE FROM sessions")
            .execute(&pool)
            .await
            .unwrap();
        assert_eq!(
            QueuedMessageService::pending_incoming(&pool, workspace)
                .await
                .unwrap(),
            vec![input]
        );
        assert!(
            !QueuedMessageService::dismiss_incoming(&pool, Uuid::new_v4(), input)
                .await
                .unwrap()
        );
        assert!(
            QueuedMessageService::dismiss_incoming(&pool, workspace, input)
                .await
                .unwrap()
        );
        assert!(
            QueuedMessageService::pending_incoming(&pool, workspace)
                .await
                .unwrap()
                .is_empty()
        );
        let original: String =
            sqlx::query_scalar("SELECT data FROM turn_github_sync_incoming WHERE id = ?")
                .bind(input)
                .fetch_one(&pool)
                .await
                .unwrap();
        assert!(
            original.contains("Synthetic private input"),
            "explicit dismissal retains the private original"
        );
    }

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
