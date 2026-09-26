use db::models::execution_process::{CreateExecutionProcess, ExecutionProcessRunReason};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::BaseCodingAgent,
    profile::ExecutorConfig,
};
use sqlx::sqlite::SqlitePoolOptions;

use super::*;

async fn fixture() -> (SqlitePool, QueuedMessageService, Uuid) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let session = add_session(&pool).await;
    let service = QueuedMessageService::new(pool.clone());
    (pool, service, session)
}

async fn add_session(pool: &SqlitePool) -> Uuid {
    let workspace = Uuid::new_v4();
    let session = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces (id, branch) VALUES (?, 'test')")
        .bind(workspace)
        .execute(pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO sessions (id, workspace_id, executor) VALUES (?, ?, 'CODEX')")
        .bind(session)
        .bind(workspace)
        .execute(pool)
        .await
        .unwrap();
    session
}

fn draft(text: &str) -> DraftFollowUpData {
    DraftFollowUpData {
        message: text.into(),
        executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
    }
}

fn process_input(session: Uuid) -> CreateExecutionProcess {
    CreateExecutionProcess {
        session_id: session,
        executor_action: ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: "accepted work".into(),
                executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                working_dir: None,
            }),
            None,
        ),
        run_reason: ExecutionProcessRunReason::CodingAgent,
    }
}

async fn state(pool: &SqlitePool, id: Uuid) -> String {
    sqlx::query_scalar("SELECT state FROM agent_deliveries WHERE id = ?")
        .bind(id)
        .fetch_one(pool)
        .await
        .unwrap()
}

#[tokio::test]
async fn preserves_legacy_prompt_projection_and_idempotent_acceptance() {
    let (pool, service, session) = fixture().await;
    let key = Uuid::new_v4();
    service
        .queue_with_key(session, draft("one\nexact"), false, key)
        .await
        .unwrap();
    service
        .queue_with_key(session, draft("one\nexact"), false, key)
        .await
        .unwrap();
    assert!(
        service
            .queue_with_key(session, draft("different"), false, key)
            .await
            .is_err()
    );
    let mut second = draft("two");
    second.executor_config =
        ExecutorConfig::from(executors::profile::ExecutorProfileId::with_variant(
            BaseCodingAgent::Codex,
            "CUSTOM".into(),
        ));
    service
        .queue_message(session, second.clone())
        .await
        .unwrap();
    let recreated = QueuedMessageService::new(pool);
    let queued = recreated.get_queued(session).await.unwrap().unwrap();
    assert_eq!(queued.messages.len(), 2);
    assert_eq!(queued.data.message, "two");
    assert_eq!(
        serde_json::to_value(&queued.data.executor_config).unwrap(),
        serde_json::to_value(&second.executor_config).unwrap()
    );
    let collapsed = queued.into_follow_up_data();
    assert!(
        collapsed
            .message
            .ends_with("Follow-up 1:\none\nexact\n\nFollow-up 2:\ntwo")
    );
}

#[tokio::test]
async fn claim_cancel_and_release_never_consume_newer_input() {
    let (pool, service, session) = fixture().await;
    service
        .queue_message(session, draft("claimed"))
        .await
        .unwrap();
    let (a, b) = tokio::join!(service.take_queued(session), service.take_queued(session));
    let claims: Vec<_> = [a.unwrap(), b.unwrap()].into_iter().flatten().collect();
    assert_eq!(claims.len(), 1);
    let batch = &claims[0];
    service.cancel_queued(session).await.unwrap();
    assert_eq!(
        state(&pool, batch.claim.deliveries[0].id).await,
        "dispatching"
    );
    service
        .queue_message(session, draft("arrived after claim"))
        .await
        .unwrap();
    AgentDelivery::release(&pool, &batch.claim, false)
        .await
        .unwrap();
    let queue = service.get_queued(session).await.unwrap().unwrap();
    assert_eq!(
        queue
            .messages
            .iter()
            .map(|d| d.message.as_str())
            .collect::<Vec<_>>(),
        vec!["claimed", "arrived after claim"]
    );
    service.cancel_queued(session).await.unwrap();
    assert!(service.take_queued(session).await.unwrap().is_none());
    assert_eq!(
        state(&pool, batch.claim.deliveries[0].id).await,
        "cancelled"
    );
}

#[tokio::test]
async fn capacity_order_and_replacement_preserve_normal_queue_and_receipts() {
    let (pool, service, normal) = fixture().await;
    let first = add_session(&pool).await;
    let second = add_session(&pool).await;
    service
        .queue_message(normal, draft("normal"))
        .await
        .unwrap();
    service
        .queue_for_capacity(first, draft("older"))
        .await
        .unwrap();
    service
        .queue_for_capacity(second, draft("newer"))
        .await
        .unwrap();
    let batch = service
        .take_oldest_capacity_queued()
        .await
        .unwrap()
        .unwrap();
    assert_eq!(batch.claim.session_id, first);
    service
        .queue_for_capacity(second, draft("replacement"))
        .await
        .unwrap();
    assert!(service.get_queued(normal).await.unwrap().is_some());
    assert_eq!(
        service
            .get_queued(second)
            .await
            .unwrap()
            .unwrap()
            .data
            .message,
        "replacement"
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>(
            "SELECT count(*) FROM agent_deliveries WHERE session_id = ? AND state = 'cancelled'"
        )
        .bind(second)
        .fetch_one(&pool)
        .await
        .unwrap(),
        1
    );
}

#[tokio::test]
async fn admission_is_atomic_and_fences_duplicate_spawn() {
    let (pool, service, session) = fixture().await;
    service.queue_message(session, draft("one")).await.unwrap();
    service.queue_message(session, draft("two")).await.unwrap();
    let batch = service.take_queued(session).await.unwrap().unwrap();
    sqlx::query("CREATE TRIGGER fail_process BEFORE INSERT ON execution_processes BEGIN SELECT RAISE(ABORT, 'injected admission failure'); END")
        .execute(&pool).await.unwrap();
    assert!(
        AgentDelivery::admit(
            &pool,
            &batch.claim,
            &process_input(session),
            Uuid::new_v4(),
            &[]
        )
        .await
        .is_err()
    );
    for delivery in &batch.claim.deliveries {
        assert_eq!(state(&pool, delivery.id).await, "dispatching");
    }
    sqlx::query("DROP TRIGGER fail_process")
        .execute(&pool)
        .await
        .unwrap();
    let process = AgentDelivery::admit(
        &pool,
        &batch.claim,
        &process_input(session),
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    assert!(
        AgentDelivery::admit(
            &pool,
            &batch.claim,
            &process_input(session),
            Uuid::new_v4(),
            &[]
        )
        .await
        .is_err()
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM execution_processes")
            .fetch_one(&pool)
            .await
            .unwrap(),
        1
    );
    assert_eq!(sqlx::query_scalar::<_, i64>("SELECT count(*) FROM agent_deliveries WHERE execution_process_id = ? AND state = 'started'")
        .bind(process.id).fetch_one(&pool).await.unwrap(), 2);
    AgentDelivery::release(&pool, &batch.claim, true)
        .await
        .unwrap();
    assert!(service.get_queued(session).await.unwrap().is_none());
    sqlx::query("UPDATE execution_processes SET status = 'completed', exit_code = 0 WHERE id = ?")
        .bind(process.id)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    for delivery in &batch.claim.deliveries {
        assert_eq!(state(&pool, delivery.id).await, "completed");
    }
}

#[tokio::test]
async fn recovery_retries_only_unadmitted_work_and_retains_uncertainty() {
    let (pool, service, session) = fixture().await;
    let key = Uuid::new_v4();
    service
        .queue_with_key(session, draft("recover"), false, key)
        .await
        .unwrap();
    let old = service.take_queued(session).await.unwrap().unwrap();
    sqlx::query("UPDATE agent_deliveries SET lease_until = unixepoch() - 1 WHERE claim_id = ?")
        .bind(old.claim.id)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    let new = service.take_queued(session).await.unwrap().unwrap();
    assert_ne!(old.claim.id, new.claim.id);
    assert!(
        AgentDelivery::admit(
            &pool,
            &old.claim,
            &process_input(session),
            Uuid::new_v4(),
            &[]
        )
        .await
        .is_err()
    );
    let process = AgentDelivery::admit(
        &pool,
        &new.claim,
        &process_input(session),
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert!(service.get_queued(session).await.unwrap().is_none());
    sqlx::query("DELETE FROM execution_processes WHERE id = ?")
        .bind(process.id)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert_eq!(
        state(&pool, new.claim.deliveries[0].id).await,
        "unknown_delivery"
    );
    assert!(service.take_queued(session).await.unwrap().is_none());
}

#[tokio::test]
async fn capacity_denial_retains_identity_and_cannot_overwrite_new_message() {
    let (pool, service, session) = fixture().await;
    let key = Uuid::new_v4();
    service
        .queue_with_key(session, draft("original"), false, key)
        .await
        .unwrap();
    let batch = service.take_queued(session).await.unwrap().unwrap();
    let process = AgentDelivery::admit(
        &pool,
        &batch.claim,
        &process_input(session),
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    service
        .queue_message(session, draft("new correction"))
        .await
        .unwrap();
    sqlx::query("UPDATE execution_processes SET status = 'failed', dropped = 1 WHERE id = ?")
        .bind(process.id)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::capacity_denied(&pool, process.id)
        .await
        .unwrap();
    service
        .queue_with_key(session, draft("original"), false, key)
        .await
        .unwrap();
    let queue = service.get_queued(session).await.unwrap().unwrap();
    assert_eq!(queue.messages.len(), 2);
    assert_eq!(queue.messages[0].message, "original");
    assert_eq!(queue.messages[1].message, "new correction");
}

#[tokio::test]
async fn failed_predecessor_and_archived_workspace_never_launch_delayed_work() {
    let (pool, service, session) = fixture().await;
    let process = Uuid::new_v4();
    sqlx::query("INSERT INTO execution_processes (id, session_id, run_reason, executor_action, status) VALUES (?, ?, 'codingagent', '{}', 'failed')")
        .bind(process).bind(session).execute(&pool).await.unwrap();
    service
        .queue_message(session, draft("normal"))
        .await
        .unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert!(service.get_queued(session).await.unwrap().is_none());
    assert_eq!(
        sqlx::query_scalar::<_, String>(
            "SELECT error FROM agent_deliveries WHERE session_id = ? ORDER BY position LIMIT 1"
        )
        .bind(session)
        .fetch_one(&pool)
        .await
        .unwrap(),
        "predecessor_failed_or_interrupted"
    );
    service
        .queue_for_capacity(session, draft("capacity"))
        .await
        .unwrap();
    sqlx::query("UPDATE workspaces SET archived = 1 WHERE id = (SELECT workspace_id FROM sessions WHERE id = ?)")
        .bind(session).execute(&pool).await.unwrap();
    AgentDelivery::reconcile(&pool).await.unwrap();
    assert!(service.get_queued(session).await.unwrap().is_none());
}
