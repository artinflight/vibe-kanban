//! Global supervisor run engine. Its read tools share VK's database; direct
//! workspace interaction continues through the existing session APIs.
use std::{collections::HashSet, sync::Arc, time::Duration};

use db::models::conversation::{
    ConversationError, ConversationRun, ConversationStore, records::MemoryScope,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::SqlitePool;
use tokio_util::sync::CancellationToken;
use uuid::Uuid;

pub mod action_service;
pub mod context;
pub mod dispatch;
pub mod dispatch_gate;
pub mod model;
pub mod openai;
pub mod runtime;

use context::LocalContext;
use model::{
    ConversationModel, INSTRUCTIONS, ModelRequest, ModelStep, ModelUsage, PROMPT_VERSION,
    ToolExchange,
};

const MAX_STEPS: usize = 12;
const TOOL_BUDGET: usize = 192 * 1024;

#[derive(Debug, PartialEq, Eq)]
pub enum RunOutcome {
    Idle,
    Completed { message_id: Uuid },
    Failed { code: &'static str },
    Fenced,
}

#[derive(Debug, thiserror::Error)]
enum WorkError {
    #[error(transparent)]
    Store(#[from] ConversationError),
    #[error("{0}")]
    Safe(&'static str),
}

/// Construction binds the service to the installation's local operator. A future
/// remote-authority service must supply its own authorised projection, not reuse
/// this constructor with caller-selected IDs.
pub struct SupervisorWorker {
    context: LocalContext,
    model: Arc<dyn ConversationModel>,
    worker_id: Uuid,
    heartbeat: Duration,
    deadline: Duration,
    actions: Option<Arc<action_service::SupervisorActions>>,
}

impl SupervisorWorker {
    pub async fn new(
        pool: SqlitePool,
        model: Arc<dyn ConversationModel>,
    ) -> Result<Self, ConversationError> {
        Ok(Self {
            context: LocalContext::new(pool).await?,
            model,
            worker_id: Uuid::new_v4(),
            heartbeat: Duration::from_secs(15),
            deadline: Duration::from_secs(120),
            actions: None,
        })
    }

    pub fn with_actions(mut self, actions: Arc<action_service::SupervisorActions>) -> Self {
        self.actions = Some(actions);
        self
    }

    /// Called by deployment-owned scheduling. Only durable pending runs can be
    /// claimed; multiple workers arbitrate through SQLite. A failed run never
    /// silently retries, and this engine never starts a native goal.
    pub async fn run_one(
        &self,
        conversation_id: Uuid,
        shutdown: &CancellationToken,
    ) -> Result<RunOutcome, ConversationError> {
        if shutdown.is_cancelled() {
            return Ok(RunOutcome::Idle);
        }
        let store = &self.context.store;
        let Some(run) = store.claim_next(conversation_id, self.worker_id).await? else {
            return Ok(RunOutcome::Idle);
        };
        let result = {
            let work = self.work(&run);
            tokio::pin!(work);
            // Poll lease renewal alongside work. Awaiting it inside a selected
            // timer branch can deadlock a one-connection pool if work currently
            // holds a transaction and is no longer being polled to release it.
            let keepalive = async {
                let mut interval = tokio::time::interval(self.heartbeat);
                interval.tick().await;
                loop {
                    interval.tick().await;
                    if let Err(error) = store.renew(&run).await {
                        break error;
                    }
                }
            };
            tokio::pin!(keepalive);
            tokio::select! {
                biased;
                _ = shutdown.cancelled() => Err(WorkError::Safe("worker_shutdown")),
                _ = tokio::time::sleep(self.deadline) => Err(WorkError::Safe("model_timeout")),
                result = &mut work => result,
                error = &mut keepalive => Err(WorkError::Store(error)),
            }
            // Dropping work drops the provider request before terminal persistence.
        };
        match result {
            Ok(message_id) => Ok(RunOutcome::Completed { message_id }),
            Err(WorkError::Store(ConversationError::StaleLease | ConversationError::NotFound)) => {
                Ok(RunOutcome::Fenced)
            }
            Err(error) => {
                let code = match error {
                    WorkError::Safe(code) => code,
                    WorkError::Store(_) => "context_unavailable",
                };
                match store.fail_run(&run, code).await {
                    Ok(()) => Ok(RunOutcome::Failed { code }),
                    Err(ConversationError::StaleLease | ConversationError::NotFound) => {
                        Ok(RunOutcome::Fenced)
                    }
                    Err(error) => Err(error),
                }
            }
        }
    }

    async fn work(&self, run: &ConversationRun) -> Result<Uuid, WorkError> {
        let store = &self.context.store;
        let identity = self.model.identity();
        if [&identity.provider, &identity.model]
            .iter()
            .any(|s| s.is_empty() || s.len() > 100)
        {
            return Err(WorkError::Safe("model_configuration_invalid"));
        }
        let mut request = ModelRequest {
            instructions: if self.actions.is_some() {
                model::ACTION_INSTRUCTIONS
            } else {
                INSTRUCTIONS
            },
            prompt_version: PROMPT_VERSION,
            agent_actions: self.actions.is_some(),
            input: store.run_input(run).await?,
            history: store.run_history(run).await?,
            preferences: store
                .memories(
                    run.conversation_id,
                    &[MemoryScope::Conversation(run.conversation_id)],
                    16384,
                )
                .await?,
            exchanges: Vec::new(),
        };
        let mut manifest = json!({"input_id":request.input.id,"input_revision":request.input.revision,
            "history":request.history.iter().map(|m|json!({"id":m.id,"revision":m.revision})).collect::<Vec<_>>(),
            "memories":request.preferences.iter().map(|m|json!({"id":m.id,"revision":m.revision})).collect::<Vec<_>>(),
            "tools":[]});
        let model = json!({"identity":identity,"prompt_version":PROMPT_VERSION,"options":self.model.options(),"agent_actions":self.actions.is_some()});
        let mut usage = ModelUsage::default();
        let mut call_ids = HashSet::new();
        let mut evidence_seen = HashSet::new();
        let mut tool_bytes = 0;
        let mut continuation_bytes = 0;
        persist(store, run, &manifest, &model, &usage).await?;
        for _ in 0..MAX_STEPS {
            store.renew(run).await?;
            let response = self.model.next(&request).await.map_err(|error| {
                WorkError::Safe(match error {
                    model::ModelError::Authentication => "model_authentication_failed",
                    model::ModelError::Refused => "model_refused",
                    model::ModelError::Unavailable => "model_unavailable",
                    model::ModelError::RateLimited => "model_rate_limited",
                    model::ModelError::InvalidResponse => "model_invalid_response",
                })
            })?;
            usage.input_tokens = usage
                .input_tokens
                .checked_add(response.usage.input_tokens)
                .ok_or(WorkError::Safe("model_invalid_usage"))?;
            usage.output_tokens = usage
                .output_tokens
                .checked_add(response.usage.output_tokens)
                .ok_or(WorkError::Safe("model_invalid_usage"))?;
            persist(store, run, &manifest, &model, &usage).await?;
            continuation_bytes += response
                .continuation
                .bytes()
                .map_err(|_| WorkError::Safe("model_invalid_response"))?;
            if continuation_bytes > 256 * 1024 {
                return Err(WorkError::Safe("context_budget_exceeded"));
            }
            match response.step {
                ModelStep::Reply { text, evidence_ids } => {
                    if text.trim().is_empty()
                        || text.len() > 65536
                        || evidence_ids.len() > 32
                        || evidence_ids.iter().any(|id| !evidence_seen.contains(id))
                    {
                        return Err(WorkError::Safe("model_invalid_response"));
                    }
                    let message = store
                        .complete_with_evidence(run, &text, &evidence_ids)
                        .await?;
                    return Ok(message.id);
                }
                ModelStep::Tool { call } => {
                    if call.id.is_empty()
                        || call.id.len() > 128
                        || !call_ids.insert(call.id.clone())
                    {
                        return Err(WorkError::Safe("model_invalid_tool_call"));
                    }
                    let executed = match &call.tool {
                        model::SupervisorTool::ProposeAgentMessage { message, sessions } => {
                            if let Some(actions) = &self.actions {
                                match actions
                                    .propose(run, &request, self.model.as_ref(), message, sessions)
                                    .await
                                {
                                    Ok((result, policy_usage)) => {
                                        usage.input_tokens = usage
                                            .input_tokens
                                            .checked_add(policy_usage.input_tokens)
                                            .ok_or(WorkError::Safe("model_invalid_usage"))?;
                                        usage.output_tokens = usage
                                            .output_tokens
                                            .checked_add(policy_usage.output_tokens)
                                            .ok_or(WorkError::Safe("model_invalid_usage"))?;
                                        Ok(result)
                                    }
                                    Err(action_service::ActionError::Store(error)) => Err(error),
                                    Err(action_service::ActionError::Model(error)) => {
                                        return Err(WorkError::Safe(model_failure(error)));
                                    }
                                }
                            } else {
                                Ok(json!({"error":"agent_actions_unavailable"}))
                            }
                        }
                        model::SupervisorTool::ReadAction { action_id } => {
                            if let Some(actions) = &self.actions {
                                actions.status(run.conversation_id, *action_id).await
                            } else {
                                Ok(json!({"error":"agent_actions_unavailable"}))
                            }
                        }
                        _ => self.context.execute(run, &call.tool).await,
                    };
                    let result = match executed {
                        Ok(result) => result,
                        Err(ConversationError::NotFound) => json!({"error":"source_unavailable"}),
                        Err(ConversationError::InvalidRecord) => {
                            json!({"error":"invalid_tool_arguments"})
                        }
                        Err(
                            ConversationError::RevisionConflict
                            | ConversationError::IdempotencyConflict,
                        ) => json!({"error":"action_changed_reconfirm_intent"}),
                        Err(error) => return Err(error.into()),
                    };
                    let encoded = serde_json::to_vec(&result)
                        .map_err(|_| WorkError::Safe("context_unavailable"))?;
                    tool_bytes += encoded.len();
                    if tool_bytes > TOOL_BUDGET {
                        return Err(WorkError::Safe("context_budget_exceeded"));
                    }
                    if let Some(id) = result["data"]["evidence_id"]
                        .as_str()
                        .and_then(|id| Uuid::parse_str(id).ok())
                    {
                        evidence_seen.insert(id);
                    }
                    manifest["tools"].as_array_mut().unwrap().push(json!({"call":call,
                        "result_hash":format!("{:x}",Sha256::digest(&encoded)),"observed_at":result["observed_at"],
                        "evidence_id":result["data"]["evidence_id"],"version":result["data"]["version"],
                        "source_revision":result["data"]["source_revision"],
                        "memories":result["data"]["memories"].as_array().map(|memories|memories.iter().map(|m|json!({"id":m["id"],"revision":m["revision"]})).collect::<Vec<_>>())}));
                    persist(store, run, &manifest, &model, &usage).await?;
                    request.exchanges.push(ToolExchange {
                        call,
                        result,
                        continuation: response.continuation,
                    });
                }
            }
        }
        Err(WorkError::Safe("model_tool_limit"))
    }
}

async fn persist(
    store: &ConversationStore,
    run: &ConversationRun,
    manifest: &Value,
    model: &Value,
    usage: &ModelUsage,
) -> Result<(), ConversationError> {
    store
        .record_run_context(run, manifest, model, &json!(usage))
        .await
}

#[cfg(test)]
mod tests;

fn model_failure(error: model::ModelError) -> &'static str {
    match error {
        model::ModelError::Authentication => "model_authentication_failed",
        model::ModelError::Refused => "model_refused",
        model::ModelError::Unavailable => "model_unavailable",
        model::ModelError::RateLimited => "model_rate_limited",
        model::ModelError::InvalidResponse => "model_invalid_response",
    }
}
