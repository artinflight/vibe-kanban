//! Identity-bound recovery of a native final for presentation ONLY.
//! Never mutates execution status, raw capture, closure proofs, turns or badges.
use std::{
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::{Arc, OnceLock},
};

use axum::{Extension, Json, extract::State};
use chrono::{DateTime, Utc};
use db::models::{
    execution_process::{ExecutionProcess, ExecutionProcessRunReason, ExecutionProcessStatus},
    session::Session,
};
use deployment::Deployment;
use executors::{
    actions::ExecutorActionType,
    executors::{BaseCodingAgent, codex::codex_home},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError, middleware::RelayRequestSignatureContext};

const MAX_SOURCE_BYTES: u64 = 256 * 1024 * 1024;
const MAX_LINE_BYTES: u64 = 16 * 1024 * 1024;
const MAX_FINAL_BYTES: usize = 128_000;
const NOTICE: &str = "Original raw capture is incomplete. This reply was recovered from an identity-verified native transcript; other missing messages are not reconstructed. Recovery does not certify capture completeness or task success.";

type RecoveryResult<T> = Result<T, String>;

// Large native histories are verified one at a time, without retaining them.
async fn permit() -> Result<tokio::sync::OwnedSemaphorePermit, ApiError> {
    static LIMIT: OnceLock<Arc<tokio::sync::Semaphore>> = OnceLock::new();
    LIMIT
        .get_or_init(|| Arc::new(tokio::sync::Semaphore::new(1)))
        .clone()
        .acquire_owned()
        .await
        .map_err(|_| ApiError::Conflict("Recovery verifier unavailable".into()))
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub(super) struct RecoveryRequest {
    pub workspace_id: Uuid,
    pub session_id: Uuid,
    pub execution_revision: DateTime<Utc>,
    pub native_session_id: Uuid,
    pub native_turn_id: Uuid,
    pub source_prefix_bytes: u64,
    pub source_prefix_sha256: String,
    pub original_capture_sha256: String,
    pub prompt_sha256: String,
    pub reply_sha256: String,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct RecoveredFinal {
    version: u32,
    execution_id: Uuid,
    evidence: RecoveryRequest,
    final_at: DateTime<Utc>,
    final_line: usize,
    closure_line: usize,
    native_message_id: Option<String>,
    text: String,
}

fn sha(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[allow(clippy::result_large_err)]
fn authorize(auth: Option<Extension<RelayRequestSignatureContext>>) -> Result<(), ApiError> {
    if auth.is_none() {
        return Err(ApiError::Unauthorized);
    }
    Ok(())
}

fn checked_hash(hash: &str) -> RecoveryResult<()> {
    if hash.len() != 64
        || !hash
            .bytes()
            .all(|x| x.is_ascii_digit() || (b'a'..=b'f').contains(&x))
    {
        return Err("Expected a lowercase SHA-256 digest".into());
    }
    Ok(())
}

fn binding(process: &ExecutionProcess, request: &RecoveryRequest) -> RecoveryResult<String> {
    if process.status != ExecutionProcessStatus::Completed
        || process.exit_code != Some(0)
        || process.dropped
        || process.run_reason != ExecutionProcessRunReason::CodingAgent
        || process.session_id != request.session_id
        || process.updated_at != request.execution_revision
    {
        return Err("Execution identity/revision is not the expected completed original".into());
    }
    for hash in [
        &request.source_prefix_sha256,
        &request.original_capture_sha256,
        &request.prompt_sha256,
        &request.reply_sha256,
    ] {
        checked_hash(hash)?;
    }
    if request.source_prefix_bytes == 0 || request.source_prefix_bytes > MAX_SOURCE_BYTES {
        return Err("Native transcript prefix exceeds the bounded recovery size".into());
    }
    let action = process
        .executor_action()
        .map_err(|_| "Execution configuration unavailable")?;
    if action.base_executor() != Some(BaseCodingAgent::Codex) {
        return Err("Only an existing Codex continuation can be recovered".into());
    }
    let ExecutorActionType::CodingAgentFollowUpRequest(followup) = action.typ else {
        return Err("A recorded original native continuation identity is required".into());
    };
    if followup.reset_to_message_id.is_some()
        || Uuid::parse_str(&followup.session_id).ok() != Some(request.native_session_id)
        || followup.prompt.is_empty()
        || sha(followup.prompt.as_bytes()) != request.prompt_sha256
    {
        return Err("Original native session/prompt does not match the request".into());
    }
    Ok(followup.prompt)
}

// No request supplies a filename. Enumerate only yyyy/mm/dd directories below
// the existing Codex sessions root, then open the single matching native UUID.
fn native_path(home: &Path, native: Uuid) -> RecoveryResult<PathBuf> {
    let root = home.join("sessions");
    regular_directory(&root)?;
    let mut paths = vec![root];
    let mut visited = 0;
    for width in [4, 2, 2] {
        let mut next = vec![];
        for parent in paths {
            for entry in
                fs::read_dir(parent).map_err(|_| "Native transcript directory unavailable")?
            {
                visited += 1;
                if visited > 20_000 {
                    return Err("Native transcript discovery limit exceeded".into());
                }
                let entry = entry.map_err(|_| "Native transcript directory damaged")?;
                let name = entry.file_name();
                let Some(name) = name.to_str() else {
                    continue;
                };
                if name.len() != width || !name.bytes().all(|x| x.is_ascii_digit()) {
                    continue;
                }
                if entry
                    .file_type()
                    .map_err(|_| "Native directory metadata unavailable")?
                    .is_dir()
                {
                    next.push(entry.path());
                }
            }
        }
        paths = next;
    }
    let suffix = format!("-{native}.jsonl");
    let mut found = None;
    for parent in paths {
        for entry in fs::read_dir(parent).map_err(|_| "Native transcript directory unavailable")? {
            visited += 1;
            if visited > 100_000 {
                return Err("Native transcript discovery limit exceeded".into());
            }
            let entry = entry.map_err(|_| "Native transcript directory damaged")?;
            let name = entry.file_name();
            let Some(name) = name.to_str() else {
                continue;
            };
            if name.starts_with("rollout-") && name.ends_with(&suffix) {
                if !entry
                    .file_type()
                    .map_err(|_| "Native transcript metadata unavailable")?
                    .is_file()
                    || found.is_some()
                {
                    return Err("Ambiguous or non-regular native transcript".into());
                }
                found = Some(entry.path());
            }
        }
    }
    found.ok_or_else(|| "Native transcript not found in the configured Codex home".into())
}

fn regular_directory(path: &Path) -> RecoveryResult<()> {
    if !fs::symlink_metadata(path)
        .map_err(|_| "Recovery directory unavailable")?
        .is_dir()
    {
        return Err("Recovery directory must not be a symlink".into());
    }
    Ok(())
}

fn open_regular(path: &Path) -> RecoveryResult<File> {
    if !fs::symlink_metadata(path)
        .map_err(|_| "Evidence file unavailable")?
        .is_file()
    {
        return Err("Evidence must be a regular file, not a symlink".into());
    }
    let file = File::open(path).map_err(|_| "Evidence file unavailable")?;
    // Bind the descriptor to the inspected inode (no follow-through symlink race).
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        let opened = file
            .metadata()
            .map_err(|_| "Evidence metadata unavailable")?;
        let named = fs::symlink_metadata(path).map_err(|_| "Evidence metadata unavailable")?;
        if !named.is_file() || opened.dev() != named.dev() || opened.ino() != named.ino() {
            return Err("Evidence changed during open".into());
        }
    }
    Ok(file)
}

fn bounded_file_hash(path: &Path) -> RecoveryResult<String> {
    let file = open_regular(path)?;
    if file
        .metadata()
        .map_err(|_| "Capture metadata unavailable")?
        .len()
        > MAX_SOURCE_BYTES
    {
        return Err("Original capture exceeds recovery size bound".into());
    }
    let mut digest = Sha256::new();
    let mut reader = file.take(MAX_SOURCE_BYTES + 1);
    let mut buffer = [0; 64 * 1024];
    let mut count = 0;
    loop {
        let n = reader
            .read(&mut buffer)
            .map_err(|_| "Original capture unreadable")?;
        if n == 0 {
            break;
        }
        count += n as u64;
        if count > MAX_SOURCE_BYTES {
            return Err("Original capture exceeds recovery size bound".into());
        }
        digest.update(&buffer[..n]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn message_text(payload: &Value, kind: &str) -> RecoveryResult<String> {
    let content = payload
        .get("content")
        .and_then(Value::as_array)
        .ok_or("Missing native message content")?;
    let mut text = String::new();
    for part in content {
        if part.get("type").and_then(Value::as_str) != Some(kind) {
            return Err("Unsupported native message content".into());
        }
        text.push_str(
            part.get("text")
                .and_then(Value::as_str)
                .ok_or("Missing native message text")?,
        );
    }
    Ok(text)
}

fn recover(
    process: &ExecutionProcess,
    request: &RecoveryRequest,
    home: &Path,
    capture: &Path,
) -> RecoveryResult<RecoveredFinal> {
    let prompt = binding(process, request)?;
    if bounded_file_hash(capture)? != request.original_capture_sha256 {
        return Err("Original capture changed; recovery refused".into());
    }
    let path = native_path(home, request.native_session_id)?;
    let file = open_regular(&path)?;
    if file
        .metadata()
        .map_err(|_| "Native transcript metadata unavailable")?
        .len()
        < request.source_prefix_bytes
    {
        return Err("Native transcript prefix is missing".into());
    }
    let mut reader = BufReader::new(file.take(request.source_prefix_bytes));
    let mut digest = Sha256::new();
    let mut total = 0u64;
    let mut line = Vec::new();
    let mut number = 0;
    let mut native_id = None;
    let mut started = None;
    let mut closed = None;
    let mut final_message = None;
    let mut matching_prompts = 0;
    let end = process
        .completed_at
        .ok_or("Missing original completion timestamp")?;
    loop {
        line.clear();
        let n = reader
            .by_ref()
            .take(MAX_LINE_BYTES + 1)
            .read_until(b'\n', &mut line)
            .map_err(|_| "Native transcript unreadable")?;
        if n == 0 {
            break;
        }
        if n as u64 > MAX_LINE_BYTES || line.last() != Some(&b'\n') {
            return Err("Oversized or truncated native transcript entry".into());
        }
        digest.update(&line);
        total += n as u64;
        number += 1;
        // Strictly parse EVERY entry, even outside the target turn. Never skip damage.
        let record: Value =
            serde_json::from_slice(&line).map_err(|_| "Damaged native transcript entry")?;
        let typ = record
            .get("type")
            .and_then(Value::as_str)
            .ok_or("Missing native record type")?;
        let payload = record
            .get("payload")
            .ok_or("Missing native record payload")?;
        if typ == "session_meta" {
            if native_id.is_some() {
                return Err("Duplicate native session metadata".into());
            }
            native_id = Some(
                payload
                    .get("id")
                    .and_then(Value::as_str)
                    .ok_or("Missing native session identity")?
                    .to_owned(),
            );
        }
        let at = record
            .get("timestamp")
            .and_then(Value::as_str)
            .ok_or("Missing native timestamp")?;
        let at = DateTime::parse_from_rfc3339(at)
            .map_err(|_| "Invalid native timestamp")?
            .with_timezone(&Utc);
        if at < process.started_at || at > end {
            continue;
        }
        let event = payload.get("type").and_then(Value::as_str);
        if typ == "event_msg" && matches!(event, Some("turn_aborted" | "error")) {
            return Err("Native turn contains an abort/error".into());
        }
        if typ == "event_msg" && event == Some("task_started") {
            if started.is_some() || closed.is_some() {
                return Err("Ambiguous native turn start".into());
            }
            let id = payload
                .get("turn_id")
                .and_then(Value::as_str)
                .ok_or("Missing native turn identity")?;
            if Uuid::parse_str(id).ok() != Some(request.native_turn_id) {
                return Err("Native turn identity mismatch".into());
            }
            started = Some(at);
        }
        if typ == "response_item"
            && event == Some("message")
            && payload.get("role").and_then(Value::as_str) == Some("user")
        {
            let text = message_text(payload, "input_text")?;
            // Vibe prepends instructions. The complete exact stored owner prompt
            // must be its suffix, never a summary or arbitrary substring.
            if text.ends_with(&prompt) {
                matching_prompts += 1;
            }
        }
        if typ == "response_item"
            && event == Some("message")
            && payload.get("role").and_then(Value::as_str) == Some("assistant")
            && payload.get("phase").and_then(Value::as_str) == Some("final_answer")
        {
            if started.is_none() || closed.is_some() || final_message.is_some() {
                return Err("Ambiguous native final".into());
            }
            let text = message_text(payload, "output_text")?;
            if text.is_empty()
                || text.len() > MAX_FINAL_BYTES
                || sha(text.as_bytes()) != request.reply_sha256
            {
                return Err("Native final text/hash is not the reviewed original".into());
            }
            final_message = Some((
                at,
                number,
                payload.get("id").and_then(Value::as_str).map(str::to_owned),
                text,
            ));
        }
        if typ == "event_msg" && event == Some("task_complete") {
            if closed.is_some() || started.is_none() {
                return Err("Ambiguous native completion".into());
            }
            let id = payload
                .get("turn_id")
                .and_then(Value::as_str)
                .ok_or("Missing completed native turn identity")?;
            let Some((final_at, _, _, text)) = &final_message else {
                return Err("Native completion has no preceding final".into());
            };
            if Uuid::parse_str(id).ok() != Some(request.native_turn_id)
                || at < *final_at
                || payload.get("last_agent_message").and_then(Value::as_str) != Some(text.as_str())
            {
                return Err("Native final/completion identity mismatch".into());
            }
            closed = Some(number);
        }
    }
    if total != request.source_prefix_bytes
        || format!("{:x}", digest.finalize()) != request.source_prefix_sha256
        || native_id.as_deref() != Some(request.native_session_id.to_string().as_str())
        || matching_prompts != 1
    {
        return Err("Native source integrity/session/prompt binding failed".into());
    }
    let closure_line = closed.ok_or("Native completion absent")?;
    let (final_at, final_line, native_message_id, text) =
        final_message.ok_or("Native final absent")?;
    // Detect changes to the preserved original during the recovery read too.
    if bounded_file_hash(capture)? != request.original_capture_sha256 {
        return Err("Original capture changed during recovery".into());
    }
    Ok(RecoveredFinal {
        version: 1,
        execution_id: process.id,
        evidence: request.clone(),
        final_at,
        final_line,
        closure_line,
        native_message_id,
        text,
    })
}

fn record_path(capture: &Path) -> PathBuf {
    capture.with_extension("recovered-final.json")
}

fn save(capture: &Path, record: &RecoveredFinal) -> RecoveryResult<bool> {
    let target = record_path(capture);
    if target.exists() {
        let old = load_record(&target)?;
        if old == *record {
            return Ok(false);
        }
        return Err("Conflicting recovery already exists; no overwrite permitted".into());
    }
    let parent = target.parent().ok_or("Recovery parent missing")?;
    regular_directory(parent)?;
    let temp = parent.join(format!(".recovered-{}.tmp", Uuid::new_v4()));
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(&temp)
        .map_err(|_| "Cannot create recovery staging file")?;
    let result = (|| {
        file.write_all(&serde_json::to_vec(record).map_err(|_| "Recovery serialization failed")?)
            .map_err(|_| "Recovery write failed")?;
        file.sync_all().map_err(|_| "Recovery fsync failed")?;
        match fs::hard_link(&temp, &target) {
            Ok(()) => {
                File::open(parent)
                    .and_then(|x| x.sync_all())
                    .map_err(|_| "Recovery directory fsync failed")?;
                Ok(true)
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                if load_record(&target)? == *record {
                    Ok(false)
                } else {
                    Err("Conflicting concurrent recovery; no overwrite permitted".into())
                }
            }
            Err(_) => Err("Cannot atomically publish recovery".into()),
        }
    })();
    drop(file);
    // Only our fresh staging file. Never remove a conversation/capture/evidence file.
    let _ = fs::remove_file(temp);
    result
}

fn load_record(path: &Path) -> RecoveryResult<RecoveredFinal> {
    let file = open_regular(path)?;
    if file
        .metadata()
        .map_err(|_| "Recovery metadata unavailable")?
        .len()
        > 256_000
    {
        return Err("Recovery record exceeds size bound".into());
    }
    serde_json::from_reader(file.take(256_001)).map_err(|_| "Damaged recovery record".into())
}

pub(super) async fn import(
    Extension(process): Extension<ExecutionProcess>,
    auth: Option<Extension<RelayRequestSignatureContext>>,
    State(deployment): State<DeploymentImpl>,
    Json(request): Json<RecoveryRequest>,
) -> Result<Json<utils::response::ApiResponse<Value>>, ApiError> {
    // The outer existing relay middleware verifies the signature/body/nonce.
    // Unsigned local or remote requests cannot invoke this historical writer.
    authorize(auth)?;
    let home =
        codex_home().ok_or_else(|| ApiError::Conflict("Native Codex home unavailable".into()))?;
    import_verified(process, &deployment.db().pool, home, request).await
}

async fn import_verified(
    process: ExecutionProcess,
    pool: &sqlx::SqlitePool,
    home: PathBuf,
    request: RecoveryRequest,
) -> Result<Json<utils::response::ApiResponse<Value>>, ApiError> {
    let session = Session::find_by_id(pool, process.session_id)
        .await?
        .ok_or_else(|| ApiError::Conflict("Original session unavailable".into()))?;
    if session.workspace_id != request.workspace_id
        || super::log_history::capture_page_for_process(pool, &process)
            .await?
            .is_none()
        || services::services::execution_process::capture_in_progress(process.id)
    {
        return Err(ApiError::Conflict("Only an inactive incomplete original capture in the specified workspace can be recovered".into()));
    }
    let capture = services::services::execution_process::execution_log_file_path_for_execution(
        pool, process.id,
    )
    .await
    .map_err(|_| ApiError::Conflict("Original capture lookup failed".into()))?
    .ok_or_else(|| ApiError::Conflict("Original capture unavailable".into()))?;
    let permit = permit().await?;
    let result = tokio::task::spawn_blocking(move || {
        let _permit = permit;
        let record = recover(&process, &request, &home, &capture)?;
        let created = save(&capture, &record)?;
        Ok::<_, String>(json!({"execution_id": record.execution_id, "native_turn_id": record.evidence.native_turn_id,
            "reply_sha256": record.evidence.reply_sha256, "final_at":record.final_at, "created":created,
            "original_capture_complete":false, "review_certified":false}))
    }).await.map_err(|_| ApiError::Conflict("Recovery task failed".into()))?
      .map_err(ApiError::Conflict)?;
    Ok(Json(utils::response::ApiResponse::success(result)))
}

// A recovered final is visible only through its original process's normal
// reader. Revalidate source prefix, prompt, revision and original capture on
// every read; later native append-only work cannot invalidate the pinned prefix.
pub(super) async fn read(
    process: &ExecutionProcess,
    pool: &sqlx::SqlitePool,
    before: Option<usize>,
) -> Result<Option<super::log_history::HistoryPage>, ApiError> {
    let home =
        codex_home().ok_or_else(|| ApiError::Conflict("Native Codex home unavailable".into()))?;
    read_verified(process, pool, before, home).await
}

async fn read_verified(
    process: &ExecutionProcess,
    pool: &sqlx::SqlitePool,
    before: Option<usize>,
    home: PathBuf,
) -> Result<Option<super::log_history::HistoryPage>, ApiError> {
    let capture = services::services::execution_process::execution_log_file_path_for_execution(
        pool, process.id,
    )
    .await
    .map_err(|_| ApiError::Conflict("Original capture lookup failed".into()))?;
    let Some(capture) = capture else {
        return Ok(None);
    };
    if !record_path(&capture).exists() {
        return Ok(None);
    }
    let session = Session::find_by_id(pool, process.session_id)
        .await?
        .ok_or_else(|| ApiError::Conflict("Recovered response session unavailable".into()))?;
    let process = process.clone();
    let permit = permit().await?;
    let record = tokio::task::spawn_blocking(move || {
        let _permit = permit;
        let record = load_record(&record_path(&capture))?;
        if record.version != 1
            || record.execution_id != process.id
            || record.evidence.workspace_id != session.workspace_id
        {
            return Err("Recovery record identity/version mismatch".into());
        }
        let actual = recover(&process, &record.evidence, &home, &capture)?;
        if record != actual {
            return Err("Recovery record does not match authentic native evidence".into());
        }
        Ok::<_, String>(record)
    })
    .await
    .map_err(|_| ApiError::Conflict("Recovery read failed".into()))?
    .map_err(ApiError::Conflict)?;
    Ok(Some(super::log_history::HistoryPage {
        entries: if before == Some(0) {
            vec![]
        } else {
            vec![super::log_history::HistoryEntry {
                index: 0,
                entry: json!({"type":"NORMALIZED_ENTRY","content":{"timestamp":record.final_at.to_rfc3339(),
                "entry_type":{"type":"assistant_message"},"content":record.text,
                "metadata":{"historical_recovery":{"version":1,"native_turn_id":record.evidence.native_turn_id,
                    "native_message_id":record.native_message_id,"source_line":record.final_line,
                    "reply_sha256":record.evidence.reply_sha256,"original_capture_complete":false}}}}),
            }]
        },
        next_before: None,
        capture_error: None,
        capture_pending: false,
        recovery_notice: Some(NOTICE),
    }))
}

#[cfg(test)]
mod tests;
