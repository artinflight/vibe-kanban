//! Preparation for Google's separate ACP runtime. Never invokes the agy CLI.
use std::{path::Path, sync::Arc};

use async_trait::async_trait;
use derivative::Derivative;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use ts_rs::TS;
use workspace_utils::msg_store::MsgStore;

use crate::{
    approvals::ExecutorApprovalService,
    command::CommandParts,
    env::ExecutionEnv,
    executor_discovery::ExecutorDiscoveredOptions,
    executors::{
        AppendPrompt, AvailabilityInfo, BaseCodingAgent, ExecutorError, SpawnedChild,
        StandardCodingAgentExecutor, acp::AcpAgentHarness,
    },
    logs::utils::patch,
    model_selector::{ModelSelectorConfig, PermissionPolicy},
    profile::ExecutorConfig,
};

// Deliberately not configurable through profiles or environment variables. A future
// reviewed change must establish custom-client licensing, account/runtime support,
// supervised tool behavior and end-to-end verification before lifting this gate.
const ACTIVATION_VERIFIED: bool = false;
const GATE: &str = "Antigravity ACP preparation is disabled: supported account, custom-client permission, runtime and end-to-end validation are pending";

#[derive(Derivative, Default, Clone, Serialize, Deserialize, TS, JsonSchema)]
#[derivative(Debug, PartialEq)]
#[serde(deny_unknown_fields)]
#[schemars(
    description = "Unavailable preparation profile. Saving settings does not enable execution or authenticate an account."
)]
pub struct Antigravity {
    #[serde(default)]
    pub append_prompt: AppendPrompt,
    /// Absolute path to Google's separate agy_acp_server runtime; never agy CLI.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub executable: Option<String>,
    /// Exact ACP-advertised model ID. No guessed models or fallback substitutions.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(skip)]
    #[ts(skip)]
    #[derivative(Debug = "ignore", PartialEq = "ignore")]
    pub approvals: Option<Arc<dyn ExecutorApprovalService>>,
    #[serde(skip)]
    #[ts(skip)]
    unsupported_override: bool,
}

impl Antigravity {
    fn command(&self) -> Result<CommandParts, ExecutorError> {
        let path = self.executable.as_deref().unwrap_or("");
        if !Path::new(path).is_absolute() || !Path::new(path).is_file() {
            return Err(ExecutorError::ExecutableNotFound {
                program: path.into(),
            });
        }
        // Official ACP registry launch argument. No shell, installation or billing fallback.
        let args = if cfg!(target_os = "linux") {
            vec!["--uid=".into()]
        } else {
            vec![]
        };
        Ok(CommandParts::new(path.into(), args))
    }

    fn check_activation(&self) -> Result<(), ExecutorError> {
        if !ACTIVATION_VERIFIED {
            return Err(ExecutorError::AuthRequired(GATE.into()));
        }
        if self.unsupported_override
            || !self
                .approvals
                .as_ref()
                .is_some_and(|a| a.supports_interactive_approvals())
        {
            return Err(ExecutorError::AuthRequired("Antigravity requires interactive supervised approvals; mode and reasoning overrides are unsupported".into()));
        }
        Ok(())
    }

    async fn launch(
        &self,
        cwd: &Path,
        prompt: &str,
        session: Option<&str>,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        self.check_activation()?;
        let mut harness = AcpAgentHarness::with_session_namespace("antigravity-acp");
        if let Some(model) = &self.model {
            harness = harness.with_model(model);
        }
        harness
            .spawn_supervised_with_command(
                cwd,
                self.append_prompt.combine_prompt(prompt),
                session,
                self.command()?,
                env,
                self.approvals.clone(),
            )
            .await
    }
}

#[async_trait]
impl StandardCodingAgentExecutor for Antigravity {
    fn apply_overrides(&mut self, config: &ExecutorConfig) {
        if let Some(model) = &config.model_id {
            self.model = Some(model.clone());
        }
        self.unsupported_override = config
            .permission_policy
            .as_ref()
            .is_some_and(|p| *p != PermissionPolicy::Supervised)
            || config.agent_id.is_some()
            || config.reasoning_id.is_some();
    }
    fn use_approvals(&mut self, approvals: Arc<dyn ExecutorApprovalService>) {
        self.approvals = Some(approvals);
    }
    async fn spawn(
        &self,
        cwd: &Path,
        prompt: &str,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        self.launch(cwd, prompt, None, env).await
    }
    async fn spawn_follow_up(
        &self,
        cwd: &Path,
        prompt: &str,
        session_id: &str,
        reset_to_message_id: Option<&str>,
        env: &ExecutionEnv,
    ) -> Result<SpawnedChild, ExecutorError> {
        if reset_to_message_id.is_some() {
            return Err(ExecutorError::FollowUpNotSupported(
                "Antigravity ACP cannot reset or fork a conversation".into(),
            ));
        }
        self.launch(cwd, prompt, Some(session_id), env).await
    }
    fn normalize_logs(&self, store: Arc<MsgStore>, cwd: &Path) -> Vec<tokio::task::JoinHandle<()>> {
        crate::executors::acp::normalize_logs(store, cwd)
    }
    fn default_mcp_config_path(&self) -> Option<std::path::PathBuf> {
        None
    }
    fn get_availability_info(&self) -> AvailabilityInfo {
        // Neither an installed executable nor a credential-file timestamp proves
        // supported account access. Never probe credentials or start a process here.
        AvailabilityInfo::NotFound
    }
    fn get_preset_options(&self) -> ExecutorConfig {
        ExecutorConfig {
            executor: BaseCodingAgent::Antigravity,
            variant: None,
            model_id: self.model.clone(),
            agent_id: None,
            reasoning_id: None,
            permission_policy: Some(PermissionPolicy::Supervised),
            routing: None,
        }
    }
    async fn discover_options(
        &self,
        _workdir: Option<&Path>,
        _repo: Option<&Path>,
    ) -> Result<futures::stream::BoxStream<'static, json_patch::Patch>, ExecutorError> {
        let options = ExecutorDiscoveredOptions {
            model_selector: ModelSelectorConfig {
                permissions: vec![PermissionPolicy::Supervised],
                ..Default::default()
            },
            ..Default::default()
        };
        Ok(Box::pin(futures::stream::once(async move {
            patch::executor_discovered_options(options)
        })))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn antigravity_is_unavailable_and_cannot_launch() {
        let agent = Antigravity::default();
        assert!(matches!(
            agent.get_availability_info(),
            AvailabilityInfo::NotFound
        ));
        let env = ExecutionEnv::new(Default::default(), false, String::new());
        assert!(
            agent
                .spawn(Path::new("/"), "synthetic", &env)
                .await
                .unwrap_err()
                .to_string()
                .contains("preparation is disabled")
        );
        assert!(agent.command().is_err());
        assert!(serde_json::from_str::<Antigravity>(r#"{"enabled":true}"#).is_err());
    }
}
