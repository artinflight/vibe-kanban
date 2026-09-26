//! Supervisor action policy persistence. Runtime/model code supplies a semantic
//! assessment; this layer enforces ownership, payload binding, scope, expiry,
//! cancellation and atomic hand-off to the existing delivery ledger.
use executors::{actions::ExecutorActionType, executors::BaseCodingAgent, profile::ExecutorConfig};
use serde_json::json;
use sha2::{Digest, Sha256};
use sqlx::types::Json;

use super::{
    records::{ActionProposal, ConversationAction},
    *,
};
use crate::models::{
    agent_delivery::AgentDelivery, execution_process::ExecutionProcess, scratch::DraftFollowUpData,
};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS)]
#[serde(deny_unknown_fields)]
pub struct MessageTarget {
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub workspace_name: String,
    pub session_name: Option<String>,
    pub branch: String,
    pub executor_config: ExecutorConfig,
    pub version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
#[serde(deny_unknown_fields)]
pub struct AgentMessage {
    pub message: String,
    pub targets: Vec<MessageTarget>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MessageImpact {
    Ordinary,
    Consequential,
    Unclear,
    /// Native-goal activation, tool approval or another dedicated control cannot
    /// be smuggled through natural-language messages, even after confirmation.
    UnsupportedControl,
}

/// Trusted policy assessment of the user's request and exact proposed message.
/// It must not be accepted from an HTTP client or copied from an agent report.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MessageAssessment {
    pub authorised_by_user: bool,
    pub impact: MessageImpact,
    pub recipients_explicit: bool,
    pub explanation: String,
}

#[derive(Debug, Serialize, Deserialize, FromRow, TS)]
pub struct ActionConfirmation {
    pub id: Uuid,
    pub conversation_id: Uuid,
    pub action_id: Uuid,
    pub principal_id: Uuid,
    pub payload_digest: String,
    #[ts(type = "number")]
    pub action_revision: i64,
    #[ts(type = "number")]
    pub expires_at: i64,
    pub state: String,
    pub answered_message_id: Option<Uuid>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug)]
pub struct ActionAdmission {
    pub action: ConversationAction,
    pub deliveries: Vec<AgentDelivery>,
    /// Only the transaction that admitted these attempts may send their RPCs.
    /// Replays contain no attempts, even if an old receipt is still in flight.
    pub steering_attempts: Vec<AgentDelivery>,
}

impl ConversationStore {
    pub async fn prepare_agent_message(
        &self,
        id: Uuid,
        message: String,
        sessions: &[Uuid],
    ) -> Result<AgentMessage> {
        self.get(id).await?;
        validate_body(&message)?;
        if sessions.is_empty() || sessions.len() > 20 {
            return Err(ConversationError::InvalidRecord);
        }
        let mut unique = std::collections::HashSet::new();
        let mut tx = self.pool.begin().await?;
        let mut targets = Vec::new();
        for session in sessions {
            if !unique.insert(*session) {
                return Err(ConversationError::InvalidRecord);
            }
            targets.push(target(&mut tx, *session).await?);
        }
        tx.commit().await?;
        Ok(AgentMessage { message, targets })
    }

    pub async fn propose_agent_message(
        &self,
        run: &ConversationRun,
        request_id: Uuid,
        message: &AgentMessage,
        assessment: &MessageAssessment,
    ) -> Result<ConversationAction> {
        validate_body(&message.message)?;
        if message.targets.is_empty()
            || message.targets.len() > 20
            || assessment.explanation.len() > 4096
        {
            return Err(ConversationError::InvalidRecord);
        }
        let mut sessions = std::collections::HashSet::new();
        for t in &message.targets {
            if !sessions.insert(t.session_id) {
                return Err(ConversationError::InvalidRecord);
            }
        }
        // Generic proposal persistence handles immutable request identity and the
        // originating generation. No execution is authorised by this write alone.
        self.propose_action(
            run,
            &ActionProposal {
                request_id,
                origin_message_id: run.input_message_id,
                intent_kind: "agent_message".into(),
                payload: json!(message),
                route_evidence: json!({"assessment":assessment}),
            },
        )
        .await?;
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, run.conversation_id).await?;
        self.check_lease(&mut tx, run).await?;
        let action: ConversationAction = sqlx::query_as(
            "SELECT * FROM conversation_actions WHERE conversation_id=? AND request_id=?",
        )
        .bind(run.conversation_id)
        .bind(request_id)
        .fetch_one(&mut *tx)
        .await?;
        if action.state != "proposed" {
            tx.commit().await?;
            return Ok(action);
        }
        // Re-read after semantic classification: names, relationships and executor
        // selection may have changed while a model was thinking.
        for t in &message.targets {
            if target(&mut tx, t.session_id).await? != *t {
                return Err(ConversationError::RevisionConflict);
            }
        }
        let state = if !assessment.authorised_by_user
            || assessment.impact == MessageImpact::UnsupportedControl
        {
            "rejected"
        } else if assessment.impact != MessageImpact::Ordinary
            || (message.targets.len() > 5 && !assessment.recipients_explicit)
        {
            let inserted = sqlx::query("INSERT INTO conversation_confirmations (id,conversation_id,action_id,principal_id,payload_digest,action_revision,expires_at,state) VALUES (?,?,?,?,?,?,unixepoch()+300,'pending') ON CONFLICT(action_id) DO NOTHING")
                .bind(Uuid::new_v4()).bind(run.conversation_id).bind(action.id).bind(self.scope.principal_id).bind(&action.payload_digest).bind(action.revision)
                .execute(&mut *tx).await?.rows_affected();
            if inserted > 0 {
                emit(
                    &mut tx,
                    run.conversation_id,
                    "confirmation.requested",
                    action.id,
                    action.revision,
                    &json!({"action_id":action.id}),
                )
                .await?;
            }
            tx.commit().await?;
            return Ok(action);
        } else {
            "approved"
        };
        let updated = transition(
            &mut tx,
            &action,
            state,
            Some(if state == "approved" {
                "user_request"
            } else {
                "policy_rejected"
            }),
        )
        .await?;
        tx.commit().await?;
        Ok(updated)
    }

    pub async fn action_for_request(
        &self,
        id: Uuid,
        request_id: Uuid,
    ) -> Result<Option<ConversationAction>> {
        self.get(id).await?;
        Ok(sqlx::query_as(
            "SELECT * FROM conversation_actions WHERE conversation_id=? AND request_id=?",
        )
        .bind(id)
        .bind(request_id)
        .fetch_optional(&self.pool)
        .await?)
    }

    pub async fn action(&self, id: Uuid, action_id: Uuid) -> Result<ConversationAction> {
        self.get(id).await?;
        sqlx::query_as("SELECT * FROM conversation_actions WHERE conversation_id=? AND id=?")
            .bind(id)
            .bind(action_id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(ConversationError::NotFound)
    }

    pub async fn record_dispatch_block(
        &self,
        id: Uuid,
        action_id: Uuid,
        reason: &str,
    ) -> Result<()> {
        if reason.is_empty() || reason.len() > 128 {
            return Err(ConversationError::InvalidRecord);
        }
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        let action: ConversationAction =
            sqlx::query_as("SELECT * FROM conversation_actions WHERE conversation_id=? AND id=?")
                .bind(id)
                .bind(action_id)
                .fetch_optional(&mut *tx)
                .await?
                .ok_or(ConversationError::NotFound)?;
        if action.state == "approved" {
            emit(
                &mut tx,
                id,
                "action.blocked",
                action.id,
                action.revision,
                &json!({"action_id":action.id,"reason":reason}),
            )
            .await?;
        }
        tx.commit().await?;
        Ok(())
    }
    pub async fn dispatch_block(&self, id: Uuid, action_id: Uuid) -> Result<Option<String>> {
        let action = self.action(id, action_id).await?;
        if action.state != "approved" {
            return Ok(None);
        }
        let payload:Option<String>=sqlx::query_scalar("SELECT payload FROM conversation_events WHERE conversation_id=? AND entity_id=? AND type='action.blocked' ORDER BY seq DESC LIMIT 1").bind(id).bind(action_id).fetch_optional(&self.pool).await?;
        Ok(payload
            .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
            .and_then(|v| v["reason"].as_str().map(str::to_owned)))
    }

    pub async fn confirmation(
        &self,
        id: Uuid,
        confirmation_id: Uuid,
    ) -> Result<ActionConfirmation> {
        self.get(id).await?;
        sqlx::query_as("SELECT * FROM conversation_confirmations WHERE conversation_id=? AND id=? AND principal_id=?").bind(id).bind(confirmation_id).bind(self.scope.principal_id).fetch_optional(&self.pool).await?.ok_or(ConversationError::NotFound)
    }

    pub async fn confirmations(&self, id: Uuid) -> Result<Vec<ActionConfirmation>> {
        self.get(id).await?;
        Ok(sqlx::query_as("SELECT * FROM conversation_confirmations WHERE conversation_id=? AND principal_id=? ORDER BY created_at DESC LIMIT 200")
            .bind(id).bind(self.scope.principal_id).fetch_all(&self.pool).await?)
    }

    /// HTTP/UI callers supply only an existing confirmation identity, digest and
    /// revision. They cannot change recipients or provide their own risk rating.
    pub async fn answer_confirmation(
        &self,
        id: Uuid,
        confirmation_id: Uuid,
        digest: &str,
        revision: i64,
        accept: bool,
    ) -> Result<ConversationAction> {
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        let confirmation:ActionConfirmation=sqlx::query_as("SELECT * FROM conversation_confirmations WHERE conversation_id=? AND id=? AND principal_id=?")
            .bind(id).bind(confirmation_id).bind(self.scope.principal_id).fetch_optional(&mut *tx).await?.ok_or(ConversationError::NotFound)?;
        let action: ConversationAction =
            sqlx::query_as("SELECT * FROM conversation_actions WHERE conversation_id=? AND id=?")
                .bind(id)
                .bind(confirmation.action_id)
                .fetch_one(&mut *tx)
                .await?;
        if confirmation.payload_digest != digest
            || confirmation.action_revision != revision
            || action.payload_digest != digest
        {
            return Err(ConversationError::RevisionConflict);
        }
        let chosen = if accept { "accepted" } else { "rejected" };
        if confirmation.state == chosen {
            tx.commit().await?;
            return Ok(action);
        }
        let now: i64 = sqlx::query_scalar("SELECT unixepoch()")
            .fetch_one(&mut *tx)
            .await?;
        if confirmation.state != "pending"
            || confirmation.expires_at <= now
            || action.state != "proposed"
            || action.revision != revision
        {
            return Err(ConversationError::RevisionConflict);
        }
        if accept {
            check_origin(&mut tx, &action).await?;
            let message: AgentMessage = serde_json::from_value(action.payload.0.clone())
                .map_err(|_| ConversationError::InvalidRecord)?;
            for t in &message.targets {
                if target(&mut tx, t.session_id).await? != *t {
                    return Err(ConversationError::RevisionConflict);
                }
            }
        }
        sqlx::query("UPDATE conversation_confirmations SET state=? WHERE id=?")
            .bind(chosen)
            .bind(confirmation.id)
            .execute(&mut *tx)
            .await?;
        emit(
            &mut tx,
            id,
            "confirmation.resolved",
            confirmation.id,
            revision + 1,
            &json!({"confirmation_id":confirmation.id,"action_id":action.id,"state":chosen}),
        )
        .await?;
        let action = transition(
            &mut tx,
            &action,
            if accept { "approved" } else { "rejected" },
            Some("explicit_confirmation"),
        )
        .await?;
        tx.commit().await?;
        Ok(action)
    }

    /// Atomically transfers authorised recipients into the shared queue/steering
    /// ledger. Existing queue recovery owns queued work; no second queue exists.
    /// Runtime code checks goal/approval gates before calling and again before
    /// executing a steering attempt. Scope/config is revalidated under this lock.
    pub async fn admit_agent_message(&self, id: Uuid, action_id: Uuid) -> Result<ActionAdmission> {
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        let action: ConversationAction =
            sqlx::query_as("SELECT * FROM conversation_actions WHERE conversation_id=? AND id=?")
                .bind(id)
                .bind(action_id)
                .fetch_optional(&mut *tx)
                .await?
                .ok_or(ConversationError::NotFound)?;
        let existing = action_deliveries(&mut tx, id, action_id).await?;
        if !existing.is_empty() {
            tx.commit().await?;
            return Ok(ActionAdmission {
                action,
                deliveries: existing,
                steering_attempts: vec![],
            });
        }
        if action.state != "approved" || action.intent_kind != "agent_message" {
            return Err(ConversationError::InvalidRecord);
        }
        check_origin(&mut tx, &action).await?;
        if action.authorisation_source.as_deref() == Some("explicit_confirmation") {
            let valid:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_confirmations WHERE action_id=? AND principal_id=? AND payload_digest=? AND state='accepted' AND expires_at>unixepoch())")
                .bind(action.id).bind(self.scope.principal_id).bind(&action.payload_digest).fetch_one(&mut *tx).await?;
            if !valid {
                return Err(ConversationError::RevisionConflict);
            }
        }
        let message: AgentMessage = serde_json::from_value(action.payload.0.clone())
            .map_err(|_| ConversationError::InvalidRecord)?;
        let mut attempts = Vec::new();
        for t in &message.targets {
            if target(&mut tx, t.session_id).await? != *t {
                return Err(ConversationError::RevisionConflict);
            }
            let active:Option<Uuid>=sqlx::query_scalar("SELECT id FROM execution_processes WHERE session_id=? AND status='running' AND run_reason='codingagent' AND dropped=0 ORDER BY created_at DESC,rowid DESC LIMIT 1")
                .bind(t.session_id).fetch_optional(&mut *tx).await?;
            let steer = active.is_some() && t.executor_config.executor == BaseCodingAgent::Codex;
            let waiting:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM agent_deliveries WHERE session_id=? AND state='waiting_capacity')")
                .bind(t.session_id).fetch_one(&mut *tx).await?;
            let data = DraftFollowUpData {
                message: message.message.clone(),
                executor_config: t.executor_config.clone(),
            };
            let record:AgentDelivery=sqlx::query_as("INSERT INTO agent_deliveries (id,action_id,source_kind,source_id,idempotency_key,session_id,workspace_id,data,state,requested_capacity,wait_for_capacity,predecessor_process_id,claim_id,lease_until,attempt_count,execution_process_id,delivery_mode) VALUES (?,?,'supervisor',?,?,?,?,?,?,0,?,?,?,?,?,?,?) RETURNING *")
                .bind(Uuid::new_v4()).bind(action.id).bind(id).bind(action.id).bind(t.session_id).bind(t.workspace_id).bind(Json(data))
                .bind(if steer {"dispatching"} else if waiting {"waiting_capacity"} else {"queued"}).bind(waiting && !steer)
                .bind(if steer {None} else {active}).bind(if steer {Some(Uuid::new_v4())} else {None})
                .bind(if steer {Some(Utc::now().timestamp()+60)} else {None}).bind(i64::from(steer))
                .bind(if steer {active} else {None}).bind(if steer {"steer"} else {"queue"}).fetch_one(&mut *tx).await?;
            if steer {
                attempts.push(record);
            }
        }
        let action = transition(&mut tx, &action, "dispatching", None).await?;
        let deliveries = action_deliveries(&mut tx, id, action_id).await?;
        tx.commit().await?;
        Ok(ActionAdmission {
            action,
            deliveries,
            steering_attempts: attempts,
        })
    }

    pub async fn action_deliveries(&self, id: Uuid, action_id: Uuid) -> Result<Vec<AgentDelivery>> {
        self.action(id, action_id).await?;
        let mut conn = self.pool.acquire().await?;
        action_deliveries(&mut conn, id, action_id).await
    }

    pub async fn reconcile_action(&self, id: Uuid, action_id: Uuid) -> Result<ConversationAction> {
        let mut tx = self.pool.begin().await?;
        self.lock(&mut tx, id).await?;
        invalidate_pending(&mut tx, id).await?;
        let action: ConversationAction =
            sqlx::query_as("SELECT * FROM conversation_actions WHERE conversation_id=? AND id=?")
                .bind(id)
                .bind(action_id)
                .fetch_optional(&mut *tx)
                .await?
                .ok_or(ConversationError::NotFound)?;
        let rows = action_deliveries(&mut tx, id, action_id).await?;
        let state = if rows.is_empty() {
            None
        } else if rows.iter().any(|d| d.state == "unknown_delivery") {
            Some("unknown_delivery")
        } else if rows
            .iter()
            .all(|d| matches!(d.state.as_str(), "completed" | "failed" | "cancelled"))
        {
            Some(if rows.iter().all(|d| d.state == "completed") {
                "succeeded"
            } else {
                "failed"
            })
        } else {
            Some("dispatching")
        };
        let action = if let Some(state) = state.filter(|s| *s != action.state) {
            transition(&mut tx, &action, state, None).await?
        } else {
            action
        };
        tx.commit().await?;
        Ok(action)
    }

    /// Called by the existing delivery recovery scan. Select only actions whose
    /// aggregate changed; old uncertain receipts cannot starve newer outcomes.
    pub async fn reconcile_delivery_actions(&self) -> Result<usize> {
        let changed: Vec<(Uuid, Uuid)> = sqlx::query_as(
            "WITH outcomes AS (
                SELECT a.conversation_id,a.id,a.state,
                    CASE WHEN sum(d.state='unknown_delivery')>0 THEN 'unknown_delivery'
                    WHEN sum(d.state NOT IN ('completed','failed','cancelled'))=0
                        THEN CASE WHEN sum(d.state!='completed')=0 THEN 'succeeded' ELSE 'failed' END
                    ELSE 'dispatching' END AS outcome
                FROM conversation_actions a
                JOIN conversations c ON c.id=a.conversation_id
                JOIN agent_deliveries d ON d.action_id=a.id AND d.source_id=a.conversation_id AND d.source_kind='supervisor'
                WHERE c.authority_id=? AND c.principal_id=?
                GROUP BY a.id
            ) SELECT conversation_id,id FROM outcomes WHERE state!=outcome LIMIT 200",
        ).bind(self.scope.authority_id).bind(self.scope.principal_id).fetch_all(&self.pool).await?;
        for (id, action) in &changed {
            self.reconcile_action(*id, *action).await?;
        }
        Ok(changed.len())
    }
}

/// Retire only proposals that have not crossed into the delivery ledger. This
/// fences cancelled/failed/expired workers and expired confirmation grants,
/// without suggesting already delivered work was undone.
pub(super) async fn invalidate_pending(conn: &mut SqliteConnection, id: Uuid) -> Result<()> {
    let invalid:Vec<ConversationAction>=sqlx::query_as("SELECT a.* FROM conversation_actions a WHERE a.conversation_id=? AND a.state IN ('proposed','approved') AND NOT EXISTS(SELECT 1 FROM agent_deliveries d WHERE d.action_id=a.id) AND (NOT EXISTS(SELECT 1 FROM conversation_runs r WHERE r.id=a.run_id AND r.conversation_id=a.conversation_id AND r.input_message_id=a.origin_message_id AND (r.status='completed' OR (r.status='running' AND r.lease_until>unixepoch()))) OR EXISTS(SELECT 1 FROM conversation_confirmations c WHERE c.action_id=a.id AND c.expires_at<=unixepoch()))")
        .bind(id).fetch_all(&mut *conn).await?;
    for action in invalid {
        let confirmations:Vec<ActionConfirmation>=sqlx::query_as("UPDATE conversation_confirmations SET state='expired' WHERE action_id=? AND state IN ('pending','accepted') RETURNING *")
            .bind(action.id).fetch_all(&mut *conn).await?;
        for confirmation in confirmations {
            emit(
                conn,
                id,
                "confirmation.resolved",
                confirmation.id,
                action.revision + 1,
                &json!({"confirmation_id":confirmation.id,"action_id":action.id,"state":"expired"}),
            )
            .await?;
        }
        transition(conn, &action, "cancelled", None).await?;
    }
    Ok(())
}

async fn check_origin(conn: &mut SqliteConnection, action: &ConversationAction) -> Result<()> {
    let valid:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM conversation_runs WHERE id=? AND conversation_id=? AND input_message_id=? AND (status='completed' OR (status='running' AND lease_until>unixepoch())))")
        .bind(action.run_id).bind(action.conversation_id).bind(action.origin_message_id).fetch_one(conn).await?;
    if valid {
        Ok(())
    } else {
        Err(ConversationError::StaleLease)
    }
}

async fn transition(
    conn: &mut SqliteConnection,
    action: &ConversationAction,
    state: &str,
    authority: Option<&str>,
) -> Result<ConversationAction> {
    let updated:ConversationAction=sqlx::query_as("UPDATE conversation_actions SET state=?,authorisation_source=coalesce(?,authorisation_source),revision=revision+1 WHERE id=? AND conversation_id=? AND revision=? RETURNING *")
        .bind(state).bind(authority).bind(action.id).bind(action.conversation_id).bind(action.revision).fetch_optional(&mut *conn).await?.ok_or(ConversationError::RevisionConflict)?;
    emit(
        conn,
        action.conversation_id,
        "action.status",
        action.id,
        updated.revision,
        &updated,
    )
    .await?;
    Ok(updated)
}
async fn action_deliveries(
    conn: &mut SqliteConnection,
    id: Uuid,
    action: Uuid,
) -> Result<Vec<AgentDelivery>> {
    Ok(sqlx::query_as("SELECT * FROM agent_deliveries WHERE source_kind='supervisor' AND source_id=? AND action_id=? ORDER BY position").bind(id).bind(action).fetch_all(conn).await?)
}

pub(crate) async fn target(conn: &mut SqliteConnection, session_id: Uuid) -> Result<MessageTarget> {
    #[derive(FromRow, Serialize)]
    struct Identity {
        workspace_id: Uuid,
        name: Option<String>,
        branch: String,
        session_name: Option<String>,
        executor: Option<String>,
        agent_working_dir: Option<String>,
        task_id: Option<Uuid>,
    }
    let mut identity:Identity=sqlx::query_as("SELECT w.id AS workspace_id,w.name,w.branch,s.name AS session_name,s.executor,s.agent_working_dir,w.task_id FROM sessions s JOIN workspaces w ON w.id=s.workspace_id WHERE s.id=? AND w.archived=0 AND w.worktree_deleted=0")
        .bind(session_id).fetch_optional(&mut *conn).await?.ok_or(ConversationError::NotFound)?;
    let process:ExecutionProcess=sqlx::query_as("SELECT * FROM execution_processes WHERE session_id=? AND run_reason='codingagent' AND dropped=0 ORDER BY created_at DESC,rowid DESC LIMIT 1")
        .bind(session_id).fetch_optional(&mut *conn).await?.ok_or(ConversationError::InvalidRecord)?;
    let config = match &process
        .executor_action()
        .map_err(|_| ConversationError::InvalidRecord)?
        .typ
    {
        ExecutorActionType::CodingAgentInitialRequest(r) => r.executor_config.clone(),
        ExecutorActionType::CodingAgentFollowUpRequest(r) => r.executor_config.clone(),
        ExecutorActionType::ReviewRequest(r) => r.executor_config.clone(),
        _ => return Err(ConversationError::InvalidRecord),
    };
    if identity
        .executor
        .as_ref()
        .is_some_and(|e| *e != config.executor.to_string())
    {
        return Err(ConversationError::InvalidRecord);
    }
    // Filling a legacy NULL executor column with the already-selected executor
    // is not a routing change. Canonicalize it before binding the snapshot.
    identity.executor = Some(config.executor.to_string());
    let repos:Vec<(Uuid,String)>=sqlx::query_as("SELECT repo_id,target_branch FROM workspace_repos WHERE workspace_id=? ORDER BY repo_id LIMIT 33")
        .bind(identity.workspace_id).fetch_all(&mut *conn).await?;
    if repos.len() > 32 {
        return Err(ConversationError::InvalidRecord);
    }
    let version = format!(
        "{:x}",
        Sha256::digest(
            serde_json::to_vec(
                &json!({"session_id":session_id,"identity":identity,"repos":repos,"config":config})
            )
            .map_err(|_| ConversationError::InvalidRecord)?
        )
    );
    Ok(MessageTarget {
        workspace_id: identity.workspace_id,
        session_id,
        workspace_name: identity.name.unwrap_or_else(|| identity.branch.clone()),
        session_name: identity.session_name,
        branch: identity.branch,
        executor_config: config,
        version,
    })
}

#[cfg(test)]
mod tests;
