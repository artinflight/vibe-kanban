//! Actual Axum handlers + native normalizer/storage writer + real SQLite on SSD.
//! No Deployment::new, agent launch, production config, auth or live badges.
use std::{path::PathBuf, sync::Arc, time::Duration};

use axum::{
    Router,
    routing::{get, post, put},
};
use db::models::coding_agent_turn::CodingAgentTurn;
use futures_util::StreamExt;
use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions};
use tokio::sync::Notify;
use utils::{assets::asset_dir, msg_store::MsgStore};

use super::*;

include!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/tests/fixtures/review_storage_root.rs"
));

#[derive(Clone)]
struct Fixture {
    pool: SqlitePool,
    before_mark: Option<Arc<(Notify, Notify)>>,
}
impl ReviewBackend for Fixture {
    fn pool(&self) -> &SqlitePool {
        &self.pool
    }
    async fn fingerprint(&self, process: &ExecutionProcess) -> Result<(usize, String), ApiError> {
        let messages =
            services::services::report_review::replay_review_log(&self.pool, process, &asset_dir())
                .await
                .map_err(|e| ApiError::Conflict(format!("Strict durable replay rejected: {e}")))?;
        let result =
            crate::routes::execution_processes::log_history::fingerprint_review_messages(messages)
                .map_err(|e| *e)?;
        if let Some(gate) = &self.before_mark {
            gate.0.notify_one();
            gate.1.notified().await;
        }
        Ok(result)
    }
}
struct App {
    context: Fixture,
    workspace: Workspace,
    session: Uuid,
    execution: Uuid,
    revision: String,
    database: PathBuf,
}
impl App {
    async fn new() -> Self {
        let app = Self::unwritten().await;
        app.write_log().await;
        app
    }
    async fn unwritten() -> Self {
        assert_fixture_root();
        let database = asset_dir().join(format!("review-http-{}.sqlite", Uuid::new_v4()));
        let pool = Self::connect(&database).await;
        sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
        let wid = Uuid::new_v4();
        let session = Uuid::new_v4();
        let execution = Uuid::new_v4();
        sqlx::query("INSERT INTO workspaces(id,branch,name) VALUES (?,'fixture','Disposable report fixture')")
            .bind(wid).execute(&pool).await.unwrap();
        sqlx::query("INSERT INTO sessions(id,workspace_id,executor) VALUES (?,?,'CODEX')")
            .bind(session)
            .bind(wid)
            .execute(&pool)
            .await
            .unwrap();
        let revision = "2026-10-07T10:01:00Z".to_string();
        let action = json!({"typ":{"type":"CodingAgentInitialRequest","prompt":"disposable test report","executor_config":{"executor":"CODEX"}},"next_action":null});
        sqlx::query("INSERT INTO execution_processes(id,session_id,run_reason,executor_action,status,exit_code,created_at,started_at,completed_at,updated_at) VALUES (?,?,'codingagent',?,'completed',0,'2026-10-07T10:00:00Z','2026-10-07T10:00:00Z',?,?)")
            .bind(execution).bind(session).bind(action.to_string()).bind(&revision).bind(&revision).execute(&pool).await.unwrap();
        sqlx::query("INSERT INTO coding_agent_turns(id,execution_process_id,summary,seen,updated_at) VALUES (?,?,'Fixture report',0,?)")
            .bind(Uuid::new_v4()).bind(execution).bind(&revision).execute(&pool).await.unwrap();
        let workspace = Workspace::find_by_id(&pool, wid).await.unwrap().unwrap();
        let context = Fixture {
            pool,
            before_mark: None,
        };
        Self {
            context,
            workspace,
            session,
            execution,
            revision,
            database,
        }
    }
    async fn connect(path: &std::path::Path) -> SqlitePool {
        SqlitePoolOptions::new()
            .max_connections(4)
            .connect_with(
                SqliteConnectOptions::new()
                    .filename(path)
                    .create_if_missing(true)
                    .foreign_keys(true)
                    .journal_mode(SqliteJournalMode::Wal)
                    .busy_timeout(Duration::from_secs(5)),
            )
            .await
            .unwrap()
    }
    async fn write_log(&self) {
        let store = Arc::new(MsgStore::new());
        // Valid native final report; split across raw stdout chunks to exercise
        // real reconstruction rather than per-chunk JSON parsing.
        let event = include_str!("../../../../executors/src/executors/codex/fixtures/review-goal-sleep.jsonl").to_string()
            + &json!({"method":"codex/event/agent_message","params":{"msg":{"type":"agent_message","message":"Fixture report"}}}).to_string() + "\n";
        store.push_stdout(&event[..17]);
        store.push_stdout(&event[17..]);
        store.push_finished();
        services::services::execution_process::spawn_stream_raw_logs_to_storage(
            store,
            db::DBService {
                pool: self.context.pool.clone(),
            },
            self.execution,
            self.session,
        )
        .await
        .unwrap();
    }
    fn receipt(&self, channel: &str) -> Value {
        json!({"workspace_id":self.workspace.id,"execution_id":self.execution,"session_id":self.session,
        "message_index":0,"reply_sha256":sha("Fixture report"),"hash_version":"utf8-sha256-v1",
        "execution_revision":self.revision,"disposition":"handled","intent_version":0,
        "receipt_id":sha(&format!("fixture:{}:{channel}",self.execution)),
        "source":{"actor":"root","channel":channel,"event_id":format!("fixture-{}-{channel}",self.execution),
        "evidence":"DISPOSABLE isolated test receipt, never user evidence"}})
    }
    async fn serve(&self) -> (String, tokio::task::JoinHandle<()>) {
        let base = format!("/api/workspaces/{}", self.workspace.id);
        let app = Router::new()
            .route(&(base.clone() + "/review-state"), get(state::<Fixture>))
            .route(
                &(base.clone() + "/review-receipts"),
                post(receipt::<Fixture>),
            )
            .route(&(base.clone() + "/review-hold"), put(hold::<Fixture>))
            .layer(Extension(self.workspace.clone()))
            .with_state(self.context.clone());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let url = format!("http://{}{}", listener.local_addr().unwrap(), base);
        let job = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        (url, job)
    }
    async fn unread(&self) -> bool {
        CodingAgentTurn::find_workspaces_with_unseen(&self.context.pool, false)
            .await
            .unwrap()
            .contains(&self.workspace.id)
    }
    async fn add_activity(&self, status: &str) -> Uuid {
        let session = Uuid::new_v4();
        let ep = Uuid::new_v4();
        sqlx::query("INSERT INTO sessions(id,workspace_id) VALUES (?,?)")
            .bind(session)
            .bind(self.workspace.id)
            .execute(&self.context.pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO execution_processes(id,session_id,run_reason,status,created_at,completed_at,updated_at) VALUES (?,?,'codingagent',?,'2026-10-07T11:00:00Z',?,'2026-10-07T11:01:00Z')")
            .bind(ep).bind(session).bind(status).bind(if status=="completed" {Some("2026-10-07T11:01:00Z")} else {None}).execute(&self.context.pool).await.unwrap();
        sqlx::query("INSERT INTO coding_agent_turns(id,execution_process_id,summary,seen) VALUES (?,?,'New unreported report',0)")
            .bind(Uuid::new_v4()).bind(ep).execute(&self.context.pool).await.unwrap();
        ep
    }
}
async fn post_receipt(url: &str, body: &Value) -> (u16, Value) {
    let response = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .unwrap()
        .post(format!("{url}/review-receipts"))
        .json(body)
        .send()
        .await
        .unwrap();
    let status = response.status().as_u16();
    (status, response.json().await.unwrap())
}
async fn set_hold(app: &App, url: &str) {
    let body = json!({"held":true,"event_id":"explicit-hold","expected_intent_version":0,"source":{"actor":"root","channel":"voice","event_id":"leave-unread","evidence":"DISPOSABLE fixture manual hold"}});
    let response = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .unwrap()
        .put(format!("{url}/review-hold"))
        .json(&body)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status().as_u16(), 200);
    assert!(app.unread().await);
}

#[tokio::test]
async fn http_voice_chat_receipt_conditional_mark_and_restart_duplicate_recovery() {
    for channel in ["voice", "chat"] {
        let mut app = App::new().await;
        let unrelated = App::new().await;
        // Put unrelated workspace in the SAME database, with its own unread turn.
        sqlx::query("INSERT INTO workspaces(id,branch,name) VALUES (?,'other','Untouched')")
            .bind(unrelated.workspace.id)
            .execute(&app.context.pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO sessions(id,workspace_id) VALUES (?,?)")
            .bind(unrelated.session)
            .bind(unrelated.workspace.id)
            .execute(&app.context.pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO execution_processes(id,session_id) VALUES (?,?)")
            .bind(unrelated.execution)
            .bind(unrelated.session)
            .execute(&app.context.pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO coding_agent_turns(id,execution_process_id,summary,seen) VALUES (?,?,'Unrelated',0)").bind(Uuid::new_v4()).bind(unrelated.execution).execute(&app.context.pool).await.unwrap();
        let (url, job) = app.serve().await;
        assert!(app.unread().await);
        let body = app.receipt(channel);
        let (status, result) = post_receipt(&url, &body).await;
        assert_eq!(status, 200, "{result}");
        assert_eq!(result["data"]["status"], "applied");
        assert!(!app.unread().await);
        assert!(
            CodingAgentTurn::find_workspaces_with_unseen(&app.context.pool, false)
                .await
                .unwrap()
                .contains(&unrelated.workspace.id)
        );
        job.abort();
        job.await.unwrap_err();
        app.context.pool.close().await;
        // Reopen persistent DB and server. A duplicate cannot clear manual unread.
        app.context.pool = App::connect(&app.database).await;
        manual_intent(&app.context, app.workspace.id, false)
            .await
            .unwrap();
        let (url, job) = app.serve().await;
        let (status, result) = post_receipt(&url, &body).await;
        assert_eq!(status, 200, "{result}");
        assert_eq!(result["data"]["status"], "already_applied");
        assert!(app.unread().await);
        let state = reqwest::get(format!("{url}/review-state"))
            .await
            .unwrap()
            .json::<Value>()
            .await
            .unwrap();
        assert_eq!(state["data"]["held"], true);
        let mut reused = body.clone();
        reused["source"]["evidence"] = json!("changed event payload");
        assert_eq!(post_receipt(&url, &reused).await.0, 409);
        job.abort();
        job.await.unwrap_err();
    }
}
#[tokio::test]
async fn http_rejects_newer_completed_or_running_other_session() {
    for status in ["completed", "running"] {
        let app = App::new().await;
        app.add_activity(status).await;
        let (url, job) = app.serve().await;
        let (status, result) = post_receipt(&url, &app.receipt("voice")).await;
        assert_eq!(status, 409, "{result}");
        assert!(app.unread().await);
        job.abort();
        job.await.unwrap_err();
    }
}
#[tokio::test]
async fn http_held_report_and_hold_added_during_verification_fail_closed() {
    for racing in [false, true] {
        let mut app = App::new().await;
        let gate = Arc::new((Notify::new(), Notify::new()));
        if racing {
            app.context.before_mark = Some(gate.clone());
        }
        let (url, job) = app.serve().await;
        let receipt = app.receipt("voice");
        let pending = if racing {
            let url = url.clone();
            let body = receipt.clone();
            let request = tokio::spawn(async move { post_receipt(&url, &body).await });
            tokio::time::timeout(Duration::from_secs(5), gate.0.notified())
                .await
                .unwrap();
            Some(request)
        } else {
            None
        };
        set_hold(&app, &url).await;
        let result = if let Some(pending) = pending {
            gate.1.notify_one();
            pending.await.unwrap()
        } else {
            post_receipt(&url, &receipt).await
        };
        assert_eq!(result.0, 409, "{:?}", result.1);
        assert!(app.unread().await);
        job.abort();
        job.await.unwrap_err();
    }
}
#[tokio::test]
async fn http_new_reply_races_before_mark_and_after_mark_stays_unread() {
    for before in [false, true] {
        let mut app = App::new().await;
        let gate = Arc::new((Notify::new(), Notify::new()));
        if before {
            app.context.before_mark = Some(gate.clone());
        }
        let (url, job) = app.serve().await;
        let receipt = app.receipt("chat");
        if before {
            let target = url.clone();
            let body = receipt.clone();
            let request = tokio::spawn(async move { post_receipt(&target, &body).await });
            tokio::time::timeout(Duration::from_secs(5), gate.0.notified())
                .await
                .unwrap();
            sqlx::query("UPDATE coding_agent_turns SET summary='New changed reply',updated_at='2026-10-07T11:05:00Z' WHERE execution_process_id=?")
                .bind(app.execution).execute(&app.context.pool).await.unwrap();
            gate.1.notify_one();
            assert_eq!(request.await.unwrap().0, 409);
        } else {
            assert_eq!(post_receipt(&url, &receipt).await.0, 200);
            assert!(!app.unread().await);
            app.add_activity("completed").await;
            // Old duplicate returns old proof, without consuming the new turn.
            assert_eq!(post_receipt(&url, &receipt).await.0, 200);
        }
        assert!(app.unread().await);
        job.abort();
        job.await.unwrap_err();
    }
}
#[tokio::test]
async fn http_missing_closure_wrong_identity_and_damaged_log_never_mark() {
    for damage in [
        "missing",
        "missing-file",
        "wrong-index",
        "malformed",
        "removed-valid-line",
        "partial",
    ] {
        let app = App::new().await;
        let mut receipt = app.receipt("voice");
        let path = utils::execution_logs::process_log_file_path(app.session, app.execution);
        match damage {
            "missing" => {
                sqlx::query("DELETE FROM workspace_review_log_finalized WHERE execution_id=?")
                    .bind(app.execution)
                    .execute(&app.context.pool)
                    .await
                    .unwrap();
            }
            "missing-file" => {
                tokio::fs::remove_file(&path).await.unwrap();
            }
            "wrong-index" => receipt["message_index"] = json!(99),
            "malformed" => {
                let mut bytes = tokio::fs::read(&path).await.unwrap();
                bytes.extend_from_slice(b"broken JSON\n");
                tokio::fs::write(&path, bytes).await.unwrap();
            }
            "removed-valid-line" => {
                let bytes = tokio::fs::read_to_string(&path).await.unwrap();
                tokio::fs::write(
                    &path,
                    bytes.lines().skip(1).collect::<Vec<_>>().join("\n") + "\n",
                )
                .await
                .unwrap();
            }
            "partial" => {
                let mut bytes = tokio::fs::read(&path).await.unwrap();
                bytes.pop();
                tokio::fs::write(&path, bytes).await.unwrap();
            }
            _ => unreachable!(),
        }
        let (url, job) = app.serve().await;
        assert_eq!(post_receipt(&url, &receipt).await.0, 409, "{damage}");
        assert!(app.unread().await);
        job.abort();
        job.await.unwrap_err();
    }
}
#[tokio::test]
async fn lifecycle_deletion_cascades_projection_but_preserves_receipt_audit() {
    let app = App::new().await;
    let (url, job) = app.serve().await;
    assert_eq!(post_receipt(&url, &app.receipt("voice")).await.0, 200);
    sqlx::query("INSERT INTO workspace_review_hold_events VALUES (?,'fixture-hold',1,'fixture')")
        .bind(app.workspace.id)
        .execute(&app.context.pool)
        .await
        .unwrap();
    sqlx::query("DELETE FROM execution_processes WHERE id=?")
        .bind(app.execution)
        .execute(&app.context.pool)
        .await
        .unwrap();
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM workspace_review_log_finalized")
        .fetch_one(&app.context.pool)
        .await
        .unwrap();
    assert_eq!(count, 0);
    sqlx::query("DELETE FROM workspaces WHERE id=?")
        .bind(app.workspace.id)
        .execute(&app.context.pool)
        .await
        .unwrap();
    for table in ["workspace_review_intent", "workspace_review_hold_events"] {
        let count: i64 = sqlx::query_scalar(&format!("SELECT COUNT(*) FROM {table}"))
            .fetch_one(&app.context.pool)
            .await
            .unwrap();
        assert_eq!(count, 0);
    }
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_receipts WHERE workspace_id=? AND execution_id=?",
    )
    .bind(app.workspace.id)
    .bind(app.execution)
    .fetch_one(&app.context.pool)
    .await
    .unwrap();
    assert_eq!(count, 1);
    let violations = sqlx::query("PRAGMA foreign_key_check")
        .fetch_all(&app.context.pool)
        .await
        .unwrap();
    assert!(violations.is_empty());
    job.abort();
    job.await.unwrap_err();
}

#[tokio::test]
async fn http_hold_restart_and_out_of_order_events_preserve_latest_intent() {
    let mut app = App::new().await;
    let (url, job) = app.serve().await;
    set_hold(&app, &url).await;
    job.abort();
    job.await.unwrap_err();
    app.context.pool.close().await;
    app.context.pool = App::connect(&app.database).await;
    let (url, job) = app.serve().await;
    assert_eq!(post_receipt(&url, &app.receipt("voice")).await.0, 409);
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .unwrap();
    let old = json!({"held":true,"event_id":"explicit-hold","expected_intent_version":0,"source":{"actor":"root","channel":"voice","event_id":"leave-unread","evidence":"DISPOSABLE fixture manual hold"}});
    let release = json!({"held":false,"event_id":"explicit-release","expected_intent_version":1,"source":{"actor":"root","channel":"voice","event_id":"release","evidence":"DISPOSABLE fixture release"}});
    assert_eq!(
        client
            .put(format!("{url}/review-hold"))
            .json(&release)
            .send()
            .await
            .unwrap()
            .status()
            .as_u16(),
        200
    );
    let response = client
        .put(format!("{url}/review-hold"))
        .json(&old)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status().as_u16(), 200);
    let current = response.json::<Value>().await.unwrap();
    assert_eq!(current["data"]["held"], false);
    assert_eq!(current["data"]["intent_version"], 2);
    // A never-applied old delivery cannot consume a reply after release.
    assert_eq!(post_receipt(&url, &app.receipt("voice")).await.0, 409);
    assert!(app.unread().await);
    job.abort();
    job.await.unwrap_err();
}

// Compatibility read routes only for the Python connector acceptance fixture.
// Data is read from the real disposable DB and the actual strict native replay;
// mutation uses the exact production review handler above, never a fake backend.
async fn fixture_execution(
    State(c): State<Fixture>,
    axum::extract::Path(id): axum::extract::Path<Uuid>,
) -> Json<ApiResponse<Value>> {
    let process = ExecutionProcess::find_by_id(&c.pool, id)
        .await
        .unwrap()
        .unwrap();
    Json(ApiResponse::success(serde_json::to_value(process).unwrap()))
}
async fn fixture_session(
    State(c): State<Fixture>,
    axum::extract::Path(id): axum::extract::Path<Uuid>,
) -> Json<ApiResponse<Value>> {
    let wid: Uuid = sqlx::query_scalar("SELECT workspace_id FROM sessions WHERE id=?")
        .bind(id)
        .fetch_one(&c.pool)
        .await
        .unwrap();
    Json(ApiResponse::success(json!({"id":id,"workspace_id":wid})))
}
async fn fixture_history(
    State(c): State<Fixture>,
    axum::extract::Path(id): axum::extract::Path<Uuid>,
) -> Result<Json<ApiResponse<Value>>, ApiError> {
    let process = ExecutionProcess::find_by_id(&c.pool, id)
        .await
        .unwrap()
        .unwrap();
    if process.status == ExecutionProcessStatus::Running {
        return Err(ApiError::Conflict(
            "Running logs must use the live stream".into(),
        ));
    }
    if let Some(page) =
        crate::routes::execution_processes::log_history::capture_page_for_process(&c.pool, &process)
            .await
            .unwrap()
    {
        return Ok(Json(ApiResponse::success(
            serde_json::to_value(page).unwrap(),
        )));
    }
    let messages =
        services::services::report_review::replay_review_log(&c.pool, &process, &asset_dir())
            .await
            .unwrap();
    let mut entries = std::collections::BTreeMap::new();
    for message in messages {
        if let utils::log_msg::LogMsg::JsonPatch(patch) = message {
            for op in patch.0 {
                match op {
                    json_patch::PatchOperation::Add(op) => {
                        entries.insert(op.path.to_string(), op.value);
                    }
                    json_patch::PatchOperation::Replace(op) => {
                        entries.insert(op.path.to_string(), op.value);
                    }
                    _ => panic!("Unexpected fixture patch"),
                }
            }
        }
    }
    let entries:Vec<Value>=entries.into_iter().map(|(path,entry)|json!({"index":path.strip_prefix("/entries/").unwrap().parse::<usize>().unwrap(),"entry":entry})).collect();
    Ok(Json(ApiResponse::success(
        json!({"entries":entries,"next_before":null,"capture_pending":false}),
    )))
}
async fn fixture_summaries(State(c): State<Fixture>) -> Json<ApiResponse<Value>> {
    let unread = CodingAgentTurn::find_workspaces_with_unseen(&c.pool, false)
        .await
        .unwrap();
    let ids: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM workspaces WHERE archived=0")
        .fetch_all(&c.pool)
        .await
        .unwrap();
    let summaries: Vec<Value> = ids
        .into_iter()
        .map(|id| json!({"workspace_id":id,"has_unseen_turns":unread.contains(&id)}))
        .collect();
    Json(ApiResponse::success(json!({"summaries":summaries})))
}
#[tokio::test]
#[ignore = "MCP-only installed connector acceptance; run explicitly on mounted SSD"]
async fn installed_connector_tool_receipt_to_real_http_conditional_mark_readback() {
    let app = App::new().await;
    let router = Router::new()
        .route("/api/execution-processes/{id}", get(fixture_execution))
        .route(
            "/api/execution-processes/{id}/log-history",
            get(fixture_history),
        )
        .route("/api/sessions/{id}", get(fixture_session))
        .route("/api/workspaces/summaries", post(fixture_summaries))
        .nest(
            &format!("/api/workspaces/{}", app.workspace.id),
            Router::new()
                .route("/review-state", get(state::<Fixture>))
                .route("/review-receipts", post(receipt::<Fixture>))
                .layer(Extension(app.workspace.clone())),
        )
        .with_state(app.context.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    let job = tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    let mut receipt = app.receipt("voice");
    receipt.as_object_mut().unwrap().remove("receipt_id");
    receipt.as_object_mut().unwrap().remove("intent_version");
    let input = json!({"base":base,"root":PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize().unwrap(),"ledger":asset_dir().join(format!("disposable-connector-{}.sqlite",Uuid::new_v4())),"receipt":receipt});
    use tokio::io::AsyncWriteExt;
    let mut child = tokio::process::Command::new("/usr/bin/python3")
        .arg(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/connector_receipt_caller.py"
        ))
        .env_clear()
        .env("HOME", asset_dir())
        .env("PATH", "/usr/bin:/bin")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .kill_on_drop(true)
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(input.to_string().as_bytes())
        .await
        .unwrap();
    let output = tokio::time::timeout(Duration::from_secs(30), child.wait_with_output())
        .await
        .unwrap()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let result: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(result["result"]["status"], "applied");
    assert!(!app.unread().await);
    job.abort();
    job.await.unwrap_err();
}

#[tokio::test]
async fn incomplete_capture_is_explicit_over_http_and_cannot_review_or_backfill() {
    let app = App::new().await;
    let path = utils::execution_logs::process_log_file_path(app.session, app.execution);
    // Simulate the observed mid-thread/resume prefix in this disposable file.
    let original = tokio::fs::read(&path).await.unwrap();
    let partial = utils::log_msg::LogMsg::Stdout("{\"id\":3,\"result\":{\"thread\":".into());
    tokio::fs::write(&path, serde_json::to_string(&partial).unwrap() + "\n")
        .await
        .unwrap();
    let router = Router::new()
        .route("/history/{id}", get(fixture_history))
        .with_state(app.context.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!(
        "http://{}/history/{}",
        listener.local_addr().unwrap(),
        app.execution
    );
    let job = tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    let result: Value = reqwest::get(&url).await.unwrap().json().await.unwrap();
    assert!(
        result["data"]["capture_error"]
            .as_str()
            .unwrap()
            .contains("Incomplete")
    );
    assert_eq!(result["data"]["entries"], json!([]));
    let (review_url, review_job) = app.serve().await;
    let (status, _) = post_receipt(&review_url, &app.receipt("voice")).await;
    assert_eq!(status, 409, "No valid closure/hash after damaged capture");
    assert!(app.unread().await);
    // Only this disposable fixture is restored from its exact original bytes.
    // No native-transcript synthesis and no writer fence is fabricated.
    tokio::fs::write(&path, &original).await.unwrap();
    let result: Value = reqwest::get(&url).await.unwrap().json().await.unwrap();
    assert!(result["data"].get("capture_error").is_none());
    assert!(
        result["data"]["entries"]
            .as_array()
            .unwrap()
            .iter()
            .any(|entry| entry["entry"]["content"]["entry_type"]["type"] == "assistant_message")
    );
    assert!(app.unread().await, "Reading recovery is not delivery");
    job.abort();
    review_job.abort();
}

#[tokio::test]
async fn http_running_completed_draining_closed_is_authoritative_and_not_failure() {
    let app = App::unwritten().await;
    sqlx::query("UPDATE execution_processes SET status='running' WHERE id=?")
        .bind(app.execution)
        .execute(&app.context.pool)
        .await
        .unwrap();
    let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 1));
    let gate = Arc::new(Notify::new());
    let final_gate = gate.clone();
    let source = futures_util::stream::once(async { Ok::<_,std::io::Error>(utils::log_msg::LogMsg::Stdout("{\"id\":1,\"result\":{}}\n".into())) })
        .chain(futures_util::stream::once(async move {
            final_gate.notified().await;
            Ok(utils::log_msg::LogMsg::Stdout(json!({"method":"codex/event/agent_message","params":{"msg":{"type":"agent_message","message":"Fixture report"}}}).to_string()+"\n"))
        }));
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        store.clone(),
        db::DBService {
            pool: app.context.pool.clone(),
        },
        app.execution,
        app.session,
    );
    let producer = store.clone().spawn_forwarder(source);
    let router = Router::new()
        .route("/history/{id}", get(fixture_history))
        .with_state(app.context.clone());
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let url = format!(
        "http://{}/history/{}",
        listener.local_addr().unwrap(),
        app.execution
    );
    let job = tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });
    assert_eq!(reqwest::get(&url).await.unwrap().status(), 409);
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(app.execution)
        .execute(&app.context.pool)
        .await
        .unwrap();
    let pending: Value = reqwest::get(&url).await.unwrap().json().await.unwrap();
    assert_eq!(pending["data"]["capture_pending"], true);
    assert!(pending["data"]["capture_error"].is_null());
    assert_eq!(pending["data"]["entries"], json!([]));
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(app.execution)
    .fetch_one(&app.context.pool)
    .await
    .unwrap();
    assert_eq!(count, 0, "Draining does not certify closure");
    store.push_finished();
    gate.notify_one();
    tokio::time::timeout(Duration::from_secs(5), async {
        producer.await.unwrap();
        writer.await.unwrap();
    })
    .await
    .unwrap();
    let closed: Value = reqwest::get(&url).await.unwrap().json().await.unwrap();
    assert_eq!(closed["data"]["capture_pending"], false);
    assert!(closed["data"].get("capture_error").is_none());
    assert!(
        closed["data"]["entries"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["entry"]["content"]["content"] == "Fixture report")
    );
    assert!(app.unread().await, "Reading closure is not delivery");
    job.abort();
}

#[tokio::test]
async fn stopped_capture_owner_leaves_terminal_error_not_endless_draining() {
    let app = App::unwritten().await;
    let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 1));
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        store.clone(),
        db::DBService {
            pool: app.context.pool.clone(),
        },
        app.execution,
        app.session,
    );
    let path = utils::execution_logs::process_log_file_path(app.session, app.execution);
    tokio::time::timeout(Duration::from_secs(5), async {
        while !path.with_extension("capture.json").exists() {
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    let process = ExecutionProcess::find_by_id(&app.context.pool, app.execution)
        .await
        .unwrap()
        .unwrap();
    let page = crate::routes::execution_processes::log_history::capture_page_for_process(
        &app.context.pool,
        &process,
    )
    .await
    .unwrap()
    .unwrap();
    assert_eq!(serde_json::to_value(page).unwrap()["capture_pending"], true);
    writer.abort();
    assert!(writer.await.unwrap_err().is_cancelled());
    let page = crate::routes::execution_processes::log_history::capture_page_for_process(
        &app.context.pool,
        &process,
    )
    .await
    .unwrap()
    .unwrap();
    let page = serde_json::to_value(page).unwrap();
    assert_eq!(page["capture_pending"], false);
    assert!(
        page["capture_error"]
            .as_str()
            .unwrap()
            .contains("Incomplete")
    );
    assert!(app.unread().await);
}

struct ResumeNotificationCapture {
    raw: String,
    normalized: Vec<Value>,
    requests: Vec<Value>,
}

fn latest_normalized_values(store: &MsgStore) -> Vec<Value> {
    let mut entries = std::collections::BTreeMap::new();
    for message in store.get_history() {
        if let utils::log_msg::LogMsg::JsonPatch(patch) = message
            && let Some((index, entry)) =
                executors::logs::utils::patch::extract_normalized_entry_from_patch(&patch)
        {
            entries.insert(index, serde_json::to_value(entry).unwrap());
        }
    }
    entries.into_values().collect()
}

async fn capture_resume_notifications(runtime: &str) -> ResumeNotificationCapture {
    use std::process::Stdio;

    use executors::{
        env::RepoContext,
        executors::codex::{
            client::{AppServerClient, LogWriter},
            jsonrpc::{ExitSignalSender, JsonRpcPeer},
            normalize_logs::normalize_logs,
        },
    };
    use sha2::{Digest, Sha256};
    use tokio::io::AsyncReadExt;
    use tokio_util::{io::ReaderStream, sync::CancellationToken};

    let app = App::unwritten().await;
    let store = Arc::new(MsgStore::with_durable_capture(4 * 1024 * 1024, 64, 64));
    let normalizers = normalize_logs(store.clone(), std::path::Path::new("/workspace"));
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        store.clone(),
        db::DBService {
            pool: app.context.pool.clone(),
        },
        app.execution,
        app.session,
    );

    // This is the same byte path used by the executor: AppServerClient writes
    // raw JSONL to its LogWriter, the process stream is decoded into MsgStore,
    // and the durable consumer persists it independently of UI normalization.
    let (log_sink, log_source) = tokio::io::duplex(64 * 1024);
    let source = store
        .clone()
        .spawn_forwarder(utils::execution_logs::decode_stdout(ReaderStream::new(
            log_source,
        )));

    let full: Value = serde_json::from_str(include_str!(
        "../../../../executors/src/executors/codex/fixtures/new-error-resume.json"
    ))
    .unwrap();
    let mut empty = full.clone();
    empty["thread"]["turns"] = json!([]);
    let mut child = tokio::process::Command::new("python3")
        .args([
            "-u",
            "-c",
            r#"
import json, sys
runtime, empty_raw, full_raw = sys.argv[1:]
empty = json.loads(empty_raw)
full = json.loads(full_raw)
notifications = [
    {"method":"turn/started","params":{"threadId":"thread-fixture","turn":{"id":"synthetic-turn","items":[],"status":"inProgress","error":None}}},
    {"method":"item/started","params":{"threadId":"thread-fixture","turnId":"synthetic-turn","item":{"type":"commandExecution","id":"synthetic-tool","command":"printf synthetic-tool-output","cwd":"/workspace","processId":None,"status":"inProgress","commandActions":[],"aggregatedOutput":None,"exitCode":None,"durationMs":None}}},
    {"method":"item/completed","params":{"threadId":"thread-fixture","turnId":"synthetic-turn","item":{"type":"commandExecution","id":"synthetic-tool","command":"printf synthetic-tool-output","cwd":"/workspace","processId":None,"status":"completed","commandActions":[],"aggregatedOutput":"synthetic-tool-output","exitCode":0,"durationMs":1}}},
    {"method":"item/completed","params":{"threadId":"thread-fixture","turnId":"synthetic-turn","item":{"type":"agentMessage","id":"synthetic-final","text":"new assistant terminal survives — ✓","phase":"final_answer","memoryCitation":None}}},
    {"method":"turn/completed","params":{"threadId":"thread-fixture","turn":{"id":"synthetic-turn","items":[],"status":"completed","error":None}}},
]
for line in sys.stdin:
    request = json.loads(line)
    print(json.dumps(request, separators=(",", ":")), file=sys.stderr, flush=True)
    if "id" not in request:
        continue
    method = request["method"]
    if method == "initialize":
        result = {"userAgent": runtime, "platformFamily": "unix", "platformOs": "linux"}
    elif method == "thread/resume":
        result = empty if request["params"].get("excludeTurns") is True else full
    elif method == "turn/start":
        result = {"turn":{"id":"synthetic-turn","items":[],"status":"inProgress","error":None}}
    else:
        result = {}
    print(json.dumps({"id":request["id"],"result":result}, separators=(",", ":")), flush=True)
    if method == "turn/start":
        for notification in notifications:
            print(json.dumps(notification, separators=(",", ":")), flush=True)
"#,
        ])
        .arg(runtime)
        .arg(empty.to_string())
        .arg(full.to_string())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()
        .unwrap();
    let mut stderr = child.stderr.take().unwrap();
    let cancel = CancellationToken::new();
    let client = AppServerClient::new(
        LogWriter::new(log_sink),
        None,
        false,
        false,
        RepoContext::default(),
        false,
        String::new(),
        cancel.clone(),
    );
    let (exit_tx, exit_rx) = tokio::sync::oneshot::channel();
    client.connect(JsonRpcPeer::spawn(
        child.stdin.take().unwrap(),
        child.stdout.take().unwrap(),
        client.clone(),
        ExitSignalSender::new(exit_tx),
        cancel.clone(),
    ));
    client.initialize().await.unwrap();
    let resumed = client
        .delegation_request("thread/resume", json!({"threadId":"thread-fixture"}))
        .await
        .unwrap();
    assert_eq!(resumed["thread"]["id"], "thread-fixture");
    client.register_session("thread-fixture").await.unwrap();
    let turn = client
        .delegation_request(
            "turn/start",
            json!({"threadId":"thread-fixture","input":[]}),
        )
        .await
        .unwrap();
    assert_eq!(turn["turn"]["id"], "synthetic-turn");
    tokio::time::timeout(Duration::from_secs(5), exit_rx)
        .await
        .unwrap()
        .unwrap();
    let _ = child.kill().await;
    child.wait().await.unwrap();
    cancel.cancel();
    drop(client);
    tokio::time::timeout(Duration::from_secs(5), source)
        .await
        .unwrap()
        .unwrap();

    // Do not publish metadata EOF until both real notification-derived entries
    // have traversed the normalizer. This keeps the writer footer after them.
    tokio::time::timeout(Duration::from_secs(5), async {
        loop {
            let entries = latest_normalized_values(&store);
            if entries
                .iter()
                .any(|entry| entry["content"] == "new assistant terminal survives — ✓")
                && entries.iter().any(|entry| {
                    entry["entry_type"]["type"] == "tool_use"
                        && entry["entry_type"]["tool_name"] == "bash"
                        && entry["entry_type"]["status"]["status"] == "success"
                })
            {
                break;
            }
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    store.push_finished();
    for normalizer in normalizers {
        normalizer.await.unwrap();
    }
    writer.await.unwrap();

    let path = utils::execution_logs::process_log_file_path(app.session, app.execution);
    utils::execution_logs::validate_native_capture(&path, 4 * 1024 * 1024)
        .await
        .unwrap();
    let (bytes, messages) =
        utils::execution_logs::read_execution_log_strict(&path, 4 * 1024 * 1024)
            .await
            .unwrap();
    let raw = messages
        .iter()
        .filter_map(|message| match message {
            utils::log_msg::LogMsg::Stdout(stdout) => Some(stdout.as_str()),
            _ => None,
        })
        .collect::<String>();
    let footer: Value = serde_json::from_slice(
        &tokio::fs::read(path.with_extension("capture.json"))
            .await
            .unwrap(),
    )
    .unwrap();
    assert_eq!(footer["capture_state"], "closed");
    let finalized: (i64, String) = sqlx::query_as(
        "SELECT raw_bytes,raw_sha256 FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(app.execution)
    .fetch_one(&app.context.pool)
    .await
    .unwrap();
    assert_eq!(finalized.0, bytes.len() as i64);
    assert_eq!(finalized.1, format!("{:x}", Sha256::digest(&bytes)));

    let mut request_log = String::new();
    stderr.read_to_string(&mut request_log).await.unwrap();
    ResumeNotificationCapture {
        raw,
        normalized: latest_normalized_values(&store),
        requests: request_log
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect(),
    }
}

#[tokio::test]
async fn resume_suppression_preserves_real_notifications_normalization_and_footer() {
    let narrow = capture_resume_notifications("codex_cli_rs/0.159.2 (synthetic)").await;
    let legacy = capture_resume_notifications("codex_cli_rs/0.116.0 (synthetic)").await;

    let narrow_resume = narrow
        .requests
        .iter()
        .find(|request| request["method"] == "thread/resume")
        .unwrap();
    let legacy_resume = legacy
        .requests
        .iter()
        .find(|request| request["method"] == "thread/resume")
        .unwrap();
    assert_eq!(narrow_resume["params"]["excludeTurns"], true);
    assert!(legacy_resume["params"].get("excludeTurns").is_none());

    assert!(!narrow.raw.contains("Potentially unintended activity"));
    assert!(legacy.raw.contains("Potentially unintended activity"));
    assert!(narrow.raw.len() < legacy.raw.len());

    let new_events = |raw: &str| {
        raw.lines()
            .filter_map(|line| serde_json::from_str::<Value>(line).ok())
            .filter(|value| {
                matches!(
                    value["method"].as_str(),
                    Some("turn/started" | "turn/completed" | "item/started" | "item/completed")
                )
            })
            .collect::<Vec<_>>()
    };
    let narrow_events = new_events(&narrow.raw);
    let legacy_events = new_events(&legacy.raw);
    assert_eq!(narrow_events, legacy_events);
    for events in [&narrow_events, &legacy_events] {
        assert!(events.iter().any(|event| {
            event["method"] == "item/completed"
                && event["params"]["item"]["type"] == "agentMessage"
                && event["params"]["item"]["text"] == "new assistant terminal survives — ✓"
        }));
        assert!(events.iter().any(|event| {
            event["method"] == "item/completed"
                && event["params"]["item"]["type"] == "commandExecution"
                && event["params"]["item"]["aggregatedOutput"] == "synthetic-tool-output"
        }));
    }
    assert_eq!(narrow.normalized, legacy.normalized);
    assert!(narrow.normalized.iter().any(|entry| {
        entry["entry_type"]["type"] == "assistant_message"
            && entry["content"] == "new assistant terminal survives — ✓"
    }));
    assert!(narrow.normalized.iter().any(|entry| {
        entry["entry_type"]["type"] == "tool_use"
            && entry["entry_type"]["tool_name"] == "bash"
            && entry["entry_type"]["status"]["status"] == "success"
            && entry["entry_type"]["action_type"]["result"]["output"] == "synthetic-tool-output"
    }));
}

#[tokio::test]
async fn pr57_subscriber_timeout_preserves_durable_footer_and_final() {
    let app = App::unwritten().await;
    let (blocked, ()) = tokio::join!(
        crate::routes::execution_processes::bounded_execution_log_ws_io::<()>(
            "send",
            std::future::pending()
        ),
        app.write_log()
    );
    assert!(blocked.unwrap_err().to_string().contains("send timed out"));
    let process = ExecutionProcess::find_by_id(&app.context.pool, app.execution)
        .await
        .unwrap()
        .unwrap();
    let messages = services::services::report_review::replay_review_log(
        &app.context.pool,
        &process,
        &asset_dir(),
    )
    .await
    .unwrap();
    let (selected_index, digest) =
        crate::routes::execution_processes::log_history::fingerprint_review_messages(messages)
            .unwrap();
    assert_eq!(selected_index, 0);
    assert_eq!(digest, sha("Fixture report"));
    assert!(app.unread().await);
}
