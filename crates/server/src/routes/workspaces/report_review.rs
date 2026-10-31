//! Proposed additive backend route. NOT installed in the running Vibe process.
//! Exact final-message identity comes from immutable full log replay, not summary.
use axum::{Extension, Json, extract::State};
use db::models::{
    execution_process::{ExecutionProcess, ExecutionProcessStatus},
    workspace::Workspace,
};
use deployment::Deployment;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::{Row, Sqlite, SqlitePool, Transaction};
use utils::response::ApiResponse;
use uuid::Uuid;

use super::workspace_summary::invalidate_workspace_summary_cache;
use crate::{DeploymentImpl, error::ApiError};

/// Narrow dependency boundary for isolated HTTP acceptance. Production still
/// supplies its existing deployment; no application constructor/test agent runs.
pub trait ReviewBackend: Clone + Send + Sync + 'static {
    fn pool(&self) -> &SqlitePool;
    fn fingerprint(
        &self,
        process: &ExecutionProcess,
    ) -> impl std::future::Future<Output = Result<(usize, String), ApiError>> + Send;
}
impl ReviewBackend for DeploymentImpl {
    fn pool(&self) -> &SqlitePool {
        &self.db().pool
    }
    async fn fingerprint(&self, process: &ExecutionProcess) -> Result<(usize, String), ApiError> {
        crate::routes::execution_processes::log_history::final_reply_fingerprint(self, process)
            .await
    }
}

const PROTOCOL: &str = "workspace-review-v1";
pub const ENSURE_INTENT: &str = "INSERT INTO workspace_review_intent(workspace_id,held,version) VALUES (?,0,0) ON CONFLICT(workspace_id) DO NOTHING";
pub const LOCK_INTENT: &str =
    "UPDATE workspace_review_intent SET version=version WHERE workspace_id=?";
pub const GET_INTENT: &str =
    "SELECT held,version FROM workspace_review_intent WHERE workspace_id=?";
pub const PROCESS: &str = "SELECT ep.session_id,ep.status,ep.updated_at,ep.created_at,ep.completed_at FROM execution_processes ep JOIN sessions s ON ep.session_id=s.id WHERE ep.id=? AND s.workspace_id=? AND ep.run_reason='codingagent'";
pub const OTHER_ACTIVITY: &str = "SELECT COUNT(*) FROM execution_processes ep JOIN sessions s ON ep.session_id=s.id WHERE s.workspace_id=? AND ep.id<>? AND (ep.status NOT IN ('completed','failed','killed') OR ep.completed_at IS NULL OR (ep.run_reason='codingagent' AND (ep.created_at>? OR ep.completed_at>?)))";
pub const MARK_EXACT: &str =
    "UPDATE coding_agent_turns SET seen=1,updated_at=? WHERE execution_process_id=? AND seen=0";
pub const LOG_FINALIZED: &str =
    "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?";
pub const MANUAL_SEEN: &str = "UPDATE coding_agent_turns SET seen=1,updated_at=? WHERE execution_process_id IN (SELECT ep.id FROM execution_processes ep JOIN sessions s ON ep.session_id=s.id WHERE s.workspace_id=?) AND seen=0";
pub const MANUAL_UNREAD: &str = "UPDATE coding_agent_turns SET seen=0,updated_at=? WHERE execution_process_id=(SELECT ep.id FROM execution_processes ep JOIN sessions s ON ep.session_id=s.id WHERE s.workspace_id=? AND ep.run_reason='codingagent' ORDER BY ep.created_at DESC,ep.id DESC LIMIT 1)";

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Source {
    actor: String,
    channel: String,
    event_id: String,
    evidence: String,
}
impl Source {
    fn validate(&self) -> Result<(), &'static str> {
        if !["root", "dot"].contains(&self.actor.as_str())
            || !["voice", "chat"].contains(&self.channel.as_str())
            || self.event_id.trim().is_empty()
            || self.event_id.len() > 200
            || self.evidence.trim().is_empty()
            || self.evidence.len() > 8000
        {
            return Err("Actual redacted voice/chat delivery evidence required");
        }
        Ok(())
    }
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Receipt {
    workspace_id: Uuid,
    execution_id: Uuid,
    session_id: Uuid,
    message_index: usize,
    reply_sha256: String,
    hash_version: String,
    execution_revision: String,
    disposition: String,
    source: Source,
    receipt_id: String,
    intent_version: i64,
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Hold {
    held: bool,
    event_id: String,
    source: Source,
    expected_intent_version: i64,
}

fn sha(text: &str) -> String {
    format!("{:x}", Sha256::digest(text.as_bytes()))
}
fn hex64(text: &str) -> bool {
    text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn conflict(text: &str) -> ApiError {
    ApiError::Conflict(text.into())
}

async fn lock(tx: &mut Transaction<'_, Sqlite>, wid: Uuid) -> Result<(), ApiError> {
    // First statement writes: obtain SQLite's writer lock BEFORE reading any
    // intent, execution, or receipt. All UI, hold and receipt writers serialize.
    sqlx::query(ENSURE_INTENT)
        .bind(wid)
        .execute(&mut **tx)
        .await?;
    sqlx::query(LOCK_INTENT)
        .bind(wid)
        .execute(&mut **tx)
        .await?;
    Ok(())
}

pub async fn state<B: ReviewBackend>(
    Extension(w): Extension<Workspace>,
    State(d): State<B>,
) -> Result<Json<ApiResponse<Value>>, ApiError> {
    let row = sqlx::query(GET_INTENT)
        .bind(w.id)
        .fetch_optional(d.pool())
        .await?;
    let (held, version) = row
        .map(|r| (r.get::<bool, _>("held"), r.get::<i64, _>("version")))
        .unwrap_or((false, 0));
    Ok(Json(ApiResponse::success(
        json!({"protocol":PROTOCOL,"atomic_exact_reply":true,
        "manual_intent_guard":true,"held":held,"intent_version":version}),
    )))
}

pub async fn receipt<B: ReviewBackend>(
    Extension(w): Extension<Workspace>,
    State(d): State<B>,
    Json(p): Json<Receipt>,
) -> Result<Json<ApiResponse<Value>>, ApiError> {
    p.source
        .validate()
        .map_err(|e| ApiError::BadRequest(e.into()))?;
    if p.workspace_id != w.id
        || p.hash_version != "utf8-sha256-v1"
        || !hex64(&p.reply_sha256)
        || !hex64(&p.receipt_id)
        || !["delivered", "handled"].contains(&p.disposition.as_str())
        || p.intent_version < 0
    {
        return Err(ApiError::BadRequest("Invalid exact report receipt".into()));
    }
    let process = ExecutionProcess::find_by_id(d.pool(), p.execution_id)
        .await?
        .ok_or_else(|| conflict("Execution missing"))?;
    let finalized: i64 = sqlx::query_scalar(LOG_FINALIZED)
        .bind(p.execution_id)
        .fetch_one(d.pool())
        .await?;
    if finalized != 1 {
        return Err(conflict(
            "Successful closed-log writer proof missing; historical reports require release-owner closure validation",
        ));
    }
    let expected_revision = chrono::DateTime::parse_from_rfc3339(&p.execution_revision)
        .map_err(|_| ApiError::BadRequest("Invalid execution revision".into()))?
        .with_timezone(&chrono::Utc);
    if process.status != ExecutionProcessStatus::Completed
        || process.session_id != p.session_id
        || process.updated_at != expected_revision
    {
        return Err(conflict("Execution ownership/revision/status changed"));
    }
    let turn_before: Option<chrono::DateTime<chrono::Utc>> = sqlx::query_scalar(
        "SELECT updated_at FROM coding_agent_turns WHERE execution_process_id=?",
    )
    .bind(p.execution_id)
    .fetch_optional(d.pool())
    .await?;
    let turn_before = turn_before.ok_or_else(|| conflict("Coding turn missing"))?;
    // This helper explicitly rejects a resident/draining store and consumes only
    // the finite durable replay. A summary (potentially 4KiB truncated) is NEVER
    // used as full-message evidence. Replay normalization version is explicit.
    let (index, hash) = d.fingerprint(&process).await?;
    if index != p.message_index || hash != p.reply_sha256 {
        return Err(conflict("Exact final reply changed"));
    }

    let encoded =
        serde_json::to_string(&p).map_err(|_| ApiError::BadRequest("Receipt encoding".into()))?;
    let payload_hash = sha(&encoded);
    let event_key = format!(
        "{}:{}:{}:{}",
        w.id, p.source.actor, p.source.channel, p.source.event_id
    );
    let mut tx = d.pool().begin().await?;
    lock(&mut tx, w.id).await?;
    if let Some(r)=sqlx::query("SELECT payload_hash,proof FROM workspace_review_receipts WHERE receipt_id=? OR event_key=?")
        .bind(&p.receipt_id).bind(&event_key).fetch_optional(&mut *tx).await? {
        if r.get::<String,_>("payload_hash")!=payload_hash { return Err(conflict("Conflicting/reused delivery event")); }
        let mut proof:Value=serde_json::from_str(&r.get::<String,_>("proof")).map_err(|_| conflict("Stored receipt invalid"))?;
        proof["status"]=json!("already_applied");
        tx.commit().await?;
        return Ok(Json(ApiResponse::success(proof))); // NO repeat marker write.
    }
    let intent = sqlx::query(GET_INTENT)
        .bind(w.id)
        .fetch_one(&mut *tx)
        .await?;
    if intent.get::<bool, _>("held") || intent.get::<i64, _>("version") != p.intent_version {
        return Err(conflict("Explicit manual intent/hold changed"));
    }
    let r = sqlx::query(PROCESS)
        .bind(p.execution_id)
        .bind(w.id)
        .fetch_optional(&mut *tx)
        .await?
        .ok_or_else(|| conflict("Workspace/session ownership changed"))?;
    let revision: chrono::DateTime<chrono::Utc> = r.try_get("updated_at")?;
    if r.get::<Uuid, _>("session_id") != p.session_id
        || r.get::<String, _>("status") != "completed"
        || revision != expected_revision
    {
        return Err(conflict("Execution revision changed during replay"));
    }
    let created: chrono::DateTime<chrono::Utc> = r.try_get("created_at")?;
    let completed: Option<chrono::DateTime<chrono::Utc>> = r.try_get("completed_at")?;
    let completed = completed.ok_or_else(|| conflict("Incomplete execution"))?;
    let active: i64 = sqlx::query_scalar(OTHER_ACTIVITY)
        .bind(w.id)
        .bind(p.execution_id)
        .bind(created)
        .bind(completed)
        .fetch_one(&mut *tx)
        .await?;
    if active != 0 {
        return Err(conflict(
            "Newer/running/uncertain activity in another workspace session",
        ));
    }
    let turn =
        sqlx::query("SELECT updated_at FROM coding_agent_turns WHERE execution_process_id=?")
            .bind(p.execution_id)
            .fetch_optional(&mut *tx)
            .await?
            .ok_or_else(|| conflict("Coding turn missing"))?;
    let turn_revision: chrono::DateTime<chrono::Utc> = turn.try_get("updated_at")?;
    if turn_revision != turn_before {
        return Err(conflict("Coding reply changed during replay"));
    }
    let now = chrono::Utc::now();
    // This marks ONLY this reviewed execution's existing coding-agent turn.
    // Other older unseen turns and every future turn are deliberately untouched.
    sqlx::query(MARK_EXACT)
        .bind(now)
        .bind(p.execution_id)
        .execute(&mut *tx)
        .await?;
    let proof = json!({"protocol":PROTOCOL,"status":"applied","receipt_id":p.receipt_id,
        "workspace_id":w.id,"execution_id":p.execution_id,"message_index":p.message_index,
        "reply_sha256":p.reply_sha256,"hash_version":p.hash_version,"intent_version":p.intent_version,
        "turn_revision_before":turn_revision.to_rfc3339(),"marked_at":now.to_rfc3339()});
    sqlx::query("INSERT INTO workspace_review_receipts(receipt_id,event_key,workspace_id,execution_id,payload_hash,proof,created_at) VALUES (?,?,?,?,?,?,?)")
        .bind(&p.receipt_id).bind(event_key).bind(w.id).bind(p.execution_id).bind(payload_hash)
        .bind(proof.to_string()).bind(now).execute(&mut *tx).await?;
    tx.commit().await?;
    invalidate_workspace_summary_cache();
    Ok(Json(ApiResponse::success(proof)))
}

pub async fn hold<B: ReviewBackend>(
    Extension(w): Extension<Workspace>,
    State(d): State<B>,
    Json(p): Json<Hold>,
) -> Result<Json<ApiResponse<Value>>, ApiError> {
    p.source
        .validate()
        .map_err(|e| ApiError::BadRequest(e.into()))?;
    if p.event_id.is_empty() || p.event_id.len() > 1000 || p.expected_intent_version < 0 {
        return Err(ApiError::BadRequest("Invalid hold event".into()));
    }
    let body = serde_json::to_string(&p.source)
        .map_err(|_| ApiError::BadRequest("Hold encoding".into()))?;
    let mut tx = d.pool().begin().await?;
    lock(&mut tx, w.id).await?;
    if let Some(r) = sqlx::query(
        "SELECT held,source FROM workspace_review_hold_events WHERE workspace_id=? AND event_id=?",
    )
    .bind(w.id)
    .bind(&p.event_id)
    .fetch_optional(&mut *tx)
    .await?
    {
        if r.get::<bool, _>("held") != p.held || r.get::<String, _>("source") != body {
            return Err(conflict("Conflicting hold event"));
        }
    } else {
        let row = sqlx::query(GET_INTENT)
            .bind(w.id)
            .fetch_one(&mut *tx)
            .await?;
        if row.get::<i64, _>("version") != p.expected_intent_version {
            return Err(conflict("Hold intent version changed"));
        }
        sqlx::query(
            "UPDATE workspace_review_intent SET held=?,version=version+1 WHERE workspace_id=?",
        )
        .bind(p.held)
        .bind(w.id)
        .execute(&mut *tx)
        .await?;
        sqlx::query("INSERT INTO workspace_review_hold_events(workspace_id,event_id,held,source) VALUES (?,?,?,?)")
            .bind(w.id).bind(p.event_id).bind(p.held).bind(body).execute(&mut *tx).await?;
    }
    tx.commit().await?;
    // A review hold only prevents automatic reads; it never flips a false badge.
    state(Extension(w), State(d)).await
}

pub async fn manual_intent<B: ReviewBackend>(d: &B, wid: Uuid, read: bool) -> Result<(), ApiError> {
    // Existing human UI seen/unread routes must join the SAME writer transaction.
    let mut tx = d.pool().begin().await?;
    lock(&mut tx, wid).await?;
    sqlx::query("UPDATE workspace_review_intent SET held=?,version=version+1 WHERE workspace_id=?")
        .bind(!read)
        .bind(wid)
        .execute(&mut *tx)
        .await?;
    sqlx::query(if read { MANUAL_SEEN } else { MANUAL_UNREAD })
        .bind(chrono::Utc::now())
        .bind(wid)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    invalidate_workspace_summary_cache();
    Ok(())
}

#[cfg(test)]
#[path = "report_review_tests.rs"]
mod tests;
