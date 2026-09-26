//! Lease-checked worker operations. Provider secrets and raw tool transcripts do
//! not belong in run metadata; callers store source IDs/versions and usage only.
use serde_json::Value;

use super::*;

impl ConversationStore {
    /// Bounded status pages use the input sequence, matching message history.
    pub async fn runs(
        &self,
        id: Uuid,
        before_seq: Option<i64>,
        limit: u32,
    ) -> Result<Vec<ConversationRun>> {
        self.get(id).await?;
        Ok(sqlx::query_as("SELECT * FROM conversation_runs WHERE conversation_id = ? AND (? IS NULL OR accepted_seq < ?) ORDER BY accepted_seq DESC LIMIT ?")
            .bind(id).bind(before_seq).bind(before_seq).bind(limit.clamp(1,200))
            .fetch_all(&self.pool).await?)
    }

    pub async fn run(&self, id: Uuid, run_id: Uuid) -> Result<ConversationRun> {
        self.get(id).await?;
        sqlx::query_as("SELECT * FROM conversation_runs WHERE conversation_id = ? AND id = ?")
            .bind(id)
            .bind(run_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(ConversationError::NotFound)
    }

    pub async fn run_input(&self, run: &ConversationRun) -> Result<ConversationMessage> {
        self.get(run.conversation_id).await?;
        sqlx::query_as("SELECT * FROM conversation_messages WHERE conversation_id = ? AND id = ? AND revision = ?")
            .bind(run.conversation_id).bind(run.input_message_id).bind(run.input_revision)
            .fetch_optional(&self.pool).await?.ok_or(ConversationError::NotFound)
    }

    /// Include replies to earlier turns even if this input arrived while the
    /// preceding run was still working. Never include a later user instruction.
    pub async fn run_history(&self, run: &ConversationRun) -> Result<Vec<ConversationMessage>> {
        self.get(run.conversation_id).await?;
        let mut history = sqlx::query_as::<_, ConversationMessage>(
            "SELECT m.* FROM conversation_messages m WHERE m.conversation_id = ? AND \
             ((m.role = 'user' AND m.created_seq < ?) OR (m.role = 'assistant' AND EXISTS \
             (SELECT 1 FROM conversation_messages p WHERE p.conversation_id = m.conversation_id \
              AND p.id = m.reply_to_id AND p.created_seq < ?))) ORDER BY m.created_seq DESC LIMIT 40")
            .bind(run.conversation_id).bind(run.accepted_seq).bind(run.accepted_seq)
            .fetch_all(&self.pool).await?;
        // Keep whole messages, never hide truncation inside a user's instruction.
        let mut bytes = 0;
        history.retain(|message| {
            bytes += message.body.len();
            bytes <= 65536
        });
        history.reverse();
        Ok(history)
    }

    pub async fn record_run_context(
        &self,
        run: &ConversationRun,
        manifest: &Value,
        model: &Value,
        usage: &Value,
    ) -> Result<()> {
        let manifest =
            serde_json::to_string(manifest).map_err(|_| ConversationError::InvalidRecord)?;
        let model = serde_json::to_string(model).map_err(|_| ConversationError::InvalidRecord)?;
        let usage = serde_json::to_string(usage).map_err(|_| ConversationError::InvalidRecord)?;
        if manifest.len() > 65536 || model.len() > 4096 || usage.len() > 4096 {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, run.conversation_id).await?;
        self.check_lease(&mut tx, run).await?;
        sqlx::query("UPDATE conversation_runs SET context_manifest = ?, model_config = ?, usage = ? WHERE id = ?")
            .bind(manifest).bind(model).bind(usage).bind(run.id).execute(&mut *tx).await?;
        tx.commit().await?;
        Ok(())
    }

    pub(super) async fn check_lease(
        &self,
        conn: &mut SqliteConnection,
        run: &ConversationRun,
    ) -> Result<()> {
        let live: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_runs WHERE id = ? AND conversation_id = ? AND status = 'running' AND generation = ? AND lease_owner = ? AND lease_until > unixepoch())")
            .bind(run.id).bind(run.conversation_id).bind(run.generation).bind(run.lease_owner).fetch_one(conn).await?;
        if live {
            Ok(())
        } else {
            Err(ConversationError::StaleLease)
        }
    }

    /// Persist a safe error code, never a provider response body containing user
    /// data or credentials. A terminal failure does not enqueue an automatic retry.
    pub async fn fail_run(&self, run: &ConversationRun, code: &str) -> Result<()> {
        if code.is_empty()
            || code.len() > 80
            || !code.bytes().all(|b| b.is_ascii_lowercase() || b == b'_')
        {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, run.conversation_id).await?;
        self.check_lease(&mut tx, run).await?;
        let failed = sqlx::query_as::<_, ConversationRun>("UPDATE conversation_runs SET status = 'failed', error = ?, generation = generation + 1, lease_owner = NULL, lease_until = NULL WHERE id = ? RETURNING *")
            .bind(code).bind(run.id).fetch_one(&mut *tx).await?;
        emit(
            &mut tx,
            run.conversation_id,
            "run.status",
            run.id,
            failed.generation + 1,
            &failed,
        )
        .await?;
        super::actions::invalidate_pending(&mut tx, run.conversation_id).await?;
        tx.commit().await?;
        Ok(())
    }
}
