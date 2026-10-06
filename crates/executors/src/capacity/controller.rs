//! Durable authority for scheduled sessions. Quota decisions remain in CU.
//! Every mutation is serialized by the caller; files are private and fsynced.
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::{self, Write},
    path::{Path, PathBuf},
    sync::OnceLock,
};

use capacity_guard::Lease;
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;
use uuid::Uuid;

use super::{
    CapacityExecution,
    first_run::{self, Binding, FirstRun, InitializationState, Receipt},
    issuer_epoch, wall_ms,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ManagedGoal {
    #[serde(default)]
    pub goal_id: String,
    #[serde(default)]
    pub initialization_state: InitializationState,
    #[serde(default)]
    pub binding: Option<Binding>,
    #[serde(default)]
    pub initialization_receipt: Option<Receipt>,
    pub session_id: Uuid,
    pub thread_id: String,
    pub objective: String,
    pub created_at: i64,
    pub eligible: bool,
    pub reason: String,
    pub grant: Option<Grant>,
}
impl ManagedGoal {
    pub fn identity(&self) -> FirstRun {
        FirstRun {
            goal_id: self.goal_id.clone(),
            thread_id: self.thread_id.clone(),
            objective: self.objective.clone(),
            created_at: self.created_at,
        }
    }
    pub fn pending_identity(&self) -> Option<FirstRun> {
        (self.initialization_state == InitializationState::Pending).then(|| self.identity())
    }
    pub fn same_native_identity(&self, other: &Self) -> bool {
        self.thread_id == other.thread_id
            && self.objective == other.objective
            && self.created_at == other.created_at
            && (self.goal_id.is_empty() || self.goal_id == other.goal_id)
    }
    pub fn check_first_run(&self, intent: Option<&FirstRun>) -> io::Result<()> {
        match self.initialization_state {
            InitializationState::Pending
                if first_run::enabled()
                    && self.initialization_receipt.is_none()
                    && intent == Some(&self.identity()) =>
            {
                self.identity().validate()
            }
            InitializationState::Checkpointed if intent.is_none() => Ok(()),
            _ => Err(invalid(
                "Explicit matching firstRun authority required; held or legacy pending launches cannot run",
            )),
        }
    }
    pub async fn revalidate(&self, own: Option<Uuid>, bootstrap: bool) -> io::Result<()> {
        let current = first_run::native(&self.thread_id).await?;
        if current.thread_id != self.thread_id
            || current.objective != self.objective
            || current.created_at != self.created_at
            || (!self.goal_id.is_empty() && current.goal_id != self.goal_id)
        {
            return Err(invalid(
                "Native goal identity changed; explicit selection required",
            ));
        }
        if let Some(expected) = &self.binding {
            let actual = first_run::binding(
                Path::new(&expected.database),
                self.session_id,
                &self.thread_id,
                own,
            )
            .await?;
            if actual != *expected {
                return Err(invalid("Session/workspace/account/turn anchor changed"));
            }
        } else if self.initialization_state == InitializationState::Pending {
            return Err(invalid("First run has no native session binding"));
        }
        let p = first_run::read_progress(&current)?;
        match self.initialization_state {
            InitializationState::Pending => {
                if !first_run::enabled() || current.status != "paused" {
                    return Err(invalid("First run is no longer paused and admissible"));
                }
                if p.is_some()
                    && !(bootstrap
                        && self
                            .initialization_receipt
                            .as_ref()
                            .is_some_and(|r| r.execution_id == own))
                {
                    return Err(invalid(
                        "Pending first run already has progress; inspect before dispatch",
                    ));
                }
                if let Some(p) = p
                    && (!p.requirements.is_empty()
                        || !p.completed.is_empty()
                        || p.turns != 0
                        || p.last_turn.is_some()
                        || p.pause_reason.is_some())
                {
                    return Err(invalid("Unexpected bootstrap evidence"));
                }
                Ok(())
            }
            InitializationState::Checkpointed => {
                let p = p.ok_or_else(|| invalid("Checkpointed goal lost its progress"))?;
                first_run::valid_checklist(&p)?;
                validate_native_readiness(&current, &p)
            }
            InitializationState::Held => Err(invalid("First native run requires inspection")),
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Grant {
    pub id: Uuid,
    pub allocation_id: String,
    pub epoch: String,
    pub expires_at_ms: u64,
    pub stop_at_ms: u64,
    pub sequence: u64,
    pub execution_id: Option<Uuid>,
    pub stopping: bool,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct State {
    pub version: u32,
    pub epoch: String,
    pub revision: u64,
    pub foreground_until_ms: u64,
    pub goals: BTreeMap<Uuid, ManagedGoal>,
    #[serde(default)]
    pub issued_ids: BTreeSet<Uuid>,
}

pub struct Controller {
    root: PathBuf,
    guard: PathBuf,
    ownership: Option<fs::File>,
    pub state: State,
}
fn invalid(message: &str) -> io::Error {
    io::Error::other(message)
}
fn save(path: &Path, value: &impl Serialize) -> io::Result<()> {
    let tmp = path.with_extension(format!("{}.tmp", Uuid::new_v4()));
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let result = (|| {
        let mut file = options.open(&tmp)?;
        file.write_all(&serde_json::to_vec(value)?)?;
        file.sync_all()?;
        fs::rename(&tmp, path)?;
        fs::File::open(path.parent().ok_or_else(|| invalid("Missing parent"))?)?.sync_all()
    })();
    if result.is_err() {
        let _ = fs::remove_file(tmp);
    }
    result
}
impl Controller {
    /// Authenticated root-turn tool/message receipt, never file presence alone.
    pub fn initialization_checkpoint(
        &mut self,
        execution: Uuid,
        native: &crate::executors::codex::goals::NativeGoal,
        progress: &crate::executors::codex::goals::Progress,
        turn: &str,
    ) -> io::Result<()> {
        let mut next = self.state.clone();
        let Some(goal) = next.goals.values_mut().find(|g| {
            g.initialization_state == InitializationState::Pending
                && g.initialization_receipt
                    .as_ref()
                    .is_some_and(|r| r.execution_id == Some(execution))
        }) else {
            return Ok(());
        };
        if goal.identity() != FirstRun::from_native(native) || turn.is_empty() {
            return Err(invalid("First native checkpoint identity changed"));
        }
        let receipt = goal.initialization_receipt.as_mut().unwrap();
        if progress.pause_reason.is_some() {
            return Err(invalid("First native turn requires user input"));
        }
        first_run::valid_checklist(progress)?;
        if receipt
            .checkpoint_turn_id
            .as_deref()
            .is_some_and(|id| id != turn)
        {
            return Err(invalid("First native checkpoint moved to another turn"));
        }
        receipt.checkpoint_turn_id = Some(turn.into());
        self.commit(next)
    }
    pub fn promote_initialization(
        &mut self,
        execution: Uuid,
        native: &crate::executors::codex::goals::NativeGoal,
        progress: &crate::executors::codex::goals::Progress,
        turn: &str,
        now: u64,
    ) -> io::Result<()> {
        let mut next = self.state.clone();
        let Some(goal) = next.goals.values_mut().find(|g| {
            g.initialization_state == InitializationState::Pending
                && g.initialization_receipt
                    .as_ref()
                    .is_some_and(|r| r.execution_id == Some(execution))
        }) else {
            return Ok(());
        };
        let receipt = goal.initialization_receipt.as_ref().unwrap();
        let grant = goal
            .grant
            .as_ref()
            .ok_or_else(|| invalid("First native run lost its grant"))?;
        if !first_run::enabled()
            || goal.identity() != FirstRun::from_native(native)
            || progress.objective != goal.objective
            || progress.created_at != goal.created_at
            || receipt.checkpoint_turn_id.as_deref() != Some(turn)
            || progress.last_turn.as_deref() != Some(turn)
            || grant.stopping
            || grant.epoch != self.state.epoch
            || grant.expires_at_ms.saturating_sub(now) <= 2000
            || grant.stop_at_ms.saturating_sub(now) <= 2000
            || progress.pause_reason.is_some()
            || !matches!(native.status.as_str(), "active" | "complete")
        {
            return Err(invalid(
                "First native turn was not safely completed with authentic checklist evidence",
            ));
        }
        first_run::valid_checklist(progress)?;
        goal.initialization_state = InitializationState::Checkpointed;
        goal.reason = "Native first turn verified; checkpointed continuation available".into();
        if progress.all_complete() || native.status == "complete" {
            goal.eligible = false;
        }
        self.commit(next)
    }
    pub fn standby(root: PathBuf, guard: PathBuf) -> io::Result<Self> {
        if !root.is_absolute() || !guard.is_absolute() || !guard.is_file() {
            return Err(invalid(
                "Absolute controller directory and existing guard required",
            ));
        }
        Ok(Self {
            root,
            guard,
            ownership: None,
            state: State {
                version: 1,
                epoch: String::new(),
                revision: 0,
                foreground_until_ms: 0,
                goals: BTreeMap::new(),
                issued_ids: BTreeSet::new(),
            },
        })
    }
    pub fn is_owner(&self) -> bool {
        self.ownership.is_some()
    }
    pub fn ensure_owner(&self) -> io::Result<()> {
        if !self.is_owner() {
            return Err(invalid(
                "Capacity ownership released; explicit acquisition required",
            ));
        }
        Ok(())
    }
    pub fn release(&mut self, epoch: &str, revision: u64) -> io::Result<State> {
        self.check_revision(epoch, revision)?;
        if self.state.goals.values().any(|goal| goal.grant.is_some()) {
            return Err(invalid(
                "Drain and reconcile all capacity grants before release",
            ));
        }
        // Dropping our descriptor releases the same inode, never a replacement lock.
        self.ownership.take();
        Ok(self.state.clone())
    }
    pub fn acquire(&mut self, epoch: &str, revision: u64) -> io::Result<()> {
        if self.is_owner() {
            return Err(invalid("Already owns capacity controller"));
        }
        let next = Self::open_checked(
            self.root.clone(),
            self.guard.clone(),
            Uuid::new_v4().to_string(),
            Some((epoch, revision)),
        )?;
        *self = next;
        Ok(())
    }
    pub fn open(root: PathBuf, guard: PathBuf, epoch: String) -> io::Result<Self> {
        Self::open_checked(root, guard, epoch, None)
    }
    fn open_checked(
        root: PathBuf,
        guard: PathBuf,
        epoch: String,
        expected: Option<(&str, u64)>,
    ) -> io::Result<Self> {
        if !root.is_absolute() || !guard.is_absolute() || !guard.is_file() {
            return Err(invalid(
                "Absolute capacity state directory and existing guard required",
            ));
        }
        fs::create_dir_all(&root)?;
        if fs::symlink_metadata(&root)?.file_type().is_symlink() {
            return Err(invalid("Capacity directory cannot be a symlink"));
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::{MetadataExt, PermissionsExt};
            fs::set_permissions(&root, fs::Permissions::from_mode(0o700))?;
            if fs::symlink_metadata(&root)?.file_type().is_symlink()
                || fs::metadata(&root)?.mode() & 0o077 != 0
            {
                return Err(invalid("Private real capacity directory required"));
            }
        }
        let lock = fs::OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .open(root.join("controller.lock"))?;
        lock.try_lock().map_err(io::Error::other)?;
        let mut state: State = match fs::read(root.join("state.json")) {
            Ok(bytes) => serde_json::from_slice(&bytes)?,
            Err(e) if e.kind() == io::ErrorKind::NotFound => State {
                version: 1,
                epoch: epoch.clone(),
                revision: 0,
                foreground_until_ms: 0,
                goals: BTreeMap::new(),
                issued_ids: BTreeSet::new(),
            },
            Err(e) => return Err(e),
        };
        if !matches!(state.version, 1 | 2) || state.goals.len() > 100 {
            return Err(invalid("Unsupported capacity state"));
        }
        if let Some((expected_epoch, revision)) = expected {
            if state.epoch != expected_epoch || state.revision != revision {
                return Err(invalid(
                    "Stale ownership handover; read the current owner's release receipt",
                ));
            }
            if state.goals.values().any(|goal| goal.grant.is_some()) {
                return Err(invalid("Cannot acquire ownership with unreconciled grants"));
            }
        }
        for (id, goal) in &mut state.goals {
            if *id != goal.session_id {
                return Err(invalid("Invalid managed session identity"));
            }
            if let Some(grant) = &mut goal.grant {
                state.issued_ids.insert(grant.id);
                grant.stopping = true;
                goal.reason = "VK restarted; reconciling stopped execution".into();
            }
            if goal.initialization_state == InitializationState::Pending
                && goal.initialization_receipt.is_some()
            {
                goal.initialization_state = InitializationState::Held;
                goal.eligible = false;
                goal.reason =
                    "First native run interrupted by restart; inspect before any further work"
                        .into();
            }
        }
        state.epoch = epoch;
        let mut this = Self {
            root,
            guard,
            ownership: Some(lock),
            state,
        };
        this.commit(this.state.clone())?;
        this.revoke_files()?;
        Ok(this)
    }
    fn commit(&mut self, mut next: State) -> io::Result<()> {
        self.ensure_owner()?;
        // Old binaries must refuse this ledger rather than erase first-run holds.
        next.version = 2;
        next.revision = self
            .state
            .revision
            .checked_add(1)
            .ok_or_else(|| invalid("Revision exhausted"))?;
        save(&self.root.join("state.json"), &next)?;
        self.state = next;
        Ok(())
    }
    pub fn check_revision(&self, epoch: &str, revision: u64) -> io::Result<()> {
        self.ensure_owner()?;
        if epoch != self.state.epoch || revision != self.state.revision {
            return Err(invalid(
                "Stale capacity controller state; read and reconcile again",
            ));
        }
        Ok(())
    }
    pub fn lease_path(&self, id: Uuid) -> PathBuf {
        self.root.join(format!("{id}.json"))
    }
    pub fn enroll(&mut self, mut goal: ManagedGoal) -> io::Result<()> {
        if goal.grant.is_some()
            || goal.thread_id.is_empty()
            || goal.objective.trim().is_empty()
            || goal.objective.len() > 16_000
        {
            return Err(invalid("Invalid goal enrollment"));
        }
        if self
            .state
            .goals
            .get(&goal.session_id)
            .is_some_and(|old| old.grant.is_some())
        {
            return Err(invalid(
                "Reconcile current execution before changing eligibility",
            ));
        }
        if self.state.goals.len() >= 100 && !self.state.goals.contains_key(&goal.session_id) {
            return Err(invalid("Too many eligible goals"));
        }
        if let Some(old) = self.state.goals.get(&goal.session_id)
            && old.same_native_identity(&goal)
        {
            if goal.eligible && old.initialization_state != goal.initialization_state {
                return Err(invalid(
                    "Initialization evidence/state changed; inspect the stored goal rather than replacing its receipt",
                ));
            }
            if goal.eligible && old.initialization_state == InitializationState::Held {
                return Err(invalid(
                    "First native run is held; inspect it rather than reselecting it",
                ));
            }
            // Removal/reselection cannot launder a spent initialization receipt.
            goal.initialization_receipt = old.initialization_receipt.clone();
            goal.initialization_state = old.initialization_state.clone();
        }
        goal.reason = if goal.eligible {
            "Waiting for unused capacity"
        } else {
            "Not eligible"
        }
        .into();
        if goal.initialization_state == InitializationState::Held {
            goal.reason = self
                .state
                .goals
                .get(&goal.session_id)
                .map(|g| g.reason.clone())
                .unwrap_or_else(|| "First native run requires inspection".into());
        }
        let mut next = self.state.clone();
        next.goals.insert(goal.session_id, goal);
        self.commit(next)
    }
    pub fn issue(
        &mut self,
        session: Uuid,
        id: Uuid,
        allocation: String,
        expires: u64,
        stop: u64,
        now: u64,
    ) -> io::Result<CapacityExecution> {
        self.issue_with_first_run(session, id, allocation, expires, stop, now, None, None)
    }
    #[allow(clippy::too_many_arguments)]
    pub fn issue_with_first_run(
        &mut self,
        session: Uuid,
        id: Uuid,
        allocation: String,
        expires: u64,
        stop: u64,
        now: u64,
        first_run: Option<FirstRun>,
        binding: Option<Binding>,
    ) -> io::Result<CapacityExecution> {
        let active = self
            .state
            .goals
            .values()
            .filter(|g| g.grant.is_some())
            .collect::<Vec<_>>();
        if self.state.foreground_until_ms > now
            || active.len() >= 2
            || active.iter().any(|g| {
                let grant = g.grant.as_ref().unwrap();
                g.session_id == session
                    || grant.stopping
                    || grant.execution_id.is_none()
                    || grant.expires_at_ms.saturating_sub(now) <= 2000
                    || grant.epoch != self.state.epoch
                    || grant.allocation_id != allocation
                    || grant.stop_at_ms != stop
                    || self
                        .state
                        .goals
                        .get(&session)
                        .is_some_and(|next| next.thread_id == g.thread_id)
            })
        {
            return Err(invalid(
                "Interactive priority, two-agent limit, or unreconciled background execution",
            ));
        }
        if self.state.issued_ids.contains(&id)
            || self.lease_path(id).exists()
            || self.lease_path(id).with_extension("started").exists()
        {
            return Err(invalid("Permission ID already used"));
        }
        let goal = self
            .state
            .goals
            .get(&session)
            .filter(|g| g.eligible)
            .ok_or_else(|| invalid("Goal is not eligible"))?;
        goal.check_first_run(first_run.as_ref())?;
        let lease = Lease {
            version: 1,
            id: id.to_string(),
            allocation_id: allocation.clone(),
            execution_id: session.to_string(),
            expires_at_ms: expires,
            stop_at_ms: stop,
            sequence: 0,
            revoked: false,
        };
        lease.validate(now).map_err(invalid)?;
        if expires.saturating_sub(now) < 3000 {
            return Err(invalid("Permission is too close to expiry"));
        }
        let mut next = self.state.clone();
        let goal = next.goals.get_mut(&goal.session_id).unwrap();
        next.issued_ids.insert(id);
        goal.grant = Some(Grant {
            id,
            allocation_id: allocation.clone(),
            epoch: self.state.epoch.clone(),
            expires_at_ms: expires,
            stop_at_ms: stop,
            sequence: 0,
            execution_id: None,
            stopping: false,
        });
        if let Some(binding) = binding {
            goal.binding = Some(binding);
        }
        goal.reason = "Starting scheduled goal".into();
        if first_run.is_some() {
            goal.initialization_receipt = Some(Receipt {
                grant_id: id,
                execution_id: None,
                checkpoint_turn_id: None,
            });
        }
        self.commit(next)?;
        Ok(CapacityExecution {
            first_run,
            controller_revision: self.state.revision,
            // Process identity protects persisted actions; controller epochs
            // separately rotate each time this process reacquires ownership.
            issuer_epoch: issuer_epoch().into(),
            id: id.to_string(),
            allocation_id: allocation,
            expires_at_ms: expires,
            stop_at_ms: stop,
            lease_file: self.lease_path(id).to_string_lossy().into_owned(),
            guard_binary: self.guard.to_string_lossy().into_owned(),
        })
    }
    /// Called again at the executor's actual lease-creation boundary.
    pub fn bind(
        &mut self,
        request: &CapacityExecution,
        thread: &str,
        execution: Uuid,
        now: u64,
    ) -> io::Result<()> {
        let id = Uuid::parse_str(&request.id).map_err(io::Error::other)?;
        let (session, goal) = self
            .state
            .goals
            .iter()
            .find(|(_, g)| g.grant.as_ref().is_some_and(|x| x.id == id))
            .ok_or_else(|| invalid("No durable grant for launch"))?;
        let grant = goal.grant.as_ref().unwrap();
        if goal.thread_id != thread {
            return Err(invalid("Launch refers to another native goal"));
        }
        if !goal.eligible
            || grant.stopping
            || grant.execution_id.is_some()
            || grant.epoch != self.state.epoch
            || request.issuer_epoch != issuer_epoch()
            || grant.expires_at_ms <= now
            || self.state.foreground_until_ms > now
            || grant.allocation_id != request.allocation_id
            || grant.expires_at_ms != request.expires_at_ms
            || grant.stop_at_ms != request.stop_at_ms
            || request.lease_file != self.lease_path(id).to_string_lossy()
            || request.guard_binary != self.guard.to_string_lossy()
            || request.first_run.as_ref() != goal.pending_identity().as_ref()
            || (request.first_run.is_some() && request.controller_revision != self.state.revision)
        {
            return Err(invalid(
                "Launch permission was revoked, changed, expired or already bound",
            ));
        }
        let mut next = self.state.clone();
        if request.first_run.is_some() {
            let receipt = next
                .goals
                .get_mut(session)
                .unwrap()
                .initialization_receipt
                .as_mut()
                .ok_or_else(|| invalid("Missing owned initialization receipt"))?;
            if receipt.grant_id != id || receipt.execution_id.is_some() {
                return Err(invalid("Initialization already attempted"));
            }
            receipt.execution_id = Some(execution);
        }
        next.goals
            .get_mut(session)
            .unwrap()
            .grant
            .as_mut()
            .unwrap()
            .execution_id = Some(execution);
        next.goals.get_mut(session).unwrap().reason = "Running with unused daily capacity".into();
        self.commit(next)
    }
    pub fn renew(
        &mut self,
        session: Uuid,
        id: Uuid,
        allocation: &str,
        sequence: u64,
        expires: u64,
        now: u64,
    ) -> io::Result<()> {
        let goal = self
            .state
            .goals
            .get(&session)
            .ok_or_else(|| invalid("Unknown goal"))?;
        let grant = goal
            .grant
            .as_ref()
            .ok_or_else(|| invalid("No current grant"))?;
        let file = self.lease_path(grant.id);
        let mut lease = capacity_guard::read_lease(&file)?;
        if lease.id != grant.id.to_string()
            || lease.allocation_id != grant.allocation_id
            || lease.stop_at_ms != grant.stop_at_ms
        {
            return Err(invalid("Permission file identity or deadline changed"));
        }
        if !goal.eligible
            || grant.stopping
            || grant.epoch != self.state.epoch
            || grant.id != id
            || grant.allocation_id != allocation
            || grant.sequence != sequence
            || grant.expires_at_ms.saturating_sub(now) <= 2000
            || self.state.foreground_until_ms > now
            || lease.sequence != sequence
            || lease.expires_at_ms != grant.expires_at_ms
            || lease.revoked
            || Some(lease.execution_id.as_str())
                != grant
                    .execution_id
                    .as_ref()
                    .map(|id| id.to_string())
                    .as_deref()
        {
            return Err(invalid(
                "Renewal rejected; reconcile stopped or changed permission",
            ));
        }
        lease.sequence = sequence
            .checked_add(1)
            .ok_or_else(|| invalid("Sequence exhausted"))?;
        lease.expires_at_ms = expires;
        lease.validate(now).map_err(invalid)?;
        if expires <= grant.expires_at_ms {
            return Err(invalid("Renewal must extend current expiry"));
        }
        let mut next = self.state.clone();
        let grant = next
            .goals
            .get_mut(&session)
            .unwrap()
            .grant
            .as_mut()
            .unwrap();
        grant.sequence = lease.sequence;
        grant.expires_at_ms = expires;
        self.commit(next)?;
        save(&file, &lease)
    }
    pub fn revoke_all(&mut self, reason: &str, foreground_until: Option<u64>) -> io::Result<()> {
        self.revoke(reason, foreground_until, None)
    }
    pub fn revoke_session(&mut self, session: Uuid, reason: &str) -> io::Result<()> {
        self.revoke(reason, None, Some(session))
    }
    fn revoke(
        &mut self,
        reason: &str,
        foreground_until: Option<u64>,
        session: Option<Uuid>,
    ) -> io::Result<()> {
        self.ensure_owner()?;
        let mut next = self.state.clone();
        if let Some(until) = foreground_until {
            next.foreground_until_ms = next.foreground_until_ms.max(until);
        }
        for goal in next.goals.values_mut() {
            if session.is_some_and(|id| id != goal.session_id) {
                continue;
            }
            if let Some(grant) = &mut goal.grant {
                grant.stopping = true;
                goal.reason = reason.into();
                if goal.initialization_state == InitializationState::Pending
                    && goal.initialization_receipt.is_some()
                {
                    goal.initialization_state = InitializationState::Held;
                    goal.eligible = false;
                }
            }
        }
        // Persistence failure must never leave in-memory renewal authority open.
        // A restart independently invalidates old grants; existing guards also
        // enforce the last short lease even if its revocation cannot be written.
        if let Err(error) = self.commit(next.clone()) {
            self.state = next;
            let _ = self.revoke_files();
            return Err(error);
        }
        self.revoke_files()
    }
    fn revoke_files(&self) -> io::Result<()> {
        self.ensure_owner()?;
        for goal in self.state.goals.values() {
            if let Some(grant) = &goal.grant
                && grant.stopping
            {
                let path = self.lease_path(grant.id);
                match capacity_guard::read_lease(&path) {
                    Ok(mut lease) => {
                        lease.revoked = true;
                        save(&path, &lease)?;
                    }
                    Err(e) if e.kind() == io::ErrorKind::NotFound => {}
                    // Removing unreadable permission is fail closed at the guard.
                    Err(_) => {
                        fs::remove_file(&path)?;
                        fs::File::open(&self.root)?.sync_all()?;
                    }
                }
            }
        }
        Ok(())
    }
    /// Caller must establish cgroup/process exit. Mere native RPC success is insufficient.
    pub fn stopped(&mut self, session: Uuid, id: Uuid, reason: String) -> io::Result<()> {
        let mut next = self.state.clone();
        let goal = next
            .goals
            .get_mut(&session)
            .ok_or_else(|| invalid("Unknown goal"))?;
        if goal.grant.as_ref().is_none_or(|g| g.id != id) {
            return Err(invalid("Grant changed during stop reconciliation"));
        }
        goal.grant = None;
        goal.reason = reason;
        if goal.initialization_state == InitializationState::Pending
            && goal.initialization_receipt.is_some()
        {
            goal.initialization_state = InitializationState::Held;
            goal.eligible = false;
        }
        self.commit(next)
    }
}

pub fn configured() -> io::Result<Option<&'static Mutex<Controller>>> {
    static CONTROLLER: OnceLock<Result<Option<Mutex<Controller>>, String>> = OnceLock::new();
    let result = CONTROLLER.get_or_init(|| {
        let Ok(root) = std::env::var("VK_CAPACITY_STATE_DIR") else {
            return Ok(None);
        };
        let guard = std::env::var("VK_CAPACITY_GUARD")
            .map_err(|_| "VK_CAPACITY_GUARD is required".to_string())?;
        let controller = match std::env::var("VK_CAPACITY_START_PAUSED").as_deref() {
            Ok("1") => Controller::standby(root.into(), guard.into()),
            Ok("0") | Err(std::env::VarError::NotPresent) => {
                Controller::open(root.into(), guard.into(), issuer_epoch().into())
            }
            _ => return Err("VK_CAPACITY_START_PAUSED must be 0 or 1".into()),
        };
        controller
            .map(|c| Some(Mutex::new(c)))
            .map_err(|e| e.to_string())
    });
    match result {
        Ok(value) => Ok(value.as_ref()),
        Err(message) => Err(invalid(message)),
    }
}

pub async fn before_launch(session: Uuid, background: bool) -> io::Result<()> {
    admit_launch(configured(), session, background).await
}

async fn admit_launch(
    controller: io::Result<Option<&Mutex<Controller>>>,
    session: Uuid,
    background: bool,
) -> io::Result<()> {
    let controller = match controller {
        Ok(controller) => controller,
        Err(error) if !background => {
            tracing::warn!(%error, "Capacity controller unavailable; ordinary work remains available");
            return Ok(());
        }
        Err(error) => return Err(error),
    };
    let Some(controller) = controller else {
        return if background {
            Err(invalid("No scheduled goal controller"))
        } else {
            Ok(())
        };
    };
    let mut c = controller.lock().await;
    c.ensure_owner()?;
    if !background {
        let owned = c.state.goals.get(&session).and_then(|g| g.grant.clone());
        if let Err(error) = c.revoke_all(
            "Interactive work takes priority",
            Some(wall_ms() + 10 * 60_000),
        ) {
            tracing::warn!(%error, "Background authority fenced; ordinary launch continues despite capacity storage failure");
        }
        // Idle selection is not an execution lock. For an active selected goal,
        // revoke first and confirm containment exit before allowing a second
        // app-server to touch the same native thread. Keep the selection saved.
        drop(c);
        if let Some(grant) = owned {
            if let Some(execution) = grant.execution_id {
                let _ = tokio::time::timeout(
                    std::time::Duration::from_secs(3),
                    crate::executors::codex::client::AppServerClient::suspend_capacity_execution(
                        execution,
                        "Manual work takes priority".into(),
                    ),
                )
                .await;
                if !stop_execution_unit(execution).await? {
                    return Err(invalid(
                        "Background work is still stopping; retry your message shortly",
                    ));
                }
            }
            let mut c = controller.lock().await;
            if c.state
                .goals
                .get(&session)
                .and_then(|g| g.grant.as_ref())
                .is_some_and(|g| g.id == grant.id)
            {
                c.stopped(session, grant.id, "Paused for manual work".into())?;
            }
        }
    }
    Ok(())
}

pub async fn stop_execution_unit(execution: Uuid) -> io::Result<bool> {
    let unit = crate::capacity::unit_name(execution);
    let _ = tokio::time::timeout(
        std::time::Duration::from_secs(3),
        tokio::process::Command::new("systemctl")
            .args(["--user", "stop", &unit])
            .kill_on_drop(true)
            .output(),
    )
    .await;
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(2),
        tokio::process::Command::new("systemctl")
            .args([
                "--user",
                "show",
                &unit,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=ControlGroup",
            ])
            .kill_on_drop(true)
            .output(),
    )
    .await
    .map_err(|_| invalid("Cannot verify execution shutdown"))??;
    let text = String::from_utf8_lossy(&output.stdout);
    let values: std::collections::HashMap<_, _> =
        text.lines().filter_map(|l| l.split_once('=')).collect();
    if values.get("LoadState") == Some(&"not-found") {
        return Ok(true);
    }
    if !matches!(values.get("ActiveState"), Some(&"inactive" | &"failed")) {
        return Ok(false);
    }
    let Some(group) = values.get("ControlGroup") else {
        return Ok(false);
    };
    if group.is_empty() {
        return Ok(true);
    }
    if !group.starts_with('/') || group.contains("..") {
        return Ok(false);
    }
    match tokio::fs::read_to_string(format!("/sys/fs/cgroup{group}/cgroup.events")).await {
        Ok(events) => Ok(events.lines().any(|l| l == "populated 0")),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(true),
        Err(e) => Err(e),
    }
}

pub async fn record_launch_failure(execution: Uuid, reason: &str) {
    if let Ok(Some(controller)) = configured() {
        let mut c = controller.lock().await;
        if let Some(session) = c
            .state
            .goals
            .values()
            .find(|g| {
                g.grant
                    .as_ref()
                    .is_some_and(|grant| grant.execution_id == Some(execution))
            })
            .map(|g| g.session_id)
        {
            let reason = format!(
                "Could not start: {}",
                reason.chars().take(500).collect::<String>()
            );
            if let Err(error) = c.revoke_session(session, &reason) {
                tracing::warn!(%error, "Could not persist scheduled launch failure");
            }
        }
    }
}

pub async fn validate_native(lease: &Lease, snapshot: &serde_json::Value) -> io::Result<()> {
    let controller = configured()?.ok_or_else(|| invalid("No scheduled goal controller"))?;
    let c = controller.lock().await;
    c.ensure_owner()?;
    let goal = c
        .state
        .goals
        .values()
        .find(|g| {
            g.grant
                .as_ref()
                .is_some_and(|x| x.id.to_string() == lease.id && !x.stopping)
        })
        .ok_or_else(|| invalid("Scheduled goal authority changed"))?;
    let native: crate::executors::codex::goals::NativeGoal =
        serde_json::from_value(snapshot["goal"].clone())?;
    let native = first_run::resolve_wire(native).await?;
    match goal.initialization_state {
        InitializationState::Pending if native.status == "paused" => {}
        InitializationState::Checkpointed => {
            let progress =
                first_run::read_progress(&native)?.ok_or_else(|| invalid("Missing checkpoint"))?;
            validate_native_readiness(&native, &progress)?;
        }
        _ => return Err(invalid("Native status no longer permits dispatch")),
    }
    if native.thread_id != goal.thread_id
        || native.objective != goal.objective
        || native.created_at != goal.created_at
        || native.status == "complete"
        || (!goal.goal_id.is_empty() && native.goal_id != goal.goal_id)
    {
        return Err(invalid(
            "Native goal changed; select its new objective explicitly",
        ));
    }
    goal.revalidate(Uuid::parse_str(&lease.execution_id).ok(), false)
        .await?;
    Ok(())
}

// Goal status is the app-server wire value, not the SQLite storage spelling.
pub fn validate_native_readiness(
    native: &crate::executors::codex::goals::NativeGoal,
    progress: &crate::executors::codex::goals::Progress,
) -> io::Result<()> {
    if progress.objective != native.objective || progress.created_at != native.created_at {
        return Err(invalid("Native checkpoint identity changed"));
    }
    first_run::valid_checklist(progress)?;
    if let Some(reason) = &progress.pause_reason {
        return Err(invalid(&format!(
            "Goal is waiting for your input: {reason}"
        )));
    }
    if progress.all_complete() {
        return Err(invalid(
            "Goal checklist is complete; no scheduled work remains",
        ));
    }
    match native.status.as_str() {
        "paused" | "active" | "usageLimited" => Ok(()),
        "budgetLimited" => Err(invalid(
            "Goal has reached its token budget; scheduled work cannot raise it",
        )),
        "blocked" => Err(invalid(
            "Goal is blocked; resolve it before scheduled continuation",
        )),
        "complete" => Err(invalid("Goal is complete; no scheduled work remains")),
        status => Err(invalid(&format!(
            "Unsupported native goal status: {status}"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn pending(f: &mut Fixture) -> FirstRun {
        let c = f.c.as_mut().unwrap();
        let mut goal = c.state.goals[&f.session].clone();
        goal.goal_id = Uuid::new_v4().to_string();
        goal.created_at += 1; // a distinct synthetic uninitialized identity
        goal.initialization_state = InitializationState::Pending;
        c.enroll(goal.clone()).unwrap();
        goal.identity()
    }
    fn first_issue(f: &mut Fixture, identity: FirstRun) -> CapacityExecution {
        f.c.as_mut()
            .unwrap()
            .issue_with_first_run(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000,
                Some(identity),
                None,
            )
            .unwrap()
    }
    #[test]
    fn lost_checkpoint_cannot_be_reclassified_as_a_pending_first_run() {
        let mut f = Fixture::new();
        let c = f.c.as_mut().unwrap();
        let mut goal = c.state.goals[&f.session].clone();
        goal.initialization_state = InitializationState::Pending;
        goal.goal_id = Uuid::new_v4().to_string();
        assert!(c.enroll(goal).is_err());
        assert_eq!(
            c.state.goals[&f.session].initialization_state,
            InitializationState::Checkpointed
        );
    }
    #[test]
    fn first_run_selection_is_inert_and_removal_survives_restart() {
        if !first_run::enabled() {
            return;
        }
        let mut f = Fixture::new();
        let identity = pending(&mut f);
        let c = f.c.as_mut().unwrap();
        assert!(c.state.goals[&f.session].grant.is_none());
        assert!(c.state.goals[&f.session].initialization_receipt.is_none());
        assert!(
            !crate::executors::codex::goals::progress_path(&identity.thread_id)
                .unwrap()
                .exists()
        );
        assert_eq!(fs::read_dir(&f.root).unwrap().count(), 2); // ledger and owner lock only
        f.c.take();
        let mut c = Controller::open(f.root.clone(), f.guard.clone(), "restarted".into()).unwrap();
        assert_eq!(
            c.state.goals[&f.session].initialization_state,
            InitializationState::Pending
        );
        let mut goal = c.state.goals[&f.session].clone();
        goal.eligible = false;
        c.enroll(goal).unwrap();
        assert!(
            c.issue_with_first_run(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000,
                Some(identity.clone()),
                None
            )
            .is_err()
        );
        assert_eq!(c.state.goals[&f.session].identity(), identity);
        f.c = Some(c);
    }
    #[test]
    fn first_run_rejects_legacy_identity_races_and_revision_changes() {
        if !first_run::enabled() {
            return;
        }
        let mut f = Fixture::new();
        let identity = pending(&mut f);
        let c = f.c.as_mut().unwrap();
        assert!(
            c.issue(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000
            )
            .is_err()
        );
        for field in 0..4 {
            let mut changed = identity.clone();
            match field {
                0 => changed.goal_id = Uuid::new_v4().to_string(),
                1 => changed.thread_id = "different".into(),
                2 => changed.objective.push('!'),
                _ => changed.created_at += 1,
            }
            assert!(
                c.issue_with_first_run(
                    f.session,
                    Uuid::new_v4(),
                    "old-week:day".into(),
                    30_000,
                    90_000,
                    1000,
                    Some(changed),
                    None
                )
                .is_err()
            );
        }
        let request = first_issue(&mut f, identity);
        let c = f.c.as_mut().unwrap();
        let mut legacy = request.clone();
        legacy.first_run = None;
        assert!(
            c.bind(&legacy, "native-thread", Uuid::new_v4(), 1000)
                .is_err()
        );
        let mut stale = request.clone();
        stale.controller_revision -= 1;
        assert!(
            c.bind(&stale, "native-thread", Uuid::new_v4(), 1000)
                .is_err()
        );
        c.bind(&request, "native-thread", Uuid::new_v4(), 1000)
            .unwrap();
        assert!(
            c.bind(&request, "native-thread", Uuid::new_v4(), 1000)
                .is_err()
        );
    }
    #[test]
    fn ambiguous_first_dispatch_is_held_and_cannot_be_laundered_by_reselection() {
        if !first_run::enabled() {
            return;
        }
        let mut f = Fixture::new();
        let identity = pending(&mut f);
        let request = first_issue(&mut f, identity.clone());
        f.c.take();
        let mut c = Controller::open(f.root.clone(), f.guard.clone(), "restart".into()).unwrap();
        assert_eq!(
            c.state.goals[&f.session].initialization_state,
            InitializationState::Held
        );
        assert!(!c.state.goals[&f.session].eligible);
        c.stopped(
            f.session,
            Uuid::parse_str(&request.id).unwrap(),
            "Verified exit; still ambiguous".into(),
        )
        .unwrap();
        let mut goal = c.state.goals[&f.session].clone();
        goal.eligible = true;
        assert!(c.enroll(goal.clone()).is_err());
        goal.eligible = false;
        c.enroll(goal).unwrap();
        assert!(
            c.issue_with_first_run(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000,
                Some(identity),
                None
            )
            .is_err()
        );
        assert!(
            !crate::executors::codex::goals::progress_path("native-thread")
                .unwrap()
                .exists()
        );
        f.c = Some(c);
    }
    #[test]
    fn first_run_promotion_requires_owned_root_checkpoint_and_completed_turn() {
        if !first_run::enabled() {
            return;
        }
        use crate::executors::codex::goals::{NativeGoal, Progress};
        let mut f = Fixture::new();
        let identity = pending(&mut f);
        let request = first_issue(&mut f, identity.clone());
        let execution = Uuid::new_v4();
        let c = f.c.as_mut().unwrap();
        c.bind(&request, "native-thread", execution, 1000).unwrap();
        let native = NativeGoal {
            goal_id: identity.goal_id,
            thread_id: identity.thread_id,
            objective: identity.objective.clone(),
            created_at: identity.created_at,
            status: "active".into(),
        };
        let mut p = Progress {
            objective: native.objective.clone(),
            created_at: native.created_at,
            ..Default::default()
        };
        p.finish_turn("one");
        assert!(
            c.promote_initialization(execution, &native, &p, "one", 2000)
                .is_err()
        );
        p.checkpoint(serde_json::json!({"requirements":{"deliver":"Deliver requested outcome"},"completed":{},"disposition":"continue","reason":""})).unwrap();
        assert!(
            c.promote_initialization(execution, &native, &p, "one", 2000)
                .is_err()
        );
        c.initialization_checkpoint(execution, &native, &p, "one")
            .unwrap();
        assert!(
            c.promote_initialization(execution, &native, &p, "different", 2000)
                .is_err()
        );
        assert!(
            c.promote_initialization(execution, &native, &p, "one", 29_000)
                .is_err()
        );
        let mut held = p.clone();
        held.pause_reason = Some("Choose behavior".into());
        assert!(
            c.promote_initialization(execution, &native, &held, "one", 2000)
                .is_err()
        );
        c.promote_initialization(execution, &native, &p, "one", 2000)
            .unwrap();
        assert_eq!(
            c.state.goals[&f.session].initialization_state,
            InitializationState::Checkpointed
        );
        c.stopped(
            f.session,
            Uuid::parse_str(&request.id).unwrap(),
            "Verified exit".into(),
        )
        .unwrap();
        assert!(
            c.issue(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                2000
            )
            .is_ok()
        );
    }
    #[test]
    fn revoked_first_run_never_promotes_or_reissues() {
        if !first_run::enabled() {
            return;
        }
        let mut f = Fixture::new();
        let identity = pending(&mut f);
        let request = first_issue(&mut f, identity.clone());
        let c = f.c.as_mut().unwrap();
        c.revoke_session(f.session, "Cutoff or stale quota")
            .unwrap();
        assert!(
            c.bind(&request, "native-thread", Uuid::new_v4(), 1000)
                .is_err()
        );
        c.stopped(
            f.session,
            Uuid::parse_str(&request.id).unwrap(),
            "Stopped".into(),
        )
        .unwrap();
        assert!(
            c.issue_with_first_run(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000,
                Some(identity),
                None
            )
            .is_err()
        );
        assert_eq!(
            c.state.goals[&f.session].initialization_state,
            InitializationState::Held
        );
    }
    #[test]
    fn native_usage_limited_wire_response_can_resume_but_user_and_budget_stops_cannot() {
        use crate::executors::codex::goals::{NativeGoal, Progress};
        // Shape and casing captured from the installed app-server's goal/get
        // response for the goal rejected on September 21.
        let mut native: NativeGoal = serde_json::from_value(serde_json::json!({
            "threadId": "01a0801c-5784-7560-8919-3783ef7ccc7c",
            "objective": "Finish existing development goal", "status": "usageLimited",
            "tokenBudget": null, "tokensUsed": 32377768, "timeUsedSeconds": 44554,
            "createdAt": 1789223198, "updatedAt": 1789327215
        }))
        .unwrap();
        let mut progress = Progress {
            objective: native.objective.clone(),
            created_at: native.created_at,
            ..Default::default()
        };
        progress
            .requirements
            .insert("work".into(), "Finish remaining work".into());
        validate_native_readiness(&native, &progress).unwrap();
        progress.pause_reason = Some("Choose required behavior".into());
        assert!(
            validate_native_readiness(&native, &progress)
                .unwrap_err()
                .to_string()
                .contains("Choose required behavior")
        );
        progress.pause_reason = None;
        progress
            .completed
            .insert("work".into(), "Verified complete".into());
        assert!(validate_native_readiness(&native, &progress).is_err());
        progress.completed.clear();
        for status in [
            "budgetLimited",
            "blocked",
            "complete",
            "usage_limited",
            "unknown",
        ] {
            native.status = status.into();
            assert!(
                validate_native_readiness(&native, &progress).is_err(),
                "{status}"
            );
        }
        for status in ["paused", "active"] {
            native.status = status.into();
            validate_native_readiness(&native, &progress).unwrap();
        }
    }

    struct Fixture {
        root: PathBuf,
        guard: PathBuf,
        session: Uuid,
        c: Option<Controller>,
    }
    impl Fixture {
        fn new() -> Self {
            let root =
                std::env::temp_dir().join(format!("vk-capacity-controller-{}", Uuid::new_v4()));
            let guard = std::env::current_exe().unwrap();
            let mut c = Controller::open(root.clone(), guard.clone(), "test-epoch".into()).unwrap();
            let session = Uuid::new_v4();
            c.enroll(ManagedGoal {
                goal_id: String::new(),
                initialization_state: InitializationState::Checkpointed,
                binding: None,
                initialization_receipt: None,
                session_id: session,
                thread_id: "native-thread".into(),
                objective: "Preserve full development objective".into(),
                created_at: 123,
                eligible: true,
                reason: String::new(),
                grant: None,
            })
            .unwrap();
            Self {
                root,
                guard,
                session,
                c: Some(c),
            }
        }
        fn issue(&mut self) -> CapacityExecution {
            self.c
                .as_mut()
                .unwrap()
                .issue(
                    self.session,
                    Uuid::new_v4(),
                    "old-week:day".into(),
                    30_000,
                    90_000,
                    1000,
                )
                .unwrap()
        }
        fn launch(&mut self, request: &CapacityExecution) -> Lease {
            let execution = Uuid::new_v4();
            self.c
                .as_mut()
                .unwrap()
                .bind(request, "native-thread", execution, 1000)
                .unwrap();
            let lease = Lease {
                version: 1,
                id: request.id.clone(),
                allocation_id: request.allocation_id.clone(),
                execution_id: execution.to_string(),
                expires_at_ms: request.expires_at_ms,
                stop_at_ms: request.stop_at_ms,
                sequence: 0,
                revoked: false,
            };
            save(Path::new(&request.lease_file), &lease).unwrap();
            lease
        }
    }

    #[test]
    fn ownership_handover_reloads_latest_state_on_return() {
        let mut f = Fixture::new();
        let a = f.c.as_mut().unwrap();
        let mut b = Controller::standby(f.root.clone(), f.guard.clone()).unwrap();
        let epoch = a.state.epoch.clone();
        let revision = a.state.revision;
        assert!(b.acquire(&epoch, revision).is_err());
        let released = a.release(&epoch, revision).unwrap();
        assert!(!a.is_owner());
        assert!(a.revoke_all("stale writer", None).is_err());
        assert!(a.check_revision(&epoch, revision).is_err());
        b.acquire(&released.epoch, released.revision).unwrap();
        assert_ne!(b.state.epoch, epoch);
        let mut goal = b.state.goals[&f.session].clone();
        goal.eligible = false;
        b.enroll(goal).unwrap();
        let used = Uuid::new_v4();
        let mut next = b.state.clone();
        next.issued_ids.insert(used);
        next.foreground_until_ms += 1000;
        b.commit(next).unwrap();
        let back = b.release(&b.state.epoch.clone(), b.state.revision).unwrap();
        let disk = fs::read(f.root.join("state.json")).unwrap();
        assert!(a.acquire(&epoch, revision).is_err());
        assert_eq!(fs::read(f.root.join("state.json")).unwrap(), disk);
        assert!(!a.is_owner());
        a.acquire(&back.epoch, back.revision).unwrap();
        assert!(!a.state.goals[&f.session].eligible);
        assert!(a.state.issued_ids.contains(&used));
        assert_eq!(a.state.foreground_until_ms, back.foreground_until_ms);
        assert_ne!(a.state.epoch, back.epoch);
        assert!(b.acquire(&back.epoch, back.revision).is_err());
        let mut goal = a.state.goals[&f.session].clone();
        goal.eligible = true;
        a.enroll(goal).unwrap();
        let request = a
            .issue(
                f.session,
                Uuid::new_v4(),
                "new-allocation".into(),
                30_000,
                90_000,
                2000,
            )
            .unwrap();
        assert_eq!(request.issuer_epoch, issuer_epoch());
        a.bind(&request, "native-thread", Uuid::new_v4(), 2000)
            .unwrap();
    }

    #[test]
    fn ownership_release_rejects_unreconciled_grants_and_stale_receipts() {
        let mut f = Fixture::new();
        f.issue();
        let c = f.c.as_mut().unwrap();
        assert!(c.release(&c.state.epoch.clone(), c.state.revision).is_err());
        assert!(c.is_owner());
        assert!(c.release("wrong", c.state.revision).is_err());
        assert!(Controller::open(f.root.clone(), f.guard.clone(), "other".into()).is_err());
    }

    #[tokio::test]
    async fn released_owner_cannot_admit_foreground_or_background_work() {
        let mut f = Fixture::new();
        let mut c = f.c.take().unwrap();
        c.release(&c.state.epoch.clone(), c.state.revision).unwrap();
        let before = fs::read(f.root.join("state.json")).unwrap();
        let c = Mutex::new(c);
        assert!(admit_launch(Ok(Some(&c)), f.session, false).await.is_err());
        assert!(admit_launch(Ok(Some(&c)), f.session, true).await.is_err());
        assert_eq!(fs::read(f.root.join("state.json")).unwrap(), before);
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            self.c.take();
            let _ = fs::remove_dir_all(&self.root);
        }
    }
    #[test]
    fn two_grants_have_independent_revocation_and_a_hard_concurrency_limit() {
        let mut f = Fixture::new();
        let first = f.issue();
        let first_lease = f.launch(&first);
        let c = f.c.as_mut().unwrap();
        let second_session = Uuid::new_v4();
        let mut second = c.state.goals[&f.session].clone();
        second.session_id = second_session;
        second.grant = None;
        c.enroll(second.clone()).unwrap();
        assert!(
            c.issue(
                second_session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000
            )
            .is_err(),
            "same native thread cannot run twice"
        );
        second.thread_id = "second-thread".into();
        c.enroll(second).unwrap();
        assert!(
            c.issue(
                second_session,
                Uuid::new_v4(),
                "different-allocation".into(),
                30_000,
                90_000,
                1000
            )
            .is_err()
        );
        let request = c
            .issue(
                second_session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000,
            )
            .unwrap();
        let execution = Uuid::new_v4();
        c.bind(&request, "second-thread", execution, 1000).unwrap();
        let second_lease = Lease {
            id: request.id.clone(),
            execution_id: execution.to_string(),
            ..first_lease.clone()
        };
        save(Path::new(&request.lease_file), &second_lease).unwrap();
        let third_session = Uuid::new_v4();
        let mut third = c.state.goals[&second_session].clone();
        third.session_id = third_session;
        third.thread_id = "third-thread".into();
        third.grant = None;
        c.enroll(third).unwrap();
        assert!(
            c.issue(
                third_session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000
            )
            .is_err()
        );
        c.revoke_session(second_session, "Individual cap reached")
            .unwrap();
        assert!(
            capacity_guard::read_lease(Path::new(&request.lease_file))
                .unwrap()
                .revoked
        );
        assert!(
            !capacity_guard::read_lease(Path::new(&first.lease_file))
                .unwrap()
                .revoked
        );
        c.renew(
            f.session,
            Uuid::parse_str(&first.id).unwrap(),
            "old-week:day",
            0,
            40_000,
            10_000,
        )
        .unwrap();
        c.revoke_all("Interactive work", Some(600_000)).unwrap();
        assert!(
            capacity_guard::read_lease(Path::new(&first.lease_file))
                .unwrap()
                .revoked
        );
    }

    #[tokio::test]
    async fn optional_controller_failure_only_blocks_scheduled_launches() {
        let session = Uuid::new_v4();
        assert!(
            admit_launch(Err(invalid("broken ledger")), session, false)
                .await
                .is_ok()
        );
        assert!(
            admit_launch(Err(invalid("broken ledger")), session, true)
                .await
                .is_err()
        );
        assert!(admit_launch(Ok(None), session, false).await.is_ok());
        assert!(admit_launch(Ok(None), session, true).await.is_err());
    }

    #[tokio::test]
    async fn ordinary_launch_survives_storage_failure_and_fences_only_background() {
        let mut f = Fixture::new();
        let request = f.issue();
        f.launch(&request);
        let controller = Mutex::new(f.c.take().unwrap());
        // Force ledger replacement to fail without making the lease unreadable.
        fs::remove_file(f.root.join("state.json")).unwrap();
        fs::create_dir(f.root.join("state.json")).unwrap();
        let ordinary = Uuid::new_v4();
        assert!(
            admit_launch(Ok(Some(&controller)), ordinary, false)
                .await
                .is_ok()
        );
        assert!(
            admit_launch(Ok(Some(&controller)), f.session, false)
                .await
                .is_err()
        );
        let mut c = controller.lock().await;
        assert!(!c.state.goals.contains_key(&ordinary));
        assert!(c.state.goals[&f.session].grant.as_ref().unwrap().stopping);
        assert!(c.state.foreground_until_ms > wall_ms());
        assert!(
            capacity_guard::read_lease(Path::new(&request.lease_file))
                .unwrap()
                .revoked
        );
        assert!(
            c.renew(
                f.session,
                Uuid::parse_str(&request.id).unwrap(),
                "old-week:day",
                0,
                31_000,
                2000
            )
            .is_err()
        );
    }

    #[tokio::test]
    async fn selected_idle_goal_allows_manual_work_without_losing_selection() {
        let mut f = Fixture::new();
        let controller = Mutex::new(f.c.take().unwrap());
        assert!(
            admit_launch(Ok(Some(&controller)), f.session, false)
                .await
                .is_ok()
        );
        assert!(controller.lock().await.state.goals[&f.session].eligible);
        assert!(
            admit_launch(Ok(Some(&controller)), f.session, false)
                .await
                .is_ok()
        );
        let ordinary = Uuid::new_v4();
        assert!(
            admit_launch(Ok(Some(&controller)), ordinary, false)
                .await
                .is_ok()
        );
        let c = controller.lock().await;
        assert!(c.state.goals[&f.session].eligible);
        assert!(!c.state.goals.contains_key(&ordinary));
        assert!(c.state.goals.values().all(|goal| goal.grant.is_none()));
    }

    #[test]
    fn revoke_during_launch_closes_authority_before_lease_creation() {
        let mut f = Fixture::new();
        let request = f.issue();
        let c = f.c.as_mut().unwrap();
        c.revoke_all("Interactive", Some(600_000)).unwrap();
        assert!(
            c.bind(&request, "native-thread", Uuid::new_v4(), 1001)
                .is_err()
        );
        assert!(!Path::new(&request.lease_file).exists());
        assert!(
            c.issue(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1001
            )
            .is_err()
        );
    }
    #[test]
    fn renewals_are_shared_bounded_and_cannot_reopen_expiry() {
        let mut f = Fixture::new();
        let request = f.issue();
        f.launch(&request);
        let c = f.c.as_mut().unwrap();
        let id = Uuid::parse_str(&request.id).unwrap();
        let other = Uuid::new_v4();
        let mut goal = c.state.goals[&f.session].clone();
        goal.session_id = other;
        goal.grant = None;
        c.enroll(goal).unwrap();
        assert!(
            c.issue(
                other,
                Uuid::new_v4(),
                "old-week:day".into(),
                40_000,
                90_000,
                10_000
            )
            .is_err()
        );
        assert!(
            c.renew(f.session, id, "new-week", 0, 40_000, 10_000)
                .is_err()
        );
        assert!(
            c.renew(f.session, id, "old-week:day", 0, 91_000, 20_000)
                .is_err()
        );
        c.renew(f.session, id, "old-week:day", 0, 40_000, 10_000)
            .unwrap();
        let lease = capacity_guard::read_lease(Path::new(&request.lease_file)).unwrap();
        assert_eq!(lease.sequence, 1);
        assert_eq!(lease.stop_at_ms, 90_000);
        assert!(
            c.renew(f.session, id, "old-week:day", 0, 50_000, 20_000)
                .is_err()
        );
        assert!(
            c.renew(f.session, id, "old-week:day", 1, 60_000, 40_000)
                .is_err()
        );
    }
    #[test]
    fn restart_revokes_running_grants_and_requires_reconciled_fresh_authority() {
        let mut f = Fixture::new();
        let request = f.issue();
        f.launch(&request);
        let revision = f.c.as_ref().unwrap().state.revision;
        f.c.take();
        let mut c = Controller::open(f.root.clone(), f.guard.clone(), "new-epoch".into()).unwrap();
        let grant = c.state.goals[&f.session].grant.clone().unwrap();
        assert!(grant.stopping);
        assert!(
            capacity_guard::read_lease(Path::new(&request.lease_file))
                .unwrap()
                .revoked
        );
        assert!(c.check_revision("test-epoch", revision).is_err());
        assert!(
            c.renew(f.session, grant.id, "old-week:day", 0, 40_000, 10_000)
                .is_err()
        );
        assert!(
            c.issue(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                40_000,
                90_000,
                10_000
            )
            .is_err()
        );
        c.stopped(f.session, grant.id, "Verified stopped".into())
            .unwrap();
        assert!(
            c.bind(&request, "native-thread", Uuid::new_v4(), 10_000)
                .is_err()
        );
        assert!(
            c.issue(
                f.session,
                grant.id,
                "old-week:day".into(),
                40_000,
                90_000,
                10_000
            )
            .is_err()
        );
        let next = c
            .issue(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                40_000,
                90_000,
                10_000,
            )
            .unwrap();
        assert_eq!(next.issuer_epoch, issuer_epoch());
        assert_eq!(
            c.state.goals[&f.session].objective,
            "Preserve full development objective"
        );
        f.c = Some(c);
    }
    #[test]
    fn cancelled_unbound_grant_id_cannot_be_replayed() {
        let mut f = Fixture::new();
        let request = f.issue();
        let id = Uuid::parse_str(&request.id).unwrap();
        let c = f.c.as_mut().unwrap();
        c.revoke_all("Cancelled before launch", None).unwrap();
        c.stopped(f.session, id, "No execution was bound".into())
            .unwrap();
        assert!(!Path::new(&request.lease_file).exists());
        assert!(
            c.issue(f.session, id, "old-week:day".into(), 30_000, 90_000, 1001)
                .is_err()
        );
        assert!(
            c.bind(&request, "native-thread", Uuid::new_v4(), 1001)
                .is_err()
        );
    }
    #[test]
    fn failed_persistence_does_not_issue_authority() {
        let mut f = Fixture::new();
        let c = f.c.as_mut().unwrap();
        let revision = c.state.revision;
        fs::rename(f.root.join("state.json"), f.root.join("saved.json")).unwrap();
        fs::create_dir(f.root.join("state.json")).unwrap();
        assert!(
            c.issue(
                f.session,
                Uuid::new_v4(),
                "old-week:day".into(),
                30_000,
                90_000,
                1000
            )
            .is_err()
        );
        assert_eq!(c.state.revision, revision);
        assert!(c.state.goals[&f.session].grant.is_none());
    }
    #[test]
    fn second_controller_cannot_take_ownership_and_wrong_thread_cannot_bind() {
        let mut f = Fixture::new();
        assert!(Controller::open(f.root.clone(), f.guard.clone(), "other".into()).is_err());
        let request = f.issue();
        let c = f.c.as_mut().unwrap();
        assert!(
            c.bind(&request, "other-native-thread", Uuid::new_v4(), 1000)
                .is_err()
        );
        c.bind(&request, "native-thread", Uuid::new_v4(), 1000)
            .unwrap();
        assert!(
            c.bind(&request, "native-thread", Uuid::new_v4(), 1000)
                .is_err()
        );
    }
}

#[cfg(test)]
mod native_acceptance {
    use super::*;
    use crate::{
        env::{ExecutionEnv, RepoContext},
        executors::{
            ExecutorExitResult, StandardCodingAgentExecutor,
            codex::{
                Codex,
                goals::{Progress, progress_path},
            },
        },
    };
    #[tokio::test]
    #[ignore = "requires isolated seeded CODEX_HOME, capacity controller directory and systemd guard"]
    async fn managed_capacity_runtime() {
        let home = std::env::var("CODEX_HOME").unwrap();
        assert!(home.contains("vk-continuation"));
        let thread = fs::read_to_string(Path::new(&home).join("capacity-thread-id")).unwrap();
        let before: Progress =
            serde_json::from_slice(&fs::read(progress_path(&thread).unwrap()).unwrap()).unwrap();
        assert!(!before.completed.is_empty());
        let session = Uuid::new_v4();
        let controller = configured().unwrap().unwrap();
        controller
            .lock()
            .await
            .enroll(ManagedGoal {
                goal_id: String::new(),
                initialization_state: InitializationState::Checkpointed,
                binding: None,
                initialization_receipt: None,
                session_id: session,
                thread_id: thread.clone(),
                objective: before.objective.clone(),
                created_at: before.created_at,
                eligible: true,
                reason: String::new(),
                grant: None,
            })
            .unwrap();
        let codex:Codex=serde_json::from_value(serde_json::json!({"model":"fixture","model_provider":"fixture","sandbox":"danger-full-access","ask_for_approval":"never","base_command_override":format!("python3 {}/../../scripts/testing/codex_goal_provider.py",env!("CARGO_MANIFEST_DIR"))})).unwrap();
        for _ in 0..2 {
            let marker = Path::new(&home).join("capacity-request-active");
            let _ = fs::remove_file(&marker);
            let execution = Uuid::new_v4();
            let now = wall_ms();
            let request = controller
                .lock()
                .await
                .issue(
                    session,
                    Uuid::new_v4(),
                    "old-week:day".into(),
                    now + 6000,
                    now + 8000,
                    now,
                )
                .unwrap();
            let prepared = {
                let mut c = controller.lock().await;
                c.bind(&request, &thread, execution, wall_ms()).unwrap();
                request.prepare(&execution.to_string()).unwrap()
            };
            // Scheduled capacity must not override a checkpoint requesting
            // human input or a native goal's explicit token-budget boundary.
            let path = progress_path(&thread).unwrap();
            let saved = fs::read(&path).unwrap();
            let mut waiting: Progress = serde_json::from_slice(&saved).unwrap();
            waiting.pause_reason = Some("Operator decision required".into());
            fs::write(&path, serde_json::to_vec(&waiting).unwrap()).unwrap();
            let mut snapshot = serde_json::json!({"goal": {
                "threadId": thread, "objective": before.objective,
                "createdAt": before.created_at, "status": "paused"
            }});
            assert!(validate_native(&prepared.lease, &snapshot).await.is_err());
            fs::write(&path, saved).unwrap();
            snapshot["goal"]["status"] = "budgetLimited".into();
            assert!(validate_native(&prepared.lease, &snapshot).await.is_err());
            snapshot["goal"]["status"] = "usageLimited".into();
            validate_native(&prepared.lease, &snapshot).await.unwrap();
            let mut env = ExecutionEnv::new(RepoContext::default(), false, String::new());
            env.insert("VK_EXECUTION_PROCESS_ID", execution.to_string());
            env.insert("CODEX_HOME", home.clone());
            env.insert("VK_GOAL_TEST_SCENARIO", "capacity-containment");
            env.insert(
                "VK_CAPACITY_BUILD_ROOTS",
                std::env::var("VK_CAPACITY_BUILD_ROOTS").unwrap(),
            );
            env.capacity = Some(prepared);
            let mut spawned = codex
                .spawn_follow_up(
                    &Path::new(&home).join("work"),
                    "/goal resume",
                    &thread,
                    None,
                    &env,
                )
                .await
                .unwrap();
            assert_eq!(
                spawned.transient_unit_name.as_deref(),
                Some(super::super::unit_name(execution).as_str())
            );
            let stdout = spawned.child.inner().stdout.take().unwrap();
            let protocol_path = Path::new(&home).join(format!("managed-{execution}.jsonl"));
            let drain = tokio::spawn(async move {
                let mut stdout = stdout;
                let mut file = tokio::fs::File::create(protocol_path).await.unwrap();
                tokio::io::copy(&mut stdout, &mut file).await.unwrap();
            });
            let result = tokio::time::timeout(
                std::time::Duration::from_secs(7),
                spawned.exit_signal.take().unwrap(),
            )
            .await
            .unwrap()
            .unwrap();
            assert!(matches!(result, ExecutorExitResult::Success));
            assert!(
                marker.exists(),
                "An active model request must have been interrupted"
            );
            tokio::time::timeout(std::time::Duration::from_secs(4), spawned.child.wait())
                .await
                .unwrap()
                .unwrap();
            assert!(wall_ms() < request.stop_at_ms);
            let proof: serde_json::Value = serde_json::from_slice(
                &fs::read(Path::new(&home).join("work/native-containment.json")).unwrap(),
            )
            .unwrap();
            assert_eq!(proof["workspace_write"], true);
            assert_eq!(
                proof["build_exit"], 0,
                "Build must use its approved cache: {proof}"
            );
            assert_eq!(proof["built_program_exit"], 0);
            assert_eq!(proof["built_program_output"], "scheduled build works");
            assert_eq!(proof["child_started"], true);
            assert_eq!(proof["tcp"], 1, "TCP socket creation must be denied");
            assert_eq!(
                proof["systemd_bus"], 1,
                "Service-control sockets must be denied"
            );
            assert!(
                proof["outside_write"].is_number(),
                "Outside workspace must not be writable"
            );
            let tools: serde_json::Value = serde_json::from_slice(
                &fs::read(Path::new(&home).join("capacity-tools.json")).unwrap(),
            )
            .unwrap();
            for tool in tools.as_array().unwrap() {
                if tool["type"] == "namespace" {
                    assert_eq!(
                        tool["name"], "multi_agent_v1",
                        "No external tool namespaces"
                    );
                }
                assert!(!tool["name"].as_str().unwrap_or("").starts_with("mcp_"));
            }
            let delegation: serde_json::Value = serde_json::from_slice(
                &fs::read(Path::new(&home).join("capacity-delegation-reply.json")).unwrap(),
            )
            .unwrap();
            let reply = delegation["input"]
                .as_array()
                .unwrap()
                .iter()
                .find(|item| {
                    item["type"] == "function_call_output" && item["call_id"] == "delegation"
                })
                .unwrap()["output"]
                .as_str()
                .unwrap();
            assert!(
                reply == "unsupported call: spawn_agent"
                    || reply.contains("depth")
                    || reply.contains("limit"),
                "Delegation must be rejected before starting a child: {reply}"
            );
            let heartbeat = Path::new(&home).join("work/contained-child-heartbeat");
            let stopped = fs::read(&heartbeat).unwrap();
            tokio::time::sleep(std::time::Duration::from_millis(350)).await;
            assert_eq!(
                fs::read(&heartbeat).unwrap(),
                stopped,
                "Detached child must stop with the guarded service"
            );
            if let Some(cancel) = spawned.cancel {
                cancel.cancel();
            }
            drain.await.unwrap();
            let after: Progress =
                serde_json::from_slice(&fs::read(progress_path(&thread).unwrap()).unwrap())
                    .unwrap();
            assert_eq!(after.objective, before.objective);
            assert_eq!(after.created_at, before.created_at);
            for (id, evidence) in &before.completed {
                assert_eq!(after.completed.get(id), Some(evidence));
            }
            controller
                .lock()
                .await
                .stopped(
                    session,
                    Uuid::parse_str(&request.id).unwrap(),
                    "Verified systemd process exit".into(),
                )
                .unwrap();
        }
    }
}
