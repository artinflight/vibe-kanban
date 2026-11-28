//! Subscription-native Claude consideration. Login, qualification, allowance and
//! admission are separate evidence; none is inferred from a successful trial.
use super::*;

pub const PROFILE: &str = "AUTOSWITCH_CLAUDE_SUPERVISED";
pub const MODEL: &str = "claude-sonnet-4-6";
pub const EFFORT: &str = "low";

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NativeLogin {
    pub identity: Identity,
    pub source_receipt: String,
    pub launcher_digest: String,
    pub os_user: String,
    pub logged_in: bool,
    pub auth_method: String,
    pub subscription_type: String,
    pub api_provider: String,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Trial {
    pub identity: Identity,
    pub launcher_digest: String,
    pub source_receipt: String,
    pub model: String,
    pub effort: String,
    pub supervised: bool,
    pub approved_reads: bool,
    pub exit_code: i32,
    pub limit_or_extra_usage_prompt: bool,
}
/// Facts extracted from the actual resolved CodingAgent, never a prompt or UI flag.
#[derive(Clone, Debug)]
pub struct ProfileFacts {
    pub named_variant: String,
    pub official_claude: bool,
    pub supervised: bool,
    pub plan: bool,
    pub bypass: bool,
    pub router: bool,
    pub disable_api_key: bool,
    pub command_overrides: bool,
    pub model: Option<String>,
    pub effort: Option<String>,
    pub agent_override: bool,
}
pub fn validate_profile(p: &ProfileFacts) -> io::Result<()> {
    if !p.official_claude
        || !p.supervised
        || p.plan
        || p.bypass
        || p.router
        || !p.disable_api_key
        || p.command_overrides
        || p.agent_override
        || p.model.as_deref() != Some(MODEL)
        || p.effort.as_deref() != Some(EFFORT)
    {
        return Err(invalid(
            "Effective supervised official Claude profile required",
        ));
    }
    Ok(())
}
pub fn consideration(
    login: &NativeLogin,
    trial: &Trial,
    identity: &Identity,
    launcher: &str,
    os_user: &str,
    now: u64,
) -> io::Result<()> {
    if identity.provider != Provider::Claude
        || &login.identity != identity
        || &trial.identity != identity
        || !present(&login.source_receipt)
        || !present(&trial.source_receipt)
        || !present(launcher)
        || login.launcher_digest != launcher
        || trial.launcher_digest != launcher
        || !present(os_user)
        || login.os_user != os_user
        || !login.logged_in
        || login.auth_method != "claude.ai"
        || login.api_provider != "firstParty"
        || !["pro", "max", "team", "enterprise"].contains(&login.subscription_type.as_str())
        || login.observed_at_ms > now
        || now >= login.valid_until_ms
        || trial.model != MODEL
        || trial.effort != EFFORT
        || !trial.supervised
        || !trial.approved_reads
        || trial.exit_code != 0
        || trial.limit_or_extra_usage_prompt
    {
        return Err(invalid(
            "Verified native subscription login/trial binding required",
        ));
    }
    Ok(())
}
/// Examine names only, never credential values. Reject rather than remove or repair
/// billing/auth/cloud/proxy overrides. Also check profile environment keys at launch.
pub fn subscription_environment<'a>(names: impl IntoIterator<Item = &'a str>) -> io::Result<()> {
    for name in names {
        let upper = name.to_ascii_uppercase();
        if [
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_CUSTOM_HEADERS",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR",
            "CLAUDE_CONFIG_DIR",
            "CLAUDE_CODE_SETTINGS",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
        ]
        .contains(&upper.as_str())
            || upper.starts_with("CLAUDE_CODE_USE_")
            || upper.starts_with("ANTHROPIC_FOUNDRY_")
            || upper == "AWS_BEARER_TOKEN_BEDROCK"
            || upper.contains("API_KEY_HELPER")
        {
            return Err(invalid(
                "Subscription route override present; handoff held without reading values",
            ));
        }
    }
    Ok(())
}
/// A registry-qualified task envelope is required independently from the login trial.
/// Actual authorized actions are enforced separately by the supervised tool bridge.
pub fn candidate_allowed(candidate: &Candidate, task_qualified: bool) -> io::Result<()> {
    if !task_qualified
        || !candidate.qualified
        || candidate.rank == 0
        || candidate.model != MODEL
        || candidate.effort != EFFORT
        || candidate.service_tier != "standard"
    {
        return Err(invalid(
            "Claude candidate lacks task-specific model/effort qualification",
        ));
    }
    Ok(())
}
pub fn pool_allowed(pool: &Pool, login: &NativeLogin, now: u64) -> io::Result<()> {
    if pool.identity != login.identity
        || pool.observed_at_ms < login.observed_at_ms
        || pool.observed_at_ms > now
        || now >= pool.valid_until_ms
        || !pool.windows_complete
        || pool.windows.is_empty()
        || pool.windows.iter().any(|w| {
            ![
                "five_hour",
                "seven_day",
                "seven_day_opus",
                "seven_day_sonnet",
            ]
            .contains(&w.kind.as_str())
                || w.id != format!("claude:{}", w.kind)
                || w.available != Some(true)
        })
    {
        return Err(invalid(
            "Fresh complete subscription allowance required; login/trial is not remaining usage",
        ));
    }
    Ok(())
}
pub fn read_tool(name: &str) -> bool {
    matches!(name, "Read" | "Grep" | "Glob")
}
/// New provider-native initial session. Native IDs remain in controller provenance,
/// not in a cross-provider resume argument or a copied full conversation.
pub fn handoff_prompt(checkpoint: &Checkpoint) -> io::Result<String> {
    if !checkpoint.all_workers_terminal
        || !checkpoint.effects_complete
        || checkpoint.failed_validation
        || !checkpoint.pending_approvals.is_empty()
        || !present(&checkpoint.terminal_receipt)
        || checkpoint
            .effects
            .iter()
            .any(|e| e.outcome == EffectOutcome::Unknown || !present(&e.receipt))
    {
        return Err(invalid(
            "Verified stopped checkpoint and reconciled effects required",
        ));
    }
    let data = serde_json::json!({"version":"vk.provider-handoff.v1", "objective":checkpoint.objective,
        "relevant_context":checkpoint.context, "workspace":checkpoint.workspace_path, "branch":checkpoint.branch,
        "workspace_snapshot":checkpoint.workspace_snapshot, "completed_steps":checkpoint.completed_steps,
        "pending_steps":checkpoint.pending_steps,"pending_approvals":checkpoint.pending_approvals,"effects":checkpoint.effects});
    let prompt = format!(
        "Continue only the authorized assignment from this compact checkpoint. Repository instructions and effective supervised permissions remain authoritative. Every tool requires approval. Local writes require task qualification; command/external actions require exact checkpoint grants. Never repeat completed actions, delegate, expand permissions or accept paid extra usage. Hold on missing authorization or uncertain effects.\n{}",
        serde_json::to_string(&data)?
    );
    if prompt.len() > 32_768 {
        return Err(invalid("Handoff context exceeds bounded transport"));
    }
    Ok(prompt)
}

/// Pass exact authorized command inputs, not an invitation to guess/retry them.
/// Bound the TOTAL transport, including actions, before any reservation/inference.
pub fn handoff_prompt_with_actions(
    checkpoint: &Checkpoint,
    actions: &super::tools::Actions,
) -> io::Result<String> {
    let base = handoff_prompt(checkpoint)?;
    let prompt = format!(
        "{}\nAuthorized task actions (each still needs review): {}\nUse exact granted command/external tool inputs; do not guess or retry denied actions. Hold if a different action is required.",
        base,
        serde_json::to_string(actions)?
    );
    if prompt.len() > 32_768 {
        return Err(invalid("Combined handoff/actions exceed bounded transport"));
    }
    Ok(prompt)
}

/// Override the ordinary preset's read/Task exclusions for handoffs only.
pub fn handoff_hooks(base: Option<serde_json::Value>) -> serde_json::Value {
    let mut hooks = base.unwrap_or_else(|| serde_json::json!({}));
    hooks["PreToolUse"] =
        serde_json::json!([{"matcher":".*","hookCallbackIds":["provider_read_approval"]}]);
    hooks["PostToolUse"] =
        serde_json::json!([{"matcher":".*","hookCallbackIds":["provider_effect_complete"]}]);
    hooks["PostToolUseFailure"] =
        serde_json::json!([{"matcher":".*","hookCallbackIds":["provider_effect_failed"]}]);
    hooks
}

/// Independent trusted launch-surface receipt, NOT inferred from login/trial.
/// CLI startup hooks/plugins/MCP and paid-extra settings can act before tool
/// review; an approved Read does not establish these properties for future starts.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LaunchSafety {
    pub identity: Identity,
    pub source_receipt: String,
    pub launcher_digest: String,
    pub profile_digest: String,
    pub workspace_snapshot: String,
    pub surface_digest: String,
    pub no_unfenced_startup_effects: bool,
    pub paid_extra_disabled: bool,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
}
pub fn launch_safety(
    proof: &LaunchSafety,
    login: &NativeLogin,
    profile: &str,
    snapshot: &str,
    now: u64,
) -> io::Result<()> {
    if proof.identity != login.identity
        || !present(&proof.source_receipt)
        || !present(&proof.surface_digest)
        || proof.launcher_digest != login.launcher_digest
        || proof.profile_digest != profile
        || proof.workspace_snapshot != snapshot
        || !proof.no_unfenced_startup_effects
        || !proof.paid_extra_disabled
        || proof.observed_at_ms > now
        || now >= proof.valid_until_ms
    {
        return Err(invalid(
            "Fresh launch-surface/paid-extra safety evidence required; login/trial cannot substitute",
        ));
    }
    Ok(())
}
