//! Read actual durable native/effect evidence. This is NOT a lifetime fence:
//! the trusted host must separately prove independent jobs/effects are closed.
use super::*;
impl Controller {
    /// Explicit continuation still cannot invent qualification, drop a lock or
    /// bypass an exclusion/native-goal owner. This is not a quota/admission grant.
    pub fn continuation_candidate(&self, id: &str, candidate: &Candidate) -> io::Result<()> {
        let w = self
            .work(id)
            .ok_or_else(|| invalid("Unknown checkpoint owner"))?;
        if w.native_goal_active
            || !candidate.qualified
            || candidate.rank == 0
            || matches!(candidate.model.as_str(), "gpt-6-astra" | "gpt-6-astra-fast")
            || candidate.scope_key != w.policy.scope_key
            || candidate.qualification_version != w.policy.qualification_version
            || w.policy.excluded_models.contains(&candidate.model)
            || w.policy
                .locked
                .as_ref()
                .is_some_and(|locked| locked != candidate)
            || (candidate != &w.incumbent && !w.policy.candidates.contains(candidate))
            || !self
                .pool(&candidate.pool_id)
                .is_some_and(|p| p.identity.provider != Provider::Antigravity)
        {
            return Err(invalid(
                "Checkpoint destination violates qualification or manual constraints",
            ));
        }
        Ok(())
    }
    pub fn continuation_evidence(&self, id: &str, cp: &Checkpoint) -> io::Result<Vec<u8>> {
        let w = self
            .work(id)
            .ok_or_else(|| invalid("Unknown checkpoint owner"))?;
        let execution = match &w.phase {
            Phase::Watching => &w.execution_id,
            Phase::Running(t) => &t.execution_id,
            // Pending dispatch is uncertain even if a terminal DB row exists.
            _ => return Err(invalid("Checkpoint dispatch outcome uncertain")),
        };
        if w.native_goal_active
            || execution != &cp.execution_id
            || w.workspace_id != cp.workspace_id
            || w.objective != cp.objective
            || !cp.all_workers_terminal
            || !cp.effects_complete
            || cp.failed_validation
            || w.event
                .as_ref()
                .is_some_and(|e| matches!(e.failure, Failure::TaskFailure | Failure::Unknown))
            || !cp.pending_approvals.is_empty()
            || !present(&cp.terminal_receipt)
            || cp.context.len() > 16_000
            || cp.completed_steps.len() > 100
            || cp.pending_steps.len() > 100
            || cp.effects.len() > 100
            || !self.ended_safely(execution)
            || self.state.adapter_holds.contains_key(execution)
        {
            return Err(invalid("Trusted terminal checkpoint incomplete"));
        }
        let mut ids = std::collections::BTreeSet::new();
        if cp.effects.iter().any(|e| {
            !ids.insert(&e.id)
                || !present(&e.id)
                || !present(&e.receipt)
                || e.outcome == EffectOutcome::Unknown
        }) || w.effects.values().any(|e| !cp.effects.contains(e))
        {
            return Err(invalid("Effect outcome missing or changed"));
        }
        let tools: Vec<_> = self
            .state
            .tool_uses
            .values()
            .filter(|t| &t.execution_id == execution)
            .collect();
        if tools.iter().any(|t| {
            !t.completed
                || !t.source_receipt.as_deref().is_some_and(present)
                || t.reconciled_outcome == Some(EffectOutcome::Unknown)
        }) {
            return Err(invalid("Native tool outcome unresolved"));
        }
        let native: Vec<_> = self
            .state
            .native_records
            .values()
            .filter(|r| &r.execution_id == execution)
            .collect();
        if !cp.native_thread_id.as_deref().is_some_and(present)
            || !native.iter().any(|r| {
                r.work_id == id
                    && r.signal.native_session_id == cp.native_thread_id
                    && (cp.native_turn_id.is_none() || r.signal.native_turn_id == cp.native_turn_id)
            })
        {
            return Err(invalid("Actual native checkpoint binding missing"));
        }
        // Unrelated quota observations do not refresh or invalidate this witness.
        Ok(serde_json::to_vec(&(
            w,
            cp,
            self.ended_receipt(execution),
            tools,
            native,
        ))?)
    }
}
