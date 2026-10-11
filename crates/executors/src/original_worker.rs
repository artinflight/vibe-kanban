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
    async fn bind(&self, env: &ExecutionEnv) -> io::Result<Option<Transport>>;
    async fn native_started(
        &self,
        env: &ExecutionEnv,
        thread: &str,
        model: &str,
        effort: &Value,
    ) -> io::Result<()>;
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
pub async fn stdio(socket: PathBuf) -> io::Result<()> {
    let token = std::env::var("VK_BOUNDED_SOCKET_TOKEN")
        .map_err(|_| io::Error::other("Missing execution binding"))?;
    serve(
        BufReader::new(tokio::io::stdin()),
        tokio::io::stdout(),
        move |request| {
            let socket = socket.clone();
            let token = token.clone();
            async move {
                let mut stream = tokio::net::UnixStream::connect(socket).await?;
                let mut wire = serde_json::to_vec(&json!({"token":token,"request":request}))?;
                wire.push(b'\n');
                stream.write_all(&wire).await?;
                stream.shutdown().await?;
                let mut reader = BufReader::new(stream);
                let mut reply = String::new();
                // The server emits only a small execution receipt or a fixed diagnostic.
                use tokio::io::AsyncReadExt;
                reader.take(LIMIT as u64).read_to_string(&mut reply).await?;
                serde_json::from_str(&reply)
                    .map_err(|_| io::Error::other("Invalid backend receipt"))
            }
        },
    )
    .await
}
