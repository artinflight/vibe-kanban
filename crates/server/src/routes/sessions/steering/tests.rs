use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use db::models::{
    execution_process::CreateExecutionProcess,
    session::CreateSession,
    workspace::{CreateWorkspace, Workspace},
};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    profile::ExecutorConfig,
};

use super::*;

async fn fixture() -> (SqlitePool, Session, ExecutionProcess) {
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let workspace = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "isolated-steering".into(),
            name: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let session = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: Some("Isolated steering test".into()),
        },
        Uuid::new_v4(),
        workspace.id,
    )
    .await
    .unwrap();
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "Fixture only".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
            working_dir: None,
        }),
        None,
    );
    let execution = ExecutionProcess::create(
        &pool,
        &CreateExecutionProcess {
            session_id: session.id,
            executor_action: action,
            run_reason: ExecutionProcessRunReason::CodingAgent,
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    (pool, session, execution)
}

fn request(execution_id: Uuid) -> SteerRequest {
    SteerRequest {
        request_id: Uuid::new_v4(),
        execution_id,
        thread_id: "fixture-thread".into(),
        turn_id: "fixture-turn".into(),
        message: "Use the verified API".into(),
    }
}

#[tokio::test]
async fn repeated_and_concurrent_requests_send_once_and_never_modify_queue_or_execution() {
    let (pool, session, execution) = fixture().await;
    let request = request(execution.id);
    let calls = Arc::new(AtomicUsize::new(0));
    let queue = services::services::queued_message::QueuedMessageService::new();
    queue.queue_for_capacity(
        session.id,
        db::models::scratch::DraftFollowUpData {
            message: "Existing queued owner input".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
        },
    );
    let original = serde_json::to_value(queue.get_status(session.id)).unwrap();
    let invoke = || {
        admit(&pool, session.id, &request, || async {
            calls.fetch_add(1, Ordering::SeqCst);
            tokio::task::yield_now().await;
            Ok(Status::Steered)
        })
    };
    let (a, b) = tokio::join!(invoke(), invoke());
    // A duplicate arriving during dispatch can truthfully see unknown, but
    // never dispatches. Reconciliation after completion returns steered.
    assert!(a.unwrap().delivered == Some(true) || b.unwrap().delivered == Some(true));
    let final_receipt = invoke().await.unwrap();
    assert_eq!(final_receipt.delivered, Some(true));
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    assert_eq!(
        serde_json::to_value(queue.get_status(session.id)).unwrap(),
        original
    );
    assert_eq!(
        ExecutionProcess::find_by_id(&pool, execution.id)
            .await
            .unwrap()
            .unwrap()
            .status,
        ExecutionProcessStatus::Running
    );
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(count, 1);
}

#[tokio::test]
async fn request_identity_cannot_be_reused_for_different_input_or_target() {
    let (pool, session, execution) = fixture().await;
    let mut request = request(execution.id);
    admit(&pool, session.id, &request, || async {
        Ok(Status::Steered)
    })
    .await
    .unwrap();
    request.message.push('!');
    assert!(
        admit(&pool, session.id, &request, || async {
            panic!("no dispatch")
        })
        .await
        .is_err()
    );
    request.message.pop();
    request.execution_id = Uuid::new_v4();
    assert!(
        admit(&pool, session.id, &request, || async {
            panic!("no dispatch")
        })
        .await
        .is_err()
    );
    request.execution_id = execution.id;
    request.turn_id = "replacement".into();
    assert!(
        admit(&pool, session.id, &request, || async {
            panic!("no dispatch")
        })
        .await
        .is_err()
    );
    assert!(
        admit(&pool, Uuid::new_v4(), &request, || async {
            panic!("no dispatch")
        })
        .await
        .is_err()
    );
}

#[tokio::test]
async fn native_failure_and_cancelled_dispatch_remain_uncertain_without_replay() {
    let (pool, session, execution) = fixture().await;
    let request = request(execution.id);
    let failure = admit(&pool, session.id, &request, || async {
        Err(ApiError::Conflict("Lost native reply".into()))
    })
    .await
    .unwrap();
    assert_eq!(failure.status, Status::Unknown);
    let retry = admit(&pool, session.id, &request, || async {
        panic!("must not replay")
    })
    .await
    .unwrap();
    assert_eq!(retry.delivered, None);
    let cancelled = super::tests::request(execution.id);
    let result = tokio::time::timeout(
        std::time::Duration::from_millis(20),
        admit(&pool, session.id, &cancelled, || std::future::pending()),
    )
    .await;
    assert!(result.is_err());
    assert_eq!(
        admit(&pool, session.id, &cancelled, || async {
            panic!("cancelled dispatch must not replay")
        })
        .await
        .unwrap()
        .status,
        Status::Unknown
    );
}

#[tokio::test]
async fn exact_session_and_coding_execution_are_required_even_with_newer_running_rows() {
    let (pool, session, execution) = fixture().await;
    assert_eq!(
        target_status(&pool, &session, execution.id).await.unwrap(),
        None
    );
    let mut foreign = session.clone();
    foreign.id = Uuid::new_v4();
    assert_eq!(
        target_status(&pool, &foreign, execution.id).await.unwrap(),
        Some(Status::TargetMismatch)
    );
    assert_eq!(
        target_status(&pool, &session, Uuid::new_v4())
            .await
            .unwrap(),
        Some(Status::TargetMismatch)
    );
    for status in ["completed", "failed", "killed"] {
        sqlx::query("UPDATE execution_processes SET status=?")
            .bind(status)
            .execute(&pool)
            .await
            .unwrap();
        assert_eq!(
            target_status(&pool, &session, execution.id).await.unwrap(),
            Some(Status::NotRunning)
        );
    }
    sqlx::query("UPDATE execution_processes SET status='running',run_reason='devserver'")
        .execute(&pool)
        .await
        .unwrap();
    assert_eq!(
        target_status(&pool, &session, execution.id).await.unwrap(),
        Some(Status::NotRunning)
    );
    sqlx::query("UPDATE execution_processes SET run_reason='codingagent',dropped=1")
        .execute(&pool)
        .await
        .unwrap();
    assert_eq!(
        target_status(&pool, &session, execution.id).await.unwrap(),
        Some(Status::NotRunning)
    );
    let mut action = execution.executor_action().unwrap().clone();
    if let ExecutorActionType::CodingAgentInitialRequest(ref mut init) = action.typ {
        init.executor_config = ExecutorConfig::new(BaseCodingAgent::ClaudeCode);
    }
    sqlx::query("UPDATE execution_processes SET dropped=0,executor_action=?")
        .bind(serde_json::to_string(&action).unwrap())
        .execute(&pool)
        .await
        .unwrap();
    assert_eq!(
        target_status(&pool, &session, execution.id).await.unwrap(),
        Some(Status::UnsupportedExecutor)
    );
}

#[tokio::test]
async fn rejected_outcomes_are_receipts_without_delivery_and_validation_precedes_dispatch() {
    let (pool, session, execution) = fixture().await;
    for status in [
        Status::NotRunning,
        Status::NotReady,
        Status::UnsupportedExecutor,
        Status::TargetMismatch,
        Status::ScheduledWork,
        Status::Blocked,
    ] {
        let request = request(execution.id);
        let result = admit(&pool, session.id, &request, || async { Ok(status) })
            .await
            .unwrap();
        assert_eq!(result.delivered, Some(false));
    }
    let mut request = request(execution.id);
    request.message = " ".into();
    assert!(
        admit(&pool, session.id, &request, || async {
            panic!("invalid input")
        })
        .await
        .is_err()
    );
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM session_steering_receipts")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(count, 6);
}
