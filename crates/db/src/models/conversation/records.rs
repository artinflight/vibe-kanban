//! Supervisor-owned records. All access is scoped through ConversationStore;
//! source identifiers are validated before retention, never interpreted as paths.
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::types::Json;

use super::*;

#[derive(Debug, Clone, Serialize, Deserialize, TS, PartialEq, Eq)]
#[serde(tag = "kind", content = "id", rename_all = "snake_case")]
pub enum MemoryScope {
    Global,
    Project(Uuid),
    Repository(Uuid),
    Workspace(Uuid),
    Conversation(Uuid),
    Session(Uuid),
}

impl MemoryScope {
    fn key(&self) -> (&'static str, Uuid) {
        match self {
            Self::Global => ("global", Uuid::nil()),
            Self::Project(id) => ("project", *id),
            Self::Repository(id) => ("repository", *id),
            Self::Workspace(id) => ("workspace", *id),
            Self::Conversation(id) => ("conversation", *id),
            Self::Session(id) => ("session", *id),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum EvidenceSource {
    AgentReport { session_id: Uuid, process_id: Uuid },
    Repository { repo_id: Uuid },
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ConversationEvidence {
    pub id: Uuid,
    pub conversation_id: Uuid,
    #[ts(type = "EvidenceSource")]
    pub source: Json<EvidenceSource>,
    pub source_revision: String,
    pub content_hash: String,
    pub availability: String,
    pub raw_report: Option<String>,
    pub captured_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ConversationAction {
    pub id: Uuid,
    pub conversation_id: Uuid,
    pub request_id: Uuid,
    pub run_id: Option<Uuid>,
    pub origin_message_id: Uuid,
    pub intent_kind: String,
    #[ts(type = "unknown")]
    pub payload: Json<Value>,
    pub payload_digest: String,
    #[ts(type = "unknown")]
    pub route_evidence: Json<Value>,
    pub authorisation_source: Option<String>,
    pub state: String,
    #[ts(type = "number")]
    pub revision: i64,
    pub created_at: DateTime<Utc>,
}

/// Created by the policy service after typed tool validation. Persistence alone
/// never authorises execution: new records are always proposals.
#[derive(Debug, Clone)]
pub struct ActionProposal {
    pub request_id: Uuid,
    pub origin_message_id: Uuid,
    pub intent_kind: String,
    pub payload: Value,
    pub route_evidence: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ConversationMemory {
    pub id: Uuid,
    pub conversation_id: Uuid,
    pub scope_kind: String,
    pub scope_id: Uuid,
    pub claim_key: String,
    pub body: String,
    #[ts(type = "MemoryScope[]")]
    pub entity_refs: Json<Vec<MemoryScope>>,
    pub state: String,
    #[ts(type = "number")]
    pub revision: i64,
    pub supersedes_id: Option<Uuid>,
    pub source_message_id: Uuid,
    pub author_kind: String,
    pub valid_until: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct MemoryChange {
    pub scope: MemoryScope,
    pub claim_key: String,
    pub body: String,
    pub entity_refs: Vec<MemoryScope>,
    pub source_message_id: Uuid,
    /// None creates a claim; Some replaces exactly this current revision.
    pub replaces: Option<(Uuid, i64)>,
    /// The caller derives this from a user instruction, never an inferred tool argument.
    pub explicit: bool,
    pub valid_until: Option<DateTime<Utc>>,
}

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct MessageEvidence {
    pub conversation_id: Uuid,
    pub message_id: Uuid,
    pub evidence_id: Uuid,
    pub relationship: String,
}

#[derive(Debug, Serialize, TS, FromRow)]
pub struct MessageEvidenceRef {
    pub evidence_id: Uuid,
    pub relationship: String,
    #[ts(type = "EvidenceSource")]
    pub source: Json<EvidenceSource>,
    pub availability: String,
}

#[derive(Debug, Serialize)]
pub struct ConversationExport {
    pub schema_version: u32,
    pub exported_at: DateTime<Utc>,
    pub conversation: Conversation,
    pub messages: Vec<ConversationMessage>,
    pub runs: Vec<ConversationRun>,
    pub events: Vec<ConversationEvent>,
    pub actions: Vec<ConversationAction>,
    pub evidence: Vec<ConversationEvidence>,
    pub message_evidence: Vec<MessageEvidence>,
    pub memories: Vec<ConversationMemory>,
    pub deliveries: Vec<super::super::agent_delivery::AgentDelivery>,
}

impl ConversationStore {
    pub async fn message_evidence(
        &self,
        id: Uuid,
        message_id: Uuid,
    ) -> Result<Vec<MessageEvidenceRef>> {
        self.get(id).await?;
        let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_messages WHERE conversation_id = ? AND id = ?)").bind(id).bind(message_id).fetch_one(&self.pool).await?;
        if !exists {
            return Err(ConversationError::NotFound);
        }
        Ok(sqlx::query_as("SELECT l.evidence_id, l.relationship, e.source, e.availability FROM conversation_message_evidence l JOIN conversation_evidence e ON e.id = l.evidence_id AND e.conversation_id = l.conversation_id WHERE l.conversation_id = ? AND l.message_id = ? ORDER BY e.captured_at, e.id").bind(id).bind(message_id).fetch_all(&self.pool).await?)
    }

    pub async fn list_memories(&self, id: Uuid) -> Result<Vec<ConversationMemory>> {
        self.get(id).await?;
        Ok(sqlx::query_as("SELECT * FROM conversation_memory WHERE conversation_id = ? AND state IN ('active','proposed') ORDER BY created_at DESC LIMIT 200").bind(id).fetch_all(&self.pool).await?)
    }

    async fn validate_scope(
        &self,
        conn: &mut SqliteConnection,
        conversation_id: Uuid,
        scope: &MemoryScope,
    ) -> Result<()> {
        let (query, id) = match scope {
            MemoryScope::Global => return Ok(()),
            MemoryScope::Conversation(id) => {
                return if *id == conversation_id {
                    Ok(())
                } else {
                    Err(ConversationError::NotFound)
                };
            }
            MemoryScope::Project(id) => ("SELECT EXISTS(SELECT 1 FROM projects WHERE id = ?)", id),
            MemoryScope::Repository(id) => ("SELECT EXISTS(SELECT 1 FROM repos WHERE id = ?)", id),
            MemoryScope::Workspace(id) => {
                ("SELECT EXISTS(SELECT 1 FROM workspaces WHERE id = ?)", id)
            }
            MemoryScope::Session(id) => ("SELECT EXISTS(SELECT 1 FROM sessions WHERE id = ?)", id),
        };
        // Local authority only. Remote references require a mapped, authorised
        // resolver rather than treating a cloud UUID as a local entity.
        if !sqlx::query_scalar::<_, bool>(query)
            .bind(id)
            .fetch_one(conn)
            .await?
        {
            return Err(ConversationError::NotFound);
        }
        Ok(())
    }

    async fn check_message(conn: &mut SqliteConnection, id: Uuid, message: Uuid) -> Result<()> {
        if !sqlx::query_scalar::<_, bool>("SELECT EXISTS(SELECT 1 FROM conversation_messages WHERE conversation_id = ? AND id = ? AND role = 'user')")
            .bind(id).bind(message).fetch_one(conn).await? {
            return Err(ConversationError::NotFound);
        }
        Ok(())
    }

    /// Record a model proposal only while its originating generation is live.
    /// Retry identities are checked before returning an existing immutable action.
    pub async fn propose_action(
        &self,
        run: &ConversationRun,
        proposal: &ActionProposal,
    ) -> Result<ConversationAction> {
        validate_body(&proposal.intent_kind)?;
        if proposal.intent_kind.len() > 100
            || serde_json::to_vec(&proposal.payload).map_err(encode)?.len() > 65536
            || serde_json::to_vec(&proposal.route_evidence)
                .map_err(encode)?
                .len()
                > 65536
        {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, run.conversation_id).await?;
        let live: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_runs WHERE id = ? AND conversation_id = ? AND status = 'running' AND generation = ? AND lease_owner = ? AND lease_until > unixepoch())")
            .bind(run.id).bind(run.conversation_id).bind(run.generation).bind(run.lease_owner).fetch_one(&mut *tx).await?;
        if !live {
            return Err(ConversationError::StaleLease);
        }
        Self::check_message(&mut tx, run.conversation_id, proposal.origin_message_id).await?;
        if proposal.origin_message_id != run.input_message_id {
            return Err(ConversationError::InvalidRecord);
        }
        let digest = hash(&serde_json::to_vec(&proposal.payload).map_err(encode)?);
        if let Some(old) = sqlx::query_as::<_, ConversationAction>(
            "SELECT * FROM conversation_actions WHERE conversation_id = ? AND request_id = ?",
        )
        .bind(run.conversation_id)
        .bind(proposal.request_id)
        .fetch_optional(&mut *tx)
        .await?
        {
            if old.run_id != Some(run.id)
                || old.origin_message_id != proposal.origin_message_id
                || old.intent_kind != proposal.intent_kind
                || old.payload.0 != proposal.payload
                || old.route_evidence.0 != proposal.route_evidence
            {
                return Err(ConversationError::IdempotencyConflict);
            }
            tx.commit().await?;
            return Ok(old);
        }
        let action = sqlx::query_as::<_, ConversationAction>("INSERT INTO conversation_actions (id, conversation_id, request_id, run_id, origin_message_id, intent_kind, payload, payload_digest, route_evidence, state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed') RETURNING *")
            .bind(Uuid::new_v4()).bind(run.conversation_id).bind(proposal.request_id).bind(run.id).bind(proposal.origin_message_id)
            .bind(&proposal.intent_kind).bind(Json(&proposal.payload)).bind(digest).bind(Json(&proposal.route_evidence)).fetch_one(&mut *tx).await?;
        emit(
            &mut tx,
            run.conversation_id,
            "action.status",
            action.id,
            action.revision,
            &action,
        )
        .await?;
        tx.commit().await?;
        Ok(action)
    }

    pub async fn actions(&self, id: Uuid) -> Result<Vec<ConversationAction>> {
        self.get(id).await?;
        Ok(sqlx::query_as("SELECT * FROM conversation_actions WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 200").bind(id).fetch_all(&self.pool).await?)
    }

    /// Retain the report actually used, including all whitespace and technical
    /// evidence. An immutable revision cannot silently change underneath a summary.
    pub async fn retain_evidence(
        &self,
        id: Uuid,
        source: &EvidenceSource,
        revision: &str,
        report: &str,
    ) -> Result<ConversationEvidence> {
        if revision.trim().is_empty() || revision.len() > 256 || report.len() > 1024 * 1024 {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        match source {
            EvidenceSource::AgentReport {
                session_id,
                process_id,
            } => {
                let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes WHERE id = ? AND session_id = ?)")
                    .bind(process_id).bind(session_id).fetch_one(&mut *tx).await?;
                if !exists {
                    return Err(ConversationError::NotFound);
                }
            }
            EvidenceSource::Repository { repo_id } => {
                self.validate_scope(&mut tx, id, &MemoryScope::Repository(*repo_id))
                    .await?
            }
        }
        let digest = hash(report.as_bytes());
        if let Some(old) = sqlx::query_as::<_, ConversationEvidence>("SELECT * FROM conversation_evidence WHERE conversation_id = ? AND source = ? AND source_revision = ?")
            .bind(id).bind(Json(source)).bind(revision).fetch_optional(&mut *tx).await? {
            if old.content_hash != digest { return Err(ConversationError::IdempotencyConflict); }
            tx.commit().await?;
            return Ok(old);
        }
        let record = sqlx::query_as::<_, ConversationEvidence>("INSERT INTO conversation_evidence (id, conversation_id, source, source_revision, content_hash, availability, raw_report) VALUES (?, ?, ?, ?, ?, 'retained', ?) RETURNING *")
            .bind(Uuid::new_v4()).bind(id).bind(Json(source)).bind(revision).bind(digest).bind(report).fetch_one(&mut *tx).await?;
        emit(&mut tx, id, "evidence.updated", record.id, 1, &json!({"id":record.id,"source":source,"source_revision":revision,"content_hash":record.content_hash,"availability":"retained"})).await?;
        tx.commit().await?;
        Ok(record)
    }

    pub async fn evidence(&self, id: Uuid, evidence_id: Uuid) -> Result<ConversationEvidence> {
        self.get(id).await?;
        sqlx::query_as("SELECT * FROM conversation_evidence WHERE conversation_id = ? AND id = ?")
            .bind(id)
            .bind(evidence_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(ConversationError::NotFound)
    }

    pub async fn link_evidence(
        &self,
        id: Uuid,
        message_id: Uuid,
        evidence_id: Uuid,
        relationship: &str,
    ) -> Result<()> {
        if !matches!(relationship, "summarised" | "quoted" | "supporting") {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_messages m JOIN conversation_evidence e ON e.conversation_id = m.conversation_id WHERE m.conversation_id = ? AND m.id = ? AND e.id = ?)")
            .bind(id).bind(message_id).bind(evidence_id).fetch_one(&mut *tx).await?;
        if !exists {
            return Err(ConversationError::NotFound);
        }
        let changed = sqlx::query("INSERT INTO conversation_message_evidence (conversation_id, message_id, evidence_id, relationship) VALUES (?, ?, ?, ?) ON CONFLICT(message_id,evidence_id) DO NOTHING")
            .bind(id).bind(message_id).bind(evidence_id).bind(relationship).execute(&mut *tx).await?.rows_affected();
        if changed > 0 {
            emit(&mut tx, id, "evidence.linked", message_id, 1, &json!({"message_id":message_id,"evidence_id":evidence_id,"relationship":relationship})).await?;
        }
        tx.commit().await?;
        Ok(())
    }

    /// A user correction supersedes one exact revision. Inferred changes are
    /// proposals; they cannot replace a user's active instruction.
    pub async fn put_memory(&self, id: Uuid, change: &MemoryChange) -> Result<ConversationMemory> {
        validate_body(&change.body)?;
        if change.claim_key.trim().is_empty()
            || change.claim_key.len() > 200
            || change.entity_refs.len() > 16
            || change.valid_until.is_some_and(|time| time <= Utc::now())
        {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        self.validate_scope(&mut tx, id, &change.scope).await?;
        for scope in &change.entity_refs {
            self.validate_scope(&mut tx, id, scope).await?;
        }
        Self::check_message(&mut tx, id, change.source_message_id).await?;
        let (kind, scope_id) = change.scope.key();
        let forgotten: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_forgotten_memory WHERE conversation_id = ? AND source_message_id = ? AND claim_key = ? AND scope_kind = ? AND scope_id = ?)")
            .bind(id).bind(change.source_message_id).bind(&change.claim_key).bind(kind).bind(scope_id).fetch_one(&mut *tx).await?;
        if forgotten {
            return Err(ConversationError::InvalidRecord);
        }
        let current = sqlx::query_as::<_, ConversationMemory>("SELECT * FROM conversation_memory WHERE conversation_id = ? AND scope_kind = ? AND scope_id = ? AND claim_key = ? AND state IN ('active','proposed')")
            .bind(id).bind(kind).bind(scope_id).bind(&change.claim_key).fetch_optional(&mut *tx).await?;
        let revision = match (&current, change.replaces) {
            (None, None) => 1,
            (Some(old), Some((old_id, revision)))
                if old.id == old_id && old.revision == revision =>
            {
                if !change.explicit && old.state == "active" {
                    return Err(ConversationError::InvalidRecord);
                }
                sqlx::query("UPDATE conversation_memory SET state = 'superseded' WHERE id = ?")
                    .bind(old.id)
                    .execute(&mut *tx)
                    .await?;
                old.revision + 1
            }
            _ => return Err(ConversationError::RevisionConflict),
        };
        let record = sqlx::query_as::<_, ConversationMemory>("INSERT INTO conversation_memory (id, conversation_id, scope_kind, scope_id, claim_key, body, entity_refs, state, revision, supersedes_id, source_message_id, author_kind, valid_until) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *")
            .bind(Uuid::new_v4()).bind(id).bind(kind).bind(scope_id).bind(&change.claim_key).bind(&change.body).bind(Json(&change.entity_refs))
            .bind(if change.explicit { "active" } else { "proposed" }).bind(revision).bind(change.replaces.map(|(id,_)|id)).bind(change.source_message_id)
            .bind(if change.explicit { "user" } else { "inferred" }).bind(change.valid_until).fetch_one(&mut *tx).await?;
        invalidate_context(&mut tx, id).await?;
        emit(
            &mut tx,
            id,
            "memory.changed",
            record.id,
            record.revision,
            &record,
        )
        .await?;
        tx.commit().await?;
        Ok(record)
    }

    /// Caller provides the narrow context resolved for this turn. No entity is
    /// implicitly expanded to its entire project. Linked entities must all be
    /// present, preventing unrelated knowledge from leaking across contexts.
    pub async fn memories(
        &self,
        id: Uuid,
        scopes: &[MemoryScope],
        budget_bytes: usize,
    ) -> Result<Vec<ConversationMemory>> {
        self.get(id).await?;
        if scopes.len() > 32 {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        let mut result = Vec::new();
        let mut remaining = budget_bytes.min(32768);
        // More specific scopes precede the global defaults. The consumer sees
        // conflicting claim keys explicitly; this layer never silently blends them.
        let mut requested = scopes.to_vec();
        requested.retain(|scope| *scope != MemoryScope::Global);
        requested.push(MemoryScope::Global);
        for scope in &requested {
            self.validate_scope(&mut tx, id, scope).await?;
            let (kind, scope_id) = scope.key();
            let records = sqlx::query_as::<_, ConversationMemory>("SELECT * FROM conversation_memory WHERE conversation_id = ? AND scope_kind = ? AND scope_id = ? AND state = 'active' AND (valid_until IS NULL OR julianday(valid_until) > julianday('now')) ORDER BY created_at DESC LIMIT 200")
                .bind(id).bind(kind).bind(scope_id).fetch_all(&mut *tx).await?;
            for record in records {
                if record.body.len() <= remaining
                    && !result
                        .iter()
                        .any(|old: &ConversationMemory| old.id == record.id)
                    && record
                        .entity_refs
                        .iter()
                        .all(|reference| requested.contains(reference))
                {
                    remaining -= record.body.len();
                    result.push(record);
                }
            }
        }
        tx.commit().await?;
        Ok(result)
    }

    /// Erase the claim's revisions and prevent automatic re-extraction. The
    /// original user conversation remains history until separately deleted.
    pub async fn forget_memory(&self, id: Uuid, memory_id: Uuid, revision: i64) -> Result<()> {
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        let current = sqlx::query_as::<_, ConversationMemory>("SELECT * FROM conversation_memory WHERE conversation_id = ? AND id = ? AND state IN ('active','proposed') AND revision = ?")
            .bind(id).bind(memory_id).bind(revision).fetch_optional(&mut *tx).await?.ok_or(ConversationError::RevisionConflict)?;
        let previous = sqlx::query_as::<_, ConversationMemory>("SELECT * FROM conversation_memory WHERE conversation_id = ? AND scope_kind = ? AND scope_id = ? AND claim_key = ?")
            .bind(id).bind(&current.scope_kind).bind(current.scope_id).bind(&current.claim_key).fetch_all(&mut *tx).await?;
        for memory in previous {
            sqlx::query("INSERT OR IGNORE INTO conversation_forgotten_memory (conversation_id,source_message_id,claim_key,scope_kind,scope_id) VALUES (?, ?, ?, ?, ?)")
                .bind(id).bind(memory.source_message_id).bind(&memory.claim_key).bind(&memory.scope_kind).bind(memory.scope_id).execute(&mut *tx).await?;
            sqlx::query("UPDATE conversation_memory SET body = '', entity_refs = '[]', state = 'retracted', revision = revision + 1 WHERE id = ?").bind(memory.id).execute(&mut *tx).await?;
            sqlx::query("UPDATE conversation_events SET payload = '{}', type = 'record.redacted' WHERE conversation_id = ? AND entity_id = ?")
                .bind(id).bind(memory.id).execute(&mut *tx).await?;
        }
        // Contexts contain references, never the sole copy of knowledge. Clear
        // any cached context immediately, including in-flight manifests.
        invalidate_context(&mut tx, id).await?;
        sqlx::query(
            "UPDATE conversation_runs SET context_manifest = '{}' WHERE conversation_id = ?",
        )
        .bind(id)
        .execute(&mut *tx)
        .await?;
        // Fence a model already holding the forgotten preference. Accepted
        // actions remain independently visible; this cannot unsend instructions.
        let interrupted = sqlx::query_as::<_, ConversationRun>("UPDATE conversation_runs SET status = 'interrupted', generation = generation + 1, lease_owner = NULL, lease_until = NULL, error = 'memory_forgotten' WHERE conversation_id = ? AND status = 'running' RETURNING *")
            .bind(id).fetch_all(&mut *tx).await?;
        for run in interrupted {
            emit(&mut tx, id, "run.status", run.id, run.generation + 1, &run).await?;
        }
        emit(
            &mut tx,
            id,
            "memory.forgotten",
            memory_id,
            revision + 1,
            &json!({"id":memory_id}),
        )
        .await?;
        tx.commit().await?;
        Ok(())
    }

    /// A consistent snapshot; only owned supervisor records and their deliveries
    /// are exported. Existing raw session history stays in its original store.
    pub async fn export(&self, id: Uuid) -> Result<ConversationExport> {
        let mut tx = self.pool.begin().await?;
        let conversation = sqlx::query_as::<_, Conversation>(
            "SELECT * FROM conversations WHERE id = ? AND authority_id = ? AND principal_id = ?",
        )
        .bind(id)
        .bind(self.scope.authority_id)
        .bind(self.scope.principal_id)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or(ConversationError::NotFound)?;
        let messages = sqlx::query_as(
            "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY created_seq",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        let runs = sqlx::query_as(
            "SELECT * FROM conversation_runs WHERE conversation_id = ? ORDER BY accepted_seq",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        let events = sqlx::query_as(
            "SELECT * FROM conversation_events WHERE conversation_id = ? ORDER BY seq",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        let actions = sqlx::query_as(
            "SELECT * FROM conversation_actions WHERE conversation_id = ? ORDER BY created_at",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        let evidence = sqlx::query_as(
            "SELECT * FROM conversation_evidence WHERE conversation_id = ? ORDER BY captured_at",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        let message_evidence =
            sqlx::query_as("SELECT * FROM conversation_message_evidence WHERE conversation_id = ?")
                .bind(id)
                .fetch_all(&mut *tx)
                .await?;
        let memories = sqlx::query_as(
            "SELECT * FROM conversation_memory WHERE conversation_id = ? ORDER BY created_at",
        )
        .bind(id)
        .fetch_all(&mut *tx)
        .await?;
        let deliveries = sqlx::query_as("SELECT * FROM agent_deliveries WHERE source_kind = 'supervisor' AND action_id IN (SELECT id FROM conversation_actions WHERE conversation_id = ?) ORDER BY position").bind(id).fetch_all(&mut *tx).await?;
        tx.commit().await?;
        Ok(ConversationExport {
            schema_version: 1,
            exported_at: Utc::now(),
            conversation,
            messages,
            runs,
            events,
            actions,
            evidence,
            message_evidence,
            memories,
            deliveries,
        })
    }

    /// Revision-checked deletion of all supervisor content for this conversation.
    /// Keep only sequence tombstones, so connected clients cannot replay erased
    /// text. This neither stops agents nor deletes their original workspace logs.
    pub async fn delete_content(&self, id: Uuid, expected_revision: i64) -> Result<Conversation> {
        let mut tx = self.pool.begin().await?;
        let conversation = self.lock(&mut tx, id).await?;
        if conversation.revision != expected_revision {
            return Err(ConversationError::RevisionConflict);
        }
        let active: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM agent_deliveries WHERE source_kind = 'supervisor' AND action_id IN (SELECT id FROM conversation_actions WHERE conversation_id = ?) AND state NOT IN ('completed','failed','cancelled')) OR EXISTS(SELECT 1 FROM conversation_actions WHERE conversation_id = ? AND state IN ('dispatching','unknown_delivery'))")
            .bind(id).bind(id).fetch_one(&mut *tx).await?;
        if active {
            return Err(ConversationError::ActiveDeliveries);
        }
        sqlx::query("DELETE FROM agent_deliveries WHERE source_kind = 'supervisor' AND action_id IN (SELECT id FROM conversation_actions WHERE conversation_id = ?)").bind(id).execute(&mut *tx).await?;
        for table in [
            "conversation_message_evidence",
            "conversation_evidence",
            "conversation_actions",
            "conversation_forgotten_memory",
            "conversation_memory",
            "conversation_context",
            "conversation_runs",
        ] {
            // Table identifiers are a closed application-owned list.
            sqlx::query(&format!("DELETE FROM {table} WHERE conversation_id = ?"))
                .bind(id)
                .execute(&mut *tx)
                .await?;
        }
        // Replies are self-references; clear them before removing the messages.
        sqlx::query(
            "UPDATE conversation_messages SET reply_to_id = NULL WHERE conversation_id = ?",
        )
        .bind(id)
        .execute(&mut *tx)
        .await?;
        sqlx::query("DELETE FROM conversation_messages WHERE conversation_id = ?")
            .bind(id)
            .execute(&mut *tx)
            .await?;
        sqlx::query("UPDATE conversation_events SET type = 'record.redacted', payload = '{}', entity_id = conversation_id WHERE conversation_id = ?").bind(id).execute(&mut *tx).await?;
        emit(
            &mut tx,
            id,
            "history.cleared",
            id,
            conversation.revision + 1,
            &json!({"id":id}),
        )
        .await?;
        let result = sqlx::query_as("SELECT * FROM conversations WHERE id = ?")
            .bind(id)
            .fetch_one(&mut *tx)
            .await?;
        tx.commit().await?;
        Ok(result)
    }
}

fn encode(error: serde_json::Error) -> sqlx::Error {
    sqlx::Error::Encode(Box::new(error))
}
fn hash(content: &[u8]) -> String {
    format!("{:x}", Sha256::digest(content))
}
async fn invalidate_context(conn: &mut SqliteConnection, id: Uuid) -> Result<()> {
    sqlx::query("UPDATE conversation_context SET summary = '', source_versions = '{}', revision = revision + 1, invalidated_at = datetime('now','subsec') WHERE conversation_id = ?")
        .bind(id).execute(conn).await?;
    Ok(())
}

#[cfg(test)]
mod tests;
