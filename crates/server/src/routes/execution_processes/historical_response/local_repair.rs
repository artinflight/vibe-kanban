//! Exact-two-incident OS-authenticated repair. No deployment initialization,
//! migrations, HTTP writes, signing contexts, credentials or arbitrary paths.
use std::{collections::HashSet, os::unix::fs::MetadataExt, time::Duration};

use sqlx::sqlite::{SqliteConnectOptions, SqlitePoolOptions};

use super::*;

const DATA_ROOT: &str = "/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban";
const HOME: &str = "/home/mcp/.local/share/vibe-kanban-green-codex-home";
const T18: &str = "3ce20433-f984-4c33-800f-d4987145fa4a";
const MM: &str = "c64a7b0c-9c34-43e0-b70d-7e05f93751ef";

fn reviewed_request(id: Uuid) -> RecoveryResult<RecoveryRequest> {
    let input = match id.to_string().as_str() {
        T18 => include_str!("t18-request.json"),
        MM => include_str!("mm-request.json"),
        _ => return Err("Only the two reviewed original executions are allowed".into()),
    };
    serde_json::from_str(input).map_err(|_| "Reviewed incident binding unavailable".into())
}

#[derive(Debug, PartialEq)]
struct Invocation {
    execution: Uuid,
    pid: u32,
    port: u16,
    apply: bool,
}

fn invocation(args: Vec<String>) -> RecoveryResult<Invocation> {
    const USAGE: &str = "Expected --target ORIGINAL_EXECUTION --server-pid PID --port PORT [--apply SAME_ORIGINAL_EXECUTION]";
    let mut values = std::collections::HashMap::new();
    let mut chunks = args.chunks_exact(2);
    for pair in &mut chunks {
        if !["--target", "--server-pid", "--port", "--apply"].contains(&pair[0].as_str())
            || values.insert(pair[0].as_str(), pair[1].as_str()).is_some()
        {
            return Err(USAGE.into());
        }
    }
    if !chunks.remainder().is_empty() {
        return Err(USAGE.into());
    }
    let execution = values
        .get("--target")
        .ok_or(USAGE)?
        .parse()
        .map_err(|_| USAGE)?;
    reviewed_request(execution)?;
    let pid = values
        .get("--server-pid")
        .ok_or(USAGE)?
        .parse()
        .map_err(|_| USAGE)?;
    let port = values
        .get("--port")
        .ok_or(USAGE)?
        .parse()
        .map_err(|_| USAGE)?;
    if pid == 0 || port == 0 {
        return Err(USAGE.into());
    }
    let apply = if let Some(value) = values.get("--apply") {
        if value.parse::<Uuid>().ok() != Some(execution) {
            return Err("Apply must explicitly name the same exact original execution".into());
        }
        true
    } else {
        false
    };
    Ok(Invocation {
        execution,
        pid,
        port,
        apply,
    })
}

fn effective_uid(pid: u32) -> RecoveryResult<u32> {
    let status = fs::read_to_string(format!("/proc/{pid}/status"))
        .map_err(|_| "Process identity unavailable")?;
    status
        .lines()
        .find_map(|line| {
            line.strip_prefix("Uid:")?
                .split_whitespace()
                .nth(1)?
                .parse()
                .ok()
        })
        .ok_or_else(|| "Effective process UID unavailable".into())
}

fn same_uid(operator: u32, server: u32) -> RecoveryResult<()> {
    if operator == 0 || operator != server {
        return Err("Recovery requires the existing same non-root service UID".into());
    }
    Ok(())
}

fn owned(path: &Path, uid: u32) -> RecoveryResult<()> {
    let metadata = fs::symlink_metadata(path).map_err(|_| "Recovery ownership unavailable")?;
    if metadata.uid() != uid || metadata.file_type().is_symlink() {
        return Err(
            "Recovery evidence/output must be owned by the service UID and not symlinked".into(),
        );
    }
    Ok(())
}

fn owned_tree(path: &Path, root: &Path, uid: u32) -> RecoveryResult<()> {
    if !path.starts_with(root) {
        return Err("Recovery evidence escaped its existing service root".into());
    }
    let mut current = path;
    loop {
        owned(current, uid)?;
        if current == root {
            break;
        }
        current = current.parent().ok_or("Recovery parent unavailable")?;
    }
    Ok(())
}

// Bind the loopback listener to the requested live process, not just a JSON PID
// supplied by an arbitrary HTTP service. Recheck start ticks against PID reuse.
fn live_server(pid: u32, port: u16, uid: u32) -> RecoveryResult<String> {
    same_uid(uid, effective_uid(pid)?)?;
    let stat = fs::read_to_string(format!("/proc/{pid}/stat"))
        .map_err(|_| "Server process unavailable")?;
    let fields = stat.rsplit_once(") ").ok_or("Server stat damaged")?.1;
    let ticks = fields
        .split_whitespace()
        .nth(19)
        .ok_or("Server start identity unavailable")?;
    let sockets: HashSet<String> = fs::read_dir(format!("/proc/{pid}/fd"))
        .map_err(|_| "Server listener identity unavailable")?
        .filter_map(|entry| fs::read_link(entry.ok()?.path()).ok())
        .filter_map(|link| {
            link.to_str()?
                .strip_prefix("socket:[")?
                .strip_suffix(']')
                .map(str::to_owned)
        })
        .collect();
    let tcp = fs::read_to_string("/proc/net/tcp").map_err(|_| "Loopback listeners unavailable")?;
    let address = format!("0100007F:{port:04X}");
    let listening = tcp.lines().skip(1).any(|line| {
        let parts: Vec<_> = line.split_whitespace().collect();
        parts.len() > 9
            && parts[1] == address
            && parts[3] == "0A"
            && parts[7].parse::<u32>().ok() == Some(uid)
            && sockets.contains(parts[9])
    });
    if !listening {
        return Err("Requested server does not own the exact loopback listener".into());
    }
    Ok(ticks.into())
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub(crate) struct CaptureStatus {
    protocol: u32,
    server_pid: u32,
    server_uid: u32,
    execution_id: Uuid,
    execution_revision: DateTime<Utc>,
    session_id: Uuid,
    workspace_id: Uuid,
    database_path_sha256: String,
    native_home_sha256: String,
    capture_path_sha256: String,
    writer_active: bool,
    incomplete: bool,
}

fn path_hash(path: &Path) -> RecoveryResult<String> {
    let canonical = fs::canonicalize(path).map_err(|_| "Service storage path unavailable")?;
    Ok(sha(canonical.as_os_str().as_encoded_bytes()))
}

async fn status_for(
    process: &ExecutionProcess,
    pool: &sqlx::SqlitePool,
    home: &Path,
) -> RecoveryResult<CaptureStatus> {
    let session = Session::find_by_id(pool, process.session_id)
        .await
        .map_err(|_| "Original session lookup failed")?
        .ok_or("Original session unavailable")?;
    let capture = services::services::execution_process::execution_log_file_path_for_execution(
        pool, process.id,
    )
    .await
    .map_err(|_| "Original capture lookup failed")?
    .ok_or("Original capture unavailable")?;
    let incomplete = super::super::log_history::capture_error_for_process(pool, process)
        .await
        .map_err(|_| "Original capture status unavailable")?
        .is_some();
    Ok(CaptureStatus {
        protocol: 1,
        server_pid: std::process::id(),
        server_uid: effective_uid(std::process::id())?,
        execution_id: process.id,
        execution_revision: process.updated_at,
        session_id: process.session_id,
        workspace_id: session.workspace_id,
        database_path_sha256: path_hash(pool.connect_options().get_filename())?,
        native_home_sha256: path_hash(home)?,
        capture_path_sha256: path_hash(&capture)?,
        writer_active: services::services::execution_process::capture_in_progress(process.id),
        incomplete,
    })
}

/// Read-only normal API; signed import authorization remains unchanged.
pub(crate) async fn capture_status(
    Extension(process): Extension<ExecutionProcess>,
    State(deployment): State<DeploymentImpl>,
) -> Result<Json<utils::response::ApiResponse<CaptureStatus>>, ApiError> {
    let request = reviewed_request(process.id).map_err(ApiError::Conflict)?;
    binding(&process, &request).map_err(ApiError::Conflict)?;
    let home = codex_home().ok_or_else(|| ApiError::Conflict("Native home unavailable".into()))?;
    let status = status_for(&process, &deployment.db().pool, &home)
        .await
        .map_err(ApiError::Conflict)?;
    Ok(Json(utils::response::ApiResponse::success(status)))
}

async fn remote_status(
    client: &reqwest::Client,
    invocation: &Invocation,
) -> RecoveryResult<CaptureStatus> {
    let response = client
        .get(format!(
            "http://127.0.0.1:{}/api/execution-processes/{}/native-recovery-status",
            invocation.port, invocation.execution
        ))
        .send()
        .await
        .map_err(
            |_| "Authoritative server capture status unavailable; matching publication required",
        )?;
    if !response.status().is_success() || response.content_length().is_some_and(|len| len > 8192) {
        return Err("Authoritative capture-status protocol unavailable".into());
    }
    let mut response = response;
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| "Capture status read failed")?
    {
        if bytes.len() + chunk.len() > 8192 {
            return Err("Capture status exceeds bound".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    let envelope: Value = serde_json::from_slice(&bytes).map_err(|_| "Capture status damaged")?;
    if envelope["success"] != true {
        return Err("Capture status refused".into());
    }
    serde_json::from_value(envelope["data"].clone())
        .map_err(|_| "Capture status protocol mismatch".into())
}

fn check_status(
    status: &CaptureStatus,
    invocation: &Invocation,
    uid: u32,
    request: &RecoveryRequest,
    database: &Path,
    home: &Path,
    capture: &Path,
) -> RecoveryResult<()> {
    same_uid(uid, status.server_uid)?;
    if status.protocol != 1
        || status.server_pid != invocation.pid
        || status.execution_id != invocation.execution
        || status.execution_revision != request.execution_revision
        || status.session_id != request.session_id
        || status.workspace_id != request.workspace_id
        || status.database_path_sha256 != path_hash(database)?
        || status.native_home_sha256 != path_hash(home)?
        || status.capture_path_sha256 != path_hash(capture)?
        || status.writer_active
        || !status.incomplete
    {
        return Err(
            "Server identity, original binding or inactive incomplete capture proof does not match"
                .into(),
        );
    }
    Ok(())
}

async fn readonly_pool(database: &Path) -> RecoveryResult<sqlx::SqlitePool> {
    SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            SqliteConnectOptions::new()
                .filename(database)
                .read_only(true)
                .create_if_missing(false),
        )
        .await
        .map_err(|_| {
            "Existing read-only database unavailable; no creation or migration allowed".into()
        })
}

async fn original(
    pool: &sqlx::SqlitePool,
    execution: Uuid,
    request: &RecoveryRequest,
) -> RecoveryResult<ExecutionProcess> {
    let process = ExecutionProcess::find_by_id(pool, execution)
        .await
        .map_err(|_| "Original execution lookup failed")?
        .ok_or("Original execution unavailable")?;
    binding(&process, request)?;
    let session = Session::find_by_id(pool, process.session_id)
        .await
        .map_err(|_| "Original session lookup failed")?
        .ok_or("Original session unavailable")?;
    if session.workspace_id != request.workspace_id {
        return Err("Original workspace mismatch".into());
    }
    Ok(process)
}

pub(crate) async fn run(args: Vec<String>) -> RecoveryResult<()> {
    let invocation = invocation(args)?;
    let request = reviewed_request(invocation.execution)?;
    let receipt = execute(
        &invocation,
        &request,
        Path::new(DATA_ROOT),
        Path::new(HOME),
        &Path::new(DATA_ROOT).join("db.v2.sqlite"),
    )
    .await?;
    println!("{receipt}");
    Ok(())
}

// Private core shared with disposable end-to-end fixtures. The only public
// invocation above derives every path and request from fixed reviewed pins.
async fn execute(
    invocation: &Invocation,
    request: &RecoveryRequest,
    root: &Path,
    home: &Path,
    database: &Path,
) -> RecoveryResult<Value> {
    let uid = effective_uid(std::process::id())?;
    let ticks = live_server(invocation.pid, invocation.port, uid)?;
    owned(database, uid)?;
    owned(root, uid)?;
    owned(home, uid)?;
    let pool = readonly_pool(database).await?;
    let process = original(&pool, invocation.execution, request).await?;
    // Derive from the fixed service root, not a debug binary's checkout asset
    // directory or an inherited XDG override. The server must independently
    // report this same existing original path in its authoritative status.
    let capture =
        utils::execution_logs::process_log_file_path_in_root(root, request.session_id, process.id);
    owned_tree(&capture, root, uid)?;
    owned_tree(&native_path(home, request.native_session_id)?, home, uid)?;
    let client = reqwest::Client::builder()
        .no_proxy()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(10))
        .build()
        .map_err(|_| "Capture status client unavailable")?;
    let before = remote_status(&client, invocation).await?;
    check_status(&before, invocation, uid, request, database, home, &capture)?;
    let record = recover(&process, request, home, &capture)?;
    // Fail on a conflicting sidecar even in verify-only mode.
    match fs::symlink_metadata(record_path(&capture)) {
        Ok(_) => {
            owned(&record_path(&capture), uid)?;
            if load_record(&record_path(&capture))? != record {
                return Err("Conflicting recovered response exists".into());
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => return Err("Recovered response metadata unavailable".into()),
    }
    let current = original(&pool, invocation.execution, request).await?;
    // Repeat exact native/capture verification before the final live-server and
    // database recheck, so a revision change during parsing cannot be published.
    if recover(&current, request, home, &capture)? != record {
        return Err("Original evidence changed before publication".into());
    }
    original(&pool, invocation.execution, request).await?;
    let after = remote_status(&client, invocation).await?;
    check_status(&after, invocation, uid, request, database, home, &capture)?;
    if before != after || live_server(invocation.pid, invocation.port, uid)? != ticks {
        return Err("Server/capture identity changed during verification".into());
    }
    owned_tree(&capture, root, uid)?;
    owned_tree(&native_path(home, request.native_session_id)?, home, uid)?;
    if bounded_file_hash(&capture)? != request.original_capture_sha256 {
        return Err("Original capture changed before publication".into());
    }
    let created = if invocation.apply {
        save(&capture, &record)?
    } else {
        false
    };
    pool.close().await;
    Ok(
        json!({"execution_id":record.execution_id,"native_turn_id":request.native_turn_id,
        "reply_sha256":request.reply_sha256,"final_at":record.final_at,"verify_only":!invocation.apply,
        "created":created,"database_read_only":true,"writer_inactive":true,
        "original_capture_complete":false,"review_certified":false}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone)]
    struct StatusFixture {
        pool: sqlx::SqlitePool,
        home: PathBuf,
        execution: Uuid,
    }

    async fn fixture_status_http(
        State(state): State<StatusFixture>,
    ) -> Result<Json<utils::response::ApiResponse<CaptureStatus>>, ApiError> {
        let process = ExecutionProcess::find_by_id(&state.pool, state.execution)
            .await?
            .ok_or_else(|| ApiError::Conflict("Fixture original unavailable".into()))?;
        let status = status_for(&process, &state.pool, &state.home)
            .await
            .map_err(ApiError::Conflict)?;
        Ok(Json(utils::response::ApiResponse::success(status)))
    }

    #[tokio::test]
    async fn actual_cli_core_verify_apply_duplicate_conflict_and_evidence_preservation() {
        let f = super::super::tests::Fixture::new();
        let database = f.home.path().join("fixture.sqlite");
        let source_pool = f.pool_at(&database).await;
        assert!(database.is_file());
        let pool = readonly_pool(&database).await.unwrap();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let mut invocation = Invocation {
            execution: f.process.id,
            pid: std::process::id(),
            port: listener.local_addr().unwrap().port(),
            apply: false,
        };
        let route = format!(
            "/api/execution-processes/{}/native-recovery-status",
            invocation.execution
        );
        let app = axum::Router::new()
            .route(&route, axum::routing::get(fixture_status_http))
            .with_state(StatusFixture {
                pool: pool.clone(),
                home: f.home.path().into(),
                execution: f.process.id,
            });
        let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        let root = utils::assets::asset_dir();
        let capture_before = bounded_file_hash(&f.capture).unwrap();
        let source = native_path(f.home.path(), f.request.native_session_id).unwrap();
        let native_before = bounded_file_hash(&source).unwrap();
        let database_before = bounded_file_hash(&database).unwrap();
        let closure = f.capture.with_extension("capture.json");
        let closure_before = fs::read(&closure).ok();
        let verified = execute(&invocation, &f.request, &root, f.home.path(), &database)
            .await
            .unwrap();
        assert_eq!(verified["verify_only"], true);
        assert!(!record_path(&f.capture).exists());
        invocation.apply = true;
        let applied = execute(&invocation, &f.request, &root, f.home.path(), &database)
            .await
            .unwrap();
        assert_eq!(applied["created"], true);
        assert_eq!(applied["review_certified"], false);
        assert_eq!(
            fs::metadata(record_path(&f.capture)).unwrap().mode() & 0o777,
            0o600
        );
        let saved = fs::read(record_path(&f.capture)).unwrap();
        assert_eq!(
            execute(&invocation, &f.request, &root, f.home.path(), &database)
                .await
                .unwrap()["created"],
            false
        );
        assert_eq!(fs::read(record_path(&f.capture)).unwrap(), saved);
        assert_eq!(bounded_file_hash(&f.capture).unwrap(), capture_before);
        assert_eq!(bounded_file_hash(&source).unwrap(), native_before);
        assert_eq!(bounded_file_hash(&database).unwrap(), database_before);
        assert_eq!(fs::read(&closure).ok(), closure_before);
        let mut conflicting = load_record(&record_path(&f.capture)).unwrap();
        conflicting.text.push_str(" fabricated");
        fs::write(
            record_path(&f.capture),
            serde_json::to_vec(&conflicting).unwrap(),
        )
        .unwrap();
        let conflict_before = fs::read(record_path(&f.capture)).unwrap();
        assert!(
            execute(&invocation, &f.request, &root, f.home.path(), &database)
                .await
                .is_err()
        );
        assert_eq!(fs::read(record_path(&f.capture)).unwrap(), conflict_before);
        invocation.apply = false;
        assert!(
            execute(&invocation, &f.request, &root, f.home.path(), &database)
                .await
                .is_err()
        );
        server.abort();
        pool.close().await;
        source_pool.close().await;
    }

    #[tokio::test]
    async fn real_server_registry_readonly_model_binding_and_revision_mutation() {
        let f = super::super::tests::Fixture::new();
        let database = f.home.path().join("fixture.sqlite");
        let source_pool = f.pool_at(&database).await;
        assert!(database.is_file());
        let pool = readonly_pool(&database).await.unwrap();
        let process = original(&pool, f.process.id, &f.request).await.unwrap();
        let status = status_for(&process, &pool, f.home.path()).await.unwrap();
        assert!(!status.writer_active);
        assert!(status.incomplete);
        let store = Arc::new(utils::msg_store::MsgStore::with_durable_capture(1024, 2, 1));
        let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
            store.clone(),
            db::DBService { pool: pool.clone() },
            process.id,
            process.session_id,
        );
        // This is the real live-server registry, not a CLI-local assumption.
        assert!(
            status_for(&process, &pool, f.home.path())
                .await
                .unwrap()
                .writer_active
        );
        let producer = store.clone().spawn_forwarder(futures_util::stream::empty::<
            Result<utils::log_msg::LogMsg, std::io::Error>,
        >());
        tokio::time::timeout(Duration::from_secs(5), writer)
            .await
            .unwrap()
            .unwrap();
        producer.await.unwrap();
        assert!(!services::services::execution_process::capture_in_progress(
            process.id
        ));
        let writable = SqlitePoolOptions::new()
            .max_connections(1)
            .connect_with(
                SqliteConnectOptions::new()
                    .filename(&database)
                    .create_if_missing(false),
            )
            .await
            .unwrap();
        sqlx::query(
            "UPDATE execution_processes SET updated_at = '2026-10-11T00:00:00Z' WHERE id = ?",
        )
        .bind(process.id)
        .execute(&writable)
        .await
        .unwrap();
        assert!(original(&pool, process.id, &f.request).await.is_err());
        assert!(!record_path(&f.capture).exists());
        writable.close().await;
        pool.close().await;
        source_pool.close().await;
    }

    #[test]
    fn exact_target_apply_default_and_pins() {
        let args = |extra: &[&str]| {
            ["--target", T18, "--server-pid", "123", "--port", "5561"]
                .into_iter()
                .chain(extra.iter().copied())
                .map(str::to_owned)
                .collect()
        };
        assert!(!invocation(args(&[])).unwrap().apply);
        assert!(invocation(args(&["--apply", T18])).unwrap().apply);
        for extra in [
            ["--apply", MM],
            ["--apply", "true"],
            ["--path", "/tmp/other"],
            ["--target", MM],
        ] {
            assert!(invocation(args(&extra)).is_err());
        }
        assert!(reviewed_request(Uuid::new_v4()).is_err());
        let t18 = reviewed_request(T18.parse().unwrap()).unwrap();
        let mm = reviewed_request(MM.parse().unwrap()).unwrap();
        assert_eq!(
            t18.workspace_id.to_string(),
            "c8b4d29e-b076-4f6d-a679-6f62bf287397"
        );
        assert_eq!(
            mm.workspace_id.to_string(),
            "fcf2fbbf-9dfd-4c2e-9588-7f3003ebb20d"
        );
        assert_eq!(
            t18.reply_sha256,
            "bff33c158b33897b8ddf7c568c2aa8cdaa52e6818e7053993ec9e9c9bae9d75b"
        );
        assert_eq!(
            mm.reply_sha256,
            "35c8e14f682f34ae484612283a5b459b53ff84d13575975672b43bc9e99acf27"
        );
    }

    #[test]
    fn root_uid_mismatch_and_symlink_refused() {
        assert!(same_uid(0, 0).is_err());
        assert!(same_uid(1000, 1001).is_err());
        assert!(same_uid(1000, 1000).is_ok());
        let uid = effective_uid(std::process::id()).unwrap();
        let root = tempfile::tempdir_in(utils::assets::asset_dir()).unwrap();
        let file = root.path().join("owned");
        fs::write(&file, b"fixture").unwrap();
        owned_tree(&file, root.path(), uid).unwrap();
        assert!(owned(&file, uid + 1).is_err());
        let link = root.path().join("link");
        std::os::unix::fs::symlink(&file, &link).unwrap();
        assert!(owned_tree(&link, root.path(), uid).is_err());
        assert!(owned_tree(&file, &root.path().join("other"), uid).is_err());
    }

    #[tokio::test]
    async fn actual_listener_identity_and_process_exit_fail_closed() {
        let uid = effective_uid(std::process::id()).unwrap();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let pid = std::process::id();
        let ticks = live_server(pid, port, uid).unwrap();
        assert_eq!(ticks, live_server(pid, port, uid).unwrap());
        assert!(live_server(pid, port, uid + 1).is_err());
        assert!(live_server(u32::MAX, port, uid).is_err());
        drop(listener);
        assert!(live_server(pid, port, uid).is_err());
    }

    #[tokio::test]
    async fn readonly_database_refuses_writes_creation_and_migration() {
        let root = tempfile::tempdir_in(utils::assets::asset_dir()).unwrap();
        let path = root.path().join("fixture.sqlite");
        let writable = SqlitePoolOptions::new()
            .max_connections(1)
            .connect_with(
                SqliteConnectOptions::new()
                    .filename(&path)
                    .create_if_missing(true),
            )
            .await
            .unwrap();
        sqlx::query("CREATE TABLE preserved (value TEXT)")
            .execute(&writable)
            .await
            .unwrap();
        sqlx::query("INSERT INTO preserved VALUES ('original')")
            .execute(&writable)
            .await
            .unwrap();
        writable.close().await;
        let before = bounded_file_hash(&path).unwrap();
        let pool = readonly_pool(&path).await.unwrap();
        assert_eq!(
            sqlx::query_scalar::<_, String>("SELECT value FROM preserved")
                .fetch_one(&pool)
                .await
                .unwrap(),
            "original"
        );
        assert!(
            sqlx::query("UPDATE preserved SET value = 'changed'")
                .execute(&pool)
                .await
                .is_err()
        );
        assert!(
            sqlx::query("CREATE TABLE migration (value TEXT)")
                .execute(&pool)
                .await
                .is_err()
        );
        pool.close().await;
        assert_eq!(bounded_file_hash(&path).unwrap(), before);
        let missing = root.path().join("missing.sqlite");
        assert!(readonly_pool(&missing).await.is_err());
        assert!(!missing.exists());
    }

    #[test]
    fn authoritative_writer_revision_and_storage_mismatch_refused() {
        let root = tempfile::tempdir_in(utils::assets::asset_dir()).unwrap();
        let database = root.path().join("fixture.sqlite");
        let capture = root.path().join("fixture.jsonl");
        fs::write(&database, b"fixture").unwrap();
        fs::write(&capture, b"raw incomplete fixture").unwrap();
        let uid = effective_uid(std::process::id()).unwrap();
        let request = reviewed_request(T18.parse().unwrap()).unwrap();
        let invocation = Invocation {
            execution: T18.parse().unwrap(),
            pid: std::process::id(),
            port: 5561,
            apply: false,
        };
        let good = CaptureStatus {
            protocol: 1,
            server_pid: invocation.pid,
            server_uid: uid,
            execution_id: invocation.execution,
            execution_revision: request.execution_revision,
            session_id: request.session_id,
            workspace_id: request.workspace_id,
            database_path_sha256: path_hash(&database).unwrap(),
            native_home_sha256: path_hash(root.path()).unwrap(),
            capture_path_sha256: path_hash(&capture).unwrap(),
            writer_active: false,
            incomplete: true,
        };
        let check = |status: &CaptureStatus| {
            check_status(
                status,
                &invocation,
                uid,
                &request,
                &database,
                root.path(),
                &capture,
            )
        };
        check(&good).unwrap();
        let mut status = good.clone();
        status.writer_active = true;
        assert!(check(&status).is_err());
        let mut status = good.clone();
        status.incomplete = false;
        assert!(check(&status).is_err());
        let mut status = good.clone();
        status.execution_revision += chrono::Duration::seconds(1);
        assert!(check(&status).is_err());
        let mut status = good.clone();
        status.server_pid += 1;
        assert!(check(&status).is_err());
        let mut status = good.clone();
        status.workspace_id = Uuid::new_v4();
        assert!(check(&status).is_err());
        let mut status = good.clone();
        status.database_path_sha256 = sha(b"wrong database");
        assert!(check(&status).is_err());
        let mut status = good.clone();
        status.protocol = 0;
        assert!(check(&status).is_err());
        assert!(!record_path(&capture).exists());
    }

    #[tokio::test]
    async fn real_http_missing_protocol_and_external_active_writer_refused() {
        let request = reviewed_request(T18.parse().unwrap()).unwrap();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let invocation = Invocation {
            execution: T18.parse().unwrap(),
            pid: std::process::id(),
            port: listener.local_addr().unwrap().port(),
            apply: false,
        };
        let active = CaptureStatus {
            protocol: 1,
            server_pid: invocation.pid,
            server_uid: effective_uid(invocation.pid).unwrap(),
            execution_id: invocation.execution,
            execution_revision: request.execution_revision,
            session_id: request.session_id,
            workspace_id: request.workspace_id,
            database_path_sha256: sha(b"db"),
            native_home_sha256: sha(b"home"),
            capture_path_sha256: sha(b"capture"),
            writer_active: true,
            incomplete: true,
        };
        let payload = json!({"success":true,"data":active});
        let route = format!(
            "/api/execution-processes/{}/native-recovery-status",
            invocation.execution
        );
        let app = axum::Router::new().route(
            &route,
            axum::routing::get(move || async move { Json(payload) }),
        );
        let task = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        assert!(
            remote_status(&client, &invocation)
                .await
                .unwrap()
                .writer_active
        );
        // The standalone registry is empty and MUST NOT supply server proof.
        assert!(!services::services::execution_process::capture_in_progress(
            invocation.execution
        ));
        let wrong = Invocation {
            execution: MM.parse().unwrap(),
            ..invocation
        };
        assert!(remote_status(&client, &wrong).await.is_err());
        task.abort();
        assert!(remote_status(&client, &wrong).await.is_err());
    }
}
