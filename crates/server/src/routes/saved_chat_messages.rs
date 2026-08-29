use axum::{
    Json, Router,
    extract::{Path, State},
    response::Json as ResponseJson,
    routing::{get, put},
};
use db::models::saved_chat_message::{SavedChatMessage, UpsertSavedChatMessage};
use deployment::Deployment;
use utils::response::ApiResponse;

use crate::{DeploymentImpl, error::ApiError};

async fn list(
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<Vec<SavedChatMessage>>>, ApiError> {
    let messages = SavedChatMessage::find_all(&deployment.db().pool).await?;
    Ok(ResponseJson(ApiResponse::success(messages)))
}

async fn upsert(
    State(deployment): State<DeploymentImpl>,
    Path(id): Path<String>,
    Json(mut input): Json<UpsertSavedChatMessage>,
) -> Result<ResponseJson<ApiResponse<SavedChatMessage>>, ApiError> {
    if id != input.id {
        return Err(ApiError::BadRequest(
            "Saved message ID does not match request path".to_string(),
        ));
    }
    input.title = input.title.trim().to_string();
    if input.id.is_empty() || input.title.is_empty() || input.content.trim().is_empty() {
        return Err(ApiError::BadRequest(
            "Saved messages require an ID, title, and content".to_string(),
        ));
    }
    let message = SavedChatMessage::upsert(&deployment.db().pool, &input).await?;
    Ok(ResponseJson(ApiResponse::success(message)))
}

async fn remove(
    State(deployment): State<DeploymentImpl>,
    Path(id): Path<String>,
) -> Result<ResponseJson<ApiResponse<()>>, ApiError> {
    SavedChatMessage::delete(&deployment.db().pool, &id).await?;
    Ok(ResponseJson(ApiResponse::success(())))
}

pub fn router() -> Router<DeploymentImpl> {
    Router::new()
        .route("/saved-chat-messages", get(list))
        .route("/saved-chat-messages/{id}", put(upsert).delete(remove))
}
