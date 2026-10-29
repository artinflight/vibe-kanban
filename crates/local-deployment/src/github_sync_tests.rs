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
#[tokio::test]
async fn idle_capacity_queue_wakes_without_completion_and_stops_on_shutdown() {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let mut container = observation_container(pool, Path::new("/unused-fixture-policy")).await;
    container.automatic_sync_override = Some(false);
    let queue = container.queued_message_service.clone();
    let draft = || DraftFollowUpData {
        message: "owned queue wakeup fixture; no agent launch".into(),
        executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
    };
    let normal = Uuid::new_v4();
    queue.queue_message(normal, draft());
    let first = Uuid::new_v4();
    queue.queue_for_capacity(first, draft());
    let shutdown = CancellationToken::new();
    let worker_shutdown = shutdown.clone();
    let worker = tokio::spawn(async move {
        container
            .poll_pending_work(worker_shutdown, Duration::from_millis(20))
            .await;
    });
    // Missing sessions are intentionally disposable fixture inputs: the actual
    // consumer reads SQL and discards them without launching any executor. This
    // tests autonomous wakeup, not a claim of successful agent continuation.
    for session in [first, Uuid::new_v4()] {
        if session != first {
            queue.queue_for_capacity(session, draft());
        }
        tokio::time::timeout(Duration::from_secs(2), async {
            while queue.has_queued(session) {
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .expect("idle queue must retry without another process completing");
    }
    assert!(
        queue.has_queued(normal),
        "ordinary queued input is not consumed"
    );
    shutdown.cancel();
    tokio::time::timeout(Duration::from_secs(2), worker)
        .await
        .unwrap()
        .unwrap();
    let after_shutdown = Uuid::new_v4();
    queue.queue_for_capacity(after_shutdown, draft());
    tokio::time::sleep(Duration::from_millis(40)).await;
    assert!(queue.has_queued(after_shutdown));
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn idle_capacity_queue_never_replays_uncertain_restored_batch() {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let mut container =
        observation_container(pool.clone(), Path::new("/unused-fixture-policy")).await;
    container.automatic_sync_override = Some(false);
    let session = Uuid::new_v4();
    let queued = container.queued_message_service.queue_for_capacity(
        session,
        DraftFollowUpData {
            message: "uncertain dispatched input must survive".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        },
    );
    let data = serde_json::to_string(&queued).unwrap();
    sqlx::query("INSERT INTO turn_github_sync_user_queue VALUES (?, ?, ?, 'dispatching')")
        .bind(session)
        .bind(Uuid::new_v4())
        .bind(&data)
        .execute(&pool)
        .await
        .unwrap();
    container.queued_message_service = QueuedMessageService::new();
    container
        .queued_message_service
        .restore(&pool)
        .await
        .unwrap();
    let queue = container.queued_message_service.clone();
    let shutdown = CancellationToken::new();
    let worker_shutdown = shutdown.clone();
    let worker = tokio::spawn(async move {
        container
            .poll_pending_work(worker_shutdown, Duration::from_millis(10))
            .await;
    });
    tokio::time::sleep(Duration::from_millis(50)).await;
    shutdown.cancel();
    worker.await.unwrap();
    assert_eq!(
        serde_json::to_string(&queue.get_queued(session).unwrap()).unwrap(),
        data
    );
    assert!(queue.take_oldest_capacity_queued().is_none());
    let stored: (String, String) =
        sqlx::query_as("SELECT data, state FROM turn_github_sync_user_queue WHERE session_id = ?")
            .bind(session)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(stored, (data, "dispatching".into()));
}

#[cfg(target_os = "linux")]
impl ObservationFixture {
    async fn new(scheduled: bool) -> Self {
        Self::with_publication_policy(scheduled, true).await
    }

    async fn with_publication_policy(scheduled: bool, approved: bool) -> Self {
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
        if scheduled {
            TurnGithubSync::enqueue(&pool, execution.id, workspace.id, &request.to_string())
                .await
                .unwrap();
        }
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
        if !approved {
            let mut config: serde_json::Value =
                serde_json::from_slice(&std::fs::read(&policy).unwrap()).unwrap();
            config["repositories"] = json!({});
            std::fs::write(&policy, config.to_string()).unwrap();
        }
        let container = observation_container(pool, &policy).await;
        let admitted = if scheduled {
            container
                .invoke_preservation_helper("begin", request.clone())
                .await
        } else {
            container
                .invoke_preservation("begin", request.clone())
                .await
        };
        assert_eq!(
            admitted["state"],
            if approved { "pending" } else { "blocked" },
            "{admitted}"
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
        self.callback_for(self.execution).await;
    }

    async fn callback_for(&self, execution: Uuid) {
        use command_group::AsyncCommandGroup;
        let mut child = tokio::process::Command::new("true").group_spawn().unwrap();
        let group = child.inner().id().unwrap();
        TurnGithubSync::bind_group(&self.container.db.pool, execution, group)
            .await
            .unwrap();
        self.container
            .child_store
            .write()
            .await
            .insert(execution, Arc::new(RwLock::new(child)));
        tokio::time::timeout(
            Duration::from_secs(15),
            self.container
                .spawn_exit_monitor(&execution, None, Some(group)),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(
            ExecutionProcess::find_by_id(&self.container.db.pool, execution)
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
        let mut fixture = ObservationFixture::new(true).await;
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
        if policy_changed {
            // Publication-policy edits cannot suppress a registered owner's
            // terminal-original capture; restoration still grants no stale A proof.
            let jobs = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
                .await
                .unwrap();
            assert_eq!(jobs[0].observation_state, "observed");
            let ledger = fixture
                ._root
                .path()
                .join("private-state")
                .join(fixture.workspace.to_string())
                .join(format!("{}.json", fixture.execution));
            assert!(
                std::fs::read_to_string(ledger)
                    .unwrap()
                    .contains(&fixture.b)
            );
        } else {
            fixture.assert_gate("failed").await;
        }
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn observation_callback_persistence_failure_and_lost_callback_keep_pending_gate() {
    for stage in ["lost", "claim", "finish-success", "finish-failure"] {
        let mut fixture = ObservationFixture::new(true).await;
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
    let fixture = ObservationFixture::new(true).await;
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

#[cfg(target_os = "linux")]
impl ObservationFixture {
    async fn new_legacy_owner(&self) -> (ExecutionContext, ExecutorAction) {
        use executors::actions::script::{ScriptContext, ScriptRequest, ScriptRequestLanguage};
        // Real launch path with a synthetic script, never a native agent or network task.
        let action = ExecutorAction::new(
            ExecutorActionType::ScriptRequest(ScriptRequest {
                script: "true".into(),
                language: ScriptRequestLanguage::Bash,
                context: ScriptContext::SetupScript,
                working_dir: None,
            }),
            None,
        );
        let execution = ExecutionProcess::create(
            &self.container.db.pool,
            &CreateExecutionProcess {
                session_id: self.session,
                executor_action: action.clone(),
                run_reason: ExecutionProcessRunReason::CodingAgent,
            },
            Uuid::new_v4(),
            &[],
        )
        .await
        .unwrap();
        CodingAgentTurn::create(
            &self.container.db.pool,
            &CreateCodingAgentTurn {
                execution_process_id: execution.id,
                prompt: None,
            },
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        CodingAgentTurn::update_summary(
            &self.container.db.pool,
            execution.id,
            "New unscheduled owner",
        )
        .await
        .unwrap();
        assert!(
            !TurnGithubSync::is_scheduled(&self.container.db.pool, execution.id)
                .await
                .unwrap()
        );
        (
            ExecutionProcess::load_context(&self.container.db.pool, execution.id)
                .await
                .unwrap(),
            action,
        )
    }

    fn offer_green_legacy_receipt(&mut self) -> Arc<RwLock<Vec<String>>> {
        let calls = Arc::new(RwLock::new(Vec::new()));
        // Controlled helper boundary offers a bound green report. The production
        // admission/monitor/coverage gates must refuse to request or accept it.
        let report = json!({"version":2,"state":"verified", "reason":"synthetic exact remote witness",
            "repositories":[{"receipt":{"commit":self.b,"changed":false}}]});
        self.container.preservation_fixture = Some((report, calls.clone()));
        self.container.automatic_sync_override = Some(false);
        calls
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn legacy_observation_gate_survives_restart_disable_and_policy_rollback_for_new_owner() {
    for policy_present in [true, false] {
        let mut fixture = ObservationFixture::new(true).await;
        // No rewrite: the current head stays B. Failure is durable only in SQLite.
        let saved = std::fs::read(&fixture.policy).unwrap();
        std::fs::remove_file(&fixture.policy).unwrap();
        fixture.callback().await;
        std::fs::write(&fixture.policy, saved).unwrap();
        fixture.reopen().await;
        let calls = fixture.offer_green_legacy_receipt();
        // Offer exactly the stale A witness the old legacy path could certify.
        fixture.container.preservation_fixture.as_mut().unwrap().0["repositories"][0]["receipt"]
            ["commit"] = json!(fixture.a);
        if !policy_present {
            fixture.container.preservation_config = None;
        }
        assert!(!fixture.container.automatic_sync_enabled());
        let (ctx, action) = fixture.new_legacy_owner().await;
        let before_ledger = std::fs::read(
            fixture
                ._root
                .path()
                .join("private-state")
                .join(fixture.workspace.to_string())
                .join("latest.json"),
        )
        .unwrap();
        let error = fixture
            .container
            .execution_git_readiness(&ctx.workspace, &ctx.execution_process, json!({}))
            .await
            .unwrap_err();
        assert!(error.to_string().contains("observation is unproven"));
        assert!(
            !fixture
                .container
                .child_store
                .read()
                .await
                .contains_key(&ctx.execution_process.id)
        );
        assert!(
            calls.read().await.is_empty(),
            "admission must stop before helper/launch"
        );
        assert_eq!(
            std::fs::read(
                fixture
                    ._root
                    .path()
                    .join("private-state")
                    .join(fixture.workspace.to_string())
                    .join("latest.json")
            )
            .unwrap(),
            before_ledger
        );
        // A late/in-flight unscheduled completion must also stay blocked, even
        // when there is no legacy policy and the old selector would choose None.
        fixture.callback_for(ctx.execution_process.id).await;
        let summary = CodingAgentTurn::find_by_execution_process_id(
            &fixture.container.db.pool,
            ctx.execution_process.id,
        )
        .await
        .unwrap()
        .unwrap()
        .summary
        .unwrap();
        assert!(summary.starts_with("New unscheduled owner"));
        assert!(
            summary.contains("Git preservation blocked")
                && summary.contains("observation is unproven"),
            "{summary}"
        );
        assert!(!summary.contains("Git preservation verified"));
        let request = LocalContainerService::preservation_request(
            &ctx.workspace,
            &ctx.execution_process,
            &ctx.repos,
            true,
        );
        for action in ["begin", "end", "check", "checkpoint", "check-all"] {
            let request = if action == "check-all" {
                json!({"turns":[request.clone()]})
            } else {
                request.clone()
            };
            let report = fixture.container.invoke_preservation(action, request).await;
            assert_eq!(report["state"], "blocked", "{action}: {report}");
            assert!(
                report["reason"]
                    .as_str()
                    .unwrap()
                    .contains("observation is unproven")
            );
        }
        // A helper reply already in flight must not persist a stale green either.
        let mut offered = fixture
            .container
            .preservation_fixture
            .as_ref()
            .unwrap()
            .0
            .clone();
        offered["workspace"] = json!(ctx.workspace.id);
        offered["turn"] = json!(ctx.execution_process.id);
        let report = fixture
            .container
            .record_preservation_report(&ctx, request.clone(), offered)
            .await;
        assert_eq!(report["state"], "blocked");
        // Direct completion entrypoint has the same gate before fencing/helper work.
        assert_eq!(
            fixture
                .container
                .preserve_finished_turn(&ctx, Some(u32::MAX))
                .await["state"],
            "blocked"
        );
        assert!(calls.read().await.iter().all(|action| action == "block"));
        let jobs = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
            .await
            .unwrap();
        assert_eq!(
            jobs.len(),
            1,
            "legacy owner must not create/replace a scheduled obligation"
        );
        assert_eq!(jobs[0].execution_process_id, fixture.execution);
        assert_eq!(jobs[0].observation_state, "failed");
        assert_eq!(
            fixture_git(&fixture.repo, &["rev-parse", "HEAD"]),
            fixture.b
        );
        fixture.reopen().await;
        assert!(
            TurnGithubSync::has_unobserved(&fixture.container.db.pool, fixture.workspace)
                .await
                .unwrap()
        );
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn legacy_observation_gate_preserves_clean_admission_and_completion() {
    for scheduled_history in [false, true] {
        let mut fixture = ObservationFixture::new(scheduled_history).await;
        if scheduled_history {
            fixture.callback().await;
        } else {
            ExecutionProcess::update_completion(
                &fixture.container.db.pool,
                fixture.execution,
                ExecutionProcessStatus::Completed,
                Some(0),
            )
            .await
            .unwrap();
        }
        fixture.reopen().await;
        assert!(
            !TurnGithubSync::has_unobserved(&fixture.container.db.pool, fixture.workspace)
                .await
                .unwrap()
        );
        let calls = fixture.offer_green_legacy_receipt();
        let (ctx, action) = fixture.new_legacy_owner().await;
        fixture
            .container
            .start_execution_inner(&ctx.workspace, &ctx.execution_process, &action)
            .await
            .unwrap();
        let handle = fixture
            .container
            .exit_monitor_handles
            .write()
            .await
            .remove(&ctx.execution_process.id)
            .unwrap();
        tokio::time::timeout(Duration::from_secs(20), handle)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(&*calls.read().await, &["begin", "end"]);
        let summary = CodingAgentTurn::find_by_execution_process_id(
            &fixture.container.db.pool,
            ctx.execution_process.id,
        )
        .await
        .unwrap()
        .unwrap()
        .summary
        .unwrap();
        assert!(summary.contains("Git preservation verified"), "{summary}");
        assert!(
            !TurnGithubSync::is_scheduled(&fixture.container.db.pool, ctx.execution_process.id)
                .await
                .unwrap()
        );
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn legacy_observation_gate_refuses_coverage_when_workspace_state_is_unreadable() {
    let mut fixture = ObservationFixture::new(false).await;
    let calls = fixture.offer_green_legacy_receipt();
    fixture.container.db.pool.close().await;
    for action in ["begin", "end", "check", "checkpoint", "check-all"] {
        let request = if action == "check-all" {
            json!({"turns":[fixture.request.clone()]})
        } else {
            fixture.request.clone()
        };
        assert_eq!(
            fixture.container.invoke_preservation(action, request).await["state"],
            "blocked"
        );
    }
    assert!(calls.read().await.is_empty());
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn missing_publication_policy_callback_retains_b_across_reset_restart_and_idle_worker() {
    let mut fixture = ObservationFixture::with_publication_policy(true, false).await;
    fixture.callback().await;
    let jobs = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
        .await
        .unwrap();
    assert_eq!(jobs[0].observation_state, "observed");
    let ledger = fixture
        ._root
        .path()
        .join("private-state")
        .join(fixture.workspace.to_string())
        .join(format!("{}.json", fixture.execution));
    let evidence: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&ledger).unwrap()).unwrap();
    assert_eq!(evidence["state"], "blocked");
    assert_eq!(
        evidence["admission_failure"],
        "repository has no approved publication policy"
    );
    assert!(evidence["obligations"].to_string().contains(&fixture.b));
    assert!(evidence["repositories"].as_array().unwrap().is_empty());
    fixture
        .container
        .reset_session_to_process(fixture.session, fixture.execution, true, true)
        .await
        .unwrap();
    assert_eq!(
        fixture_git(&fixture.repo, &["rev-parse", "HEAD"]),
        fixture.a
    );
    fixture.reopen().await;
    fixture.container.sync_one_idle_turn().await;
    assert!(
        std::fs::read_to_string(ledger)
            .unwrap()
            .contains(&fixture.b)
    );
    let jobs = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
        .await
        .unwrap();
    assert!(jobs.iter().all(|job| job.state != "verified"));
    assert_eq!(jobs[0].state, "waiting");
    assert!(
        jobs[0]
            .report
            .as_ref()
            .unwrap()
            .contains("publication awaits a reviewed repository policy")
    );
    let summary = CodingAgentTurn::find_by_execution_process_id(
        &fixture.container.db.pool,
        fixture.execution,
    )
    .await
    .unwrap()
    .unwrap()
    .summary
    .unwrap();
    assert!(summary.contains("Git preservation pending"));
    assert!(!summary.contains("Git preservation verified"));
    sqlx::query("UPDATE turn_github_sync SET retry_at=0 WHERE execution_process_id=?")
        .bind(fixture.execution)
        .execute(&fixture.container.db.pool)
        .await
        .unwrap();
    fixture.container.sync_one_idle_turn().await;
    let retried = CodingAgentTurn::find_by_execution_process_id(
        &fixture.container.db.pool,
        fixture.execution,
    )
    .await
    .unwrap()
    .unwrap();
    assert_eq!(retried.summary.as_deref(), Some(summary.as_str()));
    let jobs = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
        .await
        .unwrap();
    assert_eq!(jobs[0].state, "waiting");
    assert_eq!(jobs[0].observation_state, "observed");
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn checkpoint_readiness_retains_missing_policy_and_observation_blocks() {
    use executors::{
        actions::coding_agent_initial::CodingAgentInitialRequest, executors::BaseCodingAgent,
    };
    for (retained_observation, scheduling) in [(false, true), (true, true), (true, false)] {
        let mut fixture =
            ObservationFixture::with_publication_policy(retained_observation, false).await;
        fixture.container.automatic_sync_override = Some(scheduling);
        if !scheduling {
            fixture.container.preservation_config = None;
        }
        let mut config = ExecutorConfig::new(BaseCodingAgent::ClaudeCode);
        // Deliberately nonexistent profile: even a regression cannot invoke a provider.
        config.variant = Some("READINESS_TEST_MUST_NOT_RESOLVE".into());
        let action = ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: "offline fixture".into(),
                executor_config: config,
                working_dir: None,
            }),
            None,
        );
        sqlx::query("UPDATE execution_processes SET executor_action=? WHERE id=?")
            .bind(serde_json::to_string(&action).unwrap())
            .bind(fixture.execution)
            .execute(&fixture.container.db.pool)
            .await
            .unwrap();
        let ctx = ExecutionProcess::load_context(&fixture.container.db.pool, fixture.execution)
            .await
            .unwrap();
        let ledger = fixture
            ._root
            .path()
            .join("private-state")
            .join(fixture.workspace.to_string())
            .join(format!("{}.json", fixture.execution));
        let before = std::fs::read(&ledger).unwrap();
        let result = fixture
            .container
            .start_execution_inner(&ctx.workspace, &ctx.execution_process, &action)
            .await;
        let Err(ContainerError::ReadinessBlocked(report)) = result else {
            panic!("known Git prerequisite must reject before provider/profile resolution")
        };
        assert_eq!(
            report["code"],
            if retained_observation {
                "observation_unproven"
            } else {
                "publication_policy_missing"
            }
        );
        assert_eq!(report["provider_started"], false);
        assert!(
            !fixture
                .container
                .child_store
                .read()
                .await
                .contains_key(&fixture.execution)
        );
        assert!(
            !fixture
                .container
                .exit_monitor_handles
                .read()
                .await
                .contains_key(&fixture.execution)
        );
        assert_eq!(std::fs::read(ledger).unwrap(), before);
        let jobs = TurnGithubSync::for_workspace(&fixture.container.db.pool, fixture.workspace)
            .await
            .unwrap();
        if retained_observation {
            assert_eq!(jobs[0].observation_state, "pending");
        } else {
            assert!(jobs.is_empty());
        }
    }
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn readiness_rejects_changed_native_owner_head_checkpoint_and_inventory() {
    let fixture = ObservationFixture::with_publication_policy(false, true).await;
    let ctx = ExecutionProcess::load_context(&fixture.container.db.pool, fixture.execution)
        .await
        .unwrap();
    let check = |result: Result<serde_json::Value, ContainerError>, code: &str| {
        let Err(ContainerError::ReadinessBlocked(report)) = result else {
            panic!("changed native binding must fail before launch")
        };
        assert_eq!(report["code"], code);
        assert_eq!(report["provider_started"], false);
    };
    check(
        fixture
            .container
            .execution_git_readiness(&ctx.workspace, &ctx.execution_process, json!({}))
            .await,
        "source_binding_changed",
    );
    check(
        fixture
            .container
            .execution_git_readiness(
                &ctx.workspace,
                &ctx.execution_process,
                json!({"expected_source_heads": {"unmatched": "checkpoint"}}),
            )
            .await,
        "checkpoint_source_mismatch",
    );
    let mut changed_owner = ctx.workspace.clone();
    changed_owner.branch = "changed-owner".into();
    check(
        fixture
            .container
            .execution_git_readiness(&changed_owner, &ctx.execution_process, json!({}))
            .await,
        "ownership_changed",
    );
    let other = ExecutionProcess::create(
        &fixture.container.db.pool,
        &CreateExecutionProcess {
            session_id: fixture.session,
            executor_action: ctx.execution_process.executor_action().unwrap().clone(),
            run_reason: ExecutionProcessRunReason::CodingAgent,
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    check(
        fixture
            .container
            .execution_git_readiness(&ctx.workspace, &ctx.execution_process, json!({}))
            .await,
        "owner_busy",
    );
    ExecutionProcess::update_completion(
        &fixture.container.db.pool,
        other.id,
        ExecutionProcessStatus::Failed,
        None,
    )
    .await
    .unwrap();
    sqlx::query("DELETE FROM execution_process_repo_states WHERE execution_process_id=?")
        .bind(fixture.execution)
        .execute(&fixture.container.db.pool)
        .await
        .unwrap();
    check(
        fixture
            .container
            .execution_git_readiness(&ctx.workspace, &ctx.execution_process, json!({}))
            .await,
        "source_binding_missing",
    );
    assert!(fixture.container.child_store.read().await.is_empty());
    assert!(
        !TurnGithubSync::has_unobserved(&fixture.container.db.pool, fixture.workspace)
            .await
            .unwrap()
    );
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn active_owner_rejects_before_routing_or_creating_execution() {
    use executors::{
        actions::coding_agent_initial::CodingAgentInitialRequest,
        executors::BaseCodingAgent,
        routing::{CapabilityFloor, RoutingMode, RoutingPolicy},
    };
    let fixture = ObservationFixture::with_publication_policy(true, false).await;
    let ctx = ExecutionProcess::load_context(&fixture.container.db.pool, fixture.execution)
        .await
        .unwrap();
    let before: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(&fixture.container.db.pool)
        .await
        .unwrap();
    let mut config = ExecutorConfig::new(BaseCodingAgent::Codex);
    config.routing = Some(Box::new(RoutingPolicy {
        mode: RoutingMode::Shadow,
        floor: CapabilityFloor::Workhorse,
        denied_models: vec!["gpt-6-astra".into()],
        allow_escalation: false,
    }));
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "offline classification must never be reached".into(),
            executor_config: config,
            working_dir: None,
        }),
        None,
    );
    let result = fixture
        .container
        .start_execution(
            &ctx.workspace,
            &ctx.session,
            &action,
            &ExecutionProcessRunReason::CodingAgent,
        )
        .await;
    let Err(ContainerError::ReadinessBlocked(report)) = result else {
        panic!("active owner must reject before routing");
    };
    assert_eq!(report["code"], "owner_busy");
    assert_eq!(report["provider_started"], false);
    let after: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(&fixture.container.db.pool)
        .await
        .unwrap();
    assert_eq!(before, after);
}

#[cfg(target_os = "linux")]
#[tokio::test]
async fn interactive_admission_retains_historical_uncertainty_without_publication_grant() {
    for retained in [false, true] {
        let fixture = ObservationFixture::with_publication_policy(retained, false).await;
        ExecutionProcess::update_completion(
            &fixture.container.db.pool,
            fixture.execution,
            ExecutionProcessStatus::Completed,
            Some(0),
        )
        .await
        .unwrap();
        let ctx = ExecutionProcess::load_context(&fixture.container.db.pool, fixture.execution)
            .await
            .unwrap();
        let action = ctx.execution_process.executor_action().unwrap();
        let ledger = fixture
            ._root
            .path()
            .join("private-state")
            .join(fixture.workspace.to_string())
            .join(format!("{}.json", fixture.execution));
        let before = std::fs::read(&ledger).unwrap();
        let policy = std::fs::read(&fixture.policy).unwrap();
        let jobs_before: Vec<(String, String, Option<String>)> = sqlx::query_as(
            "SELECT state, observation_state, observation_report FROM turn_github_sync ORDER BY execution_process_id")
            .fetch_all(&fixture.container.db.pool).await.unwrap();
        fixture
            .container
            .pre_route_git_readiness(&ctx.workspace, &ctx.session, Uuid::new_v4(), action)
            .await
            .unwrap();
        assert_eq!(std::fs::read(&ledger).unwrap(), before);
        assert_eq!(std::fs::read(&fixture.policy).unwrap(), policy);
        let jobs_after: Vec<(String, String, Option<String>)> = sqlx::query_as(
            "SELECT state, observation_state, observation_report FROM turn_github_sync ORDER BY execution_process_id")
            .fetch_all(&fixture.container.db.pool).await.unwrap();
        assert_eq!(jobs_before, jobs_after);
        assert!(fixture.container.child_store.read().await.is_empty());
        let mut changed = ctx.workspace.clone();
        changed.branch = "different-owner".into();
        let Err(ContainerError::ReadinessBlocked(report)) = fixture
            .container
            .pre_route_git_readiness(&changed, &ctx.session, Uuid::new_v4(), action)
            .await
        else {
            panic!("interactive sends must still reject changed ownership");
        };
        assert_eq!(report["code"], "ownership_changed");
    }
}
