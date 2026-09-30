use std::sync::atomic::AtomicUsize;

use super::*;

struct MemoryModel {
    proposal: MemoryProposal,
    decision: MemoryDecision,
    calls: AtomicUsize,
    requests: Mutex<Vec<ModelRequest>>,
    cancel: Option<SqlitePool>,
    unavailable: bool,
}
impl MemoryModel {
    fn new(scope: MemoryScope, decision: MemoryDecision) -> Self {
        Self {
            proposal: MemoryProposal {
                scope,
                claim_key: "communication.validation".into(),
                body: "Leave routine successful validation out of supervisor updates.".into(),
                entity_refs: vec![],
                replaces: None,
            },
            decision,
            calls: AtomicUsize::new(0),
            requests: Mutex::new(vec![]),
            cancel: None,
            unavailable: false,
        }
    }
}
#[async_trait]
impl ConversationModel for MemoryModel {
    fn identity(&self) -> ModelIdentity {
        identity()
    }
    fn supports_memory_changes(&self) -> bool {
        true
    }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        self.requests.lock().unwrap().push(request.clone());
        if request.exchanges.len() < 2 {
            Ok(ModelResponse {
                continuation: ModelContinuation::default(),
                usage: ModelUsage::default(),
                step: ModelStep::Tool {
                    call: ToolCall {
                        id: format!("memory_{}", request.exchanges.len()),
                        tool: SupervisorTool::ProposeMemoryChange {
                            proposal: self.proposal.clone(),
                        },
                    },
                },
            })
        } else {
            Ok(reply("Your preference has been reviewed."))
        }
    }
    async fn assess_memory(
        &self,
        request: &MemoryAssessmentRequest,
    ) -> Result<MemoryAssessmentResponse, ModelError> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        assert!(request.entity_context.is_empty());
        assert!(!request.current_user_request.contains("attacker.invalid"));
        if let Some(pool) = &self.cancel {
            sqlx::query("UPDATE conversation_runs SET status='cancelled',lease_owner=NULL,lease_until=NULL WHERE status='running'").execute(pool).await.unwrap();
        }
        if self.unavailable {
            return Err(ModelError::Unavailable);
        }
        Ok(MemoryAssessmentResponse {
            assessment: MemoryAssessment {
                decision: self.decision.clone(),
                explanation: "Scripted policy result; not a real-model judgment.".into(),
            },
            usage: ModelUsage {
                input_tokens: 7,
                output_tokens: 3,
            },
        })
    }
}
async fn drive(f: &Fixture, model: Arc<MemoryModel>, text: &str) -> RunOutcome {
    f.context.store.accept(f.id, &input(text)).await.unwrap();
    SupervisorWorker::new(f.pool.clone(), model)
        .await
        .unwrap()
        .run_one(f.id, &CancellationToken::new())
        .await
        .unwrap()
}

#[tokio::test]
async fn explicit_memory_persists_across_workers_and_duplicate_tools_recover_one_receipt() {
    let f = fixture().await;
    let model = Arc::new(MemoryModel::new(
        MemoryScope::Global,
        MemoryDecision::Remember,
    ));
    assert!(matches!(
        drive(
            &f,
            model.clone(),
            "Unless something fails, leave validation out."
        )
        .await,
        RunOutcome::Completed { .. }
    ));
    assert_eq!(model.calls.load(Ordering::SeqCst), 1);
    let memories = f.context.store.list_memories(f.id).await.unwrap();
    assert_eq!(memories.len(), 1);
    assert_eq!(memories[0].state, "active");
    assert_eq!(memories[0].author_kind, "user");
    assert_eq!(memories[0].revision, 1);
    let requests = model.requests.lock().unwrap();
    assert_eq!(requests[1].preferences[0].id, memories[0].id);
    assert_eq!(
        requests[2].exchanges[1].result["data"]["already_recorded"],
        true
    );
    drop(requests);
    // A separately constructed worker receives the saved preference at startup.
    let next = Arc::new(MemoryModel::new(
        MemoryScope::Global,
        MemoryDecision::Decline,
    ));
    drive(&f, next.clone(), "What happened since yesterday?").await;
    assert_eq!(
        next.requests.lock().unwrap()[0].preferences[0].id,
        memories[0].id
    );
    let raw: String =
        sqlx::query_scalar("SELECT summary FROM coding_agent_turns WHERE execution_process_id=?")
            .bind(f.process)
            .fetch_one(&f.pool)
            .await
            .unwrap();
    assert_eq!(raw, f.raw);
}

#[tokio::test]
async fn memory_corrections_supersede_exact_revision_and_forgetting_removes_later_context() {
    let f = fixture().await;
    drive(
        &f,
        Arc::new(MemoryModel::new(
            MemoryScope::Global,
            MemoryDecision::Remember,
        )),
        "Remember: leave validation detail out.",
    )
    .await;
    let old = f.context.store.list_memories(f.id).await.unwrap().remove(0);
    let mut correction = MemoryModel::new(MemoryScope::Global, MemoryDecision::Remember);
    correction.proposal.body =
        "Mention failed validation and explain what still needs checking.".into();
    correction.proposal.replaces = Some(MemoryRevision {
        id: old.id,
        revision: old.revision,
    });
    let correction = Arc::new(correction);
    assert!(matches!(
        drive(
            &f,
            correction.clone(),
            "Correct that preference: explain failures and missing checks."
        )
        .await,
        RunOutcome::Completed { .. }
    ));
    assert_eq!(correction.calls.load(Ordering::SeqCst), 1);
    let current = f.context.store.list_memories(f.id).await.unwrap().remove(0);
    assert_eq!(current.revision, 2);
    assert_eq!(current.supersedes_id, Some(old.id));
    let old_state: String = sqlx::query_scalar("SELECT state FROM conversation_memory WHERE id=?")
        .bind(old.id)
        .fetch_one(&f.pool)
        .await
        .unwrap();
    assert_eq!(old_state, "superseded");
    // The stale revision cannot silently overwrite a later correction.
    drive(&f, correction, "Change it again.").await;
    assert_eq!(
        f.context.store.list_memories(f.id).await.unwrap()[0].id,
        current.id
    );
    f.context
        .store
        .forget_memory(f.id, current.id, current.revision)
        .await
        .unwrap();
    let next = Arc::new(MemoryModel::new(
        MemoryScope::Global,
        MemoryDecision::Decline,
    ));
    drive(&f, next.clone(), "Tell me the current state.").await;
    assert!(next.requests.lock().unwrap()[0].preferences.is_empty());
}

#[tokio::test]
async fn inferred_memory_stays_proposed_until_explicit_acceptance_and_is_scoped() {
    let f = fixture().await;
    drive(
        &f,
        Arc::new(MemoryModel::new(
            MemoryScope::Workspace(f.workspace),
            MemoryDecision::Propose,
        )),
        "The Android agent gives too much detail.",
    )
    .await;
    let pending = f.context.store.list_memories(f.id).await.unwrap().remove(0);
    assert_eq!(pending.state, "proposed");
    assert!(
        f.context
            .store
            .memories(f.id, &[MemoryScope::Workspace(f.workspace)], 16384)
            .await
            .unwrap()
            .is_empty()
    );
    let run = lease(&f).await;
    let data = f
        .context
        .execute(
            &run,
            &SupervisorTool::SearchMemory {
                workspace_id: None,
                session_id: Some(f.session),
            },
        )
        .await
        .unwrap();
    assert_eq!(
        data["data"]["proposed_memories"][0]["id"],
        pending.id.to_string()
    );
    let global = f
        .context
        .execute(
            &run,
            &SupervisorTool::SearchMemory {
                workspace_id: None,
                session_id: None,
            },
        )
        .await
        .unwrap();
    assert_eq!(global["data"]["proposed_memories"], json!([]));
    f.context
        .store
        .complete_with_evidence(&run, "That is still a proposed preference.", &[])
        .await
        .unwrap();
    let mut accept = MemoryModel::new(
        MemoryScope::Workspace(f.workspace),
        MemoryDecision::Remember,
    );
    accept.proposal.replaces = Some(MemoryRevision {
        id: pending.id,
        revision: pending.revision,
    });
    drive(
        &f,
        Arc::new(accept),
        "Yes, remember that preference for Android.",
    )
    .await;
    let other = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces(id,branch) VALUES (?,'unrelated')")
        .bind(other)
        .execute(&f.pool)
        .await
        .unwrap();
    assert!(
        f.context
            .store
            .memories(f.id, &[MemoryScope::Workspace(other)], 16384)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        f.context
            .store
            .memories(f.id, &[MemoryScope::Workspace(f.workspace)], 16384)
            .await
            .unwrap()[0]
            .state,
        "active"
    );
}

#[tokio::test]
async fn memory_policy_failure_clarification_and_cancellation_never_write_active_claims() {
    for decision in [MemoryDecision::Clarify, MemoryDecision::Decline] {
        let f = fixture().await;
        drive(
            &f,
            Arc::new(MemoryModel::new(MemoryScope::Global, decision)),
            "The last process is running.",
        )
        .await;
        assert!(
            f.context
                .store
                .list_memories(f.id)
                .await
                .unwrap()
                .is_empty()
        );
    }
    let f = fixture().await;
    let mut unavailable = MemoryModel::new(MemoryScope::Global, MemoryDecision::Remember);
    unavailable.unavailable = true;
    assert_eq!(
        drive(&f, Arc::new(unavailable), "Remember this preference.").await,
        RunOutcome::Failed {
            code: "model_unavailable"
        }
    );
    assert!(
        f.context
            .store
            .list_memories(f.id)
            .await
            .unwrap()
            .is_empty()
    );
    let mut cancelled = MemoryModel::new(MemoryScope::Global, MemoryDecision::Remember);
    cancelled.cancel = Some(f.pool.clone());
    assert_eq!(
        drive(&f, Arc::new(cancelled), "Remember this preference.").await,
        RunOutcome::Fenced
    );
    assert!(
        f.context
            .store
            .list_memories(f.id)
            .await
            .unwrap()
            .is_empty()
    );
}

#[tokio::test]
async fn memory_run_transaction_rejects_foreign_source_and_expired_lease() {
    let f = fixture().await;
    let earlier = f
        .context
        .store
        .accept(f.id, &input("earlier user source"))
        .await
        .unwrap();
    let run = f
        .context
        .store
        .claim_next(f.id, Uuid::new_v4())
        .await
        .unwrap()
        .unwrap();
    f.context
        .store
        .complete_with_evidence(&run, "acknowledged", &[])
        .await
        .unwrap();
    let run = lease(&f).await;
    let mut change = MemoryChange {
        scope: MemoryScope::Global,
        claim_key: "test".into(),
        body: "A durable preference".into(),
        entity_refs: vec![],
        source_message_id: earlier.message.id,
        replaces: None,
        explicit: true,
        valid_until: None,
    };
    assert!(matches!(
        f.context.store.put_run_memory(&run, &change).await,
        Err(ConversationError::InvalidRecord)
    ));
    change.source_message_id = run.input_message_id;
    sqlx::query("UPDATE conversation_runs SET lease_until=unixepoch()-1 WHERE id=?")
        .bind(run.id)
        .execute(&f.pool)
        .await
        .unwrap();
    assert!(matches!(
        f.context.store.put_run_memory(&run, &change).await,
        Err(ConversationError::StaleLease)
    ));
    assert!(
        f.context
            .store
            .list_memories(f.id)
            .await
            .unwrap()
            .is_empty()
    );
}
