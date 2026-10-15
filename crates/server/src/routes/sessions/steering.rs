//! Explicit, identity-fenced steering. The legacy UI queue/takeover path is
//! deliberately separate: this endpoint cannot launch, stop or queue work.
use std::future::Future;

use axum::{
    Extension, Json, Router,
    extract::{DefaultBodyLimit, Path, Query, Request, State},
    middleware::{Next, from_fn_with_state},
    response::Response,
    routing::{get, post},
};
use db::models::{
    execution_process::{ExecutionProcess, ExecutionProcessRunReason, ExecutionProcessStatus},
    session::Session,
};
use deployment::Deployment;
use executors::executors::BaseCodingAgent;
use serde::{Deserialize, Serialize};
use services::services::{admission, container::ContainerService, original_worker};
use sha2::{Digest, Sha256};
use sqlx::SqlitePool;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct SteerRequest {
    pub request_id: Uuid,
    pub execution_id: Uuid,
    pub thread_id: String,
    pub turn_id: String,
    pub message: String,
}

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(crate) enum Status {
    Steered,
    NotRunning,
    NotReady,
    UnsupportedExecutor,
    TargetMismatch,
    ScheduledWork,
    Blocked,
    Unknown,
}

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct Receipt {
    pub request_id: Uuid,
    pub session_id: Uuid,
    pub execution_id: Uuid,
    pub thread_id: String,
    pub turn_id: String,
    pub status: Status,
    pub delivered: Option<bool>,
    pub message_sha256: String,
}

fn status_name(status: &Status) -> &'static str {
    match status {
        Status::Steered => "steered",
        Status::NotRunning => "not_running",
        Status::NotReady => "not_ready",
        Status::UnsupportedExecutor => "unsupported_executor",
        Status::TargetMismatch => "target_mismatch",
        Status::ScheduledWork => "scheduled_work",
        Status::Blocked => "blocked",
        Status::Unknown => "unknown",
    }
}

type Stored = (Uuid, Uuid, String, String, String, String);

async fn stored(pool: &SqlitePool, request: Uuid) -> Result<Option<Stored>, ApiError> {
    Ok(sqlx::query_as("SELECT session_id,execution_id,thread_id,turn_id,message_sha256,status FROM session_steering_receipts WHERE request_id=?")
        .bind(request).fetch_optional(pool).await?)
}

fn receipt(request_id: Uuid, row: Stored) -> Result<Receipt, ApiError> {
    let status: Status = serde_json::from_value(serde_json::Value::String(row.5))
        .map_err(|_| ApiError::Conflict("Invalid steering receipt; do not resend".into()))?;
    Ok(Receipt {
        request_id,
        session_id: row.0,
        execution_id: row.1,
        thread_id: row.2,
        turn_id: row.3,
        message_sha256: row.4,
        delivered: if status == Status::Unknown {
            None
        } else {
            Some(status == Status::Steered)
        },
        status,
    })
}

/// Reserve durably before any side effect. Repeated/uncertain requests never
/// invoke dispatch again, even with a new process or a concurrent caller.
pub(crate) async fn admit<F, Fut>(
    pool: &SqlitePool,
    session_id: Uuid,
    request: &SteerRequest,
    dispatch: F,
) -> Result<Receipt, ApiError>
where
    F: FnOnce() -> Fut,
    Fut: Future<Output = Result<Status, ApiError>>,
{
    if request.request_id.is_nil()
        || request.execution_id.is_nil()
        || request.message.trim().is_empty()
        || request.message.chars().count() > 60_000
        || request.thread_id.is_empty()
        || request.thread_id.len() > 256
        || request.turn_id.is_empty()
        || request.turn_id.len() > 256
    {
        return Err(ApiError::BadRequest(
            "Invalid bounded steering request".into(),
        ));
    }
    let hash = format!("{:x}", Sha256::digest(request.message.as_bytes()));
    let inserted = sqlx::query("INSERT INTO session_steering_receipts(request_id,session_id,execution_id,thread_id,turn_id,message_sha256) VALUES(?,?,?,?,?,?) ON CONFLICT(request_id) DO NOTHING")
        .bind(request.request_id).bind(session_id).bind(request.execution_id)
        .bind(&request.thread_id).bind(&request.turn_id).bind(&hash).execute(pool).await?.rows_affected();
    if inserted == 0 {
        let row = stored(pool, request.request_id).await?.ok_or_else(|| {
            ApiError::Conflict("Steering receipt unavailable; do not resend".into())
        })?;
        if row.0 != session_id
            || row.1 != request.execution_id
            || row.2 != request.thread_id
            || row.3 != request.turn_id
            || row.4 != hash
        {
            return Err(ApiError::Conflict(
                "request_id already belongs to a different steering request".into(),
            ));
        }
        return receipt(request.request_id, row);
    }
    // A cancelled handler or database failure leaves 'unknown' permanently.
    // Native errors may follow delivery; never infer non-delivery from them.
    let status = dispatch().await.unwrap_or(Status::Unknown);
    sqlx::query("UPDATE session_steering_receipts SET status=? WHERE request_id=?")
        .bind(status_name(&status))
        .bind(request.request_id)
        .execute(pool)
        .await?;
    Ok(Receipt {
        request_id: request.request_id,
        session_id,
        execution_id: request.execution_id,
        thread_id: request.thread_id.clone(),
        turn_id: request.turn_id.clone(),
        message_sha256: hash,
        delivered: if status == Status::Unknown {
            None
        } else {
            Some(status == Status::Steered)
        },
        status,
    })
}

async fn target_status(
    pool: &SqlitePool,
    session: &Session,
    id: Uuid,
) -> Result<Option<Status>, ApiError> {
    let Some(process) = ExecutionProcess::find_by_id(pool, id).await? else {
        return Ok(Some(Status::TargetMismatch));
    };
    if process.session_id != session.id {
        return Ok(Some(Status::TargetMismatch));
    }
    if process.dropped
        || process.status != ExecutionProcessStatus::Running
        || process.run_reason != ExecutionProcessRunReason::CodingAgent
    {
        return Ok(Some(Status::NotRunning));
    }
    if process
        .executor_action()
        .map_err(|_| ApiError::Conflict("Invalid execution configuration".into()))?
        .base_executor()
        != Some(BaseCodingAgent::Codex)
    {
        return Ok(Some(Status::UnsupportedExecutor));
    }
    Ok(None)
}

async fn scheduled(session: Uuid) -> Result<bool, ApiError> {
    match executors::capacity::controller::configured() {
        Ok(Some(controller)) => Ok(controller
            .lock()
            .await
            .state
            .goals
            .get(&session)
            .is_some_and(|goal| goal.grant.is_some())),
        Ok(None) => Ok(false),
        Err(_) => Err(ApiError::Conflict("Scheduled ownership unavailable".into())),
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TargetQuery {
    execution_id: Uuid,
}

#[derive(Serialize)]
struct Target {
    session_id: Uuid,
    execution_id: Uuid,
    status: &'static str,
    thread_id: Option<String>,
    turn_id: Option<String>,
}

async fn get_target<D: Deployment>(
    Extension(session): Extension<Session>,
    State(deployment): State<D>,
    Query(query): Query<TargetQuery>,
) -> Result<Json<ApiResponse<Target>>, ApiError> {
    let invalid = target_status(&deployment.db().pool, &session, query.execution_id).await?;
    let (status, binding) = if let Some(status) = invalid {
        (status_name(&status), None)
    } else if scheduled(session.id).await? {
        ("scheduled_work", None)
    } else {
        match deployment
            .container()
            .steering_target(query.execution_id)
            .await
        {
            Some(binding) => ("ready", Some(binding)),
            None => ("not_ready", None),
        }
    };
    let (thread_id, turn_id) = binding.map(|(a, b)| (Some(a), Some(b))).unwrap_or_default();
    Ok(Json(ApiResponse::success(Target {
        session_id: session.id,
        execution_id: query.execution_id,
        status,
        thread_id,
        turn_id,
    })))
}

async fn steer<D: Deployment>(
    Extension(session): Extension<Session>,
    State(deployment): State<D>,
    Json(request): Json<SteerRequest>,
) -> Result<Json<ApiResponse<Receipt>>, ApiError> {
    let pool = &deployment.db().pool;
    let incoming = if stored(pool, request.request_id).await?.is_none() {
        services::services::queued_message::QueuedMessageService::receive(
            pool,
            session.id,
            serde_json::json!({"kind":"explicit_steering", "payload": &request}),
        )
        .await?
    } else {
        None
    };
    let value = admission::locked(admit(pool, session.id, &request, || async {
        if let Some(status) = target_status(pool, &session, request.execution_id).await? {
            return Ok(status);
        }
        // Unlike /queue, never invoke scheduled takeover or before_launch.
        if scheduled(session.id).await? {
            return Ok(Status::ScheduledWork);
        }
        if deployment
            .container()
            .steering_target(request.execution_id)
            .await
            != Some((request.thread_id.clone(), request.turn_id.clone()))
        {
            return Ok(Status::NotReady);
        }
        original_worker::record_input(pool, session.id, false)
            .await
            .map_err(|e| ApiError::Conflict(e.to_string()))?;
        if original_worker::ordinary_input(session.id, "active_turn_steering")
            .await
            .is_err()
        {
            return Ok(Status::Blocked);
        }
        Ok(
            match deployment
                .container()
                .steer_bound_turn(
                    request.execution_id,
                    request.thread_id.clone(),
                    request.turn_id.clone(),
                    request.message.clone(),
                )
                .await
            {
                Ok(true) => Status::Steered,
                Ok(false) => Status::NotReady,
                Err(_) => Status::Unknown,
            },
        )
    }))
    .await?;
    if value.status != Status::Unknown {
        services::services::queued_message::QueuedMessageService::acknowledge(pool, incoming)
            .await?;
    }
    Ok(Json(ApiResponse::success(value)))
}

#[derive(Deserialize)]
struct ReceiptPath {
    request_id: Uuid,
}

async fn get_receipt<D: Deployment>(
    Extension(session): Extension<Session>,
    State(deployment): State<D>,
    Path(ReceiptPath { request_id }): Path<ReceiptPath>,
) -> Result<Json<ApiResponse<Option<Receipt>>>, ApiError> {
    let row = stored(&deployment.db().pool, request_id)
        .await?
        .filter(|row| row.0 == session.id);
    Ok(Json(ApiResponse::success(
        row.map(|row| receipt(request_id, row)).transpose()?,
    )))
}

pub(super) fn router(deployment: &DeploymentImpl) -> Router<DeploymentImpl> {
    router_for(deployment)
}

#[derive(Deserialize)]
struct SessionPath {
    session_id: Uuid,
}

async fn load_scope<D: Deployment>(
    State(deployment): State<D>,
    Path(SessionPath { session_id }): Path<SessionPath>,
    mut request: Request,
    next: Next,
) -> Result<Response, axum::http::StatusCode> {
    let session = Session::find_by_id(&deployment.db().pool, session_id)
        .await
        .map_err(|_| axum::http::StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(axum::http::StatusCode::NOT_FOUND)?;
    request.extensions_mut().insert(session);
    Ok(next.run(request).await)
}

pub(crate) fn router_for<D: Deployment>(deployment: &D) -> Router<D> {
    Router::new()
        .route("/", post(steer::<D>))
        .route("/target", get(get_target::<D>))
        .route("/{request_id}", get(get_receipt::<D>))
        .layer(DefaultBodyLimit::max(300_000))
        .layer(from_fn_with_state(deployment.clone(), load_scope::<D>))
}

#[cfg(test)]
mod tests;
