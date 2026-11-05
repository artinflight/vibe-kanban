//! Shared no-takeover continuation boundary; no provider selector or retry loop.
use std::{io, sync::Arc};

use db::models::{
    coding_agent_turn::CodingAgentTurn,
    execution_process::ExecutionProcess,
    provider_admission::{self as store, Receipt},
    scratch::{Scratch, ScratchPayload, ScratchType},
    session::Session,
    workspace::Workspace,
    workspace_repo::WorkspaceRepo,
};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_follow_up::CodingAgentFollowUpRequest,
        coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::{BaseCodingAgent, CodingAgent, StandardCodingAgentExecutor},
    profile::{ExecutorConfig, ExecutorConfigs},
    routing::RoutingMode,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use super::container::{ContainerError, ContainerService};
pub mod checkpoint;
pub const CONTRACT: &str = "vk.provider-admission.v1";
fn error(s: &str) -> ContainerError {
    ContainerError::Other(anyhow::anyhow!(s.to_owned()))
}
/// Explicit recursive key ordering; serde_json preserve_order feature unification
/// elsewhere must not change the request identity agreed with the T67 client.
struct Canonical<'a>(&'a Value);
impl Serialize for Canonical<'_> {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        use serde::ser::{SerializeMap, SerializeSeq};
        match self.0 {
            Value::Object(object) => {
                let mut keys: Vec<_> = object.keys().collect();
                keys.sort_unstable();
                let mut map = serializer.serialize_map(Some(keys.len()))?;
                for key in keys {
                    map.serialize_entry(key, &Canonical(&object[key]))?;
                }
                map.end()
            }
            Value::Array(array) => {
                let mut seq = serializer.serialize_seq(Some(array.len()))?;
                for item in array {
                    seq.serialize_element(&Canonical(item))?;
                }
                seq.end()
            }
            scalar => scalar.serialize(serializer),
        }
    }
}
pub fn hash(v: &Value) -> String {
    format!(
        "{:x}",
        Sha256::digest(serde_json::to_vec(&Canonical(v)).expect("bounded JSON value"))
    )
}
fn source_generation() -> &'static str {
    static GENERATION: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    GENERATION.get_or_init(|| {
        // Bind target/POST/recovery to compiled contract code even when an older
        // build has no externally supplied source stamp. No live filesystem read.
        hash(&json!([
            option_env!("VK_BUILD_SOURCE_COMMIT"),
            include_str!("provider_admission.rs"),
            include_str!("provider_admission/checkpoint.rs"),
            include_str!("../../../executors/src/provider_failover/checkpoint.rs")
        ]))
    })
}
fn value(v: &impl Serialize) -> Result<Value, ContainerError> {
    serde_json::to_value(v).map_err(|_| error("invalid_configuration"))
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Intent {
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub request_id: Uuid,
    pub prompt: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub initial_executor_config: Option<ExecutorConfig>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub checkpoint_receipt: Option<String>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Expected {
    pub workspace_id: Uuid,
    pub executor: String,
    pub state_token: String,
    pub predecessor_execution_id: Option<Uuid>,
    pub native_binding_sha256: Option<String>,
}
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub contract_version: String,
    pub request_id: Uuid,
    pub intent_sha256: String,
    // Keep exact wire shape (omitted fields vs explicit null included) for Python's
    // canonical intent/config hashes. Typed roundtrips are NOT canonicalization.
    pub intent: Value,
    pub expected: Expected,
    pub executor_config: Value,
}
#[derive(Debug, Serialize)]
pub struct Target {
    pub contract_version: &'static str,
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub executor: String,
    pub status: String,
    pub running: bool,
    pub queue_pending: bool,
    pub conflicting_jobs: bool,
    pub state_token: String,
    pub predecessor_execution_id: Option<Uuid>,
    pub native_binding_sha256: Option<String>,
    pub checkpoint_receipt: Option<String>,
    pub available_checkpoint_receipt: Option<String>,
    pub blocker_code: Option<String>,
    pub provider_started: bool,
    #[serde(skip)]
    pub selected: Option<ExecutorConfig>,
    #[serde(skip)]
    pub native_session: Option<String>,
    #[serde(skip)]
    pub profile_pin: Option<String>,
    #[serde(skip)]
    pub(super) unrelated_owner_conflict: bool,
}

pub fn selected_profile(config: &ExecutorConfig) -> Result<CodingAgent, ContainerError> {
    if !matches!(
        config.executor,
        BaseCodingAgent::Codex | BaseCodingAgent::ClaudeCode
    ) || config.model_id.as_deref() == Some("gpt-6-astra")
        || config
            .routing
            .as_ref()
            .is_some_and(|r| r.mode != RoutingMode::Shadow)
    {
        return Err(error("unsupported_executor_or_selection"));
    }
    let mut agent = ExecutorConfigs::get_cached()
        .get_coding_agent(&config.profile_id())
        .ok_or_else(|| error("saved_profile_missing"))?;
    agent.apply_overrides(config);
    if matches!(&agent,CodingAgent::Codex(native) if native.model.is_none()) {
        return Err(error("selected_model_unknown"));
    }
    if matches!(&agent,CodingAgent::Codex(native) if native.model.as_deref().is_some_and(|m|m=="gpt-6-astra" || m=="gpt-6-astra-fast"))
    {
        return Err(error("astra_requires_separate_explicit_manual_approval"));
    }
    if let Some(wanted) = &config.reasoning_id {
        let actual = match &agent {
            CodingAgent::Codex(c) => value(&c.model_reasoning_effort)?,
            CodingAgent::ClaudeCode(c) => value(
                &c.provider_profile_facts(config.variant.as_deref().unwrap_or("DEFAULT"))
                    .effort,
            )?,
            _ => return Err(error("unsupported_executor")),
        };
        if actual != json!(wanted) {
            return Err(error("selected_effort_not_supported"));
        }
    }
    if let CodingAgent::ClaudeCode(c) = &agent {
        let p = c.provider_profile_facts(config.variant.as_deref().unwrap_or("DEFAULT"));
        if !p.supervised
            || p.plan
            || p.bypass
            || p.router
            || p.command_overrides
            || !p.disable_api_key
            || p.agent_override
        {
            return Err(error("effective_supervised_subscription_profile_required"));
        }
        executors::provider_failover::claude::subscription_environment(
            std::env::vars_os()
                .filter_map(|(k, _)| k.into_string().ok())
                .collect::<Vec<_>>()
                .iter()
                .map(String::as_str),
        )?;
    }
    Ok(agent)
}
fn recommend(mut c: ExecutorConfig) -> ExecutorConfig {
    let r = c.routing.get_or_insert_with(|| {
        Box::new(executors::routing::RoutingPolicy {
            mode: RoutingMode::Shadow,
            floor: Default::default(),
            denied_models: vec![],
            allow_escalation: false,
        })
    });
    r.mode = RoutingMode::Shadow;
    c
}

/// Bounded metadata only. A state token is a revalidation fingerprint, NOT a lease.
/// Existing checkpoint/effect handoff remains owned by provider_failover; a string
/// supplied by a client never manufactures cross-provider checkpoint authority.
pub async fn target<C: ContainerService + ?Sized>(
    c: &C,
    session: &Session,
    checkpoint: Option<String>,
    own: Option<Uuid>,
) -> Result<Target, ContainerError> {
    let pool = &c.db().pool;
    let session = Session::find_by_id(pool, session.id)
        .await?
        .ok_or_else(|| error("stale_binding"))?;
    let workspace = Workspace::find_by_id(pool, session.workspace_id)
        .await?
        .ok_or_else(|| error("stale_binding"))?;
    let sessions = Session::find_by_workspace_id(pool, workspace.id).await?;
    if sessions.len() > 128 {
        return Err(error("bounded_inventory_exceeded"));
    }
    let mut t = Target {
        contract_version: CONTRACT,
        workspace_id: workspace.id,
        session_id: session.id,
        executor: session.executor.clone().unwrap_or_default(),
        status: "ready".into(),
        running: false,
        queue_pending: false,
        conflicting_jobs: false,
        state_token: String::new(),
        predecessor_execution_id: None,
        native_binding_sha256: None,
        checkpoint_receipt: checkpoint.clone(),
        available_checkpoint_receipt: None,
        blocker_code: None,
        provider_started: false,
        selected: None,
        native_session: None,
        profile_pin: None,
        unrelated_owner_conflict: false,
    };
    let mut scheduled = false;
    if let Some(controller) = executors::capacity::controller::configured()? {
        let ctl = controller.lock().await;
        scheduled = sessions.iter().any(|s| {
            ctl.state
                .goals
                .get(&s.id)
                .is_some_and(|g| g.grant.is_some())
        });
    }
    if let Some(ledger) = super::original_worker::current()
        && sessions.iter().any(|s| {
            s.id == ledger.contract.worker.session || s.id == ledger.contract.manager.session
        })
        && !ledger.terminal().await?
    {
        t.status = "owner_conflict".into();
        t.unrelated_owner_conflict = true;
    }
    for s in &sessions {
        t.queue_pending |= c.provider_continuation_queue_pending(s.id);
    }
    let running:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.status='running' AND (? IS NULL OR e.id!=?))")
        .bind(workspace.id).bind(own).bind(own).fetch_one(pool).await?;
    t.running = running;
    let queued:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM turn_github_sync_user_queue WHERE workspace_id=?) OR EXISTS(SELECT 1 FROM turn_github_sync_incoming WHERE workspace_id=? AND state='received')")
        .bind(workspace.id).bind(workspace.id).fetch_one(pool).await?;
    t.queue_pending |= queued;
    let ids: Vec<_> = sessions.iter().map(|s| s.id).collect();
    let jobs =
        db::models::subagent_job::SubagentJob::active_counts_by_session_ids_with_codex_threads(
            pool, &ids,
        )
        .await?;
    let pending_child:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM subagent_jobs j JOIN sessions s ON s.id=j.session_id WHERE s.workspace_id=? AND j.status NOT IN ('completed','failed'))")
        .bind(workspace.id).fetch_one(pool).await?;
    t.conflicting_jobs = pending_child
        || jobs.values().any(|j| j.running > 0 || j.unresolved > 0)
        || c.workspace_has_external_processes(&workspace).await;
    let previous:Option<(Uuid,String,String,Option<i64>)>=sqlx::query_as("SELECT id,status,executor_action,exit_code FROM execution_processes WHERE session_id=? AND run_reason='codingagent' AND dropped=0 AND (? IS NULL OR id!=?) ORDER BY created_at DESC,rowid DESC LIMIT 1")
        .bind(session.id).bind(own).bind(own).fetch_optional(pool).await?;
    t.predecessor_execution_id = previous.as_ref().map(|p| p.0);
    let native = CodingAgentTurn::find_latest_session_info(pool, session.id).await?;
    let interrupted =
        CodingAgentTurn::find_interrupted_context_excluding(pool, session.id, own).await?;
    let draft = Scratch::find_by_id(pool, session.id, &ScratchType::DraftFollowUp)
        .await
        .map_err(|_| error("saved_selection_unknown"))?;
    t.selected = match &draft {
        Some(d) => match &d.payload {
            ScratchPayload::DraftFollowUp(d) => Some(d.executor_config.clone()),
            _ => return Err(error("saved_selection_unknown")),
        },
        None => previous
            .as_ref()
            .map(|p| serde_json::from_str::<ExecutorAction>(&p.2))
            .transpose()
            .map_err(|_| error("saved_selection_unknown"))?
            .as_ref()
            .and_then(executors::routing::config)
            .cloned(),
    }
    .map(recommend);
    if let Some(n) = &native {
        t.native_session = Some(n.session_id.clone());
        t.native_binding_sha256 = Some(hash(&json!([t.executor, n.session_id, n.message_id])));
    } else if previous.is_some() {
        t.status = "stale_binding".into();
    }
    if let Some(config) = &t.selected {
        if config.executor.to_string() != t.executor {
            t.status = "stale_binding".into();
        }
        match selected_profile(config) {
            Ok(agent) => t.profile_pin = Some(executors::original_worker::profile_digest(&agent)?),
            Err(_) => {
                t.status = "blocked".into();
                t.blocker_code = Some("saved_profile_not_eligible_for_guarded_continuation".into());
            }
        }
    }
    // An empty target in an already-used workspace is a provider handoff, never
    // permission to restart history from scratch. Existing trusted dispatcher must
    // consume a real checkpoint; this generic continuation endpoint will not guess.
    let used_elsewhere:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND s.id!=? AND e.run_reason='codingagent')")
        .bind(workspace.id).bind(session.id).fetch_one(pool).await?;
    let workspace_predecessor:Option<Uuid>=sqlx::query_scalar("SELECT e.session_id FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.run_reason='codingagent' AND e.dropped=0 AND (? IS NULL OR e.id!=?) ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1")
        .bind(workspace.id).bind(own).bind(own).fetch_optional(pool).await?;
    // Re-selecting an older destination session is still a handoff. Its own
    // native history is valuable, but is not proof of the source's pending work.
    if checkpoint.is_some()
        || (previous.is_none() && used_elsewhere)
        || workspace_predecessor.is_some_and(|id| id != session.id)
    {
        t.status = "checkpoint_required".into();
    }
    if db::models::provider_handoff::owner(pool, workspace.id)
        .await?
        .is_some()
        || db::models::provider_handoff::activation(pool, workspace.id)
            .await?
            .is_some()
    {
        t.status = "owner_conflict".into();
    }
    if let Some(owner) = store::owner(pool, workspace.id).await?
        && Some(owner.execution_id) != own
        && owner.status != "admitted"
    {
        t.status = "owner_conflict".into();
        t.unrelated_owner_conflict = true;
    }
    if scheduled {
        t.status = "scheduled".into();
    }
    if t.conflicting_jobs {
        t.status = "conflicting_jobs".into();
    }
    if t.queue_pending {
        t.status = "queued".into();
    }
    if t.running {
        t.status = "running".into();
    }
    if !matches!(t.executor.as_str(), "CODEX" | "CLAUDE_CODE") {
        t.status = "unsupported_executor".into();
    }
    if t.status == "ready"
        && c.verify_provider_continuation_boundary(&workspace, own)
            .await
            .is_err()
    {
        t.status = "checkpoint_required".into();
        t.blocker_code = Some("native_terminal_capture_unverified".into());
    }
    let mut repos = WorkspaceRepo::find_repos_for_workspace(pool, workspace.id).await?;
    repos.sort_by_key(|r| r.id);
    let mut links = WorkspaceRepo::find_by_workspace_id(pool, workspace.id).await?;
    links.sort_by_key(|r| r.repo_id);
    let inventory = repos
        .iter()
        .map(|r| {
            json!([
                r.id,
                r.path,
                r.name,
                r.setup_script,
                r.cleanup_script,
                r.archive_script,
                r.copy_files,
                r.parallel_setup_script,
                r.dev_server_script,
                r.default_target_branch,
                r.default_working_dir
            ])
        })
        .collect::<Vec<_>>();
    let linked = links
        .iter()
        .map(|r| json!([r.id, r.repo_id, r.target_branch]))
        .collect::<Vec<_>>();
    let interrupted_digest = hash(&json!(
        interrupted
            .iter()
            .map(|i| json!([i.status, i.exit_code, i.prompt, i.summary, i.created_at]))
            .collect::<Vec<_>>()
    ));
    // Normal start touches timestamps and unarchives the workspace. Those are
    // not changed source/permission authority. Bind stable scope explicitly.
    t.state_token = hash(&json!([
        source_generation(),
        [
            workspace.id,
            workspace.task_id,
            workspace.container_ref,
            workspace.branch,
            workspace.worktree_deleted
        ],
        [
            session.id,
            session.workspace_id,
            session.executor,
            session.agent_working_dir
        ],
        inventory,
        linked,
        previous,
        t.native_binding_sha256,
        draft.as_ref().map(|d| &d.payload),
        t.selected,
        t.profile_pin,
        interrupted_digest
    ]));
    if checkpoint.is_none() && matches!(t.status.as_str(), "checkpoint_required" | "owner_conflict")
    {
        t.available_checkpoint_receipt = store::checkpoint::available(
            &c.db().pool,
            t.session_id,
            &t.state_token,
            chrono::Utc::now().timestamp_millis(),
        )
        .await?;
        // A discovered reference does NOT turn a blocked target into ready.
    }
    if let Some(reference) = checkpoint {
        match checkpoint::verify(c, &t, &reference, own).await {
            Ok(_)
                if !t.unrelated_owner_conflict
                    && matches!(
                        t.status.as_str(),
                        "checkpoint_required" | "owner_conflict" | "ready"
                    ) =>
            {
                t.status = "ready".into();
                t.blocker_code = None;
            }
            Ok(_) => {}
            Err(_)
                if matches!(
                    t.status.as_str(),
                    "checkpoint_required" | "owner_conflict" | "ready"
                ) =>
            {
                t.status = "checkpoint_required".into();
                t.blocker_code = Some("trusted_checkpoint_missing_stale_or_unfenced".into());
            }
            Err(_) => {}
        }
    }
    Ok(t)
}

struct Launch {
    request: Uuid,
    workspace: Uuid,
    session: Uuid,
    execution: Uuid,
    action: ExecutorAction,
    token: String,
    profile: String,
    checkpoint: Option<String>,
}
tokio::task_local! {static LAUNCH:Launch;}
pub fn in_dispatch() -> bool {
    LAUNCH.try_with(|_| true).unwrap_or(false)
}
pub fn execution_id(workspace: Uuid, session: Uuid) -> Result<Option<Uuid>, ContainerError> {
    LAUNCH
        .try_with(|l| {
            if l.workspace == workspace && l.session == session {
                Ok(Some(l.execution))
            } else {
                Err(error("stale_binding"))
            }
        })
        .unwrap_or(Ok(None))
}
/// Called before inference/setup on EVERY common launch, not just this route.
pub async fn before_start<C: ContainerService + ?Sized>(
    c: &C,
    workspace: Uuid,
    session: Uuid,
) -> Result<(), ContainerError> {
    if let Some(r) = store::owner(&c.db().pool, workspace).await?
        && execution_id(workspace, session)? != Some(r.execution_id)
    {
        return Err(error("provider_continuation_owner_conflict"));
    }
    Ok(())
}
/// Resolve Recommend telemetry once, then bind its exact persisted action. Model,
/// effort, profile, prompt, native anchor and cleanup chain may not change here.
pub async fn bind_resolved(
    pool: &sqlx::SqlitePool,
    action: &ExecutorAction,
) -> Result<(), ContainerError> {
    let Some((request, mut expected)) = LAUNCH.try_with(|l| (l.request, l.action.clone())).ok()
    else {
        return Ok(());
    };
    expected.routing_decision = action.routing_decision.clone();
    if value(&expected)? != value(action)? {
        return Err(error("resolved_selection_changed"));
    }
    if !store::bind_action(
        pool,
        request,
        &serde_json::to_string(action).map_err(|_| error("invalid_action"))?,
    )
    .await?
    {
        return Err(error("dispatch_already_claimed"));
    }
    Ok(())
}
/// Fresh database/config/native/queue checks after asynchronous setup. No timeout
/// releases ownership; cancellation leaves the exact immutable receipt to inspect.
pub async fn before_spawn<C: ContainerService + ?Sized>(
    c: &C,
    workspace: Uuid,
    session: Uuid,
    action: &ExecutorAction,
) -> Result<(), ContainerError> {
    before_start(c, workspace, session).await?;
    let Some((request, execution, token, profile, checkpoint)) = LAUNCH
        .try_with(|l| {
            (
                l.request,
                l.execution,
                l.token.clone(),
                l.profile.clone(),
                l.checkpoint.clone(),
            )
        })
        .ok()
    else {
        return Ok(());
    };
    let r = store::get(&c.db().pool, request)
        .await?
        .ok_or_else(|| error("receipt_missing"))?;
    if r.status != "dispatching"
        || r.ownership != "held"
        || r.execution_id != execution
        || r.expected_action
            != serde_json::to_string(action).map_err(|_| error("invalid_action"))?
    {
        return Err(error("dispatch_binding_changed"));
    }
    let s = Session::find_by_id(&c.db().pool, session)
        .await?
        .ok_or_else(|| error("stale_binding"))?;
    let t = target(c, &s, checkpoint, Some(execution)).await?;
    if t.status != "ready" || t.state_token != token {
        return Err(error("post_setup_binding_changed"));
    }
    let config =
        executors::routing::config(action).ok_or_else(|| error("missing_configuration"))?;
    if executors::original_worker::profile_digest(&selected_profile(config)?)? != profile {
        return Err(error("resolved_profile_changed"));
    }
    executors::capacity::controller::before_no_takeover_launch(session).await?;
    Ok(())
}

pub async fn readback(pool: &sqlx::SqlitePool, r: &Receipt) -> Result<Value, ContainerError> {
    let execution = if r.status == "admitted" {
        Some(
            ExecutionProcess::find_by_id(pool, r.execution_id)
                .await?
                .ok_or_else(|| error("accepted_execution_missing"))?,
        )
    } else {
        None
    };
    Ok(
        json!({"contract_version":CONTRACT,"workspace_id":r.workspace_id,"session_id":r.session_id,
        "request_id":r.request_id,"executor":r.executor,"intent_sha256":r.intent_sha256,
        "configuration_sha256":r.configuration_sha256,"durable":true,"status":r.status,
        "accepted":match r.status.as_str(){"admitted"=>Some(true),"rejected"=>Some(false),_=>None},
        "execution_id":execution.as_ref().map(|e|e.id),"execution":execution,
        "reason":r.reason,"queue_id":null}),
    )
}

pub async fn dispatch<C: ContainerService>(
    c: &C,
    session: &Session,
    request: Request,
) -> Result<Value, ContainerError> {
    super::admission::locked(async {
        let intent: Intent =
            serde_json::from_value(request.intent.clone()).map_err(|_| error("invalid_intent"))?;
        if request.contract_version != CONTRACT
            || request.request_id != intent.request_id
            || request.request_id.is_nil()
            || intent.session_id != session.id
            || intent.workspace_id != session.workspace_id
            || intent.prompt.trim().is_empty()
            || intent.prompt.chars().count() > 60_000
            || intent.workspace_id.is_nil()
            || intent.session_id.is_nil()
            || hash(&request.intent) != request.intent_sha256
        {
            return Err(error("request_conflict"));
        }
        if let Some(r) = store::get(&c.db().pool, request.request_id).await? {
            if r.workspace_id != intent.workspace_id
                || r.session_id != intent.session_id
                || r.intent_sha256 != request.intent_sha256
            {
                return Err(error("request_conflict"));
            }
            return readback(&c.db().pool, &r).await;
        }
        if !request.executor_config.as_object().is_some_and(|m| {
            m.keys().all(|k| {
                matches!(
                    k.as_str(),
                    "executor"
                        | "variant"
                        | "model_id"
                        | "agent_id"
                        | "reasoning_id"
                        | "permission_policy"
                        | "routing"
                )
            })
        }) {
            return Err(error("invalid_configuration"));
        }
        let fresh = Session::find_by_id(&c.db().pool, session.id)
            .await?
            .ok_or_else(|| error("stale_binding"))?;
        if value(&fresh)? != value(session)? {
            return Err(error("stale_binding"));
        }
        let config: ExecutorConfig = serde_json::from_value(request.executor_config.clone())
            .map_err(|_| error("invalid_configuration"))?;
        let t = target(c, session, intent.checkpoint_receipt.clone(), None).await?;
        if t.status != "ready" {
            return Err(error(&t.status));
        }
        if request.expected.workspace_id != t.workspace_id
            || request.expected.executor != t.executor
            || request.expected.state_token != t.state_token
            || request.expected.predecessor_execution_id != t.predecessor_execution_id
            || request.expected.native_binding_sha256 != t.native_binding_sha256
        {
            return Err(error("stale_binding"));
        }
        if intent
            .initial_executor_config
            .as_ref()
            .is_some_and(|c| c.routing.is_some() || c.permission_policy.is_some())
        {
            return Err(error("initial_policy_override_forbidden"));
        }
        let expected = match t.selected.clone() {
            Some(c) if intent.initial_executor_config.is_none() => c,
            None if t.predecessor_execution_id.is_none() => recommend(
                intent
                    .initial_executor_config
                    .ok_or_else(|| error("initial_selection_required"))?,
            ),
            _ => return Err(error("saved_selection_changed")),
        };
        if config != expected || config.executor.to_string() != t.executor {
            return Err(error("saved_selection_changed"));
        }
        let profile = executors::original_worker::profile_digest(&selected_profile(&config)?)?;
        let workspace = Workspace::find_by_id(&c.db().pool, session.workspace_id)
            .await?
            .ok_or_else(|| error("stale_binding"))?;
        if intent.prompt.trim_start().starts_with('/') {
            return Err(error("approval_hold"));
        }
        let interrupted = CodingAgentTurn::find_interrupted_context_since_latest_success(
            &c.db().pool,
            session.id,
        )
        .await?;
        let mut prompt =
            CodingAgentTurn::prompt_with_interrupted_context(intent.prompt, &interrupted);
        if let Some(reference) = &intent.checkpoint_receipt {
            // Only backend-verified compact data is copied; source native IDs are
            // provenance and NEVER replace the destination's actual resume ID.
            let evidence = checkpoint::verify(c, &t, reference, None).await?;
            prompt = checkpoint::handoff(&evidence, prompt)?;
        }
        // Native control commands need their own scoped authority, never convert
        // continuation admission into /goal resume, rollback, fork or Stop.
        if prompt.trim_start().starts_with('/') {
            return Err(error("approval_hold"));
        }
        let typ = if let Some(native) = t.native_session {
            ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                capacity: None,
                prompt,
                session_id: native,
                reset_to_message_id: None,
                executor_config: config,
                working_dir: session.agent_working_dir.clone(),
            })
        } else {
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt,
                executor_config: config,
                working_dir: session.agent_working_dir.clone(),
            })
        };
        // Do not add cleanup/scripts to a request with no authority to reset or
        // replay side effects. Existing history and dirty workspace stay intact.
        let action = ExecutorAction::new(typ, None);
        let r = Receipt {
            request_id: request.request_id,
            workspace_id: workspace.id,
            session_id: session.id,
            executor: t.executor,
            intent_sha256: request.intent_sha256,
            configuration_sha256: hash(&request.executor_config),
            intent: serde_json::to_string(&request.intent).map_err(|_| error("invalid_intent"))?,
            state_token: t.state_token.clone(),
            predecessor_execution_id: t.predecessor_execution_id,
            execution_id: Uuid::new_v4(),
            expected_action: serde_json::to_string(&action).map_err(|_| error("invalid_action"))?,
            status: "reserved".into(),
            ownership: "held".into(),
            reason: String::new(),
        };
        let previous = store::owner(&c.db().pool, workspace.id).await?;
        if !store::reserve_with_checkpoint(
            &c.db().pool,
            &r,
            previous.as_ref(),
            intent.checkpoint_receipt.as_deref(),
            chrono::Utc::now().timestamp_millis(),
        )
        .await?
        {
            let prior = store::get(&c.db().pool, r.request_id)
                .await?
                .ok_or_else(|| error("receipt_missing"))?;
            if prior.intent_sha256 != r.intent_sha256 || prior.session_id != r.session_id {
                return Err(error("request_conflict"));
            }
            return readback(&c.db().pool, &prior).await;
        }
        let launch = Launch {
            request: r.request_id,
            workspace: r.workspace_id,
            session: r.session_id,
            execution: r.execution_id,
            action: action.clone(),
            token: r.state_token.clone(),
            profile,
            checkpoint: intent.checkpoint_receipt.clone(),
        };
        let result = LAUNCH
            .scope(launch, async {
                // Repeat metadata after the durable claim and before any classifier.
                let check = target(
                    c,
                    session,
                    intent.checkpoint_receipt.clone(),
                    Some(r.execution_id),
                )
                .await?;
                if check.status != "ready" || check.state_token != r.state_token {
                    return Err(error("stale_binding"));
                }
                c.start_execution(
                    &workspace,
                    session,
                    &action,
                    &db::models::execution_process::ExecutionProcessRunReason::CodingAgent,
                )
                .await
            })
            .await;
        if result.is_err() {
            // Only a still-reserved row is proven not dispatched. Once the common
            // launch bound its action, errors/cancellation are always uncertain.
            if intent.checkpoint_receipt.is_some() {
                store::checkpoint::hold(&c.db().pool, r.request_id).await?;
            } else {
                store::reject(&c.db().pool, r.request_id, "blocked").await?;
            }
        }
        store::outcome(&c.db().pool, r.request_id, result.is_ok()).await?;
        let final_row = store::get(&c.db().pool, r.request_id)
            .await?
            .ok_or_else(|| error("receipt_missing"))?;
        readback(&c.db().pool, &final_row).await
    })
    .await
}

#[derive(Debug)]
struct Pin {
    pool: sqlx::SqlitePool,
    request: Uuid,
    config: ExecutorConfig,
    profile: String,
}
#[async_trait::async_trait]
impl executors::original_worker::LaunchGuard for Pin {
    async fn resolved(&self, agent: &CodingAgent, raw: &ExecutorConfig) -> io::Result<()> {
        executors::original_worker::verify_resolved(agent, raw, &self.config, &self.profile)?;
        let r = store::get(&self.pool, self.request)
            .await
            .map_err(io::Error::other)?
            .ok_or_else(|| io::Error::other("Continuation receipt missing"))?;
        if r.status != "dispatching" || r.ownership != "held" {
            return Err(io::Error::other("Continuation ownership changed"));
        }
        let intent: Intent = serde_json::from_str(&r.intent).map_err(io::Error::other)?;
        if let Some(reference) = intent.checkpoint_receipt {
            let cp = store::checkpoint::get(&self.pool, &reference)
                .await
                .map_err(io::Error::other)?
                .ok_or_else(|| io::Error::other("Trusted checkpoint missing"))?;
            if cp.claimed_request != Some(r.request_id)
                || cp.workspace_id != r.workspace_id
                || cp.destination_session_id != r.session_id
                || chrono::Utc::now().timestamp_millis() >= cp.valid_until_ms
            {
                return Err(io::Error::other(
                    "Trusted checkpoint expired or changed before native launch",
                ));
            }
        }
        Ok(())
    }
    async fn activation(
        &self,
        _thread: &str,
        _input: Option<&str>,
    ) -> io::Result<executors::original_worker::ActivationFence> {
        Err(io::Error::other(
            "Continuation is not bounded-worker authority",
        ))
    }
    fn worker(&self) -> bool {
        false
    }
}
pub fn launch_pin(
    pool: &sqlx::SqlitePool,
    action: &ExecutorAction,
) -> Result<Option<Arc<dyn executors::original_worker::LaunchGuard>>, ContainerError> {
    let Some((request, profile)) = LAUNCH.try_with(|l| (l.request, l.profile.clone())).ok() else {
        return Ok(None);
    };
    let config = executors::routing::config(action)
        .ok_or_else(|| error("missing_configuration"))?
        .clone();
    Ok(Some(Arc::new(Pin {
        pool: pool.clone(),
        request,
        config,
        profile,
    })))
}
