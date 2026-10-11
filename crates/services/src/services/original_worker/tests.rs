use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use executors::{
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
    sqlx::raw_sql("CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,exit_code INTEGER,dropped BOOLEAN,run_reason TEXT,created_at INTEGER);").execute(&pool).await.unwrap();
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
        "INSERT INTO execution_processes VALUES (?,?,'running',NULL,FALSE,'codingagent',1)",
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
