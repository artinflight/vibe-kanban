//! User-intent assessment and execution for global supervisor message tools.
use std::sync::Arc;

use db::models::{
    agent_delivery::AgentDelivery,
    conversation::{
        ConversationError, ConversationRun, ConversationScope, ConversationStore,
        records::ConversationAction,
    },
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::SqlitePool;
use uuid::Uuid;

use super::{
    dispatch::{ActionDispatcher, AgentTransport, DispatchError},
    dispatch_gate::DispatchGate,
    model::{AssessmentRequest, ConversationModel, ModelError, ModelRequest, ModelUsage},
};

#[derive(Debug, thiserror::Error)]
pub enum ActionError {
    #[error(transparent)]
    Store(#[from] ConversationError),
    #[error(transparent)]
    Model(#[from] ModelError),
}

pub struct SupervisorActions {
    dispatcher: ActionDispatcher,
    transport: Arc<dyn AgentTransport>,
    pub(super) runtime: Arc<dyn super::dispatch_gate::RuntimeState>,
}
impl SupervisorActions {
    pub async fn new(
        pool: SqlitePool,
        gate: DispatchGate,
        transport: Arc<dyn AgentTransport>,
    ) -> Result<Self, ConversationError> {
        let store = ConversationStore::new(
            pool.clone(),
            ConversationScope::local_operator(&pool).await?,
        );
        Ok(Self {
            runtime: gate.runtime.clone(),
            dispatcher: ActionDispatcher::new(pool, store, gate),
            transport,
        })
    }
    pub async fn propose(
        &self,
        run: &ConversationRun,
        request: &ModelRequest,
        model: &dyn ConversationModel,
        message: &str,
        sessions: &[Uuid],
    ) -> Result<(Value, ModelUsage), ActionError> {
        let store = &self.dispatcher.store;
        store.renew(run).await?;
        let mut targets = sessions.to_vec();
        targets.sort();
        // Duplicate model calls within a turn cannot send the same instruction
        // twice by inventing a new function-call ID. Scope includes the user turn.
        let digest = Sha256::digest(
            serde_json::to_vec(&json!([run.id, message, targets]))
                .map_err(|_| ConversationError::InvalidRecord)?,
        );
        let key = Uuid::from_slice(&digest[..16]).map_err(|_| ConversationError::InvalidRecord)?;
        if let Some(action) = store.action_for_request(run.conversation_id, key).await? {
            // A target change/failure can leave the immutable proposal recorded
            // before policy finalization. It is not a pending human approval.
            if action.state == "proposed"
                && !store
                    .confirmations(run.conversation_id)
                    .await?
                    .iter()
                    .any(|c| c.action_id == action.id)
            {
                return Err(ConversationError::RevisionConflict.into());
            }
            return Ok((
                self.dispatch_or_read(run.conversation_id, &action).await?,
                ModelUsage::default(),
            ));
        }
        let proposed = store
            .prepare_agent_message(run.conversation_id, message.to_owned(), &targets)
            .await?;
        let assessment = model
            .assess(&AssessmentRequest {
                current_user_request: request.input.body.clone(),
                previous_user_requests: request
                    .history
                    .iter()
                    .filter(|m| m.role == "user")
                    .map(|m| m.body.clone())
                    .collect(),
                routing_context: request
                    .exchanges
                    .iter()
                    .filter(|e| {
                        matches!(
                            e.call.tool,
                            super::model::SupervisorTool::FindContext { .. }
                                | super::model::SupervisorTool::ReadWorkspaceState { .. }
                        )
                    })
                    .map(|e| e.result.clone())
                    .collect(),
                proposed: proposed.clone(),
            })
            .await?;
        let action = store
            .propose_agent_message(run, key, &proposed, &assessment.assessment)
            .await?;
        Ok((
            self.dispatch_or_read(run.conversation_id, &action).await?,
            assessment.usage,
        ))
    }
    pub async fn dispatch(&self, id: Uuid, action_id: Uuid) -> Result<Value, ConversationError> {
        let action = self.dispatcher.store.action(id, action_id).await?;
        self.dispatch_or_read(id, &action).await
    }
    async fn dispatch_or_read(
        &self,
        id: Uuid,
        action: &ConversationAction,
    ) -> Result<Value, ConversationError> {
        let mut blocked = None;
        if action.state == "approved" {
            match self
                .dispatcher
                .via_transport(id, action.id, self.transport.clone())
                .await
            {
                Ok(_) => {}
                Err(DispatchError::Blocked(reason)) => blocked = Some(reason.to_string()),
                Err(DispatchError::Store(error)) => return Err(error),
                Err(DispatchError::Database(error)) => return Err(error.into()),
            }
        }
        if let Some(reason) = &blocked {
            self.dispatcher
                .store
                .record_dispatch_block(id, action.id, reason)
                .await?;
        }
        let mut result = self.status(id, action.id).await?;
        result["blocked"] = json!(blocked);
        Ok(result)
    }
    pub async fn status(&self, id: Uuid, action_id: Uuid) -> Result<Value, ConversationError> {
        let store = &self.dispatcher.store;
        let action = store.reconcile_action(id, action_id).await?;
        let receipts = store.action_deliveries(id, action_id).await?;
        let blocked = store.dispatch_block(id, action_id).await?;
        let confirmations = store
            .confirmations(id)
            .await?
            .into_iter()
            .filter(|c| c.action_id == action_id)
            .collect::<Vec<_>>();
        Ok(
            json!({"observed_at":chrono::Utc::now(),"blocked":blocked,"data":{"action":action,"confirmations":confirmations,"deliveries":receipts.iter().map(delivery_receipt).collect::<Vec<_>>()}}),
        )
    }
}
pub fn delivery_receipt(d: &AgentDelivery) -> Value {
    json!({"id":d.id,"session_id":d.session_id,"workspace_id":d.workspace_id,"state":d.state,"delivery_mode":d.delivery_mode,"execution_process_id":d.execution_process_id,"acknowledged_at":d.steering_acknowledged_at,"error":d.error})
}
