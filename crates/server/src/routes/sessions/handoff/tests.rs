use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use db::models::{execution_process::CreateExecutionProcess, workspace::CreateWorkspace};

use super::*;

async fn fixture() -> (SqlitePool, Session, ExecutionProcess) {
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let workspace = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "handoff-fixture".into(),
            name: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let session = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CLAUDE_CODE".into()),
            name: None,
        },
        Uuid::new_v4(),
        workspace.id,
    )
    .await
    .unwrap();
    let mut config = ExecutorConfig::new(BaseCodingAgent::ClaudeCode);
    config.model_id = Some("sonnet".into());
    config.reasoning_id = Some("high".into());
    config.permission_policy = Some(executors::model_selector::PermissionPolicy::Supervised);
    let execution = ExecutionProcess::create(
        &pool,
        &CreateExecutionProcess {
            session_id: session.id,
            run_reason: ExecutionProcessRunReason::CodingAgent,
            executor_action: ExecutorAction::new(
                ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                    prompt: "Original owner objective and restrictions".into(),
                    executor_config: config,
                    working_dir: None,
                }),
                None,
            ),
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    ExecutionProcess::update_completion(
        &pool,
        execution.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    let execution = ExecutionProcess::find_by_id(&pool, execution.id)
        .await
        .unwrap()
        .unwrap();
    (pool, session, execution)
}

fn request(execution: Uuid) -> HandoffRequest {
    HandoffRequest {
        request_id: Uuid::new_v4(),
        execution_id: execution,
        prompt: "Continue the original objective".into(),
        model_id: "gpt-6.1-sol".into(),
        reasoning_id: "high".into(),
    }
}

#[tokio::test]
async fn successful_exact_checkpoint_and_explicit_selection_preserve_approvals_and_policy() {
    let (_, session, execution) = fixture().await;
    let source =
        source_checkpoint(&session, std::slice::from_ref(&execution), execution.id).unwrap();
    let mut source = source;
    source.routing = Some(Box::new(RoutingPolicy {
        mode: RoutingMode::Auto,
        floor: executors::routing::CapabilityFloor::Frontier,
        denied_models: vec!["blocked".into()],
        allow_escalation: false,
    }));
    let config = target_config(&source, &request(execution.id)).unwrap();
    assert_eq!(config.model_id.as_deref(), Some("gpt-6.1-sol"));
    assert_eq!(config.reasoning_id.as_deref(), Some("high"));
    assert_eq!(config.permission_policy, source.permission_policy);
    let policy = config.routing.unwrap();
    assert_eq!(policy.mode, RoutingMode::Shadow);
    assert_eq!(policy.floor, source.routing.as_ref().unwrap().floor);
    assert_eq!(policy.denied_models, vec!["blocked"]);
    assert!(!policy.allow_escalation);
}

#[tokio::test]
async fn running_failed_dropped_wrong_executor_and_stale_checkpoint_fail_closed() {
    let (_, session, execution) = fixture().await;
    assert!(source_checkpoint(&session, std::slice::from_ref(&execution), Uuid::new_v4()).is_err());
    for status in [
        ExecutionProcessStatus::Running,
        ExecutionProcessStatus::Failed,
        ExecutionProcessStatus::Killed,
    ] {
        let mut changed = execution.clone();
        changed.status = status;
        assert!(source_checkpoint(&session, &[changed], execution.id).is_err());
    }
    let mut changed = execution.clone();
    changed.dropped = true;
    assert!(source_checkpoint(&session, &[changed], execution.id).is_err());
    let mut wrong = session.clone();
    wrong.executor = Some("CODEX".into());
    assert!(source_checkpoint(&wrong, std::slice::from_ref(&execution), execution.id).is_err());
    let mut changed = execution.clone();
    changed.session_id = Uuid::new_v4();
    assert!(source_checkpoint(&session, &[changed], execution.id).is_err());
}

#[tokio::test]
async fn unsupported_or_denied_selection_is_never_substituted() {
    let (_, session, execution) = fixture().await;
    let mut source =
        source_checkpoint(&session, std::slice::from_ref(&execution), execution.id).unwrap();
    let mut req = request(execution.id);
    req.reasoning_id = "not-supported".into();
    assert!(matches!(
        ApiError::from(target_config(&source, &req).unwrap_err()),
        ApiError::BadRequest(_)
    ));
    req.reasoning_id = "high".into();
    req.model_id = "unknown-provider-model".into();
    assert!(target_config(&source, &req).is_err());
    req.model_id = "gpt-6.1-sol".into();
    source.routing = Some(Box::new(RoutingPolicy {
        mode: RoutingMode::Shadow,
        floor: Default::default(),
        denied_models: vec![req.model_id.clone()],
        allow_escalation: false,
    }));
    assert!(target_config(&source, &req).is_err());
}

#[tokio::test]
async fn concurrent_replay_new_request_and_identity_conflicts_never_duplicate_dispatch() {
    let (pool, session, execution) = fixture().await;
    let req = request(execution.id);
    let calls = Arc::new(AtomicUsize::new(0));
    let dispatch = |_| async {
        calls.fetch_add(1, Ordering::SeqCst);
        Ok(Uuid::new_v4())
    };
    let (a, b) = tokio::join!(
        reserve(&pool, session.id, &req, "context", dispatch),
        reserve(&pool, session.id, &req, "context", dispatch)
    );
    let a = a.unwrap();
    let b = b.unwrap();
    assert_eq!(a.target_session_id, b.target_session_id);
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    let again = reserve(&pool, session.id, &req, "changed-context", dispatch)
        .await
        .unwrap();
    assert_eq!(again.status, "started");
    let other = request(execution.id);
    assert!(
        reserve(&pool, session.id, &other, "context", dispatch)
            .await
            .is_err()
    );
    let mut conflict = req;
    conflict.prompt = "Different owner input".into();
    assert!(
        reserve(&pool, session.id, &conflict, "context", dispatch)
            .await
            .is_err()
    );
    assert_eq!(calls.load(Ordering::SeqCst), 1);
    assert!(require_unclaimed(&pool, session.id).await.is_err());
}

#[tokio::test]
async fn uncertain_dispatch_and_cancelled_waiter_remain_fenced_without_replay() {
    let (pool, session, execution) = fixture().await;
    let req = request(execution.id);
    let value = reserve(&pool, session.id, &req, "context", |_| async {
        Err(ApiError::Conflict("Uncertain spawn".into()))
    })
    .await
    .unwrap();
    assert_eq!(value.status, "unknown");
    assert!(value.target_execution_id.is_none());
    reserve(&pool, session.id, &req, "context", |_| async {
        panic!("must never replay")
    })
    .await
    .unwrap();
    let (pool, session, execution) = fixture().await;
    let req = request(execution.id);
    let result = tokio::time::timeout(
        std::time::Duration::from_millis(100),
        reserve(&pool, session.id, &req, "context", |_| {
            std::future::pending()
        }),
    )
    .await;
    assert!(result.is_err());
    assert_eq!(
        stored(&pool, req.request_id).await.unwrap().unwrap().status,
        "unknown"
    );
    assert!(require_unclaimed(&pool, session.id).await.is_err());
}

#[tokio::test]
async fn complete_context_preserves_original_prompt_and_raw_history_or_refuses_without_truncation()
{
    let (pool, session, execution) = fixture().await;
    let temp = tempfile::tempdir().unwrap();
    let path = process_log_file_path_in_root(temp.path(), session.id, execution.id);
    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
    let raw = b"{\"Stdout\":\"assistant/tool history and unresolved constraints\"}\n";
    std::fs::write(&path, raw).unwrap();
    // Missing closure evidence must never be accepted as complete history.
    assert!(
        complete_context(
            &pool,
            temp.path(),
            &session,
            std::slice::from_ref(&execution),
            "Continue"
        )
        .await
        .is_err()
    );
    std::fs::write(
        path.with_extension("capture.json"),
        b"{\"capture_state\":\"closed\"}",
    )
    .unwrap();
    sqlx::query("INSERT INTO workspace_review_log_finalized(execution_id,finalized_at,raw_bytes,raw_sha256) VALUES(?,datetime('now'),?,?)").bind(execution.id).bind(raw.len() as i64).bind(hash(raw)).execute(&pool).await.unwrap();
    let context = complete_context(
        &pool,
        temp.path(),
        &session,
        std::slice::from_ref(&execution),
        "Continue",
    )
    .await
    .unwrap();
    assert!(context.contains("Original owner objective and restrictions"));
    assert!(context.contains("assistant/tool history and unresolved constraints"));
    assert!(context.contains(&session.id.to_string()));
    assert!(
        complete_context(
            &pool,
            temp.path(),
            &session,
            std::slice::from_ref(&execution),
            &"x".repeat(60_000)
        )
        .await
        .is_err()
    );
    std::fs::write(&path, b"{\"Stdout\":\"changed\"}\n").unwrap();
    assert!(
        complete_context(&pool, temp.path(), &session, &[execution], "Continue")
            .await
            .is_err()
    );
}

#[test]
fn request_fingerprint_matches_connector_sorted_json() {
    let req = HandoffRequest {
        request_id: Uuid::nil(),
        execution_id: Uuid::nil(),
        prompt: "Continue".into(),
        model_id: "gpt-6.1-sol".into(),
        reasoning_id: "high".into(),
    };
    let bytes=br#"{"execution_id":"00000000-0000-0000-0000-000000000000","model_id":"gpt-6.1-sol","prompt":"Continue","reasoning_id":"high","request_id":"00000000-0000-0000-0000-000000000000"}"#;
    assert_eq!(request_hash(&req).unwrap(), hash(bytes));
}

#[tokio::test]
async fn workspace_db_guards_reject_running_jobs_queues_pending_inputs_drafts_and_unverified_continuity()
 {
    let (pool, session, execution) = fixture().await;
    idle_records(&pool, &session).await.unwrap();
    let unrelated = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CLAUDE_CODE".into()),
            name: None,
        },
        Uuid::new_v4(),
        session.workspace_id,
    )
    .await
    .unwrap();
    let active = ExecutionProcess::create(
        &pool,
        &CreateExecutionProcess {
            session_id: unrelated.id,
            run_reason: ExecutionProcessRunReason::CodingAgent,
            executor_action: execution.executor_action().unwrap().clone(),
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    assert!(idle_records(&pool, &session).await.is_err());
    ExecutionProcess::update_completion(
        &pool,
        active.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    idle_records(&pool, &session).await.unwrap();
    sqlx::query("INSERT INTO turn_github_sync_user_queue(session_id,workspace_id,data,state) VALUES(?,?,'{}','queued')").bind(session.id).bind(session.workspace_id).execute(&pool).await.unwrap();
    assert!(idle_records(&pool, &session).await.is_err());
    sqlx::query("DELETE FROM turn_github_sync_user_queue")
        .execute(&pool)
        .await
        .unwrap();
    sqlx::query(
        "INSERT INTO turn_github_sync_incoming(id,session_id,workspace_id,data) VALUES(?,?,?,'{}')",
    )
    .bind(Uuid::new_v4())
    .bind(session.id)
    .bind(session.workspace_id)
    .execute(&pool)
    .await
    .unwrap();
    assert!(idle_records(&pool, &session).await.is_err());
    sqlx::query("DELETE FROM turn_github_sync_incoming")
        .execute(&pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO turn_github_sync(execution_process_id,workspace_id,request,state,observation_state) VALUES(?,?,'{}','verified','pending')").bind(execution.id).bind(session.workspace_id).execute(&pool).await.unwrap();
    assert!(idle_records(&pool, &session).await.is_err());
    sqlx::query("UPDATE turn_github_sync SET observation_state='observed'")
        .execute(&pool)
        .await
        .unwrap();
    idle_records(&pool, &session).await.unwrap();
    sqlx::query("INSERT INTO subagent_jobs(id,session_id,execution_process_id,agent_id,status) VALUES(?,?,?,'fixture','unresolved')").bind(Uuid::new_v4()).bind(session.id).bind(execution.id).execute(&pool).await.unwrap();
    assert!(idle_records(&pool, &session).await.is_err());
    sqlx::query("DELETE FROM subagent_jobs")
        .execute(&pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO scratch(id,scratch_type,payload) VALUES(?,'DRAFT_FOLLOW_UP',?)").bind(session.id).bind(r#"{"type":"DRAFT_FOLLOW_UP","data":{"message":"unsent owner input","executor_config":{"executor":"CLAUDE_CODE"}}}"#).execute(&pool).await.unwrap();
    assert!(idle_records(&pool, &session).await.is_err());
    // Validation never consumes any pending owner draft.
    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM scratch")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(count, 1);
}

#[tokio::test]
async fn unresolved_target_cannot_be_manually_relaunched_but_confirmed_target_can_continue() {
    let (pool, session, execution) = fixture().await;
    let req = request(execution.id);
    let receipt = reserve(&pool, session.id, &req, "context", |_| async {
        Err(ApiError::Conflict("uncertain".into()))
    })
    .await
    .unwrap();
    assert!(
        require_unclaimed(&pool, receipt.target_session_id)
            .await
            .is_err()
    );
    let (pool, session, execution) = fixture().await;
    let req = request(execution.id);
    let receipt = reserve(&pool, session.id, &req, "context", |_| async {
        Ok(Uuid::new_v4())
    })
    .await
    .unwrap();
    require_unclaimed(&pool, receipt.target_session_id)
        .await
        .unwrap();
}

#[tokio::test]
async fn atomic_reservation_rechecks_new_pending_input_without_launch_or_consumption() {
    let (pool, session, execution) = fixture().await;
    let req = request(execution.id);
    idle_records(&pool, &session).await.unwrap();
    sqlx::query(
        "INSERT INTO turn_github_sync_incoming(id,session_id,workspace_id,data) VALUES(?,?,?,'{}')",
    )
    .bind(Uuid::new_v4())
    .bind(session.id)
    .bind(session.workspace_id)
    .execute(&pool)
    .await
    .unwrap();
    assert!(
        reserve(&pool, session.id, &req, "context", |_| async {
            panic!("new pending input must prevent dispatch")
        })
        .await
        .is_err()
    );
    assert!(stored(&pool, req.request_id).await.unwrap().is_none());
    let count: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM turn_github_sync_incoming WHERE state='received'")
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(count, 1);
}

#[tokio::test]
async fn missing_historical_approval_selection_is_never_guessed_from_a_current_preset() {
    let (_, session, execution) = fixture().await;
    let mut source =
        source_checkpoint(&session, std::slice::from_ref(&execution), execution.id).unwrap();
    source.permission_policy = None;
    assert!(target_config(&source, &request(execution.id)).is_err());
}

#[test]
fn unicode_request_fingerprint_uses_utf8_not_ascii_escape_substitution() {
    let req = HandoffRequest {
        request_id: Uuid::nil(),
        execution_id: Uuid::nil(),
        prompt: "Continue — café".into(),
        model_id: "gpt-6.1-sol".into(),
        reasoning_id: "high".into(),
    };
    assert_eq!(
        request_hash(&req).unwrap(),
        "6c5971728ec7dc04586974eed98b465627549cd3f1d371336e50818108f575d1"
    );
}

#[tokio::test]
async fn unrelated_codex_sessions_keep_existing_admission_with_or_without_other_handoffs() {
    let (pool, source, execution) = fixture().await;
    let codex = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: None,
        },
        Uuid::new_v4(),
        source.workspace_id,
    )
    .await
    .unwrap();
    require_unclaimed(&pool, codex.id).await.unwrap();
    let receipt = reserve(
        &pool,
        source.id,
        &request(execution.id),
        "context",
        |_| async { Err(ApiError::Conflict("Uncertain fixture dispatch".into())) },
    )
    .await
    .unwrap();
    assert_eq!(receipt.status, "unknown");
    require_unclaimed(&pool, codex.id).await.unwrap();
    assert!(require_unclaimed(&pool, source.id).await.is_err());
    assert!(
        require_unclaimed(&pool, receipt.target_session_id)
            .await
            .is_err()
    );
    let executions: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM execution_processes WHERE session_id=?")
            .bind(codex.id)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(executions, 0);
}

#[tokio::test]
async fn custom_source_preset_or_mode_cannot_silently_become_codex_defaults() {
    let (_, session, execution) = fixture().await;
    let mut source =
        source_checkpoint(&session, std::slice::from_ref(&execution), execution.id).unwrap();
    source.variant = Some("DEFAULT".into());
    assert!(target_config(&source, &request(execution.id)).is_ok());
    source.variant = Some("OWNER_CUSTOM".into());
    assert!(matches!(
        ApiError::from(target_config(&source, &request(execution.id)).unwrap_err()),
        ApiError::Conflict(_)
    ));
    source.variant = None;
    source.agent_id = Some("owner-mode".into());
    assert!(target_config(&source, &request(execution.id)).is_err());
}
