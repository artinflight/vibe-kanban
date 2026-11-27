//! Durable archive revival admission. Physical movement belongs to the pinned
//! lifecycle driver; ordinary execution always uses the existing launch path.
use std::future::Future;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::{Row, SqlitePool};
use ts_rs::TS;
use uuid::Uuid;

pub mod runtime;

#[derive(Clone, Debug, Serialize, Deserialize, TS)]
pub struct RevivalStatus {
    pub request_id: Uuid,
    pub session_id: Uuid,
    pub state: String,
    pub error: Option<String>,
}

#[derive(Clone, Debug)]
pub struct Reservation {
    pub workspace: Uuid,
    pub session: Uuid,
    pub request: Uuid,
    pub execution: Uuid,
    pub payload: Value,
}

tokio::task_local! { static DISPATCH: Reservation; }

pub fn in_dispatch() -> bool {
    DISPATCH.try_with(|_| true).unwrap_or(false)
}

pub fn execution_id(workspace: Uuid, session: Uuid) -> Result<Option<Uuid>, String> {
    DISPATCH
        .try_with(|r| {
            if (r.workspace, r.session) != (workspace, session) {
                Err("Archive revival dispatch owner differs".into())
            } else {
                Ok(Some(r.execution))
            }
        })
        .unwrap_or(Ok(None))
}

pub async fn dispatch_scope<T>(reservation: Reservation, work: impl Future<Output = T>) -> T {
    DISPATCH.scope(reservation, work).await
}

pub async fn status(
    pool: &SqlitePool,
    session: Uuid,
) -> Result<Option<RevivalStatus>, sqlx::Error> {
    let row = sqlx::query("SELECT request_id,session_id,state,error FROM workspace_archive_inputs WHERE session_id=? AND state NOT IN ('dispatched','cancelled') ORDER BY rowid LIMIT 1")
        .bind(session).fetch_optional(pool).await?;
    row.map(|r| {
        Ok(RevivalStatus {
            request_id: r.try_get("request_id")?,
            session_id: r.try_get("session_id")?,
            state: r.try_get("state")?,
            error: r.try_get("error")?,
        })
    })
    .transpose()
}

/// Called before waiting for custody or network recovery. The exact request and
/// settings survive disconnects and atomically revoke any cold backup exclusion.
pub async fn retain(
    pool: &SqlitePool,
    workspace: Uuid,
    session: Uuid,
    request: Uuid,
    payload: &Value,
) -> Result<RevivalStatus, anyhow::Error> {
    let mut tx = pool.begin_with("BEGIN IMMEDIATE").await?;
    if let Some(row) = sqlx::query("SELECT workspace_id,session_id,payload,state,error FROM workspace_archive_inputs WHERE request_id=?")
        .bind(request).fetch_optional(&mut *tx).await? {
        let saved: Value = serde_json::from_str(row.try_get("payload")?)?;
        if row.try_get::<Uuid,_>("workspace_id")? != workspace || row.try_get::<Uuid,_>("session_id")? != session || saved != *payload {
            anyhow::bail!("Archive request ID was reused with different input or settings");
        }
        return Ok(RevivalStatus { request_id:request, session_id:session, state:row.try_get("state")?, error:row.try_get("error")? });
    }
    let owner: Option<Uuid> = sqlx::query_scalar("SELECT workspace_id FROM sessions WHERE id=?")
        .bind(session)
        .fetch_optional(&mut *tx)
        .await?;
    if owner != Some(workspace) {
        anyhow::bail!("Archive session belongs to a different workspace");
    }
    let phase: Option<String> =
        sqlx::query_scalar("SELECT phase FROM workspace_archive_state WHERE workspace_id=?")
            .bind(workspace)
            .fetch_optional(&mut *tx)
            .await?;
    let state = if phase.as_deref().is_none_or(|p| p == "active") {
        "ready"
    } else {
        "waiting_restore"
    };
    sqlx::query("INSERT INTO workspace_archive_inputs(request_id,workspace_id,session_id,payload,state) VALUES(?,?,?,?,?)")
        .bind(request).bind(workspace).bind(session).bind(serde_json::to_string(payload)?).bind(state).execute(&mut *tx).await?;
    sqlx::query("UPDATE workspaces SET archived=0 WHERE id=?")
        .bind(workspace)
        .execute(&mut *tx)
        .await?;
    tx.commit().await?;
    Ok(RevivalStatus {
        request_id: request,
        session_id: session,
        state: state.into(),
        error: None,
    })
}

pub async fn reserve(pool: &SqlitePool, request: Uuid) -> Result<Reservation, anyhow::Error> {
    let mut tx = pool.begin_with("BEGIN IMMEDIATE").await?;
    let row = sqlx::query("SELECT i.workspace_id,i.session_id,i.payload,i.state,s.phase FROM workspace_archive_inputs i LEFT JOIN workspace_archive_state s USING(workspace_id) WHERE i.request_id=?")
        .bind(request).fetch_one(&mut *tx).await?;
    if row.try_get::<String, _>("state")? != "ready"
        || row
            .try_get::<Option<String>, _>("phase")?
            .as_deref()
            .is_some_and(|p| p != "active")
    {
        anyhow::bail!("Archive input is not ready or dispatch already reserved");
    }
    let session: Uuid = row.try_get("session_id")?;
    let first: Uuid = sqlx::query_scalar("SELECT request_id FROM workspace_archive_inputs WHERE session_id=? AND state NOT IN ('dispatched','cancelled') ORDER BY rowid LIMIT 1")
        .bind(session).fetch_one(&mut *tx).await?;
    if first != request {
        anyhow::bail!("An earlier archive input still needs reconciliation");
    }
    let reservation = Reservation {
        workspace: row.try_get("workspace_id")?,
        session,
        request,
        execution: Uuid::new_v4(),
        payload: serde_json::from_str(row.try_get("payload")?)?,
    };
    sqlx::query("UPDATE workspace_archive_inputs SET state='dispatching',execution_id=?,error=NULL WHERE request_id=?")
        .bind(reservation.execution).bind(request).execute(&mut *tx).await?;
    tx.commit().await?;
    Ok(reservation)
}

/// A restart or lost HTTP receipt can acknowledge only the already reserved
/// execution. No timeout or missing observation authorizes dispatching it again.
pub async fn reconcile(pool: &SqlitePool, request: Uuid) -> Result<bool, sqlx::Error> {
    let changed = sqlx::query("UPDATE workspace_archive_inputs SET state='dispatched',error=NULL WHERE request_id=? AND state IN ('dispatching','held') AND EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=workspace_archive_inputs.execution_id AND e.session_id=workspace_archive_inputs.session_id)")
        .bind(request).execute(pool).await?.rows_affected();
    Ok(changed == 1)
}

pub async fn hold(pool: &SqlitePool, request: Uuid, message: &str) -> Result<(), sqlx::Error> {
    sqlx::query("UPDATE workspace_archive_inputs SET state='held',error=? WHERE request_id=? AND state='dispatching'")
        .bind(message).bind(request).execute(pool).await?;
    Ok(())
}

pub async fn cancel(pool: &SqlitePool, session: Uuid) -> Result<(), anyhow::Error> {
    let mut tx = pool.begin_with("BEGIN IMMEDIATE").await?;
    let uncertain: bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspace_archive_inputs WHERE session_id=? AND state IN ('dispatching','held'))")
        .bind(session).fetch_one(&mut *tx).await?;
    if uncertain {
        anyhow::bail!("Reserved archive input must be reconciled before cancellation");
    }
    sqlx::query("UPDATE workspace_archive_inputs SET state='cancelled' WHERE session_id=? AND state IN ('ready','waiting_restore')")
        .bind(session).execute(&mut *tx).await?;
    tx.commit().await?;
    Ok(())
}

#[cfg(test)]
mod tests;
