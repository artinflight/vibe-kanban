use std::{
    collections::HashMap,
    io::{IsTerminal, Write},
    sync::Arc,
};

use anyhow::{Context, Result};
use db::{
    DBService,
    models::{
        coding_agent_turn::CodingAgentTurn,
        execution_process::ExecutionProcess,
        execution_process_logs::ExecutionProcessLogs,
        subagent_job::{SubagentJob, SubagentJobStatus},
    },
};
use executors::logs::{
    ActionType, NormalizedEntryType, ToolResult, ToolStatus,
    utils::patch::extract_normalized_entry_from_patch,
};
use futures::{StreamExt, TryStreamExt, future, stream::BoxStream};
use indicatif::{ProgressBar, ProgressStyle};
use json_patch::Patch;
use serde_json::Value;
use sqlx::SqlitePool;
use tokio::{io::AsyncWriteExt, sync::RwLock, task::JoinHandle};
use utils::{
    assets::prod_asset_dir_path,
    execution_logs::{
        ExecutionLogWriter, process_log_file_path, process_log_file_path_in_root,
        read_execution_log_file, stream_execution_log_file,
    },
    log_msg::LogMsg,
    msg_store::MsgStore,
};
use uuid::Uuid;

pub async fn migrate_execution_logs_to_files() -> Result<()> {
    let pool = DBService::new_migration_pool()
        .await
        .map_err(|e| anyhow::anyhow!("Migration DB pool error: {}", e))?;

    if !ExecutionProcessLogs::has_any(&pool).await? {
        return Ok(());
    }

    let is_tty = std::io::stderr().is_terminal();
    if is_tty {
        let _ = writeln!(
            std::io::stderr(),
            "Performing one time database migration to move logs from SQLite to flat file to improve performance, data remains local, may take a few minutes, please don't exit while this process is running..."
        );
    }

    let pb = if is_tty {
        Some(new_spinner("Migrating"))
    } else {
        None
    };

    let total_processes = Arc::new(std::sync::atomic::AtomicUsize::new(0));

    let count_task = {
        let pool = pool.clone();
        let pb = pb.clone();
        let total_processes = total_processes.clone();
        tokio::spawn(async move {
            if let Ok(count) = ExecutionProcessLogs::count_distinct_processes(&pool).await {
                total_processes.store(count as usize, std::sync::atomic::Ordering::Relaxed);
                if let Some(pb) = pb {
                    pb.set_length(count as u64);
                    pb.set_style(
                        ProgressStyle::default_bar()
                            .template("{bar:36.yellow} {percent:>3}% {msg:<12.dim}")
                            .unwrap_or_else(|_| ProgressStyle::default_bar())
                            .progress_chars("■⬝"),
                    );
                }
            }
        })
    };

    let completed = Arc::new(std::sync::atomic::AtomicUsize::new(0));

    ExecutionProcessLogs::stream_distinct_processes(&pool)
        .map_err(anyhow::Error::from)
        .map(|res| {
            let pool = pool.clone();
            let pb = pb.clone();
            let completed = completed.clone();
            let total_processes = total_processes.clone();
            async move {
                let p = res?;

                let path = process_log_file_path(p.session_id, p.execution_id);
                if path.exists() {
                    if let Some(pb) = &pb {
                        pb.inc(1);
                    }
                    return Ok::<(), anyhow::Error>(());
                }

                if let Some(parent) = path.parent() {
                    tokio::fs::create_dir_all(parent).await?;
                }

                let temp_path = path.with_extension("jsonl.tmp");
                let mut file = tokio::fs::OpenOptions::new()
                    .create(true)
                    .write(true)
                    .truncate(true)
                    .open(&temp_path)
                    .await?;

                let mut logs_stream =
                    ExecutionProcessLogs::stream_log_lines_by_execution_id(&pool, &p.execution_id);
                let mut has_logs = false;
                while let Some(log_res) = logs_stream.next().await {
                    let log = log_res?;
                    has_logs = true;
                    let mut line = log;
                    if !line.ends_with('\n') {
                        line.push('\n');
                    }
                    file.write_all(line.as_bytes()).await?;
                }

                if !has_logs {
                    let _ = tokio::fs::remove_file(&temp_path).await;
                    if let Some(pb) = &pb {
                        pb.inc(1);
                    }
                    return Ok::<(), anyhow::Error>(());
                }

                file.sync_all().await?;
                tokio::fs::rename(temp_path, path).await?;

                let c = completed.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;

                if let Some(pb) = &pb {
                    pb.inc(1);
                } else if c.is_multiple_of(100) {
                    let t = total_processes.load(std::sync::atomic::Ordering::Relaxed);
                    let _ = writeln!(
                        std::io::stderr(),
                        "sqlite-migration:{}",
                        if t > 0 {
                            (c * 100 / t).to_string()
                        } else {
                            "?".to_string()
                        }
                    );
                }

                Ok::<(), anyhow::Error>(())
            }
        })
        .buffer_unordered(64)
        .try_collect::<Vec<_>>()
        .await?;

    let _ = count_task.await;

    if let Some(pb) = pb {
        pb.finish_and_clear();
    } else {
        let _ = writeln!(std::io::stderr(), "sqlite-migration:done");
    }

    let vacuum_pb = if is_tty {
        Some(new_spinner("Compacting"))
    } else {
        let _ = writeln!(std::io::stderr(), "Compacting database...");
        None
    };

    ExecutionProcessLogs::delete_all(&pool).await?;
    sqlx::query("VACUUM").execute(&pool).await?;

    if let Some(pb) = vacuum_pb {
        pb.finish_and_clear();
    }

    let _ = writeln!(std::io::stderr(), "Database migration complete.");

    pool.close().await;

    Ok(())
}

pub async fn remove_session_process_logs(session_id: Uuid) -> Result<()> {
    let dir = utils::execution_logs::process_logs_session_dir(session_id);
    match tokio::fs::remove_dir_all(&dir).await {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => {
            Err(e).with_context(|| format!("remove session process logs at {}", dir.display()))
        }
    }
}

pub async fn load_raw_log_messages(pool: &SqlitePool, execution_id: Uuid) -> Option<Vec<LogMsg>> {
    if let Some(jsonl) = read_execution_logs_for_execution(pool, execution_id)
        .await
        .inspect_err(|e| {
            tracing::warn!(
                "Failed to read execution log file for execution {}: {:#}",
                execution_id,
                e
            );
        })
        .ok()
        .flatten()
    {
        let messages = utils::execution_logs::parse_log_jsonl_lossy(execution_id, &jsonl);
        if !messages.is_empty() {
            return Some(messages);
        }
    }

    let db_log_records = match ExecutionProcessLogs::find_by_execution_id(pool, execution_id).await
    {
        Ok(records) if !records.is_empty() => records,
        Ok(_) => return None,
        Err(e) => {
            tracing::error!(
                "Failed to fetch DB logs for execution {}: {}",
                execution_id,
                e
            );
            return None;
        }
    };

    match ExecutionProcessLogs::parse_logs(&db_log_records) {
        Ok(msgs) => Some(msgs),
        Err(e) => {
            tracing::error!(
                "Failed to parse DB logs for execution {}: {}",
                execution_id,
                e
            );
            None
        }
    }
}

pub async fn append_log_message(session_id: Uuid, execution_id: Uuid, msg: &LogMsg) -> Result<()> {
    let mut log_writer = ExecutionLogWriter::new_for_execution(session_id, execution_id)
        .await
        .with_context(|| format!("create log writer for execution {}", execution_id))?;
    let json_line = serde_json::to_string(msg)
        .with_context(|| format!("serialize log message for execution {}", execution_id))?;
    let mut json_line_with_newline = json_line;
    json_line_with_newline.push('\n');
    log_writer
        .append_jsonl_line(&json_line_with_newline)
        .await
        .with_context(|| format!("append log message for execution {}", execution_id))?;
    Ok(())
}

pub fn spawn_stream_raw_logs_to_storage(
    msg_stores: Arc<RwLock<HashMap<Uuid, Arc<MsgStore>>>>,
    db: DBService,
    execution_id: Uuid,
    session_id: Uuid,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut log_writer =
            match ExecutionLogWriter::new_for_execution(session_id, execution_id).await {
                Ok(w) => w,
                Err(e) => {
                    tracing::error!(
                        "Failed to create log file writer for execution {}: {}",
                        execution_id,
                        e
                    );
                    return;
                }
            };

        let store = {
            let map = msg_stores.read().await;
            map.get(&execution_id).cloned()
        };

        if let Some(store) = store {
            let mut stream = store.history_plus_stream();

            while let Some(Ok(msg)) = stream.next().await {
                match &msg {
                    LogMsg::Stdout(stdout) => {
                        if let Err(e) = update_subagent_jobs_from_stdout(
                            &db.pool,
                            session_id,
                            execution_id,
                            stdout,
                        )
                        .await
                        {
                            tracing::warn!(
                                "Failed to update sub-agent jobs from stdout for execution {}: {}",
                                execution_id,
                                e
                            );
                        }

                        match serde_json::to_string(&msg) {
                            Ok(jsonl_line) => {
                                let mut jsonl_line_with_newline = jsonl_line;
                                jsonl_line_with_newline.push('\n');

                                if let Err(e) =
                                    log_writer.append_jsonl_line(&jsonl_line_with_newline).await
                                {
                                    tracing::error!(
                                        "Failed to append log line for execution {}: {}",
                                        execution_id,
                                        e
                                    );
                                }
                            }
                            Err(e) => {
                                tracing::error!(
                                    "Failed to serialize log message for execution {}: {}",
                                    execution_id,
                                    e
                                );
                            }
                        }
                    }
                    LogMsg::Stderr(_) => match serde_json::to_string(&msg) {
                        Ok(jsonl_line) => {
                            let mut jsonl_line_with_newline = jsonl_line;
                            jsonl_line_with_newline.push('\n');

                            if let Err(e) =
                                log_writer.append_jsonl_line(&jsonl_line_with_newline).await
                            {
                                tracing::error!(
                                    "Failed to append log line for execution {}: {}",
                                    execution_id,
                                    e
                                );
                            }
                        }
                        Err(e) => {
                            tracing::error!(
                                "Failed to serialize log message for execution {}: {}",
                                execution_id,
                                e
                            );
                        }
                    },
                    LogMsg::SessionId(agent_session_id) => {
                        if let Err(e) = CodingAgentTurn::update_agent_session_id(
                            &db.pool,
                            execution_id,
                            agent_session_id,
                        )
                        .await
                        {
                            tracing::error!(
                                "Failed to update agent_session_id {} for execution process {}: {}",
                                agent_session_id,
                                execution_id,
                                e
                            );
                        }
                    }
                    LogMsg::MessageId(agent_message_id) => {
                        if let Err(e) = CodingAgentTurn::update_agent_message_id(
                            &db.pool,
                            execution_id,
                            agent_message_id,
                        )
                        .await
                        {
                            tracing::error!(
                                "Failed to update agent_message_id {} for execution process {}: {}",
                                agent_message_id,
                                execution_id,
                                e
                            );
                        }
                    }
                    LogMsg::Finished => {
                        break;
                    }
                    LogMsg::JsonPatch(patch) => {
                        if let Err(e) = update_subagent_jobs_from_patch(
                            &db.pool,
                            session_id,
                            execution_id,
                            patch,
                        )
                        .await
                        {
                            tracing::warn!(
                                "Failed to update sub-agent jobs for execution {}: {}",
                                execution_id,
                                e
                            );
                        }
                    }
                    LogMsg::Ready => continue,
                }
            }
        }
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum RawSubagentEvent {
    Spawned { agent_id: String },
}

async fn update_subagent_jobs_from_stdout(
    pool: &SqlitePool,
    session_id: Uuid,
    execution_id: Uuid,
    stdout: &str,
) -> Result<(), sqlx::Error> {
    for event in raw_subagent_events_from_stdout(stdout) {
        match event {
            RawSubagentEvent::Spawned { agent_id } => {
                SubagentJob::update_status(
                    pool,
                    session_id,
                    execution_id,
                    &agent_id,
                    SubagentJobStatus::Running,
                )
                .await?;
            }
        }
    }

    Ok(())
}

fn raw_subagent_events_from_stdout(stdout: &str) -> Vec<RawSubagentEvent> {
    stdout
        .lines()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
        .flat_map(raw_subagent_events_from_codex_event)
        .collect()
}

fn raw_subagent_events_from_codex_event(event: Value) -> Vec<RawSubagentEvent> {
    let method = event.get("method").and_then(Value::as_str);
    let params = event.get("params").and_then(Value::as_object);

    match method {
        Some("item/completed") => raw_spawn_events_from_completed_item(params),
        _ => Vec::new(),
    }
}

fn raw_spawn_events_from_completed_item(
    params: Option<&serde_json::Map<String, Value>>,
) -> Vec<RawSubagentEvent> {
    let Some(item) = params
        .and_then(|params| params.get("item"))
        .and_then(Value::as_object)
    else {
        return Vec::new();
    };

    let is_completed_spawn = item.get("type").and_then(Value::as_str)
        == Some("collabAgentToolCall")
        && item.get("tool").and_then(Value::as_str) == Some("spawnAgent")
        && item.get("status").and_then(Value::as_str) == Some("completed");

    if !is_completed_spawn {
        return Vec::new();
    }

    item.get("receiverThreadIds")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .filter(|agent_id| !agent_id.trim().is_empty())
        .map(|agent_id| RawSubagentEvent::Spawned {
            agent_id: agent_id.to_owned(),
        })
        .collect()
}

async fn update_subagent_jobs_from_patch(
    pool: &SqlitePool,
    session_id: Uuid,
    execution_id: Uuid,
    patch: &Patch,
) -> Result<(), sqlx::Error> {
    let Some((_index, entry)) = extract_normalized_entry_from_patch(patch) else {
        return Ok(());
    };

    let NormalizedEntryType::ToolUse {
        tool_name,
        action_type,
        status,
    } = entry.entry_type
    else {
        return Ok(());
    };

    let ActionType::Tool {
        arguments, result, ..
    } = action_type
    else {
        return Ok(());
    };

    if is_spawn_agent_tool(&tool_name) {
        let result_payload = result_payload(result.as_ref());
        let agent_id = result_payload
            .as_ref()
            .and_then(|value| value.get("agent_id"))
            .and_then(Value::as_str);
        let nickname = result_payload
            .as_ref()
            .and_then(|value| value.get("nickname"))
            .and_then(Value::as_str);

        if let Some(agent_id) = agent_id {
            if matches!(status, ToolStatus::Failed) {
                SubagentJob::update_status(
                    pool,
                    session_id,
                    execution_id,
                    agent_id,
                    SubagentJobStatus::Failed,
                )
                .await?;
            } else {
                SubagentJob::upsert_spawned(pool, session_id, execution_id, agent_id, nickname)
                    .await?;
            }
        }
    } else if is_wait_agent_tool(&tool_name) {
        let targets = wait_agent_targets(arguments.as_ref());

        if matches!(status, ToolStatus::Created) {
            for agent_id in targets {
                SubagentJob::update_status(
                    pool,
                    session_id,
                    execution_id,
                    &agent_id,
                    SubagentJobStatus::Running,
                )
                .await?;
            }
            return Ok(());
        }

        let result_payload = result_payload(result.as_ref());
        let timed_out = result_payload
            .as_ref()
            .and_then(|value| value.get("timed_out"))
            .and_then(Value::as_bool)
            .unwrap_or(false);

        if let Some(status_map) = result_payload
            .as_ref()
            .and_then(|value| value.get("status"))
            .and_then(Value::as_object)
        {
            for (agent_id, agent_status) in status_map {
                let status = if agent_status == "not_found" {
                    SubagentJobStatus::NotFound
                } else if agent_status
                    .as_object()
                    .map(|object| object.contains_key("completed"))
                    .unwrap_or(false)
                {
                    SubagentJobStatus::Completed
                } else if timed_out {
                    SubagentJobStatus::Running
                } else {
                    SubagentJobStatus::Unresolved
                };
                SubagentJob::update_status(pool, session_id, execution_id, agent_id, status)
                    .await?;
            }
        } else if timed_out {
            for agent_id in targets {
                SubagentJob::update_status(
                    pool,
                    session_id,
                    execution_id,
                    &agent_id,
                    SubagentJobStatus::Running,
                )
                .await?;
            }
        }
    }

    Ok(())
}

fn is_spawn_agent_tool(tool_name: &str) -> bool {
    tool_name == "spawn_agent" || tool_name.ends_with(".spawn_agent")
}

fn is_wait_agent_tool(tool_name: &str) -> bool {
    tool_name == "wait_agent" || tool_name.ends_with(".wait_agent")
}

fn result_payload(result: Option<&ToolResult>) -> Option<Value> {
    let value = result?.value.clone();
    match value {
        Value::String(text) => serde_json::from_str(&text).ok(),
        value => Some(value),
    }
}

fn wait_agent_targets(arguments: Option<&Value>) -> Vec<String> {
    let Some(arguments) = arguments else {
        return Vec::new();
    };

    if let Some(targets) = arguments.get("targets").and_then(Value::as_array) {
        return targets
            .iter()
            .filter_map(Value::as_str)
            .filter(|target| !target.trim().is_empty())
            .map(ToOwned::to_owned)
            .collect();
    }

    arguments
        .get("target")
        .and_then(Value::as_str)
        .filter(|target| !target.trim().is_empty())
        .map(|target| vec![target.to_owned()])
        .unwrap_or_default()
}

async fn read_execution_logs_for_execution(
    pool: &SqlitePool,
    execution_id: Uuid,
) -> Result<Option<String>> {
    match execution_log_file_path_for_execution(pool, execution_id).await? {
        Some(path) => Ok(Some(read_execution_log_file(&path).await.with_context(
            || format!("read execution log file for execution {execution_id}"),
        )?)),
        None => Ok(None),
    }
}

async fn execution_log_file_path_for_execution(
    pool: &SqlitePool,
    execution_id: Uuid,
) -> Result<Option<std::path::PathBuf>> {
    let session_id = if let Some(process) = ExecutionProcess::find_by_id(pool, execution_id).await?
    {
        process.session_id
    } else {
        return Ok(None);
    };
    let path = process_log_file_path(session_id, execution_id);

    match tokio::fs::metadata(&path).await {
        Ok(_) => Ok(Some(path)),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            if cfg!(debug_assertions) {
                // Convenience for local development with a clone of a prod db. Read only access to prod logs.
                let prod_path =
                    process_log_file_path_in_root(&prod_asset_dir_path(), session_id, execution_id);
                match tokio::fs::metadata(&prod_path).await {
                    Ok(_) => return Ok(Some(prod_path)),
                    Err(err) if err.kind() == std::io::ErrorKind::NotFound => {}
                    Err(err) => {
                        return Err(err).with_context(|| {
                            format!(
                                "check execution log file exists for execution {execution_id} at {}",
                                prod_path.display()
                            )
                        });
                    }
                }
            }
            Ok(None)
        }
        Err(e) => Err(e).with_context(|| {
            format!(
                "check execution log file exists for execution {execution_id} at {}",
                path.display()
            )
        }),
    }
}

pub async fn stream_raw_log_messages(
    pool: &SqlitePool,
    execution_id: Uuid,
) -> Option<BoxStream<'static, std::io::Result<LogMsg>>> {
    if let Some(path) = execution_log_file_path_for_execution(pool, execution_id)
        .await
        .inspect_err(|e| {
            tracing::warn!(
                "Failed to resolve execution log file for execution {}: {:#}",
                execution_id,
                e
            );
        })
        .ok()
        .flatten()
    {
        match stream_execution_log_file(&path).await {
            Ok(lines) => {
                let stream = lines
                    .scan(0usize, move |bad_lines, line_res| {
                        future::ready(match line_res {
                            Ok(line) if line.trim().is_empty() => Some(None),
                            Ok(line) => match serde_json::from_str::<LogMsg>(&line) {
                                Ok(msg) => Some(Some(Ok(msg))),
                                Err(e) => {
                                    *bad_lines += 1;
                                    if *bad_lines <= 3 {
                                        tracing::warn!(
                                            "Skipping unparsable streamed log line for execution {}: {}",
                                            execution_id,
                                            e
                                        );
                                    }
                                    Some(None)
                                }
                            },
                            Err(err) => Some(Some(Err(err))),
                        })
                    })
                    .filter_map(future::ready)
                    .boxed();

                return Some(stream);
            }
            Err(e) => {
                tracing::warn!(
                    "Failed to open execution log file stream for execution {}: {}",
                    execution_id,
                    e
                );
            }
        }
    }

    let db_log_records = match ExecutionProcessLogs::find_by_execution_id(pool, execution_id).await
    {
        Ok(records) if !records.is_empty() => records,
        Ok(_) => return None,
        Err(e) => {
            tracing::error!(
                "Failed to fetch DB logs for execution {}: {}",
                execution_id,
                e
            );
            return None;
        }
    };

    match ExecutionProcessLogs::parse_logs(&db_log_records) {
        Ok(msgs) => Some(futures::stream::iter(msgs.into_iter().map(Ok)).boxed()),
        Err(e) => {
            tracing::error!(
                "Failed to parse DB logs for execution {}: {}",
                execution_id,
                e
            );
            None
        }
    }
}

fn new_spinner(message: &'static str) -> ProgressBar {
    let pb = ProgressBar::new_spinner();
    pb.set_style(
        ProgressStyle::default_spinner()
            .template("{spinner:.yellow} {msg:<12.dim}")
            .unwrap_or_else(|_| ProgressStyle::default_spinner())
            .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
    );
    pb.set_message(message);
    pb.enable_steady_tick(std::time::Duration::from_millis(100));
    pb
}

#[cfg(test)]
mod tests {
    use super::{RawSubagentEvent, raw_subagent_events_from_stdout};

    #[test]
    fn raw_codex_spawn_agent_events_preserve_child_thread_ids() {
        let stdout = r#"{"method":"item/completed","params":{"item":{"type":"collabAgentToolCall","id":"call_123","tool":"spawnAgent","status":"completed","senderThreadId":"parent-thread","receiverThreadIds":["019e0d97-27ff-7c43-b252-28979c51d3e9"],"prompt":"work"}}}"#;

        assert_eq!(
            raw_subagent_events_from_stdout(stdout),
            vec![RawSubagentEvent::Spawned {
                agent_id: "019e0d97-27ff-7c43-b252-28979c51d3e9".to_string(),
            }]
        );
    }

    #[test]
    fn raw_codex_spawn_agent_parser_ignores_parent_status_events() {
        let stdout = r#"{"method":"thread/status/changed","params":{"threadId":"parent-thread","status":{"type":"active","activeFlags":[]}}}
{"method":"item/completed","params":{"item":{"type":"collabAgentToolCall","id":"call_123","tool":"spawnAgent","status":"inProgress","senderThreadId":"parent-thread","receiverThreadIds":[]}}}"#;

        assert!(raw_subagent_events_from_stdout(stdout).is_empty());
    }
}
