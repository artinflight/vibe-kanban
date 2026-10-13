//! Actual idle worker + durable models on synthetic state; no HTTP/live agents.
use db::models::{
    coding_agent_turn::CreateCodingAgentTurn, execution_process::CreateExecutionProcess,
    session::CreateSession, workspace::CreateWorkspace, workspace_repo::CreateWorkspaceRepo,
};
use executors::profile::ExecutorConfig;
use sqlx::sqlite::SqlitePoolOptions;

use super::*;

#[cfg(target_os = "linux")]
#[tokio::test]
async fn idle_worker_preserves_queued_input_live_writers_and_failed_jobs_without_new_turns() {
    use std::os::unix::process::CommandExt;
    assert!(
        !crate::turn_preservation::enabled(),
        "fixture requires unconfigured publication"
    );
    let root = tempfile::tempdir().unwrap();
    let repo_path = root.path().join("repo");
    std::fs::create_dir(&repo_path).unwrap();
    std::fs::write(repo_path.join("source.txt"), "owner work survives failure").unwrap();
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let repo = Repo::find_or_create(&pool, &repo_path, "fixture")
        .await
        .unwrap();
    let workspace = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "feat/fixture".into(),
            name: Some("Synthetic checkpoint owner".into()),
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    sqlx::query("UPDATE workspaces SET container_ref = ? WHERE id = ?")
        .bind(root.path().to_str().unwrap())
        .bind(workspace.id)
        .execute(&pool)
        .await
        .unwrap();
    WorkspaceRepo::create_many(
        &pool,
        workspace.id,
        &[CreateWorkspaceRepo {
            repo_id: repo.id,
            target_branch: "staging".into(),
        }],
    )
    .await
    .unwrap();
    let session = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: None,
        },
        Uuid::new_v4(),
        workspace.id,
    )
    .await
    .unwrap();
    let execution = ExecutionProcess::create(
        &pool,
        &CreateExecutionProcess {
            session_id: session.id,
            executor_action: ExecutorAction::new(
                ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                    prompt: "Synthetic work".into(),
                    executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                    working_dir: None,
                }),
                None,
            ),
            run_reason: ExecutionProcessRunReason::CodingAgent,
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    CodingAgentTurn::create(
        &pool,
        &CreateCodingAgentTurn {
            execution_process_id: execution.id,
            prompt: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    CodingAgentTurn::update_summary(
        &pool,
        execution.id,
        "Owner summary\n\n[Automatic GitHub checkpoint]\nuser content",
    )
    .await
    .unwrap();
    ExecutionProcess::update_completion(
        &pool,
        execution.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    let ctx = ExecutionProcess::load_context(&pool, execution.id)
        .await
        .unwrap();
    let request = LocalContainerService::preservation_request(
        &ctx.workspace,
        &ctx.execution_process,
        &ctx.repos,
        false,
    );
    TurnGithubSync::enqueue(&pool, execution.id, workspace.id, &request.to_string())
        .await
        .unwrap();
    // This fixture isolates idle/input fencing; completion observation is covered below.
    assert!(
        TurnGithubSync::claim_observation(&pool, execution.id)
            .await
            .unwrap()
    );
    TurnGithubSync::record_observation(&pool, execution.id, true, "fixture durable originals")
        .await
        .unwrap();
    let queue = QueuedMessageService::new();
    let config = Arc::new(RwLock::new(Config::default()));
    let container = LocalContainerService::new(
        DBService { pool: pool.clone() },
        Arc::new(RwLock::new(HashMap::new())),
        config,
        GitService::new(),
        FileService::new(pool.clone()).unwrap(),
        None,
        Approvals::new(),
        queue.clone(),
        None,
    )
    .await;
    let mut writer = std::process::Command::new("sleep")
        .arg("30")
        .process_group(0)
        .spawn()
        .unwrap();
    TurnGithubSync::bind_group(&pool, execution.id, writer.id())
        .await
        .unwrap();
    queue.queue_message(
        session.id,
        DraftFollowUpData {
            message: "Incoming user work".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        },
    );
    container.sync_one_idle_turn().await;
    assert!(queue.has_queued(session.id));
    assert!(
        writer.try_wait().unwrap().is_none(),
        "worker must not interrupt a live writer"
    );
    assert_eq!(
        TurnGithubSync::for_workspace(&pool, workspace.id)
            .await
            .unwrap()[0]
            .attempts,
        0
    );
    queue.cancel_queued(session.id);
    sqlx::query("UPDATE turn_github_sync SET retry_at = 0")
        .execute(&pool)
        .await
        .unwrap();
    container.sync_one_idle_turn().await;
    assert!(writer.try_wait().unwrap().is_none());
    assert_eq!(
        TurnGithubSync::for_workspace(&pool, workspace.id)
            .await
            .unwrap()[0]
            .attempts,
        0
    );
    writer.kill().unwrap();
    writer.wait().unwrap();
    sqlx::query("UPDATE turn_github_sync SET retry_at = 0")
        .execute(&pool)
        .await
        .unwrap();
    container.sync_one_idle_turn().await;
    let job = TurnGithubSync::for_workspace(&pool, workspace.id)
        .await
        .unwrap()
        .remove(0);
    assert_eq!(job.state, "blocked");
    assert!(job.report.unwrap().contains("not configured"));
    assert_eq!(
        std::fs::read_to_string(repo_path.join("source.txt")).unwrap(),
        "owner work survives failure"
    );
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(
        count, 1,
        "direct checkpoints cannot create sync-prompt loops"
    );
    let summary = CodingAgentTurn::find_by_execution_process_id(&pool, execution.id)
        .await
        .unwrap()
        .unwrap()
        .summary
        .unwrap();
    assert!(summary.starts_with("Owner summary\n\n[Automatic GitHub checkpoint]\nuser content"));
}

#[cfg(target_os = "linux")]
struct ObservationFixture {
    _root: tempfile::TempDir,
    workspace_root: std::path::PathBuf,
    repo: std::path::PathBuf,
    policy: std::path::PathBuf,
    database: String,
    container: LocalContainerService,
    execution: Uuid,
    session: Uuid,
    workspace: Uuid,
    a: String,
    b: String,
    request: serde_json::Value,
}

#[cfg(target_os = "linux")]
impl Drop for ObservationFixture {
    fn drop(&mut self) {
        // This fixture created and exclusively owns this UUID's synthetic directory.
        let _ = std::fs::remove_dir_all(&self.workspace_root);
    }
}

#[cfg(target_os = "linux")]
fn fixture_git(repo: &Path, args: &[&str]) -> String {
    let output = std::process::Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .output()
        .unwrap();
    assert!(output.status.success(), "fixture Git failed: {:?}", args);
    String::from_utf8(output.stdout).unwrap().trim().into()
}

#[cfg(target_os = "linux")]
async fn observation_container(pool: sqlx::SqlitePool, policy: &Path) -> LocalContainerService {
    let mut container = LocalContainerService::new(
        DBService { pool: pool.clone() },
        Arc::new(RwLock::new(HashMap::new())),
        Arc::new(RwLock::new(Config::default())),
        GitService::new(),
        FileService::new(pool).unwrap(),
        None,
        Approvals::new(),
        QueuedMessageService::new(),
        None,
    )
    .await;
    container.preservation_config = Some(policy.to_path_buf());
    container
}

#[cfg(target_os = "linux")]
impl ObservationFixture {
    async fn new() -> Self {
        let root = tempfile::tempdir().unwrap();
        let repo_path = root.path().join("repo");
        std::fs::create_dir(&repo_path).unwrap();
        fixture_git(&repo_path, &["init", "-q", "-b", "staging"]);
        fixture_git(&repo_path, &["config", "user.name", "Fixture"]);
        fixture_git(
            &repo_path,
            &["config", "user.email", "fixture@example.invalid"],
        );
        std::fs::write(repo_path.join("source.txt"), "A\n").unwrap();
        fixture_git(&repo_path, &["add", "."]);
        fixture_git(&repo_path, &["commit", "-qm", "A"]);
        let a = fixture_git(&repo_path, &["rev-parse", "HEAD"]);
        let database = format!(
            "sqlite://{}?mode=rwc",
            root.path().join("queue.sqlite").display()
        );
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&database)
            .await
            .unwrap();
        sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
        let repo = Repo::find_or_create(&pool, &repo_path, "fixture")
            .await
            .unwrap();
        let workspace = Workspace::create(
            &pool,
            &CreateWorkspace {
                branch: "feat/fixture".into(),
                name: Some("Observation fixture".into()),
            },
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        let common_dir = repo_path.join(".git");
        let workspace_root = LocalContainerService::default_workspace_dir(&workspace);
        assert!(
            !workspace_root.exists(),
            "fixture must own a new exact workspace directory"
        );
        std::fs::create_dir_all(&workspace_root).unwrap();
        let worktree = workspace_root.join(&repo.name);
        fixture_git(
            &repo_path,
            &[
                "worktree",
                "add",
                "-q",
                "-b",
                "feat/fixture",
                worktree.to_str().unwrap(),
                "staging",
            ],
        );
        let repo_path = worktree;
        sqlx::query("UPDATE workspaces SET container_ref = ? WHERE id = ?")
            .bind(workspace_root.to_str().unwrap())
            .bind(workspace.id)
            .execute(&pool)
            .await
            .unwrap();
        WorkspaceRepo::create_many(
            &pool,
            workspace.id,
            &[CreateWorkspaceRepo {
                repo_id: repo.id,
                target_branch: "staging".into(),
            }],
        )
        .await
        .unwrap();
        let session = Session::create(
            &pool,
            &CreateSession {
                executor: Some("CODEX".into()),
                name: None,
            },
            Uuid::new_v4(),
            workspace.id,
        )
        .await
        .unwrap();
        let execution = ExecutionProcess::create(
            &pool,
            &CreateExecutionProcess {
                session_id: session.id,
                executor_action: ExecutorAction::new(
                    ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                        prompt: "Synthetic owner".into(),
                        executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                        working_dir: None,
                    }),
                    None,
                ),
                run_reason: ExecutionProcessRunReason::CodingAgent,
            },
            Uuid::new_v4(),
            &[
                db::models::execution_process_repo_state::CreateExecutionProcessRepoState {
                    repo_id: repo.id,
                    before_head_commit: Some(a.clone()),
                    after_head_commit: None,
                    merge_commit: None,
                },
            ],
        )
        .await
        .unwrap();
        CodingAgentTurn::create(
            &pool,
            &CreateCodingAgentTurn {
                execution_process_id: execution.id,
                prompt: None,
            },
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        CodingAgentTurn::update_summary(&pool, execution.id, "Completed owner B")
            .await
            .unwrap();
        let ctx = ExecutionProcess::load_context(&pool, execution.id)
            .await
            .unwrap();
        let request = LocalContainerService::preservation_request(
            &ctx.workspace,
            &ctx.execution_process,
            &ctx.repos,
            false,
        );
        TurnGithubSync::enqueue(&pool, execution.id, workspace.id, &request.to_string())
            .await
            .unwrap();
        let policy = root.path().join("policy.json");
        std::fs::create_dir(root.path().join("private-state")).unwrap();
        let mut mount = root.path();
        // Match the production helper's mounted-storage constraint on this synthetic host.
        while !std::process::Command::new("mountpoint")
            .arg("-q")
            .arg(mount)
            .status()
            .unwrap()
            .success()
        {
            mount = mount.parent().unwrap();
        }
        std::fs::write(&policy, json!({"storage_mount": mount, "state_root": root.path().join("private-state"),
            "repositories": { repo.id.to_string(): {"common_dir": common_dir, "allowed": ["source.txt"]} }
        }).to_string()).unwrap();
        let container = observation_container(pool, &policy).await;
        assert_eq!(
            container
                .invoke_preservation("begin", request.clone())
                .await["state"],
            "pending"
        );
        std::fs::write(repo_path.join("source.txt"), "B\n").unwrap();
        fixture_git(&repo_path, &["add", "."]);
        fixture_git(&repo_path, &["commit", "-qm", "B"]);
        let b = fixture_git(&repo_path, &["rev-parse", "HEAD"]);
        Self {
            _root: root,
            workspace_root,
            repo: repo_path,
            policy,
            database,
            container,
            execution: execution.id,
            session: session.id,
            workspace: workspace.id,
            a,
            b,
            request,
        }
    }

    async fn callback(&self) {
        use command_group::AsyncCommandGroup;
        let mut child = tokio::process::Command::new("true").group_spawn().unwrap();
        let group = child.inner().id().unwrap();
        TurnGithubSync::bind_group(&self.container.db.pool, self.execution, group)
            .await
            .unwrap();
        self.container
            .child_store
            .write()
            .await
            .insert(self.execution, Arc::new(RwLock::new(child)));
        tokio::time::timeout(
            Duration::from_secs(15),
            self.container
                .spawn_exit_monitor(&self.execution, None, Some(group)),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(
            ExecutionProcess::find_by_id(&self.container.db.pool, self.execution)
                .await
                .unwrap()
                .unwrap()
                .status,
            ExecutionProcessStatus::Completed
        );
    }

    async fn reopen(&mut self) {
        self.container.db.pool.close().await;
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&self.database)
            .await
            .unwrap();
        self.container = observation_container(pool, &self.policy).await;
    }

    async fn assert_gate(&self, expected: &str) {
        let pool = &self.container.db.pool;
        assert_eq!(
            TurnGithubSync::for_workspace(pool, self.workspace)
                .await
                .unwrap()[0]
                .observation_state,
            expected
        );
        let error = self
            .container
            .reset_session_to_process(self.session, self.execution, true, true)
            .await
            .unwrap_err();
        assert!(error.to_string().contains("observation is unproven"));
        assert_eq!(fixture_git(&self.repo, &["rev-parse", "HEAD"]), self.b);
        assert!(
            ExecutionProcess::find_by_id(pool, self.execution)
                .await
                .unwrap()
                .is_some()
        );
        // External rewrite cannot turn restored policy + the old A ledger into green.
        fixture_git(&self.repo, &["reset", "--hard", &self.a]);
        self.container.sync_one_idle_turn().await;
        let jobs = TurnGithubSync::for_workspace(pool, self.workspace)
            .await
            .unwrap();
        assert_eq!(jobs[0].state, "blocked");
        assert!(
            jobs[0]
                .report
                .as_ref()
                .unwrap()
                .contains("observation is unproven")
        );
        // A later owner's success cannot launder this workspace's older obligation.
        let later = Uuid::new_v4();
        TurnGithubSync::enqueue(pool, later, self.workspace, &self.request.to_string())
            .await
            .unwrap();
        assert!(
            TurnGithubSync::claim_observation(pool, later)
                .await
                .unwrap()
        );
        TurnGithubSync::record_observation(pool, later, true, "later originals")
            .await
            .unwrap();
        let later_job = TurnGithubSync::for_workspace(pool, self.workspace)
            .await
            .unwrap()
            .remove(0);
        later_job
            .record(pool, "verified", "old A receipt")
            .await
            .unwrap();
        assert_ne!(
            TurnGithubSync::for_workspace(pool, self.workspace)
                .await
                .unwrap()[0]
                .state,
            "verified"
        );
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn observation_callback_failure_reset_and_worker_survive_restart_and_policy_restore() {
    for policy_changed in [false, true] {
        let mut fixture = ObservationFixture::new().await;
        let saved = std::fs::read(&fixture.policy).unwrap();
        if policy_changed {
            let mut policy: serde_json::Value = serde_json::from_slice(&saved).unwrap();
            policy["publication_review"] = json!("changed after admission");
            std::fs::write(&fixture.policy, policy.to_string()).unwrap();
        } else {
            std::fs::remove_file(&fixture.policy).unwrap();
        }
        fixture.callback().await;
        std::fs::write(&fixture.policy, saved).unwrap();
        // A later callback with restored policy must not erase the known failure.
        fixture
            .container
            .observe_completed_turn(fixture.execution)
            .await;
        fixture.reopen().await;
        fixture.assert_gate("failed").await;
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn observation_callback_persistence_failure_and_lost_callback_keep_pending_gate() {
    for stage in ["lost", "claim", "finish-success", "finish-failure"] {
        let mut fixture = ObservationFixture::new().await;
        let saved_policy = std::fs::read(&fixture.policy).unwrap();
        if stage == "lost" {
            ExecutionProcess::update_completion(
                &fixture.container.db.pool,
                fixture.execution,
                ExecutionProcessStatus::Completed,
                Some(0),
            )
            .await
            .unwrap();
            TurnGithubSync::bind_group(&fixture.container.db.pool, fixture.execution, u32::MAX)
                .await
                .unwrap();
        } else {
            let condition = if stage == "claim" {
                "1"
            } else {
                "NEW.observation_state != 'observing'"
            };
            sqlx::raw_sql(&format!("CREATE TRIGGER fail_observation BEFORE UPDATE OF observation_state ON turn_github_sync WHEN {condition} BEGIN SELECT RAISE(FAIL, 'synthetic persistence failure'); END;"))
                .execute(&fixture.container.db.pool).await.unwrap();
            if stage == "finish-failure" {
                std::fs::remove_file(&fixture.policy).unwrap();
            }
            fixture.callback().await;
            sqlx::raw_sql("DROP TRIGGER fail_observation")
                .execute(&fixture.container.db.pool)
                .await
                .unwrap();
            std::fs::write(&fixture.policy, saved_policy).unwrap();
        }
        fixture.reopen().await;
        let expected = if stage.starts_with("finish") {
            "observing"
        } else {
            "pending"
        };
        fixture.assert_gate(expected).await;
        // Even after external B->A, restored policy must not recapture A as B.
        fixture
            .container
            .observe_completed_turn(fixture.execution)
            .await;
        let job = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
            .await
            .unwrap()
            .into_iter()
            .find(|j| j.execution_process_id == fixture.execution)
            .unwrap();
        assert_eq!(job.observation_state, expected);
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn observation_callback_acknowledges_original_b_before_normal_reset() {
    let fixture = ObservationFixture::new().await;
    fixture.callback().await;
    assert!(
        !TurnGithubSync::has_unobserved(&fixture.container.db.pool, fixture.workspace)
            .await
            .unwrap()
    );
    let report = fixture
        .container
        .invoke_preservation("observe-finished", fixture.request.clone())
        .await;
    assert!(crate::turn_preservation::observed(&report), "{report}");
    assert!(
        report["repositories"][0]["original_commits"]
            .as_array()
            .unwrap()
            .iter()
            .any(|c| c == &fixture.b)
    );
    fixture
        .container
        .reset_session_to_process(fixture.session, fixture.execution, true, true)
        .await
        .unwrap();
    assert_eq!(
        fixture_git(&fixture.repo, &["rev-parse", "HEAD"]),
        fixture.a
    );
    fixture.container.sync_one_idle_turn().await;
    let job = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
        .await
        .unwrap()
        .remove(0);
    assert_ne!(
        job.state, "verified",
        "reset must retain the original owner's job"
    );
}
