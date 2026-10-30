//! Isolated, dormant cross-provider boundary controller. No network, scheduler,
//! process launcher or automatic provider registration. Native observation hooks are
//! inactive without an explicit trusted host binding. Inputs must
//! come from trusted executor/admission adapters, never prompts/model output.
use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{self, Read, Write},
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

pub mod checkpoint;
pub mod claude;
pub mod native;
pub mod observer;
pub mod readiness;
pub mod selection;
pub mod tools;

const MAX_STATE: usize = 2 * 1024 * 1024;
const MAX_WORK: usize = 100;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Provider {
    Codex,
    Claude,
    Antigravity,
}

/// pool_id and binding_key follow cu.allocation.v1. A profile/home is NOT a pool.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub provider: Provider,
    pub pool_id: String,
    pub binding_key: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Window {
    pub id: String,
    /// Provider-defined, e.g. short/weekly; never an assumed five-hour duration.
    pub kind: String,
    pub available: Option<bool>,
    pub reset_at_ms: Option<u64>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Pool {
    pub identity: Identity,
    pub generation: String,
    /// Legacy preference metadata only; never capacity, quota or billing evidence.
    pub allocation_rank: Option<u32>,
    pub source_receipt: String,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
    /// Complete applicable windows, including an explicitly verified unmetered set.
    pub windows_complete: bool,
    pub windows: Vec<Window>,
    pub authorized: bool,
    pub adapter_verified: bool,
    pub handoff_supported: bool,
    pub auth_verified_at_ms: Option<u64>,
    pub health_verified_at_ms: Option<u64>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Failure {
    Quota {
        window_id: String,
    },
    /// Native quota exhaustion without a verified named window.
    QuotaUnspecified,
    RateLimit,
    Authentication,
    Outage,
    TaskFailure,
    Unknown,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LimitEvent {
    pub id: String,
    pub execution_id: String,
    pub identity: Identity,
    pub source_receipt: String,
    pub observed_at_ms: u64,
    pub failure: Failure,
    /// Adapter-normalized Retry-After, not a clock-based grant of capacity.
    pub retry_at_ms: Option<u64>,
}

/// Seconds form and parsed HTTP-date form preserve a conservative wait interval.
/// HTTP-date parsing belongs to the HTTP adapter; invalid/missing dates are unknown.
#[derive(Clone, Debug)]
pub enum RetryAfter {
    Seconds(u64),
    ServerDate { date_ms: u64, server_now_ms: u64 },
}
pub fn retry_deadline(value: RetryAfter, received_at_ms: u64) -> Option<u64> {
    let delay = match value {
        RetryAfter::Seconds(s) => s.checked_mul(1000)?,
        RetryAfter::ServerDate {
            date_ms,
            server_now_ms,
        } => date_ms.checked_sub(server_now_ms)?,
    };
    received_at_ms.checked_add(delay)
}

/// At most five metadata refresh attempts; caller persists its attempt count.
/// No inference retries and no reset permission are implied by a deadline.
pub fn refresh_deadline(attempt: u8, now: u64, retry_at: Option<u64>) -> Option<u64> {
    let delay = *([5_000u64, 10_000, 20_000, 40_000, 60_000].get(attempt as usize)?);
    Some(now.checked_add(delay)?.max(retry_at.unwrap_or(now)))
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Candidate {
    pub pool_id: String,
    pub model: String,
    pub effort: String,
    pub service_tier: String,
    /// Exact qualification/floor/constraint result; no cross-vendor model ladder.
    pub scope_key: String,
    pub qualification_version: String,
    pub qualified: bool,
    /// Preference only; never a billing or allowance multiplier.
    pub rank: u32,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    Manual,
    Recommend,
    Auto,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Policy {
    pub mode: Mode,
    pub failover_authorized: bool,
    pub scope_key: String,
    pub qualification_version: String,
    pub locked: Option<Candidate>,
    pub excluded_models: Vec<String>,
    pub candidates: Vec<Candidate>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectOutcome {
    Completed,
    NotStarted,
    Unknown,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Effect {
    pub id: String,
    pub outcome: EffectOutcome,
    pub receipt: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Checkpoint {
    pub execution_id: String,
    pub objective: String,
    pub context: String,
    pub workspace_id: String,
    pub workspace_path: String,
    pub branch: String,
    /// Authoritative digest/receipt covering HEAD AND dirty/index/untracked state.
    pub workspace_snapshot: String,
    pub completed_steps: Vec<String>,
    pub pending_steps: Vec<String>,
    pub pending_approvals: Vec<String>,
    pub effects: Vec<Effect>,
    pub all_workers_terminal: bool,
    pub terminal_receipt: String,
    pub effects_complete: bool,
    pub failed_validation: bool,
    /// Provenance only; MUST NOT be passed as another provider's resume ID.
    pub native_thread_id: Option<String>,
    pub native_turn_id: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Transfer {
    pub transition_id: String,
    pub execution_id: String,
    pub previous_execution_id: String,
    pub candidate: Candidate,
    pub identity: Identity,
    pub generation: String,
    pub checkpoint: Checkpoint,
    pub permit_receipt: String,
    pub ownership_fence: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LaunchReceipt {
    pub source_receipt: String,
    pub transition_id: String,
    pub execution_id: String,
    pub identity: Identity,
    pub effective: Candidate,
    pub native_session_id: String,
    pub native_turn_id: Option<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Watching,
    DispatchPending(Transfer),
    Running(Transfer),
    Finished(Transfer),
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Work {
    pub id: String,
    pub workspace_id: String,
    pub objective: String,
    pub execution_id: String,
    pub incumbent: Candidate,
    pub policy: Policy,
    pub native_goal_active: bool,
    pub event: Option<LimitEvent>,
    pub checkpoint: Option<Checkpoint>,
    pub phase: Phase,
    /// One alternate attempt per work identity, including failed/ambiguous starts.
    pub attempts: u8,
    pub launch_receipt: Option<LaunchReceipt>,
    pub effects: BTreeMap<String, Effect>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Block {
    pub event: LimitEvent,
    pub generation: String,
    pub until_ms: u64,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct State {
    version: u32,
    revision: u64,
    last_now_ms: u64,
    pools: BTreeMap<String, Pool>,
    blocks: BTreeMap<String, Vec<Block>>,
    events: BTreeMap<String, LimitEvent>,
    works: BTreeMap<String, Work>,
    #[serde(default)]
    native_records: BTreeMap<String, native::Record>,
    #[serde(default)]
    ended: BTreeMap<String, observer::Ended>,
    #[serde(default)]
    adapter_holds: BTreeMap<String, String>,
    #[serde(default)]
    capacities: BTreeMap<String, selection::Capacity>,
    #[serde(default)]
    completed_works: BTreeMap<String, String>,
    #[serde(default)]
    transfers: BTreeMap<String, Transfer>,
    #[serde(default)]
    launches: BTreeMap<String, LaunchReceipt>,
    #[serde(default)]
    actions: BTreeMap<String, tools::Actions>,
    #[serde(default)]
    tool_uses: BTreeMap<String, tools::ToolUse>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Plan {
    Hold {
        reason: &'static str,
        retry_at_ms: Option<u64>,
    },
    Recommend(Candidate),
    Ready(Candidate),
}
fn hold(reason: &'static str) -> Plan {
    Plan::Hold {
        reason,
        retry_at_ms: None,
    }
}
fn invalid(s: &str) -> io::Error {
    io::Error::other(s)
}
fn present(s: &str) -> bool {
    !s.trim().is_empty()
}

/// Opaque admission receipt supplied by the existing budget/capacity authority.
/// Quota observations and this controller never grant admission themselves.
#[derive(Clone, Debug)]
pub struct Admission {
    pub receipt: String,
    pub work_id: String,
    pub transition_id: String,
    pub execution_id: String,
    pub identity: Identity,
    pub generation: String,
    pub scope_key: String,
    pub qualification_version: String,
    pub candidate: Candidate,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
    pub global_lane_granted: bool,
    pub budget_granted: bool,
}

/// Trusted host receipt: existing admission transaction reserves the workspace
/// against competing queued/resumed owners and rechecks the complete process tree.
#[derive(Clone, Debug)]
pub struct Boundary {
    pub work_id: String,
    pub previous_execution_id: String,
    pub workspace_id: String,
    pub workspace_snapshot: String,
    pub terminal_receipt: String,
    pub ownership_fence: String,
    pub all_workers_terminal: bool,
    pub effects_reconciled: bool,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
}

pub struct Controller {
    root: PathBuf,
    _lock: File,
    state: State,
    poisoned: bool,
}
impl Controller {
    /// Explicit creation cannot silently replace a lost/corrupt existing journal.
    /// Caller provisions a private directory; this never chmods an existing path.
    pub fn create(root: &Path) -> io::Result<Self> {
        if fs::symlink_metadata(root.join("controller.lock")).is_ok() {
            return Err(invalid(
                "Existing journal identity; open/reconcile instead of recreating",
            ));
        }
        let mut c = Self::locked(root)?;
        if root.join("state.json").exists() {
            return Err(invalid("State already exists"));
        }
        c.commit(c.state.clone())?;
        Ok(c)
    }
    pub fn open(root: &Path) -> io::Result<Self> {
        let mut c = Self::locked(root)?;
        private_file(&root.join("state.json"))?;
        let mut bytes = Vec::new();
        File::open(root.join("state.json"))?
            .take((MAX_STATE + 1) as u64)
            .read_to_end(&mut bytes)?;
        if bytes.len() > MAX_STATE {
            return Err(invalid("State too large"));
        }
        c.state = serde_json::from_slice(&bytes)?;
        if c.state.version != 1 || c.state.works.len() > MAX_WORK {
            return Err(invalid("Unsupported state"));
        }
        Ok(c)
    }
    fn locked(root: &Path) -> io::Result<Self> {
        if !root.is_absolute() || fs::canonicalize(root)? != root || !fs::metadata(root)?.is_dir() {
            return Err(invalid("Private absolute real directory required"));
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            if fs::metadata(root)?.mode() & 0o077 != 0 {
                return Err(invalid("Directory must already be private"));
            }
        }
        let path = root.join("controller.lock");
        match fs::symlink_metadata(&path) {
            Ok(_) => private_file(&path)?,
            Err(e) if e.kind() == io::ErrorKind::NotFound => {}
            Err(e) => return Err(e),
        }
        let mut options = OpenOptions::new();
        options.create(true).truncate(false).read(true).write(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let lock = options.open(path)?;
        lock.try_lock().map_err(io::Error::other)?;
        Ok(Self {
            root: root.into(),
            _lock: lock,
            poisoned: false,
            state: State {
                version: 1,
                revision: 0,
                last_now_ms: 0,
                pools: BTreeMap::new(),
                blocks: BTreeMap::new(),
                events: BTreeMap::new(),
                works: BTreeMap::new(),
                native_records: BTreeMap::new(),
                ended: BTreeMap::new(),
                adapter_holds: BTreeMap::new(),
                capacities: BTreeMap::new(),
                completed_works: BTreeMap::new(),
                transfers: BTreeMap::new(),
                launches: BTreeMap::new(),
                actions: BTreeMap::new(),
                tool_uses: BTreeMap::new(),
            },
        })
    }
    fn commit(&mut self, mut next: State) -> io::Result<()> {
        if self.poisoned {
            return Err(invalid("Journal requires recovery"));
        }
        next.revision = self
            .state
            .revision
            .checked_add(1)
            .ok_or_else(|| invalid("Revision exhausted"))?;
        let bytes = serde_json::to_vec(&next)?;
        if bytes.len() > MAX_STATE {
            return Err(invalid(
                "Journal capacity reached; operator archival required",
            ));
        }
        let tmp = self.root.join(format!(
            ".state-{}-{}.next",
            std::process::id(),
            next.revision
        ));
        let result = (|| {
            let mut options = OpenOptions::new();
            options.create_new(true).write(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            let mut file = options.open(&tmp)?;
            file.write_all(&bytes)?;
            file.sync_all()?;
            fs::rename(&tmp, self.root.join("state.json"))?;
            File::open(&self.root)?.sync_all()
        })();
        if let Err(e) = result {
            // Rename/fsync may have committed. No further dispatch until reopen.
            self.poisoned = true;
            return Err(e);
        }
        self.state = next;
        Ok(())
    }
    pub fn pool(&self, id: &str) -> Option<&Pool> {
        self.state.pools.get(id)
    }
    pub fn work(&self, id: &str) -> Option<&Work> {
        self.state.works.get(id)
    }
    pub fn observe_pool(&mut self, pool: Pool) -> io::Result<()> {
        if !present(&pool.identity.pool_id)
            || !pool.identity.binding_key.starts_with("sha256:")
            || pool.identity.binding_key.len() != 71
            || !pool.identity.binding_key[7..]
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
            || !present(&pool.source_receipt)
            || !present(&pool.generation)
            || pool.observed_at_ms >= pool.valid_until_ms
            || pool.windows.len() > 32
        {
            return Err(invalid("Invalid pool observation"));
        }
        let mut windows = std::collections::BTreeSet::new();
        for w in &pool.windows {
            if !present(&w.id) || !present(&w.kind) || !windows.insert(&w.id) {
                return Err(invalid("Invalid window identity"));
            }
        }
        for p in self.state.pools.values() {
            if p.identity.pool_id == pool.identity.pool_id {
                if p.identity != pool.identity {
                    return Err(invalid("Pool cannot be rebound"));
                }
                if pool.observed_at_ms < p.observed_at_ms {
                    return Err(invalid("Older pool evidence"));
                }
                if pool.observed_at_ms == p.observed_at_ms && *p != pool {
                    return Err(invalid("Conflicting pool evidence"));
                }
            } else if p.identity.binding_key == pool.identity.binding_key {
                return Err(invalid("Allowance alias; use existing pool"));
            }
        }
        let mut next = self.state.clone();
        next.last_now_ms = next.last_now_ms.max(pool.observed_at_ms);
        next.pools.insert(pool.identity.pool_id.clone(), pool);
        self.commit(next)
    }
    pub fn register(&mut self, work: Work) -> io::Result<()> {
        if !present(&work.id)
            || !present(&work.objective)
            || !present(&work.workspace_id)
            || !present(&work.execution_id)
            || !present(&work.policy.scope_key)
            || !present(&work.policy.qualification_version)
            || work.attempts != 0
            || work.phase != Phase::Watching
            || work.event.is_some()
            || work.checkpoint.is_some()
            || work.launch_receipt.is_some()
            || !work.effects.is_empty()
            || self.state.works.len() >= MAX_WORK
            || !self.state.pools.contains_key(&work.incumbent.pool_id)
        {
            return Err(invalid("Invalid initial work"));
        }
        if self
            .state
            .transfers
            .values()
            .any(|t| t.execution_id == work.execution_id)
        {
            return Err(invalid(
                "Execution identity already belongs to a preserved transfer",
            ));
        }
        if self.state.works.values().any(|w| {
            w.id == work.id
                || (w.workspace_id == work.workspace_id
                    && !self.state.completed_works.contains_key(&w.id))
                || w.execution_id == work.execution_id
        }) {
            return Err(invalid("Existing workspace/operation owner; reconcile it"));
        }
        let mut next = self.state.clone();
        next.works.insert(work.id.clone(), work);
        self.commit(next)
    }
    /// Structured event only: no error-string matching, exit-code guessing or quota RPC.
    pub fn observe(&mut self, work_id: &str, event: LimitEvent) -> io::Result<()> {
        if let Some(old) = self.state.events.get(&event.id) {
            return if old == &event {
                Ok(())
            } else {
                Err(invalid("Conflicting immutable event"))
            };
        }
        let w = self.work(work_id).ok_or_else(|| invalid("Unknown work"))?;
        let (execution, pool_id) = match &w.phase {
            Phase::Watching => (&w.execution_id, &w.incumbent.pool_id),
            Phase::DispatchPending(t) | Phase::Running(t) => {
                (&t.execution_id, &t.candidate.pool_id)
            }
            Phase::Finished(_) => return Err(invalid("Finished work")),
        };
        let p = self
            .state
            .pools
            .get(pool_id)
            .ok_or_else(|| invalid("Unknown pool"))?;
        if !present(&event.id)
            || !present(&event.source_receipt)
            || event.execution_id != *execution
            || event.identity != p.identity
        {
            return Err(invalid("Unbound failure event"));
        }
        let mut until = event.retry_at_ms.unwrap_or(event.observed_at_ms);
        if let Failure::Quota { window_id } = &event.failure {
            let window = p
                .windows
                .iter()
                .find(|w| w.id == *window_id)
                .ok_or_else(|| invalid("Unverified quota window"))?;
            until = until.max(window.reset_at_ms.unwrap_or(event.observed_at_ms));
        }
        if matches!(
            event.failure,
            Failure::RateLimit | Failure::Outage | Failure::Authentication
        ) {
            until = until.max(event.observed_at_ms.saturating_add(60_000));
        }
        let mut next = self.state.clone();
        if !matches!(event.failure, Failure::TaskFailure | Failure::Unknown) {
            next.blocks.entry(pool_id.clone()).or_default().push(Block {
                event: event.clone(),
                generation: p.generation.clone(),
                until_ms: until,
            });
        }
        next.last_now_ms = next.last_now_ms.max(event.observed_at_ms);
        next.events.insert(event.id.clone(), event.clone());
        next.works.get_mut(work_id).unwrap().event = Some(event);
        self.commit(next)
    }
    pub fn checkpoint(&mut self, id: &str, checkpoint: Checkpoint) -> io::Result<()> {
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        if w.phase != Phase::Watching
            || checkpoint.execution_id != w.execution_id
            || checkpoint.workspace_id != w.workspace_id
            || checkpoint.objective != w.objective
            || !present(&checkpoint.workspace_path)
            || !Path::new(&checkpoint.workspace_path).is_absolute()
            || !present(&checkpoint.branch)
            || !present(&checkpoint.workspace_snapshot)
            || checkpoint.context.len() > 16_000
            || checkpoint.completed_steps.len() > 100
            || checkpoint.pending_steps.len() > 100
        {
            return Err(invalid("Checkpoint identity/scope changed"));
        }
        let mut effects = std::collections::BTreeSet::new();
        for e in &checkpoint.effects {
            if !present(&e.id) || !effects.insert(&e.id) {
                return Err(invalid("Duplicate effect identity"));
            }
        }
        let mut next = self.state.clone();
        next.works.get_mut(id).unwrap().checkpoint = Some(checkpoint);
        self.commit(next)
    }
    fn pool_ready(&self, p: &Pool, now: u64) -> bool {
        if !p.authorized
            || !p.adapter_verified
            || !p.handoff_supported
            || !p.auth_verified_at_ms.is_some_and(|t| t <= p.observed_at_ms)
            || !p.windows_complete
            || p.observed_at_ms > now
            || now >= p.valid_until_ms
            || !p.windows.iter().all(|w| w.available == Some(true))
        {
            return false;
        }
        self.state
            .blocks
            .get(&p.identity.pool_id)
            .into_iter()
            .flatten()
            .all(|b| {
                if now < b.until_ms
                    || p.observed_at_ms <= b.event.observed_at_ms
                    || p.observed_at_ms < b.until_ms
                {
                    return false;
                }
                match b.event.failure {
                    Failure::Quota { ref window_id } => {
                        p.generation != b.generation
                            && p.windows
                                .iter()
                                .any(|w| w.id == *window_id && w.available == Some(true))
                    }
                    Failure::QuotaUnspecified => p.generation != b.generation,
                    Failure::Authentication => p
                        .auth_verified_at_ms
                        .is_some_and(|t| t > b.event.observed_at_ms && t <= p.observed_at_ms),
                    Failure::Outage => p
                        .health_verified_at_ms
                        .is_some_and(|t| t > b.event.observed_at_ms && t <= p.observed_at_ms),
                    Failure::RateLimit => true,
                    _ => false,
                }
            })
    }
    pub fn plan(&self, id: &str, now: u64) -> Plan {
        if self.state.completed_works.contains_key(id) {
            return hold("work_completed");
        }
        if self.poisoned {
            return hold("journal_recovery_required");
        }
        if now < self.state.last_now_ms {
            return hold("clock_reconciliation_required");
        }
        let Some(w) = self.work(id) else {
            return hold("unknown_work");
        };
        if self.state.adapter_holds.contains_key(&w.execution_id) {
            return hold("native_adapter_reconciliation_required");
        }
        if matches!(w.phase, Phase::DispatchPending(_)) {
            return hold("dispatch_outcome_unknown");
        }
        if w.phase != Phase::Watching || w.attempts >= 1 {
            return hold("alternate_attempt_exhausted");
        }
        if w.policy.mode == Mode::Manual {
            return hold("manual_selection");
        }
        if w.native_goal_active {
            return hold("native_goal_owner_pinned");
        }
        let Some(event) = &w.event else {
            return hold("no_structured_limit");
        };
        if event.observed_at_ms > now {
            return hold("future_event");
        }
        if matches!(event.failure, Failure::TaskFailure | Failure::Unknown) {
            return hold("task_failure_requires_review");
        }
        let Some(c) = &w.checkpoint else {
            return hold("checkpoint_required");
        };
        if !c.all_workers_terminal || !present(&c.terminal_receipt) {
            return hold("prior_worker_outcome_unknown");
        }
        if self.native_observed(&c.execution_id) && !self.ended_safely(&c.execution_id) {
            return hold("native_lifecycle_not_fenced");
        }
        if !c.effects_complete
            || c.effects
                .iter()
                .any(|e| e.outcome == EffectOutcome::Unknown || !present(&e.receipt))
        {
            return hold("side_effect_outcome_unknown");
        }
        if c.failed_validation {
            return hold("failed_validation_protection");
        }
        if !c.pending_approvals.is_empty() {
            return hold("pending_approval");
        }
        let mut choices: Vec<_> = w
            .policy
            .candidates
            .iter()
            .filter(|c| {
                c.pool_id != w.incumbent.pool_id
                    && c.qualified
                    && c.rank > 0
                    // Break-glass approval is a separate explicit manual action.
                    // A qualification, outage or generic escalation flag cannot grant it.
                    && c.model != "gpt-6-astra"
                    && present(&c.model)
                    && present(&c.effort)
                    && present(&c.service_tier)
                    && c.scope_key == w.policy.scope_key
                    && c.qualification_version == w.policy.qualification_version
                    && !w.policy.excluded_models.contains(&c.model)
                    && w.policy.locked.as_ref().is_none_or(|locked| locked == *c)
                    && self
                        .state
                        .pools
                        .get(&c.pool_id)
                        .is_some_and(|p| p.identity.provider != Provider::Antigravity && self.pool_ready(p, now))
            })
            .cloned()
            .collect();
        match self.select(w, &mut choices, now) {
            Err(reason) => return hold(reason),
            Ok(()) => {}
        }
        let Some(candidate) = choices.into_iter().next() else {
            let retry = self
                .state
                .blocks
                .values()
                .flatten()
                .filter_map(|b| (b.until_ms > now).then_some(b.until_ms))
                .min();
            return Plan::Hold {
                reason: "no_authorized_qualified_provider",
                retry_at_ms: retry,
            };
        };
        if w.policy.mode == Mode::Recommend {
            Plan::Recommend(candidate)
        } else if !w.policy.failover_authorized {
            hold("failover_not_authorized")
        } else {
            Plan::Ready(candidate)
        }
    }
    /// Write-ahead dispatch. Returns ONCE. A crash/lost result requires reconciliation,
    /// never calling the provider again with a new execution/idempotency identity.
    pub fn claim(
        &mut self,
        id: &str,
        permit: Admission,
        boundary: Boundary,
        now: u64,
    ) -> io::Result<Transfer> {
        let Plan::Ready(candidate) = self.plan(id, now) else {
            return Err(invalid("No authorized ready handoff"));
        };
        let checkpoint = self
            .work(id)
            .and_then(|w| w.checkpoint.clone())
            .ok_or_else(|| invalid("Checkpoint required"))?;
        self.claim_selected(id, candidate, checkpoint, permit, boundary, now)
    }
    fn claim_selected(
        &mut self,
        id: &str,
        candidate: Candidate,
        checkpoint: Checkpoint,
        permit: Admission,
        boundary: Boundary,
        now: u64,
    ) -> io::Result<Transfer> {
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        let p = self.state.pools.get(&candidate.pool_id).unwrap();
        if !present(&permit.receipt)
            || !present(&permit.transition_id)
            || !present(&permit.execution_id)
            || permit.work_id != id
            || permit.identity != p.identity
            || permit.generation != p.generation
            || permit.scope_key != w.policy.scope_key
            || permit.qualification_version != w.policy.qualification_version
            || permit.candidate != candidate
            || permit.observed_at_ms > now
            || now >= permit.valid_until_ms
            || !permit.global_lane_granted
            || !permit.budget_granted
            || boundary.work_id != id
            || boundary.previous_execution_id != checkpoint.execution_id
            || boundary.workspace_id != w.workspace_id
            || boundary.workspace_snapshot != checkpoint.workspace_snapshot
            || boundary.terminal_receipt != checkpoint.terminal_receipt
            || !present(&boundary.ownership_fence)
            || !boundary.all_workers_terminal
            || !boundary.effects_reconciled
            || boundary.observed_at_ms > now
            || now >= boundary.valid_until_ms
            || self.state.transfers.values().any(|t| {
                t.execution_id == permit.execution_id || t.transition_id == permit.transition_id
            })
            || self.state.works.values().any(|other| {
                other.execution_id == permit.execution_id
                    || match &other.phase {
                        Phase::DispatchPending(t) | Phase::Running(t) | Phase::Finished(t) => {
                            t.execution_id == permit.execution_id
                                || t.transition_id == permit.transition_id
                        }
                        _ => false,
                    }
            })
        {
            return Err(invalid("Admission, ownership or workspace changed"));
        }
        let t = Transfer {
            transition_id: permit.transition_id,
            execution_id: permit.execution_id,
            previous_execution_id: checkpoint.execution_id.clone(),
            candidate,
            identity: p.identity.clone(),
            generation: p.generation.clone(),
            checkpoint,
            permit_receipt: permit.receipt,
            ownership_fence: boundary.ownership_fence,
        };
        let mut next = self.state.clone();
        next.last_now_ms = now;
        // Older version-1 journals kept the current transfer/launch only on Work.
        // Preserve EXACT existing evidence before advancing, without inventing any
        // missing receipt or admission. Old attempts remain attributable.
        if let Phase::DispatchPending(prior) | Phase::Running(prior) = &w.phase {
            next.transfers
                .entry(prior.transition_id.clone())
                .or_insert_with(|| prior.clone());
        }
        if let Some(receipt) = &w.launch_receipt {
            next.launches
                .entry(receipt.transition_id.clone())
                .or_insert_with(|| receipt.clone());
        }
        next.transfers.insert(t.transition_id.clone(), t.clone());
        let w = next.works.get_mut(id).unwrap();
        w.launch_receipt = None;
        w.attempts += 1;
        w.effects = t
            .checkpoint
            .effects
            .iter()
            .map(|e| (e.id.clone(), e.clone()))
            .collect();
        w.phase = Phase::DispatchPending(t.clone());
        self.commit(next)?;
        Ok(t)
    }
    /// Reconcile an existing execution, never spawn. Native observations, not
    /// requested settings, confirm the actual executor/model and preserve CU joins.
    pub fn confirm_started(&mut self, id: &str, receipt: LaunchReceipt) -> io::Result<()> {
        if let Some(old) = self.state.launches.get(&receipt.transition_id) {
            return if old == &receipt {
                Ok(())
            } else {
                Err(invalid("Conflicting immutable launch receipt"))
            };
        }
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        if let Some(old) = &w.launch_receipt {
            return if old == &receipt {
                Ok(())
            } else {
                Err(invalid("Conflicting immutable launch receipt"))
            };
        }
        let Phase::DispatchPending(t) = &w.phase else {
            return Err(invalid("No pending launch"));
        };
        if !present(&receipt.source_receipt)
            || !present(&receipt.native_session_id)
            || receipt.execution_id != t.execution_id
            || receipt.transition_id != t.transition_id
            || receipt.identity != t.identity
            || receipt.effective != t.candidate
        {
            return Err(invalid(
                "Native launch identity/settings mismatch; reconcile and hold",
            ));
        }
        let t = t.clone();
        let mut next = self.state.clone();
        next.launches
            .insert(receipt.transition_id.clone(), receipt.clone());
        let w = next.works.get_mut(id).unwrap();
        w.phase = Phase::Running(t);
        w.launch_receipt = Some(receipt);
        self.commit(next)
    }
    /// Trusted adapter guard for checkpoint-listed side effects. Completed effects
    /// return false; unknown/new effects cannot acquire permission by relabelling.
    /// Persist Unknown BEFORE a side effect. Lost replies need reconciliation.
    pub fn claim_effect(&mut self, id: &str, effect_id: &str) -> io::Result<bool> {
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        if !matches!(w.phase, Phase::Running(_)) {
            return Err(invalid("No confirmed owner"));
        }
        let e = w
            .effects
            .get(effect_id)
            .ok_or_else(|| invalid("Uncheckpointed effect requires review"))?;
        match e.outcome {
            EffectOutcome::Completed => return Ok(false),
            EffectOutcome::Unknown => return Err(invalid("Effect outcome must be reconciled")),
            EffectOutcome::NotStarted => {}
        }
        let mut next = self.state.clone();
        let e = next
            .works
            .get_mut(id)
            .unwrap()
            .effects
            .get_mut(effect_id)
            .unwrap();
        e.outcome = EffectOutcome::Unknown;
        e.receipt.clear();
        self.commit(next)?;
        Ok(true)
    }
    pub fn confirm_effect(&mut self, id: &str, effect_id: &str, receipt: &str) -> io::Result<()> {
        if !present(receipt) {
            return Err(invalid("Effect receipt required"));
        }
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        if !matches!(w.phase, Phase::Running(_)) {
            return Err(invalid("No confirmed owner"));
        }
        let e = w
            .effects
            .get(effect_id)
            .ok_or_else(|| invalid("Unknown effect"))?;
        if e.outcome == EffectOutcome::Completed {
            return if e.receipt == receipt {
                Ok(())
            } else {
                Err(invalid("Conflicting effect receipt"))
            };
        }
        if e.outcome != EffectOutcome::Unknown {
            return Err(invalid("No pending effect"));
        }
        let mut next = self.state.clone();
        let e = next
            .works
            .get_mut(id)
            .unwrap()
            .effects
            .get_mut(effect_id)
            .unwrap();
        e.outcome = EffectOutcome::Completed;
        e.receipt = receipt.into();
        self.commit(next)
    }
}
fn private_file(path: &Path) -> io::Result<()> {
    let m = fs::symlink_metadata(path)?;
    if !m.is_file() {
        return Err(invalid("Journal must be a real file"));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if m.mode() & 0o077 != 0 || m.nlink() != 1 {
            return Err(invalid("Private single-link journal required"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests;
