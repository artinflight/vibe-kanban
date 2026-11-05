//! Opt-in provider host caller at existing execution/exit boundaries. No scheduler,
//! timeout takeover, inferred admission, model probe or global routing enrollment.
use std::{
    io,
    path::PathBuf,
    sync::{Arc, Mutex, OnceLock},
};

use anyhow::anyhow;
use db::models::{
    execution_process::{ExecutionProcess, ExecutionProcessRunReason},
    provider_handoff::{self, Reservation},
    session::Session,
    workspace::Workspace,
};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::{BaseCodingAgent, CodingAgent, StandardCodingAgentExecutor},
    model_selector::PermissionPolicy,
    profile::{ExecutorConfig, ExecutorConfigs},
    provider_failover::{
        self as pf, Admission, Boundary, Controller, Plan, Provider, claude,
        readiness::{self, Readiness},
    },
};
use serde::Serialize;
use sha2::{Digest, Sha256};
use uuid::Uuid;

use super::{
    admission,
    container::{ContainerError, ContainerService},
};

fn held(s: &str) -> ContainerError {
    ContainerError::Other(anyhow!(s.to_owned()))
}
fn uuid(s: &str) -> Result<Uuid, ContainerError> {
    Uuid::parse_str(s).map_err(|_| held("Invalid provider scope identity"))
}
fn now() -> Result<u64, ContainerError> {
    chrono::Utc::now()
        .timestamp_millis()
        .try_into()
        .map_err(|_| held("Invalid clock"))
}
pub fn actions_digest(actions: &pf::tools::Actions) -> Result<String, ContainerError> {
    Ok(format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(actions).map_err(|_| held("Invalid action scope"))?)
    ))
}
fn hold(reason: &str) -> Readiness {
    Readiness::Hold {
        reason: reason.into(),
    }
}
#[derive(Debug, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Outcome {
    Unmanaged,
    Held {
        reason: String,
    },
    Blocked {
        code: String,
        action: String,
        provider_started: bool,
    },
    Activated,
    CheckpointReady {
        receipt: String,
    },
    Released,
    Started {
        execution_id: Uuid,
    },
}
fn stopped(reason: Readiness) -> Outcome {
    match reason {
        Readiness::Hold { reason } => Outcome::Held { reason },
        Readiness::Blocked { code, action, .. } => Outcome::Blocked {
            code,
            action,
            provider_started: false,
        },
        _ => Outcome::Held {
            reason: "readiness_not_granted".into(),
        },
    }
}

/// Returned only by a trusted backend readiness/admission adapter, NOT request JSON.
/// The Git owner supplies inventory/head/capture/owner proof; this consumer does
/// not create a competing Git protocol or infer success from a missing receipt.
pub struct Activation {
    pub journal_root: PathBuf,
    pub create_new: bool,
    pub work: pf::Work,
    pub pools: Vec<pf::Pool>,
    pub readiness_scope: readiness::Scope,
    pub readiness: Option<readiness::Receipt>,
    pub native_session_id: String,
    pub codex_limit_id: Option<String>,
}
pub struct ClaudeEligibility {
    pub login: claude::NativeLogin,
    pub trial: claude::Trial,
    pub launch_safety: claude::LaunchSafety,
    pub launcher_digest: String,
    pub os_user: String,
}
pub struct Completion {
    pub checkpoint: pf::Checkpoint,
    pub readiness_scope: readiness::Scope,
    pub readiness: Option<readiness::Receipt>,
    pub accepted_result_receipt: String,
}
pub struct DispatchRequest {
    pub work_id: String,
    /// Explicit trusted destination, not inferred from a provider/name/last chat.
    /// Some prepares a checkpoint for T67; None preserves the existing caller.
    pub continuation_session: Option<Uuid>,
    pub checkpoint: pf::Checkpoint,
    pub ended: pf::observer::Ended,
    pub pools: Vec<pf::Pool>,
    pub capacities: Vec<pf::selection::Capacity>,
    pub claude: Option<ClaudeEligibility>,
    /// Exact task qualification, including authorized writes; the login trial
    /// alone neither qualifies nor permanently prohibits general coding work.
    pub task_qualified: bool,
    pub actions: pf::tools::Actions,
    pub reconciled_tools: Vec<pf::tools::ReconciledTool>,
    /// Actual trusted permission/toolchain facts in the sealed Git contract shape.
    pub git_dispatch_context: serde_json::Value,
    pub profile: ExecutorConfig,
    pub profile_digest: String,
    pub readiness_scope: readiness::Scope,
    pub readiness: Option<readiness::Receipt>,
    pub permit: Admission,
    pub boundary: Boundary,
}
static CONTROLLERS: OnceLock<Mutex<std::collections::BTreeMap<PathBuf, Arc<Mutex<Controller>>>>> =
    OnceLock::new();
fn controller(root: PathBuf, create: bool) -> Result<Arc<Mutex<Controller>>, ContainerError> {
    let mut cache = CONTROLLERS
        .get_or_init(Default::default)
        .lock()
        .map_err(|_| held("Controller registry poisoned"))?;
    if let Some(c) = cache.get(&root) {
        return Ok(c.clone());
    }
    if cache.len() >= 100 {
        return Err(held("Controller registry full"));
    }
    // Explicit create only. Missing/corrupt recovery journals never get recreated.
    let c = Arc::new(Mutex::new(if create {
        Controller::create(&root)?
    } else {
        Controller::open(&root)?
    }));
    cache.insert(root, c.clone());
    Ok(c)
}
pub(super) fn continuation_candidate(
    root: &str,
    work: &str,
    candidate: &pf::Candidate,
) -> Result<(), ContainerError> {
    let core = controller(PathBuf::from(root), false)?;
    core.lock()
        .map_err(|_| held("Controller poisoned"))?
        .continuation_candidate(work, candidate)?;
    Ok(())
}
pub(super) fn continuation_evidence(
    root: &str,
    work: &str,
    cp: &pf::Checkpoint,
) -> Result<Vec<u8>, ContainerError> {
    let core = controller(PathBuf::from(root), false)?;
    let evidence = core
        .lock()
        .map_err(|_| held("Controller poisoned"))?
        .continuation_evidence(work, cp)?;
    Ok(evidence)
}

struct Launch {
    workspace: Uuid,
    session: Uuid,
    execution: Uuid,
    action: String,
    evidence_deadline_ms: u64,
}
tokio::task_local! {static LAUNCH:Launch;}
pub fn reserved_execution(
    workspace: Uuid,
    session: Uuid,
    action: &ExecutorAction,
) -> io::Result<Option<Uuid>> {
    LAUNCH
        .try_with(|l| {
            if l.workspace != workspace
                || l.session != session
                || serde_json::to_string(action)? != l.action
            {
                return Err(io::Error::other("Provider launch scope/action changed"));
            }
            let time = chrono::Utc::now().timestamp_millis();
            if time < 0 || time as u64 >= l.evidence_deadline_ms {
                return Err(io::Error::other(
                    "Provider evidence expired before process start",
                ));
            }
            Ok(Some(l.execution))
        })
        .unwrap_or(Ok(None))
}
pub fn before_provider_spawn(
    workspace: Uuid,
    session: Uuid,
    action: &ExecutorAction,
) -> Result<(), ContainerError> {
    reserved_execution(workspace, session, action)?;
    Ok(())
}
/// Run before routing/classifier/setup work, not merely before the DB INSERT.
/// Ordinary starts must not pay inference to rediscover an existing held owner.
pub async fn before_start<C: ContainerService + ?Sized>(
    container: &C,
    workspace: Uuid,
    session: Uuid,
    action: &ExecutorAction,
) -> Result<(), ContainerError> {
    if reserved_execution(workspace, session, action)?.is_some() {
        return Ok(());
    }
    if provider_handoff::activation(&container.db().pool, workspace)
        .await?
        .is_some()
        || provider_handoff::owner(&container.db().pool, workspace)
            .await?
            .is_some()
    {
        return Err(held(
            "provider_workspace_reserved: checkpoint/reconcile required before any classifier or provider start",
        ));
    }
    Ok(())
}

/// Real activation caller. The HTTP caller supplies only an existing execution ID;
/// authority, settings, receipts and native identities come from the backend adapter.
pub async fn activate<C: ContainerService>(
    container: &C,
    execution: Uuid,
) -> Result<Outcome, ContainerError> {
    admission::locked(async {
        let a = match container.prepare_provider_activation(execution).await {
            Ok(a) => a,
            Err(e) => return Ok(stopped(e)),
        };
        let t = now()?;
        if let r @ Readiness::Hold { .. } =
            readiness::check(a.readiness.as_ref(), &a.readiness_scope, t)
        {
            return Ok(stopped(r));
        }
        let ctx = ExecutionProcess::load_context(&container.db().pool, execution).await?;
        let selected = ctx.execution_process.executor_action()?;
        let config = executors::routing::config(selected)
            .ok_or_else(|| held("Selected execution config absent"))?;
        if a.work.execution_id != execution.to_string()
            || a.work.workspace_id != ctx.workspace.id.to_string()
            || a.work.policy.mode != pf::Mode::Auto
            || !a.work.policy.failover_authorized
            || a.work.native_goal_active
            || config.executor != BaseCodingAgent::Codex
            || config.model_id.as_deref() != Some("gpt-6.1-sol")
            || a.work.incumbent.model != "gpt-6.1-sol"
            || config.reasoning_id.as_deref() != Some(&a.work.incumbent.effort)
            || !a
                .work
                .policy
                .excluded_models
                .iter()
                .any(|m| m == "gpt-6-astra")
            || a.readiness_scope.workspace_id != a.work.workspace_id
            || a.readiness_scope.execution_id != a.work.execution_id
        {
            return Ok(stopped(hold(
                "explicit_task_provider_authority_or_selected_settings_mismatch",
            )));
        }
        if let Some(existing) =
            provider_handoff::activation(&container.db().pool, ctx.workspace.id).await?
        {
            return Ok(
                if existing.work_id == a.work.id && existing.initial_execution_id == execution {
                    if existing.state == "active"
                        && pf::observer::is_registered(&execution.to_string())
                    {
                        Outcome::Activated
                    } else {
                        stopped(hold("activation_recovery_required_no_native_binding"))
                    }
                } else {
                    stopped(hold("workspace_already_owned"))
                },
            );
        }
        let c = controller(a.journal_root.clone(), a.create_new)?;
        {
            let mut core = c.lock().map_err(|_| held("Controller poisoned"))?;
            for p in a.pools {
                core.observe_pool(p)?;
            }
            if let Some(old) = core.work(&a.work.id) {
                if old != &a.work {
                    return Ok(stopped(hold(
                        "existing_journal_work_requires_reconciliation",
                    )));
                }
            } else {
                core.register(a.work.clone())?;
            }
        }
        provider_handoff::activate(
            &container.db().pool,
            &provider_handoff::Activation {
                workspace_id: ctx.workspace.id,
                work_id: a.work.id.clone(),
                initial_execution_id: execution,
                journal_root: a
                    .journal_root
                    .to_str()
                    .ok_or_else(|| held("Journal path encoding"))?
                    .into(),
                source_receipt: a.readiness.as_ref().unwrap().source_receipt.clone(),
                owner_generation: a.readiness_scope.owner_generation,
                state: "active".into(),
                reason: String::new(),
            },
        )
        .await?;
        let identity = c
            .lock()
            .map_err(|_| held("Controller poisoned"))?
            .pool(&a.work.incumbent.pool_id)
            .ok_or_else(|| held("Unknown pool"))?
            .identity
            .clone();
        pf::observer::register(
            &c,
            &a.work.id,
            &execution.to_string(),
            identity,
            &a.native_session_id,
            a.codex_limit_id,
        )?
        .retain_until_terminal();
        Ok(Outcome::Activated)
    })
    .await
}
/// Called by the EXISTING terminal monitor, and by explicit recovery/status retry.
/// A missing readiness/permit produces a structured hold without a provider turn.
pub async fn boundary<C: ContainerService>(
    container: &C,
    execution: Uuid,
) -> Result<Outcome, ContainerError> {
    admission::locked(async {
        let ctx = ExecutionProcess::load_context(&container.db().pool, execution).await?;
        let Some(a) = provider_handoff::activation(&container.db().pool, ctx.workspace.id).await?
        else {
            return Ok(Outcome::Unmanaged);
        };
        if a.state != "active" {
            return Ok(stopped(hold("provider_activation_held")));
        }
        let c = controller(PathBuf::from(&a.journal_root), false)?;
        let request = match container
            .prepare_provider_dispatch(&a.work_id, execution)
            .await
        {
            Ok(r) => r,
            Err(e) => return Ok(stopped(e)),
        };
        if request.work_id != a.work_id
            || request.checkpoint.execution_id != execution.to_string()
            || request.readiness_scope.owner_generation != a.owner_generation
        {
            return Ok(stopped(hold("checkpoint_identity_changed")));
        }
        if let Some(destination) = request.continuation_session {
            let receipt =
                super::provider_admission::checkpoint::publish(container, destination, &request)
                    .await?;
            // No new session, native turn, quota grant or ownership release here.
            return Ok(Outcome::CheckpointReady { receipt });
        }
        dispatch(container, c, request).await
    })
    .await
}
/// Explicit accepted-result release; never automatically mark quota/task failure
/// completed or drop a reservation just to unblock a queue.
pub async fn release<C: ContainerService>(
    container: &C,
    execution: Uuid,
) -> Result<Outcome, ContainerError> {
    admission::locked(async {
        let ctx = ExecutionProcess::load_context(&container.db().pool, execution).await?;
        let Some(a) = provider_handoff::activation(&container.db().pool, ctx.workspace.id).await?
        else {
            return Ok(Outcome::Unmanaged);
        };
        let completion = match container.prepare_provider_completion(execution).await {
            Ok(r) => r,
            Err(e) => return Ok(stopped(e)),
        };
        let cp = &completion.checkpoint;
        if cp.execution_id != execution.to_string()
            || completion.readiness_scope.workspace_id != a.workspace_id.to_string()
            || completion.readiness_scope.execution_id != cp.execution_id
            || completion.readiness_scope.snapshot_receipt != cp.workspace_snapshot
            || completion.readiness_scope.owner_generation != a.owner_generation
        {
            return Ok(stopped(hold("completion_identity_changed")));
        }
        if let r @ Readiness::Hold { .. } = readiness::check(
            completion.readiness.as_ref(),
            &completion.readiness_scope,
            now()?,
        ) {
            return Ok(stopped(r));
        }
        container.verify_provider_checkpoint(cp).await?;
        let c = controller(PathBuf::from(&a.journal_root), false)?;
        if let Some(owner) = provider_handoff::owner(&container.db().pool, ctx.workspace.id).await?
            && (owner.next_execution_id != execution
                || provider_handoff::reconcile(&container.db().pool, &owner, true).await?
                    != "terminal_checkpoint_verified")
        {
            return Ok(stopped(hold("completion_owner_not_terminal")));
        }
        c.lock().map_err(|_| held("Controller poisoned"))?.finish(
            &a.work_id,
            cp,
            &completion.accepted_result_receipt,
        )?;
        provider_handoff::release(
            &container.db().pool,
            ctx.workspace.id,
            &a.work_id,
            execution,
            &completion.accepted_result_receipt,
        )
        .await?;
        Ok(Outcome::Released)
    })
    .await
}
async fn dispatch<C: ContainerService>(
    container: &C,
    c: Arc<Mutex<Controller>>,
    request: DispatchRequest,
) -> Result<Outcome, ContainerError> {
    let time = now()?;
    if let r @ Readiness::Hold { .. } =
        readiness::check(request.readiness.as_ref(), &request.readiness_scope, time)
    {
        return Ok(stopped(r));
    }
    let cp = &request.checkpoint;
    if request.readiness_scope.workspace_id != cp.workspace_id
        || request.readiness_scope.execution_id != cp.execution_id
        || request.readiness_scope.snapshot_receipt != cp.workspace_snapshot
        || request.ended.execution_id != cp.execution_id
        || !request.task_qualified
        || request.profile.permission_policy != Some(PermissionPolicy::Supervised)
        || request.profile.routing.is_some()
        || request.profile.agent_id.is_some()
    {
        return Ok(stopped(hold(
            "task_actions_permissions_or_checkpoint_unverified",
        )));
    }
    // Check ALL known blockers and actual workspace before reservation or process.
    let workspace_id = uuid(&cp.workspace_id)?;
    let workspace = Workspace::find_by_id(&container.db().pool, workspace_id)
        .await?
        .ok_or_else(|| held("Workspace missing"))?;
    if workspace.branch != cp.branch
        || workspace.container_ref.as_deref() != Some(cp.workspace_path.as_str())
    {
        return Ok(stopped(hold("workspace_changed")));
    }
    if let Err(error) = container.verify_provider_checkpoint(cp).await {
        tracing::warn!(%error,"Provider preservation preflight failed; no inference");
        return Ok(stopped(hold("preservation_checkpoint_unverified")));
    }
    let previous = uuid(&cp.execution_id)?;
    let prior = ExecutionProcess::find_by_id(&container.db().pool, previous)
        .await?
        .ok_or_else(|| held("Predecessor missing"))?;
    let parent_session = Session::find_by_id(&container.db().pool, prior.session_id)
        .await?
        .ok_or_else(|| held("Predecessor session missing"))?;
    if parent_session.workspace_id != workspace_id {
        return Ok(stopped(hold("predecessor_workspace_mismatch")));
    }
    let (candidate, pool, previous_transition) = {
        let mut core = c.lock().map_err(|_| held("Controller poisoned"))?;
        for p in request.pools {
            core.observe_pool(p)?;
        }
        for capacity in request.capacities {
            core.observe_capacity(capacity)?;
        }
        if core.ended_receipt(&cp.execution_id).is_none() {
            core.record_ended(request.ended)?;
        }
        for proof in request.reconciled_tools {
            core.reconcile_tool(&request.work_id, proof)?;
        }
        let work = core
            .work(&request.work_id)
            .ok_or_else(|| held("Unknown work"))?;
        let previous_transition = match &work.phase {
            pf::Phase::Watching => None,
            pf::Phase::Running(t) | pf::Phase::DispatchPending(t)
                if t.execution_id == cp.execution_id =>
            {
                Some(t.transition_id.clone())
            }
            _ => return Ok(stopped(hold("current_owner_mismatch"))),
        };
        let plan = if previous_transition.is_some() {
            core.boundary_plan(&request.work_id, cp, time)
        } else {
            core.checkpoint(&request.work_id, cp.clone())?;
            core.plan(&request.work_id, time)
        };
        let candidate = match plan {
            Plan::Ready(c) => c,
            Plan::Recommend(_) => return Ok(stopped(hold("recommend_only_no_dispatch"))),
            Plan::Hold { reason, .. } => return Ok(stopped(hold(reason))),
        };
        let pool = core
            .pool(&candidate.pool_id)
            .ok_or_else(|| held("Unknown pool"))?
            .clone();
        // Current operator policy: Claude exhaustion pauses for supervision;
        // generic failover consent must not spend Codex allowance as a blind fallback.
        if core
            .work(&request.work_id)
            .and_then(|w| w.event.as_ref())
            .is_some_and(|e| {
                e.execution_id == cp.execution_id
                    && e.identity.provider == Provider::Claude
                    && matches!(
                        e.failure,
                        pf::Failure::Quota { .. } | pf::Failure::QuotaUnspecified
                    )
            })
            && pool.identity.provider != Provider::Claude
        {
            return Ok(stopped(hold("claude_quota_pause_requires_supervisor")));
        }
        (candidate, pool, previous_transition)
    };
    if request.permit.candidate != candidate
        || candidate.model == "gpt-6-astra"
        || !request.permit.budget_granted
        || !request.permit.global_lane_granted
        || request.permit.observed_at_ms > time
        || time >= request.permit.valid_until_ms
        || request.profile.model_id.as_deref() != Some(&candidate.model)
        || request.profile.reasoning_id.as_deref() != Some(&candidate.effort)
        || candidate.service_tier != "standard"
    {
        return Ok(stopped(hold("fresh_budget_lane_selected_profile_required")));
    }
    request.actions.validate(&candidate, cp)?;
    if request.readiness_scope.authorized_actions != actions_digest(&request.actions)?
        || request.readiness_scope.effective_permissions != request.profile_digest
        || request.readiness_scope.qualification_version != candidate.qualification_version
    {
        return Ok(stopped(hold(
            "readiness_actions_profile_or_qualification_changed",
        )));
    }
    let Some(mut agent) =
        ExecutorConfigs::get_cached().get_coding_agent(&request.profile.profile_id())
    else {
        return Ok(stopped(hold("explicit_provider_profile_missing")));
    };
    agent.apply_overrides(&request.profile);
    let executor =
        match (&pool.identity.provider, &agent) {
            (Provider::Claude, CodingAgent::ClaudeCode(native)) => {
                let auth = request
                    .claude
                    .as_ref()
                    .ok_or_else(|| held("Claude native subscription receipt missing"))?;
                claude::consideration(
                    &auth.login,
                    &auth.trial,
                    &pool.identity,
                    &auth.launcher_digest,
                    &auth.os_user,
                    time,
                )?;
                claude::candidate_allowed(&candidate, request.task_qualified)?;
                claude::pool_allowed(&pool, &auth.login, time)?;
                claude::launch_safety(
                    &auth.launch_safety,
                    &auth.login,
                    &request.profile_digest,
                    &cp.workspace_snapshot,
                    time,
                )?;
                claude::validate_profile(&native.provider_profile_facts(
                    request.profile.variant.as_deref().unwrap_or("DEFAULT"),
                ))?;
                "CLAUDE_CODE"
            }
            (Provider::Codex, CodingAgent::Codex(_)) if candidate.model == "gpt-6.1-sol" => {
                // Codex retains its native approval/sandbox guards. Unintercepted external
                // commands cannot silently inherit Claude's exact-effect capability.
                if !request.actions.effects.is_empty() {
                    return Ok(stopped(hold("codex_external_effect_fence_not_qualified")));
                }
                "CODEX"
            }
            _ => return Ok(stopped(hold("provider_adapter_unavailable"))),
        };
    if executors::original_worker::profile_digest(&agent)? != request.profile_digest {
        return Ok(stopped(hold("effective_profile_changed")));
    }
    // The concrete sealed Git contract and CU reader run UNDER the existing
    // admission lock, before any reservation/claim/provider start. Readiness is
    // not remote coverage; preserve the separate verify_provider_checkpoint proof.
    let expected_checkpoint = format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(cp).map_err(|_| held("Invalid checkpoint"))?)
    );
    let context = &request.git_dispatch_context;
    if context["permissions_digest"].as_str()
        != Some(request.readiness_scope.authorized_actions.as_str())
        || context["profile_digest"].as_str() != Some(request.profile_digest.as_str())
        || context["toolchain_digest"].as_str() != Some(request.readiness_scope.toolchain.as_str())
        || context["checkpoint_digest"].as_str() != Some(expected_checkpoint.as_str())
        || context["ownership_fence"].as_str() != Some(request.boundary.ownership_fence.as_str())
    {
        return Err(ContainerError::ReadinessBlocked(
            serde_json::json!({"version":2,"state":"blocked",
            "workspace":workspace_id,"turn":previous,"code":"permissions_required",
            "action":"bind_trusted_task_actions_profile_toolchain_and_checkpoint","provider_started":false,"coverage_verified":false}),
        ));
    }
    let git_context =
        serde_json::json!({"require_dispatch_context":true,"dispatch_context":context});
    let git_readiness =
        super::provider_receipts::git(container, previous, git_context.clone(), true).await?;
    let cu_observation=super::provider_receipts::cu(pool.identity.provider.clone(),Some(&pool.identity.pool_id),Some(&pool.source_receipt),Some(&candidate.model)).await
        .map_err(|_|ContainerError::ReadinessBlocked(serde_json::json!({"version":2,"state":"blocked",
            "workspace":workspace_id,"turn":previous,"code":"cu_observation_unavailable",
            "action":"inspect_existing_cu_observation_service","provider_started":false,"coverage_verified":false})))?;
    super::provider_receipts::require_cu(&cu_observation, workspace_id, previous)?;
    if let Some(old) = provider_handoff::owner(&container.db().pool, workspace_id).await? {
        if previous_transition.as_deref() != Some(&old.transition_id)
            || old.next_execution_id != previous
        {
            return Ok(stopped(hold("durable_owner_requires_recovery")));
        }
        let state = provider_handoff::reconcile(&container.db().pool, &old, true).await?;
        if state != "terminal_checkpoint_verified" {
            return Ok(stopped(hold(state)));
        }
    } else if previous_transition.is_some() {
        return Ok(stopped(hold(
            "durable_reservation_missing_no_reconstruction",
        )));
    }
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: claude::handoff_prompt_with_actions(cp, &request.actions)?,
            executor_config: request.profile,
            working_dir: parent_session.agent_working_dir.clone(),
        }),
        None,
    );
    let action_json =
        serde_json::to_string(&action).map_err(|_| held("Cannot serialize provider action"))?;
    let execution_id = uuid(&request.permit.execution_id)?;
    let session_id = Uuid::new_v4();
    provider_handoff::reserve(
        &container.db().pool,
        Reservation {
            transition: &request.permit.transition_id,
            workspace: workspace_id,
            previous,
            session: session_id,
            execution: execution_id,
            action: &action_json,
            snapshot: &cp.workspace_snapshot,
            ownership_fence: &request.boundary.ownership_fence,
            executor,
            previous_transition: previous_transition.as_deref(),
            working_dir: parent_session.agent_working_dir.as_deref(),
        },
    )
    .await?;
    let transition = request.permit.transition_id.clone();
    let result = async {
        // Recheck volatile preservation AFTER exclusive SQL ownership. Recheck the
        // authority's dependency scope too; a prior cached Ready is not permission.
        if let Err(error) = container.verify_provider_checkpoint(cp).await {
            tracing::warn!(%error,"Provider checkpoint preflight failed; no inference");
            return Err(held("preservation_checkpoint_unverified"));
        }
        // Reuse is only valid for the SAME exact execution and trusted context.
        // The owning helper re-reads inventory/policy/native snapshots; 30 seconds
        // is a maximum receipt lifetime, never an assumed filesystem/credit lock.
        let mut recheck = git_context.clone();
        recheck["readiness_receipt"] = git_readiness["receipt"].clone();
        super::provider_receipts::git(container, previous, recheck, true).await?;
        if !matches!(
            readiness::check(request.readiness.as_ref(), &request.readiness_scope, now()?),
            Readiness::Ready { .. }
        ) {
            return Err(held(
                "Trusted task permission/admission proof expired under reservation",
            ));
        }
        let observed = super::provider_receipts::cu(
            pool.identity.provider.clone(),
            Some(&pool.identity.pool_id),
            Some(&pool.source_receipt),
            Some(&candidate.model),
        )
        .await
        .map_err(|_| held("CU revalidation unavailable; reservation retained"))?;
        super::provider_receipts::require_cu(&observed, workspace_id, previous)?;
        let evidence_deadline_ms = request
            .permit
            .valid_until_ms
            .min(request.boundary.valid_until_ms)
            .min(
                request
                    .readiness
                    .as_ref()
                    .ok_or_else(|| held("Readiness receipt missing"))?
                    .valid_until_ms,
            )
            .min(pool.valid_until_ms)
            .min(
                observed["quotaExpiresAtMs"]
                    .as_u64()
                    .ok_or_else(|| held("Quota expiry unknown"))?,
            )
            .min(
                (git_readiness["receipt"]["valid_until"]
                    .as_f64()
                    .ok_or_else(|| held("Git expiry unknown"))?
                    * 1000.0) as u64,
            );

        {
            let mut core = c.lock().map_err(|_| held("Controller poisoned"))?;
            if previous_transition.is_some() {
                core.claim_boundary(
                    &request.work_id,
                    cp.clone(),
                    request.permit,
                    request.boundary,
                    now()?,
                )?;
            } else {
                core.claim(&request.work_id, request.permit, request.boundary, now()?)?;
            }
            core.authorize_actions(&request.work_id, request.actions)?;
        }
        let observer = if executor == "CLAUDE_CODE" {
            pf::observer::register_initial_claude(
                &c,
                &request.work_id,
                &execution_id.to_string(),
                pool.identity,
                &request.profile_digest,
            )?
        } else {
            pf::observer::register_initial_codex(
                &c,
                &request.work_id,
                &execution_id.to_string(),
                pool.identity,
                &request.profile_digest,
            )?
        };
        if !provider_handoff::dispatching(&container.db().pool, &transition).await? {
            return Err(held("Dispatch already attempted; reconcile exact identity"));
        }
        observer.retain_until_terminal();
        let session = Session::find_by_id(&container.db().pool, session_id)
            .await?
            .ok_or_else(|| held("Reserved session missing"))?;
        LAUNCH
            .scope(
                Launch {
                    workspace: workspace_id,
                    session: session_id,
                    execution: execution_id,
                    action: action_json,
                    evidence_deadline_ms,
                },
                container.start_execution(
                    &workspace,
                    &session,
                    &action,
                    &ExecutionProcessRunReason::CodingAgent,
                ),
            )
            .await
    }
    .await;
    provider_handoff::outcome(
        &container.db().pool,
        &transition,
        if result.is_ok() { "running" } else { "held" },
        if result.is_ok() {
            "launch returned; native settings observed separately"
        } else {
            "launch outcome requires exact reconciliation; no retry"
        },
    )
    .await?;
    result.map(|p| Outcome::Started { execution_id: p.id })
}
