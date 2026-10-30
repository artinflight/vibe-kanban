//! Backend-only bridge from the existing trusted host/controller to T67's opaque
//! reference. No HTTP mint endpoint and no authority from client summaries/flags.
use db::models::provider_admission::checkpoint as store;
use executors::{model_selector::PermissionPolicy, provider_failover as pf};

use super::*;

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Evidence {
    version: String,
    checkpoint: pf::Checkpoint,
    source_native: String,
    controller_digest: String,
    generation: String,
    activation_source: String,
    profile: String,
    // Trusted host lifetime authority, NOT Git readiness or the local exit flag.
    fence: String,
    observed_at_ms: u64,
    valid_until_ms: u64,
}
fn now() -> Result<u64, ContainerError> {
    chrono::Utc::now()
        .timestamp_millis()
        .try_into()
        .map_err(|_| error("invalid_clock"))
}
fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn lifetime(
    b: &pf::Boundary,
    cp: &pf::Checkpoint,
    work: &str,
    time: u64,
) -> Result<(), ContainerError> {
    if b.work_id != work
        || b.previous_execution_id != cp.execution_id
        || b.workspace_id != cp.workspace_id
        || b.workspace_snapshot != cp.workspace_snapshot
        || b.terminal_receipt != cp.terminal_receipt
        || b.ownership_fence.trim().is_empty()
        || !b.all_workers_terminal
        || !b.effects_reconciled
        || b.observed_at_ms > time
        || time >= b.valid_until_ms
        || b.valid_until_ms.saturating_sub(b.observed_at_ms) > 30_000
    {
        return Err(error("independent_job_lifetime_or_effect_fence_unproven"));
    }
    Ok(())
}
async fn source<C: ContainerService + ?Sized>(
    c: &C,
    cp: &pf::Checkpoint,
    own: Option<Uuid>,
) -> Result<String, ContainerError> {
    let execution = Uuid::parse_str(&cp.execution_id).map_err(|_| error("invalid_checkpoint"))?;
    let workspace = Uuid::parse_str(&cp.workspace_id).map_err(|_| error("invalid_checkpoint"))?;
    let latest:Option<Uuid>=sqlx::query_scalar("SELECT e.id FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.run_reason='codingagent' AND e.dropped=0 AND (? IS NULL OR e.id!=?) ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1")
        .bind(workspace).bind(own).bind(own).fetch_optional(&c.db().pool).await?;
    if latest != Some(execution) {
        return Err(error("source_checkpoint_superseded"));
    }
    let native = CodingAgentTurn::find_by_execution_process_id(&c.db().pool, execution)
        .await?
        .ok_or_else(|| error("source_native_binding_missing"))?;
    // agent_message_id is a resume/message anchor, not a provider-native turn ID.
    // Keep both independent: the controller verifies actual native turn provenance.
    if native.agent_session_id.is_none() || native.agent_session_id != cp.native_thread_id {
        return Err(error("source_native_binding_changed"));
    }
    c.verify_provider_checkpoint_at(cp, own).await?;
    Ok(hash(&json!([
        execution,
        native.agent_session_id,
        native.agent_message_id
    ])))
}
/// Called at the existing terminal/recovery boundary ONLY after the host's actual
/// prepare_provider_dispatch succeeds. Default producer still holds; a parent
/// ended flag/client-supplied text can never reach this publisher.
pub async fn publish<C: ContainerService + ?Sized>(
    c: &C,
    destination: Uuid,
    request: &crate::services::provider_failover::DispatchRequest,
) -> Result<String, ContainerError> {
    let time = now()?;
    let cp = &request.checkpoint;
    lifetime(&request.boundary, cp, &request.work_id, time)?;
    if !matches!(
        pf::readiness::check(request.readiness.as_ref(), &request.readiness_scope, time),
        pf::readiness::Readiness::Ready { .. }
    ) || !request.task_qualified
        || request.profile.permission_policy != Some(PermissionPolicy::Supervised)
        || request.readiness_scope.workspace_id != cp.workspace_id
        || request.readiness_scope.execution_id != cp.execution_id
        || request.readiness_scope.snapshot_receipt != cp.workspace_snapshot
    {
        return Err(error(
            "trusted_checkpoint_scope_permissions_or_readiness_unproven",
        ));
    }
    // Existing resume paths do not install the old initial-only exact external
    // effect guard. Do not silently remove it or permanently restrict local coding
    // to read-only: file implementation is eligible, external-effect handoff holds.
    if !cp.effects.is_empty() || !request.actions.effects.is_empty() {
        return Err(error(
            "destination_resume_external_effect_fence_unqualified",
        ));
    }
    let pool = &c.db().pool;
    let s = Session::find_by_id(pool, destination)
        .await?
        .ok_or_else(|| error("stale_binding"))?;
    if s.workspace_id.to_string() != cp.workspace_id {
        return Err(error("stale_binding"));
    }
    let t = super::target(c, &s, None, None).await?;
    if t.unrelated_owner_conflict
        || !matches!(
            t.status.as_str(),
            "ready" | "checkpoint_required" | "owner_conflict"
        )
        || t.blocker_code.is_some()
        || (t.predecessor_execution_id.is_some() && t.native_binding_sha256.is_none())
    {
        return Err(error("checkpoint_destination_blocked"));
    }
    let config = t
        .selected
        .as_ref()
        .ok_or_else(|| error("saved_selection_required"))?;
    if selected_profile(config)?
        .get_preset_options()
        .permission_policy
        != Some(PermissionPolicy::Supervised)
    {
        return Err(error("effective_supervised_destination_required"));
    }
    if recommend(request.profile.clone()) != *config
        || request.profile_digest != t.profile_pin.clone().unwrap_or_default()
        || request.readiness_scope.authorized_actions
            != crate::services::provider_failover::actions_digest(&request.actions)?
    {
        return Err(error("checkpoint_destination_qualification_changed"));
    }
    // Reuse the concrete Git contract, not a second inventory/permission protocol.
    // This proves Git readiness only; the independent lifetime fence above is
    // separate and must remain held through the atomic reservation.
    let context = &request.git_dispatch_context;
    let checkpoint_digest = format!(
        "sha256:{}",
        digest(&serde_json::to_vec(cp).map_err(|_| error("invalid_checkpoint"))?)
    );
    if context["permissions_digest"].as_str()
        != Some(request.readiness_scope.authorized_actions.as_str())
        || context["profile_digest"].as_str() != Some(request.profile_digest.as_str())
        || context["toolchain_digest"].as_str() != Some(request.readiness_scope.toolchain.as_str())
        || context["checkpoint_digest"].as_str() != Some(checkpoint_digest.as_str())
        || context["ownership_fence"].as_str() != Some(request.boundary.ownership_fence.as_str())
    {
        return Err(error("checkpoint_trusted_action_context_missing"));
    }
    crate::services::provider_receipts::git(
        c,
        Uuid::parse_str(&cp.execution_id).map_err(|_| error("invalid_checkpoint"))?,
        json!({"require_dispatch_context":true,"dispatch_context":context}),
        true,
    )
    .await?;
    let a = db::models::provider_handoff::activation(pool, s.workspace_id)
        .await?
        .ok_or_else(|| error("trusted_checkpoint_owner_missing"))?;
    if a.state != "active"
        || a.work_id != request.work_id
        || a.owner_generation != request.readiness_scope.owner_generation
    {
        return Err(error("trusted_checkpoint_owner_changed"));
    }
    let legacy = db::models::provider_handoff::owner(pool, s.workspace_id).await?;
    if legacy.as_ref().is_some_and(|r| {
        r.state != "checkpoint_required" || r.next_execution_id.to_string() != cp.execution_id
    }) {
        return Err(error("uncertain_dispatch_owner_retained"));
    }
    request.actions.validate(&request.permit.candidate, cp)?;
    crate::services::provider_failover::continuation_candidate(
        &a.journal_root,
        &a.work_id,
        &request.permit.candidate,
    )?;
    let effective = selected_profile(config)?.get_preset_options();
    if effective.model_id.as_deref() != Some(request.permit.candidate.model.as_str())
        || effective.reasoning_id.as_deref() != Some(request.permit.candidate.effort.as_str())
    {
        return Err(error("checkpoint_qualified_model_effort_mismatch"));
    }
    let source_native = source(c, cp, None).await?;
    let bytes =
        crate::services::provider_failover::continuation_evidence(&a.journal_root, &a.work_id, cp)?;
    let evidence = Evidence {
        version: CONTRACT.into(),
        checkpoint: cp.clone(),
        source_native,
        controller_digest: digest(&bytes),
        generation: source_generation().into(),
        activation_source: a.source_receipt,
        profile: t
            .profile_pin
            .clone()
            .ok_or_else(|| error("saved_profile_missing"))?,
        fence: request.boundary.ownership_fence.clone(),
        observed_at_ms: request.boundary.observed_at_ms,
        valid_until_ms: request.boundary.valid_until_ms,
    };
    let payload = serde_json::to_string(&evidence).map_err(|_| error("invalid_checkpoint"))?;
    if payload.len() > 262_144 {
        return Err(error("bounded_checkpoint_exceeded"));
    }
    // Include destination and state in identity, not just a source summary hash.
    let reference = format!(
        "checkpoint:{}",
        hash(&json!([
            payload,
            s.id,
            t.state_token,
            a.work_id,
            a.owner_generation
        ]))
    );
    // Async preservation/permission inspection must not refresh old evidence.
    lifetime(&request.boundary, cp, &request.work_id, now()?)?;
    if !matches!(
        pf::readiness::check(request.readiness.as_ref(), &request.readiness_scope, now()?),
        pf::readiness::Readiness::Ready { .. }
    ) {
        return Err(error("trusted_checkpoint_readiness_expired"));
    }
    store::publish(
        pool,
        &store::Checkpoint {
            reference: reference.clone(),
            workspace_id: s.workspace_id,
            source_execution_id: Uuid::parse_str(&cp.execution_id)
                .map_err(|_| error("invalid_checkpoint"))?,
            destination_session_id: s.id,
            target_token: t.state_token,
            work_id: a.work_id,
            owner_generation: a.owner_generation,
            legacy_transition: legacy.map(|r| r.transition_id),
            evidence: payload,
            valid_until_ms: evidence
                .valid_until_ms
                .try_into()
                .map_err(|_| error("invalid_clock"))?,
            claimed_request: None,
        },
    )
    .await?;
    Ok(reference)
}
/// Reload persisted backend evidence and recheck real source/native/capture/jobs
/// before claim AND after asynchronous setup. A reference is never a grant itself.
pub async fn verify<C: ContainerService + ?Sized>(
    c: &C,
    t: &Target,
    reference: &str,
    own: Option<Uuid>,
) -> Result<Evidence, ContainerError> {
    if reference.len() > 256
        || (t.predecessor_execution_id.is_some() && t.native_binding_sha256.is_none())
    {
        return Err(error("invalid_checkpoint_or_destination_native_binding"));
    }
    let row = store::get(&c.db().pool, reference)
        .await?
        .ok_or_else(|| error("checkpoint_missing"))?;
    let e: Evidence =
        serde_json::from_str(&row.evidence).map_err(|_| error("invalid_checkpoint"))?;
    let time = now()?;
    if row.workspace_id != t.workspace_id
        || row.destination_session_id != t.session_id
        || row.target_token != t.state_token
        || e.generation != source_generation()
        || e.version != CONTRACT
        || e.observed_at_ms > time
        || time >= e.valid_until_ms
        || e.valid_until_ms.saturating_sub(e.observed_at_ms) > 30_000
        || row.valid_until_ms
            != i64::try_from(e.valid_until_ms).map_err(|_| error("invalid_clock"))?
        || e.profile != t.profile_pin.clone().unwrap_or_default()
        || e.fence.trim().is_empty()
        || e.checkpoint.execution_id != row.source_execution_id.to_string()
        || e.checkpoint.workspace_id != t.workspace_id.to_string()
        || !e.checkpoint.effects.is_empty()
    {
        return Err(error("stale_checkpoint"));
    }
    match (row.claimed_request, own) {
        (None, None) => {}
        (Some(request), Some(execution)) => {
            let owner = super::store::owner(&c.db().pool, t.workspace_id)
                .await?
                .ok_or_else(|| error("owner_conflict"))?;
            if owner.request_id != request
                || owner.execution_id != execution
                || !matches!(owner.status.as_str(), "reserved" | "dispatching")
            {
                return Err(error("owner_conflict"));
            }
        }
        _ => return Err(error("checkpoint_already_claimed")),
    }
    let a:Option<(String,String,String,String,String)>=sqlx::query_as("SELECT work_id,owner_generation,journal_root,source_receipt,state FROM provider_failover_activations WHERE workspace_id=?")
        .bind(t.workspace_id).fetch_optional(&c.db().pool).await?;
    let (work, generation, root, activation_source, state) =
        a.ok_or_else(|| error("checkpoint_owner_missing"))?;
    if work != row.work_id
        || generation != row.owner_generation
        || activation_source != e.activation_source
        || state != if own.is_some() { "released" } else { "active" }
    {
        return Err(error("checkpoint_owner_changed"));
    }
    let legacy = db::models::provider_handoff::owner(&c.db().pool, t.workspace_id).await?;
    if own.is_none() {
        if legacy.as_ref().map(|r| r.transition_id.as_str()) != row.legacy_transition.as_deref()
            || legacy.as_ref().is_some_and(|r| {
                r.state != "checkpoint_required" || r.next_execution_id != row.source_execution_id
            })
        {
            return Err(error("uncertain_dispatch_owner_retained"));
        }
    } else if legacy.is_some() {
        return Err(error("owner_conflict"));
    }
    let w = Workspace::find_by_id(&c.db().pool, t.workspace_id)
        .await?
        .ok_or_else(|| error("stale_binding"))?;
    c.verify_provider_continuation_boundary(&w, own).await?;
    if source(c, &e.checkpoint, own).await? != e.source_native
        || digest(&crate::services::provider_failover::continuation_evidence(
            &root,
            &work,
            &e.checkpoint,
        )?) != e.controller_digest
    {
        return Err(error("checkpoint_evidence_changed"));
    }
    if now()? >= e.valid_until_ms {
        return Err(error("trusted_checkpoint_expired_during_recheck"));
    }
    Ok(e)
}
pub(super) fn handoff(e: &Evidence, prompt: String) -> Result<String, ContainerError> {
    // Native IDs deliberately excluded. Native action construction keeps the
    // destination's own existing ID and never forks/resets/truncates history.
    let cp = &e.checkpoint;
    let context = json!({"objective":cp.objective,"context":cp.context,"workspace":cp.workspace_path,
        "branch":cp.branch,"snapshot":cp.workspace_snapshot,"completed":cp.completed_steps,
        "pending":cp.pending_steps,"pending_approvals":cp.pending_approvals});
    Ok(format!(
        "Verified compact task handoff; preserve completed work and existing approvals.\n{}\nCurrent instruction:\n{}",
        serde_json::to_string(&context).map_err(|_| error("invalid_checkpoint"))?,
        prompt
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn cp() -> pf::Checkpoint {
        pf::Checkpoint {
            execution_id: "source".into(),
            objective: "approved task".into(),
            context: "compact source context".into(),
            workspace_id: "workspace".into(),
            workspace_path: "/synthetic/repo".into(),
            branch: "feature".into(),
            workspace_snapshot: "snapshot".into(),
            completed_steps: vec!["existing edit".into()],
            pending_steps: vec!["review".into()],
            pending_approvals: vec![],
            effects: vec![],
            all_workers_terminal: true,
            terminal_receipt: "native-ended".into(),
            effects_complete: true,
            failed_validation: false,
            native_thread_id: Some("SOURCE-NATIVE-DO-NOT-RESUME".into()),
            native_turn_id: Some("SOURCE-TURN".into()),
        }
    }
    fn fence() -> pf::Boundary {
        pf::Boundary {
            work_id: "work".into(),
            previous_execution_id: "source".into(),
            workspace_id: "workspace".into(),
            workspace_snapshot: "snapshot".into(),
            terminal_receipt: "native-ended".into(),
            ownership_fence: "synthetic:separate-job-lifetime-authority".into(),
            all_workers_terminal: true,
            effects_reconciled: true,
            observed_at_ms: 1000,
            valid_until_ms: 2000,
        }
    }
    #[test]
    fn trusted_bridge_lifetime_never_accepts_parent_flag_alone_or_expired_fence() {
        let cp = cp();
        let mut b = fence();
        b.ownership_fence.clear();
        assert!(lifetime(&b, &cp, "work", 1500).is_err());
        b = fence();
        b.effects_reconciled = false;
        assert!(lifetime(&b, &cp, "work", 1500).is_err());
        b = fence();
        assert!(lifetime(&b, &cp, "work", 999).is_err());
        assert!(lifetime(&b, &cp, "work", 1999).is_ok());
        assert!(lifetime(&b, &cp, "work", 2000).is_err());
    }
    #[test]
    fn trusted_bridge_lifetime_identity_and_snapshot_are_exact() {
        let cp = cp();
        let mut b = fence();
        b.workspace_snapshot = "different dirty tree".into();
        assert!(lifetime(&b, &cp, "work", 1500).is_err());
        b = fence();
        assert!(lifetime(&b, &cp, "other-owner", 1500).is_err());
        b.valid_until_ms = 40_000;
        assert!(lifetime(&b, &cp, "work", 1500).is_err());
    }
    #[test]
    fn trusted_bridge_compact_handoff_keeps_work_but_never_cross_resumes_source_ids() {
        let e = Evidence {
            version: CONTRACT.into(),
            checkpoint: cp(),
            source_native: "source-binding".into(),
            controller_digest: "digest".into(),
            generation: "generation".into(),
            activation_source: "activation".into(),
            profile: "profile".into(),
            fence: "fence".into(),
            observed_at_ms: 1000,
            valid_until_ms: 2000,
        };
        let prompt = handoff(&e, "Continue approved source changes".into()).unwrap();
        assert!(prompt.contains("existing edit"));
        assert!(prompt.contains("compact source context"));
        assert!(prompt.contains("Continue approved source changes"));
        assert!(!prompt.contains("SOURCE-NATIVE-DO-NOT-RESUME"));
        assert!(!prompt.contains("SOURCE-TURN"));
    }
}
