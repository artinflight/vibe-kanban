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

use super::{CapacityExecution, issuer_epoch, wall_ms};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ManagedGoal {
    pub session_id: Uuid,
    pub thread_id: String,
    pub objective: String,
    pub created_at: i64,
    pub eligible: bool,
    pub reason: String,
    pub grant: Option<Grant>,
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
    _lock: fs::File,
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
    pub fn open(root: PathBuf, guard: PathBuf, epoch: String) -> io::Result<Self> {
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
        if state.version != 1 || state.goals.len() > 100 {
            return Err(invalid("Unsupported capacity state"));
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
        }
        state.epoch = epoch;
        let mut this = Self {
            root,
            guard,
            _lock: lock,
            state,
        };
        this.commit(this.state.clone())?;
        this.revoke_files()?;
        Ok(this)
    }
    fn commit(&mut self, mut next: State) -> io::Result<()> {
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
        goal.reason = if goal.eligible {
            "Waiting for unused capacity"
        } else {
            "Not eligible"
        }
        .into();
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
        if self.state.foreground_until_ms > now
            || self.state.goals.values().any(|g| g.grant.is_some())
        {
            return Err(invalid(
                "Interactive priority or unreconciled background execution",
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
        goal.reason = "Starting scheduled goal".into();
        self.commit(next)?;
        Ok(CapacityExecution {
            issuer_epoch: self.state.epoch.clone(),
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
            || request.issuer_epoch != self.state.epoch
            || grant.expires_at_ms <= now
            || self.state.foreground_until_ms > now
            || grant.allocation_id != request.allocation_id
            || grant.expires_at_ms != request.expires_at_ms
            || grant.stop_at_ms != request.stop_at_ms
            || request.lease_file != self.lease_path(id).to_string_lossy()
            || request.guard_binary != self.guard.to_string_lossy()
        {
            return Err(invalid(
                "Launch permission was revoked, changed, expired or already bound",
            ));
        }
        let mut next = self.state.clone();
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
        let mut next = self.state.clone();
        if let Some(until) = foreground_until {
            next.foreground_until_ms = next.foreground_until_ms.max(until);
        }
        for goal in next.goals.values_mut() {
            if let Some(grant) = &mut goal.grant {
                grant.stopping = true;
                goal.reason = reason.into();
            }
        }
        self.commit(next)?;
        self.revoke_files()
    }
    fn revoke_files(&self) -> io::Result<()> {
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
        if !goal.grant.as_ref().is_some_and(|g| g.id == id) {
            return Err(invalid("Grant changed during stop reconciliation"));
        }
        goal.grant = None;
        goal.reason = reason;
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
        Controller::open(root.into(), guard.into(), issuer_epoch().into())
            .map(|c| Some(Mutex::new(c)))
            .map_err(|e| e.to_string())
    });
    match result {
        Ok(value) => Ok(value.as_ref()),
        Err(message) => Err(invalid(message)),
    }
}

pub async fn before_launch(session: Uuid, background: bool) -> io::Result<()> {
    let Some(controller) = configured()? else {
        return Ok(());
    };
    let mut c = controller.lock().await;
    if !background {
        c.revoke_all(
            "Interactive work takes priority",
            Some(wall_ms() + 10 * 60_000),
        )?;
        if c.state
            .goals
            .get(&session)
            .is_some_and(|g| g.eligible || g.grant.is_some())
        {
            return Err(invalid(
                "Take this goal out of unused-capacity mode before manual continuation",
            ));
        }
    }
    Ok(())
}

pub async fn validate_native(lease: &Lease, snapshot: &serde_json::Value) -> io::Result<()> {
    let controller = configured()?.ok_or_else(|| invalid("No scheduled goal controller"))?;
    let c = controller.lock().await;
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
    let progress: crate::executors::codex::goals::Progress = serde_json::from_slice(&fs::read(
        crate::executors::codex::goals::progress_path(&goal.thread_id)?,
    )?)?;
    if progress.pause_reason.is_some()
        || progress.all_complete()
        || !matches!(
            native.status.as_str(),
            "paused" | "active" | "usage_limited"
        )
    {
        return Err(invalid(
            "Goal requires user involvement before scheduled continuation",
        ));
    }
    if native.thread_id != goal.thread_id
        || native.objective != goal.objective
        || native.created_at != goal.created_at
        || native.status == "complete"
    {
        return Err(invalid(
            "Native goal changed; select its new objective explicitly",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
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
    impl Drop for Fixture {
        fn drop(&mut self) {
            self.c.take();
            let _ = fs::remove_dir_all(&self.root);
        }
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
        assert_eq!(next.issuer_epoch, "new-epoch");
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
            snapshot["goal"]["status"] = "budget_limited".into();
            assert!(validate_native(&prepared.lease, &snapshot).await.is_err());
            snapshot["goal"]["status"] = "paused".into();
            validate_native(&prepared.lease, &snapshot).await.unwrap();
            let mut env = ExecutionEnv::new(RepoContext::default(), false, String::new());
            env.insert("VK_EXECUTION_PROCESS_ID", execution.to_string());
            env.insert("CODEX_HOME", home.clone());
            env.insert("VK_GOAL_TEST_SCENARIO", "capacity-containment");
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
