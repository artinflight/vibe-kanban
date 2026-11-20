//! Supervised Google's official ACP runtime. Never invokes the agy CLI.
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
    model_selector::{ModelInfo, ModelSelectorConfig, PermissionPolicy},
    profile::ExecutorConfig,
};

// Qualified on the official 1.4.1 runtime: personal auth, explicit default mode,
// model selection, AllowOnce, denial, native load and cancellation. No environment
// or profile can bypass supervised approval requirements. Installation discovery
// does not assert account access; every launch must authenticate successfully.
const ACTIVATION_VERIFIED: bool = true;
const GATE: &str = "Antigravity ACP execution is disabled pending native acceptance for this build";

pub const DEFAULT_ANTIGRAVITY_MODEL: &str = "gemini-3.8-flash-low";

pub const ANTIGRAVITY_MODELS: &[(&str, &str)] = &[
    ("gemini-4-argon-medium", "Gemini 4 Argon (Medium)"),
    ("gemini-4-argon-high", "Gemini 4 Argon (High)"),
    ("gemini-4-argon-low", "Gemini 4 Argon (Low)"),
    ("gemini-3.8-flash-high", "Gemini 3.8 Flash (High)"),
    ("gemini-3.8-flash-medium", "Gemini 3.8 Flash (Medium)"),
    ("gemini-3.8-flash-low", "Gemini 3.8 Flash (Low)"),
];

#[derive(Derivative, Default, Clone, Serialize, Deserialize, TS, JsonSchema)]
#[derivative(Debug, PartialEq)]
#[serde(deny_unknown_fields)]
#[schemars(
    description = "Supervised official ACP runtime. Requires an explicit executable and personal account authentication; saving settings does not authenticate an account."
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
        // A service-scoped default avoids rewriting saved profiles at deployment.
        // Explicit user profile values always win; an invalid value never falls back.
        let configured = self
            .executable
            .clone()
            .or_else(|| std::env::var("VK_ANTIGRAVITY_ACP_EXECUTABLE").ok());
        let path = configured.as_deref().unwrap_or("");
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

    fn selected_model(&self) -> Option<String> {
        self.model
            .as_deref()
            .map(str::trim)
            .filter(|model| !model.is_empty())
            .map(ToOwned::to_owned)
            .or_else(|| {
                std::env::var("VK_ANTIGRAVITY_ACP_MODEL")
                    .ok()
                    .map(|model| model.trim().to_owned())
                    .filter(|model| !model.is_empty())
            })
    }

    fn model_selector_models(&self) -> (Vec<ModelInfo>, Option<String>) {
        let selected_model = self.selected_model();
        let mut models: Vec<ModelInfo> = ANTIGRAVITY_MODELS
            .iter()
            .map(|(id, name)| ModelInfo {
                id: (*id).to_string(),
                name: (*name).to_string(),
                provider_id: None,
                reasoning_options: vec![],
            })
            .collect();
        if let Some(selected) = selected_model.as_deref()
            && !models
                .iter()
                .any(|model| model.id.eq_ignore_ascii_case(selected))
        {
            models.insert(
                0,
                ModelInfo {
                    id: selected.to_string(),
                    name: selected.to_string(),
                    provider_id: None,
                    reasoning_options: vec![],
                },
            );
        }
        let default_model =
            Some(selected_model.unwrap_or_else(|| DEFAULT_ANTIGRAVITY_MODEL.to_string()));
        (models, default_model)
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
        let mut harness =
            AcpAgentHarness::with_session_namespace("antigravity-acp").with_personal_auth();
        if let Some(model) = self.selected_model() {
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
        // Installation is distinct from authentication. Never inspect credentials
        // or start a process merely to render the executor selector.
        if ACTIVATION_VERIFIED && self.command().is_ok() {
            AvailabilityInfo::InstallationFound
        } else {
            AvailabilityInfo::NotFound
        }
    }
    fn get_preset_options(&self) -> ExecutorConfig {
        ExecutorConfig {
            executor: BaseCodingAgent::Antigravity,
            variant: None,
            model_id: self.selected_model(),
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
        let (models, default_model) = self.model_selector_models();
        let options = ExecutorDiscoveredOptions {
            model_selector: ModelSelectorConfig {
                models,
                default_model,
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
    use std::ffi::{OsStr, OsString};

    use futures::StreamExt;

    use super::*;

    struct EnvGuard {
        key: &'static str,
        previous: Option<OsString>,
    }

    impl EnvGuard {
        fn set(key: &'static str, value: Option<&OsStr>) -> Self {
            let previous = std::env::var_os(key);
            unsafe {
                match value {
                    Some(v) => std::env::set_var(key, v),
                    None => std::env::remove_var(key),
                }
            }
            Self { key, previous }
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            unsafe {
                match &self.previous {
                    Some(v) => std::env::set_var(self.key, v),
                    None => std::env::remove_var(self.key),
                }
            }
        }
    }

    async fn discovered_model_selector(agent: &Antigravity) -> ModelSelectorConfig {
        let mut stream = agent.discover_options(None, None).await.unwrap();
        let patch = stream.next().await.expect("discovery patch");
        let mut doc = serde_json::json!({ "options": null });
        json_patch::patch(&mut doc, &patch).unwrap();
        let options: ExecutorDiscoveredOptions =
            serde_json::from_value(doc["options"].clone()).unwrap();
        options.model_selector
    }
    #[tokio::test]
    async fn antigravity_unconfigured_or_without_approval_owner_cannot_launch() {
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
                .contains("interactive supervised approvals")
        );
        assert!(agent.command().is_err());
        assert!(serde_json::from_str::<Antigravity>(r#"{"enabled":true}"#).is_err());
    }

    #[test]
    fn antigravity_configured_installation_does_not_claim_authenticated() {
        let executable = tempfile::NamedTempFile::new().unwrap();
        let agent = Antigravity {
            executable: Some(executable.path().display().to_string()),
            ..Default::default()
        };
        assert!(matches!(
            agent.get_availability_info(),
            AvailabilityInfo::InstallationFound
        ));
        assert!(
            agent.check_activation().is_err(),
            "approval owner remains mandatory"
        );
    }

    #[tokio::test]
    async fn antigravity_discover_options_exposes_offered_models_and_preserves_selection() {
        let _env = EnvGuard::set(
            "VK_ANTIGRAVITY_ACP_MODEL",
            Some(OsStr::new("gemini-3.8-flash-low")),
        );

        let default_agent = Antigravity::default();
        assert_eq!(
            default_agent.get_preset_options().model_id.as_deref(),
            Some("gemini-3.8-flash-low")
        );
        let selector = discovered_model_selector(&default_agent).await;
        assert_eq!(
            selector.default_model.as_deref(),
            Some("gemini-3.8-flash-low")
        );
        let offered: Vec<(&str, &str)> = selector
            .models
            .iter()
            .map(|m| (m.id.as_str(), m.name.as_str()))
            .collect();
        assert_eq!(offered, ANTIGRAVITY_MODELS);
        assert!(
            selector
                .models
                .iter()
                .all(|m| m.reasoning_options.is_empty())
        );

        // Saved profile selection for a provider-offered model is preserved without duplication.
        let saved_agent = Antigravity {
            model: Some("gemini-4-argon-high".into()),
            ..Default::default()
        };
        assert_eq!(
            saved_agent.get_preset_options().model_id.as_deref(),
            Some("gemini-4-argon-high")
        );
        let saved_selector = discovered_model_selector(&saved_agent).await;
        assert_eq!(
            saved_selector.default_model.as_deref(),
            Some("gemini-4-argon-high")
        );
        assert_eq!(saved_selector.models.len(), ANTIGRAVITY_MODELS.len());

        // Saved custom model and explicit override remain selectable alongside offered models.
        let mut custom_agent = Antigravity {
            model: Some("gemini-custom-preview".into()),
            ..Default::default()
        };
        let custom_selector = discovered_model_selector(&custom_agent).await;
        assert_eq!(
            custom_selector.default_model.as_deref(),
            Some("gemini-custom-preview")
        );
        assert_eq!(custom_selector.models[0].id, "gemini-custom-preview");
        assert_eq!(custom_selector.models.len(), ANTIGRAVITY_MODELS.len() + 1);

        custom_agent.apply_overrides(&ExecutorConfig {
            executor: BaseCodingAgent::Antigravity,
            variant: None,
            model_id: Some("gemini-4-argon-medium".into()),
            agent_id: None,
            reasoning_id: None,
            permission_policy: Some(PermissionPolicy::Supervised),
            routing: None,
        });
        assert_eq!(
            custom_agent.get_preset_options().model_id.as_deref(),
            Some("gemini-4-argon-medium")
        );
    }
}
