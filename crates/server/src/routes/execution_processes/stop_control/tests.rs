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
    executors::BaseCodingAgent,
    profile::ExecutorConfig,
};

use super::*;

async fn fixture() -> (SqlitePool, StopRequest) {
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let workspace = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "isolated-stop-contract".into(),
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
            name: None,
        },
        Uuid::new_v4(),
        workspace.id,
    )
    .await
    .unwrap();
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "Synthetic process fixture only".into(),
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
    let request = StopRequest {
        request_id: Uuid::new_v4(),
        execution_id: execution.id,
        session_id: session.id,
        workspace_id: workspace.id,
        expected_created_at: execution.created_at,
        reason: "user_request".into(),
    };
    (pool, request)
}

#[tokio::test]
async fn exact_stop_replay_and_second_request_dispatch_only_once() {
    let (pool, request) = fixture().await;
    let calls = AtomicUsize::new(0);
    let expected = request.execution_id;
    let counter = &calls;
    let first = admit(&pool, &request, |process| async move {
        assert_eq!(process.id, expected);
        counter.fetch_add(1, Ordering::SeqCst);
        Ok(())
    })
    .await
    .unwrap();
    assert_eq!(first.stopped, Some(true));
    let replay = admit(&pool, &request, |_| async {
        panic!("Replay must not stop again")
    })
    .await
    .unwrap();
    assert_eq!(replay.status, "stopped");
    let other = StopRequest {
        request_id: Uuid::new_v4(),
        ..request.clone()
    };
    assert_eq!(
        admit(&pool, &other, |_| async {
            panic!("Terminal execution cannot be stopped")
        })
        .await
        .unwrap()
        .status,
        "not_running"
    );
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn terminal_dropped_and_non_agent_targets_are_untouched() {
    for state in ["completed", "failed", "killed"] {
        let (pool, request) = fixture().await;
        sqlx::query("UPDATE execution_processes SET status=? WHERE id=?")
            .bind(state)
            .bind(request.execution_id)
            .execute(&pool)
            .await
            .unwrap();
        let result = admit(&pool, &request, |_| async {
            panic!("Finished execution must not reach goal/process Stop")
        })
        .await
        .unwrap();
        assert_eq!(result.stopped, Some(false));
        assert_eq!(result.status, "not_running");
        let actual: String =
            sqlx::query_scalar("SELECT status FROM execution_processes WHERE id=?")
                .bind(request.execution_id)
                .fetch_one(&pool)
                .await
                .unwrap();
        assert_eq!(actual, state);
    }
    for sql in [
        "UPDATE execution_processes SET dropped=1",
        "UPDATE execution_processes SET run_reason='devserver'",
    ] {
        let (pool, request) = fixture().await;
        sqlx::query(sql).execute(&pool).await.unwrap();
        assert_eq!(
            admit(&pool, &request, |_| async {
                panic!("Unrelated process must survive")
            })
            .await
            .unwrap()
            .status,
            "not_running"
        );
    }
}

#[tokio::test]
async fn workspace_session_execution_and_creation_identity_are_fenced() {
    for field in 0..4 {
        let (pool, mut request) = fixture().await;
        match field {
            0 => request.workspace_id = Uuid::new_v4(),
            1 => request.session_id = Uuid::new_v4(),
            2 => request.execution_id = Uuid::new_v4(),
            _ => request.expected_created_at += chrono::Duration::seconds(1),
        }
        assert_eq!(
            admit(&pool, &request, |_| async {
                panic!("Wrong target must not stop")
            })
            .await
            .unwrap()
            .status,
            "target_mismatch"
        );
        let running: i64 =
            sqlx::query_scalar("SELECT count(*) FROM execution_processes WHERE status='running'")
                .fetch_one(&pool)
                .await
                .unwrap();
        assert_eq!(running, 1);
    }
}

#[tokio::test]
async fn conflicting_request_identity_is_not_reused() {
    let (pool, request) = fixture().await;
    admit(&pool, &request, |_| async { Ok(()) }).await.unwrap();
    for field in 0..3 {
        let mut other = request.clone();
        match field {
            0 => other.workspace_id = Uuid::new_v4(),
            1 => other.reason = "budget_exhausted".into(),
            _ => other.expected_created_at += chrono::Duration::seconds(1),
        }
        assert!(
            admit(&pool, &other, |_| async {
                panic!("Conflicting retry must not stop")
            })
            .await
            .is_err()
        );
    }
}

#[tokio::test]
async fn independent_completion_wins_atomic_claim_without_a_stop() {
    let (pool, request) = fixture().await;
    sqlx::query("CREATE TRIGGER completion_wins BEFORE INSERT ON execution_stop_claims BEGIN UPDATE execution_processes SET status='completed' WHERE id=NEW.execution_id; SELECT RAISE(IGNORE); END").execute(&pool).await.unwrap();
    let result = admit(&pool, &request, |_| async {
        panic!("Completion won the race")
    })
    .await
    .unwrap();
    assert_eq!(result.status, "not_running");
    let actual = ExecutionProcess::find_by_id(&pool, request.execution_id)
        .await
        .unwrap()
        .unwrap();
    assert_eq!(actual.status, ExecutionProcessStatus::Completed);
}

#[tokio::test]
async fn concurrent_requests_with_different_ids_have_one_dispatch() {
    let (pool, request) = fixture().await;
    let other = StopRequest {
        request_id: Uuid::new_v4(),
        ..request.clone()
    };
    let calls = AtomicUsize::new(0);
    let (a, b) = tokio::join!(
        admit(&pool, &request, |_| async {
            calls.fetch_add(1, Ordering::SeqCst);
            Ok(())
        }),
        admit(&pool, &other, |_| async {
            calls.fetch_add(1, Ordering::SeqCst);
            Ok(())
        })
    );
    assert!(a.is_ok() && b.is_ok());
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn failed_or_cancelled_dispatch_remains_unknown_and_is_never_replayed() {
    let (pool, request) = fixture().await;
    let failed = admit(&pool, &request, |_| async {
        Err(ApiError::Conflict("Synthetic lost response".into()))
    })
    .await
    .unwrap();
    assert_eq!(failed.status, "unknown");
    assert_eq!(failed.stopped, None);
    assert_eq!(
        ExecutionProcess::find_by_id(&pool, request.execution_id)
            .await
            .unwrap()
            .unwrap()
            .status,
        ExecutionProcessStatus::Running
    );
    assert_eq!(
        admit(&pool, &request, |_| async {
            panic!("Unknown stop cannot be resent")
        })
        .await
        .unwrap()
        .stopped,
        None
    );

    let (pool, request) = fixture().await;
    let worker_pool = pool.clone();
    let worker_request = request.clone();
    let (started, ready) = tokio::sync::oneshot::channel();
    let task = tokio::spawn(async move {
        admit(&worker_pool, &worker_request, |_| async move {
            let _ = started.send(());
            std::future::pending::<Result<(), ApiError>>().await
        })
        .await
    });
    ready.await.unwrap();
    task.abort();
    let _ = task.await;
    let readback = admit(&pool, &request, |_| async {
        panic!("Cancelled stop cannot be resent")
    })
    .await
    .unwrap();
    assert_eq!(readback.status, "unknown");
    assert_eq!(readback.stopped, None);
    assert_eq!(
        ExecutionProcess::find_by_id(&pool, request.execution_id)
            .await
            .unwrap()
            .unwrap()
            .status,
        ExecutionProcessStatus::Running
    );
}

#[tokio::test]
async fn losing_http_waiter_does_not_abandon_the_owned_stop() {
    let (pool, request) = fixture().await;
    let worker_pool = pool.clone();
    let worker_request = request.clone();
    let (started, ready) = tokio::sync::oneshot::channel();
    let (release, resume) = tokio::sync::oneshot::channel();
    let waiter = tokio::spawn(finish_owned(async move {
        admit(&worker_pool, &worker_request, |_| async move {
            let _ = started.send(());
            let _ = resume.await;
            Ok(())
        })
        .await
    }));
    ready.await.unwrap();
    waiter.abort();
    let _ = waiter.await;
    release.send(()).unwrap();
    tokio::time::timeout(std::time::Duration::from_secs(2), async {
        loop {
            if previous(&pool, &request)
                .await
                .unwrap()
                .is_some_and(|r| r.stopped == Some(true))
            {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    assert_eq!(
        admit(&pool, &request, |_| async {
            panic!("Owned stop cannot be resent")
        })
        .await
        .unwrap()
        .stopped,
        Some(true)
    );
}

#[tokio::test]
async fn invalid_requests_cannot_reserve_or_stop() {
    let (pool, mut request) = fixture().await;
    request.request_id = Uuid::nil();
    assert!(
        admit(&pool, &request, |_| async { panic!("Invalid request") })
            .await
            .is_err()
    );
    let count: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_stop_requests")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(count, 0);
}

#[cfg(unix)]
#[tokio::test]
async fn actual_disposable_process_stops_without_touching_user_agents() {
    let (pool, request) = fixture().await;
    let process = Arc::new(tokio::sync::Mutex::new(
        tokio::process::Command::new("sleep")
            .arg("30")
            .kill_on_drop(true)
            .spawn()
            .unwrap(),
    ));
    assert!(process.lock().await.try_wait().unwrap().is_none());
    let owned = process.clone();
    let result = admit(&pool, &request, move |_| async move {
        owned
            .lock()
            .await
            .kill()
            .await
            .map_err(|error| ApiError::Conflict(error.to_string()))?;
        Ok(())
    })
    .await
    .unwrap();
    assert_eq!(result.stopped, Some(true));
    assert!(process.lock().await.try_wait().unwrap().is_some());
}
