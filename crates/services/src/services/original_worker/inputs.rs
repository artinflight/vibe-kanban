//! Streaming native input freshness, independent of the mutable VK action.
//! Prefix serialization is byte-compatible with the original Vec<Value> seal.
use std::{
    collections::HashMap,
    fs::{File, Metadata},
    io::{self, BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::{Arc, OnceLock},
};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use sqlx::{
    Connection,
    sqlite::{SqliteConnectOptions, SqliteConnection},
};

use super::{digest, invalid};

// Bound the allocation for one JSONL record, not the lifetime of a thread.
// The buffer is reused; no transcript, input list or serialized prefix is held.
const MAX_RECORD_BYTES: u64 = 16 * 1024 * 1024;

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InputSeal {
    pub coverage_id: uuid::Uuid,
    pub backend_sequence: i64,
    pub rollout: PathBuf,
    pub records: usize,
    pub prefix_digest: String,
}

struct Input {
    kind: String,
    payload: Value,
    text: Option<String>,
}

fn input(line: &[u8]) -> io::Result<Option<Input>> {
    let entry: Value = serde_json::from_slice(line)
        .map_err(|_| invalid("Native history incomplete or invalid"))?;
    let kind = entry["type"]
        .as_str()
        .ok_or_else(|| invalid("Unknown native history envelope"))?;
    let p = &entry["payload"];
    let event = p["type"].as_str().unwrap_or("");
    if kind == "response_item" && event == "message" && p["role"] == "user" {
        // Adopted historical inputs may contain images. Preserve their entire
        // payload in the prefix seal; only newly dispatched plain text can
        // match a backend-owned continuation receipt.
        let text = p["content"].as_array().and_then(|content| {
            content.iter().try_fold(String::new(), |mut text, item| {
                if item["type"] != "input_text" {
                    return None;
                }
                text.push_str(item["text"].as_str()?);
                Some(text)
            })
        });
        return Ok(Some(Input {
            kind: "response".into(),
            payload: p.clone(),
            text,
        }));
    } else if kind == "event_msg" && event == "user_message" {
        return Ok(Some(Input {
            kind: "event".into(),
            payload: p.clone(),
            text: Some(
                p["message"]
                    .as_str()
                    .ok_or_else(|| invalid("Unknown native steering text"))?
                    .into(),
            ),
        }));
    } else if kind == "event_msg"
        && ["rollback", "rolled_back", "reset", "steer", "drop", "input"]
            .iter()
            .any(|s| event.contains(s))
    {
        return Ok(Some(Input {
            kind: "amendment".into(),
            payload: p.clone(),
            text: None,
        }));
    } else if !matches!(
        kind,
        "session_meta"
            | "turn_context"
            | "response_item"
            | "event_msg"
            | "compacted"
            | "world_state"
            | "token_usage_record"
    ) {
        return Err(invalid("Unknown native history record"));
    } else if matches!(kind, "compacted" | "world_state") {
        // World state contains instruction/permission inputs. Adopted records
        // are sealed in full; a new one cannot be authorized as plain text.
        return Ok(Some(Input {
            kind: "amendment".into(),
            payload: p.clone(),
            text: None,
        }));
    }
    Ok(None)
}

struct HashWriter(Sha256);
impl Write for HashWriter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0.update(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn verify_stream(
    mut reader: impl BufRead,
    seal: &InputSeal,
    authorized: &[String],
) -> io::Result<()> {
    let mut prefix = HashWriter(Sha256::new());
    prefix.write_all(b"[")?;
    let mut records = 0usize;
    let mut allowed = HashMap::<&str, usize>::new();
    for hash in authorized {
        *allowed.entry(hash).or_default() += 1;
    }
    let mut seen = HashMap::<(String, String), usize>::new();
    let mut line = Vec::new();
    loop {
        line.clear();
        // take() stops even a malicious unterminated record from allocating
        // indefinitely. Parsing must also validate ignored output records.
        let n = reader
            .by_ref()
            .take(MAX_RECORD_BYTES + 1)
            .read_until(b'\n', &mut line)?;
        if n == 0 {
            break;
        }
        if n as u64 > MAX_RECORD_BYTES {
            return Err(invalid("Native history record exceeds verification bound"));
        }
        if line.last() == Some(&b'\n') {
            line.pop();
        }
        if line.is_empty() {
            continue;
        }
        let Some(record) = input(&line)? else {
            continue;
        };
        if records < seal.records {
            if records != 0 {
                prefix.write_all(b",")?;
            }
            serde_json::to_writer(&mut prefix, &record.payload)?;
        } else {
            let text = record
                .text
                .as_ref()
                .ok_or_else(|| invalid("Native input history amended"))?;
            let hash = digest(text.as_bytes());
            // Reject before storing an unknown digest: memory is bounded by
            // durable receipts, not by the number of attacker supplied inputs.
            let limit = allowed.get(hash.as_str()).copied().unwrap_or(0);
            if limit == 0 {
                return Err(invalid("Unaccounted native user or steering input"));
            }
            let count = seen.entry((record.kind, hash)).or_default();
            *count += 1;
            if *count > limit {
                return Err(invalid("Unaccounted native user or steering input"));
            }
        }
        records = records
            .checked_add(1)
            .ok_or_else(|| invalid("Native input count overflow"))?;
    }
    if records < seal.records {
        return Err(invalid("Native input history was reset"));
    }
    prefix.write_all(b"]")?;
    if format!("{:x}", prefix.0.finalize()) != seal.prefix_digest {
        return Err(invalid("Native input prefix changed"));
    }
    Ok(())
}

#[cfg(test)]
fn verify(bytes: &[u8], seal: &InputSeal, authorized: &[String]) -> io::Result<()> {
    verify_stream(io::Cursor::new(bytes), seal, authorized)
}

fn same_file(a: &Metadata, b: &Metadata) -> bool {
    if !a.is_file() || !b.is_file() || a.len() != b.len() || a.modified().ok() != b.modified().ok()
    {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        a.dev() == b.dev()
            && a.ino() == b.ino()
            && a.mtime_nsec() == b.mtime_nsec()
            && a.ctime() == b.ctime()
            && a.ctime_nsec() == b.ctime_nsec()
    }
    #[cfg(not(unix))]
    {
        false
    } // Bootstrap currently requires Unix object identity.
}

struct Snapshot {
    file: File,
    before: Metadata,
    path: PathBuf,
}
impl Snapshot {
    fn open(path: PathBuf) -> io::Result<Self> {
        let before = std::fs::metadata(&path)?;
        if !before.is_file() {
            return Err(invalid("Native rollout is not a regular file"));
        }
        let file = File::open(&path)?;
        let snapshot = Self { file, before, path };
        snapshot.unchanged()?;
        Ok(snapshot)
    }
    fn unchanged(&self) -> io::Result<()> {
        if !same_file(&self.before, &self.file.metadata()?)
            || !same_file(&self.before, &std::fs::metadata(&self.path)?)
        {
            return Err(invalid("Native history changed during verification"));
        }
        Ok(())
    }
    fn verify(&mut self, seal: &InputSeal, authorized: &[String]) -> io::Result<()> {
        // Read only the initially observed extent, never chase an active writer.
        verify_stream(
            BufReader::new((&mut self.file).take(self.before.len())),
            seal,
            authorized,
        )?;
        self.unchanged()
    }
}

async fn indexed_path(
    db: &mut SqliteConnection,
    thread: &str,
    home: &Path,
    seal: &InputSeal,
) -> io::Result<PathBuf> {
    let path: String = sqlx::query_scalar("SELECT rollout_path FROM threads WHERE id=?")
        .bind(thread)
        .fetch_one(db)
        .await
        .map_err(|_| invalid("Native rollout binding unavailable"))?;
    let path = PathBuf::from(path).canonicalize()?;
    if path != seal.rollout || !path.starts_with(home) {
        return Err(invalid("Native rollout binding changed"));
    }
    Ok(path)
}

/// The shared startup and invocation verifier. No history, index or grant writes.
/// Blocking parsing stays off the async runtime. One in-flight scan bounds host
/// memory even when several callers verify large histories concurrently.
pub async fn verify_native(
    thread: &str,
    seal: &InputSeal,
    authorized: &[String],
) -> io::Result<()> {
    let home = executors::executors::codex::codex_home()
        .ok_or_else(|| invalid("Native home unavailable"))?;
    verify_in_home(&home, thread, seal, authorized).await
}

async fn verify_in_home(
    home: &Path,
    thread: &str,
    seal: &InputSeal,
    authorized: &[String],
) -> io::Result<()> {
    verify_after_scan(home, thread, seal, authorized, || async { Ok(()) }).await
}

async fn verify_after_scan<F, Fut>(
    home: &Path,
    thread: &str,
    seal: &InputSeal,
    authorized: &[String],
    after_scan: F,
) -> io::Result<()>
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = io::Result<()>>,
{
    static SCANS: OnceLock<Arc<tokio::sync::Semaphore>> = OnceLock::new();
    let permit = SCANS
        .get_or_init(|| Arc::new(tokio::sync::Semaphore::new(1)))
        .clone()
        .acquire_owned()
        .await
        .map_err(|_| invalid("Native verifier unavailable"))?;
    let home = home.canonicalize()?;
    let index = home.join("state_5.sqlite");
    let index_before = std::fs::metadata(&index)?;
    let mut db = SqliteConnection::connect_with(
        &SqliteConnectOptions::new()
            .filename(&index)
            .read_only(true)
            .create_if_missing(false),
    )
    .await
    .map_err(|_| invalid("Native input index unavailable"))?;
    let path = indexed_path(&mut db, thread, &home, seal).await?;
    let owned_seal = seal.clone();
    let authorized = authorized.to_vec();
    let (snapshot, _permit) = tokio::task::spawn_blocking(move || {
        let mut snapshot = Snapshot::open(path)?;
        snapshot.verify(&owned_seal, &authorized)?;
        // Retain the permit even if the awaiting future was cancelled.
        Ok::<_, io::Error>((snapshot, permit))
    })
    .await
    .map_err(|_| invalid("Native verifier failed"))??;
    after_scan().await?;
    indexed_path(&mut db, thread, &home, seal).await?;
    // SQLite may legitimately change while unrelated threads run. Refuse index
    // object replacement without rejecting those unrelated WAL transactions.
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        let after = std::fs::metadata(&index)?;
        if (index_before.dev(), index_before.ino()) != (after.dev(), after.ino()) {
            return Err(invalid("Native input index replaced"));
        }
    }
    snapshot.unchanged()
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn wire(v: Value) -> Vec<u8> {
        serde_json::to_vec(&v).unwrap()
    }
    fn seal() -> InputSeal {
        InputSeal {
            coverage_id: uuid::Uuid::new_v4(),
            backend_sequence: 0,
            rollout: "/synthetic/native.jsonl".into(),
            records: 0,
            prefix_digest: digest(b"[]"),
        }
    }
    #[test]
    fn unchanged_goal_does_not_hide_steering_or_dropped_reset_history() {
        for payload in [
            json!({"type":"user_message","message":"Synthetic amendment"}),
            json!({"type":"thread_rolled_back","num_turns":1}),
            json!({"type":"input_dropped","id":"synthetic"}),
        ] {
            assert!(
                verify(
                    &wire(json!({"type":"event_msg","payload":payload})),
                    &seal(),
                    &[]
                )
                .is_err()
            );
        }
        assert!(verify(b"{\"type\":", &seal(), &[]).is_err());
    }
    #[test]
    fn only_exact_activated_input_and_one_record_per_native_kind_are_admitted() {
        let event = wire(
            json!({"type":"event_msg","payload":{"type":"user_message","message":"Synthetic fixed continuation"}}),
        );
        let response = wire(
            json!({"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Synthetic fixed continuation"}]}}),
        );
        let allowed = [digest(b"Synthetic fixed continuation")];
        let mut both = event.clone();
        both.push(b'\n');
        both.extend_from_slice(&response);
        verify(&both, &seal(), &allowed).unwrap();
        both.push(b'\n');
        both.extend_from_slice(&event);
        assert!(verify(&both, &seal(), &allowed).is_err());
        assert!(verify(&response, &seal(), &[digest(b"Altered synthetic prompt")]).is_err());
    }
    #[test]
    fn pinned_prefix_cannot_be_truncated_or_replaced() {
        let p = json!({"type":"user_message","message":"Synthetic adopted input"});
        let seal = InputSeal {
            records: 1,
            prefix_digest: digest(&wire(json!([p.clone()]))),
            ..seal()
        };
        verify(&wire(json!({"type":"event_msg","payload":p})), &seal, &[]).unwrap();
        assert!(verify(b"", &seal, &[]).is_err());
        assert!(verify(&wire(json!({"type":"event_msg","payload":{"type":"user_message","message":"Changed synthetic input"}})),&seal,&[]).is_err());
    }
}

#[cfg(test)]
#[path = "inputs_tests.rs"]
mod streaming_tests;
