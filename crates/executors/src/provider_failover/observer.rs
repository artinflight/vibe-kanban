//! Dormant native/lifecycle bridge. Only an independently verified host may register
//! a binding. No environment switch, provider discovery, launcher or budget grant.
use std::{
    sync::{Arc, Mutex, OnceLock, Weak},
    time::{SystemTime, UNIX_EPOCH},
};

use super::{native::Signal, *};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ended {
    pub execution_id: String,
    pub source_receipt: String,
    pub observed_at_ms: u64,
    pub exit_code: Option<i64>,
    /// Existing local process-group check only; not a detached-worker/effect fence.
    pub process_group_quiescent: bool,
    pub preservation_verified: bool,
}
struct Binding {
    controller: Weak<Mutex<Controller>>,
    work_id: String,
    identity: Identity,
    native_session_id: String,
    /// Exact native Codex limitId, None means the protocol's default bucket only.
    codex_limit_id: Option<String>,
}
static BINDINGS: OnceLock<Mutex<BTreeMap<String, Arc<Binding>>>> = OnceLock::new();
fn bindings() -> &'static Mutex<BTreeMap<String, Arc<Binding>>> {
    BINDINGS.get_or_init(|| Mutex::new(BTreeMap::new()))
}
fn binding(execution: &str) -> io::Result<Option<Arc<Binding>>> {
    let Some(registry) = BINDINGS.get() else {
        return Ok(None);
    };
    Ok(registry
        .lock()
        .map_err(|_| invalid("Observer registry poisoned"))?
        .get(execution)
        .cloned())
}
pub fn is_registered(execution: &str) -> bool {
    // An empty dormant bridge does not scan process groups or touch the journal.
    binding(execution).is_ok_and(|value| value.is_some())
}
fn now_ms() -> io::Result<u64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| invalid("Clock before epoch"))?
        .as_millis()
        .try_into()
        .map_err(|_| invalid("Clock overflow"))
}
/// RAII binding is held by the existing host owner, not a native tool/model. Its
/// lifetime must include callback drain and terminal receipt collection. Dropping
/// it never launches, stops or transfers a worker. New registration is explicit.
pub struct Registration {
    execution: String,
    binding: Arc<Binding>,
}
impl Drop for Registration {
    fn drop(&mut self) {
        if let Ok(mut registry) = bindings().lock() {
            if registry
                .get(&self.execution)
                .is_some_and(|b| Arc::ptr_eq(b, &self.binding))
            {
                registry.remove(&self.execution);
            }
        }
    }
}
pub fn register(
    controller: &Arc<Mutex<Controller>>,
    work_id: &str,
    execution: &str,
    identity: Identity,
    native_session_id: &str,
    codex_limit_id: Option<String>,
) -> io::Result<Registration> {
    let c = controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?;
    let w = c.work(work_id).ok_or_else(|| invalid("Unknown work"))?;
    let (expected, pool) = match &w.phase {
        Phase::Watching => (&w.execution_id, &w.incumbent.pool_id),
        Phase::DispatchPending(t) | Phase::Running(t) => (&t.execution_id, &t.candidate.pool_id),
        _ => return Err(invalid("Finished work")),
    };
    if expected != execution
        || c.state.pools.get(pool).map(|p| &p.identity) != Some(&identity)
        || identity.provider == Provider::Antigravity
        || !present(native_session_id)
        || native_session_id.len() > 200
        || codex_limit_id
            .as_ref()
            .is_some_and(|id| !present(id) || id.len() > 200)
        || (identity.provider != Provider::Codex && codex_limit_id.is_some())
    {
        return Err(invalid("Unverified observer identity"));
    }
    let binding = Arc::new(Binding {
        controller: Arc::downgrade(controller),
        work_id: work_id.into(),
        identity,
        native_session_id: native_session_id.into(),
        codex_limit_id,
    });
    let mut registry = bindings()
        .lock()
        .map_err(|_| invalid("Observer registry poisoned"))?;
    if registry.contains_key(execution) || registry.len() >= MAX_WORK {
        return Err(invalid("Execution already bound or registry full"));
    }
    registry.insert(execution.into(), binding.clone());
    Ok(Registration {
        execution: execution.into(),
        binding,
    })
}
fn record(
    execution: &str,
    b: &Binding,
    signal: io::Result<Option<Signal>>,
    now: u64,
) -> io::Result<bool> {
    let owner = b
        .controller
        .upgrade()
        .ok_or_else(|| invalid("Observer owner unavailable"))?;
    let mut c = owner.lock().map_err(|_| invalid("Controller poisoned"))?;
    let signal = match signal {
        Ok(None) => return Ok(false),
        Ok(Some(s))
            if s.provider == b.identity.provider
                && s.native_session_id
                    .as_ref()
                    .is_none_or(|id| id == &b.native_session_id) =>
        {
            s
        }
        _ => {
            c.hold_adapter(execution)?;
            return Err(invalid("Native adapter evidence invalid; handoff held"));
        }
    };
    c.record_native(
        &b.work_id,
        execution,
        &b.identity,
        signal,
        "native-executor-observer/v1",
        now,
    )?;
    Ok(true)
}
pub fn codex(execution: &str, method: &str, params: &serde_json::Value) -> io::Result<bool> {
    let Some(b) = binding(execution)? else {
        return Ok(false);
    };
    if b.identity.provider != Provider::Codex {
        return record(
            execution,
            &b,
            Err(invalid("Wrong native provider")),
            now_ms()?,
        );
    }
    let signal = if method == "account/rateLimits/updated"
        && params
            .pointer("/rateLimits/limitId")
            .and_then(serde_json::Value::as_str)
            != b.codex_limit_id.as_deref()
    {
        Err(invalid("Unexpected native limit bucket"))
    } else {
        super::native::codex(method, params)
    };
    record(execution, &b, signal, now_ms()?)
}
pub fn claude(execution: &str, message: &serde_json::Value) -> io::Result<bool> {
    let Some(b) = binding(execution)? else {
        return Ok(false);
    };
    record(execution, &b, super::native::claude(message), now_ms()?)
}
pub fn ended(
    execution: &str,
    exit_code: Option<i64>,
    group_quiescent: bool,
    preservation_verified: bool,
) -> io::Result<bool> {
    let Some(b) = binding(execution)? else {
        return Ok(false);
    };
    let owner = b
        .controller
        .upgrade()
        .ok_or_else(|| invalid("Observer owner unavailable"))?;
    let mut c = owner.lock().map_err(|_| invalid("Controller poisoned"))?;
    c.record_ended(Ended {
        execution_id: execution.into(),
        source_receipt: "vk-exit-monitor/v1".into(),
        observed_at_ms: now_ms()?,
        exit_code,
        process_group_quiescent: group_quiescent,
        preservation_verified,
    })?;
    Ok(true)
}
impl Controller {
    pub(super) fn hold_adapter(&mut self, execution: &str) -> io::Result<()> {
        let mut next = self.state.clone();
        next.adapter_holds
            .insert(execution.into(), "native_evidence_invalid".into());
        self.commit(next)
    }
    pub fn record_ended(&mut self, ended: Ended) -> io::Result<()> {
        let matches = self.state.works.values().any(|w| match &w.phase {
            Phase::Watching => w.execution_id == ended.execution_id,
            Phase::DispatchPending(t) | Phase::Running(t) => t.execution_id == ended.execution_id,
            _ => false,
        });
        if !matches
            || !present(&ended.source_receipt)
            || ended.observed_at_ms < self.state.last_now_ms
        {
            return Err(invalid("Unbound lifecycle receipt"));
        }
        if let Some(old) = self.state.ended.get(&ended.execution_id) {
            return if old == &ended {
                Ok(())
            } else {
                Err(invalid("Conflicting immutable lifecycle receipt"))
            };
        }
        let mut next = self.state.clone();
        next.last_now_ms = ended.observed_at_ms;
        next.ended.insert(ended.execution_id.clone(), ended);
        self.commit(next)
    }
    pub(super) fn ended_safely(&self, execution: &str) -> bool {
        self.state.ended.get(execution).is_some_and(|e| {
            e.exit_code.is_some() && e.process_group_quiescent && e.preservation_verified
        })
    }
    /// Advisory only. Return to the qualified original Sol pool after a verified
    /// reset and a NEW stopped alternate checkpoint. Not a second dispatch/retry.
    /// Existing host must reserve/fence/re-admit a distinct continuation separately.
    pub fn preferred_return(&self, id: &str, checkpoint: &Checkpoint, now: u64) -> Plan {
        let Some(w) = self.work(id) else {
            return hold("unknown_work");
        };
        let Phase::Running(t) = &w.phase else {
            return hold("no_running_alternate");
        };
        let c = &w.incumbent;
        if self.poisoned
            || now < self.state.last_now_ms
            || w.native_goal_active
            || w.policy.mode == Mode::Manual
            || c.model != "gpt-6.1-sol"
            || !c.qualified
            || c.scope_key != w.policy.scope_key
            || c.qualification_version != w.policy.qualification_version
            || w.policy.excluded_models.contains(&c.model)
            || w.policy.locked.as_ref().is_some_and(|v| v != c)
            || !self
                .state
                .pools
                .get(&c.pool_id)
                .is_some_and(|p| self.pool_ready(p, now))
        {
            return hold("preferred_return_not_qualified_or_reset");
        }
        if checkpoint.execution_id != t.execution_id
            || checkpoint.workspace_id != w.workspace_id
            || checkpoint.objective != w.objective
            || !present(&checkpoint.workspace_snapshot)
            || !Path::new(&checkpoint.workspace_path).is_absolute()
            || !present(&checkpoint.branch)
            || !checkpoint.all_workers_terminal
            || !present(&checkpoint.terminal_receipt)
            || !self.ended_safely(&t.execution_id)
            || self.state.adapter_holds.contains_key(&t.execution_id)
            || checkpoint.failed_validation
            || !checkpoint.pending_approvals.is_empty()
            || !checkpoint.effects_complete
            || w.effects
                .values()
                .any(|e| e.outcome == EffectOutcome::Unknown)
            || w.effects.values().any(|e| !checkpoint.effects.contains(e))
            || checkpoint
                .effects
                .iter()
                .any(|e| !present(&e.receipt) || e.outcome == EffectOutcome::Unknown)
        {
            return hold("preferred_return_checkpoint_required");
        }
        Plan::Recommend(c.clone())
    }
}
