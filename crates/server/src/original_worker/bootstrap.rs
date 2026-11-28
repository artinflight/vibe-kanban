//! Release-owner bootstrap proof, never an agent-supplied authority assertion.
//! The existing backend/host is trusted; this is not independent external custody.
use std::{
    collections::HashSet,
    fs, io,
    path::{Path, PathBuf},
    sync::Arc,
};

use serde::{Deserialize, Serialize};
use services::services::original_worker::{Contract, invalid};
use sqlx::Connection;
use uuid::Uuid;

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct ProcessPin {
    pub pid: u32,
    pub start_ticks: u64,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct WriterPin {
    pub session: Uuid,
    pub thread: String,
    pub process: Option<ProcessPin>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Receipt {
    pub contract_sha256: String,
    pub dataset_id: String,
    pub database: PathBuf,
    pub database_object: String,
    pub native_home: PathBuf,
    pub boot_id: String,
    pub old_ingress: Vec<ProcessPin>,
    pub native_writers: Vec<WriterPin>,
}

pub(super) struct Procfs {
    root: PathBuf,
    own_pid: u32,
    uid: u32,
    units: Arc<dyn UnitLookup>,
}
#[executors::original_worker::async_trait]
pub(super) trait UnitLookup: Send + Sync {
    async fn properties(&self, unit: &str) -> io::Result<String>;
}
struct SystemdUnits;
#[executors::original_worker::async_trait]
impl UnitLookup for SystemdUnits {
    async fn properties(&self, unit: &str) -> io::Result<String> {
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(2),
            tokio::process::Command::new("systemctl")
                .args([
                    "--user",
                    "show",
                    unit,
                    "--property=Environment",
                    "--property=ControlGroup",
                    "--property=Description",
                    "--property=Transient",
                    "--property=ActiveState",
                    "--property=InvocationID",
                ])
                .kill_on_drop(true)
                .output(),
        )
        .await
        .map_err(|_| invalid("Unit ownership receipt timed out"))?
        .map_err(|_| invalid("Unit ownership unavailable"))?;
        if !output.status.success() || output.stdout.len() > 64 * 1024 {
            return Err(invalid("Unit ownership unknown"));
        }
        // This includes service environment data. Parse in-process only; neither
        // stdout, stderr nor credentials become diagnostics or persisted state.
        String::from_utf8(output.stdout).map_err(|_| invalid("Unit ownership invalid"))
    }
}
impl Procfs {
    #[cfg(target_os = "linux")]
    pub fn live() -> io::Result<Self> {
        use std::os::unix::fs::MetadataExt;
        Ok(Self {
            root: "/proc".into(),
            own_pid: std::process::id(),
            uid: fs::metadata("/proc/self")?.uid(),
            units: Arc::new(SystemdUnits),
        })
    }
    #[cfg(not(target_os = "linux"))]
    pub fn live() -> io::Result<Self> {
        Err(invalid("Bootstrap requires Linux process provenance"))
    }

    fn boot(&self) -> io::Result<String> {
        let boot = fs::read_to_string(self.root.join("sys/kernel/random/boot_id"))?;
        Uuid::parse_str(boot.trim()).map_err(|_| invalid("Kernel boot identity unknown"))?;
        Ok(boot.trim().to_owned())
    }
    fn absent(&self, pin: &ProcessPin) -> io::Result<()> {
        if pin.pid == 0 || pin.start_ticks == 0 {
            return Err(invalid("Old producer identity missing"));
        }
        match fs::read_to_string(self.root.join(pin.pid.to_string()).join("stat")) {
            Ok(stat) if start_ticks(&stat)? == pin.start_ticks => {
                Err(invalid("Old input producer is still live"))
            }
            Ok(_) => Ok(()), // Exact start identity proves PID reuse, not the old process.
            Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(()),
            Err(_) => Err(invalid("Old producer liveness unknown")),
        }
    }
    /// Scan current owned processes as well as pinned old identities. A receipt
    /// cannot omit a surviving child/writer and turn omission into quiescence.
    pub async fn verify(
        &self,
        receipt: &Receipt,
        contract: &Contract,
        pool: &sqlx::SqlitePool,
    ) -> io::Result<()> {
        if self.boot()? != receipt.boot_id
            || receipt.old_ingress.is_empty()
            || receipt.old_ingress.len() > 16
            || receipt.native_writers.len() != 2
        {
            return Err(invalid("Bootstrap quiescence inventory missing or stale"));
        }
        let mut pins = HashSet::new();
        for pin in &receipt.old_ingress {
            if !pins.insert((pin.pid, pin.start_ticks)) {
                return Err(invalid("Duplicate producer inventory"));
            }
            self.absent(pin)?;
        }
        let mut writers = HashSet::new();
        for writer in &receipt.native_writers {
            let identity = [&contract.manager, &contract.worker]
                .into_iter()
                .find(|i| i.session == writer.session && i.thread == writer.thread)
                .ok_or_else(|| invalid("Native writer scope differs from fixed contract"))?;
            if !writers.insert(identity.session) {
                return Err(invalid("Missing original native writer inventory"));
            }
            if let Some(pin) = &writer.process {
                self.absent(pin)?;
            }
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            let entries =
                fs::read_dir(&self.root).map_err(|_| invalid("Process inventory unavailable"))?;
            for entry in entries {
                let entry = entry.map_err(|_| invalid("Process inventory incomplete"))?;
                let Ok(pid) = entry.file_name().to_string_lossy().parse::<u32>() else {
                    continue;
                };
                if pid == self.own_pid {
                    continue;
                }
                let path = entry.path();
                let metadata = match fs::metadata(&path) {
                    Ok(m) => m,
                    Err(e) if e.kind() == io::ErrorKind::NotFound => continue,
                    Err(_) => return Err(invalid("Process ownership unknown")),
                };
                if metadata.uid() != self.uid {
                    continue;
                }
                // Read only selected identity fields. Never retain/log environment,
                // argv, credential values, transcripts or file-descriptor payloads.
                let observation = async {
                    let stat = fs::read_to_string(path.join("stat"))?;
                    let state = stat
                        .rsplit_once(')')
                        .ok_or_else(|| invalid("Process identity unknown"))?
                        .1
                        .split_whitespace()
                        .next();
                    if state == Some("Z") {
                        return Ok(());
                    } // No executable producer remains.
                    let before = start_ticks(&stat)?;
                    let env = fs::read(path.join("environ"))?;
                    let value = |key: &str| -> Option<&[u8]> {
                        env.split(|b| *b == 0).find_map(|v| {
                            v.strip_prefix(key.as_bytes())
                                .and_then(|v| v.strip_prefix(b"="))
                        })
                    };
                    let uuid = |key: &str| {
                        value(key)
                            .and_then(|v| std::str::from_utf8(v).ok())
                            .and_then(|v| Uuid::parse_str(v).ok())
                    };
                    let target_session = uuid("VK_SESSION_ID").is_some_and(|id| {
                        id == contract.manager.session || id == contract.worker.session
                    });
                    let target_workspace = uuid("VK_WORKSPACE_ID").is_some_and(|id| {
                        id == contract.manager.workspace || id == contract.worker.workspace
                    });
                    let cwd = fs::read_link(path.join("cwd"))?;
                    let root_owned = [&contract.manager.root, &contract.worker.root]
                        .iter()
                        .any(|root| cwd.starts_with(root));
                    let home = value("CODEX_HOME")
                        .and_then(|v| std::str::from_utf8(v).ok())
                        .map(Path::new);
                    let native_home = home.is_some_and(|p| {
                        p.canonicalize().ok().as_ref() == Some(&receipt.native_home)
                    });
                    let native_unbound = native_home && uuid("VK_SESSION_ID").is_none();
                    let exe = fs::read_link(path.join("exe"))?;
                    let name = exe.file_name().and_then(|s| s.to_str()).unwrap_or("");
                    let name = name.strip_suffix(" (deleted)").unwrap_or(name);
                    let backend = matches!(
                        name,
                        "server" | "vibe-kanban" | "vibe-kanban-serve" | "vibe-kanban-serve-prod"
                    ) || name.starts_with("vibe-kanban-serve");
                    // An unscoped native writer may use a default home rather
                    // than CODEX_HOME. Neither a missing marker nor missing
                    // environment binding proves that it cannot serve a target.
                    let unscoped_codex = (name == "codex" || name.starts_with("codex-"))
                        && uuid("VK_SESSION_ID").is_none();
                    let ingress_marker = value("VK_RUNTIME_IDENTITY_FILE").is_some();
                    if target_session
                        || target_workspace
                        || root_owned
                        || native_unbound
                        || backend
                        || unscoped_codex
                        || (ingress_marker && uuid("VK_SESSION_ID").is_none())
                    {
                        return Err(invalid("Active or potentially competing input producer"));
                    }
                    // Process environment is only a claim. An unrelated native
                    // writer needs the kernel's service membership, backend-set
                    // unit bindings, persisted execution and its actual rollout.
                    if native_home || name == "codex" || name.starts_with("codex-") {
                        self.unrelated_writer(
                            &path,
                            &cwd,
                            receipt,
                            contract,
                            pool,
                            uuid("VK_SESSION_ID"),
                            uuid("VK_WORKSPACE_ID"),
                            uuid("VK_EXECUTION_PROCESS_ID"),
                        )
                        .await?;
                    }
                    for fd in fs::read_dir(path.join("fd"))? {
                        let fd = fd?;
                        match fs::read_link(fd.path()) {
                            Ok(target)
                                if target == contract.manager.input_seal.rollout
                                    || target == contract.worker.input_seal.rollout =>
                            {
                                return Err(invalid(
                                    "Original native input file still owned by a process",
                                ));
                            }
                            Ok(_) => {}
                            Err(e) if e.kind() == io::ErrorKind::NotFound => {}
                            Err(_) => return Err(invalid("Native writer ownership unknown")),
                        }
                    }
                    if start_ticks(&fs::read_to_string(path.join("stat"))?)? != before {
                        return Err(invalid("Process identity changed during inventory"));
                    }
                    Ok::<_, io::Error>(())
                }
                .await;
                if let Err(error) = observation {
                    // A process that demonstrably disappeared cannot deliver input.
                    // Every other incomplete observation is unknown, never approval.
                    if !matches!(fs::metadata(&path),Err(ref e) if e.kind()==io::ErrorKind::NotFound)
                    {
                        return Err(invalid(&format!(
                            "Bootstrap process proof unavailable: {}",
                            error.kind()
                        )));
                    }
                }
            }
        }
        #[cfg(not(unix))]
        {
            return Err(invalid("Native writer proof unsupported"));
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    async fn unrelated_writer(
        &self,
        process: &Path,
        cwd: &Path,
        receipt: &Receipt,
        contract: &Contract,
        pool: &sqlx::SqlitePool,
        session: Option<Uuid>,
        workspace: Option<Uuid>,
        execution: Option<Uuid>,
    ) -> io::Result<()> {
        use std::collections::HashMap;

        use executors::actions::{ExecutorAction, ExecutorActionType};
        let cgroup = fs::read_to_string(process.join("cgroup"))?;
        let groups: Vec<_> = cgroup
            .lines()
            .filter_map(|l| l.strip_prefix("0::"))
            .collect();
        let [group] = groups.as_slice() else {
            return Err(invalid("Native service membership unknown"));
        };
        let unit = Path::new(group)
            .file_name()
            .and_then(|s| s.to_str())
            .ok_or_else(|| invalid("Native service identity unknown"))?;
        let suffix = unit
            .strip_prefix("vk-exec-codex-")
            .or_else(|| unit.strip_prefix("vk-capacity-"))
            .and_then(|s| s.strip_suffix(".service"));
        if !group.starts_with('/')
            || group.contains("..")
            || suffix.and_then(|s| Uuid::parse_str(s).ok()).is_none()
        {
            return Err(invalid(
                "Native process lacks supported backend service ownership",
            ));
        }
        let raw = self.units.properties(unit).await?;
        let values: HashMap<_, _> = raw.lines().filter_map(|l| l.split_once('=')).collect();
        if values.get("ControlGroup") != Some(group)
            || values.get("Transient") != Some(&"yes")
            || values.get("ActiveState") != Some(&"active")
            || !matches!(
                values.get("Description"),
                Some(&"VK Codex execution" | &"VK scheduled capacity execution")
            )
            || values
                .get("InvocationID")
                .and_then(|s| Uuid::parse_str(s).ok())
                .is_none_or(|id| id.is_nil())
        {
            return Err(invalid("Native service provenance changed or unknown"));
        }
        let env = shlex::split(
            values
                .get("Environment")
                .ok_or_else(|| invalid("Backend launch binding missing"))?,
        )
        .ok_or_else(|| invalid("Backend launch binding invalid"))?;
        let binding = |key: &str| -> io::Result<&str> {
            let mut found = env
                .iter()
                .filter_map(|s| s.split_once('=').filter(|(k, _)| *k == key).map(|(_, v)| v));
            let value = found
                .next()
                .ok_or_else(|| invalid("Backend launch binding missing"))?;
            if found.next().is_some() {
                return Err(invalid("Ambiguous backend launch binding"));
            }
            Ok(value)
        };
        let bound_session = Uuid::parse_str(binding("VK_SESSION_ID")?)
            .map_err(|_| invalid("Invalid service session"))?;
        let bound_workspace = Uuid::parse_str(binding("VK_WORKSPACE_ID")?)
            .map_err(|_| invalid("Invalid service workspace"))?;
        let bound_execution = Uuid::parse_str(binding("VK_EXECUTION_PROCESS_ID")?)
            .map_err(|_| invalid("Invalid service execution"))?;
        if session != Some(bound_session)
            || workspace != Some(bound_workspace)
            || execution != Some(bound_execution)
            || [contract.manager.session, contract.worker.session].contains(&bound_session)
            || [contract.manager.workspace, contract.worker.workspace].contains(&bound_workspace)
            || Path::new(binding("CODEX_HOME")?).canonicalize()? != receipt.native_home
        {
            return Err(invalid(
                "Process claims differ from backend launch ownership",
            ));
        }
        if unit.starts_with("vk-capacity-")
            && unit != executors::capacity::unit_name(bound_execution)
        {
            return Err(invalid("Capacity execution membership changed"));
        }
        let row:Option<(String,String)>=sqlx::query_as("SELECT e.executor_action,w.container_ref FROM execution_processes e JOIN sessions s ON s.id=e.session_id JOIN workspaces w ON w.id=s.workspace_id WHERE e.id=? AND e.session_id=? AND s.workspace_id=? AND e.status='running' AND e.dropped=FALSE AND e.run_reason='codingagent'")
            .bind(bound_execution).bind(bound_session).bind(bound_workspace).fetch_optional(pool).await
            .map_err(|_|invalid("Persisted native ownership unavailable"))?;
        let (action, root) =
            row.ok_or_else(|| invalid("Native execution is not owned by the selected backend"))?;
        let root = Path::new(&root).canonicalize()?;
        let cwd = cwd.canonicalize()?;
        if !cwd.starts_with(&root) || root == contract.manager.root || root == contract.worker.root
        {
            return Err(invalid("Unrelated workspace ownership unproved"));
        }
        let threads:Vec<String>=sqlx::query_scalar("SELECT DISTINCT agent_session_id FROM coding_agent_turns WHERE execution_process_id=? AND agent_session_id IS NOT NULL")
            .bind(bound_execution).fetch_all(pool).await.map_err(|_|invalid("Native thread ownership unavailable"))?;
        let [thread] = threads.as_slice() else {
            return Err(invalid("Native thread ownership ambiguous"));
        };
        if thread == &contract.manager.thread || thread == &contract.worker.thread {
            return Err(invalid("Original native thread remains live"));
        }
        let action: ExecutorAction =
            serde_json::from_str(&action).map_err(|_| invalid("Native launch action unknown"))?;
        if executors::routing::config(&action)
            .is_none_or(|c| c.executor != executors::executors::BaseCodingAgent::Codex)
            || !matches!(
                action.typ(),
                ExecutorActionType::CodingAgentInitialRequest(_)
                    | ExecutorActionType::CodingAgentFollowUpRequest(_)
            )
            || matches!(action.typ(),ExecutorActionType::CodingAgentFollowUpRequest(r) if r.session_id!=*thread)
        {
            return Err(invalid("Persisted native launch/thread mismatch"));
        }
        let mut native = sqlx::SqliteConnection::connect_with(
            &sqlx::sqlite::SqliteConnectOptions::new()
                .filename(receipt.native_home.join("state_5.sqlite"))
                .read_only(true)
                .create_if_missing(false),
        )
        .await
        .map_err(|_| invalid("Native index unavailable"))?;
        let rollout: String = sqlx::query_scalar("SELECT rollout_path FROM threads WHERE id=?")
            .bind(thread)
            .fetch_one(&mut native)
            .await
            .map_err(|_| invalid("Unrelated native rollout unknown"))?;
        let rollout = Path::new(&rollout).canonicalize()?;
        if !rollout.starts_with(&receipt.native_home)
            || rollout == contract.manager.input_seal.rollout
            || rollout == contract.worker.input_seal.rollout
        {
            return Err(invalid("Unrelated native rollout binding changed"));
        }
        let mut held = false;
        for fd in fs::read_dir(process.join("fd"))? {
            let path = fs::read_link(fd?.path())?;
            if path == rollout {
                held = true;
            } else if path.starts_with(&receipt.native_home)
                && path.extension().is_some_and(|s| s == "jsonl")
            {
                return Err(invalid("Additional native writer ownership unknown"));
            }
        }
        if !held {
            return Err(invalid("Process/native-thread provenance unproved"));
        }
        if fs::read_to_string(process.join("cgroup"))? != cgroup
            || self.units.properties(unit).await? != raw
        {
            return Err(invalid(
                "Native launch ownership changed during verification",
            ));
        }
        Ok(())
    }
}
fn start_ticks(stat: &str) -> io::Result<u64> {
    stat.rsplit_once(')')
        .and_then(|(_, s)| s.split_whitespace().nth(19))
        .and_then(|s| s.parse().ok())
        .filter(|n| *n > 0)
        .ok_or_else(|| invalid("Process start identity unknown"))
}

#[cfg(unix)]
pub(super) fn object(path: &Path) -> io::Result<String> {
    use std::os::unix::fs::MetadataExt;
    let m = fs::metadata(path)?;
    Ok(format!("{}:{}", m.dev(), m.ino()))
}
#[cfg(not(unix))]
pub(super) fn object(_: &Path) -> io::Result<String> {
    Err(invalid("Database object provenance unsupported"))
}

#[cfg(all(test, unix))]
pub(super) mod tests;
