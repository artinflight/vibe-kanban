//! Comparable capacity is measured accepted-work headroom for this exact envelope,
//! never provider percentages, credits, model preference ranks or reset clocks.
use super::*;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Capacity {
    pub candidate: Candidate,
    pub generation: String,
    pub source_receipt: String,
    pub calibration_receipt: String,
    /// Same measured reference workload + version across providers, or incomparable.
    pub reference_work: String,
    pub calibration_version: String,
    pub sample_count: u32,
    /// Conservative count of the reference work that the tightest applicable
    /// provider window can support; the authority retains its raw native units.
    pub remaining_work: u64,
    pub applicable_windows: Vec<String>,
    pub economical: bool,
    pub cost_constraint_receipt: String,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
}
impl Controller {
    pub fn observe_capacity(&mut self, v: Capacity) -> io::Result<()> {
        let p = self
            .pool(&v.candidate.pool_id)
            .ok_or_else(|| invalid("Unknown capacity pool"))?;
        let mut windows = v.applicable_windows.clone();
        windows.sort();
        let mut actual: Vec<_> = p.windows.iter().map(|w| w.id.clone()).collect();
        actual.sort();
        if v.generation != p.generation
            || !present(&v.source_receipt)
            || !present(&v.calibration_receipt)
            || !present(&v.reference_work)
            || !present(&v.calibration_version)
            || !present(&v.cost_constraint_receipt)
            || v.sample_count == 0
            || windows != actual
            || !p.windows_complete
            || v.observed_at_ms < p.observed_at_ms
            || v.observed_at_ms >= v.valid_until_ms
            || v.valid_until_ms > p.valid_until_ms
        {
            return Err(invalid(
                "Capacity requires measured, versioned, complete-window evidence",
            ));
        }
        let key = serde_json::to_string(&v.candidate)?;
        if let Some(old) = self.state.capacities.get(&key) {
            if old.observed_at_ms > v.observed_at_ms
                || (old.observed_at_ms == v.observed_at_ms && old != &v)
            {
                return Err(invalid("Older/conflicting capacity evidence"));
            }
        }
        let mut next = self.state.clone();
        next.last_now_ms = next.last_now_ms.max(v.observed_at_ms);
        next.capacities.insert(key, v);
        self.commit(next)
    }
    fn capacity(&self, c: &Candidate, now: u64) -> Option<&Capacity> {
        let p = self.pool(&c.pool_id)?;
        self.state
            .capacities
            .get(&serde_json::to_string(c).ok()?)
            .filter(|v| {
                v.generation == p.generation
                    && v.observed_at_ms >= p.observed_at_ms
                    && v.observed_at_ms <= now
                    && now < v.valid_until_ms
            })
    }
    pub(super) fn select(
        &self,
        _w: &Work,
        choices: &mut Vec<Candidate>,
        now: u64,
    ) -> Result<(), &'static str> {
        // Explicitly uneconomical/zero measured capacity cannot sneak back through
        // the unknown bucket. Stale evidence is unknown, never measured availability.
        choices.retain(|c| {
            self.capacity(c, now)
                .is_none_or(|v| v.economical && v.remaining_work > 0)
        });
        let measured: Vec<_> = choices
            .iter()
            .filter_map(|c| self.capacity(c, now))
            .collect();
        if let Some(first) = measured.first() {
            if measured.iter().any(|v| {
                v.reference_work != first.reference_work
                    || v.calibration_version != first.calibration_version
            }) {
                return Err("capacity_measurements_incomparable");
            }
        }
        choices.sort_by_key(|c| {
            let v = self.capacity(c, now);
            // Verified available headroom always precedes unknown/stale. Sol is the
            // default/tie preference, not an unconditional reset-return target.
            (
                v.is_none(),
                std::cmp::Reverse(v.map_or(0, |v| v.remaining_work)),
                c.model != "gpt-6.1-sol",
                c.rank,
                c.model.clone(),
                c.effort.clone(),
                c.pool_id.clone(),
            )
        });
        Ok(())
    }
    /// Re-evaluate ONLY after the current owner stopped. At most one follow-up
    /// selection after the initial alternate; no timer, interruption or bounce loop.
    pub fn boundary_plan(&self, id: &str, cp: &Checkpoint, now: u64) -> Plan {
        if self.state.completed_works.contains_key(id) {
            return hold("work_completed");
        }
        if self.poisoned || now < self.state.last_now_ms {
            return hold("journal_or_clock_recovery_required");
        }
        let Some(w) = self.work(id) else {
            return hold("unknown_work");
        };
        let t = match &w.phase {
            Phase::Running(t) | Phase::DispatchPending(t) => t,
            _ => return hold("no_alternate_boundary"),
        };
        if w.attempts >= 2 {
            return hold("boundary_attempt_exhausted");
        }
        if w.native_goal_active || w.policy.mode == Mode::Manual {
            return hold("manual_or_goal_owner_pinned");
        }
        if cp.execution_id != t.execution_id
            || cp.workspace_id != w.workspace_id
            || cp.objective != w.objective
            || !present(&cp.workspace_snapshot)
            || !present(&cp.branch)
            || !Path::new(&cp.workspace_path).is_absolute()
            || cp.context.len() > 16_000
            || cp.completed_steps.len() > 100
            || cp.pending_steps.len() > 100
            || cp.pending_steps.is_empty()
            || !cp.all_workers_terminal
            || !present(&cp.terminal_receipt)
            || !self.ended_safely(&t.execution_id)
            || self.state.adapter_holds.contains_key(&t.execution_id)
            || cp.failed_validation
            || !cp.pending_approvals.is_empty()
            || !cp.effects_complete
            || self
                .state
                .tool_uses
                .values()
                .any(|v| v.execution_id == t.execution_id && !v.completed)
            || w.effects
                .values()
                .any(|e| e.outcome == EffectOutcome::Unknown || !cp.effects.contains(e))
            || cp
                .effects
                .iter()
                .any(|e| !present(&e.receipt) || e.outcome == EffectOutcome::Unknown)
        {
            return hold("boundary_checkpoint_required");
        }
        let native_started = w
            .launch_receipt
            .as_ref()
            .is_some_and(|r| r.execution_id == t.execution_id)
            || self.state.native_records.values().any(|r| {
                r.execution_id == t.execution_id
                    && r.signal.native_model.as_deref() == Some(&t.candidate.model)
                    && r.signal.native_session_id.is_some()
            });
        if !native_started {
            return hold("native_start_unverified");
        }
        if self
            .state
            .ended
            .get(&t.execution_id)
            .is_some_and(|e| e.exit_code != Some(0))
            && !w.event.as_ref().is_some_and(|e| {
                e.execution_id == t.execution_id
                    && matches!(
                        e.failure,
                        Failure::Quota { .. }
                            | Failure::QuotaUnspecified
                            | Failure::RateLimit
                            | Failure::Authentication
                            | Failure::Outage
                    )
            })
        {
            return hold("task_failure_requires_review");
        }
        let mut choices: Vec<_> = w
            .policy
            .candidates
            .iter()
            .chain(std::iter::once(&w.incumbent))
            .filter(|c| {
                c.qualified
                    && c.rank > 0
                    && c.model != "gpt-6-astra"
                    && c.scope_key == w.policy.scope_key
                    && c.qualification_version == w.policy.qualification_version
                    && !w.policy.excluded_models.contains(&c.model)
                    && w.policy.locked.as_ref().is_none_or(|l| l == *c)
                    && self.pool(&c.pool_id).is_some_and(|p| {
                        p.identity.provider != Provider::Antigravity && self.pool_ready(p, now)
                    })
            })
            .cloned()
            .collect();
        if let Err(reason) = self.select(w, &mut choices, now) {
            return hold(reason);
        }
        let Some(c) = choices.into_iter().next() else {
            return hold("no_authorized_qualified_provider");
        };
        if w.policy.mode == Mode::Recommend {
            Plan::Recommend(c)
        } else if !w.policy.failover_authorized {
            hold("failover_not_authorized")
        } else {
            Plan::Ready(c)
        }
    }
    pub fn claim_boundary(
        &mut self,
        id: &str,
        cp: Checkpoint,
        permit: Admission,
        boundary: Boundary,
        now: u64,
    ) -> io::Result<Transfer> {
        let Plan::Ready(c) = self.boundary_plan(id, &cp, now) else {
            return Err(invalid("Boundary not ready"));
        };
        self.claim_selected(id, c, cp, permit, boundary, now)
    }
    /// Explicit supervisor completion only, not an elapsed lease or inferred task
    /// success. Commit before DB release; replaying the same receipt is idempotent.
    pub fn finish(&mut self, id: &str, cp: &Checkpoint, receipt: &str) -> io::Result<()> {
        if let Some(old) = self.state.completed_works.get(id) {
            return if old == receipt {
                Ok(())
            } else {
                Err(invalid("Conflicting completion receipt"))
            };
        }
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        let execution = match &w.phase {
            Phase::Watching => &w.execution_id,
            Phase::Running(t) | Phase::DispatchPending(t) => &t.execution_id,
            _ => return Err(invalid("Finished phase")),
        };
        if !present(receipt)
            || execution != &cp.execution_id
            || w.workspace_id != cp.workspace_id
            || w.objective != cp.objective
            || !cp.pending_steps.is_empty()
            || !cp.pending_approvals.is_empty()
            || cp.failed_validation
            || !cp.all_workers_terminal
            || !self.ended_safely(execution)
            || !cp.effects_complete
            || !present(&cp.workspace_snapshot)
            || !present(&cp.terminal_receipt)
            || self.state.adapter_holds.contains_key(execution)
            || self
                .state
                .tool_uses
                .values()
                .any(|v| &v.execution_id == execution && !v.completed)
            || w.effects
                .values()
                .any(|e| e.outcome == EffectOutcome::Unknown || !cp.effects.contains(e))
            || cp
                .effects
                .iter()
                .any(|e| e.outcome == EffectOutcome::Unknown || !present(&e.receipt))
        {
            return Err(invalid(
                "Completion needs exact terminal accepted checkpoint and reconciled effects",
            ));
        }
        let mut next = self.state.clone();
        next.completed_works.insert(id.into(), receipt.into());
        self.commit(next)
    }
    /// Reopen/reconcile an exact attempted transfer; never issue another claim or
    /// replace identities. DB and worker evidence are supplied independently by host.
    pub fn transfer(&self, transition: &str) -> Option<&Transfer> {
        self.state.transfers.get(transition).or_else(|| {
            self.state.works.values().find_map(|w| match &w.phase {
                Phase::DispatchPending(t) | Phase::Running(t) | Phase::Finished(t)
                    if t.transition_id == transition =>
                {
                    Some(t)
                }
                _ => None,
            })
        })
    }
}
