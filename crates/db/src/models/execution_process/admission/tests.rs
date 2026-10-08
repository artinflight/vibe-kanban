use std::{path::PathBuf, time::Duration};

use executors::{
    actions::{
        coding_agent_initial::CodingAgentInitialRequest,
        script::{ScriptContext, ScriptRequest, ScriptRequestLanguage},
    },
    executors::BaseCodingAgent,
    profile::ExecutorConfig,
};
use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions};

use super::*;
use crate::models::{agent_delivery::AgentDelivery, scratch::DraftFollowUpData};

struct Fixture {
    pool: SqlitePool,
    workspace: Uuid,
    session: Uuid,
    repo: Uuid,
    path: PathBuf,
}
impl Fixture {
    async fn new() -> Self {
        // File-backed WAL with independent connections exercises the actual
        // cross-client writer boundary, rather than single-connection ordering.
        let path =
            std::env::temp_dir().join(format!("vk-chat-admission-{}.sqlite", Uuid::new_v4()));
        let pool = SqlitePoolOptions::new()
            .max_connections(4)
            .connect_with(
                SqliteConnectOptions::new()
                    .filename(&path)
                    .create_if_missing(true)
                    .journal_mode(SqliteJournalMode::Wal)
                    .busy_timeout(Duration::from_secs(10)),
            )
            .await
            .unwrap();
        sqlx::migrate!("./migrations").run(&pool).await.unwrap();
        let workspace = Uuid::new_v4();
        let session = Uuid::new_v4();
        let repo = Uuid::new_v4();
        sqlx::query("INSERT INTO workspaces (id,branch) VALUES (?,'admission')")
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO sessions (id,workspace_id,executor) VALUES (?,?,'CODEX')")
            .bind(session)
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO repos (id,path,name,display_name) VALUES (?,'/test/repo','repo','Repository')")
            .bind(repo)
            .execute(&pool)
            .await
            .unwrap();
        Self {
            pool,
            workspace,
            session,
            repo,
            path,
        }
    }
    fn states(&self) -> Vec<CreateExecutionProcessRepoState> {
        vec![CreateExecutionProcessRepoState {
            repo_id: self.repo,
            before_head_commit: Some("before".into()),
            after_head_commit: None,
            merge_commit: None,
        }]
    }
    async fn close(self) {
        self.pool.close().await;
        std::fs::remove_file(self.path).unwrap();
    }
}
fn coding(session: Uuid) -> CreateExecutionProcess {
    CreateExecutionProcess {
        session_id: session,
        run_reason: ExecutionProcessRunReason::CodingAgent,
        executor_action: ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: "Exact raw coding input.\nKeep this intact.".into(),
                executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                working_dir: None,
            }),
            None,
        ),
    }
}
fn script(session: Uuid, reason: ExecutionProcessRunReason) -> CreateExecutionProcess {
    let context = match reason {
        ExecutionProcessRunReason::DevServer => ScriptContext::DevServer,
        ExecutionProcessRunReason::CleanupScript => ScriptContext::CleanupScript,
        ExecutionProcessRunReason::ArchiveScript => ScriptContext::ArchiveScript,
        _ => ScriptContext::SetupScript,
    };
    CreateExecutionProcess {
        session_id: session,
        run_reason: reason,
        executor_action: ExecutorAction::new(
            ExecutorActionType::ScriptRequest(ScriptRequest {
                script: "true".into(),
                language: ScriptRequestLanguage::Bash,
                context,
                working_dir: None,
            }),
            None,
        ),
    }
}

#[tokio::test]
async fn concurrent_direct_and_queued_admission_create_one_process_with_atomic_prompt_and_receipt()
{
    let f = Fixture::new().await;
    AgentDelivery::enqueue(
        &f.pool,
        f.session,
        DraftFollowUpData {
            message: "queued input".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        },
        false,
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let claim = AgentDelivery::claim(&f.pool, f.session)
        .await
        .unwrap()
        .unwrap();
    let input = coding(f.session);
    let states = f.states();
    let (direct, queued) = tokio::join!(
        ExecutionProcess::create(&f.pool, &input, Uuid::new_v4(), &states),
        AgentDelivery::admit(&f.pool, &claim, &input, Uuid::new_v4(), &states)
    );
    assert_ne!(
        direct.is_ok(),
        queued.is_ok(),
        "Exactly one admission must win: {direct:?} / {queued:?}"
    );
    let queued_won = queued.is_ok();
    let process = direct.or(queued).unwrap();
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM execution_processes")
            .fetch_one(&f.pool)
            .await
            .unwrap(),
        1
    );
    let (turn_process, prompt): (Uuid, String) =
        sqlx::query_as("SELECT execution_process_id,prompt FROM coding_agent_turns")
            .fetch_one(&f.pool)
            .await
            .unwrap();
    assert_eq!(turn_process, process.id);
    assert_eq!(prompt, "Exact raw coding input.\nKeep this intact.");
    assert_eq!(
        sqlx::query_scalar::<_, Uuid>(
            "SELECT execution_process_id FROM execution_process_repo_states"
        )
        .fetch_one(&f.pool)
        .await
        .unwrap(),
        process.id
    );
    let receipt: AgentDelivery = sqlx::query_as("SELECT * FROM agent_deliveries")
        .fetch_one(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        receipt.execution_process_id,
        queued_won.then_some(process.id)
    );
    if !queued_won {
        AgentDelivery::release(&f.pool, &claim, false)
            .await
            .unwrap();
        assert_eq!(
            AgentDelivery::queued(&f.pool, f.session)
                .await
                .unwrap()
                .len(),
            1
        );
    }
    f.close().await;
}

#[tokio::test]
async fn coding_sessions_in_same_workspace_share_admission_guard() {
    let f = Fixture::new().await;
    let other = Uuid::new_v4();
    sqlx::query("INSERT INTO sessions (id,workspace_id,executor) VALUES (?,?,'CODEX')")
        .bind(other)
        .bind(f.workspace)
        .execute(&f.pool)
        .await
        .unwrap();
    let a = coding(f.session);
    let b = coding(other);
    let (a, b) = tokio::join!(
        ExecutionProcess::create(&f.pool, &a, Uuid::new_v4(), &[]),
        ExecutionProcess::create(&f.pool, &b, Uuid::new_v4(), &[])
    );
    assert_ne!(a.is_ok(), b.is_ok());
    let failed = if a.is_err() {
        a.unwrap_err()
    } else {
        b.unwrap_err()
    };
    assert!(matches!(failed, ExecutionProcessError::AdmissionConflict));
    f.close().await;
}

#[tokio::test]
async fn repository_and_prompt_write_failures_roll_back_direct_and_queued_admission() {
    for table in ["execution_process_repo_states", "coding_agent_turns"] {
        let f = Fixture::new().await;
        sqlx::query(&format!("CREATE TRIGGER write_fault BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT,'injected fault'); END")).execute(&f.pool).await.unwrap();
        assert!(
            ExecutionProcess::create(&f.pool, &coding(f.session), Uuid::new_v4(), &f.states())
                .await
                .is_err()
        );
        AgentDelivery::enqueue(
            &f.pool,
            f.session,
            DraftFollowUpData {
                message: "queued input".into(),
                executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
            },
            false,
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        let claim = AgentDelivery::claim(&f.pool, f.session)
            .await
            .unwrap()
            .unwrap();
        assert!(
            AgentDelivery::admit(
                &f.pool,
                &claim,
                &coding(f.session),
                Uuid::new_v4(),
                &f.states()
            )
            .await
            .is_err()
        );
        for table in [
            "execution_processes",
            "execution_process_repo_states",
            "coding_agent_turns",
        ] {
            assert_eq!(
                sqlx::query_scalar::<_, i64>(&format!("SELECT count(*) FROM {table}"))
                    .fetch_one(&f.pool)
                    .await
                    .unwrap(),
                0
            );
        }
        let receipt: AgentDelivery = sqlx::query_as("SELECT * FROM agent_deliveries")
            .fetch_one(&f.pool)
            .await
            .unwrap();
        assert_eq!(receipt.state, "dispatching");
        assert_eq!(receipt.execution_process_id, None);
        sqlx::query("DROP TRIGGER write_fault")
            .execute(&f.pool)
            .await
            .unwrap();
        AgentDelivery::admit(
            &f.pool,
            &claim,
            &coding(f.session),
            Uuid::new_v4(),
            &f.states(),
        )
        .await
        .unwrap();
        f.close().await;
    }
}

#[tokio::test]
async fn parallel_setup_and_dev_servers_still_overlap_coding_but_sequential_setup_owns_its_next_turn()
 {
    let f = Fixture::new().await;
    for reason in [
        ExecutionProcessRunReason::SetupScript,
        ExecutionProcessRunReason::SetupScript,
        ExecutionProcessRunReason::DevServer,
    ] {
        ExecutionProcess::create(&f.pool, &script(f.session, reason), Uuid::new_v4(), &[])
            .await
            .unwrap();
    }
    ExecutionProcess::create(&f.pool, &coding(f.session), Uuid::new_v4(), &[])
        .await
        .unwrap();
    assert!(
        ExecutionProcess::create(
            &f.pool,
            &script(f.session, ExecutionProcessRunReason::CleanupScript),
            Uuid::new_v4(),
            &[]
        )
        .await
        .is_err()
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM coding_agent_turns")
            .fetch_one(&f.pool)
            .await
            .unwrap(),
        1
    );
    sqlx::query("UPDATE execution_processes SET status='completed'")
        .execute(&f.pool)
        .await
        .unwrap();
    let mut sequential = script(f.session, ExecutionProcessRunReason::SetupScript);
    sequential.executor_action = ExecutorAction::new(
        sequential.executor_action.typ().clone(),
        Some(Box::new(coding(f.session).executor_action)),
    );
    let setup = ExecutionProcess::create(&f.pool, &sequential, Uuid::new_v4(), &[])
        .await
        .unwrap();
    assert!(
        ExecutionProcess::create(&f.pool, &coding(f.session), Uuid::new_v4(), &[])
            .await
            .is_err()
    );
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(setup.id)
        .execute(&f.pool)
        .await
        .unwrap();
    ExecutionProcess::create(&f.pool, &coding(f.session), Uuid::new_v4(), &[])
        .await
        .unwrap();
    f.close().await;
}

#[tokio::test]
async fn direct_resume_retains_unarchive_behavior_while_queued_and_deleted_targets_are_fenced() {
    let f = Fixture::new().await;
    sqlx::query("UPDATE workspaces SET archived=1")
        .execute(&f.pool)
        .await
        .unwrap();
    AgentDelivery::enqueue(
        &f.pool,
        f.session,
        DraftFollowUpData {
            message: "queued input".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        },
        false,
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let claim = AgentDelivery::claim(&f.pool, f.session)
        .await
        .unwrap()
        .unwrap();
    assert!(
        AgentDelivery::admit(&f.pool, &claim, &coding(f.session), Uuid::new_v4(), &[])
            .await
            .is_err()
    );
    let direct = ExecutionProcess::create(&f.pool, &coding(f.session), Uuid::new_v4(), &[])
        .await
        .unwrap();
    assert!(
        !sqlx::query_scalar::<_, bool>("SELECT archived FROM workspaces")
            .fetch_one(&f.pool)
            .await
            .unwrap()
    );
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(direct.id)
        .execute(&f.pool)
        .await
        .unwrap();
    sqlx::query("UPDATE workspaces SET worktree_deleted=1")
        .execute(&f.pool)
        .await
        .unwrap();
    assert!(
        ExecutionProcess::create(&f.pool, &coding(f.session), Uuid::new_v4(), &[])
            .await
            .is_err()
    );
    f.close().await;
}
