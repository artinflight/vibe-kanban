use axum::{
    Router,
    extract::DefaultBodyLimit,
    routing::{get, post},
};
use sqlx::sqlite::SqlitePoolOptions;

use super::*;

include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/tests/fixtures/review_storage_root.rs"
));

// Sanitized shapes of the actual T18/MM Oct10 native records. No private
// prompts, reasoning, tool payloads or credentials enter this public fixture.
struct Fixture {
    home: tempfile::TempDir,
    process: ExecutionProcess,
    request: RecoveryRequest,
    source: PathBuf,
    capture: PathBuf,
    records: Vec<Value>,
}
impl Fixture {
    fn new() -> Self {
        assert_fixture_root();
        let home = tempfile::tempdir_in(utils::assets::asset_dir()).unwrap();
        let execution = Uuid::new_v4();
        let session = Uuid::new_v4();
        let native = Uuid::new_v4();
        let turn = Uuid::new_v4();
        let at = |s: &str| DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc);
        let process: ExecutionProcess = serde_json::from_value(json!({"id":execution,"session_id":session,
            "run_reason":"codingagent","status":"completed","exit_code":0,"dropped":false,
            "executor_action":{"typ":{"type":"CodingAgentFollowUpRequest","prompt":"Original exact owner prompt","session_id":native,"reset_to_message_id":null,"executor_config":{"executor":"CODEX"}},"next_action":null},
            "created_at":"2026-10-10T11:00:21Z","started_at":"2026-10-10T11:00:21Z",
            "updated_at":"2026-10-10T11:00:21Z","completed_at":"2026-10-10T11:41:24Z"})).unwrap();
        let records = vec![
            json!({"timestamp":"2026-10-08T10:25:41Z","type":"session_meta","payload":{"id":native,"cwd":"fixture","source":"vibe"}}),
            json!({"timestamp":"2026-10-10T11:00:37.779Z","type":"event_msg","payload":{"type":"task_started","turn_id":turn,"root_turn_id":turn,"started_at":1791630037,"collaboration_mode_kind":"default"}}),
            json!({"timestamp":"2026-10-10T11:00:37.780Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Vibe instructions\n\nOriginal exact owner prompt"}]}}),
            json!({"timestamp":"2026-10-10T11:05:00Z","type":"world_state","payload":{"fixture":"native state format"}}),
            json!({"timestamp":"2026-10-10T11:06:00Z","type":"compacted","payload":{"message":"sanitized MM compacted history","replacement_history":[]}}),
            json!({"timestamp":"2026-10-10T11:06:01Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"sanitized compaction context"}]}}),
            json!({"timestamp":"2026-10-10T11:41:20.806Z","type":"response_item","payload":{"type":"message","role":"assistant","phase":"final_answer","id":"authentic-fixture-item","content":[{"type":"output_text","text":"Genuine fixture final — café. Work remains incomplete."}]}}),
            json!({"timestamp":"2026-10-10T11:41:20.907Z","type":"event_msg","payload":{"type":"task_complete","turn_id":turn,"last_agent_message":"Genuine fixture final — café. Work remains incomplete.","started_at":1791630037,"completed_at":1791632480,"duration_ms":2443127}}),
        ];
        let dir = home.path().join("sessions/2026/10/08");
        fs::create_dir_all(&dir).unwrap();
        let source = dir.join(format!("rollout-2026-10-08T10-25-41-{native}.jsonl"));
        let capture = utils::execution_logs::process_log_file_path(session, execution);
        fs::create_dir_all(capture.parent().unwrap()).unwrap();
        fs::write(&capture, b"{\"Stdout\":\"incomplete original prefix\"}\n").unwrap();
        let request = RecoveryRequest {
            workspace_id: Uuid::new_v4(),
            session_id: session,
            execution_revision: at("2026-10-10T11:00:21Z"),
            native_session_id: native,
            native_turn_id: turn,
            source_prefix_bytes: 1,
            source_prefix_sha256: String::new(),
            original_capture_sha256: bounded_file_hash(&capture).unwrap(),
            prompt_sha256: sha(b"Original exact owner prompt"),
            reply_sha256: sha("Genuine fixture final — café. Work remains incomplete.".as_bytes()),
        };
        let mut this = Self {
            home,
            process,
            request,
            source,
            capture,
            records,
        };
        this.rewrite();
        this
    }
    fn rewrite(&mut self) {
        let mut bytes = Vec::new();
        for record in &self.records {
            bytes.extend(serde_json::to_vec(record).unwrap());
            bytes.push(b'\n');
        }
        fs::write(&self.source, &bytes).unwrap();
        self.request.source_prefix_bytes = bytes.len() as u64;
        self.request.source_prefix_sha256 = sha(&bytes);
    }
    fn recover(&self) -> RecoveryResult<RecoveredFinal> {
        recover(
            &self.process,
            &self.request,
            self.home.path(),
            &self.capture,
        )
    }
    async fn pool(&self) -> sqlx::SqlitePool {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
        sqlx::query(
            "INSERT INTO workspaces(id,branch,name) VALUES (?,'fixture','Recovery fixture')",
        )
        .bind(self.request.workspace_id)
        .execute(&pool)
        .await
        .unwrap();
        sqlx::query("INSERT INTO sessions(id,workspace_id,executor) VALUES (?,?,'CODEX')")
            .bind(self.process.session_id)
            .bind(self.request.workspace_id)
            .execute(&pool)
            .await
            .unwrap();
        let p = &self.process;
        sqlx::query("INSERT INTO execution_processes(id,session_id,run_reason,executor_action,status,exit_code,started_at,completed_at,created_at,updated_at) VALUES (?,?,'codingagent',?,'completed',0,?,?,?,?)")
            .bind(p.id).bind(p.session_id).bind(serde_json::to_string(&p.executor_action).unwrap()).bind(p.started_at).bind(p.completed_at).bind(p.created_at).bind(p.updated_at).execute(&pool).await.unwrap();
        pool
    }
}

#[test]
fn authentic_historical_final_bound_to_original_prompt_turn_and_timestamp() {
    let f = Fixture::new();
    let r = f.recover().unwrap();
    assert_eq!(r.evidence, f.request);
    assert_eq!(r.final_line, 7);
    assert_eq!(r.closure_line, 8);
    assert_eq!(
        r.native_message_id.as_deref(),
        Some("authentic-fixture-item")
    );
    assert_eq!(r.final_at.to_rfc3339(), "2026-10-10T11:41:20.806+00:00");
    assert!(r.text.contains("Work remains incomplete"));
}

#[test]
fn incorrect_identity_revision_hash_and_running_execution_fail_closed() {
    let f = Fixture::new();
    for kind in 0..9 {
        let mut p = f.process.clone();
        let mut r = f.request.clone();
        match kind {
            0 => r.native_session_id = Uuid::new_v4(),
            1 => r.native_turn_id = Uuid::new_v4(),
            2 => r.session_id = Uuid::new_v4(),
            3 => r.execution_revision += chrono::Duration::seconds(1),
            4 => r.prompt_sha256 = sha(b"wrong"),
            5 => r.reply_sha256 = sha(b"wrong"),
            6 => r.source_prefix_sha256 = sha(b"wrong"),
            7 => p.status = ExecutionProcessStatus::Running,
            _ => p.dropped = true,
        }
        assert!(
            recover(&p, &r, f.home.path(), &f.capture).is_err(),
            "accepted incorrect binding {kind}"
        );
    }
}

#[test]
fn damaged_entries_even_before_target_and_incomplete_or_conflicting_turns_rejected() {
    for kind in 0..6 {
        let mut f = Fixture::new();
        match kind {
            0 => {
                fs::write(&f.source, b"damaged historical record\n").unwrap();
                f.request.source_prefix_bytes = 26;
                f.request.source_prefix_sha256 = sha(b"damaged historical record\n");
            }
            1 => {
                f.records.pop();
                f.rewrite();
            }
            2 => {
                f.records.push(f.records[6].clone());
                f.rewrite();
            }
            3 => {
                f.records[7]["payload"]["last_agent_message"] = json!("different");
                f.rewrite();
            }
            4 => {
                f.records.push(f.records[1].clone());
                f.rewrite();
            }
            _ => {
                let mut bytes = fs::read(&f.source).unwrap();
                bytes.pop();
                fs::write(&f.source, &bytes).unwrap();
                f.request.source_prefix_bytes = bytes.len() as u64;
                f.request.source_prefix_sha256 = sha(&bytes);
            }
        }
        assert!(
            f.recover().is_err(),
            "accepted damaged/ambiguous fixture {kind}"
        );
    }
}

#[test]
fn append_only_subsequent_work_preserved_but_changed_prefix_and_capture_refused() {
    let f = Fixture::new();
    let record = f.recover().unwrap();
    save(&f.capture, &record).unwrap();
    let mut later = OpenOptions::new().append(true).open(&f.source).unwrap();
    writeln!(later,"{}",json!({"timestamp":"2026-10-10T12:00:00Z","type":"event_msg","payload":{"type":"task_started","turn_id":Uuid::new_v4()}})).unwrap();
    assert_eq!(f.recover().unwrap(), record);
    fs::write(&f.capture, b"changed original").unwrap();
    assert!(f.recover().is_err());
    fs::write(&f.capture, b"{\"Stdout\":\"incomplete original prefix\"}\n").unwrap();
    let mut bytes = fs::read(&f.source).unwrap();
    bytes[0] = b' ';
    fs::write(&f.source, bytes).unwrap();
    assert!(f.recover().is_err());
}

#[test]
fn idempotent_concurrent_publication_restart_and_conflicting_retry() {
    let f = Fixture::new();
    let r = f.recover().unwrap();
    let results = std::thread::scope(|s| {
        let jobs = (0..4)
            .map(|_| s.spawn(|| save(&f.capture, &r).unwrap()))
            .collect::<Vec<_>>();
        jobs.into_iter()
            .map(|j| j.join().unwrap())
            .collect::<Vec<_>>()
    });
    assert_eq!(results.into_iter().filter(|created| *created).count(), 1);
    assert_eq!(load_record(&record_path(&f.capture)).unwrap(), r);
    assert!(!save(&f.capture, &r).unwrap());
    let mut conflicting = r.clone();
    conflicting.text.push_str(" fabricated");
    assert!(save(&f.capture, &conflicting).is_err());
    assert_eq!(
        bounded_file_hash(&f.capture).unwrap(),
        f.request.original_capture_sha256
    );
    assert!(!f.capture.with_extension("capture.json").exists());
}

#[cfg(unix)]
#[test]
fn path_symlink_collision_and_resource_limits_fail_closed() {
    let mut f = Fixture::new();
    let duplicate = f.source.with_file_name(format!(
        "rollout-duplicate-{}.jsonl",
        f.request.native_session_id
    ));
    fs::copy(&f.source, &duplicate).unwrap();
    assert!(f.recover().is_err());
    fs::remove_file(&duplicate).unwrap();
    let outside = f.home.path().join("outside.jsonl");
    fs::rename(&f.source, &outside).unwrap();
    std::os::unix::fs::symlink(&outside, &f.source).unwrap();
    assert!(f.recover().is_err());
    fs::remove_file(&f.source).unwrap();
    fs::rename(outside, &f.source).unwrap();
    f.request.source_prefix_bytes = MAX_SOURCE_BYTES + 1;
    assert!(f.recover().is_err());
    let mut value = serde_json::to_value(&f.request).unwrap();
    value["source_path"] = json!("/arbitrary");
    assert!(serde_json::from_value::<RecoveryRequest>(value).is_err());
}

#[derive(Clone)]
struct HttpFixture {
    pool: sqlx::SqlitePool,
    home: PathBuf,
    process: ExecutionProcess,
}
async fn import_http(
    State(f): State<HttpFixture>,
    auth: Option<Extension<RelayRequestSignatureContext>>,
    Json(r): Json<RecoveryRequest>,
) -> Result<Json<utils::response::ApiResponse<Value>>, ApiError> {
    authorize(auth)?;
    import_verified(f.process, &f.pool, f.home, r).await
}
async fn history_http(
    State(f): State<HttpFixture>,
) -> Result<Json<utils::response::ApiResponse<super::super::log_history::HistoryPage>>, ApiError> {
    let page = read_verified(&f.process, &f.pool, None, f.home)
        .await?
        .unwrap_or(super::super::log_history::HistoryPage {
            entries: vec![],
            next_before: None,
            capture_error: Some("Incomplete original capture"),
            capture_pending: false,
            recovery_notice: None,
        });
    Ok(Json(utils::response::ApiResponse::success(page)))
}

#[tokio::test]
async fn existing_signed_auth_binds_recovery_arguments_and_prevents_nonce_replay() {
    use relay_control::signing::RelaySigningService;
    // In-memory disposable fixture keys; never reads or alters a host credential.
    let server = RelaySigningService::new(ed25519_dalek::SigningKey::from_bytes(&[1; 32]));
    let client = RelaySigningService::new(ed25519_dalek::SigningKey::from_bytes(&[2; 32]));
    let session = server.create_session(client.server_public_key()).await;
    let f = Fixture::new();
    let body = serde_json::to_vec(&f.request).unwrap();
    let path = format!(
        "/api/execution-processes/{}/recover-native-final",
        f.process.id
    );
    let signature = client.sign_request(session, "POST", &path, &body);
    assert!(
        server
            .verify_request(&signature, "POST", &path, b"changed arguments")
            .await
            .is_err()
    );
    assert!(
        server
            .verify_request(&signature, "POST", "/different-execution", &body)
            .await
            .is_err()
    );
    server
        .verify_request(&signature, "POST", &path, &body)
        .await
        .unwrap();
    authorize(Some(Extension(signature.clone()))).unwrap();
    assert!(
        server
            .verify_request(&signature, "POST", &path, &body)
            .await
            .is_err()
    );
    assert!(authorize(None).is_err());
}

#[tokio::test]
async fn actual_http_recovery_normal_reader_and_restart_preserve_all_database_rows() {
    let f = Fixture::new();
    let pool = f.pool().await;
    let before = sqlx::query_scalar::<_, String>("SELECT executor_action FROM execution_processes")
        .fetch_one(&pool)
        .await
        .unwrap();
    let ctx = HttpFixture {
        pool: pool.clone(),
        home: f.home.path().to_owned(),
        process: f.process.clone(),
    };
    // Positive fixture represents the extension installed ONLY after the existing
    // relay verifier. This test does not claim a production login/signing roundtrip.
    let verified = RelayRequestSignatureContext {
        signing_session_id: Uuid::new_v4(),
        timestamp: 1,
        nonce: Uuid::new_v4(),
        signature_b64: "verified disposable fixture".into(),
    };
    let app = Router::new()
        .route(
            "/recover-native-final",
            post(import_http).layer(Extension(verified.clone())),
        )
        .route("/unsigned", post(import_http))
        .route("/log-history", get(history_http))
        .layer(DefaultBodyLimit::max(8192))
        .with_state(ctx.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    let job = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .unwrap();
    assert_eq!(
        client
            .post(format!("{base}/unsigned"))
            .json(&f.request)
            .send()
            .await
            .unwrap()
            .status(),
        401
    );
    assert!(!record_path(&f.capture).exists());
    let mut wrong = f.request.clone();
    wrong.workspace_id = Uuid::new_v4();
    assert_eq!(
        client
            .post(format!("{base}/recover-native-final"))
            .json(&wrong)
            .send()
            .await
            .unwrap()
            .status(),
        409
    );
    let body: Value = client
        .post(format!("{base}/recover-native-final"))
        .json(&f.request)
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert_eq!(body["data"]["created"], true);
    assert_eq!(body["data"]["review_certified"], false);
    let body: Value = client
        .post(format!("{base}/recover-native-final"))
        .json(&f.request)
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert_eq!(body["data"]["created"], false);
    let history: Value = client
        .get(format!("{base}/log-history"))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert_eq!(
        history["data"]["entries"][0]["entry"]["content"]["content"],
        "Genuine fixture final — café. Work remains incomplete."
    );
    assert_eq!(
        history["data"]["entries"][0]["entry"]["content"]["timestamp"],
        "2026-10-10T11:41:20.806+00:00"
    );
    assert!(
        history["data"]["recovery_notice"]
            .as_str()
            .unwrap()
            .contains("incomplete")
    );
    // New reader state (no in-memory history cache), same persisted sidecar.
    assert!(
        read_verified(&ctx.process, &pool, None, ctx.home.clone())
            .await
            .unwrap()
            .is_some()
    );
    assert_eq!(
        sqlx::query_scalar::<_, String>("SELECT executor_action FROM execution_processes")
            .fetch_one(&pool)
            .await
            .unwrap(),
        before
    );
    for table in [
        "workspace_review_log_finalized",
        "workspace_review_receipts",
        "workspace_review_hold_events",
        "coding_agent_turns",
    ] {
        let count = sqlx::query_scalar::<_, i64>(&format!("SELECT COUNT(*) FROM {table}"))
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(count, 0);
    }
    let mut unrelated = f.process.clone();
    unrelated.id = Uuid::new_v4();
    assert!(
        read_verified(&unrelated, &pool, None, ctx.home)
            .await
            .unwrap()
            .is_none()
    );
    assert_eq!(
        bounded_file_hash(&f.capture).unwrap(),
        f.request.original_capture_sha256
    );
    assert!(
        utils::execution_logs::validate_native_capture(&f.capture, MAX_SOURCE_BYTES as usize)
            .await
            .is_err()
    );
    // No foreign keys/rows introduced: normal execution deletion remains valid.
    sqlx::query("DELETE FROM execution_processes WHERE id=?")
        .bind(f.process.id)
        .execute(&pool)
        .await
        .unwrap();
    assert!(
        read_verified(&f.process, &pool, None, f.home.path().to_owned())
            .await
            .unwrap()
            .is_none()
    );
    job.abort();
}
