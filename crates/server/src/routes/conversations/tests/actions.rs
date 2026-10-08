use std::{
    collections::HashSet,
    sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    },
    time::Duration,
};

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
use services::services::{
    container::ContainerError,
    conversation::{
        action_service::SupervisorActions,
        dispatch::AgentTransport,
        dispatch_gate::{DispatchBlock, DispatchGate, RuntimeState},
        model::*,
    },
};
use tokio_util::sync::CancellationToken;

use super::*;
struct Gates;
#[async_trait::async_trait]
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
#[async_trait::async_trait]
impl AgentTransport for Transport {
    async fn steer(&self, _: AgentDelivery) -> Result<bool, ContainerError> {
        self.0.fetch_add(1, Ordering::SeqCst);
        Ok(true)
    }
}
struct Model(Uuid);
#[async_trait::async_trait]
impl ConversationModel for Model {
    fn identity(&self) -> ModelIdentity {
        ModelIdentity {
            provider: "fixture".into(),
            model: "confirmation-api".into(),
        }
    }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        Ok(ModelResponse {
            continuation: ModelContinuation::default(),
            usage: ModelUsage::default(),
            step: if request.exchanges.is_empty() {
                ModelStep::Tool {
                    call: ToolCall {
                        id: "proposal".into(),
                        tool: SupervisorTool::ProposeAgentMessage {
                            message: "Deploy the approved Android change.".into(),
                            sessions: vec![self.0],
                        },
                    },
                }
            } else {
                ModelStep::Reply {
                    text: "Please review the deployment instruction.".into(),
                    evidence_ids: vec![],
                }
            },
        })
    }
    async fn assess(&self, _: &AssessmentRequest) -> Result<AssessmentResponse, ModelError> {
        Ok(AssessmentResponse {
            assessment: MessageAssessment {
                authorised_by_user: true,
                impact: MessageImpact::Consequential,
                recipients_explicit: true,
                explanation: "The deployment is consequential.".into(),
            },
            usage: ModelUsage::default(),
        })
    }
}
#[tokio::test]
async fn api_user_message_creates_review_and_bound_confirmation_dispatches_once_across_retries() {
    let (pool, _) = fixture(false).await;
    let (workspace, session, process) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
    sqlx::query("INSERT INTO workspaces(id,name,branch) VALUES (?,'Android','mobile/parity')")
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
            prompt: "raw".into(),
            executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
            working_dir: None,
        }),
        None,
    );
    sqlx::query("INSERT INTO execution_processes(id,session_id,executor_action,run_reason,status) VALUES (?,?,?,'codingagent','running')").bind(process).bind(session).bind(sqlx::types::Json(action)).execute(&pool).await.unwrap();
    let transport = Arc::new(Transport(AtomicUsize::new(0)));
    let actions = Arc::new(
        SupervisorActions::new(
            pool.clone(),
            DispatchGate::with_runtime(pool.clone(), Arc::new(Gates)),
            transport.clone(),
        )
        .await
        .unwrap(),
    );
    let stop = CancellationToken::new();
    let runtime = SupervisorRuntime::start_with_actions(
        pool.clone(),
        Arc::new(Model(session)),
        stop.clone(),
        Some(actions),
    )
    .await
    .unwrap();
    let router: Router = api_router(ConversationApiState {
        pool: pool.clone(),
        enabled: true,
        readiness: SupervisorReadiness::Worker(runtime),
    });
    let (_, resolved) = call(&router, "POST", "/conversations/resolve", json!({})).await;
    assert_eq!(resolved["data"]["capabilities"]["agent_actions"], true);
    let id = resolved["data"]["conversation"]["id"].as_str().unwrap();
    call(&router,"POST",&format!("/conversations/{id}/messages"),json!({"client_message_id":Uuid::new_v4(),"body":"Ask the Android agent to deploy the change.","origin":"typed","reply_to_id":null})).await;
    let confirmations = tokio::time::timeout(Duration::from_secs(10), async {
        loop {
            let (_, response) = call(
                &router,
                "GET",
                &format!("/conversations/{id}/confirmations"),
                json!({}),
            )
            .await;
            if response["data"].as_array().is_some_and(|v| !v.is_empty()) {
                break response["data"].clone();
            }
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .unwrap();
    assert_eq!(transport.0.load(Ordering::SeqCst), 0);
    let c = &confirmations[0];
    let path = format!(
        "/conversations/{id}/confirmations/{}",
        c["id"].as_str().unwrap()
    );
    let answer = json!({"payload_digest":c["payload_digest"],"action_revision":c["action_revision"],"accept":true});
    let mut invalid = answer.clone();
    invalid["payload_digest"] = json!("changed");
    assert_eq!(
        call(&router, "POST", &path, invalid).await.0,
        StatusCode::CONFLICT
    );
    let mut forge = answer.clone();
    forge["message"] = json!("different instruction");
    let forged = Request::builder()
        .method("POST")
        .uri(&path)
        .header("content-type", "application/json")
        .body(Body::from(forge.to_string()))
        .unwrap();
    assert_eq!(
        router.clone().oneshot(forged).await.unwrap().status(),
        StatusCode::UNPROCESSABLE_ENTITY
    );
    for _ in 0..2 {
        let (status, result) = call(&router, "POST", &path, answer.clone()).await;
        assert_eq!(status, StatusCode::OK, "{result}");
        assert_eq!(
            result["data"]["message"]["message"],
            "Deploy the approved Android change."
        );
        assert_eq!(
            result["data"]["deliveries"][0]["execution_process_id"],
            process.to_string()
        );
        assert!(result["data"]["deliveries"][0].get("claim_id").is_none());
    }
    assert_eq!(transport.0.load(Ordering::SeqCst), 1);
    // A signed relay is still not the local supervisor's owner.
    let mut request = Request::builder()
        .method("POST")
        .uri(&path)
        .header("content-type", "application/json")
        .body(Body::from(answer.to_string()))
        .unwrap();
    request
        .extensions_mut()
        .insert(RelayRequestSignatureContext {
            signing_session_id: Uuid::new_v4(),
            timestamp: 1,
            nonce: Uuid::new_v4(),
            signature_b64: "verified transport only".into(),
        });
    assert_eq!(
        router.clone().oneshot(request).await.unwrap().status(),
        StatusCode::FORBIDDEN
    );
    stop.cancel();
    assert_eq!(call(&router, "POST", &path, answer).await.0, StatusCode::OK);
    assert_eq!(transport.0.load(Ordering::SeqCst), 1);
}

struct MessageAndForget {
    session: Uuid,
    memory: MemoryRevision,
    step: AtomicUsize,
}
#[async_trait::async_trait]
impl ConversationModel for MessageAndForget {
    fn identity(&self) -> ModelIdentity { Model(self.session).identity() }
    fn supports_memory_changes(&self) -> bool { true }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        let tool = match self.step.fetch_add(1, Ordering::SeqCst) {
            0 => SupervisorTool::ProposeAgentMessage {message:"Web remains the source of truth for onboarding.".into(),sessions:vec![self.session]},
            1 => SupervisorTool::ForgetMemory { memory:self.memory.clone() },
            2 => {
                assert!(request.exchanges.is_empty());
                assert!(request.preferences.is_empty());
                assert!(request.effects.iter().any(|e|matches!(e,TurnEffect::MemoryForgotten{..})));
                let action_id=request.effects.iter().find_map(|e|match e { TurnEffect::AgentAction{action_id}=>Some(*action_id),_=>None }).expect("The completed instruction must survive the memory-context reset");
                SupervisorTool::ReadAction{action_id}
            },
            _ => {
                assert_eq!(request.exchanges[0].result["data"]["deliveries"][0]["state"],"acknowledged");
                return Ok(ModelResponse{continuation:ModelContinuation::default(),usage:ModelUsage::default(),step:ModelStep::Reply{text:"I sent the Android instruction and forgot that preference.".into(),evidence_ids:vec![]}});
            }
        };
        Ok(ModelResponse{continuation:ModelContinuation::default(),usage:ModelUsage::default(),step:ModelStep::Tool{call:ToolCall{id:format!("mixed_{}",self.step.load(Ordering::SeqCst)),tool}}})
    }
    async fn assess(&self, _: &AssessmentRequest)->Result<AssessmentResponse,ModelError> {
        Ok(AssessmentResponse{assessment:MessageAssessment{authorised_by_user:true,impact:MessageImpact::Ordinary,recipients_explicit:true,explanation:"Fixture: explicit scoped instruction.".into()},usage:ModelUsage::default()})
    }
    async fn assess_memory(&self, request:&MemoryAssessmentRequest)->Result<MemoryAssessmentResponse,ModelError> {
        assert!(matches!(request.operation,MemoryOperation::Forget));
        Ok(MemoryAssessmentResponse{assessment:MemoryAssessment{decision:MemoryDecision::Apply,explanation:"Fixture: explicit forgetting request.".into()},usage:ModelUsage::default()})
    }
}

#[tokio::test]
async fn dispatched_instruction_receipt_survives_forgetting_without_sending_again() {
    use db::models::conversation::records::{MemoryChange,MemoryScope};
    use services::services::conversation::{RunOutcome,SupervisorWorker};
    let (pool, _) = fixture(false).await;
    let (workspace,session,process)=(Uuid::new_v4(),Uuid::new_v4(),Uuid::new_v4());
    sqlx::query("INSERT INTO workspaces(id,name,branch) VALUES (?,'Android','mobile/parity')").bind(workspace).execute(&pool).await.unwrap();
    sqlx::query("INSERT INTO sessions(id,workspace_id,executor) VALUES (?,?,'CODEX')").bind(session).bind(workspace).execute(&pool).await.unwrap();
    let action=ExecutorAction::new(ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest{prompt:"raw".into(),executor_config:ExecutorConfig::new(BaseCodingAgent::Codex),working_dir:None}),None);
    sqlx::query("INSERT INTO execution_processes(id,session_id,executor_action,run_reason,status) VALUES (?,?,?,'codingagent','running')").bind(process).bind(session).bind(sqlx::types::Json(action)).execute(&pool).await.unwrap();
    let store=ConversationStore::new(pool.clone(),ConversationScope::local_operator(&pool).await.unwrap());
    let id=store.resolve().await.unwrap().id;
    let input=|body:&str|AcceptConversationMessage{client_message_id:Uuid::new_v4(),body:body.into(),origin:ConversationInputOrigin::Typed,reply_to_id:None};
    let first=store.accept(id,&input("Remember my communication preference.")).await.unwrap();
    let memory=store.put_memory(id,&MemoryChange{scope:MemoryScope::Global,claim_key:"communication".into(),body:"Only brief updates.".into(),entity_refs:vec![],source_message_id:first.message.id,replaces:None,explicit:true,valid_until:None}).await.unwrap();
    let run=store.claim_next(id,Uuid::new_v4()).await.unwrap().unwrap();
    store.complete(&run,"Remembered.").await.unwrap();
    store.accept(id,&input("Tell Android web remains the source of truth for onboarding, then forget my communication preference.")).await.unwrap();
    let transport=Arc::new(Transport(AtomicUsize::new(0)));
    let actions=Arc::new(SupervisorActions::new(pool.clone(),DispatchGate::with_runtime(pool.clone(),Arc::new(Gates)),transport.clone()).await.unwrap());
    let worker=SupervisorWorker::new(pool.clone(),Arc::new(MessageAndForget{session,memory:MemoryRevision{id:memory.id,revision:memory.revision},step:AtomicUsize::new(0)})).await.unwrap().with_actions(Some(actions));
    assert!(matches!(worker.run_one(id,&CancellationToken::new()).await.unwrap(),RunOutcome::Completed{..}));
    assert_eq!(transport.0.load(Ordering::SeqCst),1);
    let exported=store.export(id).await.unwrap();
    assert_eq!(exported.actions.len(),1);
    assert_eq!(exported.deliveries.len(),1);
    assert!(store.list_memories(id).await.unwrap().is_empty());
}
