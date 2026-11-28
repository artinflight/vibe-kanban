//! Durable workspace reservation shared with the ordinary execution INSERT path.
use sqlx::SqlitePool;
use uuid::Uuid;

pub struct Reservation<'a> {
    pub transition: &'a str,
    pub workspace: Uuid,
    pub previous: Uuid,
    pub session: Uuid,
    pub execution: Uuid,
    pub action: &'a str,
    pub snapshot: &'a str,
    pub ownership_fence: &'a str,
    pub executor: &'a str,
    pub previous_transition: Option<&'a str>,
    pub working_dir: Option<&'a str>,
}
/// Session and exclusive reservation commit together. SQLite triggers reject a
/// competing predecessor, running owner or reused native/session execution path.
pub async fn reserve(pool: &SqlitePool, r: Reservation<'_>) -> Result<(), sqlx::Error> {
    if !["CLAUDE_CODE", "CODEX"].contains(&r.executor) {
        return Err(sqlx::Error::Protocol("Unsupported provider".into()));
    }
    let mut tx = pool.begin().await?;
    if let Some(previous) = r.previous_transition {
        // Atomic transfer, never an unowned gap. The next INSERT failing rolls this
        // release back. Unknown/held/running predecessors cannot transfer.
        let changed=sqlx::query("UPDATE provider_handoff_reservations SET state='released',reason='atomic verified-checkpoint successor' WHERE transition_id=? AND workspace_id=? AND next_execution_id=? AND state='checkpoint_required'")
            .bind(previous).bind(r.workspace).bind(r.previous).execute(&mut *tx).await?.rows_affected();
        if changed != 1 {
            return Err(sqlx::Error::Protocol(
                "Previous provider owner is not reconciled".into(),
            ));
        }
    }
    sqlx::query("INSERT INTO sessions(id,workspace_id,executor,name,agent_working_dir) VALUES(?,?,?,'AutoSwitch supervised handoff',?)")
        .bind(r.session).bind(r.workspace).bind(r.executor).bind(r.working_dir).execute(&mut *tx).await?;
    sqlx::query("INSERT INTO provider_handoff_reservations(transition_id,workspace_id,previous_execution_id,next_session_id,next_execution_id,expected_action,snapshot_receipt,ownership_fence,state) VALUES(?,?,?,?,?,?,?,?,'reserved')")
        .bind(r.transition).bind(r.workspace).bind(r.previous).bind(r.session).bind(r.execution)
        .bind(r.action).bind(r.snapshot).bind(r.ownership_fence).execute(&mut *tx).await?;
    tx.commit().await
}
pub async fn dispatching(pool: &SqlitePool, transition: &str) -> Result<bool, sqlx::Error> {
    Ok(sqlx::query("UPDATE provider_handoff_reservations SET state='dispatching' WHERE transition_id=? AND state='reserved'")
        .bind(transition).execute(pool).await?.rows_affected()==1)
}
pub async fn outcome(
    pool: &SqlitePool,
    transition: &str,
    state: &str,
    reason: &str,
) -> Result<(), sqlx::Error> {
    if !["running", "held", "checkpoint_required"].contains(&state) {
        return Err(sqlx::Error::Protocol("Unsupported handoff outcome".into()));
    }
    let changed=sqlx::query("UPDATE provider_handoff_reservations SET state=CASE WHEN state IN ('reserved','dispatching') THEN ? ELSE state END,reason=CASE WHEN state IN ('reserved','dispatching') THEN ? ELSE reason END WHERE transition_id=? AND state!='released'")
        .bind(state).bind(reason).bind(transition).execute(pool).await?.rows_affected();
    if changed != 1 {
        return Err(sqlx::Error::Protocol(
            "Provider ownership receipt missing".into(),
        ));
    }
    Ok(())
}

/// Terminal monitor records a checkpoint requirement, never releases/retries.
pub async fn terminal(pool: &SqlitePool, execution: Uuid, safe: bool) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE provider_handoff_reservations SET state=?,reason='terminal monitor: fresh checkpoint/reset/admission still required' WHERE next_execution_id=? AND state!='released'")
        .bind(if safe {"checkpoint_required"}else{"held"}).bind(execution).execute(pool).await?;
    Ok(())
}

#[derive(Clone, Debug, sqlx::FromRow)]
pub struct Activation {
    pub workspace_id: Uuid,
    pub work_id: String,
    pub initial_execution_id: Uuid,
    pub journal_root: String,
    pub source_receipt: String,
    pub owner_generation: String,
    pub state: String,
    pub reason: String,
}
pub async fn activation(
    pool: &SqlitePool,
    workspace: Uuid,
) -> Result<Option<Activation>, sqlx::Error> {
    sqlx::query_as(
        "SELECT * FROM provider_failover_activations WHERE workspace_id=? AND state!='released'",
    )
    .bind(workspace)
    .fetch_optional(pool)
    .await
}
pub async fn activate(pool: &SqlitePool, a: &Activation) -> Result<(), sqlx::Error> {
    sqlx::query("INSERT INTO provider_failover_activations(workspace_id,work_id,initial_execution_id,journal_root,source_receipt,owner_generation,state) VALUES(?,?,?,?,?,?,'active')")
        .bind(a.workspace_id).bind(&a.work_id).bind(a.initial_execution_id).bind(&a.journal_root).bind(&a.source_receipt).bind(&a.owner_generation).execute(pool).await?;
    Ok(())
}
#[derive(Clone, Debug, sqlx::FromRow)]
pub struct Recovery {
    pub transition_id: String,
    pub workspace_id: Uuid,
    pub previous_execution_id: Uuid,
    pub next_session_id: Uuid,
    pub next_execution_id: Uuid,
    pub expected_action: String,
    pub state: String,
}
pub async fn owner(pool: &SqlitePool, workspace: Uuid) -> Result<Option<Recovery>, sqlx::Error> {
    sqlx::query_as("SELECT transition_id,workspace_id,previous_execution_id,next_session_id,next_execution_id,expected_action,state FROM provider_handoff_reservations WHERE workspace_id=? AND state!='released'")
        .bind(workspace).fetch_optional(pool).await
}
/// Reconcile exact stored IDs against actual execution rows. Absence never means
/// successful admission or permission to retry. Terminal safety is independently
/// verified by the host; no acknowledgement can overwrite it later.
pub async fn reconcile(
    pool: &SqlitePool,
    r: &Recovery,
    terminal_safe: bool,
) -> Result<&'static str, sqlx::Error> {
    let actual: Option<(Uuid, String, String)> = sqlx::query_as(
        "SELECT session_id,status,executor_action FROM execution_processes WHERE id=?",
    )
    .bind(r.next_execution_id)
    .fetch_optional(pool)
    .await?;
    let state = match actual {
        Some((session, status, action))
            if session == r.next_session_id && action == r.expected_action =>
        {
            match status.as_str() {
                "running" => return Ok("running_outcome_unsettled"),
                "completed" | "failed" | "killed" if terminal_safe => "checkpoint_required",
                _ => "held",
            }
        }
        _ => "held",
    };
    sqlx::query("UPDATE provider_handoff_reservations SET state=?,reason='reconciled exact execution; no admission reconstructed or launch replayed' WHERE transition_id=? AND next_execution_id=? AND state!='released'")
        .bind(state).bind(&r.transition_id).bind(r.next_execution_id).execute(pool).await?;
    Ok(if state == "checkpoint_required" {
        "terminal_checkpoint_verified"
    } else {
        "dispatch_outcome_unknown"
    })
}

/// Explicit verified completion releases DB ownership only after the controller
/// completion is durable. Journal/rows remain preserved; no deletion or lease.
pub async fn release(
    pool: &SqlitePool,
    workspace: Uuid,
    work: &str,
    execution: Uuid,
    receipt: &str,
) -> Result<(), sqlx::Error> {
    if receipt.is_empty() {
        return Err(sqlx::Error::Protocol("Completion receipt required".into()));
    }
    let mut tx = pool.begin().await?;
    let unsafe_owner: (i64,)=sqlx::query_as("SELECT count(*) FROM provider_handoff_reservations WHERE workspace_id=? AND state!='released' AND (next_execution_id!=? OR state!='checkpoint_required')")
        .bind(workspace).bind(execution).fetch_one(&mut *tx).await?;
    if unsafe_owner.0 != 0 {
        return Err(sqlx::Error::Protocol(
            "Unreconciled owner cannot release".into(),
        ));
    }
    sqlx::query("UPDATE provider_handoff_reservations SET state='released',reason=? WHERE workspace_id=? AND next_execution_id=? AND state='checkpoint_required'")
        .bind(receipt).bind(workspace).bind(execution).execute(&mut *tx).await?;
    let changed=sqlx::query("UPDATE provider_failover_activations SET state='released',reason=? WHERE workspace_id=? AND work_id=?")
        .bind(receipt).bind(workspace).bind(work).execute(&mut *tx).await?.rows_affected();
    if changed != 1 {
        return Err(sqlx::Error::Protocol(
            "Activation missing during completion".into(),
        ));
    }
    tx.commit().await
}
