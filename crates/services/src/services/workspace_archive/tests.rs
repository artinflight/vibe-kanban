use sqlx::sqlite::SqlitePoolOptions;

use super::*;

async fn fixture() -> (SqlitePool, Uuid, Uuid) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::raw_sql("CREATE TABLE workspaces(id BLOB PRIMARY KEY,archived INTEGER,pinned INTEGER); CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT);")
        .execute(&pool).await.unwrap();
    sqlx::raw_sql(include_str!(
        "../../../../db/migrations/20261125000000_workspace_archive_requests.sql"
    ))
    .execute(&pool)
    .await
    .unwrap();
    sqlx::raw_sql(include_str!(
        "../../../../db/migrations/20261127000000_workspace_archive_catalog.sql"
    ))
    .execute(&pool)
    .await
    .unwrap();
    let (workspace, session) = (Uuid::new_v4(), Uuid::new_v4());
    sqlx::query("INSERT INTO workspaces VALUES(?,1,0)")
        .bind(workspace)
        .execute(&pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO sessions VALUES(?,?)")
        .bind(session)
        .bind(workspace)
        .execute(&pool)
        .await
        .unwrap();
    (pool, workspace, session)
}

fn payload() -> Value {
    serde_json::json!({"prompt":"exact message\n","executor_config":{"model":"selected","routing":{"mode":"Recommend"},"permission":"review"},"perform_git_reset":false,"retry_process_id":null})
}

#[tokio::test]
async fn simultaneous_identical_requests_preserve_one_exact_input_and_revoke_exclusion() {
    let (pool, w, s) = fixture().await;
    sqlx::query("INSERT INTO workspace_archive_state(workspace_id,request_version,operation_id,phase) VALUES(?,1,?,'cold')")
        .bind(w).bind(Uuid::new_v4().to_string()).execute(&pool).await.unwrap();
    let request = Uuid::new_v4();
    let input = payload();
    let (a, b) = tokio::join!(
        retain(&pool, w, s, request, &input),
        retain(&pool, w, s, request, &input)
    );
    assert_eq!(a.unwrap().state, "waiting_restore");
    assert_eq!(b.unwrap().request_id, request);
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM workspace_archive_inputs")
            .fetch_one(&pool)
            .await
            .unwrap(),
        1
    );
    let saved: String = sqlx::query_scalar("SELECT payload FROM workspace_archive_inputs")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(serde_json::from_str::<Value>(&saved).unwrap(), input);
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT archived FROM workspaces")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
    assert!(reserve(&pool, request).await.is_err());
    assert!(
        retain(
            &pool,
            w,
            s,
            request,
            &serde_json::json!({"prompt":"different"})
        )
        .await
        .is_err()
    );
}

#[tokio::test]
async fn execution_receipt_reconciles_only_exact_reserved_identity_without_replay() {
    let (pool, w, s) = fixture().await;
    let request = Uuid::new_v4();
    retain(&pool, w, s, request, &payload()).await.unwrap();
    let reservation = reserve(&pool, request).await.unwrap();
    assert!(reserve(&pool, request).await.is_err());
    sqlx::query("INSERT INTO execution_processes VALUES(?,?,'completed')")
        .bind(Uuid::new_v4())
        .bind(s)
        .execute(&pool)
        .await
        .unwrap();
    assert!(!reconcile(&pool, request).await.unwrap());
    hold(&pool, request, "uncertain receipt").await.unwrap();
    assert!(cancel(&pool, s).await.is_err());
    sqlx::query("INSERT INTO execution_processes VALUES(?,?,'running')")
        .bind(reservation.execution)
        .bind(s)
        .execute(&pool)
        .await
        .unwrap();
    assert!(reconcile(&pool, request).await.unwrap());
    assert!(status(&pool, s).await.unwrap().is_none());
}

#[tokio::test]
async fn pending_order_cancellation_and_foreign_session_are_preserved() {
    let (pool, w, s) = fixture().await;
    let a = Uuid::new_v4();
    let b = Uuid::new_v4();
    assert!(
        retain(&pool, w, Uuid::new_v4(), a, &payload())
            .await
            .is_err()
    );
    retain(&pool, w, s, a, &payload()).await.unwrap();
    retain(&pool, w, s, b, &payload()).await.unwrap();
    assert!(reserve(&pool, b).await.is_err());
    cancel(&pool, s).await.unwrap();
    assert!(status(&pool, s).await.unwrap().is_none());
    assert_eq!(
        sqlx::query_scalar::<_, i64>(
            "SELECT count(*) FROM workspace_archive_inputs WHERE state='cancelled'"
        )
        .fetch_one(&pool)
        .await
        .unwrap(),
        2
    );
}

#[tokio::test]
async fn dispatch_task_scope_binds_ordinary_execution_to_the_correct_session() {
    let (pool, w, s) = fixture().await;
    let request = Uuid::new_v4();
    retain(&pool, w, s, request, &payload()).await.unwrap();
    let r = reserve(&pool, request).await.unwrap();
    assert!(execution_id(w, s).unwrap().is_none());
    dispatch_scope(r.clone(), async {
        assert_eq!(execution_id(w, s).unwrap(), Some(r.execution));
        assert!(execution_id(w, Uuid::new_v4()).is_err());
    })
    .await;
    assert!(!in_dispatch());
}
