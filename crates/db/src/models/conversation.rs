//! Durable global supervisor history. No workspace/session chat uses this store.
//!
//! Callers resolve scope from trusted authority/authentication state, never from
//! model arguments. Mutations acquire SQLite's writer lock before reading so
//! idempotency checks and sequence allocation also work across processes.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, SqliteConnection, SqlitePool};
use ts_rs::TS;
use uuid::Uuid;

#[derive(Debug, Clone, Copy)]
pub struct ConversationScope {
    pub authority_id: Uuid,
    pub principal_id: Uuid,
}

impl ConversationScope {
    /// Only for requests already admitted under VK's trusted local boundary.
    /// Signed relay requests require an explicit principal mapping instead.
    pub async fn local_operator(pool: &SqlitePool) -> std::result::Result<Self, sqlx::Error> {
        let (authority_id, principal_id) = sqlx::query_as::<_, (Uuid, Uuid)>(
            "SELECT authority_id, principal_id FROM supervisor_installation_identity WHERE singleton = 1",
        ).fetch_one(pool).await?;
        Ok(Self {
            authority_id,
            principal_id,
        })
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ConversationError {
    #[error("Conversation or message not found in this scope")]
    NotFound,
    #[error("Message identity was reused with different content")]
    IdempotencyConflict,
    #[error("Conversation is archived")]
    Archived,
    #[error("Input must contain text and be at most 64 KiB")]
    InvalidBody,
    #[error("Run lease is expired, cancelled or superseded")]
    StaleLease,
    #[error("Record changed; reload before applying this change")]
    RevisionConflict,
    #[error("Invalid supervisor record or scope")]
    InvalidRecord,
    #[error("Resolve active or uncertain deliveries before deleting supervisor history")]
    ActiveDeliveries,
    #[error(transparent)]
    Database(#[from] sqlx::Error),
}

type Result<T> = std::result::Result<T, ConversationError>;

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct Conversation {
    pub id: Uuid,
    pub authority_id: Uuid,
    pub principal_id: Uuid,
    #[ts(type = "number")]
    pub next_seq: i64,
    #[ts(type = "number")]
    pub revision: i64,
    pub created_at: DateTime<Utc>,
    pub archived_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, TS, sqlx::Type)]
#[serde(rename_all = "snake_case")]
#[sqlx(type_name = "TEXT", rename_all = "snake_case")]
pub enum ConversationInputOrigin {
    Typed,
    Voice,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct AcceptConversationMessage {
    pub client_message_id: Uuid,
    pub body: String,
    pub origin: ConversationInputOrigin,
    pub reply_to_id: Option<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ConversationMessage {
    pub id: Uuid,
    pub conversation_id: Uuid,
    #[ts(type = "number")]
    pub created_seq: i64,
    pub role: String,
    pub origin: String,
    pub body: String,
    #[ts(type = "number")]
    pub revision: i64,
    pub status: String,
    pub reply_to_id: Option<Uuid>,
    pub client_message_id: Option<Uuid>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ConversationRun {
    pub id: Uuid,
    pub conversation_id: Uuid,
    pub input_message_id: Uuid,
    #[ts(type = "number")]
    pub input_revision: i64,
    #[ts(type = "number")]
    pub accepted_seq: i64,
    pub status: String,
    #[ts(type = "number")]
    pub generation: i64,
    pub lease_owner: Option<Uuid>,
    pub lease_until: Option<i64>,
    pub context_manifest: String,
    pub model_config: String,
    pub usage: String,
    pub error: Option<String>,
    pub output_message_id: Option<Uuid>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ConversationEvent {
    pub conversation_id: Uuid,
    #[ts(type = "number")]
    pub seq: i64,
    pub event_id: Uuid,
    #[serde(rename = "type")]
    #[sqlx(rename = "type")]
    pub event_type: String,
    #[ts(type = "number")]
    pub schema_version: i64,
    pub entity_id: Uuid,
    #[ts(type = "number")]
    pub revision: i64,
    // JSON storage is decoded by the API projection, not embedded as a JSON string on the wire.
    pub payload: String,
    pub occurred_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct AcceptedConversationMessage {
    pub message: ConversationMessage,
    pub run: ConversationRun,
}

#[derive(Clone)]
pub struct ConversationStore {
    pool: SqlitePool,
    scope: ConversationScope,
}

impl ConversationStore {
    pub fn new(pool: SqlitePool, scope: ConversationScope) -> Self {
        Self { pool, scope }
    }

    pub async fn resolve(&self) -> Result<Conversation> {
        let mut tx = self.pool.begin().await?;
        sqlx::query(
            "INSERT INTO conversations (id, authority_id, principal_id) VALUES (?, ?, ?) \
             ON CONFLICT(authority_id, principal_id) DO NOTHING",
        )
        .bind(Uuid::new_v4())
        .bind(self.scope.authority_id)
        .bind(self.scope.principal_id)
        .execute(&mut *tx)
        .await?;
        let conversation = sqlx::query_as::<_, Conversation>(
            "SELECT * FROM conversations WHERE authority_id = ? AND principal_id = ?",
        )
        .bind(self.scope.authority_id)
        .bind(self.scope.principal_id)
        .fetch_one(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(conversation)
    }

    pub async fn get(&self, id: Uuid) -> Result<Conversation> {
        sqlx::query_as::<_, Conversation>(
            "SELECT * FROM conversations WHERE id = ? AND authority_id = ? AND principal_id = ?",
        )
        .bind(id)
        .bind(self.scope.authority_id)
        .bind(self.scope.principal_id)
        .fetch_optional(&self.pool)
        .await?
        .ok_or(ConversationError::NotFound)
    }

    async fn lock(&self, conn: &mut SqliteConnection, id: Uuid) -> Result<Conversation> {
        sqlx::query_as::<_, Conversation>(
            "UPDATE conversations SET revision = revision \
             WHERE id = ? AND authority_id = ? AND principal_id = ? RETURNING *",
        )
        .bind(id)
        .bind(self.scope.authority_id)
        .bind(self.scope.principal_id)
        .fetch_optional(conn)
        .await?
        .ok_or(ConversationError::NotFound)
    }

    /// Message, model work and replay events become visible in one commit. A
    /// retry returns the original result even if its run has since completed.
    pub async fn accept(
        &self,
        id: Uuid,
        input: &AcceptConversationMessage,
    ) -> Result<AcceptedConversationMessage> {
        validate_body(&input.body)?;
        let mut tx = self.pool.begin().await?;
        let conversation = self.lock(&mut tx, id).await?;
        let origin = match input.origin {
            ConversationInputOrigin::Typed => "typed",
            ConversationInputOrigin::Voice => "voice",
        };
        if let Some(message) = sqlx::query_as::<_, ConversationMessage>(
            "SELECT * FROM conversation_messages WHERE conversation_id = ? AND client_message_id = ?",
        )
        .bind(id)
        .bind(input.client_message_id)
        .fetch_optional(&mut *tx)
        .await?
        {
            if message.body != input.body
                || message.origin != origin
                || message.reply_to_id != input.reply_to_id
            {
                return Err(ConversationError::IdempotencyConflict);
            }
            let run = sqlx::query_as::<_, ConversationRun>(
                "SELECT * FROM conversation_runs WHERE input_message_id = ?",
            )
            .bind(message.id)
            .fetch_one(&mut *tx)
            .await?;
            tx.commit().await?;
            return Ok(AcceptedConversationMessage { message, run });
        }
        actions::invalidate_pending(&mut tx,id).await?;
        if conversation.archived_at.is_some() {
            return Err(ConversationError::Archived);
        }
        if let Some(reply_to) = input.reply_to_id {
            let exists: bool = sqlx::query_scalar(
                "SELECT EXISTS(SELECT 1 FROM conversation_messages WHERE id = ? AND conversation_id = ?)",
            )
            .bind(reply_to)
            .bind(id)
            .fetch_one(&mut *tx)
            .await?;
            if !exists {
                return Err(ConversationError::NotFound);
            }
        }
        let seq = conversation.next_seq;
        let message = sqlx::query_as::<_, ConversationMessage>(
            "INSERT INTO conversation_messages \
             (id, conversation_id, created_seq, role, origin, body, status, reply_to_id, client_message_id) \
             VALUES (?, ?, ?, 'user', ?, ?, 'accepted', ?, ?) RETURNING *",
        )
        .bind(Uuid::new_v4())
        .bind(id)
        .bind(seq)
        .bind(origin)
        .bind(&input.body)
        .bind(input.reply_to_id)
        .bind(input.client_message_id)
        .fetch_one(&mut *tx)
        .await?;
        let run = sqlx::query_as::<_, ConversationRun>(
            "INSERT INTO conversation_runs \
             (id, conversation_id, input_message_id, accepted_seq, status) \
             VALUES (?, ?, ?, ?, 'pending') RETURNING *",
        )
        .bind(Uuid::new_v4())
        .bind(id)
        .bind(message.id)
        .bind(seq)
        .fetch_one(&mut *tx)
        .await?;
        emit(&mut tx, id, "message.created", message.id, 1, &message).await?;
        emit(&mut tx, id, "run.status", run.id, 1, &run).await?;
        tx.commit().await?;
        Ok(AcceptedConversationMessage { message, run })
    }

    /// Newest page in ascending display order. Cursor is an exclusive event
    /// sequence, so concurrent newer writes cannot shift an older page.
    pub async fn messages(
        &self,
        id: Uuid,
        before_seq: Option<i64>,
        limit: u32,
    ) -> Result<Vec<ConversationMessage>> {
        self.get(id).await?;
        let mut messages = sqlx::query_as::<_, ConversationMessage>(
            "SELECT * FROM conversation_messages WHERE conversation_id = ? AND created_seq < ? \
             ORDER BY created_seq DESC LIMIT ?",
        )
        .bind(id)
        .bind(before_seq.unwrap_or(i64::MAX))
        .bind(limit.clamp(1, 200))
        .fetch_all(&self.pool)
        .await?;
        messages.reverse();
        Ok(messages)
    }

    pub async fn events(
        &self,
        id: Uuid,
        after_seq: i64,
        limit: u32,
    ) -> Result<Vec<ConversationEvent>> {
        self.get(id).await?;
        Ok(sqlx::query_as::<_, ConversationEvent>(
            "SELECT * FROM conversation_events WHERE conversation_id = ? AND seq > ? \
             ORDER BY seq LIMIT ?",
        )
        .bind(id)
        .bind(after_seq.max(0))
        .bind(limit.clamp(1, 200))
        .fetch_all(&self.pool)
        .await?)
    }

    /// One worker per conversation. Expired work becomes visibly interrupted;
    /// its model/tool effects must be reconciled before any explicit retry.
    pub async fn claim_next(&self, id: Uuid, worker: Uuid) -> Result<Option<ConversationRun>> {
        let mut tx = self.pool.begin().await?;
        let conversation = self.lock(&mut tx, id).await?;
        let expired = sqlx::query_as::<_, ConversationRun>(
            "UPDATE conversation_runs SET status = 'interrupted', generation = generation + 1, \
             lease_owner = NULL, lease_until = NULL, error = 'worker_lease_expired' \
             WHERE conversation_id = ? AND status = 'running' AND lease_until <= unixepoch() RETURNING *",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        for run in expired {
            emit(&mut tx, id, "run.status", run.id, run.generation + 1, &run).await?;
        }
        if conversation.archived_at.is_some() {
            tx.commit().await?;
            return Ok(None);
        }
        let run = sqlx::query_as::<_, ConversationRun>(
            "UPDATE conversation_runs SET status = 'running', generation = generation + 1, \
             lease_owner = ?, lease_until = unixepoch() + 60 \
             WHERE id = (SELECT id FROM conversation_runs WHERE conversation_id = ? AND status = 'pending' \
                         ORDER BY accepted_seq LIMIT 1) \
             AND NOT EXISTS(SELECT 1 FROM conversation_runs WHERE conversation_id = ? AND status = 'running') \
             RETURNING *",
        )
        .bind(worker)
        .bind(id)
        .bind(id)
        .fetch_optional(&mut *tx)
        .await?;
        if let Some(run) = &run {
            emit(&mut tx, id, "run.status", run.id, run.generation + 1, run).await?;
        }
        tx.commit().await?;
        Ok(run)
    }

    pub async fn renew(&self, run: &ConversationRun) -> Result<()> {
        let changed = sqlx::query(
            "UPDATE conversation_runs SET lease_until = unixepoch() + 60 \
             WHERE id = ? AND conversation_id = ? AND status = 'running' \
             AND generation = ? AND lease_owner = ? AND lease_until > unixepoch() \
             AND conversation_id IN (SELECT id FROM conversations WHERE authority_id = ? AND principal_id = ?)",
        )
        .bind(run.id)
        .bind(run.conversation_id)
        .bind(run.generation)
        .bind(run.lease_owner)
        .bind(self.scope.authority_id)
        .bind(self.scope.principal_id)
        .execute(&self.pool)
        .await?
        .rows_affected();
        if changed == 0 {
            return Err(ConversationError::StaleLease);
        }
        Ok(())
    }

    pub async fn complete(
        &self,
        leased: &ConversationRun,
        body: &str,
    ) -> Result<ConversationMessage> {
        self.complete_with_evidence(leased, body, &[]).await
    }

    /// Final text and its evidence links appear atomically, so a crash cannot
    /// publish an apparently grounded reply with missing drill-down sources.
    pub async fn complete_with_evidence(
        &self,
        leased: &ConversationRun,
        body: &str,
        evidence_ids: &[Uuid],
    ) -> Result<ConversationMessage> {
        validate_body(body)?;
        if evidence_ids.len() > 32 {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        let conversation = self.lock(&mut tx, leased.conversation_id).await?;
        let run = sqlx::query_as::<_, ConversationRun>(
            "UPDATE conversation_runs SET status = 'completed', generation = generation + 1, \
             lease_owner = NULL, lease_until = NULL \
             WHERE id = ? AND conversation_id = ? AND status = 'running' \
             AND generation = ? AND lease_owner = ? AND lease_until > unixepoch() RETURNING *",
        )
        .bind(leased.id)
        .bind(leased.conversation_id)
        .bind(leased.generation)
        .bind(leased.lease_owner)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or(ConversationError::StaleLease)?;
        let message = sqlx::query_as::<_, ConversationMessage>(
            "INSERT INTO conversation_messages \
             (id, conversation_id, created_seq, role, origin, body, status, reply_to_id) \
             VALUES (?, ?, ?, 'assistant', 'derived', ?, 'final', ?) RETURNING *",
        )
        .bind(Uuid::new_v4())
        .bind(conversation.id)
        .bind(conversation.next_seq)
        .bind(body)
        .bind(run.input_message_id)
        .fetch_one(&mut *tx)
        .await?;
        for evidence_id in evidence_ids {
            let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_evidence WHERE conversation_id = ? AND id = ?)")
                .bind(conversation.id).bind(evidence_id).fetch_one(&mut *tx).await?;
            if !exists {
                return Err(ConversationError::NotFound);
            }
            sqlx::query("INSERT INTO conversation_message_evidence (conversation_id, message_id, evidence_id, relationship) VALUES (?, ?, ?, 'supporting') ON CONFLICT DO NOTHING")
                .bind(conversation.id).bind(message.id).bind(evidence_id).execute(&mut *tx).await?;
        }
        let run = sqlx::query_as::<_, ConversationRun>(
            "UPDATE conversation_runs SET output_message_id = ? WHERE id = ? RETURNING *",
        )
        .bind(message.id)
        .bind(run.id)
        .fetch_one(&mut *tx)
        .await?;
        emit(
            &mut tx,
            conversation.id,
            "message.final",
            message.id,
            1,
            &message,
        )
        .await?;
        emit(
            &mut tx,
            conversation.id,
            "run.status",
            run.id,
            run.generation + 1,
            &run,
        )
        .await?;
        tx.commit().await?;
        Ok(message)
    }

    /// Cancellation fences late completions; it cannot undo dispatched actions.
    pub async fn cancel(&self, id: Uuid, run_id: Uuid) -> Result<ConversationRun> {
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        let changed = sqlx::query_as::<_, ConversationRun>(
            "UPDATE conversation_runs SET status = 'cancelled', generation = generation + 1, \
             lease_owner = NULL, lease_until = NULL WHERE id = ? AND conversation_id = ? \
             AND status IN ('pending', 'running') RETURNING *",
        )
        .bind(run_id)
        .bind(id)
        .fetch_optional(&mut *tx)
        .await?;
        let run = if let Some(run) = changed {
            emit(&mut tx, id, "run.status", run.id, run.generation + 1, &run).await?;
            run
        } else {
            sqlx::query_as::<_, ConversationRun>(
                "SELECT * FROM conversation_runs WHERE id = ? AND conversation_id = ?",
            )
            .bind(run_id)
            .bind(id)
            .fetch_optional(&mut *tx)
            .await?
            .ok_or(ConversationError::NotFound)?
        };
        actions::invalidate_pending(&mut tx,id).await?;
        tx.commit().await?;
        Ok(run)
    }
}

fn validate_body(body: &str) -> Result<()> {
    if body.trim().is_empty() || body.len() > 65536 {
        return Err(ConversationError::InvalidBody);
    }
    Ok(())
}

async fn emit(
    conn: &mut SqliteConnection,
    conversation_id: Uuid,
    event_type: &str,
    entity_id: Uuid,
    revision: i64,
    payload: &impl Serialize,
) -> Result<()> {
    let seq: i64 = sqlx::query_scalar(
        "UPDATE conversations SET next_seq = next_seq + 1, revision = revision + 1 \
         WHERE id = ? RETURNING next_seq - 1",
    )
    .bind(conversation_id)
    .fetch_one(&mut *conn)
    .await?;
    let mut payload =
        serde_json::to_value(payload).map_err(|e| sqlx::Error::Encode(Box::new(e)))?;
    // Replay never needs worker leases or context/model manifests. Keeping only
    // status prevents obsolete context surviving in historical run events.
    if event_type == "run.status" {
        payload = serde_json::json!({"id":payload["id"], "input_message_id":payload["input_message_id"],
            "status":payload["status"], "generation":payload["generation"],
            "output_message_id":payload["output_message_id"], "error":payload["error"]});
    }
    let payload = serde_json::to_string(&payload).map_err(|e| sqlx::Error::Encode(Box::new(e)))?;
    sqlx::query(
        "INSERT INTO conversation_events \
         (conversation_id, seq, event_id, type, entity_id, revision, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
    )
    .bind(conversation_id)
    .bind(seq)
    .bind(Uuid::new_v4())
    .bind(event_type)
    .bind(entity_id)
    .bind(revision)
    .bind(payload)
    .execute(conn)
    .await?;
    Ok(())
}

#[cfg(test)]
mod tests;

pub mod records;
pub mod actions;
mod worker;
