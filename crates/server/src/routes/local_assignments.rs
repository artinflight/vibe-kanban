//! Local assignment identities; these routes do not create authentication accounts.
use api_types::{
    CreateIssueAssigneeRequest, IssueAssignee, MemberRole, OrganizationMemberWithProfile,
};
use axum::{
    Json, Router,
    extract::{FromRef, Path, Query, State},
    routing::get,
};
use db::models::local_issue_assignee::{LocalIssueAssignee, SEAMUS_ID};
use deployment::Deployment;
use serde::Deserialize;
use serde_json::{Value, json};
use sqlx::SqlitePool;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Clone)]
struct AssignmentDb(SqlitePool);

impl FromRef<DeploymentImpl> for AssignmentDb {
    fn from_ref(deployment: &DeploymentImpl) -> Self {
        Self(deployment.db().pool.clone())
    }
}

#[derive(Deserialize)]
struct ProjectQuery {
    project_id: Uuid,
}

#[derive(Deserialize)]
struct IssueQuery {
    issue_id: Uuid,
}

fn issue_assignee(row: LocalIssueAssignee) -> IssueAssignee {
    IssueAssignee {
        id: row.id,
        issue_id: row.issue_id,
        user_id: row.user_id,
        assigned_at: row.assigned_at,
    }
}

async fn participants(
    State(AssignmentDb(pool)): State<AssignmentDb>,
) -> Result<Json<Value>, ApiError> {
    let members = LocalIssueAssignee::participants(&pool)
        .await?
        .into_iter()
        .map(|p| OrganizationMemberWithProfile {
            user_id: p.id,
            // Reuse the picker profile shape. This is a display value, never an ACL.
            role: MemberRole::Member,
            joined_at: p.created_at,
            first_name: Some(p.display_name),
            last_name: None,
            username: Some(p.username),
            email: None,
            avatar_url: None,
        })
        .collect::<Vec<_>>();
    Ok(Json(
        json!({ "members": members, "current_user_id": SEAMUS_ID }),
    ))
}

async fn project_assignees(
    State(AssignmentDb(pool)): State<AssignmentDb>,
    Query(query): Query<ProjectQuery>,
) -> Result<Json<Value>, ApiError> {
    let rows = LocalIssueAssignee::for_project(&pool, query.project_id).await?;
    Ok(Json(
        json!({ "issue_assignees": rows.into_iter().map(issue_assignee).collect::<Vec<_>>() }),
    ))
}

async fn list(
    State(AssignmentDb(pool)): State<AssignmentDb>,
    Query(query): Query<IssueQuery>,
) -> Result<Json<Value>, ApiError> {
    let rows = LocalIssueAssignee::for_issue(&pool, query.issue_id).await?;
    Ok(Json(
        json!({ "issue_assignees": rows.into_iter().map(issue_assignee).collect::<Vec<_>>() }),
    ))
}

async fn find(
    State(AssignmentDb(pool)): State<AssignmentDb>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    Ok(Json(json!(issue_assignee(
        LocalIssueAssignee::find(&pool, id).await?
    ))))
}

async fn create(
    State(AssignmentDb(pool)): State<AssignmentDb>,
    Json(request): Json<CreateIssueAssigneeRequest>,
) -> Result<Json<Value>, ApiError> {
    let pool = &pool;
    let valid: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM tasks WHERE id = ?) AND EXISTS(SELECT 1 FROM local_participants WHERE id = ?)")
        .bind(request.issue_id).bind(request.user_id).fetch_one(pool).await?;
    if !valid {
        return Err(ApiError::BadRequest(
            "Assignment requires an existing local issue and participant".into(),
        ));
    }
    let row = LocalIssueAssignee::create(
        pool,
        request.id.unwrap_or_else(Uuid::new_v4),
        request.issue_id,
        request.user_id,
    )
    .await?;
    Ok(Json(json!({ "data": issue_assignee(row), "txid": 0 })))
}

async fn delete(
    State(AssignmentDb(pool)): State<AssignmentDb>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    LocalIssueAssignee::delete(&pool, id).await?;
    Ok(Json(json!({ "txid": 0 })))
}

async fn workspace_assignments(
    State(AssignmentDb(pool)): State<AssignmentDb>,
) -> Result<Json<Value>, ApiError> {
    Ok(Json(
        json!({ "workspace_assignments": LocalIssueAssignee::workspace_links(&pool).await? }),
    ))
}

pub fn router() -> Router<DeploymentImpl> {
    assignment_routes()
}

fn assignment_routes<S>() -> Router<S>
where
    S: Clone + Send + Sync + 'static,
    AssignmentDb: FromRef<S>,
{
    Router::new()
        .route("/local-participants", get(participants))
        .route("/fallback/issue_assignees", get(project_assignees))
        .route(
            "/fallback/workspace_assignments",
            get(workspace_assignments),
        )
        .route("/issue_assignees", get(list).post(create))
        .route("/issue_assignees/{id}", get(find).delete(delete))
}

#[cfg(test)]
mod tests {
    use sqlx::sqlite::SqlitePoolOptions;

    use super::*;

    #[tokio::test]
    async fn local_picker_http_contract_persists_multi_assignees_and_task_inheritance() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::raw_sql("PRAGMA foreign_keys=ON; CREATE TABLE tasks(id BLOB PRIMARY KEY, project_id BLOB); CREATE TABLE workspaces(id BLOB PRIMARY KEY, task_id BLOB); CREATE TABLE coding_agent_turns(seen INTEGER); INSERT INTO coding_agent_turns VALUES (0);")
            .execute(&pool).await.unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261009000000_local_issue_assignments.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        let project = Uuid::new_v4();
        let task = Uuid::new_v4();
        let workspace = Uuid::new_v4();
        sqlx::query("INSERT INTO tasks VALUES (?, ?)")
            .bind(task)
            .bind(project)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO workspaces VALUES (?, ?)")
            .bind(workspace)
            .bind(task)
            .execute(&pool)
            .await
            .unwrap();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let url = format!("http://{}", listener.local_addr().unwrap());
        let app = assignment_routes().with_state(AssignmentDb(pool.clone()));
        let server = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        let client = reqwest::Client::new();
        let participants: Value = client
            .get(format!("{url}/local-participants"))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(participants["current_user_id"], SEAMUS_ID.to_string());
        let members = participants["members"].as_array().unwrap();
        assert_eq!(members.len(), 2);
        let mut assignment_ids = Vec::new();
        for member in members {
            let id = Uuid::new_v4();
            let response = client
                .post(format!("{url}/issue_assignees"))
                .json(&json!({ "id": id, "issue_id": task, "user_id": member["user_id"] }))
                .send()
                .await
                .unwrap();
            assert!(response.status().is_success());
            let body: Value = response.json().await.unwrap();
            assert_eq!(body["txid"], 0);
            let record: IssueAssignee = serde_json::from_value(body["data"].clone()).unwrap();
            assert_eq!(record.id, id);
            assert_eq!(record.issue_id, task);
            assignment_ids.push(id);
        }
        let list: Value = client
            .get(format!(
                "{url}/fallback/issue_assignees?project_id={project}"
            ))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(list["issue_assignees"].as_array().unwrap().len(), 2);
        let list: Value = client
            .get(format!("{url}/issue_assignees?issue_id={task}"))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        assert_eq!(list["issue_assignees"].as_array().unwrap().len(), 2);
        let links: Value = client
            .get(format!("{url}/fallback/workspace_assignments"))
            .send()
            .await
            .unwrap()
            .json()
            .await
            .unwrap();
        let links = links["workspace_assignments"].as_array().unwrap();
        assert_eq!(links.len(), 2);
        assert!(
            links
                .iter()
                .all(|link| link["workspace_id"] == workspace.to_string()
                    && link["issue_id"] == task.to_string())
        );
        let invalid = client
            .post(format!("{url}/issue_assignees"))
            .json(&json!({ "issue_id": task, "user_id": Uuid::new_v4() }))
            .send()
            .await
            .unwrap();
        assert_eq!(invalid.status(), reqwest::StatusCode::BAD_REQUEST);
        let invalid = client
            .post(format!("{url}/issue_assignees"))
            .json(&json!({ "issue_id": Uuid::new_v4(), "user_id": SEAMUS_ID }))
            .send()
            .await
            .unwrap();
        assert_eq!(invalid.status(), reqwest::StatusCode::BAD_REQUEST);
        for id in assignment_ids {
            let get = client
                .get(format!("{url}/issue_assignees/{id}"))
                .send()
                .await
                .unwrap();
            assert!(get.status().is_success());
            let delete = client
                .delete(format!("{url}/issue_assignees/{id}"))
                .send()
                .await
                .unwrap();
            let body: Value = delete.json().await.unwrap();
            assert_eq!(body["txid"], 0);
        }
        let seen: i64 = sqlx::query_scalar("SELECT seen FROM coding_agent_turns")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(seen, 0);
        assert!(
            LocalIssueAssignee::for_issue(&pool, task)
                .await
                .unwrap()
                .is_empty()
        );
        server.abort();
    }
}
