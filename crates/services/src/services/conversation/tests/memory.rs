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
async fn drive(f: &Fixture, model: Arc<dyn ConversationModel>, text: &str) -> RunOutcome {
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
    let model = Arc::new(MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply));
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
        Arc::new(MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply)),
        "Remember: leave validation detail out.",
    )
    .await;
    let old = f.context.store.list_memories(f.id).await.unwrap().remove(0);
    let mut correction = MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply);
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
    let mut accept = MemoryModel::new(MemoryScope::Workspace(f.workspace), MemoryDecision::Apply);
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
    let mut unavailable = MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply);
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
    let mut cancelled = MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply);
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

struct ControlModel {
    steps: Vec<SupervisorTool>,
    requests: Mutex<Vec<ModelRequest>>,
    policy: MemoryDecision,
    assessments: Mutex<Vec<Value>>,
    cancel: Option<SqlitePool>,
}
#[async_trait]
impl ConversationModel for ControlModel {
    fn identity(&self) -> ModelIdentity {
        identity()
    }
    fn supports_memory_changes(&self) -> bool {
        true
    }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        let mut requests = self.requests.lock().unwrap();
        let step = requests.len();
        requests.push(request.clone());
        if let Some(tool) = self.steps.get(step) {
            Ok(ModelResponse {
                step: ModelStep::Tool {
                    call: ToolCall {
                        id: format!("control_{step}"),
                        tool: tool.clone(),
                    },
                },
                continuation: ModelContinuation(vec![
                    json!({"old_context":"discard-this-continuation"}),
                ]),
                usage: ModelUsage::default(),
            })
        } else {
            let mut answer =
                reply("I have updated that preference and checked the requested work.");
            if let ModelStep::Reply { evidence_ids, .. } = &mut answer.step {
                *evidence_ids = request
                    .exchanges
                    .iter()
                    .filter_map(|e| {
                        e.result["data"]["evidence_id"]
                            .as_str()
                            .and_then(|s| Uuid::parse_str(s).ok())
                    })
                    .collect();
            }
            Ok(answer)
        }
    }
    async fn assess_memory(
        &self,
        request: &MemoryAssessmentRequest,
    ) -> Result<MemoryAssessmentResponse, ModelError> {
        self.assessments
            .lock()
            .unwrap()
            .push(serde_json::to_value(request).unwrap());
        if let Some(pool) = &self.cancel {
            sqlx::query("UPDATE conversation_runs SET status='cancelled',lease_owner=NULL,lease_until=NULL WHERE status='running'").execute(pool).await.unwrap();
        }
        Ok(MemoryAssessmentResponse {
            assessment: MemoryAssessment {
                decision: self.policy.clone(),
                explanation: "Fixture policy only.".into(),
            },
            usage: ModelUsage {
                input_tokens: 7,
                output_tokens: 3,
            },
        })
    }
}
fn control(steps: Vec<SupervisorTool>, policy: MemoryDecision) -> ControlModel {
    ControlModel {
        steps,
        requests: Mutex::new(vec![]),
        policy,
        assessments: Mutex::new(vec![]),
        cancel: None,
    }
}
async fn remembered(f: &Fixture) -> MemoryRevision {
    drive(
        f,
        Arc::new(MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply)),
        "Remember my communication preference.",
    )
    .await;
    let memory = f.context.store.list_memories(f.id).await.unwrap().remove(0);
    MemoryRevision {
        id: memory.id,
        revision: memory.revision,
    }
}

#[tokio::test]
async fn conversational_forgetting_discards_old_reasoning_tools_and_manifest_then_finishes_mixed_request()
 {
    let f = fixture().await;
    let memory = remembered(&f).await;
    let model = Arc::new(control(
        vec![
            SupervisorTool::SearchMemory {
                workspace_id: None,
                session_id: None,
            },
            SupervisorTool::ForgetMemory {
                memory: memory.clone(),
            },
            SupervisorTool::ForgetMemory {
                memory: memory.clone(),
            },
            SupervisorTool::ReadAgentReport {
                process_id: f.process,
                offset: 0,
            },
        ],
        MemoryDecision::Apply,
    ));
    assert!(matches!(
        drive(
            &f,
            model.clone(),
            "Forget that preference, and tell me what the Android agent did."
        )
        .await,
        RunOutcome::Completed { .. }
    ));
    let requests = model.requests.lock().unwrap();
    assert!(!requests[0].preferences.is_empty());
    assert!(!requests[1].exchanges[0].continuation.0.is_empty());
    let fresh = &requests[2];
    assert!(fresh.exchanges.is_empty());
    assert!(fresh.preferences.is_empty());
    assert!(
        matches!(&fresh.effects[..],[TurnEffect::MemoryForgotten{memory:r}] if r.id==memory.id)
    );
    assert_eq!(
        requests[3].exchanges[0].result["data"]["already_recorded"],
        true
    );
    assert_eq!(model.assessments.lock().unwrap().len(), 1);
    assert_eq!(model.assessments.lock().unwrap()[0]["operation"], "forget");
    drop(requests);
    let exported = f.context.store.export(f.id).await.unwrap();
    let run = exported.runs.last().unwrap();
    assert_eq!(run.status, "completed");
    assert!(!run.context_manifest.contains("Leave routine"));
    assert!(!run.context_manifest.contains("search_memory"));
    assert!(!run.context_manifest.contains("discard-this-continuation"));
    assert_eq!(
        exported.evidence.last().unwrap().raw_report.as_deref(),
        Some(f.raw.as_str())
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
async fn conversational_rescope_refreshes_context_preserves_body_and_recovers_duplicate_receipt() {
    let f = fixture().await;
    let memory = remembered(&f).await;
    let scope = MemoryScope::Workspace(f.workspace);
    let step = SupervisorTool::RescopeMemory {
        memory: memory.clone(),
        scope: scope.clone(),
        entity_refs: vec![],
    };
    let model = Arc::new(control(
        vec![
            step.clone(),
            step,
            SupervisorTool::SearchMemory {
                workspace_id: Some(f.workspace),
                session_id: None,
            },
        ],
        MemoryDecision::Apply,
    ));
    assert!(matches!(
        drive(
            &f,
            model.clone(),
            "That preference should apply only to Android."
        )
        .await,
        RunOutcome::Completed { .. }
    ));
    assert_eq!(model.assessments.lock().unwrap().len(), 1);
    assert_eq!(model.assessments.lock().unwrap()[0]["operation"], "rescope");
    let requests = model.requests.lock().unwrap();
    assert!(requests[1].preferences.is_empty());
    assert!(requests[1].exchanges.is_empty());
    assert_eq!(
        requests[3].exchanges[0].result["data"]["memories"][0]["scope_id"],
        f.workspace.to_string()
    );
    drop(requests);
    let moved = f.context.store.list_memories(f.id).await.unwrap().remove(0);
    assert_eq!(moved.supersedes_id, Some(memory.id));
    assert_eq!(moved.revision, 2);
    assert!(
        f.context
            .store
            .memories(f.id, &[], 16384)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        f.context
            .store
            .memories(f.id, &[scope], 16384)
            .await
            .unwrap()[0]
            .id,
        moved.id
    );
}

#[tokio::test]
async fn forgetting_requires_explicit_assessment_current_revision_and_live_lease() {
    for decision in [
        MemoryDecision::Propose,
        MemoryDecision::Clarify,
        MemoryDecision::Decline,
    ] {
        let f = fixture().await;
        let memory = remembered(&f).await;
        let model = Arc::new(control(
            vec![SupervisorTool::ForgetMemory { memory }],
            decision,
        ));
        drive(&f, model.clone(), "What did I ask you to remember?").await;
        assert_eq!(f.context.store.list_memories(f.id).await.unwrap().len(), 1);
        assert!(model.requests.lock().unwrap()[1].effects.is_empty());
    }
    let f = fixture().await;
    let memory = remembered(&f).await;
    let stale = MemoryRevision {
        id: memory.id,
        revision: memory.revision + 1,
    };
    let model = Arc::new(control(
        vec![SupervisorTool::ForgetMemory { memory: stale }],
        MemoryDecision::Apply,
    ));
    drive(&f, model.clone(), "Forget the preference.").await;
    assert!(model.assessments.lock().unwrap().is_empty());
    assert_eq!(
        model.requests.lock().unwrap()[1].exchanges[0].result["error"],
        "memory_changed_reload"
    );
    let mut cancelled = control(
        vec![SupervisorTool::ForgetMemory { memory }],
        MemoryDecision::Apply,
    );
    cancelled.cancel = Some(f.pool.clone());
    assert_eq!(
        drive(&f, Arc::new(cancelled), "Forget the preference.").await,
        RunOutcome::Fenced
    );
    assert_eq!(f.context.store.list_memories(f.id).await.unwrap().len(), 1);
}

#[tokio::test]
async fn exact_selected_memory_controls_work_beyond_the_recent_settings_page() {
    let f = fixture().await;
    let old = remembered(&f).await;
    // Paging the settings view must not hide a selected claim from mutation.
    let source = f
        .context
        .store
        .current_memory(f.id, old.id)
        .await
        .unwrap()
        .unwrap()
        .source_message_id;
    for n in 0..200 {
        f.context
            .store
            .put_memory(
                f.id,
                &MemoryChange {
                    scope: MemoryScope::Workspace(f.workspace),
                    claim_key: format!("newer.{n}"),
                    body: "A workspace convention.".into(),
                    entity_refs: vec![],
                    source_message_id: source,
                    replaces: None,
                    explicit: true,
                    valid_until: None,
                },
            )
            .await
            .unwrap();
    }
    sqlx::query("UPDATE conversation_memory SET created_at='2000-01-01' WHERE id=?")
        .bind(old.id)
        .execute(&f.pool)
        .await
        .unwrap();
    assert!(
        !f.context
            .store
            .list_memories(f.id)
            .await
            .unwrap()
            .iter()
            .any(|m| m.id == old.id)
    );
    let mut correction = MemoryModel::new(MemoryScope::Global, MemoryDecision::Apply);
    correction.proposal.replaces = Some(old.clone());
    correction.proposal.body = "A corrected global preference.".into();
    assert!(matches!(
        drive(
            &f,
            Arc::new(correction),
            "Correct my global communication preference."
        )
        .await,
        RunOutcome::Completed { .. }
    ));
    let revised = f
        .context
        .store
        .memories(f.id, &[], 16384)
        .await
        .unwrap()
        .remove(0);
    sqlx::query("UPDATE conversation_memory SET created_at='2000-01-01' WHERE id=?")
        .bind(revised.id)
        .execute(&f.pool)
        .await
        .unwrap();
    let model = Arc::new(control(
        vec![SupervisorTool::ForgetMemory {
            memory: MemoryRevision {
                id: revised.id,
                revision: revised.revision,
            },
        }],
        MemoryDecision::Apply,
    ));
    assert!(matches!(
        drive(&f, model, "Forget my global preference.").await,
        RunOutcome::Completed { .. }
    ));
    assert!(
        f.context
            .store
            .memories(f.id, &[], 16384)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(
        f.context.store.list_memories(f.id).await.unwrap().len(),
        200
    );
}
