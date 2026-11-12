//! File observations at the normal provider boundary. Never evidence of model reads.
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::{self, Read, Write},
    path::{Component, Path, PathBuf},
    sync::{Arc, Mutex},
};

use chrono::Utc;
use notify::{Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use uuid::Uuid;

const CORE: &[&str] = &["AGENTS.md", "STATE.md", "STREAM.md", "HANDOFF.md"];
const ROUTES: &[&str] = &[
    "docs/CONTEXT_MANAGEMENT.md",
    "docs/WINDOWS_MEDIA_HANDOFF.md",
    "docs/CURRENT_STATUS.md",
];
const MAX_BYTES: u64 = 1024 * 1024;
const MAX_FILES: usize = 64;
const MAX_ROOTS: usize = 32;
const MAX_TOTAL_BYTES: usize = 8 * 1024 * 1024;

fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn relative(path: &Path) -> bool {
    !path.as_os_str().is_empty() && path.components().all(|c| matches!(c, Component::Normal(_)))
}

// Refuse symlinks (including ancestors), special files and unbounded reads.
// Nothing outside the selected workspace is read through instruction paths.
fn read(root: &Path, name: &Path) -> io::Result<Option<Vec<u8>>> {
    if !relative(name) {
        return Err(io::Error::other("invalid relative path"));
    }
    let mut path = root.to_path_buf();
    for part in name.components() {
        path.push(part);
        match fs::symlink_metadata(&path) {
            Ok(meta) if meta.file_type().is_symlink() => {
                return Err(io::Error::other("symlink"));
            }
            Ok(_) => {}
            Err(e) if e.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(e) => return Err(e),
        }
    }
    let meta = fs::metadata(&path)?;
    if !meta.is_file() || meta.len() > MAX_BYTES {
        return Err(io::Error::other("unsupported file"));
    }
    let mut bytes = Vec::new();
    File::open(path)?
        .take(MAX_BYTES + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err(io::Error::other("file limit"));
    }
    Ok(Some(bytes))
}

struct Inventory {
    sources: Value,
    paths: BTreeSet<PathBuf>,
    gaps: BTreeSet<String>,
}

fn snapshot(workspace: &Path, roots: &[PathBuf]) -> Inventory {
    let mut sources = BTreeMap::new();
    let mut paths = BTreeSet::new();
    let mut gaps = BTreeSet::new();
    let mut total_bytes = 0;
    for root in roots {
        let label = root.strip_prefix(workspace).unwrap().to_string_lossy();
        let label = if label.is_empty() { "." } else { &label };
        let mut files: BTreeSet<String> = CORE.iter().map(|s| (*s).into()).collect();
        files.insert("handoff.config.json".into());
        for route in ROUTES {
            files.insert((*route).into());
        }
        let config_bytes = if total_bytes < MAX_TOTAL_BYTES {
            read(root, Path::new("handoff.config.json"))
        } else {
            gaps.insert("snapshot-byte-limit".into());
            Err(io::Error::other("snapshot byte limit"))
        };
        let config = match config_bytes {
            Ok(Some(bytes)) => {
                total_bytes += bytes.len();
                match serde_json::from_slice::<Value>(&bytes) {
                    Ok(value) if value.is_object() => value,
                    _ => {
                        gaps.insert(format!("{label}:invalid-config"));
                        Value::Null
                    }
                }
            }
            Ok(None) => Value::Null,
            Err(_) => {
                gaps.insert(format!("{label}:unreadable-config"));
                Value::Null
            }
        };
        let version = config["instruction_version"]
            .as_str()
            .filter(|v| !v.is_empty() && v.len() <= 128);
        if version.is_none() {
            gaps.insert(format!("{label}:unversioned"));
        }
        // Adopt MM's `current` set. Additional conditional routes are explicit,
        // never a recursive scan of source, history, prompts or native homes.
        for key in ["current", "run_context_files"] {
            if let Some(value) = config.get(key) {
                if let Some(items) = value.as_array() {
                    for item in items.iter().take(MAX_FILES) {
                        match item.as_str() {
                            Some(name) if relative(Path::new(name)) && name.len() <= 512 => {
                                if files.contains(name) || files.len() < MAX_FILES {
                                    files.insert(name.into());
                                } else {
                                    gaps.insert(format!("{label}:file-limit"));
                                }
                            }
                            _ => {
                                gaps.insert(format!("{label}:invalid-file-list"));
                            }
                        }
                    }
                    if items.len() > MAX_FILES {
                        gaps.insert(format!("{label}:file-limit"));
                    }
                } else {
                    gaps.insert(format!("{label}:invalid-file-list"));
                }
            }
        }
        if files.len() > MAX_FILES {
            gaps.insert(format!("{label}:file-limit"));
        }
        let mut hashes: BTreeMap<String, Option<String>> = BTreeMap::new();
        let mut states = BTreeMap::new();
        for name in files.into_iter().take(MAX_FILES) {
            paths.insert(root.join(&name));
            let observation = if total_bytes < MAX_TOTAL_BYTES {
                read(root, Path::new(&name))
            } else {
                gaps.insert("snapshot-byte-limit".into());
                Err(io::Error::other("snapshot byte limit"))
            };
            let (digest, state) = match observation {
                Ok(Some(bytes)) => {
                    total_bytes += bytes.len();
                    (Some(hash(&bytes)), "present")
                }
                Ok(None) => (None, "missing"),
                Err(_) => {
                    gaps.insert(format!("{label}:unreadable-file"));
                    (None, "unavailable")
                }
            };
            hashes.insert(name.clone(), digest);
            states.insert(name, state);
        }
        // BTreeMap gives MM's sorted, compact JSON fingerprint encoding.
        let fingerprint = hash(&serde_json::to_vec(&hashes).expect("serializable hashes"));
        sources.insert(
            label.to_owned(),
            json!({
                "instructionVersion": version.unwrap_or("unversioned"),
                "instructionSetSha256": fingerprint,
                "fileSha256": hashes,
                "fileState": states,
            }),
        );
    }
    Inventory {
        sources: json!(sources),
        paths,
        gaps,
    }
}

fn private_dir(path: &Path) -> io::Result<()> {
    let mut builder = fs::DirBuilder::new();
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;
        builder.mode(0o700);
    }
    match builder.create(path) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == io::ErrorKind::AlreadyExists => {
            let meta = fs::symlink_metadata(path)?;
            if meta.file_type().is_symlink() || !meta.is_dir() {
                Err(io::Error::other("unsafe output directory"))
            } else {
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    if meta.permissions().mode() & 0o077 != 0 {
                        return Err(io::Error::other("non-private output directory"));
                    }
                }
                Ok(())
            }
        }
        Err(e) => Err(e),
    }
}

struct State {
    record: Value,
    paths: BTreeSet<PathBuf>,
    destination: PathBuf,
    changed: bool,
    gaps: BTreeSet<String>,
    closed: bool,
}

impl State {
    fn save(&mut self) -> io::Result<()> {
        self.record["classification"] = json!(if self.changed {
            "mixed"
        } else if !self.closed || !self.gaps.is_empty() {
            "unknown"
        } else {
            "observed-stable"
        });
        self.record["unknownReasons"] = json!(self.gaps);
        self.record["updatedAt"] = json!(Utc::now().to_rfc3339());
        let mut temporary = tempfile::NamedTempFile::new_in(self.destination.parent().unwrap())?;
        serde_json::to_writer(temporary.as_file_mut(), &self.record)?;
        temporary.write_all(b"\n")?;
        temporary.persist(&self.destination).map_err(|e| e.error)?;
        Ok(())
    }

    fn event(&mut self, result: notify::Result<Event>) {
        if self.closed {
            return;
        }
        let old_changed = self.changed;
        let old_gaps = self.gaps.len();
        match result {
            Ok(event) if matches!(event.kind, EventKind::Access(_)) => return,
            Ok(event) => {
                if event.need_rescan() || event.paths.is_empty() {
                    self.gaps.insert("watcher-gap".into());
                }
                // An ancestor rename/removal also invalidates a selected file.
                if event
                    .paths
                    .iter()
                    .any(|path| self.paths.iter().any(|p| p.starts_with(path)))
                {
                    self.changed = true;
                    self.record["changeObservedAt"] = json!(Utc::now().to_rfc3339());
                }
            }
            Err(_) => {
                self.gaps.insert("watcher-error".into());
            }
        }
        // Persist the first change/gap immediately; no event log or polling loop.
        if (old_changed != self.changed || old_gaps != self.gaps.len()) && self.save().is_err() {
            self.gaps.insert("record-write-failed".into());
            tracing::warn!("Run context update unavailable; audit coverage is unknown");
        }
    }
}

/// Owned by the execution's existing exit monitor, also covering failed spawns.
/// All errors are telemetry failures: never change launch authority or permissions.
pub(crate) struct RunContext {
    watcher: Option<RecommendedWatcher>,
    state: Arc<Mutex<State>>,
    workspace: PathBuf,
    roots: Vec<PathBuf>,
}

impl RunContext {
    pub(crate) fn start(
        workspace: PathBuf,
        mut roots: Vec<PathBuf>,
        effective_dir: PathBuf,
        workspace_id: Uuid,
        session_id: Uuid,
        execution_id: Uuid,
        resumed: bool,
    ) -> io::Result<Self> {
        let workspace = workspace.canonicalize()?;
        let effective_dir = effective_dir.canonicalize()?;
        if !effective_dir.starts_with(&workspace) {
            return Err(io::Error::other("working directory outside workspace"));
        }
        roots.push(workspace.clone());
        // Include instruction scopes between the provider cwd and workspace.
        roots.extend(
            effective_dir
                .ancestors()
                .take_while(|p| p.starts_with(&workspace))
                .map(Path::to_path_buf),
        );
        let mut validated = BTreeSet::new();
        for root in roots {
            let canonical = root.canonicalize()?;
            if !canonical.starts_with(&workspace) {
                return Err(io::Error::other("repository outside workspace"));
            }
            validated.insert(canonical);
        }
        if validated.len() > MAX_ROOTS {
            return Err(io::Error::other("root limit"));
        }
        let roots: Vec<_> = validated.into_iter().collect();
        let directory = workspace.join(".vk-run-context");
        private_dir(&directory)?;
        let directory = directory.join(execution_id.to_string());
        // A repeated execution must not overwrite an earlier observation.
        fs::create_dir(&directory)?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&directory, fs::Permissions::from_mode(0o700))?;
        }
        let initial = snapshot(&workspace, &roots);
        let state = Arc::new(Mutex::new(State {
            record: json!({
                "schema": "vk.run-context.v1",
                "observationSchema": "mm.handoff-run.v1",
                "workspaceId": workspace_id,
                "sessionId": session_id,
                "executionId": execution_id,
                "usageSelector": {"execution_id": execution_id},
                "workspaceRoot": workspace,
                "workingDirectory": effective_dir,
                "phase": if resumed { "normal-resume" } else { "normal-start" },
                "conversationContext": if resumed { "inherited-unknown" } else { "new-execution-not-proof-of-fresh-context" },
                "observedAt": Utc::now().to_rfc3339(),
                "lifecycle": "starting",
                "claim": "working-tree files present at observation, not proof of reading",
                "modelReadStatus": "unknown",
            }),
            paths: initial.paths,
            destination: directory.join("record.json"),
            changed: false,
            gaps: BTreeSet::new(),
            closed: false,
        }));
        let callback = state.clone();
        let mut watcher = notify::recommended_watcher(move |event| {
            if let Ok(mut state) = callback.lock() {
                state.event(event);
            }
        })
        .ok();
        {
            let mut state = state.lock().map_err(|_| io::Error::other("context lock"))?;
            let mut directories = BTreeSet::new();
            for path in &state.paths {
                // Missing optional parents are covered by the nearest existing
                // directory; their creation is a conservative mixed event.
                let mut parent = path.parent().unwrap();
                while !parent.is_dir() {
                    parent = parent
                        .parent()
                        .ok_or_else(|| io::Error::other("no watch root"))?;
                }
                // A rejected instruction symlink must not cause external watches.
                match parent.canonicalize() {
                    Ok(parent) if parent.starts_with(&workspace) => {
                        directories.insert(parent);
                    }
                    _ => {
                        // Collected below without mutating while borrowing paths.
                        directories.insert(workspace.clone());
                    }
                }
            }
            if let Some(watcher) = &mut watcher {
                for dir in directories {
                    if watcher.watch(&dir, RecursiveMode::NonRecursive).is_err() {
                        state.gaps.insert("watcher-unavailable".into());
                    }
                }
            } else {
                state.gaps.insert("watcher-unavailable".into());
            }
            // Establish the baseline after arming; events during capture are
            // conservative mixed evidence, never a claim of atomic file reads.
            let baseline = snapshot(&workspace, &roots);
            if baseline.paths != state.paths {
                state.gaps.insert("inventory-changed-during-start".into());
            }
            state.gaps.extend(baseline.gaps);
            state.record["start"] = baseline.sources;
            state.save()?;
        }
        Ok(Self {
            watcher,
            state,
            workspace,
            roots,
        })
    }

    pub(crate) fn finish(mut self) {
        self.close("ended", true);
    }

    fn close(&mut self, lifecycle: &str, complete: bool) {
        if let Ok(mut state) = self.state.lock() {
            if state.closed {
                return;
            }
            let end = snapshot(&self.workspace, &self.roots);
            state.changed |= state.record["start"] != end.sources;
            state.gaps.extend(end.gaps);
            if !complete {
                state.gaps.insert("spawn-or-monitor-interrupted".into());
            }
            state.closed = true;
            state.record["end"] = end.sources;
            state.record["lifecycle"] = json!(lifecycle);
            state.record["endedAt"] = json!(Utc::now().to_rfc3339());
            if state.save().is_err() {
                tracing::warn!(
                    "Run context final observation unavailable; audit coverage is unknown"
                );
            }
        }
        self.watcher.take();
    }
}

impl Drop for RunContext {
    fn drop(&mut self) {
        self.close("interrupted", false);
    }
}

#[cfg(test)]
mod tests {
    use std::time::{Duration, Instant};

    use notify::event::{AccessKind, AccessMode, ModifyKind};

    use super::*;

    fn fixture() -> tempfile::TempDir {
        let root = tempfile::tempdir().unwrap();
        for name in CORE {
            fs::write(root.path().join(name), format!("# {name}\n")).unwrap();
        }
        fs::write(
            root.path().join("handoff.config.json"),
            r#"{"instruction_version":"test-v1"}"#,
        )
        .unwrap();
        root
    }

    fn start(root: &Path, resumed: bool) -> RunContext {
        RunContext::start(
            root.to_path_buf(),
            vec![],
            root.to_path_buf(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            resumed,
        )
        .unwrap()
    }

    fn record(path: &Path) -> Value {
        serde_json::from_slice(&fs::read(path).unwrap()).unwrap()
    }

    #[test]
    fn stable_snapshot_matches_mm_fingerprint_and_exact_ids() {
        let root = fixture();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        let pending = record(&path);
        assert_eq!(pending["classification"], "unknown");
        assert_eq!(pending["modelReadStatus"], "unknown");
        context.finish();
        let result = record(&path);
        assert_eq!(result["classification"], "observed-stable");
        assert_eq!(result["start"], result["end"]);
        assert_eq!(result["start"]["."]["instructionVersion"], "test-v1");
        let hashes = &result["start"]["."]["fileSha256"];
        assert_eq!(hashes["STATE.md"], hash(b"# STATE.md\n"));
        assert_eq!(
            result["start"]["."]["instructionSetSha256"],
            hash(&serde_json::to_vec(hashes).unwrap())
        );
        assert_eq!(
            result["usageSelector"]["execution_id"],
            result["executionId"]
        );
        for key in ["workspaceId", "sessionId", "executionId"] {
            assert!(Uuid::parse_str(result[key].as_str().unwrap()).is_ok());
        }
        assert_eq!(
            result["start"]["."]["fileState"]["docs/CURRENT_STATUS.md"],
            "missing"
        );
    }

    #[test]
    fn changed_and_reverted_event_is_still_mixed() {
        let root = fixture();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        // Deterministic callback contract: a write event cannot be erased by
        // equal end hashes. Native notification delivery is tested separately.
        context
            .state
            .lock()
            .unwrap()
            .event(Ok(Event::new(EventKind::Modify(ModifyKind::Data(
                notify::event::DataChange::Any,
            )))
            .add_path(root.path().join("STATE.md"))));
        assert_eq!(record(&path)["classification"], "mixed");
        context.finish();
        let result = record(&path);
        assert_eq!(result["start"], result["end"]);
        assert_eq!(result["classification"], "mixed");
    }

    #[test]
    fn native_file_event_is_persisted_while_execution_is_active() {
        let root = fixture();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        fs::write(root.path().join("HANDOFF.md"), "changed").unwrap();
        let deadline = Instant::now() + Duration::from_secs(5);
        while record(&path)["classification"] != "mixed" {
            assert!(
                Instant::now() < deadline,
                "native watcher did not observe write"
            );
            std::thread::sleep(Duration::from_millis(10));
        }
        context.finish();
        assert_eq!(record(&path)["classification"], "mixed");
    }

    #[test]
    fn end_hash_detects_change_even_without_notification() {
        let root = fixture();
        let mut context = start(root.path(), false);
        context.watcher.take();
        let path = context.state.lock().unwrap().destination.clone();
        fs::write(root.path().join("STATE.md"), "changed").unwrap();
        context.finish();
        assert_eq!(record(&path)["classification"], "mixed");
    }

    #[test]
    fn reads_and_unrelated_writes_do_not_mark_mixed() {
        let root = fixture();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        {
            let mut state = context.state.lock().unwrap();
            state.event(Ok(Event::new(EventKind::Access(AccessKind::Open(
                AccessMode::Read,
            )))
            .add_path(root.path().join("AGENTS.md"))));
            state.event(Ok(Event::new(EventKind::Modify(ModifyKind::Any))
                .add_path(root.path().join("unrelated.rs"))));
        }
        context.finish();
        assert_eq!(record(&path)["classification"], "observed-stable");
    }

    #[test]
    fn watcher_errors_and_interrupted_spawn_are_unknown() {
        let root = fixture();
        let context = start(root.path(), true);
        let path = context.state.lock().unwrap().destination.clone();
        context
            .state
            .lock()
            .unwrap()
            .event(Err(notify::Error::generic("unavailable")));
        drop(context);
        let result = record(&path);
        assert_eq!(result["classification"], "unknown");
        assert_eq!(result["lifecycle"], "interrupted");
        assert_eq!(result["conversationContext"], "inherited-unknown");
        assert!(
            result["unknownReasons"]
                .as_array()
                .unwrap()
                .contains(&json!("watcher-error"))
        );
    }

    #[test]
    fn notification_rescan_is_unknown_and_does_not_claim_stability() {
        let root = fixture();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        context.state.lock().unwrap().event(Ok(
            Event::new(EventKind::Other).set_flag(notify::event::Flag::Rescan)
        ));
        context.finish();
        let result = record(&path);
        assert_eq!(result["classification"], "unknown");
        assert!(
            result["unknownReasons"]
                .as_array()
                .unwrap()
                .contains(&json!("watcher-gap"))
        );
    }

    #[test]
    fn snapshot_budget_and_file_limits_are_unknown_without_dropping_core_paths() {
        let root = fixture();
        let mut names = Vec::new();
        for i in 0..(MAX_FILES + 1) {
            let name = format!("000-{i:03}.md");
            let file = File::create(root.path().join(&name)).unwrap();
            file.set_len(MAX_BYTES).unwrap();
            names.push(name);
        }
        fs::write(
            root.path().join("handoff.config.json"),
            json!({
                "instruction_version":"test-v1", "run_context_files":names,
            })
            .to_string(),
        )
        .unwrap();
        let observed = snapshot(root.path(), &[root.path().to_path_buf()]);
        assert!(observed.gaps.contains("snapshot-byte-limit"));
        assert!(observed.gaps.contains(".:file-limit"));
        assert!(observed.paths.contains(&root.path().join("AGENTS.md")));
        assert_eq!(
            observed.sources["."]["fileSha256"]
                .as_object()
                .unwrap()
                .len(),
            MAX_FILES
        );
        fn assert_send<T: Send>() {}
        assert_send::<RunContext>();
    }

    #[test]
    fn version_changes_and_added_routes_are_mixed() {
        let root = fixture();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        fs::write(root.path().join("route.md"), "conditional instructions").unwrap();
        fs::write(
            root.path().join("handoff.config.json"),
            r#"{"instruction_version":"test-v2","run_context_files":["route.md"]}"#,
        )
        .unwrap();
        context.finish();
        let result = record(&path);
        assert_eq!(result["classification"], "mixed");
        assert_eq!(result["end"]["."]["instructionVersion"], "test-v2");
        assert_eq!(
            result["end"]["."]["fileSha256"]["route.md"],
            hash(b"conditional instructions")
        );
    }

    #[test]
    fn invalid_config_unversioned_and_limits_remain_unknown() {
        let root = fixture();
        fs::write(root.path().join("handoff.config.json"), "invalid").unwrap();
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        context.finish();
        let result = record(&path);
        assert_eq!(result["classification"], "unknown");
        assert_eq!(result["start"]["."]["instructionVersion"], "unversioned");
        let file = File::create(root.path().join("STATE.md")).unwrap();
        file.set_len(MAX_BYTES + 1).unwrap();
        assert!(read(root.path(), Path::new("STATE.md")).is_err());
        assert!(read(root.path(), Path::new("../outside")).is_err());
    }

    #[test]
    fn separate_repositories_and_nested_cwd_are_observed_in_actual_workspace() {
        let root = fixture();
        fs::create_dir(root.path().join("repo")).unwrap();
        fs::create_dir(root.path().join("repo/sub")).unwrap();
        fs::write(root.path().join("repo/sub/AGENTS.md"), "scoped").unwrap();
        let context = RunContext::start(
            root.path().into(),
            vec![root.path().join("repo")],
            root.path().join("repo/sub"),
            Uuid::new_v4(),
            Uuid::new_v4(),
            Uuid::new_v4(),
            true,
        )
        .unwrap();
        let path = context.state.lock().unwrap().destination.clone();
        context.finish();
        assert_eq!(
            record(&path)["start"]["repo/sub"]["fileSha256"]["AGENTS.md"],
            hash(b"scoped")
        );
        assert!(path.starts_with(root.path()));
    }

    #[test]
    fn rejects_external_cwd_and_preserves_duplicate_record() {
        let root = fixture();
        let external = fixture();
        assert!(
            RunContext::start(
                root.path().into(),
                vec![],
                external.path().into(),
                Uuid::new_v4(),
                Uuid::new_v4(),
                Uuid::new_v4(),
                false
            )
            .is_err()
        );
        let context = start(root.path(), false);
        let path = context.state.lock().unwrap().destination.clone();
        let result = record(&path);
        assert!(
            RunContext::start(
                root.path().into(),
                vec![],
                root.path().into(),
                Uuid::new_v4(),
                Uuid::new_v4(),
                Uuid::parse_str(result["executionId"].as_str().unwrap()).unwrap(),
                false
            )
            .is_err()
        );
        assert_eq!(result, record(&path));
        context.finish();
    }

    #[cfg(unix)]
    #[test]
    fn rejects_external_symlinks_and_non_private_storage() {
        use std::os::unix::fs::{PermissionsExt, symlink};
        let root = fixture();
        let external = fixture();
        fs::remove_file(root.path().join("STATE.md")).unwrap();
        symlink(
            external.path().join("STATE.md"),
            root.path().join("STATE.md"),
        )
        .unwrap();
        assert!(read(root.path(), Path::new("STATE.md")).is_err());
        let directory = root.path().join(".vk-run-context");
        symlink(external.path(), &directory).unwrap();
        assert!(private_dir(&directory).is_err());
        fs::remove_file(&directory).unwrap();
        fs::create_dir(&directory).unwrap();
        fs::set_permissions(&directory, fs::Permissions::from_mode(0o755)).unwrap();
        assert!(private_dir(&directory).is_err());
    }
}
