//! Explicit existing-session continuation. Never calls legacy follow-up/queue.
use axum::{
    Extension, Json, Router,
    extract::{DefaultBodyLimit, Path, Query, Request, State},
    middleware::{Next, from_fn_with_state},
    response::Response,
    routing::{get, post},
};
use db::models::{provider_admission as store, session::Session};
use deployment::Deployment;
use serde::Deserialize;
use serde_json::{Value, json};
use services::services::provider_admission as shared;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

async fn capabilities() -> Json<ApiResponse<Value>> {
    Json(ApiResponse::success(
        json!({"contract_version":shared::CONTRACT,
        "atomic_request_admission":true,"durable_receipts":true,"no_takeover":true,
        "executors":["CODEX","CLAUDE_CODE"],"cross_provider_handoff":"verified_checkpoint_dispatch_only","automatic_provider_failover":false,"client_checkpoint_reference_is_authority":false,
        "checkpoint_bridge":"trusted_terminal_host_only","checkpoint_lifetime_max_ms":30000,"external_effect_resume_qualified":false}),
    ))
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TargetQuery {
    checkpoint_receipt: Option<String>,
}
async fn target(
    Extension(session): Extension<Session>,
    State(d): State<DeploymentImpl>,
    Query(q): Query<TargetQuery>,
) -> Result<Json<ApiResponse<shared::Target>>, ApiError> {
    let t = services::services::admission::locked(shared::target(
        d.container(),
        &session,
        q.checkpoint_receipt,
        None,
    ))
    .await?;
    Ok(Json(ApiResponse::success(t)))
}
async fn submit(
    Extension(session): Extension<Session>,
    State(d): State<DeploymentImpl>,
    Json(request): Json<shared::Request>,
) -> Result<Json<ApiResponse<Value>>, ApiError> {
    Ok(Json(ApiResponse::success(
        shared::dispatch(d.container(), &session, request).await?,
    )))
}
#[derive(Deserialize)]
struct ReceiptPath {
    request_id: Uuid,
}
async fn receipt(
    Extension(session): Extension<Session>,
    State(d): State<DeploymentImpl>,
    Path(p): Path<ReceiptPath>,
) -> Result<Json<ApiResponse<Option<Value>>>, ApiError> {
    let r = store::get(&d.db().pool, p.request_id)
        .await?
        .filter(|r| r.session_id == session.id && r.workspace_id == session.workspace_id);
    let response = match r {
        Some(r) => Some(shared::readback(&d.db().pool, &r).await?),
        None => None,
    };
    Ok(Json(ApiResponse::success(response)))
}
#[derive(Deserialize)]
struct Scope {
    session_id: Uuid,
}
async fn load_scope(
    State(d): State<DeploymentImpl>,
    Path(scope): Path<Scope>,
    mut req: Request,
    next: Next,
) -> Result<Response, axum::http::StatusCode> {
    let session = Session::find_by_id(&d.db().pool, scope.session_id)
        .await
        .map_err(|_| axum::http::StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(axum::http::StatusCode::NOT_FOUND)?;
    req.extensions_mut().insert(session);
    Ok(next.run(req).await)
}
pub fn router(d: &DeploymentImpl) -> Router<DeploymentImpl> {
    Router::new()
        .route("/sessions/{session_id}/provider-admission", post(submit))
        .route(
            "/sessions/{session_id}/provider-admission/target",
            get(target),
        )
        .route(
            "/sessions/{session_id}/provider-admission/{request_id}",
            get(receipt),
        )
        .layer(DefaultBodyLimit::max(512 * 1024))
        .layer(from_fn_with_state(d.clone(), load_scope))
        .merge(Router::new().route("/provider-admission/capabilities", get(capabilities)))
}
