//! Deployment-owned worker lifecycle. Readiness follows the actual consumer,
//! never merely an environment flag. SQLite remains the queue/recovery authority.
use std::{sync::Arc, time::Duration};

use db::models::conversation::ConversationError;
use sqlx::SqlitePool;
use tokio::{sync::Notify, task::JoinHandle};
use tokio_util::sync::CancellationToken;

use super::{RunOutcome, SupervisorWorker, model::ConversationModel, openai::OpenAiModel};

#[derive(Clone)]
pub struct SupervisorRuntime(Arc<Runtime>);
struct Runtime {
    enabled: bool,
    actions: Option<Arc<super::action_service::SupervisorActions>>,
    shutdown: CancellationToken,
    wake: Arc<Notify>,
    task: Option<JoinHandle<()>>,
}
impl Drop for Runtime {
    fn drop(&mut self) {
        self.shutdown.cancel();
        // A dropped deployment must not leave a detached model request running.
        // If shutdown persistence cannot finish, lease recovery records interruption.
        if let Some(task) = &self.task {
            task.abort();
        }
    }
}
impl SupervisorRuntime {
    pub fn unavailable(enabled: bool) -> Self {
        Self(Arc::new(Runtime {
            enabled,
            actions: None,
            shutdown: CancellationToken::new(),
            wake: Arc::new(Notify::new()),
            task: None,
        }))
    }
    pub async fn from_environment(
        pool: SqlitePool,
        shutdown: CancellationToken,
        gate: super::dispatch_gate::DispatchGate,
        transport: Arc<dyn super::dispatch::AgentTransport>,
    ) -> Self {
        let enabled = std::env::var("VK_SUPERVISOR_ENABLED").is_ok_and(|s| s == "1");
        if !enabled {
            return Self::unavailable(false);
        }
        let model = match OpenAiModel::from_environment().await {
            Ok(model) => model,
            Err(_) => {
                tracing::warn!(
                    "Supervisor model configuration is missing or invalid; history remains available"
                );
                return Self::unavailable(true);
            }
        };
        let actions = match super::action_service::SupervisorActions::new(
            pool.clone(),
            gate,
            transport,
        )
        .await
        {
            Ok(actions) => Arc::new(actions),
            Err(_) => return Self::unavailable(true),
        };
        match Self::start_with_actions(pool, Arc::new(model), shutdown, Some(actions)).await {
            Ok(runtime) => runtime,
            Err(_) => {
                tracing::error!(
                    "Supervisor worker could not initialize; history remains available"
                );
                Self::unavailable(true)
            }
        }
    }
    pub async fn start(
        pool: SqlitePool,
        model: Arc<dyn ConversationModel>,
        shutdown: CancellationToken,
    ) -> Result<Self, ConversationError> {
        Self::start_with_actions(pool, model, shutdown, None).await
    }
    pub async fn start_with_actions(
        pool: SqlitePool,
        model: Arc<dyn ConversationModel>,
        shutdown: CancellationToken,
        actions: Option<Arc<super::action_service::SupervisorActions>>,
    ) -> Result<Self, ConversationError> {
        let mut worker = SupervisorWorker::new(pool, model).await?;
        if let Some(actions) = &actions {
            worker = worker.with_actions(actions.clone());
        }
        let id = worker.context.store.resolve().await?.id;
        let wake = Arc::new(Notify::new());
        let task_wake = wake.clone();
        let task_shutdown = shutdown.clone();
        let task = tokio::spawn(async move {
            loop {
                if task_shutdown.is_cancelled() {
                    break;
                }
                match worker.run_one(id, &task_shutdown).await {
                    Ok(RunOutcome::Completed { .. } | RunOutcome::Fenced) => continue,
                    Ok(RunOutcome::Failed {
                        code: "model_authentication_failed",
                    }) => {
                        tracing::warn!(
                            "Supervisor credential was rejected; message acceptance stopped"
                        );
                        break;
                    }
                    Ok(RunOutcome::Failed { .. }) => continue,
                    Ok(RunOutcome::Idle) => {}
                    Err(_) => {
                        // Stop accepting rather than accumulating work with a dead
                        // consumer. Operator restart repairs the persistent lease.
                        tracing::error!("Supervisor worker stopped after a persistence failure");
                        break;
                    }
                }
                tokio::select! {
                    _=task_shutdown.cancelled()=>break,
                    _=task_wake.notified()=>{},
                    _=tokio::time::sleep(Duration::from_millis(500))=>{},
                }
            }
        });
        Ok(Self(Arc::new(Runtime {
            enabled: true,
            actions,
            shutdown,
            wake,
            task: Some(task),
        })))
    }
    pub fn enabled(&self) -> bool {
        self.0.enabled
    }
    pub fn accepting_messages(&self) -> bool {
        self.0.enabled
            && !self.0.shutdown.is_cancelled()
            && self.0.task.as_ref().is_some_and(|task| !task.is_finished())
    }
    pub fn actions(&self) -> Option<&Arc<super::action_service::SupervisorActions>> {
        self.accepting_messages()
            .then_some(self.0.actions.as_ref())
            .flatten()
    }
    pub fn wake(&self) {
        self.0.wake.notify_one();
    }
}

#[cfg(test)]
mod tests;
