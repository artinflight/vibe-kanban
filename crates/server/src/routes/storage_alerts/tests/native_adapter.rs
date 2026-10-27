//! Test-only HTTP seam for the pinned, independently owned Operations adapter.
//! No listener/control route is compiled into or mounted by the product router.
use axum::routing::get;
use serde_json::{Value, json};

use super::*;

type ControlState = (FixtureDeployment, OwnerBinding);

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Control {
    operation: String,
}

pub(super) async fn state(State((d, b)): State<ControlState>) -> Json<Value> {
    let execution_count: i64 =
        sqlx::query_scalar("SELECT count(*) FROM execution_processes WHERE session_id=?")
            .bind(b.session_id)
            .fetch_one(&d.db().pool)
            .await
            .unwrap();
    let prompt: Option<String> = sqlx::query_scalar(
        "SELECT cat.prompt FROM coding_agent_turns cat JOIN execution_processes ep ON ep.id=cat.execution_process_id WHERE ep.session_id=? ORDER BY ep.created_at DESC LIMIT 1",
    ).bind(b.session_id).fetch_optional(&d.db().pool).await.unwrap().flatten();
    Json(json!({
        "launches": d.container.launches.load(Ordering::SeqCst),
        "server_pid":std::process::id(),
        "server_start_ticks":super::modular_adapter::process_start_ticks(),
        "queued": d.queue.get_status(b.session_id),
        "execution_count": execution_count,
        "latest_prompt": prompt,
    }))
}

pub(super) async fn control(
    State((d, b)): State<ControlState>,
    Json(command): Json<Control>,
) -> Result<Json<Value>, axum::http::StatusCode> {
    match command.operation.as_str() {
        "queue_user" => {
            d.queue.queue_for_capacity(
                b.session_id,
                DraftFollowUpData {
                    message: "synthetic queued user".into(),
                    executor_config: b.executor_config.clone(),
                },
            );
        }
        "clear_queue" => {
            d.queue.cancel_queued(b.session_id);
        }
        "busy" => {
            let process = ExecutionProcess::create(
                &d.db().pool,
                &CreateExecutionProcess {
                    session_id: b.session_id,
                    executor_action: ExecutorAction::new(
                        ExecutorActionType::CodingAgentFollowUpRequest(
                            CodingAgentFollowUpRequest {
                                capacity: None,
                                prompt: "synthetic interrupted user".into(),
                                session_id: "synthetic-existing-thread".into(),
                                reset_to_message_id: None,
                                executor_config: b.executor_config.clone(),
                                working_dir: None,
                            },
                        ),
                        None,
                    ),
                    run_reason: ExecutionProcessRunReason::CodingAgent,
                },
                Uuid::new_v4(),
                &[],
            )
            .await
            .unwrap();
            CodingAgentTurn::create(
                &d.db().pool,
                &CreateCodingAgentTurn {
                    execution_process_id: process.id,
                    prompt: Some("synthetic interrupted user".into()),
                },
                Uuid::new_v4(),
            )
            .await
            .unwrap();
        }
        "complete" | "interrupt" => {
            let complete = command.operation == "complete";
            sqlx::query("UPDATE coding_agent_turns SET summary=? WHERE execution_process_id IN (SELECT id FROM execution_processes WHERE session_id=? AND status='running')")
                .bind(if complete { "synthetic completed" } else { "synthetic partial user evidence" })
                .bind(b.session_id).execute(&d.db().pool).await.unwrap();
            sqlx::query("UPDATE execution_processes SET status=?,exit_code=? WHERE session_id=? AND status='running'")
                .bind(if complete { "completed" } else { "killed" }).bind(if complete { 0 } else { 1 })
                .bind(b.session_id).execute(&d.db().pool).await.unwrap();
        }
        _ => return Err(axum::http::StatusCode::BAD_REQUEST),
    }
    close_fixture_captures(&d.db().pool).await;
    Ok(state(State((d, b))).await)
}

async fn phase(
    d: &FixtureDeployment,
    b: &OwnerBinding,
    dir: &Path,
    phase: &str,
    driver: &Path,
    source: &str,
) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let app: Router = Router::new()
        .nest("/api", super::super::router().with_state(d.clone()))
        .merge(
            Router::new()
                .route("/__fixture", get(state).post(control))
                .with_state((d.clone(), b.clone())),
        );
    let stop = CancellationToken::new();
    let shutdown = stop.clone();
    let server = tokio::spawn(async move {
        axum::serve(listener, app)
            .with_graceful_shutdown(shutdown.cancelled_owned())
            .await
            .unwrap();
    });
    let descriptor = dir.join("adapter-descriptor.json");
    std::fs::write(
        &descriptor,
        serde_json::to_vec(&json!({
            "fixture_protocol": "storage-native-fixture-v1",
            "phase": phase,
            "base_url": format!("http://{address}/api"),
            "control_url": format!("http://{address}/__fixture"),
            "binding": {
                "workspace_id": b.workspace_id,
                "session_id": b.session_id,
                "executor_config_sha256": admission::fingerprint(&b.executor_config),
            },
            "max_validation_age_seconds": b.max_validation_age_seconds,
            "state_file": dir.join("adapter-journal.json"),
        }))
        .unwrap(),
    )
    .unwrap();
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(60),
        tokio::process::Command::new("python3")
            .arg("-B")
            .arg(driver)
            .arg(&descriptor)
            .kill_on_drop(true)
            .output(),
    )
    .await
    .expect("Bounded isolated adapter phase")
    .unwrap();
    stop.cancel();
    tokio::time::timeout(std::time::Duration::from_secs(5), server)
        .await
        .unwrap()
        .unwrap();
    assert!(
        output.status.success(),
        "Adapter {phase}: {}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let evidence: Value =
        serde_json::from_slice(&output.stdout).expect("Bounded JSON driver evidence");
    assert_eq!(evidence["fixture_protocol"], "storage-native-fixture-v1");
    assert_eq!(evidence["phase"], phase);
    assert_eq!(evidence["status"], "passed");
    let checks = evidence["evidence"]
        .as_array()
        .expect("Named completed scenarios");
    assert_eq!(evidence["checks"].as_u64().unwrap(), checks.len() as u64);
    let required = if phase == "initial" {
        &[
            "native_queue_deferral_strict_fresh_same_intent_retry",
            "execution_success_does_not_recover_pressure",
            "native_busy_deferral_and_ordinary_interrupted_turn_recovery",
            "real_commit_lost_response_restart_GET_only",
            "competing_first_deliveries_and_accepted_replay_same_execution",
            "concurrent_duplicate_native_POST_one_execution",
        ][..]
    } else {
        &["real_native_WAL_reopen_exact_accepted_binding_GET_only"][..]
    };
    for check in required {
        assert!(checks.iter().any(|value| value.as_str() == Some(*check)));
    }
    println!("NATIVE_STORAGE_ADAPTER_EVIDENCE source={source} {evidence}");
}

pub(super) async fn exercise() {
    let driver = PathBuf::from(
        std::env::var_os("VK_STORAGE_ADAPTER_DRIVER")
            .expect("Exact reviewed hosted adapter driver"),
    );
    let source = std::env::var("VK_STORAGE_ADAPTER_SOURCE").expect("Pinned Operations source");
    assert!(source.len() == 40 && source.bytes().all(|b| b.is_ascii_hexdigit()));
    let (dir, d, b, _) = fixture().await;
    std::fs::write(
        std::env::var_os("VK_STORAGE_ALERT_OWNER_FILE").unwrap(),
        serde_json::to_vec(&b).unwrap(),
    )
    .unwrap();
    phase(&d, &b, dir.path(), "initial", &driver, &source).await;
    let launches = d.container.launches.load(Ordering::SeqCst);
    assert!(launches > 0);
    assert!(!d.queue.has_queued(b.session_id));
    let execution_count: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(&d.db().pool)
        .await
        .unwrap();
    d.db().pool.close().await;
    // A new pool, new deployment, new queue and new HTTP listener use the exact
    // same migrated WAL database. No snapshot or bounded history replacement.
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(4)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new().filename(dir.path().join("isolated.sqlite")),
        )
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let db = DBService { pool };
    let config = d.config.clone();
    let reopened = FixtureDeployment {
        container: Arc::new(FixtureContainer {
            db: db.clone(),
            git: git::GitService::new(),
            stores: Arc::new(RwLock::new(HashMap::new())),
            notifications: NotificationService::new(config.clone()),
            approvals: Approvals::new(),
            launches: AtomicUsize::new(0),
            fail_spawn: std::sync::atomic::AtomicBool::new(false),
        }),
        events: EventService::new(db, Arc::new(MsgStore::new()), Arc::new(RwLock::new(0))),
        queue: QueuedMessageService::new(),
        config,
    };
    phase(&reopened, &b, dir.path(), "reopened", &driver, &source).await;
    assert_eq!(reopened.container.launches.load(Ordering::SeqCst), 0);
    let after_reopen: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(&reopened.db().pool)
        .await
        .unwrap();
    assert_eq!(after_reopen, execution_count);
    reopened.db().pool.close().await;
}
