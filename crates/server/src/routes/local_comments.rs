//! Discussion compatibility for local boards. Local participant IDs are display
//! identities only; the existing local server access boundary remains in force.
use api_types::{
    CreateIssueCommentReactionRequest, CreateIssueCommentRequest,
    UpdateIssueCommentReactionRequest, UpdateIssueCommentRequest,
};
use axum::{
    Json, Router,
    extract::{FromRef, Path, Query, State},
    http::StatusCode,
    routing::get,
};
use chrono::{DateTime, Utc};
use db::models::local_issue_assignee::SEAMUS_ID;
use deployment::Deployment;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sqlx::SqlitePool;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Clone)]
struct CommentDb(SqlitePool);
impl FromRef<DeploymentImpl> for CommentDb {
    fn from_ref(deployment: &DeploymentImpl) -> Self {
        Self(deployment.db().pool.clone())
    }
}
#[derive(Deserialize)]
struct IssueQuery {
    issue_id: Uuid,
}
#[derive(Deserialize)]
struct ReactionQuery {
    comment_id: Uuid,
}
#[derive(Serialize, sqlx::FromRow)]
struct Comment {
    id: Uuid,
    issue_id: Uuid,
    author_id: Option<Uuid>,
    parent_id: Option<Uuid>,
    message: String,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}
#[derive(Serialize, sqlx::FromRow)]
struct Reaction {
    id: Uuid,
    comment_id: Uuid,
    user_id: Uuid,
    emoji: String,
    created_at: DateTime<Utc>,
}

pub(super) async fn api_not_found() -> (StatusCode, Json<Value>) {
    (
        StatusCode::NOT_FOUND,
        Json(json!({"error": "Unknown local API route"})),
    )
}
// An explicit API wildcard is required: an outer SPA wildcard can win over a
// nested Router fallback in Axum's route selection.
pub(super) fn api_fallback<S: Clone + Send + Sync + 'static>() -> Router<S> {
    Router::new()
        .route("/", axum::routing::any(api_not_found))
        .route("/{*path}", axum::routing::any(api_not_found))
        .fallback(api_not_found)
}

fn mutation(data: impl Serialize) -> Json<Value> {
    Json(json!({"data": data, "txid": 0}))
}
fn validate_text(text: &str) -> Result<(), &'static str> {
    if text.trim().is_empty() {
        return Err("Message or emoji must not be empty");
    }
    Ok(())
}
async fn require_issue(pool: &SqlitePool, id: Uuid) -> Result<(), ApiError> {
    sqlx::query_scalar::<_, Uuid>("SELECT id FROM tasks WHERE id = ?")
        .bind(id)
        .fetch_one(pool)
        .await?;
    Ok(())
}
async fn find_comment(pool: &SqlitePool, id: Uuid) -> Result<Comment, ApiError> {
    Ok(
        sqlx::query_as("SELECT * FROM local_issue_comments WHERE id = ?")
            .bind(id)
            .fetch_one(pool)
            .await?,
    )
}
async fn find_reaction(pool: &SqlitePool, id: Uuid) -> Result<Reaction, ApiError> {
    Ok(
        sqlx::query_as("SELECT * FROM local_issue_comment_reactions WHERE id = ?")
            .bind(id)
            .fetch_one(pool)
            .await?,
    )
}
async fn comments(
    State(CommentDb(pool)): State<CommentDb>,
    Query(q): Query<IssueQuery>,
) -> Result<Json<Value>, ApiError> {
    require_issue(&pool, q.issue_id).await?;
    let rows: Vec<Comment> = sqlx::query_as(
        "SELECT * FROM local_issue_comments WHERE issue_id = ? ORDER BY created_at, id",
    )
    .bind(q.issue_id)
    .fetch_all(&pool)
    .await?;
    Ok(Json(json!({"issue_comments": rows})))
}
async fn reactions(
    State(CommentDb(pool)): State<CommentDb>,
    Query(q): Query<IssueQuery>,
) -> Result<Json<Value>, ApiError> {
    require_issue(&pool, q.issue_id).await?;
    let rows: Vec<Reaction> = sqlx::query_as("SELECT r.* FROM local_issue_comment_reactions r JOIN local_issue_comments c ON c.id = r.comment_id WHERE c.issue_id = ? ORDER BY r.created_at, r.id").bind(q.issue_id).fetch_all(&pool).await?;
    Ok(Json(json!({"issue_comment_reactions": rows})))
}
async fn comment_reactions(
    State(CommentDb(pool)): State<CommentDb>,
    Query(q): Query<ReactionQuery>,
) -> Result<Json<Value>, ApiError> {
    find_comment(&pool, q.comment_id).await?;
    let rows: Vec<Reaction> = sqlx::query_as(
        "SELECT * FROM local_issue_comment_reactions WHERE comment_id = ? ORDER BY created_at, id",
    )
    .bind(q.comment_id)
    .fetch_all(&pool)
    .await?;
    Ok(Json(json!({"issue_comment_reactions": rows})))
}
async fn comment(
    State(CommentDb(pool)): State<CommentDb>,
    Path(id): Path<Uuid>,
) -> Result<Json<Comment>, ApiError> {
    Ok(Json(find_comment(&pool, id).await?))
}
async fn reaction(
    State(CommentDb(pool)): State<CommentDb>,
    Path(id): Path<Uuid>,
) -> Result<Json<Reaction>, ApiError> {
    Ok(Json(find_reaction(&pool, id).await?))
}
async fn create_comment(
    State(CommentDb(pool)): State<CommentDb>,
    Json(q): Json<CreateIssueCommentRequest>,
) -> Result<Json<Value>, ApiError> {
    validate_text(&q.message).map_err(|message| ApiError::BadRequest(message.into()))?;
    require_issue(&pool, q.issue_id).await?;
    if let Some(parent) = q.parent_id
        && find_comment(&pool, parent).await?.issue_id != q.issue_id
    {
        return Err(ApiError::BadRequest(
            "Parent comment belongs to another issue".into(),
        ));
    }
    let id = q.id.unwrap_or_else(Uuid::new_v4);
    // Retrying a stable optimistic ID must not duplicate or overwrite content.
    sqlx::query("INSERT INTO local_issue_comments(id, issue_id, author_id, parent_id, message) VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING")
        .bind(id).bind(q.issue_id).bind(SEAMUS_ID).bind(q.parent_id).bind(&q.message).execute(&pool).await?;
    let row = find_comment(&pool, id).await?;
    if row.issue_id != q.issue_id || row.parent_id != q.parent_id || row.message != q.message {
        return Err(ApiError::Conflict(
            "Comment ID already has different content".into(),
        ));
    }
    Ok(mutation(row))
}
async fn update_comment(
    State(CommentDb(pool)): State<CommentDb>,
    Path(id): Path<Uuid>,
    Json(q): Json<UpdateIssueCommentRequest>,
) -> Result<Json<Value>, ApiError> {
    let existing = find_comment(&pool, id).await?;
    let message = q.message.unwrap_or(existing.message);
    validate_text(&message).map_err(|message| ApiError::BadRequest(message.into()))?;
    let parent = q.parent_id.unwrap_or(existing.parent_id);
    if let Some(parent_id) = parent {
        if find_comment(&pool, parent_id).await?.issue_id != existing.issue_id {
            return Err(ApiError::BadRequest(
                "Parent comment belongs to another issue".into(),
            ));
        }
        let cycle: bool = sqlx::query_scalar("WITH RECURSIVE ancestors(id, parent_id) AS (SELECT id, parent_id FROM local_issue_comments WHERE id = ? UNION SELECT c.id, c.parent_id FROM local_issue_comments c JOIN ancestors a ON c.id = a.parent_id) SELECT EXISTS(SELECT 1 FROM ancestors WHERE id = ?)")
            .bind(parent_id).bind(id).fetch_one(&pool).await?;
        if cycle {
            return Err(ApiError::BadRequest(
                "Comment replies cannot form a cycle".into(),
            ));
        }
    }
    sqlx::query("UPDATE local_issue_comments SET message = ?, parent_id = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?")
        .bind(message).bind(parent).bind(id).execute(&pool).await?;
    Ok(mutation(find_comment(&pool, id).await?))
}
async fn delete_comment(
    State(CommentDb(pool)): State<CommentDb>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    sqlx::query("DELETE FROM local_issue_comments WHERE id = ?")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(mutation(()))
}
async fn create_reaction(
    State(CommentDb(pool)): State<CommentDb>,
    Json(q): Json<CreateIssueCommentReactionRequest>,
) -> Result<Json<Value>, ApiError> {
    validate_text(&q.emoji).map_err(|message| ApiError::BadRequest(message.into()))?;
    find_comment(&pool, q.comment_id).await?;
    let id = q.id.unwrap_or_else(Uuid::new_v4);
    sqlx::query("INSERT INTO local_issue_comment_reactions(id, comment_id, user_id, emoji) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING")
        .bind(id).bind(q.comment_id).bind(SEAMUS_ID).bind(&q.emoji).execute(&pool).await?;
    // A duplicate natural key returns the existing reaction, matching cloud semantics.
    let row: Reaction = sqlx::query_as("SELECT * FROM local_issue_comment_reactions WHERE comment_id = ? AND user_id = ? AND emoji = ?")
        .bind(q.comment_id).bind(SEAMUS_ID).bind(q.emoji).fetch_optional(&pool).await?
        .ok_or_else(|| ApiError::Conflict("Reaction ID already has different content".into()))?;
    Ok(mutation(row))
}
async fn update_reaction(
    State(CommentDb(pool)): State<CommentDb>,
    Path(id): Path<Uuid>,
    Json(q): Json<UpdateIssueCommentReactionRequest>,
) -> Result<Json<Value>, ApiError> {
    let row = find_reaction(&pool, id).await?;
    let emoji = q.emoji.unwrap_or(row.emoji);
    validate_text(&emoji).map_err(|message| ApiError::BadRequest(message.into()))?;
    sqlx::query("UPDATE local_issue_comment_reactions SET emoji = ? WHERE id = ?")
        .bind(emoji)
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(mutation(find_reaction(&pool, id).await?))
}
async fn delete_reaction(
    State(CommentDb(pool)): State<CommentDb>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    sqlx::query("DELETE FROM local_issue_comment_reactions WHERE id = ?")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(mutation(()))
}
pub fn router() -> Router<DeploymentImpl> {
    comment_routes()
}
fn comment_routes<S>() -> Router<S>
where
    S: Clone + Send + Sync + 'static,
    CommentDb: FromRef<S>,
{
    Router::new()
        .route("/fallback/issue_comments", get(comments))
        .route("/fallback/issue_comment_reactions", get(reactions))
        .route("/issue_comments", get(comments).post(create_comment))
        .route(
            "/issue_comments/{id}",
            get(comment).patch(update_comment).delete(delete_comment),
        )
        .route(
            "/issue_comment_reactions",
            get(comment_reactions).post(create_reaction),
        )
        .route(
            "/issue_comment_reactions/{id}",
            get(reaction).patch(update_reaction).delete(delete_reaction),
        )
}

#[cfg(test)]
mod tests {
    use sqlx::sqlite::SqlitePoolOptions;

    use super::*;

    #[tokio::test]
    async fn local_discussion_http_contract_survives_reopen_and_cascades() {
        let directory = tempfile::tempdir().unwrap();
        let database = format!(
            "sqlite://{}?mode=rwc",
            directory.path().join("comments.sqlite3").display()
        );
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&database)
            .await
            .unwrap();
        sqlx::raw_sql("PRAGMA foreign_keys=ON; CREATE TABLE tasks(id BLOB PRIMARY KEY, project_id BLOB); CREATE TABLE workspaces(id BLOB PRIMARY KEY, task_id BLOB);")
            .execute(&pool).await.unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261009000000_local_issue_assignments.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261026193000_local_issue_comments.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        let issue = Uuid::new_v4();
        let other = Uuid::new_v4();
        for id in [issue, other] {
            sqlx::query("INSERT INTO tasks VALUES (?, ?)")
                .bind(id)
                .bind(Uuid::new_v4())
                .execute(&pool)
                .await
                .unwrap();
        }
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let url = format!("http://{}/v1", listener.local_addr().unwrap());
        // Use the same nested fallback contract as the production router.
        let v1 = comment_routes()
            .merge(api_fallback())
            .with_state(CommentDb(pool.clone()));
        let app = Router::new().nest("/v1", v1).route(
            "/{*path}",
            get(|| async { axum::response::Html("<!doctype html>") }),
        );
        let server = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        let client = reqwest::Client::new();
        for (path, key) in [
            ("issue_comments", "issue_comments"),
            ("issue_comment_reactions", "issue_comment_reactions"),
        ] {
            let r = client
                .get(format!("{url}/fallback/{path}?issue_id={issue}"))
                .send()
                .await
                .unwrap();
            assert_eq!(r.headers()["content-type"], "application/json");
            assert_eq!(r.json::<Value>().await.unwrap()[key], json!([]));
        }
        let r = client
            .get(format!("{url}/fallback/missing"))
            .send()
            .await
            .unwrap();
        assert_eq!(r.status(), StatusCode::NOT_FOUND);
        assert!(r.json::<Value>().await.unwrap()["error"].is_string());
        let id = Uuid::new_v4();
        let payload = json!({"id": id, "issue_id": issue, "message":"Persisted discussion", "parent_id":null});
        for _ in 0..2 {
            let r = client
                .post(format!("{url}/issue_comments"))
                .json(&payload)
                .send()
                .await
                .unwrap();
            assert!(r.status().is_success());
            let body = r.json::<Value>().await.unwrap();
            assert_eq!(body["data"]["id"], id.to_string());
            assert_eq!(body["data"]["author_id"], SEAMUS_ID.to_string());
            assert_eq!(body["txid"], 0);
        }
        for bad in [
            json!({"id":id,"issue_id":other,"message":"collision"}),
            json!({"issue_id":other,"message":"cross issue","parent_id":id}),
            json!({"issue_id":issue,"message":"   "}),
        ] {
            let r = client
                .post(format!("{url}/issue_comments"))
                .json(&bad)
                .send()
                .await
                .unwrap();
            assert!(r.status().is_client_error());
        }
        let child = Uuid::new_v4();
        let r = client
            .post(format!("{url}/issue_comments"))
            .json(&json!({"id":child,"issue_id":issue,"parent_id":id,"message":"Reply"}))
            .send()
            .await
            .unwrap();
        assert!(r.status().is_success());
        let r = client
            .patch(format!("{url}/issue_comments/{id}"))
            .json(&json!({"parent_id":child}))
            .send()
            .await
            .unwrap();
        assert_eq!(r.status(), StatusCode::BAD_REQUEST);
        let r = client
            .patch(format!("{url}/issue_comments/{id}"))
            .json(&json!({"message":"Edited discussion"}))
            .send()
            .await
            .unwrap();
        assert_eq!(
            r.json::<Value>().await.unwrap()["data"]["message"],
            "Edited discussion"
        );
        let reaction = Uuid::new_v4();
        for rid in [reaction, Uuid::new_v4()] {
            let r = client
                .post(format!("{url}/issue_comment_reactions"))
                .json(&json!({"id":rid,"comment_id":id,"emoji":"👍"}))
                .send()
                .await
                .unwrap();
            assert!(r.status().is_success());
            assert_eq!(
                r.json::<Value>().await.unwrap()["data"]["id"],
                reaction.to_string()
            );
        }
        let r = client
            .get(format!(
                "{url}/fallback/issue_comment_reactions?issue_id={other}"
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(
            r.json::<Value>().await.unwrap()["issue_comment_reactions"],
            json!([])
        );
        let r = client
            .get(format!("{url}/fallback/issue_comments?issue_id={issue}"))
            .send()
            .await
            .unwrap();
        assert_eq!(
            r.json::<Value>().await.unwrap()["issue_comments"]
                .as_array()
                .unwrap()
                .len(),
            2
        );
        let r = client
            .patch(format!("{url}/issue_comment_reactions/{reaction}"))
            .json(&json!({"emoji":"🎉"}))
            .send()
            .await
            .unwrap();
        assert_eq!(r.json::<Value>().await.unwrap()["data"]["emoji"], "🎉");
        // Reopen a real file to prove storage outlives connections/router state.
        server.abort();
        pool.close().await;
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&database)
            .await
            .unwrap();
        assert_eq!(
            find_comment(&pool, id).await.unwrap().message,
            "Edited discussion"
        );
        assert_eq!(find_reaction(&pool, reaction).await.unwrap().emoji, "🎉");
        let _ = delete_reaction(State(CommentDb(pool.clone())), Path(reaction))
            .await
            .unwrap();
        assert!(find_reaction(&pool, reaction).await.is_err());
        let _ = create_reaction(
            State(CommentDb(pool.clone())),
            Json(CreateIssueCommentReactionRequest {
                id: None,
                comment_id: child,
                emoji: "👍".into(),
            }),
        )
        .await
        .unwrap();
        let _ = delete_comment(State(CommentDb(pool.clone())), Path(id))
            .await
            .unwrap();
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM local_issue_comments")
                .fetch_one(&pool)
                .await
                .unwrap(),
            0
        );
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM local_issue_comment_reactions")
                .fetch_one(&pool)
                .await
                .unwrap(),
            0
        );
        let _ = create_comment(
            State(CommentDb(pool.clone())),
            Json(CreateIssueCommentRequest {
                id: None,
                issue_id: issue,
                parent_id: None,
                message: "Task deletion".into(),
            }),
        )
        .await
        .unwrap();
        sqlx::query("DELETE FROM tasks WHERE id = ?")
            .bind(issue)
            .execute(&pool)
            .await
            .unwrap();
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM local_issue_comments")
                .fetch_one(&pool)
                .await
                .unwrap(),
            0
        );
    }
}
