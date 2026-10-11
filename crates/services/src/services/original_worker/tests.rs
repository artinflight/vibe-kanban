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

struct ActivationGuard(Arc<Ledger>, Uuid);
impl std::fmt::Debug for ActivationGuard {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("SyntheticActivationGuard")
    }
}
#[executors::original_worker::async_trait]
impl executors::original_worker::LaunchGuard for ActivationGuard {
    fn worker(&self) -> bool {
        true
    }
    async fn resolved(
        &self,
        _: &executors::executors::CodingAgent,
        _: &ExecutorConfig,
    ) -> io::Result<()> {
        Ok(())
    }
    async fn receipt_uncertain(&self) -> io::Result<()> {
        self.0.native_receipt_uncertain(self.1).await
    }
    async fn activation(
        &self,
        _: &str,
        input: Option<&str>,
    ) -> io::Result<executors::original_worker::ActivationFence> {
        self.0
            .activation_fence(async {
                if let Some(input) = input {
                    self.0.activate_input(self.1, input).await?;
                }
                Ok(())
            })
            .await
    }
}

#[tokio::test]
async fn final_native_rpc_and_revocation_have_one_ordered_commit_boundary() {
    use std::process::Stdio;

    use executors::{
        env::RepoContext,
        executors::codex::{
            client::{AppServerClient, LogWriter},
            jsonrpc::{ExitSignalSender, JsonRpcPeer},
        },
    };
    use tokio::io::AsyncBufReadExt;
    use tokio_util::sync::CancellationToken;
    for revoke_first in [true, false] {
        let f = fixture().await;
        f.engine.handle(f.caller, request(1, TOOL)).await.unwrap();
        let execution: Uuid = sqlx::query_scalar("SELECT execution FROM bounded_worker_attempts")
            .fetch_one(&f.ledger.pool)
            .await
            .unwrap();
        let release = f._directory.path().join("release-native-rpc");
        let mut child = tokio::process::Command::new("python3").args(["-u", "-c", r#"
import json,sys,time,os
for line in sys.stdin:
    q=json.loads(line)
    print('native-activation-entered',file=sys.stderr,flush=True)
    while not os.path.exists(sys.argv[1]): time.sleep(.005)
    print(json.dumps({'id':q['id'],'result':{'turn':{'id':'synthetic-turn','items':[],'status':'inProgress','error':None}}}),flush=True)
"#]).arg(&release).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).kill_on_drop(true).spawn().unwrap();
        let mut events = BufReader::new(child.stderr.take().unwrap()).lines();
        let cancel = CancellationToken::new();
        let client = AppServerClient::new(
            LogWriter::new(tokio::io::sink()),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        client.set_original_worker_guard(Arc::new(ActivationGuard(f.ledger.clone(), execution)));
        let (tx, _rx) = tokio::sync::oneshot::channel();
        client.connect(JsonRpcPeer::spawn(
            child.stdin.take().unwrap(),
            child.stdout.take().unwrap(),
            client.clone(),
            ExitSignalSender::new(tx),
            cancel.clone(),
        ));
        if revoke_first {
            f.ledger
                .end("revoked", "synthetic_terminal_decision")
                .await
                .unwrap();
        }
        let start = tokio::spawn({
            let client = client.clone();
            async move {
                client.turn_start_with_mode("synthetic-thread".into(),serde_json::from_value(json!([{"type":"text","text":"Synthetic fixed native input","text_elements":[]}])).unwrap(),None).await
            }
        });
        if revoke_first {
            assert!(start.await.unwrap().is_err());
            assert!(
                tokio::time::timeout(std::time::Duration::from_millis(100), events.next_line())
                    .await
                    .is_err(),
                "revocation won: no native RPC sent"
            );
        } else {
            assert_eq!(
                tokio::time::timeout(std::time::Duration::from_secs(3), events.next_line())
                    .await
                    .unwrap()
                    .unwrap()
                    .as_deref(),
                Some("native-activation-entered")
            );
            let ending = tokio::spawn({
                let ledger = f.ledger.clone();
                async move { ledger.end("revoked", "synthetic_terminal_decision").await }
            });
            tokio::task::yield_now().await;
            assert!(
                !ending.is_finished(),
                "terminal acknowledgement must wait for in-flight activation"
            );
            tokio::fs::write(&release, b"synthetic release")
                .await
                .unwrap();
            start.await.unwrap().unwrap();
            ending.await.unwrap().unwrap();
            assert!(client.turn_start_with_mode("synthetic-thread".into(),serde_json::from_value(json!([{"type":"text","text":"Synthetic repeated activation","text_elements":[]}])).unwrap(),None).await.is_err());
        }
        cancel.cancel();
        child.kill().await.unwrap();
        child.wait().await.unwrap();
        let activated: i64 = sqlx::query_scalar("SELECT activated FROM bounded_worker_attempts")
            .fetch_one(&f.ledger.pool)
            .await
            .unwrap();
        assert_eq!(activated, i64::from(!revoke_first));
        let recovered = Ledger::adopt(f.ledger.pool.clone(), f.ledger.contract.clone())
            .await
            .unwrap();
        assert!(
            recovered.active().await.is_err(),
            "terminal decision survives restart"
        );
    }
}

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
    sqlx::raw_sql(include_str!(
        "../../../../db/migrations/20261011130000_bounded_native_activation.sql"
    ))
    .execute(&pool)
    .await
    .unwrap();
    sqlx::raw_sql("CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,exit_code INTEGER,dropped BOOLEAN,run_reason TEXT,created_at INTEGER,executor_action TEXT);").execute(&pool).await.unwrap();
    let config: ExecutorConfig = serde_json::from_value(json!({"executor":"CODEX","variant":"DEFAULT","model_id":"gpt-6.1-sol","reasoning_id":"high"})).unwrap();
    let coverage = start_input_coverage(&pool).await.unwrap();
    let identity = || Identity {
        input_seal: inputs::InputSeal {
            coverage_id: coverage,
            backend_sequence: 0,
            rollout: "/synthetic/rollout.jsonl".into(),
            records: 0,
            prefix_digest: digest(b"[]"),
        },
        session: Uuid::new_v4(),
        workspace: Uuid::new_v4(),
        thread: Uuid::new_v4().to_string(),
        root: "/synthetic/worktree".into(),
        working_dir: None,
        config: config.clone(),
        profile_digest: "c".repeat(64),
        task: None,
        repositories: vec![Uuid::new_v4()],
    };
    let caller = Uuid::new_v4();
    let contract = Contract { recommend: serde_json::from_value(json!({"mode":"shadow"})).unwrap(), id: Uuid::new_v4(), manager: identity(), worker: identity(), goal_id: "synthetic-goal".into(), goal_created_at: 10, objective: "Synthetic marketing revision".into(), revision: "synthetic-owner-revision".into(), instructions: "Retain synthetic image assets and all Figma/AE review gates; revise marketing with grey date placeholders.".into(), owner_evidence_digest: "a".repeat(64), manager_anchor: caller, worker_anchor: Uuid::new_v4(), assets: vec![AssetPin { path: "/synthetic/assets/image.png".into(), sha256: "b".repeat(64) }] };
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

#[tokio::test]
async fn effective_profile_pin_checks_actual_launch_settings_without_logging_them() {
    let f = fixture().await;
    let mut identity = f.ledger.contract.worker.clone();
    identity.profile_digest = effective_profile_digest(&identity.config).unwrap();
    verify_profile(&identity).unwrap();
    identity.config.model_id = Some("synthetic-unapproved-model".into());
    assert!(verify_profile(&identity).is_err());
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
async fn durable_steering_before_adoption_and_dropped_resume_cannot_amend_authority() {
    let f = fixture().await;
    record_input(&f.ledger.pool, f.ledger.contract.manager.session, false)
        .await
        .unwrap();
    // No executor_action update is necessary to detect this input.
    assert!(
        f.ledger
            .native_inputs(&f.ledger.contract.manager)
            .await
            .is_err()
    );
    assert!(f.ledger.active().await.is_err());
    let f = fixture().await;
    let mut action = worker_action(&f.ledger.contract);
    if let ExecutorActionType::CodingAgentFollowUpRequest(a) = &mut action.typ {
        a.prompt = "/goal resume".into();
        a.session_id = f.ledger.contract.manager.thread.clone();
        a.executor_config = f.ledger.contract.manager.config.clone();
    }
    sqlx::query("INSERT INTO execution_processes(id,session_id,status,dropped,run_reason,created_at,executor_action) VALUES (?,?,'completed',TRUE,'codingagent',2,?)")
        .bind(Uuid::new_v4()).bind(f.ledger.contract.manager.session).bind(serde_json::to_string(&action).unwrap()).execute(&f.ledger.pool).await.unwrap();
    assert!(f.ledger.manager_history().await.is_err());
    assert!(f.ledger.active().await.is_err());
}

#[tokio::test]
async fn legacy_or_forged_input_coverage_cannot_be_adopted() {
    let f = fixture().await;
    let mut contract = f.ledger.contract.clone();
    contract.id = Uuid::new_v4();
    contract.manager.input_seal.coverage_id = Uuid::new_v4();
    assert!(
        Ledger::adopt(f.ledger.pool.clone(), contract)
            .await
            .is_err()
    );
    let mut contract = f.ledger.contract.clone();
    contract.id = Uuid::new_v4();
    contract.worker.input_seal.backend_sequence = 1000;
    assert!(
        Ledger::adopt(f.ledger.pool.clone(), contract)
            .await
            .is_err()
    );
    sqlx::query("DELETE FROM bounded_native_input_coverage")
        .execute(&f.ledger.pool)
        .await
        .unwrap();
    assert!(
        Ledger::adopt(f.ledger.pool.clone(), f.ledger.contract.clone())
            .await
            .is_err()
    );
    assert!(
        f.ledger
            .native_inputs(&f.ledger.contract.manager)
            .await
            .is_err()
    );
    assert!(f.ledger.active().await.is_err());
    // No future runtime mutation can convert an unverified old capture into consent.
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

#[tokio::test]
async fn active_workspace_aliases_ignore_archive_flags_but_not_unknown_ownership() {
    let f = fixture().await;
    let pool = &f.ledger.pool;
    sqlx::raw_sql("CREATE TABLE workspaces(id BLOB PRIMARY KEY,container_ref TEXT,archived BOOLEAN,worktree_deleted BOOLEAN)").execute(pool).await.unwrap();
    let root = f._directory.path().join("worker");
    let manager = f._directory.path().join("manager");
    tokio::fs::create_dir_all(&root).await.unwrap();
    tokio::fs::create_dir_all(&manager).await.unwrap();
    let mut contract = f.ledger.contract.clone();
    contract.id = Uuid::new_v4();
    contract.worker.root = root.clone();
    let ledger = Ledger::adopt(pool.clone(), contract).await.unwrap();
    sqlx::query("INSERT INTO workspaces VALUES (?,?,FALSE,FALSE)")
        .bind(ledger.contract.manager.workspace)
        .bind(manager.to_str().unwrap())
        .execute(pool)
        .await
        .unwrap();
    // Missing unrelated idle history must not block admission.
    sqlx::query("INSERT INTO workspaces VALUES (?,?,TRUE,TRUE)")
        .bind(Uuid::new_v4())
        .bind(f._directory.path().join("missing-idle").to_str().unwrap())
        .execute(pool)
        .await
        .unwrap();
    ledger.workspace_idle(&[], None).await.unwrap();
    let workspace = Uuid::new_v4();
    let session = Uuid::new_v4();
    let process = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces VALUES (?,?,FALSE,FALSE)")
        .bind(workspace)
        .bind(root.to_str().unwrap())
        .execute(pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO sessions VALUES (?,?)")
        .bind(session)
        .bind(workspace)
        .execute(pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO execution_processes(id,session_id,status,dropped,run_reason) VALUES (?,?,'completed',FALSE,'codingagent')").bind(process).bind(session).execute(pool).await.unwrap();
    for (archived, deleted) in [(false, false), (true, false), (false, true), (true, true)] {
        sqlx::query("UPDATE workspaces SET archived=?,worktree_deleted=? WHERE id=?")
            .bind(archived)
            .bind(deleted)
            .bind(workspace)
            .execute(pool)
            .await
            .unwrap();
        assert!(ledger.workspace_idle(&[session], None).await.is_err());
        sqlx::query("UPDATE execution_processes SET status='running' WHERE id=?")
            .bind(process)
            .execute(pool)
            .await
            .unwrap();
        assert!(ledger.workspace_idle(&[], None).await.is_err());
        // Unknown active roots, including a NULL root, cannot establish exclusivity.
        for missing in [
            Some(
                f._directory
                    .path()
                    .join("missing-active")
                    .to_str()
                    .unwrap()
                    .to_owned(),
            ),
            None,
        ] {
            sqlx::query("UPDATE workspaces SET container_ref=? WHERE id=?")
                .bind(missing)
                .bind(workspace)
                .execute(pool)
                .await
                .unwrap();
            assert!(ledger.workspace_idle(&[], None).await.is_err());
            sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
                .bind(process)
                .execute(pool)
                .await
                .unwrap();
            assert!(ledger.workspace_idle(&[session], None).await.is_err());
            ledger.workspace_idle(&[], None).await.unwrap();
            sqlx::query("UPDATE execution_processes SET status='running' WHERE id=?")
                .bind(process)
                .execute(pool)
                .await
                .unwrap();
        }
        sqlx::query("UPDATE workspaces SET container_ref=? WHERE id=?")
            .bind(root.to_str().unwrap())
            .bind(workspace)
            .execute(pool)
            .await
            .unwrap();
        sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
            .bind(process)
            .execute(pool)
            .await
            .unwrap();
    }
}

#[tokio::test]
async fn silent_native_receipts_release_fence_and_persist_uncertain_without_replay() {
    use std::process::Stdio;

    use executors::{
        env::RepoContext,
        executors::codex::{
            client::{AppServerClient, LogWriter},
            jsonrpc::{ExitSignalSender, JsonRpcPeer},
        },
    };
    use tokio::io::AsyncBufReadExt;
    use tokio_util::sync::CancellationToken;
    for silence in ["thread/goal/get", "thread/resume", "turn/start"] {
        let f = fixture().await;
        f.engine.handle(f.caller, request(1, TOOL)).await.unwrap();
        let execution: Uuid = sqlx::query_scalar("SELECT execution FROM bounded_worker_attempts")
            .fetch_one(&f.ledger.pool)
            .await
            .unwrap();
        let late = f._directory.path().join("late-native-reply");
        let mut child = tokio::process::Command::new("python3").args(["-u","-c",r#"
import json,sys,time,os
for line in sys.stdin:
    q=json.loads(line)
    if q['method']!=sys.argv[1]:
        print(json.dumps({'id':q['id'],'result':{'goal':None}}),flush=True)
        continue
    print(q['method'],file=sys.stderr,flush=True)
    while not os.path.exists(sys.argv[2]): time.sleep(.005)
    print(json.dumps({'id':q['id'],'result':{'turn':{'id':'synthetic-late','items':[],'status':'inProgress','error':None}}}),flush=True)
    print('late-reply',file=sys.stderr,flush=True)
"#]).arg(silence).arg(&late).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).kill_on_drop(true).spawn().unwrap();
        let mut events = BufReader::new(child.stderr.take().unwrap()).lines();
        let cancel = CancellationToken::new();
        let client = AppServerClient::new(
            LogWriter::new(tokio::io::sink()),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        client.set_original_worker_guard(Arc::new(ActivationGuard(f.ledger.clone(), execution)));
        let (tx, _rx) = tokio::sync::oneshot::channel();
        client.connect(JsonRpcPeer::spawn(
            child.stdin.take().unwrap(),
            child.stdout.take().unwrap(),
            client.clone(),
            ExitSignalSender::new(tx),
            cancel.clone(),
        ));
        let starting = tokio::spawn({
            let client = client.clone();
            let silence = silence.to_owned();
            async move {
                if silence == "turn/start" {
                    client.turn_start_with_mode("synthetic-thread".into(),serde_json::from_value(json!([{"type":"text","text":"Synthetic fixed native input","text_elements":[]}])).unwrap(),None).await.map(|_|())
                } else {
                    let params =
                        serde_json::from_value(json!({"threadId":"synthetic-thread"})).unwrap();
                    client.thread_resume(params).await.map(|_| ())
                }
            }
        });
        assert_eq!(events.next_line().await.unwrap().as_deref(), Some(silence));
        let ending = tokio::spawn({
            let ledger = f.ledger.clone();
            async move { ledger.end("revoked", "synthetic_owner_revocation").await }
        });
        tokio::task::yield_now().await;
        assert!(!ending.is_finished());
        // Advance only after the connected peer confirms delivery, so OS process
        // scheduling cannot masquerade as a silence/receipt timeout.
        tokio::time::pause();
        tokio::time::advance(std::time::Duration::from_secs(11)).await;
        // SQLite's driver has OS-backed work; paused Tokio time must not auto-
        // advance its pool deadlines while waiting for durable acknowledgement.
        tokio::time::resume();
        assert!(starting.await.unwrap().is_err());
        ending.await.unwrap().unwrap();
        let (state, activated): (String, i64) =
            sqlx::query_as("SELECT state,activated FROM bounded_worker_attempts")
                .fetch_one(&f.ledger.pool)
                .await
                .unwrap();
        assert_eq!(state, "uncertain");
        assert_eq!(activated, i64::from(silence == "turn/start"));
        assert!(f.engine.handle(f.caller, request(2, TOOL)).await.is_err());
        tokio::fs::write(&late, b"synthetic late receipt")
            .await
            .unwrap();
        assert_eq!(
            events.next_line().await.unwrap().as_deref(),
            Some("late-reply")
        );
        let recovered = Ledger::adopt(f.ledger.pool.clone(), f.ledger.contract.clone())
            .await
            .unwrap();
        assert!(recovered.active().await.is_err());
        let state: String = sqlx::query_scalar("SELECT state FROM bounded_worker_attempts")
            .fetch_one(&f.ledger.pool)
            .await
            .unwrap();
        assert_eq!(state, "uncertain");
        cancel.cancel();
        child.kill().await.unwrap();
        child.wait().await.unwrap();
    }
}
