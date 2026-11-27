//! Ordinary backend archive/revival integration. Physical jobs use the pinned
//! driver; retained user input resumes through the existing follow-up handler.
use axum::{Extension, Json, Router, extract::State, routing::post};
use db::models::{session::Session, workspace::Workspace};
use deployment::Deployment;
use services::services::{workspace_archive as archive, workspace_archive::runtime};
use tokio_util::sync::CancellationToken;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{
    DeploymentImpl,
    error::ApiError,
    routes::sessions::{CreateFollowUpAttempt, follow_up_admitted},
};

pub fn workspace_routes() -> Router<DeploymentImpl> {
    Router::new().route("/archive-restore", post(restore_for_history))
}

async fn restore_for_history(
    Extension(workspace): Extension<Workspace>,
    State(deployment): State<DeploymentImpl>,
) -> Result<Json<ApiResponse<bool>>, ApiError> {
    let runtime = runtime::configured()
        .map_err(|e| ApiError::Conflict(e.to_string()))?
        .ok_or_else(|| ApiError::Conflict("Workspace archival is not configured".into()))?;
    if runtime.config.role != runtime::Role::Writer {
        return Err(ApiError::Conflict(
            "Restoration belongs to the writer".into(),
        ));
    }
    let _guard = runtime::readable(&deployment.db().pool, workspace.id)
        .await
        .map_err(|e| ApiError::Conflict(e.to_string()))?;
    Ok(Json(ApiResponse::success(true)))
}

pub fn start(deployment: DeploymentImpl, shutdown: CancellationToken) -> anyhow::Result<()> {
    let Some(runtime) = runtime::configured()? else {
        return Ok(());
    };
    if runtime.config.role != runtime::Role::Writer {
        return Ok(());
    }
    if deployment
        .db()
        .pool
        .connect_options()
        .get_filename()
        .canonicalize()?
        != runtime.config.database.canonicalize()?
    {
        anyhow::bail!("Archive worker does not own this serving database");
    }
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(5));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
        loop {
            tokio::select! { biased; _=shutdown.cancelled()=>break, _=interval.tick()=>{} }
            // Cancellation drops the driver's child with kill_on_drop. Its SQL
            // operation intent and exact pending input survive for reconciliation.
            tokio::select! { biased; _=shutdown.cancelled()=>break, result=tick(&deployment,&runtime)=>{
                if let Err(error)=result {tracing::warn!("Workspace archive remains pending: {error:#}");}
            }}
        }
    });
    Ok(())
}

async fn tick(deployment: &DeploymentImpl, runtime: &runtime::Runtime) -> anyhow::Result<()> {
    let pool = &deployment.db().pool;
    let uncertain: Vec<Uuid> = sqlx::query_scalar(
        "SELECT request_id FROM workspace_archive_inputs WHERE state IN ('dispatching','held')",
    )
    .fetch_all(pool)
    .await?;
    for request in uncertain {
        archive::reconcile(pool, request).await?;
    }
    let ready:Option<(Uuid,Uuid)>=sqlx::query_as("SELECT i.request_id,i.workspace_id FROM workspace_archive_inputs i WHERE i.state='ready' AND NOT EXISTS(SELECT 1 FROM workspace_archive_inputs earlier WHERE earlier.session_id=i.session_id AND earlier.rowid<i.rowid AND earlier.state NOT IN ('dispatched','cancelled')) AND NOT EXISTS(SELECT 1 FROM execution_processes e WHERE e.session_id=i.session_id AND e.status='running') ORDER BY i.rowid LIMIT 1")
        .fetch_optional(pool).await?;
    if let Some((request, workspace)) = ready {
        let _guard = runtime.readable(workspace).await?;
        services::services::admission::run(services::services::admission::owner(workspace,async {
            let reservation=archive::reserve(pool,request).await?;
            let session=Session::find_by_id(pool,reservation.session).await?.ok_or_else(||anyhow::anyhow!("Revival session no longer exists"))?;
            let payload:CreateFollowUpAttempt=serde_json::from_value(reservation.payload.clone())?;
            let result=archive::dispatch_scope(reservation.clone(),follow_up_admitted(Extension(session),State(deployment.clone()),Json(payload))).await;
            if !archive::reconcile(pool,request).await? {
                let message=match result {
                    Ok(response) if response.0.is_success()=>"Ordinary execution receipt did not match the reserved archive input".to_owned(),
                    Ok(_)=>"Ordinary admission deferred this input; reconcile its reservation before another dispatch".to_owned(),
                    Err(error)=>format!("Ordinary admission needs attention: {error}"),
                };
                archive::hold(pool,request,&message).await?;
            }
            Ok::<_,anyhow::Error>(())
        })).await?;
        return Ok(());
    }
    // Ready messages run before network recovery; restore intents precede archival. One physical workspace is
    // handled at a time; normal requests for other workspaces stay concurrent.
    let restore:Option<Uuid>=sqlx::query_scalar("SELECT w.id FROM workspaces w LEFT JOIN workspace_archive_state s ON s.workspace_id=w.id WHERE EXISTS(SELECT 1 FROM workspace_archive_reads r WHERE r.workspace_id=w.id) OR EXISTS(SELECT 1 FROM workspace_archive_inputs i WHERE i.workspace_id=w.id AND i.state='waiting_restore') ORDER BY coalesce(s.updated_at,''),w.id LIMIT 1")
        .fetch_optional(pool).await?;
    if let Some(workspace) = restore {
        sqlx::query("UPDATE workspace_archive_state SET updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE workspace_id=?")
            .bind(workspace).execute(pool).await?;
        let _guard = runtime.readable(workspace).await?;
        return Ok(());
    }
    let candidate:Option<Uuid>=sqlx::query_scalar("SELECT r.workspace_id FROM workspace_archive_requests r JOIN workspaces w ON w.id=r.workspace_id LEFT JOIN workspace_archive_state s ON s.workspace_id=r.workspace_id WHERE w.archived=1 AND w.pinned=0 AND r.requested_state='archived' AND (s.phase IS NULL OR s.phase IN ('active','preparing','verified','retiring')) AND NOT EXISTS(SELECT 1 FROM workspace_archive_inputs i WHERE i.workspace_id=w.id AND i.state NOT IN ('dispatched','cancelled')) ORDER BY coalesce(r.last_attempted_at,''),r.updated_at,w.id LIMIT 1")
        .fetch_optional(pool).await?;
    if let Some(workspace) = candidate {
        sqlx::query("UPDATE workspace_archive_requests SET last_attempted_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE workspace_id=?")
            .bind(workspace).execute(pool).await?;
        runtime.helper(workspace, "archive").await?;
    }
    Ok(())
}
