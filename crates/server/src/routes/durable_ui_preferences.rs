use axum::{
    Json, Router,
    extract::{Path, State},
    response::Json as ResponseJson,
    routing::{get, put},
};
use db::models::durable_ui_preferences::{
    DurablePreferenceError, DurableUiPreferences, ProjectNavigationOrder,
    UpdateProjectNavigationOrder, UpdateWorkspaceCardColor, WorkspaceCardColor,
};
use deployment::Deployment;
use utils::response::ApiResponse;

use crate::{DeploymentImpl, error::ApiError};

fn map_error(error: DurablePreferenceError) -> ApiError {
    match error {
        DurablePreferenceError::Conflict => ApiError::Conflict(
            "Durable preference changed in another tab; reload before retrying".to_string(),
        ),
        DurablePreferenceError::Database(error) => ApiError::Database(error),
        DurablePreferenceError::Json(error) => ApiError::BadRequest(error.to_string()),
    }
}

async fn get_preferences(
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<DurableUiPreferences>>, ApiError> {
    let preferences = DurableUiPreferences::get(&deployment.db().pool)
        .await
        .map_err(map_error)?;
    Ok(ResponseJson(ApiResponse::success(preferences)))
}

async fn update_project_order(
    State(deployment): State<DeploymentImpl>,
    Json(input): Json<UpdateProjectNavigationOrder>,
) -> Result<ResponseJson<ApiResponse<ProjectNavigationOrder>>, ApiError> {
    if input.project_ids.iter().any(String::is_empty) {
        return Err(ApiError::BadRequest(
            "Project order cannot contain empty IDs".to_string(),
        ));
    }
    let mut unique = input.project_ids.clone();
    unique.sort();
    unique.dedup();
    if unique.len() != input.project_ids.len() {
        return Err(ApiError::BadRequest(
            "Project order cannot contain duplicate IDs".to_string(),
        ));
    }
    let order = DurableUiPreferences::update_project_order(&deployment.db().pool, &input)
        .await
        .map_err(map_error)?;
    Ok(ResponseJson(ApiResponse::success(order)))
}

async fn update_workspace_color(
    State(deployment): State<DeploymentImpl>,
    Path(workspace_id): Path<String>,
    Json(mut input): Json<UpdateWorkspaceCardColor>,
) -> Result<ResponseJson<ApiResponse<Option<WorkspaceCardColor>>>, ApiError> {
    input.color = input
        .color
        .map(|color| color.trim().to_string())
        .filter(|color| !color.is_empty());
    let color =
        DurableUiPreferences::update_workspace_color(&deployment.db().pool, &workspace_id, &input)
            .await
            .map_err(map_error)?;
    Ok(ResponseJson(ApiResponse::success(color)))
}

pub fn router() -> Router<DeploymentImpl> {
    Router::new()
        .route("/durable-ui-preferences", get(get_preferences))
        .route("/project-navigation-order", put(update_project_order))
        .route(
            "/workspace-card-colors/{workspace_id}",
            put(update_workspace_color),
        )
}
