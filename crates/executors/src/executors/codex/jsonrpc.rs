//! Minimal JSON-RPC helper tailored for the Codex executor.
//!
//! We keep this bespoke layer because the codex-app-server client must handle server-initiated
//! requests as well as client-initiated requests. When a bidirectional client that
//! supports this pattern is available, this module should be straightforward to
//! replace.

use std::{
    collections::HashMap,
    fmt::Debug,
    io,
    sync::{
        Arc,
        atomic::{AtomicI64, Ordering},
    },
};

use async_trait::async_trait;
use codex_app_server_protocol::{
    CodexErrorInfo, JSONRPCError, JSONRPCMessage, JSONRPCNotification, JSONRPCRequest,
    JSONRPCResponse, RequestId, ServerNotification,
};
use serde::{Serialize, de::DeserializeOwned};
use serde_json::Value;
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    process::{ChildStdin, ChildStdout},
    sync::{Mutex, oneshot},
};
use tokio_util::sync::CancellationToken;

use crate::executors::{ExecutorError, ExecutorExitResult};

#[derive(Debug)]
pub enum PendingResponse {
    Result(Value),
    Error(JSONRPCError),
    Shutdown,
}

#[derive(Clone)]
pub struct ExitSignalSender {
    inner: Arc<Mutex<Option<oneshot::Sender<ExecutorExitResult>>>>,
}

impl ExitSignalSender {
    pub fn new(sender: oneshot::Sender<ExecutorExitResult>) -> Self {
        Self {
            inner: Arc::new(Mutex::new(Some(sender))),
        }
    }

    #[cfg(test)]
    pub(crate) async fn hold_for_stop_test(
        &self,
    ) -> tokio::sync::OwnedMutexGuard<Option<oneshot::Sender<ExecutorExitResult>>> {
        self.inner.clone().lock_owned().await
    }

    pub async fn send_exit_signal(&self, result: ExecutorExitResult) {
        if let Some(sender) = self.inner.lock().await.take() {
            let _ = sender.send(result);
        }
    }
}

#[derive(Clone)]
pub struct JsonRpcPeer {
    stdin: Arc<Mutex<ChildStdin>>,
    pending: Arc<Mutex<HashMap<RequestId, oneshot::Sender<PendingResponse>>>>,
    id_counter: Arc<AtomicI64>,
    disconnected: CancellationToken,
}

impl JsonRpcPeer {
    pub fn spawn(
        stdin: ChildStdin,
        stdout: ChildStdout,
        callbacks: Arc<dyn JsonRpcCallbacks>,
        exit_tx: ExitSignalSender,
        cancel: CancellationToken,
    ) -> Self {
        let peer = Self {
            stdin: Arc::new(Mutex::new(stdin)),
            pending: Arc::new(Mutex::new(HashMap::new())),
            id_counter: Arc::new(AtomicI64::new(1)),
            disconnected: CancellationToken::new(),
        };

        let reader_peer = peer.clone();
        let callbacks = callbacks.clone();

        tokio::spawn(async move {
            let mut reader = BufReader::new(stdout);
            let mut buffer = String::new();
            let mut completed_normally = false;

            loop {
                buffer.clear();
                tokio::select! {
                    _ = cancel.cancelled() => {
                        tracing::debug!("Codex executor cancelled");
                        break;
                    }
                    read_result = reader.read_line(&mut buffer) => {
                        match read_result {
                            Ok(0) => break,
                            Ok(_) => {
                                let line = buffer.trim_end_matches(['\n', '\r']);
                                if line.is_empty() {
                                    continue;
                                }

                                match serde_json::from_str::<JSONRPCMessage>(line) {
                                    Ok(JSONRPCMessage::Response(response)) => {
                                        let request_id = response.id.clone();
                                        let result = response.result.clone();
                                        if callbacks
                                            .on_response(&reader_peer, line, &response)
                                            .await
                                            .is_err()
                                        {
                                            break;
                                        }
                                        reader_peer
                                            .resolve(request_id, PendingResponse::Result(result))
                                            .await;
                                    }
                                    Ok(JSONRPCMessage::Error(error)) => {
                                        let request_id = error.id.clone();
                                        if callbacks
                                            .on_error(&reader_peer, line, &error)
                                            .await
                                            .is_err()
                                        {
                                            break;
                                        }
                                        reader_peer
                                            .resolve(request_id, PendingResponse::Error(error))
                                            .await;
                                    }
                                    Ok(JSONRPCMessage::Request(request)) => {
                                        if let Err(error) = callbacks
                                            .on_request(&reader_peer, line, request)
                                            .await
                                        {
                                            tracing::error!("Codex request callback failed: {error}");
                                            exit_tx.send_exit_signal(ExecutorExitResult::Failure).await;
                                            break;
                                        }
                                    }
                                    Ok(JSONRPCMessage::Notification(notification)) => {
                                        match callbacks
                                            .on_notification(&reader_peer, line, notification)
                                            .await
                                        {
                                            // finished
                                            Ok(true) => { completed_normally = true; break; },
                                            Ok(false) => {}
                                            Err(error) => {
                                                tracing::error!("Codex notification callback failed: {error}");
                                                exit_tx.send_exit_signal(ExecutorExitResult::Failure).await;
                                                break;
                                            }
                                        }
                                    }
                                    Err(_) => {
                                        if callbacks.on_non_json(line).await.is_err() {
                                            break;
                                        }
                                    }
                                }
                            }
                            Err(err) => {
                                tracing::warn!("Error reading Codex output: {err}");
                                break;
                            }
                        }
                    }
                }
            }

            exit_tx
                .send_exit_signal(if completed_normally {
                    ExecutorExitResult::Success
                } else {
                    ExecutorExitResult::Failure
                })
                .await;
            let _ = reader_peer.shutdown().await;
        });

        peer
    }

    pub fn next_request_id(&self) -> RequestId {
        RequestId::Integer(self.id_counter.fetch_add(1, Ordering::Relaxed))
    }

    pub async fn register(&self, request_id: RequestId) -> PendingReceiver {
        let (sender, receiver) = oneshot::channel();
        self.pending.lock().await.insert(request_id, sender);
        receiver
    }

    pub async fn resolve(&self, request_id: RequestId, response: PendingResponse) {
        if let Some(sender) = self.pending.lock().await.remove(&request_id) {
            let _ = sender.send(response);
        }
    }

    pub async fn shutdown(&self) -> Result<(), ExecutorError> {
        self.disconnected.cancel();
        let mut pending = self.pending.lock().await;
        for (_, sender) in pending.drain() {
            let _ = sender.send(PendingResponse::Shutdown);
        }
        Ok(())
    }

    pub fn disconnected(&self) -> CancellationToken {
        self.disconnected.clone()
    }

    pub async fn send<T>(&self, message: &T) -> Result<(), ExecutorError>
    where
        T: Serialize + Sync,
    {
        let raw = serde_json::to_string(message)
            .map_err(|err| ExecutorError::Io(io::Error::other(err.to_string())))?;
        self.send_raw(&raw).await
    }

    pub async fn request<R, T>(
        &self,
        request_id: RequestId,
        message: &T,
        label: &str,
        cancel: CancellationToken,
    ) -> Result<R, ExecutorError>
    where
        R: DeserializeOwned + Debug,
        T: Serialize + Sync,
    {
        let receiver = self.register(request_id).await;
        self.send(message).await?;
        await_response(receiver, label, cancel).await
    }

    /// Bound both pipe delivery and receipt waiting. Removing the pending sender
    /// makes late replies inert; never replay or interrupt work on deadline.
    pub async fn request_with_deadline<R, T>(
        &self,
        request_id: RequestId,
        message: &T,
        label: &str,
        cancel: CancellationToken,
        deadline: std::time::Duration,
    ) -> Result<R, ExecutorError>
    where
        R: DeserializeOwned + Debug,
        T: Serialize + Sync,
    {
        let result = tokio::time::timeout(
            deadline,
            self.request(request_id.clone(), message, label, cancel),
        )
        .await;
        self.pending.lock().await.remove(&request_id);
        result.map_err(|_| {
            ExecutorError::Io(io::Error::new(
                io::ErrorKind::TimedOut,
                format!("{label} native receipt timed out; outcome unknown"),
            ))
        })?
    }

    async fn send_raw(&self, payload: &str) -> Result<(), ExecutorError> {
        let mut guard = self.stdin.lock().await;
        guard
            .write_all(payload.as_bytes())
            .await
            .map_err(ExecutorError::Io)?;
        guard.write_all(b"\n").await.map_err(ExecutorError::Io)?;
        guard.flush().await.map_err(ExecutorError::Io)?;
        Ok(())
    }
}

pub type PendingReceiver = oneshot::Receiver<PendingResponse>;

pub async fn await_response<R>(
    receiver: PendingReceiver,
    label: &str,
    cancel: CancellationToken,
) -> Result<R, ExecutorError>
where
    R: DeserializeOwned + Debug,
{
    let response = tokio::select! {
        _ = cancel.cancelled() => {
            return Err(ExecutorError::Io(io::Error::other(format!(
                "{label} request cancelled",
            ))));
        }
        result = receiver => result,
    };

    match response {
        Ok(PendingResponse::Result(value)) => {
            let value = sanitize_response_value(label, value);
            serde_json::from_value(value).map_err(|err| {
                ExecutorError::Io(io::Error::other(format!(
                    "failed to decode {label} response: {err}",
                )))
            })
        }
        Ok(PendingResponse::Error(error)) => Err(ExecutorError::Io(io::Error::other(format!(
            "{label} request failed: {}",
            error.error.message
        )))),
        Ok(PendingResponse::Shutdown) => Err(ExecutorError::Io(io::Error::other(format!(
            "server was shutdown while waiting for {label} response",
        )))),
        Err(_) => Err(ExecutorError::Io(io::Error::other(format!(
            "{label} request was dropped",
        )))),
    }
}

pub(super) fn sanitize_response_value(label: &str, mut value: Value) -> Value {
    // Native Codex renamed this reviewer and accepts guardian_subagent as an
    // alias. Adapt only this typed response copy for the pinned protocol; raw
    // logs, native config, outbound requests and approval decisions stay intact.
    if matches!(label, "thread/start" | "thread/resume" | "thread/fork")
        && value.get("approvalsReviewer").and_then(Value::as_str) == Some("auto_review")
    {
        value["approvalsReviewer"] = Value::String("guardian_subagent".to_owned());
    }
    // Codex 0.159 reports standard tier explicitly; the pinned protocol uses null.
    // Never map an unknown/priority tier to standard.
    if matches!(
        label,
        "thread/start" | "thread/resume" | "thread/fork" | "thread/read"
    ) && value.get("serviceTier").and_then(Value::as_str) == Some("default")
    {
        value["serviceTier"] = Value::Null;
    }
    if matches!(label, "thread/resume" | "thread/fork" | "thread/read") {
        drop_unknown_thread_items(label, &mut value);
    }
    if matches!(
        label,
        "thread/resume" | "thread/fork" | "thread/read" | "thread/rollback"
    ) && let Some(turns) = value
        .pointer_mut("/thread/turns")
        .and_then(Value::as_array_mut)
    {
        for turn in turns {
            normalize_turn_error(turn.get_mut("error"));
        }
    }
    if matches!(label, "turn/start" | "turn/steer") {
        normalize_turn_error(value.pointer_mut("/turn/error"));
    }
    value
}

/// Accept new error categories without discarding the error message or failed
/// turn status. Only touch protocol error fields, never arbitrary tool output.
fn normalize_turn_error(error: Option<&mut Value>) {
    let Some(info) = error.and_then(|error| error.get_mut("codexErrorInfo")) else {
        return;
    };
    if info.is_null() {
        return;
    }
    if let Err(error) = serde_json::from_value::<CodexErrorInfo>(info.clone())
        && error.to_string().starts_with("unknown variant `")
    {
        tracing::warn!("mapping an unknown Codex error category to other");
        *info = Value::String("other".to_owned());
    }
}

pub(super) fn parse_server_notification(
    line: &str,
) -> Result<ServerNotification, serde_json::Error> {
    let mut value: Value = serde_json::from_str(line)?;
    match value.get("method").and_then(Value::as_str) {
        Some("error") => normalize_turn_error(value.pointer_mut("/params/error")),
        Some("turn/started" | "turn/completed") => {
            normalize_turn_error(value.pointer_mut("/params/turn/error"));
        }
        _ => {}
    }
    serde_json::from_value(value)
}

fn drop_unknown_thread_items(label: &str, value: &mut Value) {
    let Some(turns) = value
        .get_mut("thread")
        .and_then(|thread| thread.get_mut("turns"))
        .and_then(Value::as_array_mut)
    else {
        return;
    };

    for turn in turns {
        let Some(items) = turn.get_mut("items").and_then(Value::as_array_mut) else {
            continue;
        };
        let original_len = items.len();
        items.retain(is_known_thread_item);
        let dropped = original_len.saturating_sub(items.len());
        if dropped > 0 {
            tracing::warn!(
                dropped,
                "dropped unknown Codex thread item variant(s) from {label} response"
            );
        }
    }
}

fn is_known_thread_item(item: &Value) -> bool {
    let Some(item_type) = item.get("type").and_then(Value::as_str) else {
        return true;
    };

    matches!(
        item_type,
        "userMessage"
            | "agentMessage"
            | "plan"
            | "reasoning"
            | "commandExecution"
            | "fileChange"
            | "mcpToolCall"
            | "dynamicToolCall"
            | "collabAgentToolCall"
            | "webSearch"
            | "imageView"
            | "imageGeneration"
            | "enteredReviewMode"
            | "exitedReviewMode"
            | "contextCompaction"
    )
}

#[async_trait]
pub trait JsonRpcCallbacks: Send + Sync {
    async fn on_request(
        &self,
        peer: &JsonRpcPeer,
        raw: &str,
        request: JSONRPCRequest,
    ) -> Result<(), ExecutorError>;

    async fn on_response(
        &self,
        peer: &JsonRpcPeer,
        raw: &str,
        response: &JSONRPCResponse,
    ) -> Result<(), ExecutorError>;

    async fn on_error(
        &self,
        peer: &JsonRpcPeer,
        raw: &str,
        error: &JSONRPCError,
    ) -> Result<(), ExecutorError>;

    async fn on_notification(
        &self,
        peer: &JsonRpcPeer,
        raw: &str,
        notification: JSONRPCNotification,
    ) -> Result<bool, ExecutorError>;

    async fn on_non_json(&self, _raw: &str) -> Result<(), ExecutorError>;
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::sanitize_response_value;

    fn reviewer_response() -> serde_json::Value {
        let mut value = new_error_response();
        value["approvalsReviewer"] = json!("auto_review");
        value["sandbox"] = json!({"type":"workspaceWrite", "writableRoots":["/workspace"],
            "networkAccess":false, "excludeTmpdirEnvVar":true, "excludeSlashTmp":true});
        value["thread"]["turns"][0]["error"]["codexErrorInfo"] = json!("other");
        value
    }

    async fn receive<R: serde::de::DeserializeOwned + std::fmt::Debug>(
        method: &str,
        value: serde_json::Value,
    ) -> Result<R, crate::executors::ExecutorError> {
        let (tx, rx) = tokio::sync::oneshot::channel();
        tx.send(super::PendingResponse::Result(value)).unwrap();
        super::await_response(rx, method, tokio_util::sync::CancellationToken::new()).await
    }

    async fn reviewer_compatibility<R>(method: &str)
    where
        R: serde::de::DeserializeOwned + serde::Serialize + std::fmt::Debug,
    {
        let value = reviewer_response();
        let error = serde_json::from_value::<R>(value.clone())
            .unwrap_err()
            .to_string();
        assert!(error.contains("unknown variant `auto_review`"), "{error}");
        assert!(error.contains("`user` or `guardian_subagent`"), "{error}");
        let response: R = receive(method, value.clone()).await.unwrap();
        let mut expected = value.clone();
        expected["approvalsReviewer"] = json!("guardian_subagent");
        assert_eq!(sanitize_response_value(method, value.clone()), expected);
        let legacy: R = serde_json::from_value(expected).unwrap();
        assert_eq!(
            serde_json::to_value(response).unwrap(),
            serde_json::to_value(legacy).unwrap()
        );

        for reviewer in [json!("user"), json!("guardian_subagent")] {
            let mut value = value.clone();
            value["approvalsReviewer"] = reviewer;
            assert_eq!(sanitize_response_value(method, value.clone()), value);
            let response: R = receive(method, value.clone()).await.unwrap();
            let legacy: R = serde_json::from_value(value).unwrap();
            assert_eq!(
                serde_json::to_value(response).unwrap(),
                serde_json::to_value(legacy).unwrap()
            );
        }
        for reviewer in [
            json!("future_reviewer"),
            json!("AUTO_REVIEW"),
            json!(null),
            json!(42),
            json!({"auto_review":true}),
            json!(["auto_review"]),
        ] {
            let mut value = value.clone();
            value["approvalsReviewer"] = reviewer;
            assert_eq!(sanitize_response_value(method, value.clone()), value);
            assert!(receive::<R>(method, value).await.is_err());
        }
        let mut missing = value.clone();
        missing.as_object_mut().unwrap().remove("approvalsReviewer");
        assert!(receive::<R>(method, missing).await.is_err());
        // A recognized reviewer must not hide malformed policy or sandbox data.
        for field in ["approvalPolicy", "sandbox", "thread"] {
            let mut malformed = value.clone();
            malformed[field] = json!(42);
            assert!(receive::<R>(method, malformed).await.is_err(), "{field}");
        }
    }

    #[tokio::test]
    async fn native_reviewer_start_uses_actual_typed_await_response() {
        reviewer_compatibility::<codex_app_server_protocol::ThreadStartResponse>("thread/start")
            .await;
    }

    #[tokio::test]
    async fn native_reviewer_resume_uses_actual_typed_await_response() {
        reviewer_compatibility::<codex_app_server_protocol::ThreadResumeResponse>("thread/resume")
            .await;
    }

    #[tokio::test]
    async fn native_reviewer_fork_uses_actual_typed_await_response() {
        reviewer_compatibility::<codex_app_server_protocol::ThreadForkResponse>("thread/fork")
            .await;
    }

    #[tokio::test]
    async fn native_reviewer_scope_preserves_nested_payloads_and_unrelated_methods() {
        let mut value = reviewer_response();
        value["thread"]["turns"][0]["items"] = json!([{
            "type":"mcpToolCall", "result":{"approvalsReviewer":"auto_review",
                "decision":"decline", "approvalPolicy":"never", "sandbox":"user-owned"}
        }]);
        value["nested"] = json!({"approvalsReviewer":"auto_review"});
        for method in ["thread/start", "thread/resume", "thread/fork"] {
            let mut expected = value.clone();
            expected["approvalsReviewer"] = json!("guardian_subagent");
            assert_eq!(sanitize_response_value(method, value.clone()), expected);
        }
        for method in [
            "thread/read",
            "thread/rollback",
            "turn/start",
            "turn/steer",
            "config/read",
            "item/commandExecution/requestApproval",
            "other",
        ] {
            assert_eq!(sanitize_response_value(method, value.clone()), value);
            let response: serde_json::Value = receive(method, value.clone()).await.unwrap();
            assert_eq!(response, value);
        }
        for malformed in [json!(null), json!(42), json!("auto_review"), json!([])] {
            assert_eq!(
                sanitize_response_value("thread/start", malformed.clone()),
                malformed
            );
        }
    }

    #[tokio::test]
    async fn native_reviewer_preserves_rpc_identity_raw_history_and_errors() {
        for id in [json!(123), json!("request-fixture")] {
            let envelope = json!({"id":id, "result":reviewer_response()});
            let raw = envelope.to_string();
            let codex_app_server_protocol::JSONRPCMessage::Response(response) =
                serde_json::from_str(&raw).unwrap()
            else {
                panic!("response");
            };
            let typed: codex_app_server_protocol::ThreadResumeResponse =
                receive("thread/resume", response.result.clone())
                    .await
                    .unwrap();
            assert_eq!(typed.thread.id, "thread-fixture");
            assert_eq!(typed.thread.turns[0].id, "failed-turn");
            assert_eq!(
                typed.thread.turns[0].status,
                codex_app_server_protocol::TurnStatus::Failed
            );
            assert_eq!(serde_json::to_value(response.id).unwrap(), id);
            assert_eq!(response.result, envelope["result"]);
            assert_eq!(
                serde_json::from_str::<serde_json::Value>(&raw).unwrap(),
                envelope
            );
        }
        let (tx, rx) = tokio::sync::oneshot::channel();
        tx.send(super::PendingResponse::Error(
            serde_json::from_value(json!({
                "id":"native-error", "error":{"code":-32602, "message":"auto_review rejected",
                    "data":{"approvalsReviewer":"auto_review"}}
            }))
            .unwrap(),
        ))
        .unwrap();
        let error = super::await_response::<codex_app_server_protocol::ThreadStartResponse>(
            rx,
            "thread/start",
            tokio_util::sync::CancellationToken::new(),
        )
        .await
        .unwrap_err();
        assert!(
            error
                .to_string()
                .contains("thread/start request failed: auto_review rejected")
        );
    }

    #[tokio::test]
    async fn deadline_removes_pending_receipt_and_late_response_cannot_resolve_it() {
        use std::process::Stdio;

        use crate::{
            env::RepoContext,
            executors::codex::client::{AppServerClient, LogWriter},
        };
        let mut child = tokio::process::Command::new("python3")
            .args([
                "-u",
                "-c",
                r#"
import sys
for line in sys.stdin: pass
"#,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .unwrap();
        let cancel = tokio_util::sync::CancellationToken::new();
        let client = AppServerClient::new(
            LogWriter::new(tokio::io::sink()),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        let (tx, _rx) = tokio::sync::oneshot::channel();
        let peer = super::JsonRpcPeer::spawn(
            child.stdin.take().unwrap(),
            child.stdout.take().unwrap(),
            client,
            super::ExitSignalSender::new(tx),
            cancel.clone(),
        );
        let id = peer.next_request_id();
        let result: Result<serde_json::Value, _> = peer
            .request_with_deadline(
                id.clone(),
                &json!({"id":id,"method":"synthetic/receipt","params":{}}),
                "synthetic/receipt",
                cancel.clone(),
                std::time::Duration::from_millis(30),
            )
            .await;
        assert!(
            matches!(result,Err(crate::executors::ExecutorError::Io(ref e)) if e.kind()==std::io::ErrorKind::TimedOut)
        );
        assert!(peer.pending.lock().await.is_empty());
        peer.resolve(id, super::PendingResponse::Result(json!({"late":true})))
            .await;
        assert!(peer.pending.lock().await.is_empty());
        assert!(!cancel.is_cancelled());
        assert!(child.try_wait().unwrap().is_none());
        cancel.cancel();
        child.kill().await.unwrap();
        child.wait().await.unwrap();
    }

    #[tokio::test]
    async fn unexpected_eof_and_failed_native_turn_are_not_success() {
        use std::process::Stdio;

        use crate::{
            env::RepoContext,
            executors::{
                ExecutorExitResult,
                codex::client::{AppServerClient, LogWriter},
            },
        };
        for status in [None, Some("failed"), Some("completed")] {
            let mut command = tokio::process::Command::new("sh");
            match status {
                None => {
                    command.args(["-c", "exit 0"]);
                }
                Some(status) => {
                    command.args(["-c", "printf '%s\\n' \"$1\"", "fixture"]).arg(serde_json::json!({
                    "method":"turn/completed", "params":{"threadId":"root", "turn":{"id":"turn", "status":status, "items":[], "error":null}}
                }).to_string());
                }
            }
            let mut child = command
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .spawn()
                .unwrap();
            let cancel = tokio_util::sync::CancellationToken::new();
            let client = AppServerClient::new(
                LogWriter::new(tokio::io::sink()),
                None,
                false,
                false,
                RepoContext::default(),
                false,
                String::new(),
                cancel.clone(),
            );
            client.register_session("root").await.unwrap();
            let (tx, rx) = tokio::sync::oneshot::channel();
            let _peer = super::JsonRpcPeer::spawn(
                child.stdin.take().unwrap(),
                child.stdout.take().unwrap(),
                client,
                super::ExitSignalSender::new(tx),
                cancel,
            );
            let result = tokio::time::timeout(std::time::Duration::from_secs(3), rx)
                .await
                .unwrap()
                .unwrap();
            assert!(
                matches!(
                    (&result, status),
                    (ExecutorExitResult::Success, Some("completed"))
                        | (ExecutorExitResult::Failure, None | Some("failed"))
                ),
                "unexpected result: {result:?}"
            );
            child.wait().await.unwrap();
        }
    }

    #[test]
    fn explicit_standard_tier_is_compatible_but_priority_is_not_silently_downgraded() {
        for method in [
            "thread/start",
            "thread/resume",
            "thread/fork",
            "thread/read",
        ] {
            let mut value = new_error_response();
            value["serviceTier"] = json!("default");
            value["thread"]["turns"] = json!([]);
            let response: codex_app_server_protocol::ThreadResumeResponse =
                serde_json::from_value(sanitize_response_value(method, value)).unwrap();
            assert!(response.service_tier.is_none());
            let value = json!({"serviceTier":"priority"});
            assert_eq!(
                sanitize_response_value(method, value)["serviceTier"],
                "priority"
            );
        }
    }

    fn new_error_response() -> serde_json::Value {
        serde_json::from_str(include_str!("fixtures/new-error-resume.json")).unwrap()
    }

    #[tokio::test]
    async fn resume_decodes_new_error_category_and_preserves_failed_turn() {
        use codex_app_server_protocol::{CodexErrorInfo, ThreadResumeResponse, TurnStatus};
        let value = new_error_response();
        assert!(serde_json::from_value::<ThreadResumeResponse>(value.clone()).is_err());
        let (tx, rx) = tokio::sync::oneshot::channel();
        tx.send(super::PendingResponse::Result(value)).unwrap();
        let response: ThreadResumeResponse = super::await_response(
            rx,
            "thread/resume",
            tokio_util::sync::CancellationToken::new(),
        )
        .await
        .unwrap();
        let turn = &response.thread.turns[0];
        assert_eq!(turn.status, TurnStatus::Failed);
        let error = turn.error.as_ref().unwrap();
        assert_eq!(error.codex_error_info, Some(CodexErrorInfo::Other));
        assert!(error.message.contains("blocked by our safety systems"));
    }

    #[test]
    fn thread_error_compatibility_covers_read_fork_rollback_and_structured_categories() {
        for method in [
            "thread/resume",
            "thread/read",
            "thread/fork",
            "thread/rollback",
        ] {
            let mut value = new_error_response();
            value["thread"]["turns"][0]["error"]["codexErrorInfo"] =
                json!({"futureCategory": {"detail": "new"}});
            let sanitized = sanitize_response_value(method, value);
            assert_eq!(
                sanitized["thread"]["turns"][0]["error"]["codexErrorInfo"],
                "other"
            );
        }
    }

    #[test]
    fn error_notification_preserves_message_retry_and_identity() {
        use codex_app_server_protocol::{CodexErrorInfo, ServerNotification};
        let value = json!({"method":"error", "params": {
            "threadId":"thread-fixture", "turnId":"failed-turn", "willRetry":false,
            "error":new_error_response()["thread"]["turns"][0]["error"]
        }});
        let ServerNotification::Error(notification) =
            super::parse_server_notification(&value.to_string()).unwrap()
        else {
            panic!("expected error");
        };
        assert!(!notification.will_retry);
        assert_eq!(notification.thread_id, "thread-fixture");
        assert_eq!(
            notification.error.codex_error_info,
            Some(CodexErrorInfo::Other)
        );
        assert!(
            notification
                .error
                .message
                .contains("blocked by our safety systems")
        );
    }

    #[test]
    fn compatibility_preserves_known_errors_malformed_data_and_tool_payloads() {
        for category in [
            json!("usageLimitExceeded"),
            json!({"httpConnectionFailed":{"httpStatusCode":503}}),
            json!({"httpConnectionFailed":{"httpStatusCode":"invalid"}}),
            json!(null),
            json!(42),
        ] {
            let mut value = new_error_response();
            value["thread"]["turns"][0]["error"]["codexErrorInfo"] = category;
            assert_eq!(
                sanitize_response_value("thread/resume", value.clone()),
                value
            );
        }
        let mut value = new_error_response();
        value["thread"]["turns"][0]["items"] = json!([{
            "type":"mcpToolCall", "result":{"codexErrorInfo":"user-owned-value"}
        }]);
        let sanitized = sanitize_response_value("thread/resume", value);
        assert_eq!(
            sanitized["thread"]["turns"][0]["items"][0]["result"]["codexErrorInfo"],
            "user-owned-value"
        );
    }

    #[test]
    #[ignore = "requires a private captured thread/resume response"]
    fn captured_resume_response_decodes_without_losing_turns() {
        use codex_app_server_protocol::ThreadResumeResponse;
        let path = std::env::var("VK_TEST_RESUME_RESPONSE").expect("fixture path");
        let value: serde_json::Value =
            serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let count = value["thread"]["turns"].as_array().unwrap().len();
        let id = value["thread"]["id"].as_str().unwrap().to_owned();
        let response: ThreadResumeResponse =
            serde_json::from_value(sanitize_response_value("thread/resume", value)).unwrap();
        assert_eq!(response.thread.id, id);
        assert_eq!(response.thread.turns.len(), count);
        assert!(response.thread.turns.iter().any(|t| t.error.is_some()));
    }

    #[test]
    fn thread_response_sanitizer_drops_unknown_thread_items() {
        let value = json!({
            "thread": {
                "turns": [
                    {
                        "items": [
                            { "type": "userMessage", "id": "known", "content": [] },
                            { "type": "subAgentActivity", "id": "newer-protocol" },
                            { "type": "agentMessage", "id": "also-known", "text": "done" }
                        ]
                    }
                ]
            }
        });

        let sanitized = sanitize_response_value("thread/resume", value);
        let items = sanitized["thread"]["turns"][0]["items"].as_array().unwrap();

        assert_eq!(items.len(), 2);
        assert_eq!(items[0]["type"], "userMessage");
        assert_eq!(items[1]["type"], "agentMessage");
    }

    #[test]
    fn non_thread_response_sanitizer_keeps_unknown_items() {
        let value = json!({
            "thread": {
                "turns": [
                    {
                        "items": [
                            { "type": "subAgentActivity", "id": "newer-protocol" }
                        ]
                    }
                ]
            }
        });

        let sanitized = sanitize_response_value("turn/start", value);
        let items = sanitized["thread"]["turns"][0]["items"].as_array().unwrap();

        assert_eq!(items.len(), 1);
        assert_eq!(items[0]["type"], "subAgentActivity");
    }
}
