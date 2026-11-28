use std::{
    collections::HashMap,
    io::SeekFrom,
    sync::{LazyLock, Mutex},
    time::SystemTime,
};

use chrono::{DateTime, Utc};
use serde::Deserialize;
use tokio::{
    fs::File,
    io::{AsyncReadExt, AsyncSeekExt},
};

use super::SubagentJobStatus;

// Sidebar requests must never scan entire (potentially very large) transcripts.
const MAX_TAIL_BYTES: u64 = 1024 * 1024;

#[derive(Clone, Debug)]
pub(super) struct TurnState {
    pub status: SubagentJobStatus,
    pub timestamp: DateTime<Utc>,
}

#[derive(Clone)]
struct CachedState {
    len: u64,
    modified: SystemTime,
    state: Option<TurnState>,
}

// Cache only the derived state, never transcript contents. Metadata changes on
// completion or follow-up invalidate it, even if Codex's SQLite row lags behind.
static CACHE: LazyLock<Mutex<HashMap<String, CachedState>>> = LazyLock::new(Mutex::default);
const MAX_CACHED_ROLLOUTS: usize = 1024;

#[derive(Deserialize)]
struct RolloutEntry {
    timestamp: DateTime<Utc>,
    #[serde(rename = "type")]
    kind: String,
    payload: Payload,
}

#[derive(Deserialize)]
struct Payload {
    #[serde(rename = "type", default)]
    kind: String,
    #[serde(default)]
    error: Option<serde::de::IgnoredAny>,
}

/// Read only a stable, bounded tail. Missing, truncated or changing evidence is
/// unknown; it must not turn an old completion into proof that new work ended.
pub(super) async fn latest_turn_state(path: &str) -> Option<TurnState> {
    let mut file = File::open(path).await.ok()?;
    let before = file.metadata().await.ok()?;
    if !before.is_file() {
        return None;
    }
    let modified = before.modified().ok()?;
    if let Some(cached) = CACHE
        .lock()
        .ok()?
        .get(path)
        .filter(|cached| cached.len == before.len() && cached.modified == modified)
        .cloned()
    {
        return cached.state;
    }
    let start = before.len().saturating_sub(MAX_TAIL_BYTES);
    file.seek(SeekFrom::Start(start)).await.ok()?;
    let mut bytes = vec![0; (before.len() - start) as usize];
    file.read_exact(&mut bytes).await.ok()?;
    let after = file.metadata().await.ok()?;
    if before.len() != after.len() || before.modified().ok()? != after.modified().ok()? {
        return None;
    }
    // The first line may start outside this window; never parse that fragment.
    let bytes = if start > 0 {
        &bytes[bytes.iter().position(|byte| *byte == b'\n')? + 1..]
    } else {
        &bytes
    };
    let state = turn_state_from_tail(bytes);
    if let Ok(mut cache) = CACHE.lock() {
        if cache.len() >= MAX_CACHED_ROLLOUTS {
            cache.clear();
        }
        cache.insert(
            path.to_owned(),
            CachedState {
                len: before.len(),
                modified,
                state: state.clone(),
            },
        );
    }
    state
}

fn turn_state_from_tail(bytes: &[u8]) -> Option<TurnState> {
    if !bytes.ends_with(b"\n") {
        return None;
    }
    let mut later_activity = false;
    for line in bytes
        .rsplit(|byte| *byte == b'\n')
        .filter(|line| !line.is_empty())
    {
        // Stop at malformed records, rather than trusting an older completion.
        let entry: RolloutEntry = serde_json::from_slice(line).ok()?;
        if entry.kind != "event_msg" {
            later_activity |= matches!(entry.kind.as_str(), "response_item" | "turn_context");
            continue;
        }
        let status = match entry.payload.kind.as_str() {
            "task_started" | "turn_started" => SubagentJobStatus::Running,
            "task_complete" | "turn_complete" if !later_activity => {
                if entry.payload.error.is_some() {
                    SubagentJobStatus::Failed
                } else {
                    SubagentJobStatus::Completed
                }
            }
            "turn_aborted" if !later_activity => SubagentJobStatus::Failed,
            "task_complete" | "turn_complete" | "turn_aborted" => return None,
            "user_message" => {
                later_activity = true;
                continue;
            }
            _ => continue,
        };
        return Some(TurnState {
            status,
            timestamp: entry.timestamp,
        });
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn event(kind: &str) -> String {
        format!(
            "{{\"timestamp\":\"2026-10-15T21:23:10.628Z\",\"type\":\"event_msg\",\"payload\":{{\"type\":\"{kind}\",\"turn_id\":\"child-turn\"}}}}\n"
        )
    }

    #[test]
    fn latest_turn_controls_status_including_reuse_and_abort() {
        for (first, last, expected) in [
            (
                "task_started",
                "task_complete",
                SubagentJobStatus::Completed,
            ),
            ("task_complete", "task_started", SubagentJobStatus::Running),
            (
                "turn_started",
                "turn_complete",
                SubagentJobStatus::Completed,
            ),
            ("task_started", "turn_aborted", SubagentJobStatus::Failed),
        ] {
            let state = turn_state_from_tail((event(first) + &event(last)).as_bytes()).unwrap();
            assert_eq!(state.status, expected);
        }
    }

    #[test]
    fn uncertain_tail_never_reuses_an_old_completion() {
        for suffix in [
            "{\"type\":\"event_msg\",\"payload\":", // concurrent partial write
            "invalid\n",
            "{\"timestamp\":\"2026-10-15T21:24:00Z\",\"type\":\"response_item\",\"payload\":{\"type\":\"message\"}}\n",
        ] {
            assert!(turn_state_from_tail((event("task_complete") + suffix).as_bytes()).is_none());
        }
        assert!(turn_state_from_tail(event("token_count").as_bytes()).is_none());
    }

    #[test]
    fn terminal_error_is_failed_and_bookkeeping_after_completion_is_ignored() {
        let failed = "{\"timestamp\":\"2026-10-15T21:23:10Z\",\"type\":\"event_msg\",\"payload\":{\"type\":\"task_complete\",\"error\":{\"message\":\"test failure\"}}}\n";
        assert_eq!(
            turn_state_from_tail(failed.as_bytes()).unwrap().status,
            SubagentJobStatus::Failed
        );
        let completed = event("task_complete") + &event("token_count");
        assert_eq!(
            turn_state_from_tail(completed.as_bytes()).unwrap().status,
            SubagentJobStatus::Completed
        );
    }

    #[tokio::test]
    async fn reads_bounded_tail_and_observes_appended_followup() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("rollout.jsonl");
        let mut bytes = vec![b'x'; MAX_TAIL_BYTES as usize + 10];
        bytes.push(b'\n');
        bytes.extend_from_slice(event("task_complete").as_bytes());
        tokio::fs::write(&path, &bytes).await.unwrap();
        let path = path.to_str().unwrap();
        assert_eq!(
            latest_turn_state(path).await.unwrap().status,
            SubagentJobStatus::Completed
        );

        bytes.extend_from_slice(event("task_started").as_bytes());
        tokio::fs::write(path, &bytes).await.unwrap();
        assert_eq!(
            latest_turn_state(path).await.unwrap().status,
            SubagentJobStatus::Running
        );
        tokio::fs::remove_file(path).await.unwrap();
        assert!(latest_turn_state(path).await.is_none());
    }
}
