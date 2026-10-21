//! Opt-in ACP lifecycle for native resume and strictly supervised execution.
//! Existing Gemini/Qwen harness behavior is intentionally unchanged.
use std::{
    cell::RefCell,
    path::{Path, PathBuf},
    process::Stdio,
    rc::Rc,
    sync::Arc,
    time::Duration,
};

use agent_client_protocol::{self as proto, Agent as _};
use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use serde::{Deserialize, Serialize};
use tokio::{
    io::AsyncWriteExt,
    process::Command,
    sync::{mpsc, oneshot},
};
use tokio_util::{
    compat::{TokioAsyncReadCompatExt, TokioAsyncWriteCompatExt},
    sync::CancellationToken,
};
use workspace_utils::command_ext::GroupSpawnNoWindowExt;

use super::{AcpClient, AcpEvent};
use crate::{
    approvals::ExecutorApprovalService,
    command::CommandParts,
    env::ExecutionEnv,
    executors::{ExecutorError, ExecutorExitResult, SpawnedChild},
};

#[derive(Serialize, Deserialize)]
struct ResumeIdentity {
    executable: PathBuf,
    cwd: PathBuf,
    session: String,
}

fn encode(namespace: &str, identity: &ResumeIdentity) -> Result<String, ExecutorError> {
    Ok(format!(
        "{namespace}:v1:{}",
        URL_SAFE_NO_PAD.encode(serde_json::to_vec(identity)?)
    ))
}
fn decode(
    namespace: &str,
    id: &str,
    executable: &Path,
    cwd: &Path,
) -> Result<ResumeIdentity, ExecutorError> {
    let invalid = || {
        ExecutorError::FollowUpNotSupported(
            "ACP resume identity does not match this agent, executable or worktree".into(),
        )
    };
    let bytes = URL_SAFE_NO_PAD
        .decode(
            id.strip_prefix(&format!("{namespace}:v1:"))
                .ok_or_else(invalid)?,
        )
        .map_err(|_| invalid())?;
    let identity: ResumeIdentity = serde_json::from_slice(&bytes).map_err(|_| invalid())?;
    if identity.executable != executable || identity.cwd != cwd || identity.session.is_empty() {
        return Err(invalid());
    }
    Ok(identity)
}

#[allow(clippy::too_many_arguments)]
pub(super) async fn spawn(
    namespace: String,
    model: Option<String>,
    cwd: &Path,
    prompt: String,
    existing: Option<&str>,
    parts: CommandParts,
    env: &ExecutionEnv,
    approvals: Option<Arc<dyn ExecutorApprovalService>>,
) -> Result<SpawnedChild, ExecutorError> {
    let approvals = approvals
        .filter(|a| a.supports_interactive_approvals())
        .ok_or_else(|| {
            ExecutorError::AuthRequired("ACP requires interactive supervised approvals".into())
        })?;
    let (executable, args) = parts.into_resolved().await?;
    let executable = executable.canonicalize()?;
    let cwd = cwd.canonicalize()?;
    let resume = existing
        .map(|id| decode(&namespace, id, &executable, &cwd))
        .transpose()?;
    let mut command = Command::new(&executable);
    command
        .args(args)
        .current_dir(&cwd)
        .kill_on_drop(true)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    env.apply_to_command(&mut command);
    let mut child = command.group_spawn_no_window()?;
    let stdin = child.inner().stdin.take().expect("piped stdin");
    let stdout = child.inner().stdout.take().expect("piped stdout");
    let mut writer = crate::stdout_dup::create_stdout_pipe_writer(&mut child)?;
    let (events, mut event_rx) = mpsc::unbounded_channel::<AcpEvent>();
    // ACP stdout uses typed events; protocol errors omit arbitrary error payloads.
    // Runtime stderr still follows the existing log path and needs activation review.
    tokio::spawn(async move {
        while let Some(event) = event_rx.recv().await {
            let _ = writer.write_all(format!("{event}\n").as_bytes()).await;
        }
    });
    let (exit_tx, exit_rx) = oneshot::channel();
    let cancel = CancellationToken::new();
    let task_cancel = cancel.clone();
    tokio::task::spawn_blocking(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build();
        let Ok(rt) = rt else {
            let _ = exit_tx.send(ExecutorExitResult::Failure);
            return;
        };
        rt.block_on(tokio::task::LocalSet::new().run_until(async move {
            let client = AcpClient::new(events.clone(), Some(approvals), task_cancel.clone());
            let (conn, io) = proto::ClientSideConnection::new(client, stdin.compat_write(), stdout.compat(), |f| { tokio::task::spawn_local(f); });
            let conn = Rc::new(conn);
            let mut io_task = tokio::task::spawn_local(io);
            let active_session = RefCell::new(None::<String>);
            let execute = async {
                let setup = async {
                    let init = conn.initialize(proto::InitializeRequest::new(proto::ProtocolVersion::V1)).await
                        .map_err(|e| format!("ACP initialize failed (code {})", e.code))?;
                    if init.protocol_version != proto::ProtocolVersion::V1 { return Err("Unsupported ACP protocol version".into()); }
                    // Never call authenticate. AUTH_REQUIRED from new/load is terminal.
                    let (session, models) = if let Some(identity) = resume {
                        if !init.agent_capabilities.load_session { return Err("ACP native resume is unsupported; no history replay was sent".into()); }
                        let loaded = conn.load_session(proto::LoadSessionRequest::new(identity.session.clone(), cwd.clone())).await
                            .map_err(|e| format!("ACP resume failed (code {}); check supported account access outside VK", e.code))?;
                        (identity.session, loaded.models)
                    } else {
                        let created = conn.new_session(proto::NewSessionRequest::new(cwd.clone())).await
                            .map_err(|e| format!("ACP session creation failed (code {}); check supported account access outside VK", e.code))?;
                        (created.session_id.0.to_string(), created.models)
                    };
                    if session.is_empty() { return Err("ACP returned an empty session identity".into()); }
                    *active_session.borrow_mut() = Some(session.clone());
                    if let Some(model) = model {
                        if !models.as_ref().is_some_and(|m| m.available_models.iter().any(|item| item.model_id.0.as_ref() == model)) {
                            return Err("Requested model was not advertised by ACP; no fallback was selected".into());
                        }
                        conn.set_session_model(proto::SetSessionModelRequest::new(session.clone(), model)).await
                            .map_err(|e| format!("ACP model selection failed (code {}); no fallback was selected", e.code))?;
                    }
                    let display_id = encode(&namespace, &ResumeIdentity { executable, cwd, session: session.clone() })
                        .map_err(|_| "ACP resume identity could not be encoded".to_string())?;
                    let _ = events.send(AcpEvent::SessionStart(display_id));
                    Ok::<_, String>(session)
                };
                let session = tokio::time::timeout(Duration::from_secs(30), setup).await
                    .map_err(|_| "ACP initialization/session setup timed out".to_string())??;
                if task_cancel.is_cancelled() { return Err("ACP execution cancelled".into()); }
                let _ = events.send(AcpEvent::User(prompt.clone()));
                let response = conn.prompt(proto::PromptRequest::new(session, vec![proto::ContentBlock::Text(proto::TextContent::new(prompt))])).await
                    .map_err(|e| format!("ACP prompt failed (code {})", e.code))?;
                if response.stop_reason != proto::StopReason::EndTurn {
                    return Err(format!("ACP did not complete the turn: {:?}", response.stop_reason));
                }
                Ok::<_, String>(())
            };
            tokio::pin!(execute);
            let result = tokio::select! {
                biased;
                _ = task_cancel.cancelled() => {
                    let sid = active_session.borrow().clone();
                    if let Some(sid) = sid {
                        // cancel() queues a notification. Keep driving I/O and the
                        // original request until its response or the grace deadline.
                        let _ = conn.cancel(proto::CancelNotification::new(sid)).await;
                        let _ = tokio::time::timeout(Duration::from_secs(2), &mut execute).await;
                    }
                    Err("ACP execution cancelled".into())
                },
                result = &mut execute => result,
                _ = &mut io_task => Err("ACP connection closed or returned malformed data".into()),
            };
            // The container owns killing/reaping the group after the terminal signal.
            let outcome = match result {
                Ok(()) => {
                    let _ = events.send(AcpEvent::Done("\"end_turn\"".into()));
                    ExecutorExitResult::Success
                },
                Err(message) => { let _ = events.send(AcpEvent::Error(message)); ExecutorExitResult::Failure }
            };
            io_task.abort();
            let _ = exit_tx.send(outcome);
        }));
    });
    Ok(SpawnedChild {
        child,
        transient_unit_name: None,
        exit_signal: Some(exit_rx),
        cancel: Some(cancel),
    })
}

#[cfg(test)]
mod tests;
