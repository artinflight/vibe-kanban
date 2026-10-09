//! Actual Axum handlers + native normalizer/storage writer + real SQLite on SSD.
//! No Deployment::new, agent launch, production config, auth or live badges.
use std::{collections::HashMap, path::PathBuf, sync::Arc, time::Duration};

use axum::{
    Router,
    routing::{get, post, put},
};
use db::models::coding_agent_turn::CodingAgentTurn;
use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions};
use tokio::sync::{Notify, RwLock};
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
        let app = Self {
            context,
            workspace,
            session,
            execution,
            revision,
            database,
        };
        app.write_log().await;
        app
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
        let stores = Arc::new(RwLock::new(HashMap::from([(self.execution, store)])));
        services::services::execution_process::spawn_stream_raw_logs_to_storage(
            stores,
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
) -> Json<ApiResponse<Value>> {
    let process = ExecutionProcess::find_by_id(&c.pool, id)
        .await
        .unwrap()
        .unwrap();
    if let Some(reason) =
        crate::routes::execution_processes::log_history::capture_error_for_process(
            &c.pool, &process,
        )
        .await
        .unwrap()
    {
        return Json(ApiResponse::success(
            json!({"entries":[],"next_before":null,"capture_error":reason}),
        ));
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
    Json(ApiResponse::success(
        json!({"entries":entries,"next_before":null}),
    ))
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
