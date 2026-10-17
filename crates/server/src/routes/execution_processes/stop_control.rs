//! Explicit execution stop: durable request identity, atomic terminal guard,
//! serialized with launches/completions. Never falls back to workspace Stop.
use std::future::Future;

use axum::{
    Extension, Json,
    extract::{Query, State},
};
use chrono::{DateTime, Utc};
use db::models::{
    execution_process::{ExecutionProcess, ExecutionProcessRunReason, ExecutionProcessStatus},
    session::Session,
};
use deployment::Deployment;
use serde::{Deserialize, Serialize};
use services::services::{admission, container::ContainerService};
use sqlx::SqlitePool;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct StopRequest {
    request_id: Uuid,
    execution_id: Uuid,
    session_id: Uuid,
    workspace_id: Uuid,
    expected_created_at: DateTime<Utc>,
    reason: String,
}

#[derive(Debug, Serialize)]
pub(crate) struct Receipt {
    request_id: Uuid,
    execution_id: Uuid,
    session_id: Uuid,
    workspace_id: Uuid,
    expected_created_at: DateTime<Utc>,
    reason: String,
    status: String,
    stopped: Option<bool>,
}

fn receipt(request: &StopRequest, status: &str) -> Receipt {
    Receipt {
        request_id: request.request_id,
        execution_id: request.execution_id,
        session_id: request.session_id,
        workspace_id: request.workspace_id,
        expected_created_at: request.expected_created_at,
        reason: request.reason.clone(),
        status: status.into(),
        stopped: if status == "unknown" {
            None
        } else {
            Some(status == "stopped")
        },
    }
}

async fn previous(pool: &SqlitePool, request: &StopRequest) -> Result<Option<Receipt>, ApiError> {
    let row: Option<(Uuid,Uuid,Uuid,String,String,String)> = sqlx::query_as(
        "SELECT execution_id,session_id,workspace_id,expected_created_at,reason,status FROM execution_stop_requests WHERE request_id=?")
        .bind(request.request_id).fetch_optional(pool).await?;
    let Some(row) = row else {
        return Ok(None);
    };
    if row.0 != request.execution_id
        || row.1 != request.session_id
        || row.2 != request.workspace_id
        || row.3 != request.expected_created_at.to_rfc3339()
        || row.4 != request.reason
    {
        return Err(ApiError::Conflict(
            "Stop request identity conflict; no stop sent".into(),
        ));
    }
    Ok(Some(receipt(request, &row.5)))
}

async fn target(
    pool: &SqlitePool,
    request: &StopRequest,
) -> Result<Option<ExecutionProcess>, ApiError> {
    let Some(process) = ExecutionProcess::find_by_id(pool, request.execution_id).await? else {
        return Ok(None);
    };
    let Some(session) = Session::find_by_id(pool, process.session_id).await? else {
        return Ok(None);
    };
    if process.session_id != request.session_id
        || session.workspace_id != request.workspace_id
        || process.created_at != request.expected_created_at
    {
        return Ok(None);
    }
    Ok(Some(process))
}

/// Caller holds admission::locked for the complete admission and dispatch.
/// The CAS also protects against an independent terminal-state writer. Reserve
/// unknown before side effects: a lost response/handler is never resent.
async fn admit<F, Fut>(
    pool: &SqlitePool,
    request: &StopRequest,
    dispatch: F,
) -> Result<Receipt, ApiError>
where
    F: FnOnce(ExecutionProcess) -> Fut,
    Fut: Future<Output = Result<(), ApiError>>,
{
    if request.request_id.is_nil()
        || request.execution_id.is_nil()
        || request.session_id.is_nil()
        || request.workspace_id.is_nil()
        || !matches!(request.reason.as_str(), "user_request" | "budget_exhausted")
    {
        return Err(ApiError::BadRequest(
            "Exact bounded stop identity and reason required".into(),
        ));
    }
    let inserted=sqlx::query("INSERT INTO execution_stop_requests(request_id,execution_id,session_id,workspace_id,expected_created_at,reason) VALUES(?,?,?,?,?,?) ON CONFLICT(request_id) DO NOTHING")
        .bind(request.request_id).bind(request.execution_id).bind(request.session_id).bind(request.workspace_id)
        .bind(request.expected_created_at.to_rfc3339()).bind(&request.reason).execute(pool).await?.rows_affected();
    if inserted == 0 {
        return previous(pool, request)
            .await?
            .ok_or_else(|| ApiError::Conflict("Stop receipt unavailable; do not resend".into()));
    }
    let status = match target(pool, request).await? {
        None => "target_mismatch",
        Some(process)
            if process.dropped
                || process.run_reason != ExecutionProcessRunReason::CodingAgent
                || process.status != ExecutionProcessStatus::Running =>
        {
            "not_running"
        }
        Some(process) => {
            // Claim terminal state atomically before invoking the existing exact
            // container stop. A completed turn can never be rewritten as killed.
            let claimed=sqlx::query("UPDATE execution_processes SET status='killed',exit_code=NULL,completed_at=strftime('%Y-%m-%d %H:%M:%f','now'),updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=? AND session_id=? AND status='running' AND dropped=0")
                .bind(process.id).bind(request.session_id).execute(pool).await?.rows_affected();
            if claimed == 0 {
                "not_running"
            } else if dispatch(process).await.is_ok() {
                "stopped"
            } else {
                "unknown"
            }
        }
    };
    sqlx::query("UPDATE execution_stop_requests SET status=? WHERE request_id=?")
        .bind(status)
        .bind(request.request_id)
        .execute(pool)
        .await?;
    Ok(receipt(request, status))
}

pub(crate) async fn inspect(
    Extension(process): Extension<ExecutionProcess>,
    State(deployment): State<DeploymentImpl>,
) -> Result<Json<ApiResponse<serde_json::Value>>, ApiError> {
    let session = Session::find_by_id(&deployment.db().pool, process.session_id)
        .await?
        .ok_or_else(|| ApiError::Conflict("Session unavailable".into()))?;
    Ok(Json(ApiResponse::success(
        serde_json::json!({"version":1,"execution_id":process.id,"session_id":session.id,
        "workspace_id":session.workspace_id,"expected_created_at":process.created_at,
        "execution_status":process.status,"run_reason":process.run_reason,"dropped":process.dropped,
        "serialized_admission":admission::automatic_git_sync(),
        "status": if !admission::automatic_git_sync() {"unsupported"} else if process.status==ExecutionProcessStatus::Running && process.run_reason==ExecutionProcessRunReason::CodingAgent && !process.dropped {"ready"} else {"not_running"}}),
    )))
}

pub(crate) async fn stop(
    Extension(process): Extension<ExecutionProcess>,
    State(deployment): State<DeploymentImpl>,
    Json(request): Json<StopRequest>,
) -> Result<Json<ApiResponse<Receipt>>, ApiError> {
    if process.id != request.execution_id {
        return Err(ApiError::BadRequest("Execution path/body mismatch".into()));
    }
    // Never silently enable a scheduling/configuration policy. Without the
    // existing shared serialization guarantee this capability is unavailable.
    if !admission::automatic_git_sync() {
        return Err(ApiError::Conflict(
            "Exact stop requires serialized admission".into(),
        ));
    }
    admission::locked(async {
        let deployment = &deployment;
        let result = admit(&deployment.db().pool, &request, |current| async move {
            deployment
                .container()
                .stop_execution(&current, ExecutionProcessStatus::Killed)
                .await?;
            Ok(())
        })
        .await?;
        Ok(Json(ApiResponse::success(result)))
    })
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct ReceiptQuery {
    request_id: Uuid,
}

pub(crate) async fn read_receipt(
    Extension(process): Extension<ExecutionProcess>,
    State(deployment): State<DeploymentImpl>,
    Query(ReceiptQuery { request_id }): Query<ReceiptQuery>,
) -> Result<Json<ApiResponse<Option<Receipt>>>, ApiError> {
    let execution_id = process.id;
    let row:Option<(Uuid,Uuid,Uuid,DateTime<Utc>,String)>=sqlx::query_as("SELECT execution_id,session_id,workspace_id,expected_created_at,reason FROM execution_stop_requests WHERE request_id=? AND execution_id=?")
        .bind(request_id).bind(execution_id).fetch_optional(&deployment.db().pool).await?;
    let result =
        if let Some((execution_id, session_id, workspace_id, expected_created_at, reason)) = row {
            previous(
                &deployment.db().pool,
                &StopRequest {
                    request_id,
                    execution_id,
                    session_id,
                    workspace_id,
                    expected_created_at,
                    reason,
                },
            )
            .await?
        } else {
            None
        };
    Ok(Json(ApiResponse::success(result)))
}

#[cfg(test)]
mod tests;
