//! On-demand catalog renewal only: never creates a thread, turn or billed probe.
use std::{
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Mutex, mpsc},
    time::{Duration, Instant},
};

use command_group::{CommandGroup, GroupChild};
use serde_json::{Value, json};

use crate::routing::Availability;

// One bounded attempt, with a short failure cooldown across parent/child/classifier calls.
static REFRESH: Mutex<Option<(PathBuf, Instant, String)>> = Mutex::new(None);

pub(crate) fn refresh(path: &Path, old: Availability) -> Result<Availability, String> {
    let mut state = REFRESH
        .try_lock()
        .map_err(|_| "Routing catalog refresh busy; retry at a later execution boundary")?;
    if let Some((failed_path, at, error)) = &*state
        && failed_path == path
        && at.elapsed() < Duration::from_secs(60)
    {
        return Err(error.clone());
    }
    let started = Instant::now();
    let result = refresh_file(path, old);
    match &result {
        Ok(_) => {
            *state = None;
            tracing::info!(
                elapsed_ms = started.elapsed().as_millis() as u64,
                "Routing catalog refreshed without inference; original verification timestamps retained"
            );
        }
        Err(error) => {
            let error = format!("Routing catalog refresh unavailable: {error}");
            tracing::warn!(%error);
            *state = Some((path.to_owned(), Instant::now(), error.clone()));
            return Err(error);
        }
    }
    result
}

fn refresh_file(path: &Path, old: Availability) -> Result<Availability, String> {
    if old.runtime.as_ref().is_none_or(String::is_empty) {
        return Err(
            "Legacy proof lacks native runtime identity; refresh executable-model verification"
                .into(),
        );
    }
    if crate::executors::codex::codex_execution_disabled() {
        return Err("Codex execution disabled".into());
    }
    if let Some(error) = crate::executors::codex::codex_execution_limit_error() {
        return Err(error.to_string());
    }
    let mut options = std::fs::OpenOptions::new();
    options.create(true).write(true).truncate(false);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let lock = options
        .open(path.with_extension("refresh.lock"))
        .map_err(|_| "Cannot lock routing catalog refresh")?;
    lock.try_lock()
        .map_err(|_| "Routing catalog refresh already in progress")?;
    // Another process may have refreshed while this caller read the old file.
    let source = std::fs::read(path).map_err(|_| "Cannot read routing proof")?;
    let current: Availability =
        serde_json::from_slice(&source).map_err(|_| "Invalid routing proof")?;
    if serde_json::to_value(&current).ok() != serde_json::to_value(&old).ok() {
        return Err("Routing proof changed during refresh; retry at the next boundary".into());
    }
    let mut rpc = CatalogRpc::start(&old)?;
    // Match the original probe's identity; userAgent includes clientInfo.
    let init = rpc.call(
        "initialize",
        json!({"clientInfo":{"name":"vk_routing_probe","version":"1"}}),
    )?;
    rpc.send(json!({"method":"initialized","params":{}}))?;
    let account = rpc.call("account/read", json!({}))?;
    validate_identity(&old, &init, &account)?;
    let mut catalog = Vec::new();
    let mut cursor = Value::Null;
    for _ in 0..16 {
        let page = rpc.call("model/list", json!({"includeHidden":true,"cursor":cursor}))?;
        catalog.extend(
            page["data"]
                .as_array()
                .ok_or("Invalid native model catalog")?
                .iter()
                .cloned(),
        );
        cursor = page.get("nextCursor").cloned().unwrap_or(Value::Null);
        if cursor.is_null() {
            break;
        }
    }
    if !cursor.is_null() {
        return Err("Native model catalog exceeds page bound".into());
    }
    let fresh = renew(old, &catalog, chrono::Utc::now().timestamp());
    let tmp = path.with_extension(format!("{}.tmp", uuid::Uuid::new_v4()));
    let write = (|| -> Result<(), String> {
        let mut options = std::fs::OpenOptions::new();
        options.create_new(true).write(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options
            .open(&tmp)
            .map_err(|_| "Cannot stage refreshed catalog")?;
        file.write_all(&serde_json::to_vec_pretty(&fresh).map_err(|_| "Cannot serialize catalog")?)
            .map_err(|_| "Cannot write refreshed catalog")?;
        file.sync_all()
            .map_err(|_| "Cannot sync refreshed catalog")?;
        if std::fs::read(path).map_err(|_| "Cannot recheck routing proof")? != source {
            return Err("Routing proof changed during refresh; original file preserved".into());
        }
        std::fs::rename(&tmp, path).map_err(|_| "Cannot atomically replace routing catalog")?;
        Ok(())
    })();
    if write.is_err() {
        let _ = std::fs::remove_file(tmp);
    }
    write?;
    Ok(fresh)
}

fn validate_identity(old: &Availability, init: &Value, account: &Value) -> Result<(), String> {
    if !crate::routing_runtime_identity::matches(old.runtime.as_deref(), init["userAgent"].as_str())
    {
        return Err("Native runtime changed; refresh executable-model verification".into());
    }
    let account = &account["account"];
    if account["type"] != "chatgpt"
        || account["email"].as_str().is_none_or(str::is_empty)
        || crate::routing::account_fingerprint(account) != old.account_fingerprint
    {
        return Err("Native account changed; refresh executable-model verification".into());
    }
    Ok(())
}

fn renew(mut old: Availability, catalog: &[Value], now: i64) -> Availability {
    for model in &mut old.models {
        let native = catalog.iter().find(|m| m["id"] == model.id);
        model.discovered = native.is_some();
        model.supported_efforts = native
            .and_then(|m| m["supportedReasoningEfforts"].as_array())
            .into_iter()
            .flatten()
            .filter_map(|e| e["reasoningEffort"].as_str().map(str::to_owned))
            .collect();
        // Never manufacture execution evidence or qualify newly discovered pairs.
    }
    old.observed_at = now;
    old
}

struct CatalogRpc {
    process: GroupChild,
    rx: mpsc::Receiver<Value>,
    seq: u32,
    deadline: Instant,
}
impl Drop for CatalogRpc {
    fn drop(&mut self) {
        let _ = self.process.kill();
        let _ = self.process.wait();
    }
}
impl CatalogRpc {
    fn start(old: &Availability) -> Result<Self, String> {
        let args = shlex::split(&old.launcher).ok_or("Invalid routing launcher")?;
        let (program, args) = args.split_first().ok_or("Missing routing launcher")?;
        let mut command = Command::new(program);
        command
            .args(args)
            .arg("app-server")
            .env("CODEX_HOME", &old.codex_home)
            .current_dir(&old.codex_home)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        let mut process = command
            .group_spawn()
            .map_err(|_| "Catalog process failed to start")?;
        let stdout = process.inner().stdout.take().expect("piped stdout");
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout.take(2 * 1024 * 1024));
            loop {
                let mut line = String::new();
                if !matches!(
                    reader.by_ref().take(262145).read_line(&mut line),
                    Ok(1..=262144)
                ) {
                    break;
                }
                let Ok(value) = serde_json::from_str(&line) else {
                    break;
                };
                if tx.send(value).is_err() {
                    break;
                }
            }
        });
        Ok(Self {
            process,
            rx,
            seq: 0,
            deadline: Instant::now() + Duration::from_secs(15),
        })
    }
    fn send(&mut self, value: Value) -> Result<(), String> {
        let input = self
            .process
            .inner()
            .stdin
            .as_mut()
            .ok_or("Catalog stdin unavailable")?;
        writeln!(input, "{value}")
            .and_then(|_| input.flush())
            .map_err(|_| "Catalog request failed".into())
    }
    fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        // Keep this transport incapable of paid inference, even if reused later.
        if !["initialize", "account/read", "model/list"].contains(&method) {
            return Err("Non-discovery RPC forbidden".into());
        }
        self.seq += 1;
        self.send(json!({"id":self.seq,"method":method,"params":params}))?;
        loop {
            let event = self
                .rx
                .recv_timeout(self.deadline.saturating_duration_since(Instant::now()))
                .map_err(|_| "Catalog refresh timed out or closed")?;
            if event["id"] == self.seq {
                if event.get("error").is_some() {
                    return Err(format!("Catalog RPC rejected: {method}"));
                }
                return event
                    .get("result")
                    .cloned()
                    .ok_or("Catalog result missing".into());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing::{
        CapabilityFloor, RoutingMode, RoutingPolicy, choose_assessed, model_policies,
    };

    fn proof() -> Availability {
        serde_json::from_value(json!({"version":1,"observed_at":100,"runtime":"native-v1","launcher":"codex","codex_home":"/test","account_fingerprint":crate::routing::account_fingerprint(&json!({"type":"chatgpt","email":"fixture@example.invalid"})),"models":[{"id":"gpt-6.1-sol","discovered":true,"supported_efforts":["medium"],"verified_efforts":["medium"],"verified_at":100}]})).unwrap()
    }
    fn catalog(effort: &str) -> Vec<Value> {
        vec![json!({"id":"gpt-6.1-sol","supportedReasoningEfforts":[{"reasoningEffort":effort}]})]
    }
    fn choose(a: &Availability, now: i64) -> Result<(String, String), String> {
        choose_assessed(
            &RoutingPolicy {
                mode: RoutingMode::Auto,
                floor: CapabilityFloor::Workhorse,
                denied_models: vec![],
                allow_escalation: false,
            },
            CapabilityFloor::Workhorse,
            "normal",
            &model_policies().unwrap(),
            a,
            now,
        )
    }
    #[test]
    fn fresh_discovery_retains_historical_execution_without_rewriting_it() {
        let old = proof();
        assert!(choose(&old, 90000).is_err());
        let fresh = renew(old, &catalog("medium"), 90000);
        assert_eq!(fresh.models[0].verified_at, Some(100));
        assert_eq!(
            choose(&fresh, 90000).unwrap(),
            ("gpt-6.1-sol".into(), "medium".into())
        );
        assert!(choose(&fresh, 180000).is_err());
    }
    #[test]
    fn removed_models_efforts_and_unverified_pairs_never_gain_qualification() {
        assert!(choose(&renew(proof(), &[], 90000), 90000).is_err());
        assert!(choose(&renew(proof(), &catalog("low"), 90000), 90000).is_err());
        let mut old = proof();
        old.models[0].verified_at = None;
        assert!(choose(&renew(old, &catalog("medium"), 90000), 90000).is_err());
        let mut old = proof();
        old.runtime = None;
        assert!(choose(&renew(old, &catalog("medium"), 90000), 90000).is_err());
        let mut old = proof();
        old.models[0].verified_at = Some(90001);
        assert!(choose(&renew(old, &catalog("medium"), 90000), 90000).is_err());
    }
    #[test]
    fn runtime_and_account_changes_require_new_execution_evidence() {
        let old = proof();
        let init = json!({"userAgent":"native-v1"});
        let account = json!({"account":{"type":"chatgpt","email":"fixture@example.invalid"}});
        assert!(validate_identity(&old, &init, &account).is_ok());
        assert!(validate_identity(&old, &json!({"userAgent":"native-v2"}), &account).is_err());
        assert!(
            validate_identity(
                &old,
                &init,
                &json!({"account":{"type":"chatgpt","email":"different@example.invalid"}})
            )
            .is_err()
        );
        assert!(validate_identity(&old, &init, &json!({"account":null})).is_err());
    }
    #[test]
    #[ignore = "opt-in real read-only catalog RPC; requires an isolated proof copy on SSD"]
    fn native_catalog_refresh_without_inference() {
        let path = PathBuf::from(
            std::env::var("VK_ROUTING_REFRESH_TEST_FILE").expect("isolated proof copy required"),
        );
        let old: Availability = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        let fresh = refresh_file(&path, old.clone()).unwrap();
        assert!(fresh.observed_at > old.observed_at);
        assert_eq!(fresh.account_fingerprint, old.account_fingerprint);
        assert_eq!(fresh.runtime, old.runtime);
        for (after, before) in fresh.models.iter().zip(&old.models) {
            assert_eq!(after.verified_at, before.verified_at);
            assert_eq!(after.verified_efforts, before.verified_efforts);
        }
        assert!(choose(&fresh, chrono::Utc::now().timestamp()).is_ok());
    }
}
