use axum::{
    Json, Router,
    extract::{Path, State},
    routing::{get, post},
};
use db::models::read_later::{ReadLaterItem, ReadLaterRecord};
use deployment::Deployment;
use serde::Deserialize;
use utils::response::ApiResponse;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Deserialize)]
struct SetReadLater {
    item: ReadLaterItem,
    saved: bool,
    change_id: String,
}
#[derive(Deserialize)]
struct ImportReadLater {
    items: Vec<ReadLaterItem>,
}

fn validate(scope: &str, items: &[ReadLaterItem]) -> Result<(), ApiError> {
    if scope.is_empty()
        || scope.len() > 128
        || items.len() > 10_000
        || items.iter().any(|item| {
            item.id.is_empty()
                || item.id.len() > 512
                || item.name.as_ref().is_some_and(|s| s.len() > 4096)
                || item.project_id.as_ref().is_some_and(|s| s.len() > 512)
        })
    {
        return Err(ApiError::BadRequest("Invalid Read Later preference".into()));
    }
    Ok(())
}
async fn list(
    State(d): State<DeploymentImpl>,
    Path(scope): Path<String>,
) -> Result<Json<ApiResponse<Vec<ReadLaterRecord>>>, ApiError> {
    validate(&scope, &[])?;
    Ok(Json(ApiResponse::success(
        ReadLaterRecord::list(&d.db().pool, &scope).await?,
    )))
}
async fn set(
    State(d): State<DeploymentImpl>,
    Path(scope): Path<String>,
    Json(input): Json<SetReadLater>,
) -> Result<Json<ApiResponse<()>>, ApiError> {
    validate(&scope, std::slice::from_ref(&input.item))?;
    if input.change_id.is_empty() || input.change_id.len() > 128 {
        return Err(ApiError::BadRequest("Invalid change ID".into()));
    }
    ReadLaterRecord::set(
        &d.db().pool,
        &scope,
        &input.item,
        input.saved,
        &input.change_id,
    )
    .await?;
    Ok(Json(ApiResponse::success(())))
}
async fn import(
    State(d): State<DeploymentImpl>,
    Path(scope): Path<String>,
    Json(input): Json<ImportReadLater>,
) -> Result<Json<ApiResponse<()>>, ApiError> {
    validate(&scope, &input.items)?;
    ReadLaterRecord::import(&d.db().pool, &scope, &input.items).await?;
    Ok(Json(ApiResponse::success(())))
}
pub fn router() -> Router<DeploymentImpl> {
    Router::new()
        .route("/read-later/{scope}", get(list).put(set))
        .route("/read-later/{scope}/import", post(import))
}
