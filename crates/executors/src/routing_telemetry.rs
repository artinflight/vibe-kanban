//! Optional CU feed. Identity comes from persisted VK records and native RPCs.
use std::{
    fs::OpenOptions,
    io::{BufRead, BufReader, Seek, SeekFrom, Write},
    path::Path,
};

use serde_json::{Value, json};

use crate::{actions::ExecutorAction, env::ExecutionEnv, executors::BaseCodingAgent};

pub fn routing_id(action: &ExecutorAction, execution: &str) -> String {
    action
        .routing_decision
        .as_ref()
        .map(|d| d.id.clone())
        .unwrap_or_else(|| execution.into())
}

pub fn record(
    kind: &str,
    execution: &str,
    routing: &str,
    timestamp: &str,
    mut fields: Value,
) -> Value {
    fields["schema"] = json!("vk.routing.v1");
    fields["kind"] = json!(kind);
    fields["executionId"] = json!(execution);
    fields["routingId"] = json!(routing);
    fields["timestamp"] = json!(timestamp);
    use sha2::{Digest, Sha256};
    let key = json!([
        kind,
        execution,
        fields.get("nativeThreadId"),
        fields.get("nativeTurnId")
    ]);
    fields["eventId"] = json!(format!(
        "vk:{:x}",
        Sha256::digest(key.to_string().as_bytes())
    ));
    fields
}

pub fn decision(
    action: &ExecutorAction,
    execution: &str,
    session: &str,
    workspace: &str,
    task: Option<String>,
    timestamp: &str,
) -> Option<Value> {
    let config = crate::routing::config(action)?;
    if config.executor != BaseCodingAgent::Codex {
        return None;
    }
    let d = action.routing_decision.as_deref();
    let parent = d.and_then(|d| d.previous_execution_id.clone());
    let escalate = d.is_some_and(|d| d.escalated) && parent.is_some();
    let changed =
        d.is_some_and(|d| d.previous_model.is_some() && d.previous_model != d.selected_model);
    let route = routing_id(action, execution);
    Some(record(
        "decision",
        execution,
        &route,
        timestamp,
        json!({
            "workspaceId": workspace, "taskId": task, "sessionId": session,
            "mode": d.map(|d| d.mode).unwrap_or(crate::routing::RoutingMode::Manual),
            "action": if escalate { "escalate" } else if changed { "switch" } else { "initial" },
            "policyVersion": if d.is_some_and(|d| d.version >= 2) { "vk-autoswitch-v2" } else { "vk-autoswitch-v1" }, "parentExecutionId": parent,
            "transitionId": if escalate || changed { Some(format!("transition:{route}")) } else { None },
            "reasonCode": d.and_then(|d| d.reason.split(':').next()).unwrap_or("explicit_manual"),
            "selected": { "model": d.map_or(config.model_id.as_ref(), |d| d.selected_model.as_ref()),
                "reasoningEffort": d.map_or(config.reasoning_id.as_ref(), |d| d.selected_effort.as_ref()),
                "serviceTier": d.map(|d| d.service_tier.as_str()) }
        }),
    ))
}

#[derive(Debug)]
pub struct NativeBinding {
    execution: String,
    routing: String,
    effective: Value,
}
impl NativeBinding {
    pub fn new(
        env: &ExecutionEnv,
        routing: Option<&crate::routing::RoutingDecision>,
        effective: Value,
    ) -> Option<Self> {
        let execution = env.get("VK_EXECUTION_PROCESS_ID")?.clone();
        Some(Self {
            routing: routing
                .map(|d| d.id.clone())
                .unwrap_or_else(|| execution.clone()),
            execution,
            effective,
        })
    }
    pub async fn turn(&self, thread: &str, turn: &str) {
        if thread.is_empty() || turn.is_empty() {
            return;
        }
        emit(record(
            "turn_bound",
            &self.execution,
            &self.routing,
            &chrono::Utc::now().to_rfc3339(),
            json!({
                "nativeThreadId": thread, "nativeTurnId": turn,
                "effective": self.effective, "settingsSource": "runtime_confirmed"
            }),
        ))
        .await;
    }
}

/// Optional delivery failure never changes execution outcome or starts a retry.
pub async fn emit(event: Value) {
    let Ok(path) = std::env::var("VK_ROUTING_EVENTS_FILE") else {
        return;
    };
    if path.is_empty() {
        return;
    }
    let id = event["eventId"].clone();
    let result = tokio::task::spawn_blocking(move || append_once(Path::new(&path), &event)).await;
    match result {
        Ok(Ok(())) => {}
        error => {
            tracing::warn!(event_id = %id, error = ?error, "CU routing telemetry delivery failed; execution continues unchanged")
        }
    }
}

pub(crate) fn append_once(path: &Path, event: &Value) -> std::io::Result<()> {
    use std::io::{Error, ErrorKind};
    if !path.is_absolute() {
        return Err(Error::other("Routing feed path must be absolute"));
    }
    if let Ok(metadata) = std::fs::symlink_metadata(path) {
        if !metadata.is_file() {
            return Err(Error::other("Routing feed must be a regular file"));
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if metadata.permissions().mode() & 0o077 != 0 {
                return Err(Error::other("Routing feed must be private (0600)"));
            }
        }
    }
    let mut options = OpenOptions::new();
    options.create(true).read(true).write(true).truncate(false);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path)?;
    let start = std::time::Instant::now();
    // Bounded writer coordination, not an execution retry or background loop.
    loop {
        match file.try_lock() {
            Ok(()) => break,
            Err(std::fs::TryLockError::WouldBlock)
                if start.elapsed() < std::time::Duration::from_millis(250) =>
            {
                std::thread::sleep(std::time::Duration::from_millis(5))
            }
            Err(error) => return Err(Error::other(error.to_string())),
        }
    }
    let mut reader = BufReader::new(file.try_clone()?);
    let mut line = String::new();
    let mut complete = 0u64;
    while reader.read_line(&mut line)? != 0 {
        if !line.ends_with('\n') {
            file.set_len(complete)?;
            break;
        }
        complete += line.len() as u64;
        let mut prior: Value = serde_json::from_str(&line).map_err(Error::other)?;
        if prior["eventId"] == event["eventId"] {
            let mut candidate = event.clone();
            // The first append owns its immutable timestamp; replay cannot rewrite it.
            prior
                .as_object_mut()
                .ok_or_else(|| Error::other("Invalid feed record"))?
                .remove("timestamp");
            candidate
                .as_object_mut()
                .ok_or_else(|| Error::other("Invalid event"))?
                .remove("timestamp");
            return if prior == candidate {
                Ok(())
            } else {
                Err(Error::new(
                    ErrorKind::InvalidData,
                    "Conflicting immutable routing event",
                ))
            };
        }
        line.clear();
    }
    let mut bytes = serde_json::to_vec(event).map_err(Error::other)?;
    bytes.push(b'\n');
    if bytes.len() > 64 * 1024 {
        return Err(Error::other("Routing record exceeds 64 KiB"));
    }
    file.seek(SeekFrom::End(0))?;
    if let Err(error) = file.write_all(&bytes).and_then(|_| file.sync_data()) {
        let _ = file.set_len(complete);
        return Err(error);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn immutable_duplicate_and_partial_append_recovery() {
        let path = std::env::temp_dir().join(format!("vk-routing-{}.jsonl", uuid::Uuid::new_v4()));
        let event = record(
            "execution_end",
            "execution",
            "route",
            "2026-09-30T00:00:00Z",
            json!({"outcome":"failed"}),
        );
        append_once(&path, &event).unwrap();
        let mut duplicate = event.clone();
        duplicate["timestamp"] = json!("2026-09-30T00:01:00Z");
        append_once(&path, &duplicate).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap().lines().count(), 1);
        duplicate["outcome"] = json!("completed");
        assert!(append_once(&path, &duplicate).is_err());
        OpenOptions::new()
            .append(true)
            .open(&path)
            .unwrap()
            .write_all(b"{partial")
            .unwrap();
        let next = record(
            "execution_end",
            "next",
            "route2",
            "2026-09-30T00:02:00Z",
            json!({"outcome":"completed"}),
        );
        append_once(&path, &next).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap().lines().count(), 2);
        std::fs::remove_file(path).unwrap();
    }
}
