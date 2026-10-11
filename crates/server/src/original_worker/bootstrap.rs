//! Release-owner bootstrap proof, never an agent-supplied authority assertion.
//! The existing backend/host is trusted; this is not independent external custody.
use std::{
    collections::HashSet,
    fs, io,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};
use services::services::original_worker::{Contract, invalid};
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
}
impl Procfs {
    #[cfg(target_os = "linux")]
    pub fn live() -> io::Result<Self> {
        use std::os::unix::fs::MetadataExt;
        Ok(Self {
            root: "/proc".into(),
            own_pid: std::process::id(),
            uid: fs::metadata("/proc/self")?.uid(),
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
    pub fn verify(&self, receipt: &Receipt, contract: &Contract) -> io::Result<()> {
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
                let observation = (|| -> io::Result<()> {
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
                        || (ingress_marker && (backend || uuid("VK_SESSION_ID").is_none()))
                    {
                        return Err(invalid("Active or potentially competing input producer"));
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
                    Ok(())
                })();
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
