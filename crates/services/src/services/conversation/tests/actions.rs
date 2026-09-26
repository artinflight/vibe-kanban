use std::{collections::HashSet, sync::atomic::AtomicUsize};

use db::models::{
    agent_delivery::AgentDelivery,
    conversation::actions::{MessageAssessment, MessageImpact},
};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::{BaseCodingAgent, codex::client::GoalMessageAdmission},
    profile::ExecutorConfig,
};

use super::*;
use crate::services::{
    container::ContainerError,
    conversation::{
        action_service::SupervisorActions,
        dispatch::AgentTransport,
        dispatch_gate::{DispatchBlock, DispatchGate, RuntimeState},
    },
};

struct Gates;
#[async_trait]
impl RuntimeState for Gates {
    fn approvals(&self, _: &[Uuid]) -> HashSet<Uuid> {
        HashSet::new()
    }
    async fn capacity_managed(&self, _: Uuid) -> Result<bool, DispatchBlock> {
        Ok(false)
    }
    async fn goal(&self, _: Uuid) -> Result<GoalMessageAdmission, DispatchBlock> {
        Ok(GoalMessageAdmission::Allowed)
    }
}
struct Transport(AtomicUsize);
#[async_trait]
impl AgentTransport for Transport {
    async fn steer(&self, delivery: AgentDelivery) -> Result<bool, ContainerError> {
        assert_eq!(delivery.data.message, "Web remains the source of truth.");
        self.0.fetch_add(1, Ordering::SeqCst);
        Ok(true)
    }
}
struct ActionModel {
    session: Uuid,
    impact: MessageImpact,
    authorised: bool,
    assessments: AtomicUsize,
    fail: bool,
    rename: Option<SqlitePool>,
    cancel: Option<(SqlitePool, Uuid)>,
}
#[async_trait]
impl ConversationModel for ActionModel {
    fn identity(&self) -> ModelIdentity {
        identity()
    }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        assert!(request.agent_actions);
        // Deliberately repeat the same intent with a different call ID: never
        // make its reworded tool identity into new permission to send again.
        if request.exchanges.len() < 2 {
            Ok(ModelResponse {
                continuation: ModelContinuation::default(),
                step: ModelStep::Tool {
                    call: ToolCall {
                        id: format!("propose-{}", request.exchanges.len()),
                        tool: SupervisorTool::ProposeAgentMessage {
                            message: "Web remains the source of truth.".into(),
                            sessions: vec![self.session],
                        },
                    },
                },
                usage: ModelUsage {
                    input_tokens: 1,
                    output_tokens: 1,
                },
            })
        } else {
            Ok(reply("The instruction status is available in activity."))
        }
    }
    async fn assess(&self, request: &AssessmentRequest) -> Result<AssessmentResponse, ModelError> {
        self.assessments.fetch_add(1, Ordering::SeqCst);
        assert_eq!(
            request.current_user_request,
            "Tell the Android agent that web remains the source of truth."
        );
        assert!(
            request
                .previous_user_requests
                .iter()
                .all(|s| !s.contains("attacker.invalid"))
        );
        assert_eq!(request.proposed.targets[0].session_id, self.session);
        if let Some((pool, id)) = &self.cancel {
            sqlx::query("UPDATE conversation_runs SET status='cancelled',generation=generation+1,lease_owner=NULL,lease_until=NULL WHERE conversation_id=?").bind(id).execute(pool).await.unwrap();
        }
        if let Some(pool) = &self.rename {
            sqlx::query("UPDATE workspaces SET branch='changed-while-assessing'")
                .execute(pool)
                .await
                .unwrap();
        }
        if self.fail {
            return Err(ModelError::Unavailable);
        }
        Ok(AssessmentResponse {
            assessment: MessageAssessment {
                authorised_by_user: self.authorised,
                impact: self.impact,
                recipients_explicit: true,
                explanation: "Assessment of user intent and the exact proposed message".into(),
            },
            usage: ModelUsage {
                input_tokens: 10,
                output_tokens: 2,
            },
        })
    }
}
async fn action_fixture() -> (Fixture, Arc<SupervisorActions>, Arc<Transport>) {
    let f = fixture().await;
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "raw initial".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
            working_dir: None,
        }),
        None,
    );
    sqlx::query("UPDATE execution_processes SET executor_action=?,status='running' WHERE id=?")
        .bind(sqlx::types::Json(action))
        .bind(f.process)
        .execute(&f.pool)
        .await
        .unwrap();
    let transport = Arc::new(Transport(AtomicUsize::new(0)));
    let gate = DispatchGate {
        pool: f.pool.clone(),
        runtime: Arc::new(Gates),
    };
    let actions = Arc::new(
        SupervisorActions::new(f.pool.clone(), gate, transport.clone())
            .await
            .unwrap(),
    );
    f.context
        .store
        .accept(
            f.id,
            &input("Tell the Android agent that web remains the source of truth."),
        )
        .await
        .unwrap();
    (f, actions, transport)
}
fn model(f: &Fixture, impact: MessageImpact, authorised: bool) -> ActionModel {
    ActionModel {
        session: f.session,
        impact,
        authorised,
        assessments: AtomicUsize::new(0),
        fail: false,
        rename: None,
        cancel: None,
    }
}

#[tokio::test]
async fn requested_ordinary_message_dispatches_once_without_confirmation_or_raw_chat_changes() {
    let (f, actions, transport) = action_fixture().await;
    let model = Arc::new(model(&f, MessageImpact::Ordinary, true));
    let worker = SupervisorWorker::new(f.pool.clone(), model.clone())
        .await
        .unwrap()
        .with_actions(actions);
    assert!(matches!(
        worker
            .run_one(f.id, &CancellationToken::new())
            .await
            .unwrap(),
        RunOutcome::Completed { .. }
    ));
    assert_eq!(transport.0.load(Ordering::SeqCst), 1);
    assert_eq!(model.assessments.load(Ordering::SeqCst), 1);
    assert!(
        f.context
            .store
            .confirmations(f.id)
            .await
            .unwrap()
            .is_empty()
    );
    let records = f.context.store.actions(f.id).await.unwrap();
    assert_eq!(records.len(), 1);
    let raw: String =
        sqlx::query_scalar("SELECT summary FROM coding_agent_turns WHERE execution_process_id=?")
            .bind(f.process)
            .fetch_one(&f.pool)
            .await
            .unwrap();
    assert_eq!(raw, f.raw);
}

#[tokio::test]
async fn consequential_instruction_waits_for_exact_confirmation_then_retries_only_receipts() {
    let (f, actions, transport) = action_fixture().await;
    let worker = SupervisorWorker::new(
        f.pool.clone(),
        Arc::new(model(&f, MessageImpact::Consequential, true)),
    )
    .await
    .unwrap()
    .with_actions(actions.clone());
    worker
        .run_one(f.id, &CancellationToken::new())
        .await
        .unwrap();
    assert_eq!(transport.0.load(Ordering::SeqCst), 0);
    let c = f.context.store.confirmations(f.id).await.unwrap().remove(0);
    let action = f
        .context
        .store
        .answer_confirmation(f.id, c.id, &c.payload_digest, c.action_revision, true)
        .await
        .unwrap();
    actions.dispatch(f.id, action.id).await.unwrap();
    actions.dispatch(f.id, action.id).await.unwrap();
    assert_eq!(transport.0.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn unrequested_instructions_and_dedicated_controls_never_get_confirmations_or_delivery() {
    for (impact, authorised) in [
        (MessageImpact::Ordinary, false),
        (MessageImpact::UnsupportedControl, true),
    ] {
        let (f, actions, transport) = action_fixture().await;
        let worker = SupervisorWorker::new(f.pool.clone(), Arc::new(model(&f, impact, authorised)))
            .await
            .unwrap()
            .with_actions(actions);
        worker
            .run_one(f.id, &CancellationToken::new())
            .await
            .unwrap();
        assert_eq!(transport.0.load(Ordering::SeqCst), 0);
        assert!(
            f.context
                .store
                .confirmations(f.id)
                .await
                .unwrap()
                .is_empty()
        );
        assert_eq!(
            f.context.store.actions(f.id).await.unwrap()[0].state,
            "rejected"
        );
    }
}

#[tokio::test]
async fn assessment_failure_or_user_cancellation_cannot_authorize_any_delivery() {
    for cancel in [false, true] {
        let (f, actions, transport) = action_fixture().await;
        let mut model = model(&f, MessageImpact::Ordinary, true);
        model.fail = !cancel;
        model.cancel = cancel.then(|| (f.pool.clone(), f.id));
        let worker = SupervisorWorker::new(f.pool.clone(), Arc::new(model))
            .await
            .unwrap()
            .with_actions(actions);
        let outcome = worker
            .run_one(f.id, &CancellationToken::new())
            .await
            .unwrap();
        assert!(matches!(
            outcome,
            RunOutcome::Fenced
                | RunOutcome::Failed {
                    code: "model_unavailable"
                }
        ));
        assert_eq!(transport.0.load(Ordering::SeqCst), 0);
        assert!(f.context.store.actions(f.id).await.unwrap().is_empty());
    }
}

#[tokio::test]
async fn a_target_change_during_assessment_cannot_turn_an_unfinalized_proposal_into_confirmation() {
    let (f, actions, transport) = action_fixture().await;
    let mut model = model(&f, MessageImpact::Ordinary, true);
    model.rename = Some(f.pool.clone());
    let worker = SupervisorWorker::new(f.pool.clone(), Arc::new(model))
        .await
        .unwrap()
        .with_actions(actions);
    assert!(matches!(
        worker
            .run_one(f.id, &CancellationToken::new())
            .await
            .unwrap(),
        RunOutcome::Completed { .. }
    ));
    assert_eq!(transport.0.load(Ordering::SeqCst), 0);
    assert!(
        f.context
            .store
            .confirmations(f.id)
            .await
            .unwrap()
            .is_empty()
    );
    let records = f.context.store.actions(f.id).await.unwrap();
    assert_eq!(records.len(), 1);
    assert!(
        f.context
            .store
            .action_deliveries(f.id, records[0].id)
            .await
            .unwrap()
            .is_empty()
    );
}
