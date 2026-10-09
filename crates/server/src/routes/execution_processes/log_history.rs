//! Finite pages of completed logs. Replay is reduced on the server rather than
//! making the browser render every intermediate version of a long turn.
use std::{
    collections::{BTreeMap, VecDeque},
    sync::{Arc, Mutex, OnceLock},
    time::{Duration, Instant},
};

use axum::{
    Extension, Json,
    extract::{Query, State},
};
use db::models::execution_process::{ExecutionProcess, ExecutionProcessStatus};
use deployment::Deployment;
use futures_util::StreamExt;
use json_patch::PatchOperation;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use services::services::container::ContainerService;
use utils::{log_msg::LogMsg, response::ApiResponse};
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

#[derive(Deserialize)]
pub(super) struct HistoryQuery {
    before: Option<usize>,
    limit: Option<usize>,
}

#[derive(Serialize)]
pub(super) struct HistoryEntry {
    index: usize,
    entry: Value,
}

#[derive(Serialize)]
pub(super) struct HistoryPage {
    entries: Vec<HistoryEntry>,
    next_before: Option<usize>,
    capture_error: Option<&'static str>,
}

type Entries = BTreeMap<usize, Value>;

// Completed logs are immutable for a given process revision. Bound both retained
// serialized payload and turn count; do not accumulate all viewed workspaces.
const CACHE_BYTES: usize = 32 * 1024 * 1024;
const CACHE_TURNS: usize = 4;
const CACHE_TTL: Duration = Duration::from_secs(300);
#[derive(Default)]
struct HistoryCache {
    turns: VecDeque<CachedTurn>,
}
struct CachedTurn {
    key: (Uuid, String),
    entries: Arc<Entries>,
    bytes: usize,
    created: Instant,
}
impl HistoryCache {
    fn get(&mut self, key: &(Uuid, String)) -> Option<Arc<Entries>> {
        self.turns.retain(|turn| turn.created.elapsed() < CACHE_TTL);
        let index = self.turns.iter().position(|turn| &turn.key == key)?;
        let turn = self.turns.remove(index)?;
        let entries = turn.entries.clone();
        self.turns.push_back(turn);
        Some(entries)
    }
    fn insert(&mut self, key: (Uuid, String), entries: Arc<Entries>, bytes: usize) {
        self.turns
            .retain(|turn| turn.key.0 != key.0 && turn.created.elapsed() < CACHE_TTL);
        if bytes > CACHE_BYTES {
            return;
        }
        while self.turns.len() >= CACHE_TURNS
            || self.turns.iter().map(|turn| turn.bytes).sum::<usize>() + bytes > CACHE_BYTES
        {
            self.turns.pop_front();
        }
        self.turns.push_back(CachedTurn {
            key,
            entries,
            bytes,
            created: Instant::now(),
        });
    }
}
fn history_cache() -> &'static Mutex<HistoryCache> {
    static CACHE: OnceLock<Mutex<HistoryCache>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HistoryCache::default()))
}

pub(super) async fn get_log_history(
    Extension(process): Extension<ExecutionProcess>,
    State(deployment): State<DeploymentImpl>,
    Query(query): Query<HistoryQuery>,
) -> Result<Json<ApiResponse<HistoryPage>>, ApiError> {
    if process.status == ExecutionProcessStatus::Running {
        return Err(ApiError::Conflict(
            "Running logs must use the live stream".into(),
        ));
    }
    // Fail visibly for a durable Codex prefix, including historical captures
    // stopped on broadcast lag. Completion/exit zero is not capture completeness.
    if process.status == ExecutionProcessStatus::Completed
        && process
            .executor_action()
            .map_err(|_| ApiError::BadRequest("Execution configuration unavailable".into()))?
            .base_executor()
            == Some(executors::executors::BaseCodingAgent::Codex)
        && let Some(reason) = capture_error_for_process(&deployment.db().pool, &process).await?
    {
        return Ok(Json(ApiResponse::success(HistoryPage {
            entries: vec![],
            next_before: None,
            capture_error: Some(reason),
        })));
    }
    let limit = query.limit.unwrap_or(40).clamp(1, 200);
    let key = (process.id, process.updated_at.to_rfc3339());
    // A resident live store may still be draining its last patches after the
    // status changes. Only cache a finite replay reconstructed from storage.
    let cacheable = deployment
        .container()
        .get_msg_store_by_id(&process.id)
        .await
        .is_none();
    let cached = if cacheable {
        history_cache().lock().unwrap().get(&key)
    } else {
        None
    };
    if let Some(entries) = cached {
        return Ok(Json(ApiResponse::success(page(
            &entries,
            query.before,
            limit,
        ))));
    }
    let script =
        process.run_reason != db::models::execution_process::ExecutionProcessRunReason::CodingAgent;
    let stream = if script {
        deployment.container().stream_raw_logs(&process.id).await
    } else {
        deployment
            .container()
            .stream_normalized_logs(&process.id)
            .await
    };
    let mut entries = BTreeMap::new();
    let mut raw_index = 0;
    if let Some(mut stream) = stream {
        while let Some(msg) = stream.next().await {
            match msg? {
                LogMsg::JsonPatch(patch) => {
                    for op in patch.0 {
                        apply_entry(&mut entries, op)
                            .map_err(|message| ApiError::BadRequest(message.into()))?;
                    }
                }
                LogMsg::Stdout(content) if script => {
                    entries.insert(raw_index, json!({"type": "STDOUT", "content": content}));
                    raw_index += 1;
                }
                LogMsg::Stderr(content) if script => {
                    entries.insert(raw_index, json!({"type": "STDERR", "content": content}));
                    raw_index += 1;
                }
                LogMsg::Finished => break,
                _ => {}
            }
        }
    }
    let entries = Arc::new(entries);
    if cacheable {
        let bytes = entries.values().map(|value| value.to_string().len()).sum();
        history_cache()
            .lock()
            .unwrap()
            .insert(key, entries.clone(), bytes);
    }
    Ok(Json(ApiResponse::success(page(
        &entries,
        query.before,
        limit,
    ))))
}

pub(crate) async fn capture_error_for_process(
    pool: &sqlx::SqlitePool,
    process: &ExecutionProcess,
) -> Result<Option<&'static str>, ApiError> {
    let path = services::services::execution_process::execution_log_file_path_for_execution(
        pool, process.id,
    )
    .await
    .map_err(|_| ApiError::BadRequest("Execution capture location unavailable".into()))?;
    let available = if let Some(path) = path {
        utils::execution_logs::validate_native_capture(
            &path,
            services::services::report_review::MAX_RAW_BYTES,
        )
        .await
        .is_ok()
    } else {
        false
    };
    if !available {
        return Ok(Some(
            "Incomplete, damaged, or unverified execution capture; reply unavailable. Native transcript evidence must be preserved; no historical fallback or review acknowledgement.",
        ));
    }
    Ok(None)
}

// Log entry indices are stable identities, including sparse indices after a
// remove. Treat replace as upsert, as the existing streaming client does.
fn apply_entry(
    entries: &mut BTreeMap<usize, Value>,
    op: PatchOperation,
) -> Result<(), &'static str> {
    let index = op
        .path()
        .strip_prefix("/entries/")
        .and_then(|s| s.parse::<usize>().ok())
        .ok_or("Unsupported conversation patch path")?;
    match op {
        PatchOperation::Add(op) => {
            entries.insert(index, op.value);
        }
        PatchOperation::Replace(op) => {
            entries.insert(index, op.value);
        }
        PatchOperation::Remove(_) => {
            entries.remove(&index);
        }
        _ => {
            return Err("Unsupported conversation patch operation");
        }
    }
    Ok(())
}

fn page(entries: &Entries, before: Option<usize>, limit: usize) -> HistoryPage {
    let mut newest = entries
        .iter()
        .rev()
        .filter(|(index, _)| before.is_none_or(|before| **index < before))
        .take(limit + 1)
        .collect::<Vec<_>>();
    let has_more = newest.len() > limit;
    newest.truncate(limit);
    newest.reverse();
    let next_before = if has_more {
        newest.first().map(|(index, _)| **index)
    } else {
        None
    };
    HistoryPage {
        entries: newest
            .into_iter()
            .map(|(&index, entry)| HistoryEntry {
                index,
                entry: entry.clone(),
            })
            .collect(),
        next_before,
        capture_error: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn long_turn_pages_from_tail_without_duplicates_or_skipping_sparse_indices() {
        let entries = (0..10_000)
            .filter(|i| i % 7 != 0)
            .map(|i| (i, json!(i)))
            .collect::<BTreeMap<_, _>>();
        let expected = entries.keys().copied().collect::<Vec<_>>();
        let mut before = None;
        let mut loaded = Vec::new();
        loop {
            let result = page(&entries, before, 40);
            assert!(result.entries.len() <= 40);
            let mut indices = result.entries.iter().map(|e| e.index).collect::<Vec<_>>();
            indices.extend(loaded);
            loaded = indices;
            before = result.next_before;
            if before.is_none() {
                break;
            }
        }
        assert_eq!(loaded, expected);
    }

    #[test]
    fn cache_evicts_by_size_count_and_revision() {
        let mut cache = HistoryCache::default();
        let entries = Arc::new(BTreeMap::new());
        let keys = (0..6)
            .map(|_| (Uuid::new_v4(), "revision".to_string()))
            .collect::<Vec<_>>();
        for key in &keys {
            cache.insert(key.clone(), entries.clone(), 1);
        }
        assert_eq!(cache.turns.len(), CACHE_TURNS);
        assert!(cache.get(&keys[0]).is_none());
        assert!(cache.get(&keys[5]).is_some());
        cache.insert(keys[0].clone(), entries.clone(), CACHE_BYTES);
        assert_eq!(cache.turns.len(), 1);
        cache.insert(keys[1].clone(), entries.clone(), CACHE_BYTES + 1);
        assert!(cache.get(&keys[1]).is_none());
        let revision = (keys[0].0, "new revision".to_string());
        cache.insert(revision.clone(), entries, 1);
        assert!(cache.get(&keys[0]).is_none());
        assert!(cache.get(&revision).is_some());
        cache.turns[0].created = Instant::now() - CACHE_TTL;
        assert!(cache.get(&revision).is_none());
    }

    #[test]
    fn replay_returns_final_replacements_and_handles_removals() {
        let mut entries = BTreeMap::new();
        let patch: json_patch::Patch = serde_json::from_value(json!([
            {"op":"add", "path":"/entries/0", "value":"old"},
            {"op":"replace", "path":"/entries/0", "value":"final"},
            {"op":"replace", "path":"/entries/2", "value":"upsert"},
            {"op":"remove", "path":"/entries/0"}
        ]))
        .unwrap();
        for op in patch.0 {
            apply_entry(&mut entries, op).unwrap();
        }
        let result = page(&entries, None, 40);
        assert_eq!(result.entries.len(), 1);
        assert_eq!(result.entries[0].index, 2);
        assert_eq!(result.entries[0].entry, json!("upsert"));
        assert_eq!(result.next_before, None);
        assert!(page(&BTreeMap::new(), None, 40).entries.is_empty());
    }
}

// Append to execution_processes/log_history.rs; uses its existing replay reducer.
pub(crate) async fn final_reply_fingerprint(
    deployment: &DeploymentImpl,
    process: &ExecutionProcess,
) -> Result<(usize, String), ApiError> {
    if process.status != ExecutionProcessStatus::Completed
        || deployment
            .container()
            .get_msg_store_by_id(&process.id)
            .await
            .is_some()
    {
        return Err(ApiError::Conflict(
            "Report logs are still resident/draining".into(),
        ));
    }
    let replay = async {
        let (workspace, _) = process
            .parent_workspace_and_session(&deployment.db().pool)
            .await?
            .ok_or_else(|| ApiError::Conflict("Workspace missing".into()))?;
        let dir = deployment.container().workspace_to_current_dir(&workspace);
        let messages = services::services::report_review::replay_review_log(
            &deployment.db().pool,
            process,
            &dir,
        )
        .await
        .map_err(|e| ApiError::Conflict(format!("Strict durable replay rejected: {e}")))?;
        fingerprint_review_messages(messages).map_err(|e| *e)
    };
    tokio::time::timeout(Duration::from_secs(10), replay)
        .await
        .map_err(|_| ApiError::Conflict("Durable replay timed out".into()))?
}

/// Same bounded reducer used by production and isolated HTTP verification.
pub fn fingerprint_review_messages(
    messages: Vec<LogMsg>,
) -> Result<(usize, String), Box<ApiError>> {
    use sha2::{Digest, Sha256};
    let mut entries = BTreeMap::new();
    let mut bytes = 0usize;
    let mut patches = 0usize;
    let mut finished = false;
    for msg in messages {
        if finished {
            return Err(ApiError::Conflict("Data after replay completion".into()).into());
        }
        match msg {
            LogMsg::JsonPatch(patch) => {
                bytes += serde_json::to_vec(&patch)
                    .map_err(|_| ApiError::BadRequest("Replay encoding".into()))?
                    .len();
                patches += patch.0.len();
                if bytes > 8 * 1024 * 1024 || patches > 100_000 {
                    return Err(
                        ApiError::Conflict("Durable replay exceeds safe bound".into()).into(),
                    );
                }
                for op in patch.0 {
                    apply_entry(&mut entries, op).map_err(|m| ApiError::BadRequest(m.into()))?;
                }
            }
            LogMsg::Finished => finished = true,
            _ => {
                return Err(ApiError::Conflict("Unexpected review replay message".into()).into());
            }
        }
    }
    if !finished {
        return Err(ApiError::Conflict("Replay did not finish".into()).into());
    }
    for (index, entry) in entries.iter().rev() {
        if entry["type"] == "NORMALIZED_ENTRY"
            && entry["content"]["entry_type"]["type"] == "assistant_message"
        {
            let text = entry["content"]["content"]
                .as_str()
                .ok_or_else(|| ApiError::Conflict("Ambiguous reply text".into()))?;
            return Ok((*index, format!("{:x}", Sha256::digest(text.as_bytes()))));
        }
    }
    Err(ApiError::Conflict("No final assistant reply".into()).into())
}
