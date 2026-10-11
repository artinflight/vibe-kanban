//! Process-scoped transport. Authority and admission live in the backend.
use std::{
    io,
    path::PathBuf,
    sync::{Arc, OnceLock},
};

pub use async_trait::async_trait;
use serde_json::{Value, json};
use tokio::io::{AsyncBufRead, AsyncBufReadExt, AsyncWrite, AsyncWriteExt, BufReader};

use crate::env::ExecutionEnv;

/// Held across the actual native activation RPC, not merely its preflight.
pub type ActivationFence = tokio::sync::OwnedMutexGuard<()>;

#[async_trait]
pub trait LaunchGuard: Send + Sync + std::fmt::Debug {
    async fn resolved(
        &self,
        agent: &crate::executors::CodingAgent,
        raw: &crate::profile::ExecutorConfig,
    ) -> io::Result<()>;
    async fn activation(&self, input: Option<&str>) -> io::Result<ActivationFence>;
    fn worker(&self) -> bool;
}

/// The production follow-up/initial launch path clones once. Approval service
/// injection, prompt construction and launcher resolution happen only afterwards.
pub async fn resolve_for_launch(
    raw: &crate::profile::ExecutorConfig,
    env: &ExecutionEnv,
) -> Result<crate::executors::CodingAgent, crate::executors::ExecutorError> {
    use crate::executors::StandardCodingAgentExecutor;
    let profile = raw.profile_id();
    let mut agent = crate::profile::ExecutorConfigs::get_cached()
        .get_coding_agent(&profile)
        .ok_or_else(|| crate::executors::ExecutorError::UnknownExecutorType(profile.to_string()))?;
    agent.apply_overrides(raw);
    if let Some(guard) = &env.original_worker {
        guard.resolved(&agent, raw).await?;
    }
    Ok(agent)
}

pub fn verify_resolved(
    agent: &crate::executors::CodingAgent,
    raw: &crate::profile::ExecutorConfig,
    expected: &crate::profile::ExecutorConfig,
    pin: &str,
) -> io::Result<()> {
    if raw != expected || profile_digest(agent)? != pin {
        return Err(io::Error::other(
            "Actual resolved launch instance differs from fixed profile",
        ));
    }
    Ok(())
}

pub fn profile_digest(agent: &crate::executors::CodingAgent) -> io::Result<String> {
    use sha2::{Digest, Sha256};
    let mut value = serde_json::to_value(agent)?;
    value.sort_all_objects();
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(&value)?)))
}

pub fn worker_goal_load_allowed(snapshot: &Value) -> io::Result<()> {
    match snapshot.get("goal") {
        Some(Value::Null) => Ok(()),
        Some(goal)
            if matches!(
                goal.get("status").and_then(Value::as_str),
                Some("paused" | "complete" | "completed")
            ) =>
        {
            Ok(())
        }
        _ => Err(io::Error::other(
            "Worker goal is active or unknown; thread was not loaded",
        )),
    }
}

pub const TOOL: &str = "continue_original_worker";
pub const READY: &str = "finish_at_review_readiness";
pub const REVOKE: &str = "revoke_original_worker_continuation";
pub const LIMIT: usize = 64 * 1024;

pub struct Transport {
    pub socket: PathBuf,
    pub token: String,
}

#[async_trait]
pub trait Backend: Send + Sync {
    async fn launch_guard(&self, env: &ExecutionEnv) -> io::Result<Option<Arc<dyn LaunchGuard>>>;
    async fn bind(&self, env: &ExecutionEnv) -> io::Result<Option<Transport>>;
    async fn native_started(
        &self,
        env: &ExecutionEnv,
        thread: &str,
        model: &str,
        effort: &Value,
    ) -> io::Result<()>;
}

pub async fn attach(env: &ExecutionEnv) -> io::Result<Option<Arc<dyn LaunchGuard>>> {
    match BACKEND.get() {
        Some(backend) => backend.launch_guard(env).await,
        None => Ok(None),
    }
}

pub async fn activation(
    env: &ExecutionEnv,
    input: Option<&str>,
) -> io::Result<Option<ActivationFence>> {
    match &env.original_worker {
        Some(guard) => guard.activation(input).await.map(Some),
        None => Ok(None),
    }
}

static BACKEND: OnceLock<Arc<dyn Backend>> = OnceLock::new();
pub fn register(backend: Arc<dyn Backend>) -> io::Result<()> {
    BACKEND
        .set(backend)
        .map_err(|_| io::Error::other("Continuation backend already registered"))
}

pub async fn bind(env: &ExecutionEnv) -> io::Result<Option<Transport>> {
    match BACKEND.get() {
        Some(backend) => backend.bind(env).await,
        None => Ok(None),
    }
}

pub async fn native_started(
    env: &ExecutionEnv,
    thread: &str,
    model: &str,
    effort: &Value,
) -> io::Result<()> {
    match BACKEND.get() {
        Some(backend) => backend.native_started(env, thread, model, effort).await,
        None => Ok(()),
    }
}

pub fn tool(request: &Value) -> io::Result<&str> {
    let envelope = request
        .as_object()
        .ok_or_else(|| io::Error::other("Invalid MCP envelope"))?;
    if request["jsonrpc"] != "2.0"
        || request["method"] != "tools/call"
        || envelope
            .keys()
            .any(|k| !matches!(k.as_str(), "jsonrpc" | "id" | "method" | "params"))
    {
        return Err(io::Error::other("Unbounded MCP envelope or metadata"));
    }
    let params = request
        .get("params")
        .and_then(Value::as_object)
        .ok_or_else(|| io::Error::other("Invalid tool parameters"))?;
    if params
        .keys()
        .any(|k| !matches!(k.as_str(), "name" | "arguments"))
        || params
            .get("arguments")
            .is_some_and(|v| v.as_object().is_none_or(|v| !v.is_empty()))
    {
        return Err(io::Error::other(
            "Continuation accepts no arguments or metadata",
        ));
    }
    match params.get("name").and_then(Value::as_str) {
        Some(name @ (TOOL | READY | REVOKE)) => Ok(name),
        _ => Err(io::Error::other("Unsupported continuation action")),
    }
}

pub fn discovery(request: &Value) -> Option<Value> {
    let result = match request.get("method")?.as_str()? {
        "initialize" => {
            json!({"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"original-worker","version":"1"}})
        }
        "ping" => json!({}),
        "resources/list" => json!({"resources":[]}),
        "resources/templates/list" => json!({"resourceTemplates":[]}),
        "tools/list" => json!({"tools":[
            {"name":TOOL,"description":"Resume only your release-authorized original worker for the fixed current revision goal. The backend supplies the target and instructions and rechecks all guards. No amendments or other actions are authorized. Use only for a legitimate continuation; never send test prompts.","inputSchema":{"type":"object","properties":{},"additionalProperties":false}},
            {"name":READY,"description":"Permanently end this continuation grant at owner review readiness. Does not publish or approve Figma/AE.","inputSchema":{"type":"object","properties":{},"additionalProperties":false}},
            {"name":REVOKE,"description":"Permanently revoke this bounded continuation grant.","inputSchema":{"type":"object","properties":{},"additionalProperties":false}}
        ]}),
        _ => return None,
    };
    Some(json!({"jsonrpc":"2.0","id":request.get("id"),"result":result}))
}

pub fn error(request: &Value, reason: &str) -> Value {
    json!({"jsonrpc":"2.0","id":request.get("id"),"error":{"code":-32000,"message":reason}})
}

/// Read bounded JSON lines; errors never echo arguments, tokens or contract text.
pub async fn serve<R, W, F, Fut>(mut input: R, mut output: W, mut call: F) -> io::Result<()>
where
    R: AsyncBufRead + Unpin,
    W: AsyncWrite + Unpin,
    F: FnMut(Value) -> Fut,
    Fut: std::future::Future<Output = io::Result<Value>>,
{
    loop {
        let mut line = Vec::new();
        loop {
            let buf = input.fill_buf().await?;
            if buf.is_empty() {
                break;
            }
            let count = buf
                .iter()
                .position(|b| *b == b'\n')
                .map_or(buf.len(), |p| p + 1);
            if line.len() + count > LIMIT {
                return Err(io::Error::other("Oversized MCP frame"));
            }
            line.extend_from_slice(&buf[..count]);
            input.consume(count);
            if line.last() == Some(&b'\n') {
                break;
            }
        }
        if line.is_empty() {
            return Ok(());
        }
        let request: Value =
            serde_json::from_slice(&line).map_err(|_| io::Error::other("Invalid MCP frame"))?;
        if request.get("id").is_none() {
            continue;
        }
        let response = if let Some(result) = discovery(&request) {
            result
        } else if request["method"] == "tools/call" && tool(&request).is_ok() {
            call(request.clone()).await.unwrap_or_else(|_| {
                error(&request, "Continuation unavailable; no permission granted")
            })
        } else {
            error(&request, "Unsupported or unbounded request")
        };
        let mut bytes = serde_json::to_vec(&response)?;
        bytes.push(b'\n');
        output.write_all(&bytes).await?;
        output.flush().await?;
    }
}

#[cfg(unix)]
pub async fn forward(socket: PathBuf, token: String, request: Value) -> io::Result<Value> {
    use tokio::io::AsyncReadExt;
    let mut stream = tokio::net::UnixStream::connect(socket).await?;
    let mut wire = serde_json::to_vec(&json!({"token":token,"request":request}))?;
    wire.push(b'\n');
    stream.write_all(&wire).await?;
    stream.shutdown().await?;
    let reader = BufReader::new(stream);
    let mut reply = String::new();
    reader
        .take(LIMIT as u64 + 1)
        .read_to_string(&mut reply)
        .await?;
    if reply.len() > LIMIT {
        return Err(io::Error::other("Oversized backend receipt"));
    }
    serde_json::from_str(&reply).map_err(|_| io::Error::other("Invalid backend receipt"))
}

#[cfg(unix)]
pub async fn stdio(socket: PathBuf) -> io::Result<()> {
    let token = std::env::var("VK_BOUNDED_SOCKET_TOKEN")
        .map_err(|_| io::Error::other("Missing execution binding"))?;
    serve(
        BufReader::new(tokio::io::stdin()),
        tokio::io::stdout(),
        move |request| {
            let socket = socket.clone();
            let token = token.clone();
            forward(socket, token, request)
        },
    )
    .await
}

#[cfg(test)]
mod tests;
