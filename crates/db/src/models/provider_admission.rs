//! Durable continuation receipts. No expiry, replay, provider selector or scheduler.
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

pub mod checkpoint;

#[derive(Debug, Clone, FromRow)]
pub struct Receipt {
    pub request_id: Uuid,
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub executor: String,
    pub intent_sha256: String,
    pub configuration_sha256: String,
    pub intent: String,
    pub state_token: String,
    pub predecessor_execution_id: Option<Uuid>,
    pub execution_id: Uuid,
    pub expected_action: String,
    pub status: String,
    pub ownership: String,
    pub reason: String,
}
pub async fn get(pool: &SqlitePool, request: Uuid) -> Result<Option<Receipt>, sqlx::Error> {
    sqlx::query_as("SELECT request_id,workspace_id,session_id,executor,intent_sha256,configuration_sha256,intent,state_token,predecessor_execution_id,execution_id,expected_action,status,ownership,reason FROM provider_continuation_receipts WHERE request_id=?")
        .bind(request).fetch_optional(pool).await
}
pub async fn owner(pool: &SqlitePool, workspace: Uuid) -> Result<Option<Receipt>, sqlx::Error> {
    sqlx::query_as("SELECT request_id,workspace_id,session_id,executor,intent_sha256,configuration_sha256,intent,state_token,predecessor_execution_id,execution_id,expected_action,status,ownership,reason FROM provider_continuation_receipts WHERE workspace_id=? AND ownership='held'")
        .bind(workspace).fetch_optional(pool).await
}
/// Bind only after Recommend resolution; one CAS grants one common launch.
pub async fn bind_action(
    pool: &SqlitePool,
    request: Uuid,
    action: &str,
) -> Result<bool, sqlx::Error> {
    Ok(sqlx::query("UPDATE provider_continuation_receipts SET status='dispatching',expected_action=? WHERE request_id=? AND status='reserved' AND ownership='held'")
        .bind(action).bind(request).execute(pool).await?.rows_affected()==1)
}
/// Roll verified predecessor ownership forward and claim the successor atomically.
/// Caller has just verified native/capture/effect terminal evidence under admission.
pub async fn reserve_after_checkpoint(
    pool: &SqlitePool,
    r: &Receipt,
    previous: Option<&Receipt>,
) -> Result<bool, sqlx::Error> {
    reserve_with_checkpoint(pool, r, previous, None, 0).await
}
/// Claim checkpoint, release only its exact proved source, and reserve the new
/// owner in ONE SQLite transaction. Failed inserts restore every previous fence.
pub async fn reserve_with_checkpoint(
    pool: &SqlitePool,
    r: &Receipt,
    previous: Option<&Receipt>,
    checkpoint: Option<&str>,
    now_ms: i64,
) -> Result<bool, sqlx::Error> {
    let mut tx = pool.begin().await?;
    if let Some(reference) = checkpoint {
        checkpoint::claim(&mut tx, reference, r, now_ms).await?;
    }
    if let Some(old) = previous {
        let count=sqlx::query("UPDATE provider_continuation_receipts SET ownership='released' WHERE request_id=? AND execution_id=? AND status='admitted' AND ownership='held' AND EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=execution_id AND e.status IN ('completed','failed','killed'))")
            .bind(old.request_id).bind(old.execution_id).execute(&mut *tx).await?.rows_affected();
        if count != 1 {
            return Err(sqlx::Error::Protocol(
                "Uncertain continuation ownership; reconcile exact receipt".into(),
            ));
        }
    }
    let count=sqlx::query("INSERT INTO provider_continuation_receipts(request_id,workspace_id,session_id,executor,intent_sha256,configuration_sha256,intent,state_token,predecessor_execution_id,execution_id,expected_action) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(request_id) DO NOTHING")
        .bind(r.request_id).bind(r.workspace_id).bind(r.session_id).bind(&r.executor).bind(&r.intent_sha256)
        .bind(&r.configuration_sha256).bind(&r.intent).bind(&r.state_token).bind(r.predecessor_execution_id)
        .bind(r.execution_id).bind(&r.expected_action).execute(&mut *tx).await?.rows_affected();
    if count == 0 {
        tx.rollback().await?;
        return Ok(false);
    }
    tx.commit().await?;
    Ok(true)
}
/// An error after dispatch is uncertain, never a negative delivery receipt.
/// Only the owning caller acknowledges a successful spawn; a database row alone
/// after process restart cannot reconstruct that acknowledgement.
pub async fn outcome(pool: &SqlitePool, request: Uuid, admitted: bool) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE provider_continuation_receipts SET status=? WHERE request_id=? AND status='dispatching'")
        .bind(if admitted {"admitted"} else {"unknown"}).bind(request).execute(pool).await?;
    Ok(())
}
pub async fn reject(pool: &SqlitePool, request: Uuid, reason: &str) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE provider_continuation_receipts SET status='rejected',ownership='released',reason=? WHERE request_id=? AND status='reserved'")
        .bind(reason).bind(request).execute(pool).await?;
    Ok(())
}

#[cfg(test)]
mod tests;
