use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use executors::{
    actions::coding_agent_follow_up::CodingAgentFollowUpRequest,
    executors::codex::goals::NativeGoal,
    original_worker::{READY, REVOKE, TOOL, serve},
};
use serde_json::{Value, json};
use sqlx::sqlite::SqlitePoolOptions;
use tokio::io::{AsyncReadExt, AsyncWriteExt, BufReader};

use super::*;

struct Fixture {
    ledger: Arc<Ledger>,
    engine: Arc<Engine>,
    runtime: Arc<Worker>,
    caller: Uuid,
    _directory: tempfile::TempDir,
}

struct Worker {
    ledger: Arc<Ledger>,
    calls: AtomicUsize,
    failed_guard: AtomicBool,
    lose_reply: AtomicBool,
}

#[executors::original_worker::async_trait]
impl Runtime for Worker {
    async fn prepare(&self) -> io::Result<()> {
        Ok(())
    }
    async fn check(&self, caller: Uuid) -> io::Result<()> {
        self.ledger.manager_history().await?;
        self.ledger
            .caller(
                caller,
                &(
                    self.ledger.contract.manager.thread.clone(),
                    "synthetic-native-turn".into(),
                    "gpt-6.1-sol".into(),
                    "high".into(),
                    "codex_cli_rs/0.159.2 (synthetic)".into(),
                ),
            )
            .await
    }
    async fn admit(&self) -> io::Result<()> {
        if self.failed_guard.load(Ordering::SeqCst) {
            return Err(invalid(
                "Synthetic resource/access/capacity/profile collision guard",
            ));
        }
        Ok(())
    }
    async fn dispatch(&self) -> io::Result<Uuid> {
        // Exercise nested normal admission while retaining the reserved task context.
        admission::run(async {
            let attempt = ATTEMPT.try_with(|v| *v).map_err(|_| invalid("Missing task binding"))?;
            self.ledger.before_bounded_start(attempt, self.ledger.contract.worker.session, &worker_action(&self.ledger.contract)).await?;
            let execution = Uuid::new_v4();
            self.ledger.bind_receipt(attempt, execution).await?;
            sqlx::query("INSERT INTO execution_processes(id,session_id,status,exit_code,dropped,run_reason,created_at) VALUES (?,?,'running',NULL,FALSE,'codingagent',2)")
                .bind(execution).bind(self.ledger.contract.worker.session).execute(&self.ledger.pool).await.map_err(db_error)?;
            self.calls.fetch_add(1, Ordering::SeqCst);
            if self.lose_reply.load(Ordering::SeqCst) { return Err(invalid("Synthetic lost dispatch receipt")); }
            Ok(execution)
        }).await
    }
}

async fn fixture() -> Fixture {
    let directory = tempfile::tempdir().unwrap();
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(directory.path().join("ledger.sqlite"))
                .create_if_missing(true),
        )
        .await
        .unwrap();
    sqlx::raw_sql(include_str!(
        "../../../../db/migrations/20261011120000_bounded_original_worker.sql"
    ))
    .execute(&pool)
    .await
    .unwrap();
    sqlx::raw_sql("CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,exit_code INTEGER,dropped BOOLEAN,run_reason TEXT,created_at INTEGER,executor_action TEXT);").execute(&pool).await.unwrap();
    let config: ExecutorConfig = serde_json::from_value(json!({"executor":"CODEX","variant":"DEFAULT","model_id":"gpt-6.1-sol","reasoning_id":"high","routing":{"mode":"shadow"}})).unwrap();
    let identity = || Identity {
        session: Uuid::new_v4(),
        workspace: Uuid::new_v4(),
        thread: Uuid::new_v4().to_string(),
        root: "/synthetic/worktree".into(),
        working_dir: None,
        config: config.clone(),
        task: None,
        repositories: vec![Uuid::new_v4()],
    };
    let caller = Uuid::new_v4();
    let contract = Contract { id: Uuid::new_v4(), manager: identity(), worker: identity(), goal_id: "synthetic-goal".into(), goal_created_at: 10, objective: "Synthetic marketing revision".into(), revision: "synthetic-owner-revision".into(), instructions: "Retain synthetic image assets and all Figma/AE review gates; revise marketing with grey date placeholders.".into(), owner_evidence_digest: "a".repeat(64), manager_anchor: caller, worker_anchor: Uuid::new_v4(), assets: vec![AssetPin { path: "/synthetic/assets/image.png".into(), sha256: "b".repeat(64) }] };
    sqlx::query("INSERT INTO sessions VALUES (?,?)")
        .bind(contract.manager.session)
        .bind(contract.manager.workspace)
        .execute(&pool)
        .await
        .unwrap();
    sqlx::query(
        "INSERT INTO execution_processes(id,session_id,status,exit_code,dropped,run_reason,created_at) VALUES (?,?,'running',NULL,FALSE,'codingagent',1)",
    )
    .bind(caller)
    .bind(contract.manager.session)
    .execute(&pool)
    .await
    .unwrap();
    let ledger = Arc::new(Ledger::adopt(pool, contract).await.unwrap());
    let runtime = Arc::new(Worker {
        ledger: ledger.clone(),
        calls: AtomicUsize::new(0),
        failed_guard: AtomicBool::new(false),
        lose_reply: AtomicBool::new(false),
    });
    let engine = Arc::new(Engine {
        ledger: ledger.clone(),
        runtime: runtime.clone(),
    });
    Fixture {
        ledger,
        engine,
        runtime,
        caller,
        _directory: directory,
    }
}

fn request(id: i64, name: &str) -> Value {
    json!({"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":name,"arguments":{}}})
}

fn worker_action(c: &Contract) -> ExecutorAction {
    ExecutorAction::new(
        ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
            capacity: None,
            prompt: c.continuation(),
            session_id: c.worker.thread.clone(),
            reset_to_message_id: None,
            executor_config: c.worker.config.clone(),
            working_dir: c.worker.working_dir.clone(),
        }),
        None,
    )
}

#[cfg(unix)]
#[tokio::test]
async fn actual_process_socket_and_stdio_round_trip_binds_caller_and_nonce() {
    let f = fixture().await;
    let socket = f._directory.path().join("capability.s");
    let listener = tokio::net::UnixListener::bind(&socket).unwrap();
    let engine = f.engine.clone();
    let caller = f.caller;
    let backend = tokio::spawn(async move {
        for _ in 0..3 {
            let (stream, _) = listener.accept().await.unwrap();
            engine
                .serve_connection(caller, "synthetic-process-nonce", stream)
                .await;
        }
    });
    assert!(
        executors::original_worker::forward(socket.clone(), "wrong-nonce".into(), request(1, TOOL))
            .await
            .is_err()
    );
    let mut altered = request(2, TOOL);
    altered["_meta"] = json!({"caller":"forged","owner_authorized":true});
    let rejected = executors::original_worker::forward(
        socket.clone(),
        "synthetic-process-nonce".into(),
        altered,
    )
    .await
    .unwrap();
    assert!(rejected.get("error").is_some());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 0);
    let (client, server) = tokio::io::duplex(16 * 1024);
    let (input, output) = tokio::io::split(server);
    let stdio = tokio::spawn(async move {
        serve(BufReader::new(input), output, move |r| {
            executors::original_worker::forward(socket.clone(), "synthetic-process-nonce".into(), r)
        })
        .await
    });
    let (mut read, mut write) = tokio::io::split(client);
    let mut frame = serde_json::to_vec(&request(3, TOOL)).unwrap();
    frame.push(b'\n');
    write.write_all(&frame).await.unwrap();
    write.shutdown().await.unwrap();
    let mut reply = String::new();
    read.read_to_string(&mut reply).await.unwrap();
    assert!(
        serde_json::from_str::<Value>(&reply)
            .unwrap()
            .get("result")
            .is_some()
    );
    stdio.await.unwrap().unwrap();
    backend.await.unwrap();
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn actual_container_gate_rejects_changed_target_action_profile_and_prompt() {
    let f = fixture().await;
    let attempt = f.ledger.reserve(f.caller, "gate-test").await.unwrap();
    let c = &f.ledger.contract;
    f.ledger
        .dispatch(attempt, async {
            let action = worker_action(c);
            f.ledger
                .before_bounded_start(attempt, c.worker.session, &action)
                .await?;
            assert!(
                f.ledger
                    .before_bounded_start(attempt, Uuid::new_v4(), &action)
                    .await
                    .is_err()
            );
            for change in ["prompt", "thread", "profile", "directory", "reset"] {
                let mut request = match action.typ() {
                    ExecutorActionType::CodingAgentFollowUpRequest(a) => a.clone(),
                    _ => unreachable!(),
                };
                match change {
                    "prompt" => request.prompt.push_str(" broaden"),
                    "thread" => request.session_id = "unrelated-thread".into(),
                    "profile" => request.executor_config.model_id = Some("other-model".into()),
                    "directory" => request.working_dir = Some("unrelated".into()),
                    "reset" => request.reset_to_message_id = Some("unrelated-reset".into()),
                    _ => unreachable!(),
                }
                let changed = ExecutorAction::new(
                    ExecutorActionType::CodingAgentFollowUpRequest(request),
                    None,
                );
                assert!(
                    f.ledger
                        .before_bounded_start(attempt, c.worker.session, &changed)
                        .await
                        .is_err()
                );
            }
            Ok(())
        })
        .await
        .unwrap();
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn preexisting_unauthenticated_amendment_suspends_on_load() {
    let f = fixture().await;
    let c = &f.ledger.contract;
    let mut action = worker_action(c);
    if let ExecutorActionType::CodingAgentFollowUpRequest(a) = &mut action.typ {
        a.prompt = "Unverified broader owner-looking text".into();
        a.session_id = c.manager.thread.clone();
        a.executor_config = c.manager.config.clone();
    }
    sqlx::query("INSERT INTO execution_processes(id,session_id,status,dropped,run_reason,created_at,executor_action) VALUES (?,?,'completed',FALSE,'codingagent',2,?)")
        .bind(Uuid::new_v4()).bind(c.manager.session).bind(serde_json::to_string(&action).unwrap())
        .execute(&f.ledger.pool).await.unwrap();
    assert!(f.ledger.manager_history().await.is_err());
    assert!(f.ledger.active().await.is_err());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn actual_stdio_engine_round_trip_and_repeat_is_not_replayed() {
    let f = fixture().await;
    let (client, server) = tokio::io::duplex(16 * 1024);
    let (input, output) = tokio::io::split(server);
    let engine = f.engine.clone();
    let caller = f.caller;
    let task = tokio::spawn(async move {
        serve(BufReader::new(input), output, move |r| {
            let engine = engine.clone();
            async move { engine.handle(caller, r).await }
        })
        .await
    });
    let (mut read, mut write) = tokio::io::split(client);
    let mut bytes = serde_json::to_vec(&request(1, TOOL)).unwrap();
    bytes.push(b'\n');
    write.write_all(&bytes).await.unwrap();
    write.write_all(&bytes).await.unwrap();
    write.shutdown().await.unwrap();
    let mut replies = String::new();
    read.read_to_string(&mut replies).await.unwrap();
    task.await.unwrap().unwrap();
    let replies: Vec<Value> = replies
        .lines()
        .map(|v| serde_json::from_str(v).unwrap())
        .collect();
    assert_eq!(replies.len(), 2);
    assert!(replies[0].get("result").is_some());
    assert!(replies[1].get("error").is_some());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn concurrent_requests_and_ordinary_input_share_admission() {
    let f = fixture().await;
    let (a, b) = tokio::join!(
        f.engine.handle(f.caller, request(1, TOOL)),
        f.engine.handle(f.caller, request(2, TOOL))
    );
    assert_eq!(usize::from(a.is_ok()) + usize::from(b.is_ok()), 1);
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 1);
    admission::run(f.ledger.end("suspended", "new_or_ambiguous_input"))
        .await
        .unwrap();
    assert!(f.engine.handle(f.caller, request(3, TOOL)).await.is_err());
}

#[tokio::test]
async fn wrong_caller_stopped_caller_target_prompt_and_metadata_fail_closed() {
    let f = fixture().await;
    assert!(
        f.engine
            .handle(Uuid::new_v4(), request(1, TOOL))
            .await
            .is_err()
    );
    for field in ["target", "prompt", "owner_authorized", "_meta"] {
        let mut r = request(2, TOOL);
        r["params"]["arguments"][field] = json!("synthetic");
        assert!(f.engine.handle(f.caller, r).await.is_err());
    }
    let mut r = request(3, TOOL);
    r["params"]["_meta"] = json!({"owner_authorized":true});
    assert!(f.engine.handle(f.caller, r).await.is_err());
    sqlx::query("UPDATE execution_processes SET status='killed' WHERE id=?")
        .bind(f.caller)
        .execute(&f.ledger.pool)
        .await
        .unwrap();
    assert!(f.engine.handle(f.caller, request(4, TOOL)).await.is_err());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn amendment_profile_failure_and_unrelated_figma_actions_cannot_dispatch() {
    let f = fixture().await;
    assert!(
        f.ledger
            .caller(
                f.caller,
                &(
                    f.ledger.contract.manager.thread.clone(),
                    "turn".into(),
                    "other-model".into(),
                    "high".into(),
                    "codex_cli_rs/0.159.2 (synthetic)".into()
                )
            )
            .await
            .is_err()
    );
    for name in [
        "figma.update",
        "run_session_prompt",
        "create_grant",
        "renew_grant",
        "reactivate_grant",
    ] {
        assert!(f.engine.handle(f.caller, request(1, name)).await.is_err());
    }
    f.runtime.failed_guard.store(true, Ordering::SeqCst);
    assert!(f.engine.handle(f.caller, request(2, TOOL)).await.is_err());
    let c = &f.ledger.contract;
    let goal = NativeGoal {
        goal_id: c.goal_id.clone(),
        thread_id: c.manager.thread.clone(),
        objective: "Unverified wider amendment".into(),
        status: "active".into(),
        created_at: c.goal_created_at,
    };
    assert!(f.ledger.goal(&goal).await.is_err());
    assert!(f.ledger.active().await.is_err());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn revocation_and_review_readiness_are_durable_and_terminal() {
    for terminal in [REVOKE, READY] {
        let f = fixture().await;
        f.engine
            .handle(f.caller, request(1, terminal))
            .await
            .unwrap();
        let reopened = Ledger::adopt(f.ledger.pool.clone(), f.ledger.contract.clone())
            .await
            .unwrap();
        assert!(reopened.active().await.is_err());
        assert!(f.engine.handle(f.caller, request(2, TOOL)).await.is_err());
        assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 0);
        let mut amended = f.ledger.contract.clone();
        amended.instructions.push_str(" broaden");
        assert!(Ledger::adopt(f.ledger.pool.clone(), amended).await.is_err());
    }
}

#[tokio::test]
async fn uncertain_dispatch_requires_real_receipt_reconciliation_after_restart() {
    let f = fixture().await;
    f.runtime.lose_reply.store(true, Ordering::SeqCst);
    assert!(f.engine.handle(f.caller, request(1, TOOL)).await.is_err());
    let reopened = Ledger::adopt(f.ledger.pool.clone(), f.ledger.contract.clone())
        .await
        .unwrap();
    reopened.reconcile().await.unwrap();
    assert!(f.engine.handle(f.caller, request(2, TOOL)).await.is_err());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 1);
    sqlx::query("UPDATE execution_processes SET status='completed',exit_code=0 WHERE session_id=?")
        .bind(f.ledger.contract.worker.session)
        .execute(&f.ledger.pool)
        .await
        .unwrap();
    reopened.reconcile().await.unwrap();
    f.runtime.lose_reply.store(false, Ordering::SeqCst);
    assert!(f.engine.handle(f.caller, request(3, TOOL)).await.is_ok());
    assert_eq!(f.runtime.calls.load(Ordering::SeqCst), 2);
    assert!(f.engine.handle(f.caller, request(1, TOOL)).await.is_err());
}
