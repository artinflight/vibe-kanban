//! Actual SQLx model tests. Authored for the admitted native test slot; no provider.
use super::*;

async fn fixture() -> (SqlitePool, Receipt) {
    let db = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::raw_sql("CREATE TABLE workspaces(id BLOB PRIMARY KEY); CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB,executor TEXT,agent_working_dir TEXT); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,run_reason TEXT,executor_action TEXT,created_at TEXT,dropped INTEGER); CREATE TABLE subagent_jobs(id BLOB,session_id BLOB,execution_process_id BLOB,status TEXT); CREATE TABLE turn_github_sync_user_queue(session_id BLOB,workspace_id BLOB,data TEXT,state TEXT); CREATE TABLE turn_github_sync_incoming(id BLOB,session_id BLOB,workspace_id BLOB,data TEXT,state TEXT);")
        .execute(&db).await.unwrap();
    sqlx::raw_sql(include_str!(
        "../../../migrations/20261021140000_provider_handoff_reservations.sql"
    ))
    .execute(&db)
    .await
    .unwrap();
    sqlx::raw_sql(include_str!(
        "../../../migrations/20261024190000_provider_continuation_receipts.sql"
    ))
    .execute(&db)
    .await
    .unwrap();
    sqlx::raw_sql(include_str!(
        "../../../migrations/20261024200000_provider_continuation_checkpoints.sql"
    ))
    .execute(&db)
    .await
    .unwrap();
    let r = Receipt {
        request_id: Uuid::new_v4(),
        workspace_id: Uuid::new_v4(),
        session_id: Uuid::new_v4(),
        executor: "CODEX".into(),
        intent_sha256: "a".repeat(64),
        configuration_sha256: "b".repeat(64),
        intent: "{}".into(),
        state_token: "token".into(),
        predecessor_execution_id: None,
        execution_id: Uuid::new_v4(),
        expected_action: "{}".into(),
        status: "reserved".into(),
        ownership: "held".into(),
        reason: String::new(),
    };
    sqlx::query("INSERT INTO workspaces VALUES(?)")
        .bind(r.workspace_id)
        .execute(&db)
        .await
        .unwrap();
    sqlx::query("INSERT INTO sessions VALUES(?,?,'CODEX',NULL)")
        .bind(r.session_id)
        .bind(r.workspace_id)
        .execute(&db)
        .await
        .unwrap();
    (db, r)
}
#[tokio::test]
async fn claim_once_recovery_never_dispatches_again() {
    let (db, r) = fixture().await;
    assert!(reserve_after_checkpoint(&db, &r, None).await.unwrap());
    assert!(!reserve_after_checkpoint(&db, &r, None).await.unwrap());
    assert!(
        bind_action(&db, r.request_id, "resolved-action")
            .await
            .unwrap()
    );
    assert!(
        !bind_action(&db, r.request_id, "resolved-action")
            .await
            .unwrap()
    );
    outcome(&db, r.request_id, false).await.unwrap();
    let recovered = get(&db, r.request_id).await.unwrap().unwrap();
    assert_eq!(recovered.status, "unknown");
    assert_eq!(recovered.ownership, "held");
    assert!(
        !bind_action(&db, r.request_id, "resolved-action")
            .await
            .unwrap()
    );
}
#[tokio::test]
async fn competing_request_keeps_original_claim() {
    let (db, r) = fixture().await;
    reserve_after_checkpoint(&db, &r, None).await.unwrap();
    let mut other = r.clone();
    other.request_id = Uuid::new_v4();
    other.execution_id = Uuid::new_v4();
    assert!(reserve_after_checkpoint(&db, &other, None).await.is_err());
    assert_eq!(
        owner(&db, r.workspace_id)
            .await
            .unwrap()
            .unwrap()
            .request_id,
        r.request_id
    );
}
#[tokio::test]
async fn early_rejection_never_turns_into_dispatch() {
    let (db, r) = fixture().await;
    reserve_after_checkpoint(&db, &r, None).await.unwrap();
    reject(&db, r.request_id, "stale_binding").await.unwrap();
    assert!(owner(&db, r.workspace_id).await.unwrap().is_none());
    assert!(!bind_action(&db, r.request_id, "{}").await.unwrap());
    assert_eq!(
        get(&db, r.request_id).await.unwrap().unwrap().status,
        "rejected"
    );
}

async fn checkpoint_fixture() -> (SqlitePool, Receipt, checkpoint::Checkpoint) {
    let (db, mut r) = fixture().await;
    let source = Uuid::new_v4();
    let source_session = Uuid::new_v4();
    sqlx::query("INSERT INTO sessions VALUES(?,?,'CLAUDE_CODE',NULL)")
        .bind(source_session)
        .bind(r.workspace_id)
        .execute(&db)
        .await
        .unwrap();
    sqlx::query("INSERT INTO execution_processes VALUES(?,?,'failed','codingagent','{}','1',0)")
        .bind(source)
        .bind(source_session)
        .execute(&db)
        .await
        .unwrap();
    sqlx::query("INSERT INTO provider_failover_activations VALUES(?,'work',?,'private','trusted-source','generation','active','')")
        .bind(r.workspace_id).bind(source).execute(&db).await.unwrap();
    r.intent = r#"{"checkpoint_receipt":"checkpoint:synthetic"}"#.into();
    let cp = checkpoint::Checkpoint {
        reference: "checkpoint:synthetic".into(),
        workspace_id: r.workspace_id,
        source_execution_id: source,
        destination_session_id: r.session_id,
        target_token: r.state_token.clone(),
        work_id: "work".into(),
        owner_generation: "generation".into(),
        legacy_transition: None,
        evidence: "{}".into(),
        valid_until_ms: 2000,
        claimed_request: None,
    };
    checkpoint::publish(&db, &cp).await.unwrap();
    (db, r, cp)
}
#[tokio::test]
async fn trusted_bridge_model_atomic_transfer_and_early_failure_keeps_owner() {
    let (db, r, cp) = checkpoint_fixture().await;
    assert!(
        reserve_with_checkpoint(&db, &r, None, Some(&cp.reference), 1000)
            .await
            .unwrap()
    );
    assert_eq!(
        checkpoint::get(&db, &cp.reference)
            .await
            .unwrap()
            .unwrap()
            .claimed_request,
        Some(r.request_id)
    );
    checkpoint::hold(&db, r.request_id).await.unwrap();
    let row = owner(&db, r.workspace_id).await.unwrap().unwrap();
    assert_eq!(
        (row.status.as_str(), row.ownership.as_str()),
        ("unknown", "held")
    );
    assert!(
        reserve_with_checkpoint(&db, &r, None, Some(&cp.reference), 1001)
            .await
            .is_err()
    );
}
#[tokio::test]
async fn trusted_bridge_model_failed_insert_rolls_back_source_and_claim() {
    let (db, r, cp) = checkpoint_fixture().await;
    sqlx::query("INSERT INTO turn_github_sync_user_queue VALUES(?,?,'retained','queued')")
        .bind(r.session_id)
        .bind(r.workspace_id)
        .execute(&db)
        .await
        .unwrap();
    assert!(
        reserve_with_checkpoint(&db, &r, None, Some(&cp.reference), 1000)
            .await
            .is_err()
    );
    assert!(
        checkpoint::get(&db, &cp.reference)
            .await
            .unwrap()
            .unwrap()
            .claimed_request
            .is_none()
    );
    assert!(owner(&db, r.workspace_id).await.unwrap().is_none());
    let state: String =
        sqlx::query_scalar("SELECT state FROM provider_failover_activations WHERE workspace_id=?")
            .bind(r.workspace_id)
            .fetch_one(&db)
            .await
            .unwrap();
    assert_eq!(state, "active");
}
