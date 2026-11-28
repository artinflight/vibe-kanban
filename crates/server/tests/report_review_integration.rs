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
    writer_fixture_arc(Arc::new(store)).await
}

async fn writer_fixture_arc(store: Arc<MsgStore>) -> (SqlitePool, Uuid, Uuid) {
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
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        store,
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

#[tokio::test]
async fn real_storage_writer_captures_large_resume_and_final_despite_ui_lag() {
    let store = Arc::new(MsgStore::with_durable_capture(8 * 1024 * 1024, 2, 8));
    let resume = serde_json::json!({"id":3,"result":{"history":"x".repeat(20 * 1024 * 1024)}})
        .to_string()
        + "\n";
    let final_event = serde_json::json!({"method":"item/completed","params":{"threadId":"t","turnId":"u","item":{"type":"agentMessage","id":"final","text":"actual final survives — ✓","phase":"final_answer","memoryCitation":null}}}).to_string() + "\n";
    let expected = resume + &final_event;
    let chunks: Vec<_> = expected
        .as_bytes()
        .chunks(4096)
        .map(|c| Ok::<_, std::io::Error>(axum::body::Bytes::copy_from_slice(c)))
        .collect();
    let source = store
        .clone()
        .spawn_forwarder(utils::execution_logs::decode_stdout(
            futures_util::stream::iter(chunks),
        ));
    // Metadata Finished can arrive before the blocked raw producer drains.
    // It must never terminate the capture of the queued suffix/final.
    store.push_finished();
    let (pool, execution, session) = writer_fixture_arc(store.clone()).await;
    source.await.unwrap();
    let path = utils::execution_logs::process_log_file_path(session, execution);
    let (bytes, messages) =
        utils::execution_logs::read_execution_log_strict(&path, 64 * 1024 * 1024)
            .await
            .unwrap();
    let captured: String = messages
        .into_iter()
        .filter_map(|m| match m {
            LogMsg::Stdout(s) => Some(s),
            _ => None,
        })
        .collect();
    assert_eq!(captured, expected);
    assert!(
        store.get_history_strict().is_err(),
        "force UI eviction independent of raw capture"
    );
    let proof: (i64, String) = sqlx::query_as(
        "SELECT raw_bytes,raw_sha256 FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(execution)
    .fetch_one(&pool)
    .await
    .unwrap();
    use sha2::{Digest, Sha256};
    assert_eq!(proof.0, bytes.len() as i64);
    assert_eq!(proof.1, format!("{:x}", Sha256::digest(&bytes)));
    utils::execution_logs::validate_native_capture(&path, 64 * 1024 * 1024)
        .await
        .unwrap();
    // Independent replay after producer/writer exit, as on restart.
    let (_, reopened) = utils::execution_logs::read_execution_log_strict(&path, 64 * 1024 * 1024)
        .await
        .unwrap();
    let replay = services::services::report_review::normalize_review_log(
        reopened,
        std::path::Path::new("/isolated/fixture"),
    )
    .await
    .unwrap();
    assert!(
        serde_json::to_string(&replay)
            .unwrap()
            .contains("actual final survives")
    );
}

#[tokio::test]
async fn interrupted_writer_valid_json_prefix_is_explicit_after_restart() {
    review_storage_root::assert_fixture_root();
    let path =
        utils::assets::asset_dir().join(format!("capture-interrupted-{}.jsonl", Uuid::new_v4()));
    let mut writer = utils::execution_logs::ExecutionLogWriter::new(path.clone())
        .await
        .unwrap();
    let record = LogMsg::Stdout("{\"id\":1,\"result\":{}}\n".into());
    writer
        .append_jsonl_line(&(serde_json::to_string(&record).unwrap() + "\n"))
        .await
        .unwrap();
    drop(writer);
    assert!(
        utils::execution_logs::validate_native_capture(&path, 1024)
            .await
            .is_err(),
        "Valid prefix is not successful closure after restart"
    );
    assert!(path.with_extension("capture.json").exists());
}

#[tokio::test]
async fn failed_raw_source_cannot_close_or_publish_review_proof() {
    let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 2));
    // A valid native prefix followed by a source error is not successful EOF,
    // even when metadata Finished has already arrived.
    let producer = store.clone().spawn_forwarder(futures_util::stream::iter([
        Ok(utils::log_msg::LogMsg::Stdout(
            "{\"id\":1,\"result\":{}}\n".into(),
        )),
        Err(std::io::Error::other("disposable source failed")),
    ]));
    store.push_finished();
    let (pool, execution, session) = writer_fixture_arc(store).await;
    producer.await.unwrap();
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(execution)
    .fetch_one(&pool)
    .await
    .unwrap();
    assert_eq!(count, 0, "Failed raw source must not certify a prefix");
    let path = utils::execution_logs::process_log_file_path(session, execution);
    assert!(
        utils::execution_logs::validate_native_capture(&path, 1024)
            .await
            .is_err()
    );
}

#[tokio::test(flavor = "current_thread")]
async fn map_removal_before_writer_first_poll_preserves_claim_and_drains() {
    review_storage_root::assert_fixture_root();
    let pool = fixture().await;
    let execution = Uuid::new_v4();
    let session = Uuid::new_v4();
    sqlx::query("INSERT INTO execution_processes VALUES(?,X'02')")
        .bind(execution)
        .execute(&pool)
        .await
        .unwrap();
    let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 1));
    let stores = Arc::new(RwLock::new(HashMap::from([(execution, store.clone())])));
    let chunks = [
        "{\"id\":1,\"result\":{}}\n",
        "{\"id\":2,\"result\":{}}\n",
        "{\"id\":3,\"result\":{}}\n",
    ];
    let producer = store.clone().spawn_forwarder(futures_util::stream::iter(
        chunks.map(|s| Ok::<_, std::io::Error>(LogMsg::Stdout(s.into()))),
    ));
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        store.clone(),
        db::DBService { pool: pool.clone() },
        execution,
        session,
    );
    // No await/yield after spawn: on this single-thread runtime the writer has
    // never been polled. Cleanup removes the real map entry first.
    assert!(
        store.take_durable_capture().is_none(),
        "Receiver must already be claimed"
    );
    assert!(services::services::execution_process::capture_in_progress(
        execution
    ));
    stores
        .try_write()
        .unwrap()
        .remove(&execution)
        .unwrap()
        .push_finished();
    drop(stores);
    // Deliberately evict Finished from the two-slot UI broadcast before either
    // writer or producer can be polled. Raw EOF plus the real lifecycle marker
    // must still close; these UI-only values must not enter durable raw capture.
    store.push_stdout("UI-only after Finished 1");
    store.push_stdout("UI-only after Finished 2");
    tokio::time::timeout(Duration::from_secs(5), async {
        producer.await.unwrap();
        writer.await.unwrap();
    })
    .await
    .unwrap();
    assert!(!services::services::execution_process::capture_in_progress(
        execution
    ));
    let path = utils::execution_logs::process_log_file_path(session, execution);
    let (_, records) = utils::execution_logs::read_execution_log_strict(&path, 4096)
        .await
        .unwrap();
    let actual: String = records
        .into_iter()
        .filter_map(|m| {
            if let LogMsg::Stdout(s) = m {
                Some(s)
            } else {
                None
            }
        })
        .collect();
    assert_eq!(actual, chunks.concat());
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(execution)
    .fetch_one(&pool)
    .await
    .unwrap();
    assert_eq!(count, 1);
}

#[tokio::test(flavor = "current_thread")]
async fn cancelling_unpolled_writer_releases_owner_and_unblocks_producer() {
    review_storage_root::assert_fixture_root();
    let pool = fixture().await;
    let execution = Uuid::new_v4();
    let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 1));
    let producer = store.clone().spawn_forwarder(futures_util::stream::iter(
        (0..3).map(|_| Ok::<_, std::io::Error>(LogMsg::Stdout("fixture".into()))),
    ));
    let writer = services::services::execution_process::spawn_stream_raw_logs_to_storage(
        store,
        db::DBService { pool: pool.clone() },
        execution,
        Uuid::new_v4(),
    );
    assert!(services::services::execution_process::capture_in_progress(
        execution
    ));
    writer.abort();
    assert!(writer.await.unwrap_err().is_cancelled());
    assert!(!services::services::execution_process::capture_in_progress(
        execution
    ));
    tokio::time::timeout(Duration::from_secs(2), producer)
        .await
        .unwrap()
        .unwrap();
    let count: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM workspace_review_log_finalized WHERE execution_id=?",
    )
    .bind(execution)
    .fetch_one(&pool)
    .await
    .unwrap();
    assert_eq!(count, 0);
}

// Combined acceptance: real enlarged consent context through the durable writer,
// independent normalization and the incumbent strict JSONL reader after closure.
#[path = "fixtures/c3_strict_log_reader.rs"]
mod c3_strict_log_reader;

#[tokio::test]
async fn complete_large_consent_survives_capture_and_incumbent_reader() {
    let prompt = "🧭".repeat(60_000);
    let params = serde_json::from_value(serde_json::json!({
        "threadId":"synthetic-combined", "turnId":null, "serverName":"codex_apps",
        "mode":"form", "message":"Allow this app to run tool \"run_session_prompt\"?",
        "requestedSchema":{"type":"object","properties":{}},
        "_meta":{"codex_approval_kind":"mcp_tool_call", "tool_title":"run_session_prompt",
            "source":"connector", "connector_id":"synthetic-vk", "connector_name":"Synthetic VK",
            "tool_params":{"prompt":prompt},
            "tool_params_display":[{"name":"prompt","display_name":"prompt","value":prompt}]}
    }))
    .unwrap();
    let summary = executors::executors::codex::elicitation::validate_consent(&params).unwrap();
    assert!(summary.contains(&prompt));
    let requested = executors::executors::codex::normalize_logs::Approval::McpApprovalRequested {
        call_id: "synthetic-combined-call".into(),
        approval_id: "synthetic-pending".into(),
        server_name: "codex_apps".into(),
        message: summary,
    }
    .raw();
    let final_event = serde_json::json!({"method":"item/completed","params":{"threadId":"t","turnId":"u","item":{"type":"agentMessage","id":"synthetic-final","text":"synthetic combined capture complete","phase":"final_answer","memoryCitation":null}}}).to_string();
    let expected = requested + "\n" + &final_event + "\n";
    let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 2));
    let chunks: Vec<_> = expected
        .as_bytes()
        .chunks(4093)
        .map(|c| Ok::<_, std::io::Error>(axum::body::Bytes::copy_from_slice(c)))
        .collect();
    let source = store
        .clone()
        .spawn_forwarder(utils::execution_logs::decode_stdout(
            futures_util::stream::iter(chunks),
        ));
    store.push_finished();
    let (_, execution, session) = writer_fixture_arc(store).await;
    source.await.unwrap();
    let path = utils::execution_logs::process_log_file_path(session, execution);
    utils::execution_logs::validate_native_capture(&path, 2 * 1024 * 1024)
        .await
        .unwrap();
    let (old_bytes, old_records) =
        c3_strict_log_reader::read_execution_log_strict(&path, 2 * 1024 * 1024)
            .await
            .unwrap();
    let (new_bytes, new_records) =
        utils::execution_logs::read_execution_log_strict(&path, 2 * 1024 * 1024)
            .await
            .unwrap();
    assert_eq!(old_bytes, new_bytes);
    assert_eq!(
        serde_json::to_value(&old_records).unwrap(),
        serde_json::to_value(&new_records).unwrap()
    );
    let captured: String = old_records
        .into_iter()
        .filter_map(|m| match m {
            LogMsg::Stdout(s) => Some(s),
            _ => None,
        })
        .collect();
    assert_eq!(captured, expected);
    let replay = services::services::report_review::normalize_review_log(
        new_records,
        std::path::Path::new("/isolated/fixture"),
    )
    .await
    .unwrap();
    let replay_json = serde_json::to_string(&replay).unwrap();
    assert!(
        replay_json.contains(&prompt),
        "The entire consequential context must survive replay"
    );
    assert!(replay_json.contains("synthetic combined capture complete"));
    assert!(
        replay_json.contains("pending_approval"),
        "Capture must not manufacture approval"
    );
}
