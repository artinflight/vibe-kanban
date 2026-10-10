use std::{path::Path, sync::Arc};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

#[cfg(not(feature = "qa-mode"))]
use crate::profile::ExecutorConfigs;
use crate::{
    actions::Executable,
    approvals::ExecutorApprovalService,
    env::ExecutionEnv,
    executors::{BaseCodingAgent, ExecutorError, SpawnedChild, StandardCodingAgentExecutor},
    profile::ExecutorConfig,
};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS)]
pub struct CodingAgentFollowUpRequest {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub capacity: Option<Box<crate::capacity::CapacityExecution>>,
    pub prompt: String,
    pub session_id: String,
    #[serde(default)]
    pub reset_to_message_id: Option<String>,
    /// Unified executor identity + overrides
    #[serde(alias = "executor_profile_id", alias = "profile_variant_label")]
    pub executor_config: ExecutorConfig,
    /// Optional relative path to execute the agent in (relative to container_ref).
    /// If None, uses the container_ref directory directly.
    #[serde(default)]
    pub working_dir: Option<String>,
}

impl CodingAgentFollowUpRequest {
    pub fn effective_dir(&self, current_dir: &Path) -> std::path::PathBuf {
        match &self.working_dir {
            Some(rel_path) => current_dir.join(rel_path),
            None => current_dir.to_path_buf(),
        }
    }

    pub fn base_executor(&self) -> BaseCodingAgent {
        self.executor_config.executor
    }
}

#[async_trait]
impl Executable for CodingAgentFollowUpRequest {
    #[cfg_attr(feature = "qa-mode", allow(unused_variables))]
    async fn spawn(
        &self,
        current_dir: &Path,
        approvals: Arc<dyn ExecutorApprovalService>,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        let effective_dir = self.effective_dir(current_dir);
        let mut execution_env = env.clone();
        if let Some(capacity) = &self.capacity {
            if self.base_executor() != BaseCodingAgent::Codex
                || self.prompt != "/goal resume"
                || self.reset_to_message_id.is_some()
            {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Capacity execution must resume an existing Codex goal",
                )));
            }
            let execution_id = env.get("VK_EXECUTION_PROCESS_ID").ok_or_else(|| {
                ExecutorError::Io(std::io::Error::other("Missing execution identity"))
            })?;
            // Hold the controller lock through lease creation: revocation must
            // not race a previously queued launch into creating fresh authority.
            if let Some(controller) = crate::capacity::controller::configured()? {
                let mut controller = controller.lock().await;
                let goal = controller
                    .state
                    .goals
                    .values()
                    .find(|g| {
                        g.grant
                            .as_ref()
                            .is_some_and(|grant| grant.id.to_string() == capacity.id)
                    })
                    .ok_or_else(|| std::io::Error::other("No durable launch identity"))?;
                if let Some(binding) = &goal.binding
                    && (env.get("VK_SESSION_ID").map(String::as_str)
                        != Some(goal.session_id.to_string().as_str())
                        || env.get("VK_WORKSPACE_ID").map(String::as_str)
                            != Some(binding.workspace_id.to_string().as_str())
                        || env
                            .repo_context
                            .workspace_root
                            .canonicalize()?
                            .to_string_lossy()
                            != binding.workspace_root
                        || self.working_dir != binding.agent_working_dir
                        || !effective_dir
                            .canonicalize()?
                            .starts_with(&binding.workspace_root))
                {
                    return Err(ExecutorError::Io(std::io::Error::other(
                        "Launcher session/workspace binding changed",
                    )));
                }
                goal.revalidate(
                    Some(uuid::Uuid::parse_str(execution_id).map_err(std::io::Error::other)?),
                    false,
                )
                .await?;
                controller.bind(
                    capacity,
                    &self.session_id,
                    uuid::Uuid::parse_str(execution_id).map_err(std::io::Error::other)?,
                    crate::capacity::wall_ms(),
                )?;
                execution_env.capacity = Some(capacity.prepare(execution_id)?);
            } else {
                return Err(ExecutorError::Io(std::io::Error::other(
                    "Scheduled launch requires its durable controller",
                )));
            }
        }
        let env = &execution_env;

        #[cfg(feature = "qa-mode")]
        {
            tracing::info!("QA mode: using mock executor for follow-up instead of real agent");
            let executor = crate::executors::qa_mock::QaMockExecutor;
            return executor
                .spawn_follow_up(
                    &effective_dir,
                    &self.prompt,
                    &self.session_id,
                    self.reset_to_message_id.as_deref(),
                    env,
                )
                .await;
        }

        #[cfg(not(feature = "qa-mode"))]
        {
            let profile_id = self.executor_config.profile_id();
            let mut agent = ExecutorConfigs::get_cached()
                .get_coding_agent(&profile_id)
                .ok_or(ExecutorError::UnknownExecutorType(profile_id.to_string()))?;

            if self.executor_config.has_overrides() {
                agent.apply_overrides(&self.executor_config);
            }
            agent.use_approvals(approvals.clone());

            agent
                .spawn_follow_up(
                    &effective_dir,
                    &self.prompt,
                    &self.session_id,
                    self.reset_to_message_id.as_deref(),
                    env,
                )
                .await
        }
    }
}
