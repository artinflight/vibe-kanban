//! Exercise the production approval service with an offline JSON-RPC peer and
//! the same serialized response shape sent by the chat approval UI.
use std::{process::Stdio, sync::Arc, time::Duration};

use executors::{
    env::RepoContext,
    executors::codex::{
        client::{AppServerClient, LogWriter},
        jsonrpc::{ExitSignalSender, JsonRpcPeer},
    },
};
use serde_json::{Value, json};
use tokio::{
    io::{AsyncBufReadExt, BufReader, Lines},
    process::{Child, ChildStderr, Command},
    sync::RwLock,
};
use tokio_util::sync::CancellationToken;
use utils::approvals::{ApprovalOutcome, ApprovalResponse};
use uuid::Uuid;

use super::{Approvals, executor_approvals::ExecutorApprovalBridge};
use crate::services::{config::Config, notification::NotificationService};

struct Fixture {
    approvals: Approvals,
    execution: Uuid,
    peer: JsonRpcPeer,
    client: Arc<AppServerClient>,
    child: Child,
    responses: Lines<BufReader<ChildStderr>>,
    cancel: CancellationToken,
    logs: Arc<tokio::sync::Mutex<Vec<String>>>,
}

fn request(id: i64) -> Value {
    json!({"id":id,"method":"mcpServer/elicitation/request","params":{
        "threadId":"fixture-thread","turnId":"fixture-turn","serverName":"codex_apps",
        "mode":"form","message":"Allow this app to run tool \"run_session_prompt\"?",
        "requestedSchema":{"type":"object","properties":{}},
        "_meta":{"codex_approval_kind":"mcp_tool_call","tool_title":"run_session_prompt",
            "source":"connector","connector_id":"fixture-vk","connector_name":"Synthetic Vibe Kanban",
            "tool_params":{"session_id":format!("synthetic-target-{id}"),"prompt":"Resume synthetic Reporting only", "api_key":"do-not-log"},
            "tool_params_display":[{"name":"session_id","display_name":"Reporting session target","value":format!("synthetic-target-{id}")}],
            "persist":["session","always"],"private_fixture_sentinel":"do-not-log"}
    }})
}

impl Fixture {
    async fn new() -> Self {
        let approvals = Approvals::new();
        let execution = Uuid::parse_str("00000000-0000-4000-8000-000000000001").unwrap();
        let mut config = Config::default();
        config.notifications.sound_enabled = false;
        config.notifications.push_enabled = false;
        let bridge = ExecutorApprovalBridge::new(
            approvals.clone(),
            db::DBService {
                pool: sqlx::sqlite::SqlitePoolOptions::new()
                    .connect("sqlite::memory:")
                    .await
                    .unwrap(),
            },
            NotificationService::new(Arc::new(RwLock::new(config))),
            execution,
        );
        let cancel = CancellationToken::new();
        // Even command auto-approval must not accept MCP consent.
        let logs = Arc::new(tokio::sync::Mutex::new(Vec::new()));
        let (writer, reader) = tokio::io::duplex(128 * 1024);
        let captured = logs.clone();
        tokio::spawn(async move {
            let mut lines = BufReader::new(reader).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                captured.lock().await.push(line);
            }
        });
        let client = AppServerClient::new(
            LogWriter::new(writer),
            Some(bridge),
            true,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        let mut child = Command::new("python3")
            .arg(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../scripts/testing/codex_mcp_approval_peer.py"
            ))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .unwrap();
        let responses = BufReader::new(child.stderr.take().unwrap()).lines();
        let (tx, _) = tokio::sync::oneshot::channel();
        let peer = JsonRpcPeer::spawn(
            child.stdin.take().unwrap(),
            child.stdout.take().unwrap(),
            client.clone(),
            ExitSignalSender::new(tx),
            cancel.clone(),
        );
        client.connect(peer.clone());
        client.register_session("fixture-thread").await.unwrap();
        peer.send(&json!({"fixture":{"method":"turn/started","params":{
            "threadId":"fixture-thread","turn":{"id":"fixture-turn","items":[],"status":"inProgress","error":null}
        }}})).await.unwrap();
        Self {
            approvals,
            execution,
            peer,
            client,
            child,
            responses,
            cancel,
            logs,
        }
    }

    async fn send(&self, value: Value) {
        self.peer.send(&json!({"fixture":value})).await.unwrap();
    }

    async fn pending(&self, count: usize) -> Vec<super::ApprovalInfo> {
        tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                let infos = self.approvals.pending_infos();
                if infos.len() == count {
                    return infos;
                }
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap()
    }

    async fn respond(&self, id: &str, status: Value) {
        let response: ApprovalResponse = serde_json::from_value(json!({
            "execution_process_id":self.execution,"status":status
        }))
        .unwrap();
        self.approvals.respond(id, response).await.unwrap();
    }

    async fn result(&mut self) -> Value {
        let line = tokio::time::timeout(Duration::from_secs(5), self.responses.next_line())
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        serde_json::from_str(&line).unwrap()
    }

    async fn no_response(&mut self) {
        assert!(
            tokio::time::timeout(Duration::from_millis(100), self.responses.next_line())
                .await
                .is_err()
        );
    }

    async fn logged(&self, origin: &str) {
        tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                if self
                    .logs
                    .lock()
                    .await
                    .iter()
                    .any(|line| line.contains(origin))
                {
                    break;
                }
                tokio::time::sleep(Duration::from_millis(5)).await;
            }
        })
        .await
        .unwrap();
    }

    async fn stop(mut self) {
        self.cancel.cancel();
        self.child.kill().await.unwrap();
        self.child.wait().await.unwrap();
        self.pending(0).await;
        drop(self.client);
    }
}

#[tokio::test]
async fn mcp_reporting_resume_ui_consent_round_trip() {
    let ui_payloads = std::env::var("VK_MCP_UI_RESPONSES")
        .ok()
        .map(|path| std::fs::read_to_string(path).unwrap())
        .unwrap_or_else(|| {
            include_str!("../../../../../scripts/testing/mcp-ui-responses.json").to_owned()
        });
    let ui_payloads: Vec<ApprovalResponse> = serde_json::from_str(&ui_payloads).unwrap();
    let mut fixture = Fixture::new().await;
    fixture.send(request(0)).await;
    let pending = fixture.pending(1).await;
    assert_eq!(pending[0].execution_process_id, fixture.execution);
    assert!(!pending[0].is_question);
    let context = pending[0].mcp_consent.as_deref().unwrap();
    assert!(context.contains("synthetic-target-0"));
    assert!(context.contains("Reporting session target"));
    assert!(!context.contains("do-not-log"));
    fixture.no_response().await; // durationMs zero cannot become a dispatch without consent
    let id = &pending[0].approval_id;
    // A different execution cannot resolve this request.
    assert!(
        fixture
            .approvals
            .respond(
                id,
                ApprovalResponse {
                    execution_process_id: Uuid::new_v4(),
                    status: ApprovalOutcome::Approved,
                }
            )
            .await
            .is_err()
    );
    fixture.pending(1).await;
    fixture
        .approvals
        .respond(id, ui_payloads[0].clone())
        .await
        .unwrap();
    let result = fixture.result().await;
    assert_eq!(result["id"], 0);
    assert_eq!(result["fixtureDispatch"], true);
    assert_eq!(
        result["result"],
        json!({"action":"accept","content":{},"_meta":null})
    );
    let logged = fixture.logs.lock().await.join("\n");
    assert!(logged.contains("run_session_prompt"));
    assert!(!logged.contains("private_fixture_sentinel"));
    assert!(!logged.contains("do-not-log"));
    assert!(!logged.contains("persist"));
    assert!(
        fixture
            .approvals
            .respond(
                id,
                ApprovalResponse {
                    execution_process_id: fixture.execution,
                    status: ApprovalOutcome::Approved,
                }
            )
            .await
            .is_err()
    );
    fixture.send(request(0)).await; // duplicate cannot reuse the approval
    fixture.no_response().await;
    fixture.send(request(1)).await;
    let id = fixture.pending(1).await[0].approval_id.clone();
    fixture
        .approvals
        .respond(&id, ui_payloads[1].clone())
        .await
        .unwrap();
    let declined = fixture.result().await;
    assert_eq!(declined["result"]["action"], "decline");
    assert_eq!(declined["fixtureDispatch"], false);
    fixture.stop().await;
}

#[tokio::test]
async fn mcp_generic_monitor_context_and_inadequate_metadata_fail_closed() {
    let mut fixture = Fixture::new().await;
    let mut monitor = request(22);
    monitor["params"]["message"] =
        json!("Tool call needs your approval. Reason: This action requires confirmation");
    fixture.send(monitor).await;
    let pending = fixture.pending(1).await;
    let context = pending[0].mcp_consent.as_deref().unwrap();
    assert!(context.contains("synthetic-target-22"));
    assert!(context.contains("run_session_prompt"));
    assert!(context.contains("Resume synthetic Reporting only"));
    fixture
        .respond(&pending[0].approval_id, json!({"status":"denied"}))
        .await;
    assert_eq!(fixture.result().await["result"]["action"], "decline");
    for (id, key) in [(23, "tool_params"), (24, "connector_id")] {
        let mut incomplete = request(id);
        incomplete["params"]["_meta"]
            .as_object_mut()
            .unwrap()
            .remove(key);
        fixture.send(incomplete).await;
        let result = fixture.result().await;
        assert_eq!(result["result"]["action"], "cancel");
        assert_eq!(
            result["result"]["content"]["error"]["details"]["reason"],
            "missing_context"
        );
        fixture.pending(0).await;
    }
    for (id, payload) in [
        (25, json!({"access_token":"synthetic-nested-object"})),
        (26, json!([[{"access_token":"synthetic-nested-array"}]])),
    ] {
        let mut redacted_only = request(id);
        redacted_only["params"]["_meta"]["tool_params"] = json!({"payload":payload});
        redacted_only["params"]["_meta"]["tool_params_display"] = json!([
            {"name":"payload","display_name":"Payload","value":payload}
        ]);
        fixture.send(redacted_only).await;
        let result = fixture.result().await;
        assert_eq!(result["result"]["action"], "cancel");
        assert_eq!(
            result["result"]["content"]["error"]["details"]["reason"],
            "redacted_only"
        );
        assert_eq!(result["result"]["content"]["review_requested"], false);
        assert_eq!(result["fixtureDispatch"], false);
        fixture.pending(0).await;
    }
    let logs = fixture.logs.lock().await.join("\n");
    assert!(logs.contains("consent_validation_failed"));
    assert!(!logs.contains("do-not-log"));
    assert!(!logs.contains("synthetic-nested-object"));
    assert!(!logs.contains("synthetic-nested-array"));
    fixture.stop().await;
}

#[tokio::test]
async fn mcp_concurrent_requests_decline_timeout_and_connection_isolation() {
    let mut a = Fixture::new().await;
    let mut b = Fixture::new().await;
    a.send(request(0)).await;
    b.send(request(0)).await;
    let a_id = a.pending(1).await[0].approval_id.clone();
    let b_id = b.pending(1).await[0].approval_id.clone();
    assert_ne!(a_id, b_id);
    a.respond(
        &a_id,
        json!({"status":"denied","reason":"synthetic explicit decline"}),
    )
    .await;
    assert_eq!(a.result().await["result"]["action"], "decline");
    b.no_response().await;
    b.respond(&b_id, json!({"status":"timed_out"})).await;
    assert_eq!(b.result().await["result"]["action"], "cancel");
    a.send(request(1)).await;
    a.send(request(2)).await;
    let pending = a.pending(2).await;
    a.respond(&pending[1].approval_id, json!({"status":"approved"}))
        .await;
    assert_eq!(a.result().await["result"]["action"], "accept");
    a.pending(1).await;
    a.no_response().await;
    a.send(json!({"method":"serverRequest/resolved","params":{"threadId":"fixture-thread","requestId":1}})).await;
    a.send(json!({"method":"serverRequest/resolved","params":{"threadId":"fixture-thread","requestId":2}})).await;
    assert_eq!(a.result().await["result"]["action"], "cancel");
    a.stop().await;
    b.stop().await;
}

#[tokio::test]
async fn mcp_unsupported_malformed_stale_stop_and_disconnect_fail_closed() {
    let mut fixture = Fixture::new().await;
    let mut unsupported = request(1);
    unsupported["params"]["requestedSchema"]["properties"] = json!({"secret":{"type":"string"}});
    let mut url = request(2);
    url["params"]["mode"] = json!("url");
    url["params"]["url"] = json!("https://invalid.example/auth");
    url["params"]["elicitationId"] = json!("fixture");
    let mut stale = request(3);
    stale["params"]["turnId"] = json!("old-turn");
    for value in [
        unsupported,
        url,
        stale,
        json!({"id":4,"method":"mcpServer/elicitation/request","params":null}),
    ] {
        fixture.send(value).await;
        assert_eq!(fixture.result().await["result"]["action"], "cancel");
        fixture.pending(0).await;
    }
    fixture.send(request(5)).await;
    fixture.pending(1).await;
    fixture.peer.shutdown().await.unwrap();
    assert_eq!(fixture.result().await["result"]["action"], "cancel");
    fixture.pending(0).await;
    let logs = fixture.logs.lock().await.join("\n");
    assert!(logs.contains("disconnected"));
    assert!(!logs.contains("https://invalid.example/auth"));
    assert!(!logs.contains("private_fixture_sentinel"));
    fixture.stop().await;
    let fixture = Fixture::new().await;
    fixture.send(request(0)).await;
    fixture.pending(1).await;
    fixture.stop().await;
}

#[tokio::test]
async fn mcp_repeated_pending_request_and_nullable_turn_are_cancelled() {
    let mut fixture = Fixture::new().await;
    fixture.send(request(0)).await;
    fixture.pending(1).await;
    fixture.send(request(0)).await;
    assert_eq!(fixture.result().await["result"]["action"], "cancel");
    fixture.pending(0).await;
    let mut nullable = request(1);
    nullable["params"]["turnId"] = Value::Null;
    fixture.send(nullable).await;
    fixture.pending(1).await;
    fixture.send(json!({"method":"turn/started","params":{
        "threadId":"fixture-thread","turn":{"id":"next-turn","items":[],"status":"inProgress","error":null}
    }})).await;
    assert_eq!(fixture.result().await["result"]["action"], "cancel");
    fixture.pending(0).await;
    fixture.stop().await;
}

#[tokio::test]
async fn mcp_deadline_and_peer_eof_do_not_become_human_declines() {
    let approvals = Approvals::new();
    let mut request =
        utils::approvals::ApprovalRequest::new("synthetic MCP".into(), Uuid::new_v4());
    request.timeout_at = chrono::Utc::now() - chrono::Duration::seconds(1);
    let (_, waiter) = approvals.create_with_waiter(request, false).await.unwrap();
    let outcome = tokio::time::timeout(Duration::from_secs(5), waiter)
        .await
        .unwrap();
    assert!(matches!(outcome, ApprovalOutcome::TimedOut));
    let (action, origin) = executors::executors::codex::elicitation::outcome(Ok(
        utils::approvals::ApprovalStatus::TimedOut,
    ));
    assert_eq!(origin, "timeout");
    assert_eq!(
        serde_json::to_value(executors::executors::codex::elicitation::response(action)).unwrap()["action"],
        "cancel"
    );

    let mut fixture = Fixture::new().await;
    fixture.send(super::elicitation_tests::request(0)).await;
    fixture.pending(1).await;
    fixture.child.kill().await.unwrap(); // actual EOF, not a production process
    fixture.pending(0).await;
    tokio::time::timeout(Duration::from_secs(5), async {
        loop {
            if fixture
                .logs
                .lock()
                .await
                .iter()
                .any(|line| line.contains("disconnected"))
            {
                break;
            }
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    assert!(
        !fixture
            .logs
            .lock()
            .await
            .iter()
            .any(|line| line.contains("human_declined"))
    );
    fixture.cancel.cancel();
    fixture.child.wait().await.unwrap();
}

#[tokio::test]
async fn mcp_long_dispatch_requires_explicit_review_and_distinguishes_validation_decline_timeout() {
    let mut fixture = Fixture::new().await;
    let prompt = format!(
        "{}\nNo Figma until per-view owner signoff.\nEND-OF-PROMPT",
        "🧭".repeat(12_000)
    );
    for (id, status, action, origin) in [
        (70, "approved", "accept", "human_approved"),
        (71, "denied", "decline", "human_declined"),
        (72, "timed_out", "cancel", "timeout"),
    ] {
        let mut value = request(id);
        value["params"]["_meta"]["tool_params"]["prompt"] = json!(prompt);
        value["params"]["_meta"]["tool_params_display"].as_array_mut().unwrap().push(json!({"name":"prompt", "display_name":"Full dispatch instructions", "value":prompt}));
        fixture.send(value).await;
        let pending = fixture.pending(1).await;
        let context = pending[0].mcp_consent.as_deref().unwrap();
        assert!(context.contains(&prompt));
        assert_eq!(context.matches(&prompt).count(), 1);
        fixture.no_response().await;
        fixture
            .respond(&pending[0].approval_id, json!({"status":status}))
            .await;
        let result = fixture.result().await;
        assert_eq!(result["result"]["action"], action);
        assert_eq!(result["fixtureDispatch"], action == "accept");
        fixture.logged(origin).await;
    }
    let mut value = request(73);
    value["params"]["_meta"]["tool_params"]["prompt"] = json!("x".repeat(60_001));
    fixture.send(value).await;
    let result = fixture.result().await;
    assert_eq!(result["fixtureDispatch"], false);
    assert_eq!(
        result["result"]["content"]["error"]["details"]["reason"],
        "string_characters"
    );
    assert_eq!(
        result["result"]["content"]["error"]["details"]["observed"],
        60_001
    );
    assert_eq!(result["result"]["content"]["review_requested"], false);
    fixture.pending(0).await;
    let logs = fixture.logs.lock().await.join("\n");
    assert!(logs.contains("consent_validation_failed"));
    assert!(logs.contains("string_characters"));
    assert!(!logs.contains(&"x".repeat(60_001)));
    assert!(!logs.contains("do-not-log"));
    fixture.stop().await;
}
