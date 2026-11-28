//! Atomic local issue/assignment/workspace identity reservation. Native effects
//! remain in ContainerService and its existing shared admission boundary.
use serde::Serialize;
use sqlx::{FromRow, SqlitePool};
use thiserror::Error;
use uuid::Uuid;

use super::task::TaskStatus;

pub const RELINK_SQL: &str = include_str!("issue_workflow_sql/relink.sql");
pub const CLAIM_LAUNCH_SQL: &str = include_str!("issue_workflow_sql/claim_launch.sql");

#[derive(Debug, Error)]
pub enum WorkflowError {
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error("{0}")]
    Conflict(&'static str),
}

#[derive(Debug, Clone, FromRow, Serialize)]
pub struct IssueWorkflow {
    pub request_id: Uuid,
    pub project_id: Uuid,
    pub request_hash: String,
    pub operation: String,
    pub issue_id: Uuid,
    pub dot_user_id: Uuid,
    pub workspace_id: Option<Uuid>,
    pub session_id: Option<Uuid>,
    pub previous_issue_id: Option<Uuid>,
    pub chat_previous_issue_id: Option<Uuid>,
    pub chat_completed: bool,
    pub link_revision: Option<i64>,
    pub phase: String,
    pub execution_process_id: Option<Uuid>,
}

pub struct ReservedRepo {
    pub repo_id: Uuid,
    pub target_branch: String,
}

pub struct Reservation<'a> {
    pub request_id: Uuid,
    pub project_id: Uuid,
    pub request_hash: &'a str,
    pub operation: &'a str,
    pub issue_id: Uuid,
    pub title: &'a str,
    pub description: &'a str,
    pub status: TaskStatus,
    pub workspace_id: Option<Uuid>,
    pub name: Option<&'a str>,
    pub branch: Option<&'a str>,
    pub session_id: Option<Uuid>,
    pub executor: Option<&'a str>,
    pub repos: &'a [ReservedRepo],
    pub expected_issue_id: Option<Uuid>,
    pub chat_previous_issue_id: Option<Uuid>,
    pub expected_link_revision: Option<i64>,
    // Some only when linking to an existing issue; otherwise create one atomically.
    pub target_issue_id: Option<Uuid>,
}

impl IssueWorkflow {
    pub async fn find(pool: &SqlitePool, request: Uuid) -> Result<Option<Self>, sqlx::Error> {
        sqlx::query_as("SELECT request_id,project_id,request_hash,operation,issue_id,dot_user_id,workspace_id,session_id,previous_issue_id,chat_previous_issue_id,chat_completed,link_revision,phase,execution_process_id FROM issue_workflows WHERE request_id=?")
            .bind(request).fetch_optional(pool).await
    }

    pub async fn reserve(pool: &SqlitePool, r: &Reservation<'_>) -> Result<Self, WorkflowError> {
        let mut tx = pool.begin().await?;
        // Acquire SQLite's writer reservation BEFORE reads, including on absent
        // keys. This uses the same ordinary transaction path as existing models.
        sqlx::query("UPDATE issue_workflows SET request_hash=request_hash WHERE request_id=?")
            .bind(r.request_id)
            .execute(&mut *tx)
            .await?;
        let old: Option<Self> = sqlx::query_as("SELECT request_id,project_id,request_hash,operation,issue_id,dot_user_id,workspace_id,session_id,previous_issue_id,chat_previous_issue_id,chat_completed,link_revision,phase,execution_process_id FROM issue_workflows WHERE request_id=?")
            .bind(r.request_id).fetch_optional(&mut *tx).await?;
        if let Some(old) = old {
            if old.project_id != r.project_id
                || old.request_hash != r.request_hash
                || old.operation != r.operation
            {
                return Err(WorkflowError::Conflict("Request identity changed"));
            }
            tx.commit().await?;
            return Ok(old);
        }
        let valid_project: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM projects WHERE id=? AND remote_project_id IS NULL AND archived=0)")
            .bind(r.project_id).fetch_one(&mut *tx).await?;
        if !valid_project {
            return Err(WorkflowError::Conflict(
                "Active real local project required",
            ));
        }
        let dots: Vec<Uuid> =
            sqlx::query_scalar("SELECT id FROM local_participants WHERE username='dot'")
                .fetch_all(&mut *tx)
                .await?;
        let [dot] = dots.as_slice() else {
            return Err(WorkflowError::Conflict(
                "Verified unique dot identity required",
            ));
        };
        if r.operation == "relink" {
            let pending: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM issue_workflows r JOIN workspaces w ON w.id=r.workspace_id WHERE r.workspace_id=? AND r.operation IN ('start','relink') AND r.chat_completed=0 AND w.task_id=r.issue_id AND COALESCE((SELECT revision FROM workspace_issue_link_revisions WHERE workspace_id=w.id),0)=r.link_revision)")
                .bind(r.workspace_id).fetch_one(&mut *tx).await?;
            if pending {
                return Err(WorkflowError::Conflict(
                    "Complete previous chat migration first",
                ));
            }
            if let Some(chat_old) = r.chat_previous_issue_id {
                let valid: bool = sqlx::query_scalar(
                    "SELECT EXISTS(SELECT 1 FROM tasks WHERE id=? AND project_id=?)",
                )
                .bind(chat_old)
                .bind(r.project_id)
                .fetch_one(&mut *tx)
                .await?;
                if !valid
                    || (Some(chat_old) != r.expected_issue_id
                        && r.target_issue_id != r.expected_issue_id)
                {
                    return Err(WorkflowError::Conflict(
                        "Chat history catch-up requires an explicit same-project no-op link",
                    ));
                }
            }
        }
        let issue = r.target_issue_id.unwrap_or(r.issue_id);
        if let Some(target) = r.target_issue_id {
            let valid: bool = sqlx::query_scalar(
                "SELECT EXISTS(SELECT 1 FROM tasks WHERE id=? AND project_id=?)",
            )
            .bind(target)
            .bind(r.project_id)
            .fetch_one(&mut *tx)
            .await?;
            if !valid || r.operation != "relink" {
                return Err(WorkflowError::Conflict(
                    "Target issue unavailable in project",
                ));
            }
        } else {
            let duplicate: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM tasks WHERE project_id=? AND lower(trim(title))=lower(trim(?)))")
                .bind(r.project_id).bind(r.title).fetch_one(&mut *tx).await?;
            if duplicate {
                return Err(WorkflowError::Conflict(
                    "Dedicated issue title already exists; select that issue",
                ));
            }
            sqlx::query(
                "INSERT INTO tasks(id,project_id,title,description,status) VALUES(?,?,?,?,?)",
            )
            .bind(issue)
            .bind(r.project_id)
            .bind(r.title)
            .bind(r.description)
            .bind(&r.status)
            .execute(&mut *tx)
            .await?;
        }
        sqlx::query("INSERT INTO local_issue_assignees(id,issue_id,user_id) VALUES(?,?,?) ON CONFLICT(issue_id,user_id) DO NOTHING")
            .bind(Uuid::new_v4()).bind(issue).bind(dot).execute(&mut *tx).await?;
        let mut revision = None;
        if r.operation == "start" {
            let workspace = r
                .workspace_id
                .ok_or(WorkflowError::Conflict("Workspace identity required"))?;
            let session = r
                .session_id
                .ok_or(WorkflowError::Conflict("Session identity required"))?;
            if r.repos.is_empty() || r.repos.len() > 8 {
                return Err(WorkflowError::Conflict(
                    "Explicit project repositories required",
                ));
            }
            sqlx::query("INSERT INTO workspaces(id,task_id,branch,name) VALUES(?,?,?,?)")
                .bind(workspace)
                .bind(issue)
                .bind(r.branch.ok_or(WorkflowError::Conflict("Branch required"))?)
                .bind(r.name)
                .execute(&mut *tx)
                .await?;
            let mut working_dir = None;
            for repo in r.repos {
                let entry: Option<(String, Option<String>)> = sqlx::query_as("SELECT r.name,r.default_working_dir FROM repos r JOIN project_repos p ON p.repo_id=r.id WHERE p.project_id=? AND r.id=?")
                    .bind(r.project_id).bind(repo.repo_id).fetch_optional(&mut *tx).await?;
                let Some((name, subdir)) = entry else {
                    return Err(WorkflowError::Conflict("Repository outside project"));
                };
                if r.repos.len() == 1 {
                    let path = subdir.filter(|v| !v.is_empty()).map_or_else(
                        || std::path::PathBuf::from(&name),
                        |dir| std::path::PathBuf::from(&name).join(dir),
                    );
                    working_dir = Some(path.to_string_lossy().into_owned());
                }
                sqlx::query("INSERT INTO workspace_repos(id,workspace_id,repo_id,target_branch) VALUES(?,?,?,?)")
                    .bind(Uuid::new_v4()).bind(workspace).bind(repo.repo_id).bind(&repo.target_branch)
                    .execute(&mut *tx).await?;
            }
            sqlx::query(
                "INSERT INTO sessions(id,workspace_id,executor,agent_working_dir) VALUES(?,?,?,?)",
            )
            .bind(session)
            .bind(workspace)
            .bind(r.executor)
            .bind(working_dir)
            .execute(&mut *tx)
            .await?;
            revision = Some(0);
        } else if r.operation == "relink" {
            let changed = sqlx::query(RELINK_SQL)
                .bind(issue)
                .bind(r.workspace_id)
                .bind(r.expected_issue_id)
                .bind(r.expected_link_revision)
                .bind(issue)
                .bind(r.project_id)
                .execute(&mut *tx)
                .await?
                .rows_affected();
            if changed != 1 {
                return Err(WorkflowError::Conflict(
                    "Workspace link changed or is outside project",
                ));
            }
            revision = sqlx::query_scalar(
                "SELECT revision FROM workspace_issue_link_revisions WHERE workspace_id=?",
            )
            .bind(r.workspace_id)
            .fetch_optional(&mut *tx)
            .await?;
            // Linking to the same issue is an explicit no-op and still has a receipt.
            revision = Some(revision.unwrap_or(0));
        } else if r.operation != "create" {
            return Err(WorkflowError::Conflict("Unsupported issue operation"));
        }
        sqlx::query("INSERT INTO issue_workflows(request_id,project_id,request_hash,operation,issue_id,dot_user_id,workspace_id,session_id,previous_issue_id,chat_previous_issue_id,chat_completed,link_revision,phase) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
            .bind(r.request_id).bind(r.project_id).bind(r.request_hash).bind(r.operation).bind(issue).bind(dot)
            .bind(r.workspace_id).bind(r.session_id).bind(r.expected_issue_id).bind(r.chat_previous_issue_id).bind(r.operation == "create").bind(revision)
            .bind(if r.operation == "relink" { "linked" } else { "reserved" }).execute(&mut *tx).await?;
        tx.commit().await?;
        Self::find(pool, r.request_id)
            .await?
            .ok_or(WorkflowError::Conflict("Receipt unavailable"))
    }

    pub async fn claim_launch(&self, pool: &SqlitePool) -> Result<bool, sqlx::Error> {
        Ok(sqlx::query(CLAIM_LAUNCH_SQL)
            .bind(self.request_id)
            .bind(&self.request_hash)
            .execute(pool)
            .await?
            .rows_affected()
            == 1)
    }

    /// A persisted terminal record closes an uncertain native start without
    /// claiming successful execution or issuing another effect. Missing/running
    /// records remain uncertain. Called only from the explicit retry POST.
    pub async fn reconcile_terminal(&self, pool: &SqlitePool) -> Result<(), sqlx::Error> {
        sqlx::query(include_str!("issue_workflow_sql/reconcile_launch.sql"))
            .bind(self.request_id)
            .execute(pool)
            .await?;
        Ok(())
    }

    pub async fn record_started(
        &self,
        pool: &SqlitePool,
        execution: Uuid,
    ) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE issue_workflows SET phase='started',execution_process_id=?,updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE request_id=? AND phase='launching' AND EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=? AND e.session_id=issue_workflows.session_id)")
            .bind(execution).bind(self.request_id).bind(execution).execute(pool).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    async fn fixture() -> (SqlitePool, Uuid, Uuid, Uuid) {
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::raw_sql(include_str!("issue_workflow_sql/test_schema.sql"))
            .execute(&pool)
            .await
            .unwrap();
        sqlx::raw_sql(include_str!(
            "../../migrations/20261024180000_issue_workflows.sql"
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
        sqlx::query("INSERT INTO repos VALUES(?,'repo','src')")
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
        (pool, project, repo, dot)
    }

    fn request(project: Uuid, repos: &[ReservedRepo]) -> Reservation<'_> {
        Reservation {
            request_id: Uuid::new_v4(),
            project_id: project,
            request_hash: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            operation: "start",
            issue_id: Uuid::new_v4(),
            title: "Dedicated",
            description: "Original",
            status: TaskStatus::Todo,
            workspace_id: Some(Uuid::new_v4()),
            name: Some("Work"),
            branch: Some("vk/fixture"),
            session_id: Some(Uuid::new_v4()),
            executor: Some("CODEX"),
            repos,
            expected_issue_id: None,
            chat_previous_issue_id: None,
            expected_link_revision: None,
            target_issue_id: None,
        }
    }

    #[tokio::test]
    async fn atomic_reservation_retries_and_concurrent_callers_keep_all_identities() {
        let (pool, project, repo, dot) = fixture().await;
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let r = request(project, &repos);
        let (a, b) = tokio::join!(
            IssueWorkflow::reserve(&pool, &r),
            IssueWorkflow::reserve(&pool, &r)
        );
        let (a, b) = (a.unwrap(), b.unwrap());
        assert_eq!(a.workspace_id, b.workspace_id);
        assert_eq!(a.session_id, b.session_id);
        assert_eq!(a.issue_id, b.issue_id);
        assert_eq!(a.dot_user_id, dot);
        for table in [
            "tasks",
            "workspaces",
            "sessions",
            "workspace_repos",
            "local_issue_assignees",
            "issue_workflows",
        ] {
            let count: i64 = sqlx::query_scalar(&format!("SELECT count(*) FROM {table}"))
                .fetch_one(&pool)
                .await
                .unwrap();
            assert_eq!(count, 1);
        }
        let path: String = sqlx::query_scalar("SELECT agent_working_dir FROM sessions")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(path, "repo/src");
    }

    #[tokio::test]
    async fn partial_reservation_fault_rolls_back_issue_assignment_and_workspace() {
        let (pool, project, repo, _) = fixture().await;
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let r = request(project, &repos);
        sqlx::raw_sql("CREATE TRIGGER inject_crash BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT,'fixture crash'); END;").execute(&pool).await.unwrap();
        assert!(IssueWorkflow::reserve(&pool, &r).await.is_err());
        for table in [
            "tasks",
            "workspaces",
            "workspace_repos",
            "local_issue_assignees",
            "issue_workflows",
        ] {
            let count: i64 = sqlx::query_scalar(&format!("SELECT count(*) FROM {table}"))
                .fetch_one(&pool)
                .await
                .unwrap();
            assert_eq!(count, 0);
        }
        sqlx::query("DROP TRIGGER inject_crash")
            .execute(&pool)
            .await
            .unwrap();
        assert!(IssueWorkflow::reserve(&pool, &r).await.is_ok());
    }

    #[tokio::test]
    async fn foreign_project_repo_and_changed_request_never_partially_create() {
        let (pool, project, repo, _) = fixture().await;
        let foreign = [ReservedRepo {
            repo_id: Uuid::new_v4(),
            target_branch: "staging".into(),
        }];
        assert!(
            IssueWorkflow::reserve(&pool, &request(project, &foreign))
                .await
                .is_err()
        );
        let count: i64 = sqlx::query_scalar("SELECT count(*) FROM tasks")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(count, 0);
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let mut r = request(project, &repos);
        IssueWorkflow::reserve(&pool, &r).await.unwrap();
        r.request_hash = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        assert!(IssueWorkflow::reserve(&pool, &r).await.is_err());
    }

    #[tokio::test]
    async fn launch_write_ahead_claim_survives_handler_loss_and_never_replays() {
        let (pool, project, repo, _) = fixture().await;
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let r = request(project, &repos);
        let row = IssueWorkflow::reserve(&pool, &r).await.unwrap();
        assert!(!row.claim_launch(&pool).await.unwrap()); // Scope not acknowledged.
        sqlx::query("UPDATE issue_workflows SET chat_completed=1")
            .execute(&pool)
            .await
            .unwrap();
        assert!(row.claim_launch(&pool).await.unwrap());
        // Crash before/after process persistence both retain the SAME reservation.
        assert!(!row.claim_launch(&pool).await.unwrap());
        let read = IssueWorkflow::find(&pool, row.request_id)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(read.phase, "launching");
        let execution = Uuid::new_v4();
        sqlx::query("INSERT INTO execution_processes(id,session_id) VALUES(?,?)")
            .bind(execution)
            .bind(row.session_id)
            .execute(&pool)
            .await
            .unwrap();
        row.reconcile_terminal(&pool).await.unwrap();
        assert_eq!(
            IssueWorkflow::find(&pool, row.request_id)
                .await
                .unwrap()
                .unwrap()
                .phase,
            "launching"
        );
        sqlx::query("UPDATE execution_processes SET status='failed'")
            .execute(&pool)
            .await
            .unwrap();
        row.reconcile_terminal(&pool).await.unwrap();
        assert_eq!(
            IssueWorkflow::find(&pool, row.request_id)
                .await
                .unwrap()
                .unwrap()
                .phase,
            "settled"
        );
        row.record_started(&pool, execution).await.unwrap();
        assert!(!row.claim_launch(&pool).await.unwrap());
        let read = IssueWorkflow::find(&pool, row.request_id)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(read.execution_process_id, Some(execution));
    }

    #[tokio::test]
    async fn stale_relink_rolls_back_new_issue_and_assignment_and_rejects_aba() {
        let (pool, project, repo, _) = fixture().await;
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let initial = request(project, &repos);
        let first = IssueWorkflow::reserve(&pool, &initial).await.unwrap();
        sqlx::query("UPDATE issue_workflows SET chat_completed=1,phase='started'")
            .execute(&pool)
            .await
            .unwrap();
        let mut link = request(project, &[]);
        link.operation = "relink";
        link.title = "New dedicated";
        link.workspace_id = first.workspace_id;
        link.session_id = None;
        link.expected_issue_id = Some(first.issue_id);
        link.expected_link_revision = Some(0);
        let linked = IssueWorkflow::reserve(&pool, &link).await.unwrap();
        assert_eq!(linked.link_revision, Some(1));
        let mut race = request(project, &[]);
        race.operation = "relink";
        race.title = "Race";
        race.workspace_id = first.workspace_id;
        race.session_id = None;
        race.expected_issue_id = Some(first.issue_id);
        race.expected_link_revision = Some(0);
        assert!(IssueWorkflow::reserve(&pool, &race).await.is_err());
        let count: i64 = sqlx::query_scalar("SELECT count(*) FROM tasks")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(count, 2);
        sqlx::query("UPDATE issue_workflows SET chat_completed=1")
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("UPDATE workspaces SET task_id=?")
            .bind(first.issue_id)
            .execute(&pool)
            .await
            .unwrap();
        assert!(IssueWorkflow::reserve(&pool, &race).await.is_err()); // Same ID, newer revision.
    }

    #[tokio::test]
    async fn superseded_native_link_receipt_allows_explicit_current_chat_catchup() {
        let (pool, project, repo, _) = fixture().await;
        let repos = [ReservedRepo {
            repo_id: repo,
            target_branch: "staging".into(),
        }];
        let initial = IssueWorkflow::reserve(&pool, &request(project, &repos))
            .await
            .unwrap();
        sqlx::query("UPDATE issue_workflows SET chat_completed=1,phase='started'")
            .execute(&pool)
            .await
            .unwrap();
        let mut link = request(project, &[]);
        link.operation = "relink";
        link.title = "Linked issue";
        link.workspace_id = initial.workspace_id;
        link.session_id = None;
        link.expected_issue_id = Some(initial.issue_id);
        link.expected_link_revision = Some(0);
        let linked = IssueWorkflow::reserve(&pool, &link).await.unwrap();
        // A later legacy/native owner change supersedes the old native receipt,
        // but must not strand a current history migration or erase that receipt.
        sqlx::query("UPDATE workspaces SET task_id=?")
            .bind(initial.issue_id)
            .execute(&pool)
            .await
            .unwrap();
        let mut catchup = request(project, &[]);
        catchup.operation = "relink";
        catchup.workspace_id = initial.workspace_id;
        catchup.session_id = None;
        catchup.expected_issue_id = Some(initial.issue_id);
        catchup.expected_link_revision = Some(2);
        catchup.target_issue_id = Some(initial.issue_id);
        catchup.chat_previous_issue_id = Some(linked.issue_id);
        let current = IssueWorkflow::reserve(&pool, &catchup).await.unwrap();
        assert_eq!(current.issue_id, initial.issue_id);
        assert_eq!(current.link_revision, Some(2));
        assert!(
            !IssueWorkflow::find(&pool, linked.request_id)
                .await
                .unwrap()
                .unwrap()
                .chat_completed
        );
        let count: i64 = sqlx::query_scalar("SELECT count(*) FROM tasks")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(count, 2);
    }
}
