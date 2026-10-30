//! Dormant native/lifecycle bridge. Only an independently verified host may register
//! a binding. No environment switch, provider discovery, launcher or budget grant.
use std::{
    sync::{Arc, Mutex, OnceLock},
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
    controller: Arc<Mutex<Controller>>,
    work_id: String,
    identity: Identity,
    native_session_id: Mutex<Option<String>>,
    read_only_initial: bool,
    profile_pin: Option<String>,
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
    retained: bool,
}
impl Registration {
    /// The exit observer owns release after a verified quiescent end. A lost host
    /// reply cannot drop the live worker's approval/side-effect guard.
    pub fn retain_until_terminal(mut self) {
        self.retained = true;
    }
}
impl Drop for Registration {
    fn drop(&mut self) {
        if self.retained {
            return;
        }
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
    register_inner(
        controller,
        work_id,
        execution,
        identity,
        Some(native_session_id),
        codex_limit_id,
        false,
        None,
    )
}
pub fn register_initial_claude(
    controller: &Arc<Mutex<Controller>>,
    work_id: &str,
    execution: &str,
    identity: Identity,
    profile_pin: &str,
) -> io::Result<Registration> {
    register_inner(
        controller,
        work_id,
        execution,
        identity,
        None,
        None,
        true,
        Some(profile_pin),
    )
}
pub fn register_initial_codex(
    controller: &Arc<Mutex<Controller>>,
    work_id: &str,
    execution: &str,
    identity: Identity,
    profile_pin: &str,
) -> io::Result<Registration> {
    if identity.provider != Provider::Codex || !present(profile_pin) {
        return Err(invalid("Invalid Codex binding"));
    }
    register_inner(
        controller,
        work_id,
        execution,
        identity,
        None,
        None,
        false,
        Some(profile_pin),
    )
}
pub fn provider_launch(execution: &str) -> io::Result<bool> {
    Ok(binding(execution)?.is_some_and(|b| b.profile_pin.is_some()))
}
/// Called with the ACTUAL thread/start response before turn input, not configured
/// settings or a fabricated native ID. Unreported effort remains unknown.
pub fn codex_started(
    execution: &str,
    thread: &str,
    model: &str,
    effort: Option<&str>,
    tier: &str,
) -> io::Result<()> {
    let Some(b) = binding(execution)? else {
        return Ok(());
    };
    if b.identity.provider != Provider::Codex {
        return Err(invalid("Wrong provider native start"));
    }
    let mut c = b
        .controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?;
    let t = c
        .work(&b.work_id)
        .and_then(|w| match &w.phase {
            Phase::DispatchPending(t) => Some(t.clone()),
            _ => None,
        })
        .ok_or_else(|| invalid("No pending native start"))?;
    if !present(thread)
        || model != t.candidate.model
        || tier != t.candidate.service_tier
        || effort.is_some_and(|e| e != t.candidate.effort)
    {
        c.hold_adapter(execution)?;
        return Err(invalid("Actual Codex settings mismatch"));
    }
    if b.native_session_id
        .lock()
        .map_err(|_| invalid("Native binding poisoned"))?
        .as_deref()
        .is_some_and(|old| old != thread)
    {
        c.hold_adapter(execution)?;
        return Err(invalid("Native thread binding changed"));
    }
    *b.native_session_id
        .lock()
        .map_err(|_| invalid("Native binding poisoned"))? = Some(thread.into());
    c.record_native(
        &b.work_id,
        execution,
        &b.identity,
        Signal {
            provider: Provider::Codex,
            native_session_id: Some(thread.into()),
            native_turn_id: None,
            native_model: Some(model.into()),
            native_effort: effort.map(str::to_owned),
            windows: vec![],
            failure: None,
            native_retrying: None,
        },
        "codex-native-thread-start/v1",
        now_ms()?,
    )?;
    if effort.is_some() {
        c.confirm_started(
            &b.work_id,
            LaunchReceipt {
                source_receipt: "codex-native-thread-start/v1".into(),
                transition_id: t.transition_id,
                execution_id: execution.into(),
                identity: b.identity.clone(),
                effective: t.candidate,
                native_session_id: thread.into(),
                native_turn_id: None,
            },
        )?;
    }
    Ok(())
}
fn register_inner(
    controller: &Arc<Mutex<Controller>>,
    work_id: &str,
    execution: &str,
    identity: Identity,
    native_session_id: Option<&str>,
    codex_limit_id: Option<String>,
    read_only_initial: bool,
    profile_pin: Option<&str>,
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
        || native_session_id.is_some_and(|id| !present(id) || id.len() > 200)
        || (read_only_initial
            && (!profile_pin.is_some_and(present)
                || identity.provider != Provider::Claude
                || !matches!(&w.phase, Phase::DispatchPending(t) if t.candidate.model==super::claude::MODEL && t.candidate.effort==super::claude::EFFORT)))
        || codex_limit_id
            .as_ref()
            .is_some_and(|id| !present(id) || id.len() > 200)
        || (identity.provider != Provider::Codex && codex_limit_id.is_some())
    {
        return Err(invalid("Unverified observer identity"));
    }
    let binding = Arc::new(Binding {
        controller: controller.clone(),
        work_id: work_id.into(),
        identity,
        native_session_id: Mutex::new(native_session_id.map(str::to_owned)),
        read_only_initial,
        profile_pin: profile_pin.map(str::to_owned),
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
        retained: false,
    })
}
fn record(
    execution: &str,
    b: &Binding,
    signal: io::Result<Option<Signal>>,
    now: u64,
) -> io::Result<bool> {
    if matches!(signal, Ok(None)) {
        return Ok(false);
    }
    let mut c = b
        .controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?;
    let native = b
        .native_session_id
        .lock()
        .map_err(|_| invalid("Native binding poisoned"))?;
    let signal = match signal {
        Ok(None) => return Ok(false),
        Ok(Some(s))
            if s.provider == b.identity.provider
                && s.native_session_id
                    .as_ref()
                    .is_none_or(|id| native.as_ref() == Some(id)) =>
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
pub fn guarded_handoff(execution: &str) -> io::Result<bool> {
    Ok(binding(execution)?.is_some_and(|b| b.read_only_initial))
}
pub fn read_only_handoff(execution: &str) -> io::Result<bool> {
    guarded_handoff(execution)
}
pub fn verify_profile_pin(execution: &str, actual: &str) -> io::Result<()> {
    let Some(b) = binding(execution)? else {
        return Ok(());
    };
    if b.profile_pin.is_some() && b.profile_pin.as_deref() != Some(actual) {
        return Err(invalid(
            "Actual launch profile changed after provider admission",
        ));
    }
    Ok(())
}
pub fn tool_allowed(execution: &str, tool: &str) -> io::Result<bool> {
    action_allowed(execution, tool, &serde_json::Value::Null)
}
pub fn action_allowed(execution: &str, tool: &str, input: &serde_json::Value) -> io::Result<bool> {
    let Some(b) = binding(execution)? else {
        return Ok(true);
    };
    if !b.read_only_initial {
        return Ok(true);
    }
    let c = b
        .controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?;
    let native = b
        .native_session_id
        .lock()
        .map_err(|_| invalid("Native binding poisoned"))?;
    Ok(native.is_some()
        && !c.state.adapter_holds.contains_key(execution)
        && c.action_allowed(&b.work_id, execution, tool, input))
}
pub fn approved_tool(
    execution: &str,
    tool_id: &str,
    tool: &str,
    input: &serde_json::Value,
) -> io::Result<()> {
    let b = binding(execution)?.ok_or_else(|| invalid("Guarded owner missing"))?;
    if !action_allowed(execution, tool, input)? {
        return Err(invalid("Tool not authorized"));
    }
    b.controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?
        .claim_tool(&b.work_id, execution, tool_id, tool, input)
}
pub fn completed_tool(
    execution: &str,
    tool_id: &str,
    tool: &str,
    input: &serde_json::Value,
) -> io::Result<()> {
    let b = binding(execution)?.ok_or_else(|| invalid("Guarded owner missing"))?;
    let mut c = b
        .controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?;
    if let Err(error) = c.complete_tool(&b.work_id, execution, tool_id, tool, input) {
        c.hold_adapter(execution)?;
        return Err(error);
    }
    Ok(())
}
pub fn claude(execution: &str, message: &serde_json::Value) -> io::Result<bool> {
    let Some(b) = binding(execution)? else {
        return Ok(false);
    };
    if b.read_only_initial
        && message.get("type").and_then(serde_json::Value::as_str) == Some("system")
        && message.get("subtype").and_then(serde_json::Value::as_str) == Some("init")
    {
        let session = message
            .get("session_id")
            .and_then(serde_json::Value::as_str);
        let model = message.get("model").and_then(serde_json::Value::as_str);
        let effort = message.get("effort").and_then(serde_json::Value::as_str);
        let mut c = b
            .controller
            .lock()
            .map_err(|_| invalid("Controller poisoned"))?;
        let mut native = b
            .native_session_id
            .lock()
            .map_err(|_| invalid("Native binding poisoned"))?;
        if model != Some(super::claude::MODEL)
            || message
                .get("effort")
                .is_some_and(|value| !value.is_null() && !value.is_string())
            || effort.is_some_and(|value| value != super::claude::EFFORT)
            || !session.is_some_and(|id| present(id) && id.len() <= 200)
            || native.as_deref().is_some_and(|old| Some(old) != session)
        {
            c.hold_adapter(execution)?;
            return Err(invalid(
                "Fresh Claude native model/session mismatch; tools held",
            ));
        }
        *native = session.map(str::to_owned);
        // Native model/session are observed; effort is not claimed native-verified
        // if this CLI does not expose it. Do not manufacture a LaunchReceipt.
        c.record_native(
            &b.work_id,
            execution,
            &b.identity,
            Signal {
                provider: Provider::Claude,
                native_session_id: native.clone(),
                native_turn_id: None,
                native_model: model.map(str::to_owned),
                native_effort: effort.map(str::to_owned),
                windows: vec![],
                failure: None,
                native_retrying: None,
            },
            "claude-native-system-init/v1",
            now_ms()?,
        )?;
        if effort == Some(super::claude::EFFORT) {
            let pending = c.work(&b.work_id).and_then(|w| match &w.phase {
                Phase::DispatchPending(t) => Some(t.clone()),
                _ => None,
            });
            if let Some(t) = pending {
                c.confirm_started(
                    &b.work_id,
                    LaunchReceipt {
                        source_receipt: "claude-native-system-init/v1".into(),
                        transition_id: t.transition_id,
                        execution_id: execution.into(),
                        identity: b.identity.clone(),
                        effective: t.candidate,
                        native_session_id: native
                            .clone()
                            .ok_or_else(|| invalid("Native session missing"))?,
                        native_turn_id: None,
                    },
                )?;
            }
        }
        return Ok(true);
    }
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
    let mut c = b
        .controller
        .lock()
        .map_err(|_| invalid("Controller poisoned"))?;
    c.record_ended(Ended {
        execution_id: execution.into(),
        source_receipt: "vk-exit-monitor/v1".into(),
        observed_at_ms: now_ms()?,
        exit_code,
        process_group_quiescent: group_quiescent,
        preservation_verified,
    })?;
    drop(c);
    if group_quiescent && preservation_verified {
        bindings()
            .lock()
            .map_err(|_| invalid("Observer registry poisoned"))?
            .remove(execution);
    }
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
        if !matches || !present(&ended.source_receipt) {
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
        next.last_now_ms = next.last_now_ms.max(ended.observed_at_ms);
        next.ended.insert(ended.execution_id.clone(), ended);
        self.commit(next)
    }
    pub fn ended_receipt(&self, execution: &str) -> Option<&Ended> {
        self.state.ended.get(execution)
    }
    pub(super) fn ended_safely(&self, execution: &str) -> bool {
        self.state.ended.get(execution).is_some_and(|e| {
            e.exit_code.is_some() && e.process_group_quiescent && e.preservation_verified
        })
    }
    /// Compatibility advisory API; fresh selection now follows measured allowance,
    /// not an unconditional Sol return. Dispatch uses claim_boundary separately.
    pub fn preferred_return(&self, id: &str, checkpoint: &Checkpoint, now: u64) -> Plan {
        match self.boundary_plan(id, checkpoint, now) {
            Plan::Ready(c) => Plan::Recommend(c),
            other => other,
        }
    }
}
