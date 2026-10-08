use executors::actions::{ExecutorAction, coding_agent_initial::CodingAgentInitialRequest};
use sqlx::sqlite::SqlitePoolOptions;

use super::*;

async fn fixture() -> (SqlitePool, ConversationStore, ConversationRun) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    let scope = ConversationScope::local_operator(&pool).await.unwrap();
    let store = ConversationStore::new(pool.clone(), scope);
    let id = store.resolve().await.unwrap().id;
    store
        .accept(
            id,
            &AcceptConversationMessage {
                client_message_id: Uuid::new_v4(),
                body: "Tell the Android agent that web remains the source of truth.".into(),
                origin: ConversationInputOrigin::Typed,
                reply_to_id: None,
            },
        )
        .await
        .unwrap();
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    (pool, store, run)
}

async fn recipient(
    pool: &SqlitePool,
    running: bool,
    executor: BaseCodingAgent,
) -> (Uuid, Uuid, ExecutorConfig) {
    let workspace = Uuid::new_v4();
    let session = Uuid::new_v4();
    let process = Uuid::new_v4();
    let mut config = ExecutorConfig::new(executor);
    config.model_id = Some("selected-model".into());
    config.reasoning_id = Some("high".into());
    sqlx::query(
        "INSERT INTO workspaces (id,branch,name) VALUES (?, 'android-parity', 'Android parity')",
    )
    .bind(workspace)
    .execute(pool)
    .await
    .unwrap();
    sqlx::query(
        "INSERT INTO sessions (id,workspace_id,executor,name) VALUES (?,?,?,'Implementation')",
    )
    .bind(session)
    .bind(workspace)
    .bind(executor.to_string())
    .execute(pool)
    .await
    .unwrap();
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "original raw request".into(),
            executor_config: config.clone(),
            working_dir: None,
        }),
        None,
    );
    sqlx::query("INSERT INTO execution_processes (id,session_id,run_reason,executor_action,status) VALUES (?,?,'codingagent',?,?)").bind(process).bind(session).bind(Json(action)).bind(if running {"running"} else {"completed"}).execute(pool).await.unwrap();
    sqlx::query("INSERT INTO coding_agent_turns (id,execution_process_id,prompt,summary) VALUES (?,?,'original raw request','Validation:: 42 tests passed. Exact original report.')").bind(Uuid::new_v4()).bind(process).execute(pool).await.unwrap();
    (session, process, config)
}

fn assessment(impact: MessageImpact) -> MessageAssessment {
    MessageAssessment {
        authorised_by_user: true,
        impact,
        recipients_explicit: true,
        explanation: "Matches the user's requested instruction and recipients.".into(),
    }
}

fn delivery_process(
    claim: &crate::models::agent_delivery::DeliveryClaim,
) -> crate::models::execution_process::CreateExecutionProcess {
    let data = &claim.deliveries[0].data;
    crate::models::execution_process::CreateExecutionProcess {
        session_id: claim.session_id,
        executor_action: ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: data.message.clone(),
                executor_config: data.executor_config.clone(),
                working_dir: None,
            }),
            None,
        ),
        run_reason: crate::models::execution_process::ExecutionProcessRunReason::CodingAgent,
    }
}

#[tokio::test]
async fn queue_preserves_direct_batches_but_never_combines_a_supervisor_instruction_or_its_config()
{
    let (pool, store, run) = fixture().await;
    let (session, _, config) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    for message in ["direct first", "direct second"] {
        AgentDelivery::enqueue(
            &pool,
            session,
            DraftFollowUpData {
                message: message.into(),
                executor_config: config.clone(),
            },
            false,
            Uuid::new_v4(),
        )
        .await
        .unwrap();
    }
    let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    store
        .admit_agent_message(run.conversation_id, action.id)
        .await
        .unwrap();
    let mut later_config = config.clone();
    later_config.model_id = Some("different-model".into());
    AgentDelivery::enqueue(
        &pool,
        session,
        DraftFollowUpData {
            message: "direct last".into(),
            executor_config: later_config.clone(),
        },
        false,
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let first = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
    assert_eq!(
        first
            .deliveries
            .iter()
            .map(|d| d.data.message.as_str())
            .collect::<Vec<_>>(),
        vec!["direct first", "direct second"]
    );
    AgentDelivery::fail_claim(&pool, &first, "fixture_terminal")
        .await
        .unwrap();
    let supervisor = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
    assert_eq!(supervisor.deliveries.len(), 1);
    assert_eq!(supervisor.deliveries[0].action_id, Some(action.id));
    assert_eq!(supervisor.deliveries[0].data.executor_config, config);
    AgentDelivery::validate_supervisor_claim(&pool, &supervisor)
        .await
        .unwrap();
    AgentDelivery::fail_claim(&pool, &supervisor, "fixture_terminal")
        .await
        .unwrap();
    let last = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
    assert_eq!(last.deliveries.len(), 1);
    assert_eq!(last.deliveries[0].data.message, "direct last");
    assert_eq!(last.deliveries[0].data.executor_config, later_config);
}

#[tokio::test]
async fn queued_supervisor_target_change_after_precheck_rolls_back_process_prompt_and_receipt_admission()
 {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    store
        .admit_agent_message(run.conversation_id, action.id)
        .await
        .unwrap();
    let claim = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
    AgentDelivery::validate_supervisor_claim(&pool, &claim)
        .await
        .unwrap();
    sqlx::query("UPDATE workspaces SET branch='different-topic' WHERE id=?")
        .bind(claim.deliveries[0].workspace_id)
        .execute(&pool)
        .await
        .unwrap();
    let result = AgentDelivery::admit(
        &pool,
        &claim,
        &delivery_process(&claim),
        Uuid::new_v4(),
        &[],
    )
    .await;
    assert!(matches!(
        result,
        Err(crate::models::execution_process::ExecutionProcessError::DeliveryRejected)
    ));
    let (state, process): (String, Option<Uuid>) =
        sqlx::query_as("SELECT state,execution_process_id FROM agent_deliveries WHERE id=?")
            .bind(claim.deliveries[0].id)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(state, "dispatching");
    assert_eq!(process, None);
    for table in ["execution_processes", "coding_agent_turns"] {
        assert_eq!(
            sqlx::query_scalar::<_, i64>(&format!("SELECT count(*) FROM {table}"))
                .fetch_one(&pool)
                .await
                .unwrap(),
            1
        );
    }
    AgentDelivery::fail_claim(&pool, &claim, "supervisor_target_changed")
        .await
        .unwrap();
    assert_eq!(
        store
            .reconcile_action(run.conversation_id, action.id)
            .await
            .unwrap()
            .state,
        "failed"
    );
}

#[tokio::test]
async fn execution_admission_rejects_overridden_config_even_when_the_frozen_target_is_unchanged() {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    store
        .admit_agent_message(run.conversation_id, action.id)
        .await
        .unwrap();
    let claim = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
    let mut process = delivery_process(&claim);
    if let ExecutorActionType::CodingAgentInitialRequest(request) = &mut process.executor_action.typ
    {
        request.executor_config.reasoning_id = Some("different-reasoning".into());
    }
    assert!(matches!(
        AgentDelivery::admit(&pool, &claim, &process, Uuid::new_v4(), &[]).await,
        Err(crate::models::execution_process::ExecutionProcessError::DeliveryRejected)
    ));
    let accepted = AgentDelivery::admit(
        &pool,
        &claim,
        &delivery_process(&claim),
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    assert_eq!(accepted.session_id, session);
    let raw: String =
        sqlx::query_scalar("SELECT prompt FROM coding_agent_turns WHERE execution_process_id=?")
            .bind(accepted.id)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(raw, claim.deliveries[0].data.message);
}

#[tokio::test]
async fn queued_supervisor_delivery_rejects_executor_changes_and_cancelled_authorization() {
    for cancel in [false, true] {
        let (pool, store, run) = fixture().await;
        let (session, process, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
        let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
        store
            .admit_agent_message(run.conversation_id, action.id)
            .await
            .unwrap();
        let claim = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
        if cancel {
            sqlx::query("UPDATE conversation_actions SET state='cancelled' WHERE id=?")
                .bind(action.id)
                .execute(&pool)
                .await
                .unwrap();
        } else {
            let mut updated = delivery_process(&claim).executor_action;
            if let ExecutorActionType::CodingAgentInitialRequest(request) = &mut updated.typ {
                request.executor_config.model_id = Some("changed-model".into());
            }
            sqlx::query("UPDATE execution_processes SET executor_action=? WHERE id=?")
                .bind(Json(updated))
                .bind(process)
                .execute(&pool)
                .await
                .unwrap();
        }
        assert!(matches!(
            AgentDelivery::validate_supervisor_claim(&pool, &claim).await,
            Err(crate::models::execution_process::ExecutionProcessError::DeliveryRejected)
        ));
    }
}

async fn proposal(
    store: &ConversationStore,
    run: &ConversationRun,
    sessions: &[Uuid],
    impact: MessageImpact,
) -> ConversationAction {
    let message = store
        .prepare_agent_message(
            run.conversation_id,
            "Keep web as the source of truth.\nExact instruction.".into(),
            sessions,
        )
        .await
        .unwrap();
    store
        .propose_agent_message(run, Uuid::new_v4(), &message, &assessment(impact))
        .await
        .unwrap()
}

async fn confirm(
    store: &ConversationStore,
    id: Uuid,
    action: &ConversationAction,
) -> Result<ConversationAction> {
    let grant = store
        .confirmations(id)
        .await
        .unwrap()
        .into_iter()
        .find(|c| c.action_id == action.id)
        .unwrap();
    store
        .answer_confirmation(
            id,
            grant.id,
            &grant.payload_digest,
            grant.action_revision,
            true,
        )
        .await
}

#[tokio::test]
async fn explicit_messages_preserve_config_and_raw_history_with_one_delivery_on_concurrent_retry() {
    let (pool, store, run) = fixture().await;
    let (session, _, config) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    assert_eq!(action.state, "approved");
    assert!(
        store
            .confirmations(run.conversation_id)
            .await
            .unwrap()
            .is_empty()
    );
    let (a, b) = tokio::join!(
        store.admit_agent_message(run.conversation_id, action.id),
        store.admit_agent_message(run.conversation_id, action.id)
    );
    let a = a.unwrap();
    let b = b.unwrap();
    assert_eq!(a.deliveries.len(), 1);
    assert_eq!(a.deliveries[0].id, b.deliveries[0].id);
    assert_eq!(a.deliveries[0].action_id, Some(action.id));
    assert_eq!(a.deliveries[0].source_kind, "supervisor");
    assert_eq!(a.deliveries[0].data.executor_config, config);
    assert_eq!(a.deliveries[0].state, "queued");
    assert_eq!(
        a.deliveries[0].data.message,
        "Keep web as the source of truth.\nExact instruction."
    );
    assert!(a.steering_attempts.is_empty());
    let (prompt, summary): (String, String) =
        sqlx::query_as("SELECT prompt,summary FROM coding_agent_turns")
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(prompt, "original raw request");
    assert_eq!(
        summary,
        "Validation:: 42 tests passed. Exact original report."
    );
    assert_eq!(
        store
            .messages(run.conversation_id, None, 20)
            .await
            .unwrap()
            .len(),
        1
    );
}

#[tokio::test]
async fn consequential_messages_require_exact_owned_unexpired_confirmation_and_replays_do_not_expand_it()
 {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let message = store
        .prepare_agent_message(
            run.conversation_id,
            "Delete the obsolete branches.".into(),
            &[session],
        )
        .await
        .unwrap();
    let key = Uuid::new_v4();
    let action = store
        .propose_agent_message(
            &run,
            key,
            &message,
            &assessment(MessageImpact::Consequential),
        )
        .await
        .unwrap();
    store
        .propose_agent_message(
            &run,
            key,
            &message,
            &assessment(MessageImpact::Consequential),
        )
        .await
        .unwrap();
    assert_eq!(action.state, "proposed");
    assert!(
        store
            .admit_agent_message(run.conversation_id, action.id)
            .await
            .is_err()
    );
    let grants = store.confirmations(run.conversation_id).await.unwrap();
    assert_eq!(grants.len(), 1);
    assert_eq!(
        store
            .events(run.conversation_id, 0, 200)
            .await
            .unwrap()
            .iter()
            .filter(|e| e.event_type == "confirmation.requested")
            .count(),
        1
    );
    let grant = &grants[0];
    assert!(matches!(
        store
            .answer_confirmation(
                run.conversation_id,
                grant.id,
                "changed",
                grant.action_revision,
                true
            )
            .await,
        Err(ConversationError::RevisionConflict)
    ));
    assert!(matches!(
        store
            .answer_confirmation(
                run.conversation_id,
                grant.id,
                &grant.payload_digest,
                grant.action_revision + 1,
                true
            )
            .await,
        Err(ConversationError::RevisionConflict)
    ));
    let outsider = ConversationStore::new(
        pool.clone(),
        ConversationScope {
            principal_id: Uuid::new_v4(),
            ..store.scope.clone()
        },
    );
    assert!(matches!(
        outsider
            .answer_confirmation(
                run.conversation_id,
                grant.id,
                &grant.payload_digest,
                grant.action_revision,
                true
            )
            .await,
        Err(ConversationError::NotFound)
    ));
    // Completion of the supervisor's explanation does not invalidate a pending review.
    store
        .complete(
            &run,
            "Please review the branches and instruction before I send this.",
        )
        .await
        .unwrap();
    let accepted = confirm(&store, run.conversation_id, &action).await.unwrap();
    assert_eq!(accepted.state, "approved");
    assert_eq!(
        confirm(&store, run.conversation_id, &action)
            .await
            .unwrap()
            .revision,
        accepted.revision
    );
    assert!(matches!(
        store
            .answer_confirmation(
                run.conversation_id,
                grant.id,
                &grant.payload_digest,
                grant.action_revision,
                false
            )
            .await,
        Err(ConversationError::RevisionConflict)
    ));
    let admitted = store
        .admit_agent_message(run.conversation_id, action.id)
        .await
        .unwrap();
    assert_eq!(admitted.deliveries[0].data.message, message.message);
}

#[tokio::test]
async fn status_only_requests_and_dedicated_controls_cannot_be_smuggled_through_messages() {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let message = store
        .prepare_agent_message(
            run.conversation_id,
            "Start autonomous work.".into(),
            &[session],
        )
        .await
        .unwrap();
    for policy in [
        MessageAssessment {
            authorised_by_user: false,
            ..assessment(MessageImpact::Ordinary)
        },
        assessment(MessageImpact::UnsupportedControl),
    ] {
        let action = store
            .propose_agent_message(&run, Uuid::new_v4(), &message, &policy)
            .await
            .unwrap();
        assert_eq!(action.state, "rejected");
        assert!(
            store
                .admit_agent_message(run.conversation_id, action.id)
                .await
                .is_err()
        );
    }
    assert!(
        store
            .confirmations(run.conversation_id)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM agent_deliveries")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
}

#[tokio::test]
async fn inferred_broadcast_needs_review_but_explicit_recipient_set_does_not() {
    let (pool, store, run) = fixture().await;
    let mut sessions = Vec::new();
    for _ in 0..6 {
        sessions.push(recipient(&pool, false, BaseCodingAgent::Codex).await.0);
    }
    let message = store
        .prepare_agent_message(
            run.conversation_id,
            "Use web as the reference.".into(),
            &sessions,
        )
        .await
        .unwrap();
    let inferred = MessageAssessment {
        recipients_explicit: false,
        ..assessment(MessageImpact::Ordinary)
    };
    let action = store
        .propose_agent_message(&run, Uuid::new_v4(), &message, &inferred)
        .await
        .unwrap();
    assert_eq!(action.state, "proposed");
    let explicit = store
        .propose_agent_message(
            &run,
            Uuid::new_v4(),
            &message,
            &assessment(MessageImpact::Ordinary),
        )
        .await
        .unwrap();
    assert_eq!(explicit.state, "approved");
    let admitted = store
        .admit_agent_message(run.conversation_id, explicit.id)
        .await
        .unwrap();
    assert_eq!(admitted.deliveries.len(), sessions.len());
}

#[tokio::test]
async fn unchanged_version_cannot_authorise_forged_executor_or_workspace_fields() {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let original = store
        .prepare_agent_message(
            run.conversation_id,
            "Use web as the reference.".into(),
            &[session],
        )
        .await
        .unwrap();
    let mut forged = original.clone();
    forged.targets[0].executor_config.model_id = Some("unreviewed-model".into());
    assert!(matches!(
        store
            .propose_agent_message(
                &run,
                Uuid::new_v4(),
                &forged,
                &assessment(MessageImpact::Ordinary)
            )
            .await,
        Err(ConversationError::RevisionConflict)
    ));
    forged = original.clone();
    forged.targets[0].workspace_id = Uuid::new_v4();
    assert!(matches!(
        store
            .propose_agent_message(
                &run,
                Uuid::new_v4(),
                &forged,
                &assessment(MessageImpact::Ordinary)
            )
            .await,
        Err(ConversationError::RevisionConflict)
    ));
    let key = Uuid::new_v4();
    store
        .propose_agent_message(
            &run,
            key,
            &original,
            &assessment(MessageImpact::Consequential),
        )
        .await
        .unwrap();
    assert!(matches!(
        store
            .propose_agent_message(&run, key, &original, &assessment(MessageImpact::Ordinary))
            .await,
        Err(ConversationError::IdempotencyConflict)
    ));
    let mut changed = original;
    changed.message.push_str(" And delete everything.");
    assert!(matches!(
        store
            .propose_agent_message(
                &run,
                key,
                &changed,
                &assessment(MessageImpact::Consequential)
            )
            .await,
        Err(ConversationError::IdempotencyConflict)
    ));
}

#[tokio::test]
async fn confirmation_and_dispatch_both_revalidate_target_identity() {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let pending = proposal(&store, &run, &[session], MessageImpact::Consequential).await;
    let approved = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    sqlx::query("UPDATE sessions SET name='A different purpose' WHERE id=?")
        .bind(session)
        .execute(&pool)
        .await
        .unwrap();
    assert!(matches!(
        confirm(&store, run.conversation_id, &pending).await,
        Err(ConversationError::RevisionConflict)
    ));
    assert!(matches!(
        store
            .admit_agent_message(run.conversation_id, approved.id)
            .await,
        Err(ConversationError::RevisionConflict)
    ));
    sqlx::query("UPDATE workspaces SET archived=1")
        .execute(&pool)
        .await
        .unwrap();
    assert!(matches!(
        store
            .prepare_agent_message(run.conversation_id, "message".into(), &[session])
            .await,
        Err(ConversationError::NotFound)
    ));
}

#[tokio::test]
async fn cancelled_failed_and_expired_runs_fence_undispatched_actions() {
    for mode in ["cancel", "fail", "expire"] {
        let (pool, store, run) = fixture().await;
        let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
        let approved = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
        let pending = proposal(&store, &run, &[session], MessageImpact::Consequential).await;
        match mode {
            "cancel" => {
                store.cancel(run.conversation_id, run.id).await.unwrap();
            }
            "fail" => {
                store.fail_run(&run, "model_unavailable").await.unwrap();
            }
            _ => {
                sqlx::query("UPDATE conversation_runs SET lease_until=0 WHERE id=?")
                    .bind(run.id)
                    .execute(&pool)
                    .await
                    .unwrap();
                store
                    .claim_next(run.conversation_id, Uuid::new_v4())
                    .await
                    .unwrap();
            }
        }
        assert_eq!(
            store
                .action(run.conversation_id, approved.id)
                .await
                .unwrap()
                .state,
            "cancelled",
            "{mode}"
        );
        assert!(
            store
                .admit_agent_message(run.conversation_id, approved.id)
                .await
                .is_err()
        );
        assert!(
            confirm(&store, run.conversation_id, &pending)
                .await
                .is_err()
        );
        assert!(
            store
                .action_deliveries(run.conversation_id, approved.id)
                .await
                .unwrap()
                .is_empty()
        );
    }
}

#[tokio::test]
async fn expired_confirmation_cannot_be_accepted_or_admitted_after_prior_acceptance() {
    for accept_first in [false, true] {
        let (pool, store, run) = fixture().await;
        let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
        let action = proposal(&store, &run, &[session], MessageImpact::Consequential).await;
        if accept_first {
            confirm(&store, run.conversation_id, &action).await.unwrap();
        }
        sqlx::query("UPDATE conversation_confirmations SET expires_at=0")
            .execute(&pool)
            .await
            .unwrap();
        if !accept_first {
            assert!(confirm(&store, run.conversation_id, &action).await.is_err());
        }
        assert!(
            store
                .admit_agent_message(run.conversation_id, action.id)
                .await
                .is_err()
        );
        assert_eq!(
            store
                .reconcile_action(run.conversation_id, action.id)
                .await
                .unwrap()
                .state,
            "cancelled"
        );
        assert_eq!(
            store.confirmations(run.conversation_id).await.unwrap()[0].state,
            "expired"
        );
    }
}

#[tokio::test]
async fn process_completion_changes_delivery_mode_without_changing_pinned_session_or_config() {
    let (pool, store, run) = fixture().await;
    let (session, process, config) = recipient(&pool, true, BaseCodingAgent::Codex).await;
    let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(process)
        .execute(&pool)
        .await
        .unwrap();
    let admitted = store
        .admit_agent_message(run.conversation_id, action.id)
        .await
        .unwrap();
    assert!(admitted.steering_attempts.is_empty());
    assert_eq!(admitted.deliveries[0].delivery_mode, "queue");
    assert_eq!(admitted.deliveries[0].session_id, session);
    assert_eq!(admitted.deliveries[0].data.executor_config, config);
}

#[tokio::test]
async fn active_codex_attempt_is_owned_once_and_mixed_recipients_keep_separate_receipts() {
    let (pool, store, run) = fixture().await;
    let (codex, process, _) = recipient(&pool, true, BaseCodingAgent::Codex).await;
    let (other, other_process, _) = recipient(&pool, true, BaseCodingAgent::ClaudeCode).await;
    let action = proposal(&store, &run, &[codex, other], MessageImpact::Ordinary).await;
    let (a, b) = tokio::join!(
        store.admit_agent_message(run.conversation_id, action.id),
        store.admit_agent_message(run.conversation_id, action.id)
    );
    let a = a.unwrap();
    let b = b.unwrap();
    assert_eq!(a.steering_attempts.len() + b.steering_attempts.len(), 1);
    assert_eq!(a.deliveries.len(), 2);
    assert_eq!(a.deliveries[0].execution_process_id, Some(process));
    assert_eq!(a.deliveries[1].predecessor_process_id, Some(other_process));
    assert_eq!(a.deliveries[1].state, "queued");
    sqlx::query(
        "UPDATE agent_deliveries SET state='unknown_delivery',lease_until=NULL WHERE session_id=?",
    )
    .bind(codex)
    .execute(&pool)
    .await
    .unwrap();
    assert_eq!(
        store
            .reconcile_action(run.conversation_id, action.id)
            .await
            .unwrap()
            .state,
        "unknown_delivery"
    );
    sqlx::query("UPDATE agent_deliveries SET state=CASE WHEN session_id=? THEN 'failed' ELSE 'completed' END").bind(codex).execute(&pool).await.unwrap();
    assert_eq!(
        store
            .reconcile_action(run.conversation_id, action.id)
            .await
            .unwrap()
            .state,
        "failed"
    );
    assert_eq!(
        store
            .action_deliveries(run.conversation_id, action.id)
            .await
            .unwrap()[1]
            .state,
        "completed"
    );
    assert!(
        store
            .admit_agent_message(run.conversation_id, action.id)
            .await
            .unwrap()
            .steering_attempts
            .is_empty()
    );
}

#[tokio::test]
async fn recipient_insert_failure_rolls_back_every_delivery_and_allows_safe_retry() {
    let (pool, store, run) = fixture().await;
    let a = recipient(&pool, false, BaseCodingAgent::Codex).await.0;
    let b = recipient(&pool, false, BaseCodingAgent::Codex).await.0;
    let action = proposal(&store, &run, &[a, b], MessageImpact::Ordinary).await;
    sqlx::query("CREATE TRIGGER second_recipient_fault BEFORE INSERT ON agent_deliveries WHEN (SELECT count(*) FROM agent_deliveries)>0 BEGIN SELECT RAISE(ABORT,'injected disk fault'); END").execute(&pool).await.unwrap();
    assert!(
        store
            .admit_agent_message(run.conversation_id, action.id)
            .await
            .is_err()
    );
    assert!(
        store
            .action_deliveries(run.conversation_id, action.id)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        store
            .action(run.conversation_id, action.id)
            .await
            .unwrap()
            .state,
        "approved"
    );
    sqlx::query("DROP TRIGGER second_recipient_fault")
        .execute(&pool)
        .await
        .unwrap();
    assert_eq!(
        store
            .admit_agent_message(run.conversation_id, action.id)
            .await
            .unwrap()
            .deliveries
            .len(),
        2
    );
}

#[tokio::test]
async fn exported_confirmations_are_removed_with_supervisor_history_and_leave_raw_reports() {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    let action = proposal(&store, &run, &[session], MessageImpact::Consequential).await;
    let exported = store.export(run.conversation_id).await.unwrap();
    assert_eq!(exported.confirmations.len(), 1);
    assert_eq!(exported.confirmations[0].action_id, action.id);
    store
        .delete_content(run.conversation_id, exported.conversation.revision)
        .await
        .unwrap();
    assert!(
        store
            .confirmations(run.conversation_id)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM coding_agent_turns")
            .fetch_one(&pool)
            .await
            .unwrap(),
        1
    );
}

#[tokio::test]
async fn filling_legacy_executor_identity_does_not_invalidate_approved_queue_target() {
    let (pool, store, run) = fixture().await;
    let (session, _, _) = recipient(&pool, false, BaseCodingAgent::Codex).await;
    sqlx::query("UPDATE sessions SET executor=NULL WHERE id=?")
        .bind(session)
        .execute(&pool)
        .await
        .unwrap();
    let action = proposal(&store, &run, &[session], MessageImpact::Ordinary).await;
    store
        .admit_agent_message(run.conversation_id, action.id)
        .await
        .unwrap();
    let claim = AgentDelivery::claim(&pool, session).await.unwrap().unwrap();
    sqlx::query("UPDATE sessions SET executor='CODEX' WHERE id=?")
        .bind(session)
        .execute(&pool)
        .await
        .unwrap();
    AgentDelivery::validate_supervisor_claim(&pool, &claim)
        .await
        .unwrap();
    AgentDelivery::admit(
        &pool,
        &claim,
        &delivery_process(&claim),
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
}
