use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use db::models::{
    execution_process::{
        CreateExecutionProcess, ExecutionProcess, ExecutionProcessRunReason, ExecutionProcessStatus,
    },
    scratch::DraftFollowUpData,
    session::{CreateSession, Session},
    workspace::{CreateWorkspace, Workspace},
};
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::{BaseCodingAgent, ExecutorError},
};

use super::*;

async fn fixture() -> (SqlitePool, QueuedMessageService, OwnerBinding, Request) {
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    fixture_in(pool).await
}

async fn fixture_in(pool: SqlitePool) -> (SqlitePool, QueuedMessageService, OwnerBinding, Request) {
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let w = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "isolated-storage".into(),
            name: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let s = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: None,
        },
        Uuid::new_v4(),
        w.id,
    )
    .await
    .unwrap();
    let config = ExecutorConfig::new(BaseCodingAgent::Codex);
    let binding = OwnerBinding {
        workspace_id: w.id,
        session_id: s.id,
        executor_config: config.clone(),
        max_validation_age_seconds: 60,
        delegation_journal_dir: None,
    };
    let intent = Intent {
        workspace_id: w.id,
        session_id: s.id,
        incidents: vec![Incident {
            incident_id: Uuid::new_v4(),
            filesystem_uuid: "synthetic-volume".into(),
            policy: "fixture-critical".into(),
            opened_at: Utc::now() - chrono::Duration::minutes(1),
        }],
        receipt_ref: "synthetic-private-receipt".into(),
        prompt: "Review verified synthetic pressure using existing authority".into(),
        executor_config_sha256: fingerprint(&config),
    };
    let r = Request {
        protocol: PROTOCOL.into(),
        batch_id: Uuid::new_v4(),
        attempt_id: Uuid::new_v4(),
        intent_sha256: fingerprint(&intent),
        validation: Validation {
            observed_at: Utc::now(),
            eligible_incident_ids: intent.incidents.iter().map(|i| i.incident_id).collect(),
            evidence_sha256: "a".repeat(64),
        },
        intent,
    };
    (pool, QueuedMessageService::new(), binding, r)
}

async fn create(
    pool: &SqlitePool,
    session: Uuid,
    id: Uuid,
) -> Result<ExecutionProcess, ContainerError> {
    Ok(ExecutionProcess::create(
        pool,
        &CreateExecutionProcess {
            session_id: session,
            executor_action: ExecutorAction::new(
                ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                    prompt: "Synthetic only".into(),
                    executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                    working_dir: None,
                }),
                None,
            ),
            run_reason: ExecutionProcessRunReason::CodingAgent,
        },
        id,
        &[],
    )
    .await?)
}
async fn bind(pool: &SqlitePool, session: Uuid) -> Result<(), ContainerError> {
    create(
        pool,
        session,
        candidate_execution_id().expect("native reserved ID"),
    )
    .await?;
    Ok(())
}
async fn count(pool: &SqlitePool) -> i64 {
    sqlx::query_scalar("SELECT count(*) FROM execution_processes")
        .fetch_one(pool)
        .await
        .unwrap()
}
fn fresh(r: &Request) -> Request {
    let mut r = r.clone();
    r.attempt_id = Uuid::new_v4();
    r.validation.observed_at = Utc::now();
    r
}

#[tokio::test]
async fn competing_same_batch_deliveries_commit_exactly_one_execution_and_replay() {
    let (pool, q, owner, r) = fixture().await;
    let calls = AtomicUsize::new(0);
    let send = || {
        submit(&pool, &q, &owner, &r, |_| async {
            calls.fetch_add(1, Ordering::SeqCst);
            tokio::task::yield_now().await;
            bind(&pool, owner.session_id).await
        })
    };
    let (a, b) = tokio::join!(send(), send());
    let (a, b) = (a.unwrap(), b.unwrap());
    assert_eq!(a.outcome, "accepted");
    assert_eq!(b.outcome, "accepted");
    assert_eq!(
        a.receipt.unwrap().execution_id,
        b.receipt.unwrap().execution_id
    );
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    assert_eq!(count(&pool).await, 1);
    assert!(send().await.unwrap().replay);
}

#[tokio::test]
async fn competing_batches_share_owner_and_duplicate_incident_is_terminal_without_second_launch() {
    let (pool, q, owner, r) = fixture().await;
    let mut other = fresh(&r);
    other.batch_id = Uuid::new_v4();
    let (a, b) = tokio::join!(
        submit(&pool, &q, &owner, &r, |_| bind(&pool, owner.session_id)),
        submit(&pool, &q, &owner, &other, |_| bind(&pool, owner.session_id))
    );
    assert_eq!(a.unwrap().outcome, "accepted");
    let b = b.unwrap();
    assert_eq!(b.outcome, "rejected");
    assert_eq!(b.reason, "incident_already_pending");
    assert!(b.no_admission);
    assert_eq!(count(&pool).await, 1);
}

#[tokio::test]
async fn busy_owner_defers_and_distinct_unrelated_owner_does_not_veto() {
    let (pool, q, owner, r) = fixture().await;
    let busy = create(&pool, owner.session_id, Uuid::new_v4())
        .await
        .unwrap();
    let a = submit(&pool, &q, &owner, &r, |_| async {
        panic!("busy cannot launch")
    })
    .await
    .unwrap();
    assert_eq!(a.outcome, "deferred");
    assert_eq!(a.reason, "owner_busy");
    assert!(a.no_admission);
    assert!(!a.automatic_launch_queued);
    ExecutionProcess::update_completion(&pool, busy.id, ExecutionProcessStatus::Completed, Some(0))
        .await
        .unwrap();
    let unrelated = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "unrelated-nightly".into(),
            name: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let session = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: None,
        },
        Uuid::new_v4(),
        unrelated.id,
    )
    .await
    .unwrap();
    create(&pool, session.id, Uuid::new_v4()).await.unwrap();
    let retry = fresh(&r);
    assert_eq!(
        submit(&pool, &q, &owner, &retry, |_| bind(&pool, owner.session_id))
            .await
            .unwrap()
            .outcome,
        "accepted"
    );
}

#[tokio::test]
async fn memory_and_durable_queues_and_pending_user_receipts_are_preserved() {
    for kind in ["memory", "durable", "incoming", "sibling"] {
        let (pool, q, owner, r) = fixture().await;
        let session = if kind == "sibling" {
            Session::create(
                &pool,
                &CreateSession {
                    executor: Some("CODEX".into()),
                    name: None,
                },
                Uuid::new_v4(),
                owner.workspace_id,
            )
            .await
            .unwrap()
            .id
        } else {
            owner.session_id
        };
        let data = DraftFollowUpData {
            message: "User input must remain unchanged".into(),
            executor_config: owner.executor_config.clone(),
        };
        match kind {
            "memory" | "sibling" => {
                q.queue_for_capacity(session, data);
            }
            "durable" => {
                q.queue_message(session, data);
                q.persist(&pool, session).await.unwrap();
                q.cancel_queued(session);
            }
            _ => {
                sqlx::query("INSERT INTO turn_github_sync_incoming(id,session_id,workspace_id,data) VALUES (?,?,?,'private user input')").bind(Uuid::new_v4()).bind(session).bind(owner.workspace_id).execute(&pool).await.unwrap();
            }
        }
        let memory = serde_json::to_string(&q.get_status(session)).unwrap();
        let durable: Vec<(Uuid, String)> =
            sqlx::query_as("SELECT session_id,data FROM turn_github_sync_user_queue")
                .fetch_all(&pool)
                .await
                .unwrap();
        let incoming: Vec<(Uuid, String)> =
            sqlx::query_as("SELECT id,data FROM turn_github_sync_incoming")
                .fetch_all(&pool)
                .await
                .unwrap();
        let result = submit(&pool, &q, &owner, &r, |_| async {
            panic!("queued user wins")
        })
        .await
        .unwrap();
        assert_eq!(result.outcome, "deferred");
        assert_eq!(result.reason, "owner_user_work_pending");
        assert!(result.no_admission);
        assert_eq!(
            memory,
            serde_json::to_string(&q.get_status(session)).unwrap()
        );
        assert_eq!(
            durable,
            sqlx::query_as("SELECT session_id,data FROM turn_github_sync_user_queue")
                .fetch_all(&pool)
                .await
                .unwrap()
        );
        assert_eq!(
            incoming,
            sqlx::query_as("SELECT id,data FROM turn_github_sync_incoming")
                .fetch_all(&pool)
                .await
                .unwrap()
        );
        assert_eq!(count(&pool).await, 0);
    }
}

#[tokio::test]
async fn changed_intent_owner_and_fingerprint_never_alias_accepted_receipt() {
    let (pool, q, owner, r) = fixture().await;
    submit(&pool, &q, &owner, &r, |_| bind(&pool, owner.session_id))
        .await
        .unwrap();
    for field in ["prompt", "owner", "incidents", "hash"] {
        let mut changed = r.clone();
        match field {
            "prompt" => changed.intent.prompt.push('!'),
            "owner" => changed.intent.workspace_id = Uuid::new_v4(),
            "incidents" => changed.intent.incidents[0].incident_id = Uuid::new_v4(),
            _ => changed.intent_sha256 = "b".repeat(64),
        }
        let result = submit(&pool, &q, &owner, &changed, |_| async {
            panic!("conflict")
        })
        .await
        .unwrap();
        assert_eq!(result.outcome, "uncertain");
        assert!(!result.no_admission);
        assert!(result.receipt.is_none());
    }
    assert_eq!(count(&pool).await, 1);
}

#[tokio::test]
async fn native_capacity_deferral_is_positive_and_requires_new_attempt_and_fresh_validation() {
    let (pool, q, owner, r) = fixture().await;
    let a = submit(&pool, &q, &owner, &r, |_| async {
        Err(ContainerError::ExecutorError(
            ExecutorError::ExecutionLimitReached {
                active: 8,
                limit: 8,
            },
        ))
    })
    .await
    .unwrap();
    assert_eq!(a.outcome, "deferred");
    assert!(a.no_admission);
    assert!(!a.automatic_launch_queued);
    let a = submit(&pool, &q, &owner, &r, |_| async {
        panic!("same attempt cannot retry")
    })
    .await
    .unwrap();
    assert!(a.replay);
    let mut reused = r.clone();
    reused.validation.observed_at = Utc::now();
    assert_eq!(
        submit(&pool, &q, &owner, &reused, |_| async {
            panic!("attempt conflict")
        })
        .await
        .unwrap()
        .outcome,
        "uncertain"
    );
    let mut stale = fresh(&r);
    stale.validation.observed_at = r.validation.observed_at;
    assert_eq!(
        submit(&pool, &q, &owner, &stale, |_| async {
            panic!("requires newer observation")
        })
        .await
        .unwrap()
        .reason,
        "fresh_validation_required"
    );
    let retry = fresh(&r);
    assert_eq!(
        submit(&pool, &q, &owner, &retry, |_| bind(&pool, owner.session_id))
            .await
            .unwrap()
            .outcome,
        "accepted"
    );
    assert_eq!(count(&pool).await, 1);
    assert!(!q.has_queued(owner.session_id));
}

#[tokio::test]
async fn timeout_after_commit_is_accepted_and_lookup_does_not_depend_on_history_or_queue() {
    let (pool, q, owner, r) = fixture().await;
    let send = submit(&pool, &q, &owner, &r, |_| async {
        bind(&pool, owner.session_id).await?;
        std::future::pending::<()>().await;
        Ok(())
    });
    assert!(
        tokio::time::timeout(std::time::Duration::from_millis(50), send)
            .await
            .is_err()
    );
    let a = lookup(&pool, r.batch_id, &r.intent_sha256).await.unwrap();
    assert_eq!(a.outcome, "accepted");
    assert!(!a.no_admission);
    let id = a.receipt.unwrap().execution_id.unwrap();
    sqlx::query("UPDATE execution_processes SET dropped=TRUE WHERE id=?")
        .bind(id)
        .execute(&pool)
        .await
        .unwrap();
    assert_eq!(
        lookup(&pool, r.batch_id, &r.intent_sha256)
            .await
            .unwrap()
            .receipt
            .unwrap()
            .execution_id,
        Some(id)
    );
    assert!(
        submit(&pool, &q, &owner, &r, |_| async {
            panic!("accepted replay")
        })
        .await
        .unwrap()
        .replay
    );
    assert_eq!(count(&pool).await, 1);
}

#[tokio::test]
async fn cancellation_fences_inflight_late_insert_and_retains_terminal_tombstone() {
    let (pool, q, owner, r) = fixture().await;
    let candidate = Arc::new(tokio::sync::Mutex::new(None));
    assert!(
        tokio::time::timeout(
            std::time::Duration::from_millis(50),
            submit(&pool, &q, &owner, &r, |_| async {
                *candidate.lock().await = candidate_execution_id();
                std::future::pending::<()>().await;
                Ok(())
            })
        )
        .await
        .is_err()
    );
    let a = lookup(&pool, r.batch_id, &r.intent_sha256).await.unwrap();
    assert_eq!(a.outcome, "uncertain");
    assert!(!a.no_admission);
    assert!(owner_reserved(&pool, owner.workspace_id).await.unwrap());
    let rejected = cancel(&pool, r.batch_id, &r.intent_sha256).await.unwrap();
    assert_eq!(rejected.reason, "cancelled_tombstone");
    assert!(rejected.no_admission);
    assert!(!owner_reserved(&pool, owner.workspace_id).await.unwrap());
    assert!(
        create(&pool, owner.session_id, candidate.lock().await.unwrap())
            .await
            .is_err(),
        "late original dispatch is fenced"
    );
    assert_eq!(count(&pool).await, 0);
    assert_eq!(
        submit(&pool, &q, &owner, &fresh(&r), |_| async {
            panic!("terminal tombstone")
        })
        .await
        .unwrap()
        .reason,
        "cancelled_tombstone"
    );
    let mut regroup = fresh(&r);
    regroup.batch_id = Uuid::new_v4();
    assert_eq!(
        submit(&pool, &q, &owner, &regroup, |_| bind(
            &pool,
            owner.session_id
        ))
        .await
        .unwrap()
        .outcome,
        "accepted"
    );
}

#[tokio::test]
async fn definite_prebinding_failure_and_failure_after_binding_are_distinct() {
    for after in [false, true] {
        let (pool, q, owner, r) = fixture().await;
        let result = submit(&pool, &q, &owner, &r, |_| async {
            if after {
                bind(&pool, owner.session_id).await?;
            }
            Err(ContainerError::Other(anyhow::anyhow!("synthetic failure")))
        })
        .await
        .unwrap();
        assert_eq!(result.outcome, if after { "accepted" } else { "rejected" });
        assert_eq!(result.no_admission, !after);
        assert!(!q.has_queued(owner.session_id));
    }
}

#[tokio::test]
async fn readonly_not_found_conflict_and_missing_execution_remain_uncertain_or_bound() {
    let (pool, q, owner, r) = fixture().await;
    assert_eq!(
        lookup(&pool, r.batch_id, &r.intent_sha256)
            .await
            .unwrap()
            .outcome,
        "uncertain"
    );
    submit(&pool, &q, &owner, &r, |_| bind(&pool, owner.session_id))
        .await
        .unwrap();
    assert!(
        !lookup(&pool, r.batch_id, &"c".repeat(64))
            .await
            .unwrap()
            .no_admission
    );
    sqlx::query("DELETE FROM execution_processes")
        .execute(&pool)
        .await
        .unwrap();
    let a = lookup(&pool, r.batch_id, &r.intent_sha256).await.unwrap();
    assert_eq!(a.outcome, "accepted");
    assert!(a.execution_status.is_none());
    assert!(a.receipt.unwrap().execution_id.is_some());
    assert!(!a.no_admission);
}

#[tokio::test]
async fn validation_rejects_changed_scope_and_stale_evidence_does_not_launch() {
    for variant in [
        "owner",
        "hash",
        "eligibility",
        "empty",
        "stale",
        "future",
        "duplicate",
    ] {
        let (pool, q, owner, mut r) = fixture().await;
        match variant {
            "owner" => r.intent.session_id = Uuid::new_v4(),
            "hash" => r.intent.executor_config_sha256 = "x".into(),
            "eligibility" => r.validation.eligible_incident_ids.clear(),
            "empty" => r.intent.prompt.clear(),
            "stale" => r.validation.observed_at -= chrono::Duration::minutes(10),
            "future" => r.validation.observed_at += chrono::Duration::minutes(10),
            _ => r.intent.incidents.push(r.intent.incidents[0].clone()),
        }
        r.intent_sha256 = fingerprint(&r.intent);
        let result = submit(&pool, &q, &owner, &r, |_| async { panic!("invalid") })
            .await
            .unwrap();
        assert!(result.no_admission);
        assert_ne!(result.outcome, "accepted");
        assert_eq!(count(&pool).await, 0);
    }
}

#[tokio::test]
async fn native_insert_respects_durable_reservation_even_outside_process_owner_lock() {
    let (pool, q, owner, r) = fixture().await;
    assert!(
        tokio::time::timeout(
            std::time::Duration::from_millis(50),
            submit(&pool, &q, &owner, &r, |_| async {
                std::future::pending::<()>().await;
                Ok(())
            })
        )
        .await
        .is_err()
    );
    assert!(
        create(&pool, owner.session_id, Uuid::new_v4())
            .await
            .is_err()
    );
    cancel(&pool, r.batch_id, &r.intent_sha256).await.unwrap();
    assert!(
        create(&pool, owner.session_id, Uuid::new_v4())
            .await
            .is_ok()
    );
}

#[tokio::test]
async fn reopen_database_preserves_receipts_and_uncertainty_until_explicit_fence() {
    for state in ["accepted", "deferred", "in_flight"] {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("restart.sqlite");
        let disk_pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(2)
            .connect_with(
                sqlx::sqlite::SqliteConnectOptions::new()
                    .filename(&path)
                    .create_if_missing(true)
                    .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal),
            )
            .await
            .unwrap();
        let (pool, q, owner, r) = fixture_in(disk_pool).await;
        if state == "in_flight" {
            assert!(
                tokio::time::timeout(
                    std::time::Duration::from_millis(50),
                    submit(&pool, &q, &owner, &r, |_| async {
                        std::future::pending::<()>().await;
                        Ok(())
                    })
                )
                .await
                .is_err()
            );
        } else {
            submit(&pool, &q, &owner, &r, |_| async {
                if state == "accepted" {
                    bind(&pool, owner.session_id).await
                } else {
                    Err(ContainerError::StorageAdmissionDeferred("synthetic_hold"))
                }
            })
            .await
            .unwrap();
        }
        pool.close().await;
        let reopened = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(2)
            .connect_with(sqlx::sqlite::SqliteConnectOptions::new().filename(&path))
            .await
            .unwrap();
        let result = lookup(&reopened, r.batch_id, &r.intent_sha256)
            .await
            .unwrap();
        assert_eq!(
            result.outcome,
            if state == "in_flight" {
                "uncertain"
            } else {
                state
            }
        );
        assert_eq!(result.no_admission, state == "deferred");
        if state == "in_flight" {
            assert!(
                cancel(&reopened, r.batch_id, &r.intent_sha256)
                    .await
                    .unwrap()
                    .no_admission
            );
        }
        if state == "accepted" {
            assert!(
                submit(
                    &reopened,
                    &QueuedMessageService::new(),
                    &owner,
                    &r,
                    |_| async { panic!("restart cannot replay accepted") }
                )
                .await
                .unwrap()
                .replay
            );
        }
        if state == "deferred" {
            assert_eq!(
                submit(
                    &reopened,
                    &QueuedMessageService::new(),
                    &owner,
                    &fresh(&r),
                    |_| bind(&reopened, owner.session_id)
                )
                .await
                .unwrap()
                .outcome,
                "accepted"
            );
        }
    }
}

#[test]
fn fingerprint_has_a_language_independent_sorted_unicode_vector() {
    let a = serde_json::json!({"z":[{"b":2,"a":"é"}],"a":null});
    let b: serde_json::Value = serde_json::from_str(r#"{"a":null,"z":[{"a":"é","b":2}]}"#).unwrap();
    assert_eq!(fingerprint(&a), fingerprint(&b));
    assert_eq!(
        fingerprint(&a),
        format!(
            "{:x}",
            Sha256::digest("{\"a\":null,\"z\":[{\"a\":\"é\",\"b\":2}]}".as_bytes())
        )
    );
}

fn job_admission(
    pool: &SqlitePool,
    b: &OwnerBinding,
    execution: Uuid,
) -> executors::workspace_admission::JobAdmission {
    executors::workspace_admission::JobAdmission {
        pool: pool.clone(),
        workspace: b.workspace_id,
        session: b.session_id,
        execution,
    }
}

#[tokio::test]
async fn independent_job_wins_before_parent_exit_and_holds_only_its_owner_until_terminal() {
    let (pool, q, b, r) = fixture().await;
    let parent = create(&pool, b.session_id, Uuid::new_v4()).await.unwrap();
    // The client may already have observed idle; native authority is acquired
    // before inference, not by a late stdout spawn notification.
    let lease = job_admission(&pool, &b, parent.id).reserve().await.unwrap();
    ExecutionProcess::update_completion(
        &pool,
        parent.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    let response = submit(&pool, &q, &b, &r, |_| async {
        panic!("child lifetime must exclude watcher")
    })
    .await
    .unwrap();
    assert_eq!(response.reason, "independent_job_lifetime_unsettled");
    assert!(response.no_admission);
    assert!(!response.automatic_launch_queued);
    let (_, other_queue, other, other_request) = fixture_in(pool.clone()).await;
    assert_eq!(
        submit(&pool, &other_queue, &other, &other_request, |_| bind(
            &pool,
            other.session_id
        ))
        .await
        .unwrap()
        .outcome,
        "accepted"
    );
    lease.close().await.unwrap();
    assert_eq!(
        submit(&pool, &q, &b, &fresh(&r), |_| bind(&pool, b.session_id))
            .await
            .unwrap()
            .outcome,
        "accepted"
    );
}

#[tokio::test]
async fn watcher_wins_and_late_independent_job_has_no_pre_inference_authority() {
    let (pool, q, b, r) = fixture().await;
    let parent = create(&pool, b.session_id, Uuid::new_v4()).await.unwrap();
    ExecutionProcess::update_completion(
        &pool,
        parent.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    let admission = job_admission(&pool, &b, parent.id);
    let response = submit(&pool, &q, &b, &r, |_| async {
        // The watcher reservation and parent exit are already durable. An old
        // producer must fail before issuing its thread/turn start request.
        assert!(admission.reserve().await.is_err());
        assert!(create(&pool, b.session_id, Uuid::new_v4()).await.is_err());
        bind(&pool, b.session_id).await
    })
    .await
    .unwrap();
    assert_eq!(response.outcome, "accepted");
    assert!(admission.reserve().await.is_err());
    let leases: i64 = sqlx::query_scalar("SELECT count(*) FROM watcher_job_leases")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(leases, 0);
    // An accepted owner may use its own ordinary controlled job tools. That
    // lease does not create another owner or relax its per-action permissions.
    let own = job_admission(&pool, &b, response.receipt.unwrap().execution_id.unwrap())
        .reserve()
        .await
        .unwrap();
    own.close().await.unwrap();
}

#[tokio::test]
async fn dropped_job_and_database_reopen_do_not_fabricate_child_termination() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("job-leases.sqlite");
    let options = sqlx::sqlite::SqliteConnectOptions::new()
        .filename(&path)
        .create_if_missing(true);
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(2)
        .connect_with(options.clone())
        .await
        .unwrap();
    let (pool, q, b, r) = fixture_in(pool).await;
    let parent = create(&pool, b.session_id, Uuid::new_v4()).await.unwrap();
    let lease = job_admission(&pool, &b, parent.id).reserve().await.unwrap();
    drop(lease); // Timeout/crash/drop is not a terminal receipt.
    ExecutionProcess::update_completion(
        &pool,
        parent.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    pool.close().await;
    let reopened = sqlx::sqlite::SqlitePoolOptions::new()
        .connect_with(options)
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations")
        .run(&reopened)
        .await
        .unwrap();
    let response = submit(&reopened, &q, &b, &r, |_| async {
        panic!("unsettled lifetime survives restart")
    })
    .await
    .unwrap();
    assert_eq!(response.reason, "independent_job_lifetime_unsettled");
    assert!(response.no_admission);
    assert_eq!(count(&reopened).await, 1);
}

#[tokio::test]
async fn concurrent_job_arrival_parent_exit_and_watcher_admission_have_no_overlap() {
    for _ in 0..8 {
        let (pool, q, b, r) = fixture().await;
        let parent = create(&pool, b.session_id, Uuid::new_v4()).await.unwrap();
        let job = job_admission(&pool, &b, parent.id);
        let barrier = Arc::new(tokio::sync::Barrier::new(2));
        let (lease, response) = tokio::join!(
            async {
                barrier.wait().await;
                job.reserve().await
            },
            async {
                barrier.wait().await;
                ExecutionProcess::update_completion(
                    &pool,
                    parent.id,
                    ExecutionProcessStatus::Completed,
                    Some(0),
                )
                .await
                .unwrap();
                submit(&pool, &q, &b, &r, |_| bind(&pool, b.session_id))
                    .await
                    .unwrap()
            }
        );
        match lease {
            Ok(lease) => {
                assert_eq!(response.outcome, "deferred");
                assert_eq!(response.reason, "independent_job_lifetime_unsettled");
                assert_eq!(count(&pool).await, 1);
                lease.close().await.unwrap();
            }
            Err(_) => {
                assert_eq!(response.outcome, "accepted");
                assert_eq!(count(&pool).await, 2);
            }
        }
    }
}

#[tokio::test]
async fn unbound_reservation_is_pending_uncertainty_not_confirmed_owner_activity() {
    let (pool, q, b, r) = fixture().await;
    let reached = Arc::new(tokio::sync::Notify::new());
    let mut inflight = Box::pin(submit(&pool, &q, &b, &r, |_| async {
        reached.notify_one();
        std::future::pending::<Result<(), ContainerError>>().await
    }));
    tokio::time::timeout(std::time::Duration::from_secs(5), async {
        tokio::select! {
            _=reached.notified()=>{},
            result=&mut inflight=>panic!("reserved launch must remain in flight: {result:?}"),
        }
    })
    .await
    .unwrap();
    drop(inflight); // cancel only after the native reservation actually committed
    let mut later = r.clone();
    later.batch_id = Uuid::new_v4();
    later.attempt_id = Uuid::new_v4();
    later.intent.incidents[0].incident_id = Uuid::new_v4();
    later.intent_sha256 = fingerprint(&later.intent);
    let result = submit(&pool, &q, &b, &later, |_| async {
        panic!("unknown reservation must not launch")
    })
    .await
    .unwrap();
    assert_eq!(result.reason, "owner_admission_unsettled");
    assert!(result.no_admission);
    assert_eq!(count(&pool).await, 0);
    cancel(&pool, r.batch_id, &r.intent_sha256).await.unwrap();
    assert_eq!(
        submit(&pool, &q, &b, &fresh(&later), |_| bind(&pool, b.session_id))
            .await
            .unwrap()
            .outcome,
        "accepted"
    );
}

#[tokio::test]
async fn confirmed_child_activity_covers_episode_but_drop_reverts_to_durable_unknown() {
    let (pool, q, b, r) = fixture().await;
    let parent = create(&pool, b.session_id, Uuid::new_v4()).await.unwrap();
    let lease = job_admission(&pool, &b, parent.id).reserve().await.unwrap();
    assert!(!executors::workspace_admission::running_jobs(b.workspace_id).unwrap());
    lease.mark_running().unwrap(); // injected native acknowledgment, no inference
    ExecutionProcess::update_completion(
        &pool,
        parent.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    assert_eq!(
        submit(&pool, &q, &b, &r, |_| async {
            panic!("active child excludes launch")
        })
        .await
        .unwrap()
        .reason,
        "owner_independent_jobs_active"
    );
    drop(lease); // lost producer/ack cannot fabricate terminal status
    assert!(!executors::workspace_admission::running_jobs(b.workspace_id).unwrap());
    assert_eq!(
        submit(&pool, &q, &b, &fresh(&r), |_| async {
            panic!("unknown child lifetime excludes launch")
        })
        .await
        .unwrap()
        .reason,
        "independent_job_lifetime_unsettled"
    );
    assert_eq!(count(&pool).await, 1);
}
