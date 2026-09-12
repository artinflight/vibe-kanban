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
                        apply_entry(&mut entries, op)?;
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

// Log entry indices are stable identities, including sparse indices after a
// remove. Treat replace as upsert, as the existing streaming client does.
fn apply_entry(entries: &mut BTreeMap<usize, Value>, op: PatchOperation) -> Result<(), ApiError> {
    let index = op
        .path()
        .strip_prefix("/entries/")
        .and_then(|s| s.parse::<usize>().ok())
        .ok_or_else(|| ApiError::BadRequest("Unsupported conversation patch path".into()))?;
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
            return Err(ApiError::BadRequest(
                "Unsupported conversation patch operation".into(),
            ));
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
