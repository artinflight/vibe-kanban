//! Narrow durable admission for one explicitly configured existing owner.
//! No scheduler, queue writer, alternative executor, or dispatch retry lives here.
use std::future::Future;

use chrono::{DateTime, Utc};
use executors::profile::ExecutorConfig;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

use super::{container::ContainerError, queued_message::QueuedMessageService};

pub const PROTOCOL: &str = "storage-admission-v2";
tokio::task_local! { static CANDIDATE: Uuid; }

pub fn candidate_execution_id() -> Option<Uuid> {
    CANDIDATE.try_with(|id| *id).ok()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OwnerBinding {
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub executor_config: ExecutorConfig,
    pub max_validation_age_seconds: u32,
    /// Existing controlled-delegation journal directory, reviewed at adoption.
    /// Legacy bindings still parse, but absent producer custody holds new POSTs.
    #[serde(default)]
    pub delegation_journal_dir: Option<std::path::PathBuf>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Incident {
    pub incident_id: Uuid,
    pub filesystem_uuid: String,
    pub policy: String,
    pub opened_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Intent {
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub incidents: Vec<Incident>,
    pub receipt_ref: String,
    pub prompt: String,
    pub executor_config_sha256: String,
}

/// Producer evidence, not a substitute for the native launch/resource gates.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Validation {
    pub observed_at: DateTime<Utc>,
    pub eligible_incident_ids: Vec<Uuid>,
    pub evidence_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub protocol: String,
    pub batch_id: Uuid,
    pub attempt_id: Uuid,
    pub intent_sha256: String,
    pub intent: Intent,
    pub validation: Validation,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Receipt {
    pub batch_id: Uuid,
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub intent_sha256: String,
    pub attempt_id: Uuid,
    pub state: String,
    pub reason: String,
    pub execution_id: Option<Uuid>,
}

#[derive(Debug, Serialize)]
pub struct Response {
    pub protocol: &'static str,
    pub outcome: String,
    pub no_admission: bool,
    pub automatic_launch_queued: bool,
    pub replay: bool,
    pub receipt: Option<Receipt>,
    pub execution_status: Option<String>,
    pub reason: String,
}

impl Response {
    fn unbound(reason: &str) -> Self {
        Self {
            protocol: PROTOCOL,
            outcome: "uncertain".into(),
            no_admission: false,
            automatic_launch_queued: false,
            replay: false,
            receipt: None,
            execution_status: None,
            reason: reason.into(),
        }
    }
}

/// SHA-256 of recursively key-sorted compact UTF-8 JSON. Do not depend on the
/// workspace's serde_json preserve_order feature. Arrays retain their order.
pub fn fingerprint(value: &impl Serialize) -> String {
    fn canonical(value: &serde_json::Value, out: &mut String) {
        match value {
            serde_json::Value::Object(map) => {
                let mut keys: Vec<_> = map.keys().collect();
                keys.sort();
                out.push('{');
                for (i, key) in keys.iter().enumerate() {
                    if i != 0 {
                        out.push(',');
                    }
                    out.push_str(&serde_json::to_string(key).expect("key"));
                    out.push(':');
                    canonical(&map[*key], out);
                }
                out.push('}');
            }
            serde_json::Value::Array(values) => {
                out.push('[');
                for (i, value) in values.iter().enumerate() {
                    if i != 0 {
                        out.push(',');
                    }
                    canonical(value, out);
                }
                out.push(']');
            }
            _ => out.push_str(&serde_json::to_string(value).expect("scalar")),
        }
    }
    let mut bytes = String::new();
    canonical(
        &serde_json::to_value(value).expect("serializable intent"),
        &mut bytes,
    );
    format!("{:x}", Sha256::digest(bytes.as_bytes()))
}

const RECEIPT_SQL: &str = "SELECT b.batch_id, b.workspace_id, b.session_id, b.intent_sha256, a.attempt_id, a.state, a.reason, a.execution_id FROM storage_alert_batches b JOIN storage_alert_attempts a ON a.attempt_id = b.latest_attempt_id WHERE b.batch_id = ?";

pub async fn lookup(
    pool: &SqlitePool,
    batch: Uuid,
    expected: &str,
) -> Result<Response, sqlx::Error> {
    let receipt: Option<Receipt> = sqlx::query_as(RECEIPT_SQL)
        .bind(batch)
        .fetch_optional(pool)
        .await?;
    let Some(receipt) = receipt else {
        return Ok(Response::unbound("not_found_is_not_resend_authority"));
    };
    if receipt.intent_sha256 != expected {
        return Ok(Response::unbound("intent_conflict"));
    }
    response(pool, receipt, false).await
}

async fn response(
    pool: &SqlitePool,
    receipt: Receipt,
    replay: bool,
) -> Result<Response, sqlx::Error> {
    let status = if let Some(id) = receipt.execution_id {
        sqlx::query_scalar("SELECT status FROM execution_processes WHERE id = ?")
            .bind(id)
            .fetch_optional(pool)
            .await?
    } else {
        None
    };
    let no_admission = matches!(receipt.state.as_str(), "deferred" | "rejected");
    Ok(Response {
        protocol: PROTOCOL,
        outcome: if receipt.state == "in_flight" {
            "uncertain".into()
        } else {
            receipt.state.clone()
        },
        no_admission,
        automatic_launch_queued: false,
        replay,
        reason: receipt.reason.clone(),
        receipt: Some(receipt),
        execution_status: status,
    })
}

pub async fn owner_reserved(pool: &SqlitePool, workspace: Uuid) -> Result<bool, sqlx::Error> {
    sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM storage_alert_batches b JOIN storage_alert_attempts a ON a.attempt_id = b.latest_attempt_id WHERE b.workspace_id = ? AND (a.state = 'in_flight' OR (a.state = 'accepted' AND (NOT EXISTS(SELECT 1 FROM execution_processes e WHERE e.id = a.execution_id) OR EXISTS(SELECT 1 FROM execution_processes e WHERE e.id = a.execution_id AND e.status = 'running')))))")
        .bind(workspace).fetch_one(pool).await
}

/// Fence only unbound admission. The database serializes this with execution
/// insertion; a late insert loses its authority. Never stops an accepted run.
pub async fn cancel(
    pool: &SqlitePool,
    batch: Uuid,
    expected: &str,
) -> Result<Response, sqlx::Error> {
    let mut tx = pool.begin_with("BEGIN IMMEDIATE").await?;
    sqlx::query("UPDATE storage_alert_attempts SET state = 'rejected', reason = 'cancelled_tombstone' WHERE attempt_id = (SELECT latest_attempt_id FROM storage_alert_batches WHERE batch_id = ? AND intent_sha256 = ?) AND state IN ('in_flight', 'deferred')")
        .bind(batch).bind(expected).execute(&mut *tx).await?;
    sqlx::query("DELETE FROM storage_alert_incidents WHERE batch_id = ? AND EXISTS(SELECT 1 FROM storage_alert_attempts a JOIN storage_alert_batches b ON b.latest_attempt_id = a.attempt_id WHERE b.batch_id = ? AND b.intent_sha256 = ? AND a.state = 'rejected')")
        .bind(batch).bind(batch).bind(expected).execute(&mut *tx).await?;
    tx.commit().await?;
    lookup(pool, batch, expected).await
}

/// Called under native global admission, then the owner lock, just like normal
/// input and queue consumers. DB fences additionally protect abandoned handlers.
pub async fn submit<F, Fut>(
    pool: &SqlitePool,
    queue: &QueuedMessageService,
    binding: &OwnerBinding,
    request: &Request,
    launch: F,
) -> Result<Response, sqlx::Error>
where
    F: FnOnce(ExecutorConfig) -> Fut,
    Fut: Future<Output = Result<(), ContainerError>>,
{
    super::admission::run(super::admission::owner(binding.workspace_id, async {
        submit_owned(pool, queue, binding, request, launch).await
    }))
    .await
}

async fn submit_owned<F, Fut>(
    pool: &SqlitePool,
    queue: &QueuedMessageService,
    binding: &OwnerBinding,
    request: &Request,
    launch: F,
) -> Result<Response, sqlx::Error>
where
    F: FnOnce(ExecutorConfig) -> Fut,
    Fut: Future<Output = Result<(), ContainerError>>,
{
    let mut tx = pool.begin_with("BEGIN IMMEDIATE").await?;
    let intent = serde_json::to_string(&request.intent).expect("intent");
    let validation = serde_json::to_string(&request.validation).expect("validation");
    let old: Option<(String, String)> = sqlx::query_as(
        "SELECT intent_sha256, intent FROM storage_alert_batches WHERE batch_id = ?",
    )
    .bind(request.batch_id)
    .fetch_optional(&mut *tx)
    .await?;
    let previous_attempt: Option<(Uuid, String)> = sqlx::query_as(
        "SELECT batch_id, validation FROM storage_alert_attempts WHERE attempt_id = ?",
    )
    .bind(request.attempt_id)
    .fetch_optional(&mut *tx)
    .await?;
    if previous_attempt
        .as_ref()
        .is_some_and(|(batch, saved)| *batch != request.batch_id || saved != &validation)
    {
        return Ok(Response::unbound("attempt_identity_conflict"));
    }
    if let Some((hash, saved)) = &old {
        if hash != &request.intent_sha256 || saved != &intent {
            return Ok(Response::unbound("batch_identity_conflict"));
        }
        let receipt: Receipt = sqlx::query_as(RECEIPT_SQL)
            .bind(request.batch_id)
            .fetch_one(&mut *tx)
            .await?;
        if receipt.state != "deferred" {
            tx.commit().await?;
            return response(pool, receipt, true).await;
        }
    }
    if previous_attempt.is_some() {
        let receipt: Receipt = sqlx::query_as("SELECT b.batch_id, b.workspace_id, b.session_id, b.intent_sha256, a.attempt_id, a.state, a.reason, a.execution_id FROM storage_alert_batches b JOIN storage_alert_attempts a USING(batch_id) WHERE a.attempt_id = ?")
            .bind(request.attempt_id).fetch_one(&mut *tx).await?;
        tx.commit().await?;
        return response(pool, receipt, true).await;
    }
    if old.is_none() {
        sqlx::query("INSERT INTO storage_alert_batches(batch_id, workspace_id, session_id, intent_sha256, intent) VALUES (?, ?, ?, ?, ?)")
            .bind(request.batch_id).bind(request.intent.workspace_id).bind(request.intent.session_id).bind(&request.intent_sha256).bind(&intent).execute(&mut *tx).await?;
    }
    let mut state = "in_flight";
    let mut reason = "dispatch_reserved";
    if old.is_some() {
        let saved: String = sqlx::query_scalar("SELECT a.validation FROM storage_alert_attempts a JOIN storage_alert_batches b ON b.latest_attempt_id = a.attempt_id WHERE b.batch_id = ?")
            .bind(request.batch_id).fetch_one(&mut *tx).await?;
        let saved: Validation = serde_json::from_str(&saved)
            .map_err(|_| sqlx::Error::Protocol("Invalid retained validation".into()))?;
        if request.validation.observed_at <= saved.observed_at {
            state = "deferred";
            reason = "fresh_validation_required";
        }
    }
    let mut ids: Vec<_> = request
        .intent
        .incidents
        .iter()
        .map(|i| i.incident_id)
        .collect();
    ids.sort();
    let mut eligible = request.validation.eligible_incident_ids.clone();
    eligible.sort();
    let valid_hash = |s: &str| {
        s.len() == 64
            && s.bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    };
    if request.protocol != PROTOCOL
        || fingerprint(&request.intent) != request.intent_sha256
        || request.intent.workspace_id != binding.workspace_id
        || request.intent.session_id != binding.session_id
        || request.intent.executor_config_sha256 != fingerprint(&binding.executor_config)
        || ids.is_empty()
        || ids.len() > 8
        || ids.windows(2).any(|w| w[0] == w[1])
        || ids.iter().any(Uuid::is_nil)
        || request.batch_id.is_nil()
        || request.attempt_id.is_nil()
        || request.intent.prompt.trim().is_empty()
        || request.intent.prompt.len() > 32768
        || request.intent.prompt.trim_start().starts_with('/')
        || request.intent.receipt_ref.is_empty()
        || request.intent.incidents.iter().any(|i| {
            i.filesystem_uuid.is_empty()
                || i.policy.is_empty()
                || i.opened_at > request.validation.observed_at
        })
    {
        state = "rejected";
        reason = "invalid_intent_or_owner";
    }
    if state == "in_flight" && (eligible != ids || !valid_hash(&request.validation.evidence_sha256))
    {
        state = "rejected";
        reason = "invalid_validation";
    }
    let age = Utc::now().signed_duration_since(request.validation.observed_at);
    if state == "in_flight"
        && (age.num_milliseconds() < 0
            || age.num_seconds() > i64::from(binding.max_validation_age_seconds))
    {
        state = "deferred";
        reason = "fresh_validation_required";
    }
    let owner_valid: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM sessions s JOIN workspaces w ON w.id = s.workspace_id WHERE s.id = ? AND w.id = ? AND w.archived = FALSE AND w.worktree_deleted = FALSE)")
        .bind(binding.session_id).bind(binding.workspace_id).fetch_one(&mut *tx).await?;
    if state == "in_flight" && !owner_valid {
        state = "rejected";
        reason = "owner_unavailable";
    }
    // Read both durable and memory queues. Never take, edit or merge user input.
    let sessions: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM sessions WHERE workspace_id = ?")
        .bind(binding.workspace_id)
        .fetch_all(&mut *tx)
        .await?;
    let queued: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM turn_github_sync_user_queue WHERE workspace_id = ?) OR EXISTS(SELECT 1 FROM turn_github_sync_incoming WHERE workspace_id = ? AND state = 'received')")
        .bind(binding.workspace_id).bind(binding.workspace_id).fetch_one(&mut *tx).await?;
    let running: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id = e.session_id WHERE s.workspace_id = ? AND e.status = 'running' AND e.run_reason != 'devserver') OR EXISTS(SELECT 1 FROM storage_alert_batches b JOIN storage_alert_attempts a ON a.attempt_id = b.latest_attempt_id WHERE b.workspace_id = ? AND (a.state = 'in_flight' OR (a.state = 'accepted' AND NOT EXISTS(SELECT 1 FROM execution_processes e WHERE e.id = a.execution_id))))")
        .bind(binding.workspace_id).bind(binding.workspace_id).fetch_one(&mut *tx).await?;
    if state == "in_flight" && (queued || sessions.iter().any(|id| queue.has_queued(*id))) {
        state = "deferred";
        reason = "owner_user_work_pending";
    }
    let job_lifetime_unsettled: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM watcher_job_leases WHERE workspace_id=? AND closed_at IS NULL)")
        .bind(binding.workspace_id).fetch_one(&mut *tx).await?;
    if state == "in_flight" && job_lifetime_unsettled {
        state = "deferred";
        reason = "independent_job_lifetime_unsettled";
    }
    if state == "in_flight" && running {
        state = "deferred";
        reason = "owner_busy";
    }
    for incident in &request.intent.incidents {
        let claimed: Option<Uuid> = sqlx::query_scalar("SELECT batch_id FROM storage_alert_incidents WHERE workspace_id = ? AND incident_id = ?")
            .bind(binding.workspace_id).bind(incident.incident_id).fetch_optional(&mut *tx).await?;
        if claimed.is_some_and(|id| id != request.batch_id) && state != "rejected" {
            state = "rejected";
            reason = "incident_already_pending";
        }
    }
    let candidate = Uuid::new_v4();
    sqlx::query("INSERT INTO storage_alert_attempts(attempt_id, batch_id, validation, candidate_execution_id, state, reason) VALUES (?, ?, ?, ?, ?, ?)")
        .bind(request.attempt_id).bind(request.batch_id).bind(validation).bind(candidate).bind(state).bind(reason).execute(&mut *tx).await?;
    sqlx::query("UPDATE storage_alert_batches SET latest_attempt_id = ? WHERE batch_id = ?")
        .bind(request.attempt_id)
        .bind(request.batch_id)
        .execute(&mut *tx)
        .await?;
    if state == "in_flight" {
        for incident in &request.intent.incidents {
            sqlx::query("INSERT INTO storage_alert_incidents VALUES (?, ?, ?)")
                .bind(binding.workspace_id)
                .bind(incident.incident_id)
                .bind(request.batch_id)
                .execute(&mut *tx)
                .await?;
        }
    }
    tx.commit().await?;
    if state != "in_flight" {
        return lookup(pool, request.batch_id, &request.intent_sha256).await;
    }

    // Cancellation drops this future but leaves a durable uncertain receipt.
    // The reservation never enters the normal capacity queue.
    let result = CANDIDATE
        .scope(candidate, launch(binding.executor_config.clone()))
        .await;
    let mut tx = pool.begin_with("BEGIN IMMEDIATE").await?;
    let (state, reason) = match result {
        Ok(()) => ("rejected", "launch_returned_without_execution"),
        Err(ref e) if e.is_execution_limit_reached() => ("deferred", "native_capacity_hold"),
        Err(ContainerError::StorageAdmissionDeferred(reason)) => ("deferred", reason),
        Err(_) => ("rejected", "native_launch_rejected_before_binding"),
    };
    // A committed execution always wins, even if launch/ack failed afterwards.
    sqlx::query("UPDATE storage_alert_attempts SET state = ?, reason = ? WHERE attempt_id = ? AND state = 'in_flight'")
        .bind(state).bind(reason).bind(request.attempt_id).execute(&mut *tx).await?;
    sqlx::query("DELETE FROM storage_alert_incidents WHERE batch_id = ? AND EXISTS(SELECT 1 FROM storage_alert_attempts WHERE attempt_id = ? AND state IN ('deferred', 'rejected'))")
        .bind(request.batch_id).bind(request.attempt_id).execute(&mut *tx).await?;
    tx.commit().await?;
    lookup(pool, request.batch_id, &request.intent_sha256).await
}

#[cfg(test)]
mod tests;
