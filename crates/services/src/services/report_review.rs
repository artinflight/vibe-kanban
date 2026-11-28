//! Integrity-only durable report replay. Never use UI recovery/log caches here.
use std::{io, path::Path, sync::Arc};

use db::models::execution_process::ExecutionProcess;
use executors::executors::{BaseCodingAgent, codex::normalize_logs};
use sha2::{Digest, Sha256};
use sqlx::{Row, SqlitePool};
use utils::{
    execution_logs::{process_log_file_path, read_execution_log_strict},
    log_msg::LogMsg,
    msg_store::MsgStore,
};

pub const MAX_RAW_BYTES: usize = 32 * 1024 * 1024;
const MAX_REPLAY_BYTES: usize = 64 * 1024 * 1024;

pub async fn closed_review_log(
    pool: &SqlitePool,
    session: uuid::Uuid,
    execution: uuid::Uuid,
) -> io::Result<Vec<LogMsg>> {
    let proof = sqlx::query("SELECT raw_bytes,raw_sha256 FROM workspace_review_log_finalized WHERE execution_id=?")
        .bind(execution).fetch_optional(pool).await.map_err(|_| io::Error::other("Closed-log proof unavailable"))?
        .ok_or_else(|| io::Error::other("Successful closed-log writer proof missing; historical reports require release-owner closure validation"))?;
    let (bytes, messages) =
        read_execution_log_strict(&process_log_file_path(session, execution), MAX_RAW_BYTES)
            .await?;
    if proof.get::<i64, _>("raw_bytes") != bytes.len() as i64
        || proof.get::<String, _>("raw_sha256") != format!("{:x}", Sha256::digest(&bytes))
    {
        return Err(io::Error::other("Closed-log bytes/hash changed"));
    }
    Ok(messages)
}

// Dropping a timed-out or failed verification aborts all normalization jobs;
// detached partial replays must never continue after the caller rejects them.
struct Normalizers(Vec<tokio::task::JoinHandle<()>>);
impl Drop for Normalizers {
    fn drop(&mut self) {
        for handle in &self.0 {
            handle.abort();
        }
    }
}

async fn join_normalizers(mut jobs: Normalizers) -> io::Result<()> {
    for handle in &mut jobs.0 {
        handle
            .await
            .map_err(|_| io::Error::other("Review normalizer failed"))?;
    }
    Ok(())
}

pub async fn normalize_review_log(messages: Vec<LogMsg>, dir: &Path) -> io::Result<Vec<LogMsg>> {
    // Stdout chunks can split a JSON event at any byte. Validate the reconstructed
    // native stream, not each chunk. Stderr is intentionally plain diagnostic text.
    let stdout: String = messages
        .iter()
        .filter_map(|m| match m {
            LogMsg::Stdout(s) => Some(s.as_str()),
            _ => None,
        })
        .collect();
    if stdout.is_empty() || !stdout.ends_with('\n') {
        return Err(io::Error::other("Missing/partial native stdout"));
    }
    for line in stdout.lines() {
        normalize_logs::validate_review_line(line)?;
    }
    drop(stdout);
    let store = Arc::new(MsgStore::with_limits(MAX_REPLAY_BYTES, 100_001));
    // Populate a bounded finite input BEFORE normalizers start. They cannot lag
    // a live feed or certify read errors represented as ordinary stderr output.
    for msg in messages {
        store.push(msg);
    }
    store.push_finished();
    join_normalizers(Normalizers(normalize_logs::normalize_logs(
        store.clone(),
        dir,
    )))
    .await?;
    let mut patches = Vec::new();
    // Input Finished precedes normalized output: examine the entire finite,
    // loss-checked snapshot, including patches produced AFTER input completion.
    for msg in store.get_history_strict()? {
        if matches!(msg, LogMsg::JsonPatch(_)) {
            patches.push(msg);
        }
    }
    patches.push(LogMsg::Finished); // Only after ALL fallible work has succeeded.
    Ok(patches)
}

pub async fn replay_review_log(
    pool: &SqlitePool,
    process: &ExecutionProcess,
    dir: &Path,
) -> io::Result<Vec<LogMsg>> {
    if process
        .executor_action()
        .map_err(|_| io::Error::other("Executor action invalid"))?
        .base_executor()
        != Some(BaseCodingAgent::Codex)
    {
        return Err(io::Error::other(
            "Strict report identity currently supports Codex only",
        ));
    }
    let messages = closed_review_log(pool, process.session_id, process.id).await?;
    normalize_review_log(messages, dir).await
}

#[cfg(test)]
mod review_tests {
    use super::*;
    #[tokio::test]
    async fn review_normalizer_join_failure_is_not_finished() {
        let jobs = Normalizers(vec![tokio::spawn(async {
            panic!("isolated normalizer failure");
        })]);
        assert!(join_normalizers(jobs).await.is_err());
    }
    #[tokio::test]
    async fn review_normalizer_timeout_aborts_remaining_jobs() {
        let done = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let signal = done.clone();
        let jobs = Normalizers(vec![tokio::spawn(async move {
            tokio::time::sleep(std::time::Duration::from_millis(50)).await;
            signal.store(true, std::sync::atomic::Ordering::SeqCst);
        })]);
        assert!(
            tokio::time::timeout(std::time::Duration::from_millis(5), join_normalizers(jobs))
                .await
                .is_err()
        );
        tokio::time::sleep(std::time::Duration::from_millis(70)).await;
        assert!(!done.load(std::sync::atomic::Ordering::SeqCst));
    }
    #[tokio::test]
    async fn review_rejects_malformed_native_event_and_partial_stdout() {
        for native in [
            "broken JSON\n",
            "{\"method\":\"item/completed\",\"params\":{}}\n",
            "{}",
        ] {
            assert!(
                normalize_review_log(
                    vec![LogMsg::Stdout(native.into())],
                    Path::new("/isolated/fixture")
                )
                .await
                .is_err()
            );
        }
    }
}
