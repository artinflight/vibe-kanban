//! Local issue lifecycle. Reuses native workspace/session records, SQLite
//! transactions and shared admission; no alternate executor or retry controller.
use axum::{
    Json, Router,
    extract::{DefaultBodyLimit, Path, Query, State},
    routing::{get, post},
};
use db::models::{
    issue_workflow::{IssueWorkflow, Reservation, ReservedRepo, WorkflowError},
    requests::WorkspaceRepoInput,
    session::Session,
    task::TaskStatus,
    workspace::Workspace,
};
use deployment::Deployment;
use executors::{profile::ExecutorConfig, routing::RoutingMode};
use serde::{Deserialize, Serialize};
use services::services::{admission, container::ContainerService};
use sha2::{Digest, Sha256};
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
enum Operation {
    Create,
    Start,
    Relink,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Start {
    name: String,
    prompt: String,
    executor_config: ExecutorConfig,
    repositories: Vec<WorkspaceRepoInput>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Link {
    workspace_id: Uuid,
    expected_issue_id: Uuid,
    expected_link_revision: i64,
    target_issue_id: Option<Uuid>,
    chat_previous_issue_id: Option<Uuid>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Request {
    request_id: Uuid,
    project_id: Uuid,
    operation: Operation,
    title: Option<String>,
    description: Option<String>,
    status_id: Option<String>,
    start: Option<Start>,
    link: Option<Link>,
}

impl Request {
    // Preserve the shared HTTP error contract; no large WebRTC error is created here.
    #[allow(clippy::result_large_err)]
    fn validate(&self) -> Result<(), ApiError> {
        let invalid = || ApiError::BadRequest("Invalid bounded issue workflow request".into());
        if self.request_id.is_nil() || self.project_id.is_nil() {
            return Err(invalid());
        }
        let existing_target = self.link.as_ref().and_then(|l| l.target_issue_id).is_some();
        if existing_target {
            if self.title.is_some() || self.description.is_some() || self.status_id.is_some() {
                return Err(invalid());
            }
        } else if self
            .title
            .as_ref()
            .is_none_or(|s| s.trim().is_empty() || s.chars().count() > 240)
            || self
                .description
                .as_ref()
                .is_none_or(|s| s.chars().count() > 20_000)
            || self
                .status_id
                .as_ref()
                .is_none_or(|s| s.is_empty() || s.len() > 100)
        {
            return Err(invalid());
        }
        match self.operation {
            Operation::Create if self.start.is_none() && self.link.is_none() => {}
            Operation::Start if self.start.is_some() && self.link.is_none() => {}
            Operation::Relink if self.link.is_some() && self.start.is_none() => {}
            _ => return Err(invalid()),
        }
        if let Some(link) = &self.link
            && (link.workspace_id.is_nil()
                || link.expected_issue_id.is_nil()
                || link.expected_link_revision < 0
                || link.target_issue_id.is_some_and(|id| id.is_nil())
                || link.chat_previous_issue_id.is_some_and(|id| id.is_nil()))
        {
            return Err(invalid());
        }
        if let Some(start) = &self.start {
            if start.name.trim().is_empty()
                || start.name.chars().count() > 240
                || start.prompt.trim().is_empty()
                || start.prompt.chars().count() > 60_000
                || start.repositories.is_empty()
                || start.repositories.len() > 8
                || start.executor_config.executor.to_string() != "CODEX"
                || start
                    .executor_config
                    .routing
                    .as_ref()
                    .is_none_or(|p| p.mode != RoutingMode::Shadow)
            {
                return Err(invalid());
            }
            let mut seen = std::collections::HashSet::new();
            for repo in &start.repositories {
                if repo.repo_id.is_nil()
                    || !seen.insert(repo.repo_id)
                    || repo.target_branch.trim().is_empty()
                    || repo.target_branch.len() > 250
                {
                    return Err(invalid());
                }
            }
        }
        Ok(())
    }

    // Preserve the shared HTTP error contract; no large WebRTC error is created here.
    #[allow(clippy::result_large_err)]
    fn hash(&self) -> Result<String, ApiError> {
        Ok(format!(
            "{:x}",
            Sha256::digest(
                serde_json::to_vec(self)
                    .map_err(|_| ApiError::BadRequest("Invalid request".into()))?
            )
        ))
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Scope {
    project_id: Uuid,
}

#[derive(Serialize)]
struct Receipt {
    #[serde(flatten)]
    workflow: IssueWorkflow,
    current_link: bool,
    assignment_verified: bool,
    // Exact persisted launch evidence, never inferred from workspace existence.
    executions: Vec<ExecutionEvidence>,
}

#[derive(Serialize, sqlx::FromRow)]
struct ExecutionEvidence {
    id: Uuid,
    run_reason: String,
    status: String,
    dropped: bool,
}

fn workflow_error(error: WorkflowError) -> ApiError {
    match error {
        WorkflowError::Database(e) => e.into(),
        WorkflowError::Conflict(e) => ApiError::Conflict(e.into()),
    }
}

async fn receipt(deployment: &DeploymentImpl, row: IssueWorkflow) -> Result<Receipt, ApiError> {
    let pool = &deployment.db().pool;
    let current_link = if let Some(workspace) = row.workspace_id {
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspaces w JOIN tasks t ON t.id=w.task_id WHERE w.id=? AND t.id=? AND t.project_id=? AND COALESCE((SELECT revision FROM workspace_issue_link_revisions WHERE workspace_id=w.id),0)=?)")
            .bind(workspace).bind(row.issue_id).bind(row.project_id).bind(row.link_revision).fetch_one(pool).await?
    } else {
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM tasks WHERE id=? AND project_id=?)")
            .bind(row.issue_id)
            .bind(row.project_id)
            .fetch_one(pool)
            .await?
    };
    let assignment_verified = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM local_issue_assignees WHERE issue_id=? AND user_id=?)",
    )
    .bind(row.issue_id)
    .bind(row.dot_user_id)
    .fetch_one(pool)
    .await?;
    let executions = sqlx::query_as("SELECT id,run_reason,status,dropped FROM execution_processes WHERE session_id=? ORDER BY created_at,rowid LIMIT 100")
        .bind(row.session_id).fetch_all(pool).await?;
    Ok(Receipt {
        workflow: row,
        current_link,
        assignment_verified,
        executions,
    })
}

async fn capabilities() -> Json<ApiResponse<serde_json::Value>> {
    Json(ApiResponse::success(
        serde_json::json!({"version":1,"atomic_reservation":true,"conditional_relink":true,"durable_launch_receipts":true}),
    ))
}

async fn read(
    State(deployment): State<DeploymentImpl>,
    Path(id): Path<Uuid>,
    Query(scope): Query<Scope>,
) -> Result<Json<ApiResponse<Option<Receipt>>>, ApiError> {
    let row = IssueWorkflow::find(&deployment.db().pool, id).await?;
    if row
        .as_ref()
        .is_some_and(|r| r.project_id != scope.project_id)
    {
        return Err(ApiError::Conflict("Request unavailable in project".into()));
    }
    let result = match row {
        Some(row) => Some(receipt(&deployment, row).await?),
        None => None,
    };
    Ok(Json(ApiResponse::success(result)))
}

async fn link_context(
    State(deployment): State<DeploymentImpl>,
    Path(id): Path<Uuid>,
    Query(scope): Query<Scope>,
) -> Result<Json<ApiResponse<serde_json::Value>>, ApiError> {
    let row: Option<(Uuid,i64)> = sqlx::query_as("SELECT t.id,COALESCE(v.revision,0) FROM workspaces w JOIN tasks t ON t.id=w.task_id JOIN projects p ON p.id=t.project_id LEFT JOIN workspace_issue_link_revisions v ON v.workspace_id=w.id WHERE w.id=? AND p.id=? AND p.remote_project_id IS NULL AND p.archived=0")
        .bind(id).bind(scope.project_id).fetch_optional(&deployment.db().pool).await?;
    let (issue, revision) = row.ok_or_else(|| {
        ApiError::Conflict("Linked local workspace unavailable in project".into())
    })?;
    Ok(Json(ApiResponse::success(
        serde_json::json!({"workspace_id":id,"project_id":scope.project_id,"issue_id":issue,"link_revision":revision}),
    )))
}

/// SQLite hooks may read before a transaction commits. Publish the committed
/// workspace explicitly through the existing event store; retries use JSON Add
/// at the same ID, so no duplicate workspace/notification identity is invented.
async fn publish_reserved_workspace(
    deployment: &DeploymentImpl,
    row: &IssueWorkflow,
) -> Result<(), ApiError> {
    if let Some(id) = row.workspace_id
        && let Some(workspace) =
            Workspace::find_by_id_with_status(&deployment.db().pool, id).await?
    {
        deployment
            .events()
            .msg_store()
            .push_patch(services::services::events::workspace_patch::add(&workspace));
    }
    Ok(())
}

async fn prepare(
    State(deployment): State<DeploymentImpl>,
    Json(request): Json<Request>,
) -> Result<Json<ApiResponse<Receipt>>, ApiError> {
    request.validate()?;
    let hash = request.hash()?;
    if let Some(old) = IssueWorkflow::find(&deployment.db().pool, request.request_id).await? {
        if old.project_id != request.project_id || old.request_hash != hash {
            return Err(ApiError::Conflict("Request identity changed".into()));
        }
        publish_reserved_workspace(&deployment, &old).await?;
        return Ok(Json(ApiResponse::success(receipt(&deployment, old).await?)));
    }
    let (status, description) = if request
        .link
        .as_ref()
        .and_then(|l| l.target_issue_id)
        .is_some()
    {
        (TaskStatus::Todo, String::new())
    } else {
        super::local_compat::workflow_issue_fields(
            &deployment,
            request.project_id,
            request.status_id.as_deref().unwrap_or_default(),
            request.description.as_deref().unwrap_or_default(),
        )
        .await?
    };
    let wid = request
        .start
        .as_ref()
        .map(|_| Uuid::new_v4())
        .or_else(|| request.link.as_ref().map(|l| l.workspace_id));
    let sid = request.start.as_ref().map(|_| Uuid::new_v4());
    let branch = if let Some(start) = &request.start {
        Some(
            deployment
                .container()
                .git_branch_from_workspace(&wid.expect("start has workspace"), &start.name)
                .await,
        )
    } else {
        None
    };
    let repos: Vec<_> = request
        .start
        .as_ref()
        .map(|s| {
            s.repositories
                .iter()
                .map(|r| ReservedRepo {
                    repo_id: r.repo_id,
                    target_branch: r.target_branch.clone(),
                })
                .collect()
        })
        .unwrap_or_default();
    let executor = request
        .start
        .as_ref()
        .map(|s| s.executor_config.executor.to_string());
    let row = IssueWorkflow::reserve(
        &deployment.db().pool,
        &Reservation {
            request_id: request.request_id,
            project_id: request.project_id,
            request_hash: &hash,
            operation: match request.operation {
                Operation::Create => "create",
                Operation::Start => "start",
                Operation::Relink => "relink",
            },
            issue_id: Uuid::new_v4(),
            title: request.title.as_deref().unwrap_or_default(),
            description: &description,
            status,
            workspace_id: wid,
            name: request.start.as_ref().map(|s| s.name.as_str()),
            branch: branch.as_deref(),
            session_id: sid,
            executor: executor.as_deref(),
            repos: &repos,
            expected_issue_id: request.link.as_ref().map(|l| l.expected_issue_id),
            expected_link_revision: request.link.as_ref().map(|l| l.expected_link_revision),
            target_issue_id: request.link.as_ref().and_then(|l| l.target_issue_id),
            chat_previous_issue_id: request.link.as_ref().and_then(|l| l.chat_previous_issue_id),
        },
    )
    .await
    .map_err(workflow_error)?;
    publish_reserved_workspace(&deployment, &row).await?;
    Ok(Json(ApiResponse::success(receipt(&deployment, row).await?)))
}

/// Same write-ahead admission pattern as explicit steering. The caller owns
/// current source/config checks and existing admission lock; this function owns
/// exactly one effect for the durable request across cancellation and retries.
async fn dispatch_once<F, Fut>(
    pool: &sqlx::SqlitePool,
    row: &IssueWorkflow,
    dispatch: F,
) -> Result<IssueWorkflow, ApiError>
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = Result<Uuid, ApiError>>,
{
    if row.claim_launch(pool).await? {
        if let Ok(execution) = dispatch().await {
            row.record_started(pool, execution).await?;
        }
    } else {
        row.reconcile_terminal(pool).await?;
    }
    IssueWorkflow::find(pool, row.request_id)
        .await?
        .ok_or_else(|| ApiError::Conflict("Receipt missing".into()))
}

async fn launch(
    State(deployment): State<DeploymentImpl>,
    Path(id): Path<Uuid>,
    Json(request): Json<Request>,
) -> Result<Json<ApiResponse<Receipt>>, ApiError> {
    request.validate()?;
    if request.request_id != id || request.operation != Operation::Start {
        return Err(ApiError::BadRequest("Exact start request required".into()));
    }
    admission::locked(async {
        let pool = &deployment.db().pool;
        let row = IssueWorkflow::find(pool, id)
            .await?
            .ok_or_else(|| ApiError::Conflict("Reserve workflow first".into()))?;
        if row.project_id != request.project_id || row.request_hash != request.hash()? {
            return Err(ApiError::Conflict("Request identity changed".into()));
        }
        if row.phase != "reserved" {
            row.reconcile_terminal(pool).await?;
            let current = IssueWorkflow::find(pool, id)
                .await?
                .ok_or_else(|| ApiError::Conflict("Receipt missing".into()))?;
            return Ok(Json(ApiResponse::success(
                receipt(&deployment, current).await?,
            )));
        }
        let current = receipt(&deployment, row.clone()).await?;
        if !current.current_link || !current.assignment_verified {
            return Err(ApiError::Conflict(
                "Issue link or assignment changed".into(),
            ));
        }
        let workspace = Workspace::find_by_id(
            pool,
            row.workspace_id
                .ok_or_else(|| ApiError::Conflict("Workspace missing".into()))?,
        )
        .await?
        .ok_or_else(|| ApiError::Conflict("Workspace missing".into()))?;
        let session = Session::find_by_id(
            pool,
            row.session_id
                .ok_or_else(|| ApiError::Conflict("Session missing".into()))?,
        )
        .await?
        .ok_or_else(|| ApiError::Conflict("Session missing".into()))?;
        let start = request
            .start
            .as_ref()
            .ok_or_else(|| ApiError::BadRequest("Start selection required".into()))?;
        if session.workspace_id != workspace.id
            || session.executor.as_deref()
                != Some(start.executor_config.executor.to_string().as_str())
        {
            return Err(ApiError::Conflict("Reserved session changed".into()));
        }
        // Deterministic existing worktree preparation is resumable before launch
        // admission. No setup or agent command is sent by ensure_container_exists.
        deployment
            .container()
            .ensure_container_exists(&workspace)
            .await
            .map_err(ApiError::Container)?;
        let row = dispatch_once(pool, &row, || async {
            let actual = Workspace::find_by_id(pool, workspace.id)
                .await?
                .ok_or_else(|| ApiError::Conflict("Workspace missing".into()))?;
            deployment
                .container()
                .start_workspace_session(
                    &actual,
                    &session,
                    start.executor_config.clone(),
                    start.prompt.clone(),
                )
                .await
                .map(|execution| execution.id)
                .map_err(ApiError::Container)
        })
        .await?;
        Ok(Json(ApiResponse::success(receipt(&deployment, row).await?)))
    })
    .await
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ChatReady {
    project_id: Uuid,
    request_hash: String,
}

async fn chat_ready(
    State(deployment): State<DeploymentImpl>,
    Path(id): Path<Uuid>,
    Json(request): Json<ChatReady>,
) -> Result<Json<ApiResponse<Receipt>>, ApiError> {
    let pool = &deployment.db().pool;
    let row = IssueWorkflow::find(pool, id)
        .await?
        .ok_or_else(|| ApiError::Conflict("Receipt unavailable".into()))?;
    if row.project_id != request.project_id || row.request_hash != request.request_hash {
        return Err(ApiError::Conflict("Request identity changed".into()));
    }
    let current = receipt(&deployment, row.clone()).await?;
    if !current.current_link {
        return Err(ApiError::Conflict("Workspace link changed".into()));
    }
    let changed=sqlx::query("UPDATE issue_workflows SET chat_completed=1 WHERE request_id=? AND request_hash=? AND EXISTS(SELECT 1 FROM workspaces w WHERE w.id=issue_workflows.workspace_id AND w.task_id=issue_workflows.issue_id AND COALESCE((SELECT revision FROM workspace_issue_link_revisions WHERE workspace_id=w.id),0)=issue_workflows.link_revision)")
        .bind(id).bind(&request.request_hash).execute(pool).await?.rows_affected();
    if changed != 1 {
        return Err(ApiError::Conflict("Workspace link changed".into()));
    }
    Ok(Json(ApiResponse::success(
        receipt(
            &deployment,
            IssueWorkflow::find(pool, id)
                .await?
                .ok_or_else(|| ApiError::Conflict("Receipt unavailable".into()))?,
        )
        .await?,
    )))
}

pub fn router() -> Router<DeploymentImpl> {
    Router::new()
        .route("/issue-workflows/capabilities", get(capabilities))
        .route("/issue-workflows", post(prepare))
        .route("/issue-workflows/{id}", get(read))
        .route("/issue-workflows/{id}/launch", post(launch))
        .route("/issue-workflows/{id}/chat-ready", post(chat_ready))
        .route("/issue-workflows/workspaces/{id}", get(link_context))
        .layer(DefaultBodyLimit::max(512 * 1024))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create() -> serde_json::Value {
        serde_json::json!({"request_id":Uuid::new_v4(),"project_id":Uuid::new_v4(),"operation":"create","title":"Dedicated","description":"Owner scope","status_id":"todo","start":null,"link":null})
    }

    #[test]
    fn missing_nil_invalid_and_unknown_inputs_reject_before_reservation() {
        let mut value = create();
        value["request_id"] = serde_json::json!(Uuid::nil());
        assert!(
            serde_json::from_value::<Request>(value)
                .unwrap()
                .validate()
                .is_err()
        );
        let mut value = create();
        value["title"] = serde_json::json!("");
        assert!(
            serde_json::from_value::<Request>(value)
                .unwrap()
                .validate()
                .is_err()
        );
        let mut value = create();
        value["owner"] = serde_json::json!("forged");
        assert!(serde_json::from_value::<Request>(value).is_err());
        let mut value = create();
        value.as_object_mut().unwrap().remove("request_id");
        assert!(serde_json::from_value::<Request>(value).is_err());
    }

    #[test]
    fn request_hash_binds_project_operation_and_full_owner_selection() {
        let value = create();
        let one: Request = serde_json::from_value(value.clone()).unwrap();
        one.validate().unwrap();
        let mut changed = value;
        changed["description"] = serde_json::json!("Changed request");
        assert_ne!(
            one.hash().unwrap(),
            serde_json::from_value::<Request>(changed)
                .unwrap()
                .hash()
                .unwrap()
        );
    }

    async fn reserved_fixture() -> (sqlx::SqlitePool, IssueWorkflow) {
        use db::models::issue_workflow::{Reservation, ReservedRepo};
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/src/models/issue_workflow_sql/test_schema.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261024180000_issue_workflows.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        let (project, repo, dot) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        sqlx::query("INSERT INTO projects VALUES(?,0,NULL)")
            .bind(project)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO repos VALUES(?,'repo',NULL)")
            .bind(repo)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO project_repos VALUES(?,?)")
            .bind(project)
            .bind(repo)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO local_participants VALUES(?,'dot')")
            .bind(dot)
            .execute(&pool)
            .await
            .unwrap();
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let request = Reservation {
            request_id: Uuid::new_v4(),
            project_id: project,
            request_hash: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            operation: "start",
            issue_id: Uuid::new_v4(),
            title: "Dedicated",
            description: "Owner",
            status: TaskStatus::Todo,
            workspace_id: Some(Uuid::new_v4()),
            name: Some("Work"),
            branch: Some("vk/fixture"),
            session_id: Some(Uuid::new_v4()),
            executor: Some("CODEX"),
            repos: &repos,
            expected_issue_id: None,
            chat_previous_issue_id: None,
            expected_link_revision: None,
            target_issue_id: None,
        };
        let row = IssueWorkflow::reserve(&pool, &request).await.unwrap();
        sqlx::query("UPDATE issue_workflows SET chat_completed=1")
            .execute(&pool)
            .await
            .unwrap();
        (pool, row)
    }

    #[tokio::test]
    async fn concurrent_native_dispatch_claims_exactly_one_effect() {
        let (pool, row) = reserved_fixture().await;
        let count = std::sync::atomic::AtomicUsize::new(0);
        let dispatch = || async {
            count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            let execution = Uuid::new_v4();
            sqlx::query("INSERT INTO execution_processes(id,session_id) VALUES(?,?)")
                .bind(execution)
                .bind(row.session_id)
                .execute(&pool)
                .await?;
            Ok(execution)
        };
        let (a, b) = tokio::join!(
            dispatch_once(&pool, &row, dispatch),
            dispatch_once(&pool, &row, dispatch)
        );
        assert!(a.is_ok() && b.is_ok());
        assert_eq!(count.load(std::sync::atomic::Ordering::SeqCst), 1);
        let number: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(number, 1);
    }

    #[tokio::test]
    async fn cancelled_handler_after_claim_never_reissues_launch() {
        let (pool, row) = reserved_fixture().await;
        let (send, receive) = tokio::sync::oneshot::channel();
        let (owned_pool, owned_row) = (pool.clone(), row.clone());
        let task = tokio::spawn(async move {
            dispatch_once(&owned_pool, &owned_row, || async move {
                let _ = send.send(());
                std::future::pending::<Result<Uuid, ApiError>>().await
            })
            .await
        });
        receive.await.unwrap();
        task.abort();
        assert!(task.await.unwrap_err().is_cancelled());
        let called = std::sync::atomic::AtomicBool::new(false);
        let result = dispatch_once(&pool, &row, || async {
            called.store(true, std::sync::atomic::Ordering::SeqCst);
            Err(ApiError::Conflict("Duplicate dispatch".into()))
        })
        .await
        .unwrap();
        assert!(!called.load(std::sync::atomic::Ordering::SeqCst));
        assert_eq!(result.phase, "launching");
        assert_eq!(result.workspace_id, row.workspace_id);
    }

    #[tokio::test]
    async fn lost_response_after_process_persistence_reconciles_terminal_without_retry() {
        let (pool, row) = reserved_fixture().await;
        let execution = Uuid::new_v4();
        let unknown = dispatch_once(&pool, &row, || async {
            sqlx::query("INSERT INTO execution_processes(id,session_id) VALUES(?,?)")
                .bind(execution)
                .bind(row.session_id)
                .execute(&pool)
                .await?;
            Err(ApiError::BadGateway(
                "Synthetic lost native response".into(),
            ))
        })
        .await
        .unwrap();
        assert_eq!(unknown.phase, "launching");
        sqlx::query("UPDATE execution_processes SET status='failed'")
            .execute(&pool)
            .await
            .unwrap();
        let called = std::sync::atomic::AtomicBool::new(false);
        let result = dispatch_once(&pool, &row, || async {
            called.store(true, std::sync::atomic::Ordering::SeqCst);
            Err(ApiError::Conflict("Duplicate dispatch".into()))
        })
        .await
        .unwrap();
        assert!(!called.load(std::sync::atomic::Ordering::SeqCst));
        assert_eq!(result.phase, "settled");
        assert_eq!(result.execution_process_id, Some(execution));
    }
}
