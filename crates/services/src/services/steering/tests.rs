use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::BaseCodingAgent,
    profile::ExecutorConfig,
};
use sqlx::{sqlite::SqlitePoolOptions, types::Json};
use tokio::sync::Notify;

use super::*;

fn draft() -> DraftFollowUpData {
    DraftFollowUpData {
        message: "Keep web as the source of truth.\nExact direct input.".into(),
        executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
    }
}
async fn fixture() -> (SqlitePool, Uuid, Uuid) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let workspace = Uuid::new_v4();
    let session = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces (id,branch) VALUES (?, 'steering')")
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
    let process = add_process(&pool, session).await;
    (pool, session, process)
}
async fn add_process(pool: &SqlitePool, session: Uuid) -> Uuid {
    let id = Uuid::new_v4();
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "original raw request".into(),
            executor_config: draft().executor_config,
            working_dir: None,
        }),
        None,
    );
    sqlx::query("INSERT INTO execution_processes (id,session_id,run_reason,executor_action,status) VALUES (?,?,'codingagent',?,'running')").bind(id).bind(session).bind(Json(action)).execute(pool).await.unwrap();
    id
}
async fn receipts(pool: &SqlitePool) -> Vec<AgentDelivery> {
    sqlx::query_as("SELECT * FROM agent_deliveries ORDER BY position")
        .fetch_all(pool)
        .await
        .unwrap()
}

#[tokio::test]
async fn acknowledgement_replay_is_idempotent_even_after_process_completion() {
    let (pool, session, process) = fixture().await;
    let key = Uuid::new_v4();
    let calls = &AtomicUsize::new(0);
    let receipt = steer(&pool, session, &draft(), key, |id| async move {
        assert_eq!(id, process);
        calls.fetch_add(1, Ordering::SeqCst);
        Ok::<_, ()>(true)
    })
    .await
    .unwrap();
    assert!(matches!(receipt,SteeringOutcome::Acknowledged{process_id,..} if process_id==process));
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(process)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert_eq!(
        steer(&pool, session, &draft(), key, |_| async {
            calls.fetch_add(1, Ordering::SeqCst);
            Ok::<_, ()>(true)
        })
        .await
        .unwrap(),
        receipt
    );
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    let rows = receipts(&pool).await;
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].state, "completed");
    assert_eq!(rows[0].data.message, draft().message);
    assert!(rows[0].steering_acknowledged_at.is_some());
    assert!(
        AgentDelivery::queued(&pool, session)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM conversation_messages")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
}

#[tokio::test]
async fn unavailable_codex_is_a_known_rejection_with_no_queue_fallback() {
    let (pool, session, _) = fixture().await;
    let key = Uuid::new_v4();
    assert_eq!(
        steer(&pool, session, &draft(), key, |_| async {
            Ok::<_, ()>(false)
        })
        .await
        .unwrap(),
        SteeringOutcome::Unavailable
    );
    assert_eq!(
        steer(&pool, session, &draft(), key, |_| async {
            panic!("must not retry the RPC");
            #[allow(unreachable_code)]
            Ok::<_, ()>(true)
        })
        .await
        .unwrap(),
        SteeringOutcome::Unavailable
    );
    assert!(
        AgentDelivery::queued(&pool, session)
            .await
            .unwrap()
            .is_empty()
    );
    let rows = receipts(&pool).await;
    assert_eq!(rows[0].state, "failed");
    assert_eq!(rows[0].error.as_deref(), Some("steering_unavailable"));
    assert!(rows[0].steering_acknowledged_at.is_none());
}

#[tokio::test]
async fn executor_error_stays_uncertain_and_never_reenters_the_queue() {
    let (pool, session, _) = fixture().await;
    let key = Uuid::new_v4();
    assert!(matches!(
        steer(&pool, session, &draft(), key, |_| async {
            Err::<bool, _>("private provider error")
        })
        .await,
        Err(SteeringError::Uncertain)
    ));
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert!(matches!(
        steer(&pool, session, &draft(), key, |_| async {
            panic!("uncertain receipt must not resend");
            #[allow(unreachable_code)]
            Ok::<_, ()>(true)
        })
        .await,
        Err(SteeringError::Uncertain)
    ));
    let rows = receipts(&pool).await;
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].state, "unknown_delivery");
    assert!(
        !serde_json::to_string(&rows)
            .unwrap()
            .contains("private provider error")
    );
    assert!(
        AgentDelivery::recoverable_sessions(&pool)
            .await
            .unwrap()
            .is_empty()
    );
}

#[tokio::test]
async fn lost_receipt_write_after_acknowledgement_never_reports_safe_retry() {
    let (pool, session, _) = fixture().await;
    let key = Uuid::new_v4();
    sqlx::query("CREATE TRIGGER reject_ack BEFORE UPDATE ON agent_deliveries WHEN NEW.steering_acknowledged_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'disk fault'); END").execute(&pool).await.unwrap();
    assert!(matches!(
        steer(&pool, session, &draft(), key, |_| async {
            Ok::<_, ()>(true)
        })
        .await,
        Err(SteeringError::Uncertain)
    ));
    sqlx::query("DROP TRIGGER reject_ack")
        .execute(&pool)
        .await
        .unwrap();
    sqlx::query("UPDATE agent_deliveries SET lease_until=0")
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert_eq!(receipts(&pool).await[0].state, "unknown_delivery");
    assert!(
        AgentDelivery::queued(&pool, session)
            .await
            .unwrap()
            .is_empty()
    );
}

#[tokio::test]
async fn crash_in_flight_is_not_resent_and_a_late_exact_ack_can_resolve_it() {
    let (pool, session, _) = fixture().await;
    let key = Uuid::new_v4();
    let SteeringAdmission::Attempt(attempt) =
        AgentDelivery::begin_steering(&pool, session, &draft(), key)
            .await
            .unwrap()
    else {
        panic!("missing attempt")
    };
    // Simulate restart after the external RPC, before local acknowledgement.
    sqlx::query("UPDATE agent_deliveries SET lease_until=0 WHERE id=?")
        .bind(attempt.id)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert!(matches!(
        steer(&pool, session, &draft(), key, |_| async {
            panic!("crash recovery must not resend");
            #[allow(unreachable_code)]
            Ok::<_, ()>(true)
        })
        .await,
        Err(SteeringError::Uncertain)
    ));
    let resolved = AgentDelivery::finish_steering(&pool, &attempt, SteeringResult::Acknowledged)
        .await
        .unwrap();
    assert!(resolved.steering_acknowledged_at.is_some());
    assert_eq!(resolved.state, "started");
    assert!(
        AgentDelivery::finish_steering(&pool, &attempt, SteeringResult::Unavailable)
            .await
            .is_err()
    );
}

#[tokio::test]
async fn concurrent_retry_never_invokes_two_rpcs_and_execution_is_pinned() {
    let (pool, session, process) = fixture().await;
    let key = Uuid::new_v4();
    let entered = Arc::new(Notify::new());
    let release = Arc::new(Notify::new());
    let task_pool = pool.clone();
    let task_entered = entered.clone();
    let task_release = release.clone();
    let task = tokio::spawn(async move {
        steer(&task_pool, session, &draft(), key, |id| async move {
            assert_eq!(id, process);
            task_entered.notify_one();
            task_release.notified().await;
            Ok::<_, ()>(true)
        })
        .await
    });
    entered.notified().await;
    assert!(matches!(
        steer(&pool, session, &draft(), key, |_| async {
            panic!("duplicate RPC");
            #[allow(unreachable_code)]
            Ok::<_, ()>(true)
        })
        .await,
        Err(SteeringError::Uncertain)
    ));
    // A newly running process must not replace the attempt's original target.
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(process)
        .execute(&pool)
        .await
        .unwrap();
    let replacement = add_process(&pool, session).await;
    assert_ne!(replacement, process);
    release.notify_one();
    assert!(
        matches!(task.await.unwrap().unwrap(),SteeringOutcome::Acknowledged{process_id,..} if process_id==process)
    );
    assert_eq!(receipts(&pool).await[0].execution_process_id, Some(process));
}

#[tokio::test]
async fn changed_content_or_mode_cannot_reuse_receipt_identity() {
    let (pool, session, _) = fixture().await;
    let key = Uuid::new_v4();
    steer(&pool, session, &draft(), key, |_| async {
        Ok::<_, ()>(true)
    })
    .await
    .unwrap();
    let mut changed = draft();
    changed.message = "Different instruction".into();
    assert!(matches!(
        steer(&pool, session, &changed, key, |_| async {
            panic!("conflicting request must not send");
            #[allow(unreachable_code)]
            Ok::<_, ()>(true)
        })
        .await,
        Err(SteeringError::IdempotencyConflict)
    ));
    assert!(
        AgentDelivery::enqueue(&pool, session, draft(), false, key)
            .await
            .is_err()
    );
    assert_eq!(receipts(&pool).await.len(), 1);
}

#[tokio::test]
async fn archived_dropped_completed_and_non_codex_targets_do_not_receive_steering() {
    for scenario in ["archived", "dropped", "completed", "non_codex"] {
        let (pool, session, process) = fixture().await;
        let mut data = draft();
        match scenario {
            "archived" => {
                sqlx::query("UPDATE workspaces SET archived=1")
                    .execute(&pool)
                    .await
                    .unwrap();
            }
            "dropped" => {
                sqlx::query("UPDATE execution_processes SET dropped=1 WHERE id=?")
                    .bind(process)
                    .execute(&pool)
                    .await
                    .unwrap();
            }
            "completed" => {
                sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
                    .bind(process)
                    .execute(&pool)
                    .await
                    .unwrap();
            }
            _ => data.executor_config = ExecutorConfig::new(BaseCodingAgent::ClaudeCode),
        }
        assert_eq!(
            steer(&pool, session, &data, Uuid::new_v4(), |_| async {
                panic!("unavailable process must not send");
                #[allow(unreachable_code)]
                Ok::<_, ()>(true)
            })
            .await
            .unwrap(),
            SteeringOutcome::Unavailable
        );
        assert!(receipts(&pool).await.is_empty());
    }
}
