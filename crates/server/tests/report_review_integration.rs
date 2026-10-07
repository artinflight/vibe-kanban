#[path = "fixtures/review_storage_root.rs"]
mod review_storage_root;

use std::{collections::HashMap, sync::Arc, time::Duration};

use futures_util::StreamExt;
use sqlx::{SqlitePool, sqlite::SqlitePoolOptions};
use tokio::sync::RwLock;
use utils::{log_msg::LogMsg, msg_store::MsgStore};
use uuid::Uuid;

async fn fixture() -> SqlitePool {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::raw_sql(
        "PRAGMA foreign_keys=ON;
         CREATE TABLE workspaces(id BLOB PRIMARY KEY);
         CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB REFERENCES workspaces(id) ON DELETE CASCADE);
         CREATE TABLE execution_processes(id BLOB PRIMARY KEY, session_id BLOB REFERENCES sessions(id) ON DELETE CASCADE);
         CREATE TABLE coding_agent_turns(id BLOB PRIMARY KEY, execution_process_id BLOB REFERENCES execution_processes(id) ON DELETE CASCADE, summary TEXT, agent_message_id TEXT, seen INTEGER, updated_at TEXT);
         INSERT INTO workspaces VALUES (X'01');
         INSERT INTO sessions VALUES (X'02',X'01');
         INSERT INTO execution_processes VALUES (X'03',X'02');
         INSERT INTO coding_agent_turns VALUES (X'04',X'03','report','message',0,'before');",
    )
    .execute(&pool)
    .await
    .unwrap();
    sqlx::raw_sql(include_str!(
        "../../db/migrations/20261007190000_workspace_report_receipts.sql"
    ))
    .execute(&pool)
    .await
    .unwrap();
    pool
}

#[tokio::test]
async fn changed_reply_reopens_only_its_existing_turn() {
    let pool = fixture().await;
    sqlx::raw_sql(
        "UPDATE coding_agent_turns SET seen=1; UPDATE coding_agent_turns SET summary='new report';",
    )
    .execute(&pool)
    .await
    .unwrap();
    let seen: i64 = sqlx::query_scalar("SELECT seen FROM coding_agent_turns")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(seen, 0);
}

#[tokio::test]
async fn seen_only_write_does_not_invent_a_new_reply() {
    let pool = fixture().await;
    sqlx::query("UPDATE coding_agent_turns SET seen=1")
        .execute(&pool)
        .await
        .unwrap();
    let seen: i64 = sqlx::query_scalar("SELECT seen FROM coding_agent_turns")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(seen, 1);
}

#[tokio::test]
async fn review_intent_must_not_break_existing_workspace_deletion() {
    let pool = fixture().await;
    sqlx::query("INSERT INTO workspace_review_intent(workspace_id) VALUES(X'01')")
        .execute(&pool)
        .await
        .unwrap();
    let result = sqlx::query("DELETE FROM workspaces WHERE id=X'01'")
        .execute(&pool)
        .await;
    assert!(
        result.is_ok(),
        "Opening/marking a workspace must not prevent deletion: {result:?}"
    );
}

#[tokio::test]
async fn finalized_log_must_not_break_existing_execution_deletion() {
    let pool = fixture().await;
    sqlx::query("INSERT INTO workspace_review_log_finalized VALUES(X'03','finished',1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')")
        .execute(&pool)
        .await
        .unwrap();
    let result = sqlx::query("DELETE FROM execution_processes WHERE id=X'03'")
        .execute(&pool)
        .await;
    assert!(
        result.is_ok(),
        "Finishing a log must not prevent execution deletion: {result:?}"
    );
}

#[tokio::test]
async fn review_writer_requires_loss_detection_for_evicted_history() {
    let store = MsgStore::with_limits(1, 4);
    store.push_stdout("required report bytes");
    store.push_finished();
    let first = store.history_plus_stream_strict().next().await.unwrap();
    assert!(
        first.is_err(),
        "Truncated history must not certify completion: {first:?}"
    );
}

#[tokio::test]
async fn complete_untruncated_history_preserves_report_before_finished() {
    let store = MsgStore::new();
    store.push_stdout("complete report");
    store.push_finished();
    let mut stream = store.history_plus_stream_strict();
    assert!(matches!(stream.next().await, Some(Ok(LogMsg::Stdout(_)))));
    assert!(matches!(stream.next().await, Some(Ok(LogMsg::Finished))));
}

async fn writer_fixture(store: MsgStore) -> (SqlitePool, Uuid, Uuid) {
    // Debug asset_dir is this task's isolated source/dev_assets. Never run the
    // real deployment constructor or any agent/cleanup fixture.
    review_storage_root::assert_fixture_root();
    let pool = fixture().await;
    let execution = Uuid::new_v4();
    let session = Uuid::new_v4();
    sqlx::query("INSERT INTO execution_processes VALUES(?,X'02')")
        .bind(execution)
        .execute(&pool)
        .await
        .unwrap();
    let stores = Arc::new(RwLock::new(HashMap::from([(execution, Arc::new(store))])));
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        stores,
        db::DBService { pool: pool.clone() },
        execution,
        session,
    );
    tokio::time::timeout(Duration::from_secs(5), writer)
        .await
        .unwrap()
        .unwrap();
    (pool, execution, session)
}

#[tokio::test]
async fn actual_storage_writer_must_not_finalize_evicted_report_bytes() {
    let store = MsgStore::with_limits(1, 4);
    store.push_stdout("required report bytes");
    store.push_finished();
    let (pool, execution, _) = writer_fixture(store).await;
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(execution)
    .fetch_one(&pool)
    .await
    .unwrap();
    assert_eq!(
        count, 0,
        "Lossy replay must not publish a finalized-log fence"
    );
}

#[tokio::test]
async fn actual_storage_writer_finalizes_complete_flushed_report() {
    let store = MsgStore::new();
    store.push_stdout("complete report bytes");
    store.push_finished();
    let (pool, execution, session) = writer_fixture(store).await;
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(execution)
    .fetch_one(&pool)
    .await
    .unwrap();
    assert_eq!(count, 1);
    let path = utils::execution_logs::process_log_file_path(session, execution);
    assert!(
        tokio::fs::read_to_string(path)
            .await
            .unwrap()
            .contains("complete report bytes")
    );
}
