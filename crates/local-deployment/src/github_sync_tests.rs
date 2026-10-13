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
