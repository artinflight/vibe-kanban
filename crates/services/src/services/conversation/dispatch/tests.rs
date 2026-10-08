use std::{
    collections::HashSet,
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
};

use async_trait::async_trait;
use db::models::conversation::{
    AcceptConversationMessage, ConversationInputOrigin, ConversationScope,
    actions::{MessageAssessment, MessageImpact},
};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::{BaseCodingAgent, codex::client::GoalMessageAdmission},
    profile::ExecutorConfig,
};
use sqlx::sqlite::SqlitePoolOptions;

use super::{super::dispatch_gate::RuntimeState, *};
struct Runtime {
    blocked: AtomicBool,
}
#[async_trait]
impl RuntimeState for Runtime {
    fn approvals(&self, ids: &[Uuid]) -> HashSet<Uuid> {
        if self.blocked.load(Ordering::SeqCst) {
            ids.iter().copied().collect()
        } else {
            HashSet::new()
        }
    }
    async fn capacity_managed(&self, _: Uuid) -> Result<bool, DispatchBlock> {
        Ok(false)
    }
    async fn goal(&self, _: Uuid) -> Result<GoalMessageAdmission, DispatchBlock> {
        Ok(GoalMessageAdmission::Allowed)
    }
}
async fn fixture(running: &[bool]) -> (ActionDispatcher, Arc<Runtime>, Uuid, Uuid) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let store = ConversationStore::new(
        pool.clone(),
        ConversationScope::local_operator(&pool).await.unwrap(),
    );
    let id = store.resolve().await.unwrap().id;
    store
        .accept(
            id,
            &AcceptConversationMessage {
                client_message_id: Uuid::new_v4(),
                body: "Tell both Android agents that web remains the source of truth.".into(),
                origin: ConversationInputOrigin::Typed,
                reply_to_id: None,
            },
        )
        .await
        .unwrap();
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    let mut sessions = vec![];
    for active in running {
        let (workspace, session, process) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
        sqlx::query("INSERT INTO workspaces(id,branch,name) VALUES (?,'mobile/parity','Android')")
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO sessions(id,workspace_id,executor) VALUES (?,?,'CODEX')")
            .bind(session)
            .bind(workspace)
            .execute(&pool)
            .await
            .unwrap();
        let action = ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: "original raw request".into(),
                executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                working_dir: None,
            }),
            None,
        );
        sqlx::query("INSERT INTO execution_processes(id,session_id,executor_action,run_reason,status) VALUES (?,?,?,'codingagent',?)").bind(process).bind(session).bind(sqlx::types::Json(action)).bind(if *active {"running"} else {"completed"}).execute(&pool).await.unwrap();
        sessions.push(session);
    }
    let message = store
        .prepare_agent_message(id, "Web remains the source of truth.".into(), &sessions)
        .await
        .unwrap();
    let proposal = store
        .propose_agent_message(
            &run,
            Uuid::new_v4(),
            &message,
            &MessageAssessment {
                authorised_by_user: true,
                impact: MessageImpact::Ordinary,
                recipients_explicit: true,
                explanation: "Explicit user instruction and recipients".into(),
            },
        )
        .await
        .unwrap();
    let runtime = Arc::new(Runtime {
        blocked: AtomicBool::new(false),
    });
    let gate = DispatchGate {
        pool: pool.clone(),
        runtime: runtime.clone(),
    };
    (
        ActionDispatcher::new(pool, store, gate),
        runtime,
        id,
        proposal.id,
    )
}

#[tokio::test]
async fn mixes_queue_and_exact_process_steering_without_replay_or_transport_fallback() {
    let (dispatcher, runtime, id, action) = fixture(&[true, false]).await;
    let calls = AtomicUsize::new(0);
    let result = dispatcher
        .dispatch_with(id, action, |delivery| {
            calls.fetch_add(1, Ordering::SeqCst);
            assert_eq!(delivery.data.message, "Web remains the source of truth.");
            assert_eq!(delivery.delivery_mode, "steer");
            assert!(delivery.execution_process_id.is_some());
            async { Ok(true) }
        })
        .await
        .unwrap();
    assert_eq!(result.state, "dispatching");
    let receipts = dispatcher
        .store
        .action_deliveries(id, action)
        .await
        .unwrap();
    assert_eq!(receipts.len(), 2);
    assert!(
        receipts
            .iter()
            .any(|d| d.steering_acknowledged_at.is_some())
    );
    assert!(receipts.iter().any(|d| d.state == "queued"));
    runtime.blocked.store(true, Ordering::SeqCst);
    dispatcher
        .dispatch_with(id, action, |_| async { panic!("replay must not send") })
        .await
        .unwrap();
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn preflight_blocks_entire_set_before_any_admission() {
    let (dispatcher, runtime, id, action) = fixture(&[false, true]).await;
    runtime.blocked.store(true, Ordering::SeqCst);
    assert!(matches!(
        dispatcher
            .dispatch_with(id, action, |_| async { panic!("blocked") })
            .await,
        Err(DispatchError::Blocked(DispatchBlock::PendingApproval))
    ));
    assert!(
        dispatcher
            .store
            .action_deliveries(id, action)
            .await
            .unwrap()
            .is_empty()
    );
}

#[tokio::test]
async fn runtime_change_between_recipients_leaves_partial_evidence_and_never_sends_blocked_input() {
    let (dispatcher, runtime, id, action) = fixture(&[true, true]).await;
    let calls = AtomicUsize::new(0);
    dispatcher
        .dispatch_with(id, action, |_| {
            calls.fetch_add(1, Ordering::SeqCst);
            runtime.blocked.store(true, Ordering::SeqCst);
            async { Ok(true) }
        })
        .await
        .unwrap();
    let receipts = dispatcher
        .store
        .action_deliveries(id, action)
        .await
        .unwrap();
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    assert!(
        receipts
            .iter()
            .any(|d| d.steering_acknowledged_at.is_some())
    );
    assert!(receipts.iter().any(|d|d.state=="failed" && d.error.as_deref()==Some("pending_executor_approval")));
}

#[tokio::test]
async fn rpc_error_is_unknown_and_known_unavailable_is_failed_neither_requeues() {
    for uncertain in [true, false] {
        let (dispatcher, _, id, action) = fixture(&[true]).await;
        let result = dispatcher
            .dispatch_with(id, action, |_| async move {
                if uncertain {
                    Err(ContainerError::Other(anyhow::anyhow!(
                        "simulated transport loss"
                    )))
                } else {
                    Ok(false)
                }
            })
            .await
            .unwrap();
        assert_eq!(
            result.state,
            if uncertain {
                "unknown_delivery"
            } else {
                "failed"
            }
        );
        dispatcher
            .dispatch_with(id, action, |_| async {
                panic!("failed/unknown must not resend")
            })
            .await
            .unwrap();
        let receipts = dispatcher
            .store
            .action_deliveries(id, action)
            .await
            .unwrap();
        assert_eq!(receipts.len(), 1);
        assert_eq!(receipts[0].delivery_mode, "steer");
    }
}

#[tokio::test]
async fn changed_target_between_recipients_is_not_sent_and_recovery_publishes_terminal_outcome() {
    let (dispatcher, _, id, action) = fixture(&[true, true]).await;
    let calls = AtomicUsize::new(0);
    dispatcher
        .dispatch_with(id, action, |delivery| {
            calls.fetch_add(1, Ordering::SeqCst);
            let pool = dispatcher.pool.clone();
            async move {
                sqlx::query("UPDATE workspaces SET branch='changed-after-admission' WHERE id!=?")
                    .bind(delivery.workspace_id)
                    .execute(&pool)
                    .await?;
                Ok(true)
            }
        })
        .await
        .unwrap();
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    let receipts = dispatcher
        .store
        .action_deliveries(id, action)
        .await
        .unwrap();
    assert!(
        receipts
            .iter()
            .any(|d| d.error.as_deref() == Some("target_unavailable"))
    );
    sqlx::query("UPDATE execution_processes SET status='completed'")
        .execute(&dispatcher.pool)
        .await
        .unwrap();
    AgentDelivery::reconcile(&dispatcher.pool).await.unwrap();
    assert_eq!(
        dispatcher.store.reconcile_delivery_actions().await.unwrap(),
        1
    );
    assert_eq!(
        dispatcher.store.action(id, action).await.unwrap().state,
        "failed"
    );
    assert_eq!(
        dispatcher.store.reconcile_delivery_actions().await.unwrap(),
        0
    );
    let replay = dispatcher.store.events(id, 0, 200).await.unwrap();
    assert!(replay.iter().any(|e| e.event_type == "action.status"
        && serde_json::from_str::<serde_json::Value>(&e.payload).unwrap()["state"] == "failed"));
}
