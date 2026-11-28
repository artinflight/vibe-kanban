//! Synthetic procfs uses the production parser; no target process or grant exists.
use services::services::original_worker::digest;

use super::*;
use crate::original_worker::StartupFiles;

#[derive(Default)]
struct SyntheticUnits(std::sync::Mutex<std::collections::HashMap<String, String>>);
#[executors::original_worker::async_trait]
impl UnitLookup for SyntheticUnits {
    async fn properties(&self, unit: &str) -> io::Result<String> {
        self.0
            .lock()
            .unwrap()
            .get(unit)
            .cloned()
            .ok_or_else(|| invalid("Synthetic unit not registered"))
    }
}

pub(in crate::original_worker) struct Fixture {
    pub(in crate::original_worker) processes: Procfs,
    pub(in crate::original_worker) receipt: Receipt,
    pub(in crate::original_worker) files: StartupFiles,
    units: Arc<SyntheticUnits>,
}
impl Fixture {
    pub(in crate::original_worker) fn new(
        directory: &Path,
        contract: &Contract,
        database: &Path,
    ) -> Self {
        use std::os::unix::fs::MetadataExt;
        let root = directory.join("synthetic-proc");
        fs::create_dir_all(root.join("sys/kernel/random")).unwrap();
        let boot = "11111111-2222-4333-8444-555555555555";
        fs::write(root.join("sys/kernel/random/boot_id"), boot).unwrap();
        let bytes = serde_json::to_vec(contract).unwrap();
        let files = StartupFiles {
            contract: directory.join("fixed-contract.json"),
            contract_sha256: digest(&bytes),
            bootstrap: directory.join("quiescence.json"),
            bootstrap_sha256: String::new(),
        };
        fs::write(&files.contract, bytes).unwrap();
        let home = executors::executors::codex::codex_home()
            .unwrap()
            .canonicalize()
            .unwrap();
        let receipt = Receipt {
            contract_sha256: files.contract_sha256.clone(),
            dataset_id: "a".repeat(32),
            database: database.canonicalize().unwrap(),
            database_object: object(database).unwrap(),
            native_home: home,
            boot_id: boot.into(),
            old_ingress: vec![ProcessPin {
                pid: 42,
                start_ticks: 100,
            }],
            native_writers: vec![
                WriterPin {
                    session: contract.manager.session,
                    thread: contract.manager.thread.clone(),
                    process: Some(ProcessPin {
                        pid: 43,
                        start_ticks: 200,
                    }),
                },
                WriterPin {
                    session: contract.worker.session,
                    thread: contract.worker.thread.clone(),
                    process: None,
                },
            ],
        };
        let units = Arc::new(SyntheticUnits::default());
        let processes = Procfs {
            uid: fs::metadata(&root).unwrap().uid(),
            root,
            own_pid: 999,
            units: units.clone(),
        };
        let mut f = Self {
            processes,
            receipt,
            files,
            units,
        };
        f.save();
        f
    }
    pub(in crate::original_worker) fn save(&mut self) {
        let bytes = serde_json::to_vec(&self.receipt).unwrap();
        fs::write(&self.files.bootstrap, &bytes).unwrap();
        self.files.bootstrap_sha256 = digest(&bytes);
    }
    pub(in crate::original_worker) fn process(
        &self,
        pid: u32,
        ticks: u64,
        env: &str,
        cwd: &Path,
        exe: &str,
    ) {
        use std::os::unix::fs::symlink;
        let path = self.processes.root.join(pid.to_string());
        fs::create_dir_all(path.join("fd")).unwrap();
        fs::write(
            path.join("stat"),
            format!(
                "{pid} (synthetic) S {} {ticks}",
                std::iter::repeat_n("0", 18).collect::<Vec<_>>().join(" ")
            ),
        )
        .unwrap();
        fs::write(path.join("environ"), env).unwrap();
        symlink(cwd, path.join("cwd")).unwrap();
        symlink(Path::new("/synthetic").join(exe), path.join("exe")).unwrap();
    }
    pub(in crate::original_worker) fn forget_process(&self, pid: u32) {
        // Frozen synthetic test path only, never /proc or an actual execution.
        fs::remove_dir_all(self.processes.root.join(pid.to_string())).unwrap();
    }
    pub(in crate::original_worker) fn unknown_process(&self, pid: u32) {
        fs::remove_file(self.processes.root.join(pid.to_string()).join("environ")).unwrap();
    }
    pub(in crate::original_worker) fn held_rollout(&self, pid: u32, rollout: &Path) {
        std::os::unix::fs::symlink(
            rollout,
            self.processes.root.join(pid.to_string()).join("fd/3"),
        )
        .unwrap();
    }
    pub(in crate::original_worker) fn unit(&self, pid: u32, unit: &str, binding: &str) {
        let group = format!("/user.slice/synthetic/{unit}");
        fs::write(
            self.processes.root.join(pid.to_string()).join("cgroup"),
            format!("0::{group}\n"),
        )
        .unwrap();
        self.units.0.lock().unwrap().insert(unit.into(),format!("ControlGroup={group}\nTransient=yes\nActiveState=active\nDescription=VK Codex execution\nInvocationID=11111111222243338444555555555555\nEnvironment={binding}\n"));
    }
}

#[tokio::test]
async fn actual_kernel_process_identity_cannot_be_declared_quiescent_while_live() {
    use std::process::Stdio;
    let processes = Procfs::live().unwrap();
    let mut child = tokio::process::Command::new("python3")
        .args(["-c", "import time; time.sleep(60)"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .unwrap();
    let pid = child.id().unwrap();
    let stat = fs::read_to_string(Path::new("/proc").join(pid.to_string()).join("stat")).unwrap();
    let pin = ProcessPin {
        pid,
        start_ticks: start_ticks(&stat).unwrap(),
    };
    assert!(processes.absent(&pin).is_err());
    // Different start ticks demonstrate reuse; absence never relies on PID alone.
    assert!(
        processes
            .absent(&ProcessPin {
                pid,
                start_ticks: pin.start_ticks + 1
            })
            .is_ok()
    );
    child.kill().await.unwrap();
    child.wait().await.unwrap();
    processes.absent(&pin).unwrap();
    assert!(start_ticks("malformed").is_err());
}
