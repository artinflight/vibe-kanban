//! Immutable backend evidence; opaque references are never client authority.
use super::*;
#[derive(Clone, Debug, FromRow)]
pub struct Checkpoint {
    pub reference: String,
    pub workspace_id: Uuid,
    pub source_execution_id: Uuid,
    pub destination_session_id: Uuid,
    pub target_token: String,
    pub work_id: String,
    pub owner_generation: String,
    pub legacy_transition: Option<String>,
    pub evidence: String,
    pub valid_until_ms: i64,
    pub claimed_request: Option<Uuid>,
}
pub async fn get(pool: &SqlitePool, reference: &str) -> Result<Option<Checkpoint>, sqlx::Error> {
    sqlx::query_as("SELECT * FROM provider_continuation_checkpoints WHERE reference=?")
        .bind(reference)
        .fetch_optional(pool)
        .await
}
pub async fn publish(pool: &SqlitePool, c: &Checkpoint) -> Result<(), sqlx::Error> {
    sqlx::query("INSERT INTO provider_continuation_checkpoints(reference,workspace_id,source_execution_id,destination_session_id,target_token,work_id,owner_generation,legacy_transition,evidence,valid_until_ms) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(reference) DO NOTHING")
        .bind(&c.reference).bind(c.workspace_id).bind(c.source_execution_id).bind(c.destination_session_id)
        .bind(&c.target_token).bind(&c.work_id).bind(&c.owner_generation).bind(&c.legacy_transition)
        .bind(&c.evidence).bind(c.valid_until_ms).execute(pool).await?;
    let stored = get(pool, &c.reference)
        .await?
        .ok_or_else(|| sqlx::Error::Protocol("Checkpoint missing".into()))?;
    if stored.evidence != c.evidence
        || stored.target_token != c.target_token
        || stored.workspace_id != c.workspace_id
        || stored.source_execution_id != c.source_execution_id
        || stored.destination_session_id != c.destination_session_id
        || stored.work_id != c.work_id
        || stored.owner_generation != c.owner_generation
        || stored.legacy_transition != c.legacy_transition
        || stored.valid_until_ms != c.valid_until_ms
    {
        return Err(sqlx::Error::Protocol(
            "Conflicting checkpoint identity".into(),
        ));
    }
    Ok(())
}
pub(super) async fn claim(
    tx: &mut sqlx::Transaction<'_, sqlx::Sqlite>,
    reference: &str,
    r: &Receipt,
    now: i64,
) -> Result<(), sqlx::Error> {
    let changed=sqlx::query("UPDATE provider_continuation_checkpoints SET claimed_request=? WHERE reference=? AND claimed_request IS NULL AND workspace_id=? AND destination_session_id=? AND target_token=? AND valid_until_ms>? AND source_execution_id=(SELECT e.id FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.run_reason='codingagent' AND e.dropped=0 ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1) AND EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=source_execution_id AND e.status IN ('completed','failed','killed'))")
        .bind(r.request_id).bind(reference).bind(r.workspace_id).bind(r.session_id).bind(&r.state_token).bind(now).bind(r.workspace_id)
        .execute(&mut **tx).await?.rows_affected();
    if changed != 1 {
        return Err(sqlx::Error::Protocol(
            "stale_checkpoint_or_already_claimed".into(),
        ));
    }
    // Only the exact terminal/reconciled legacy transition may transfer. A
    // reserved/dispatching/held predecessor is never converted into success.
    sqlx::query("UPDATE provider_handoff_reservations SET state='released',reason='atomic trusted continuation checkpoint' WHERE workspace_id=? AND state='checkpoint_required' AND EXISTS(SELECT 1 FROM provider_continuation_checkpoints c WHERE c.reference=? AND c.claimed_request=? AND c.legacy_transition=transition_id AND c.source_execution_id=next_execution_id)")
        .bind(r.workspace_id).bind(reference).bind(r.request_id).execute(&mut **tx).await?;
    let released=sqlx::query("UPDATE provider_failover_activations SET state='released',reason='atomic trusted continuation checkpoint' WHERE workspace_id=? AND state='active' AND EXISTS(SELECT 1 FROM provider_continuation_checkpoints c WHERE c.reference=? AND c.claimed_request=? AND c.work_id=provider_failover_activations.work_id AND c.owner_generation=provider_failover_activations.owner_generation) AND NOT EXISTS(SELECT 1 FROM provider_handoff_reservations h WHERE h.workspace_id=? AND h.state!='released')")
        .bind(r.workspace_id).bind(reference).bind(r.request_id).bind(r.workspace_id).execute(&mut **tx).await?.rows_affected();
    if released != 1 {
        return Err(sqlx::Error::Protocol(
            "trusted_checkpoint_owner_changed".into(),
        ));
    }
    Ok(())
}

/// Once a bridge moved source ownership, an early failure also retains the new
/// owner. Never erase the only fence merely because spawn has not acknowledged.
pub async fn hold(pool: &SqlitePool, request: Uuid) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE provider_continuation_receipts SET status='unknown',reason='checkpoint transfer requires exact recovery; no replay' WHERE request_id=? AND status IN ('reserved','dispatching') AND ownership='held'")
        .bind(request).execute(pool).await?;
    Ok(())
}

/// Discovery is a scoped hint, not readiness/authority. The supplied reference is
/// fully verified again by target/POST and the after-setup/native launch fences.
pub async fn available(
    pool: &SqlitePool,
    session: Uuid,
    token: &str,
    now: i64,
) -> Result<Option<String>, sqlx::Error> {
    sqlx::query_scalar("SELECT reference FROM provider_continuation_checkpoints WHERE destination_session_id=? AND target_token=? AND claimed_request IS NULL AND valid_until_ms>? ORDER BY valid_until_ms DESC,reference LIMIT 1")
        .bind(session).bind(token).bind(now).fetch_optional(pool).await
}
