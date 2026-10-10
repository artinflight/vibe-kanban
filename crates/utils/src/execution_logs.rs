use std::path::{Path, PathBuf};

use futures::{StreamExt, stream::BoxStream};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio_stream::wrappers::LinesStream;
use uuid::Uuid;

use crate::{assets::asset_dir, log_msg::LogMsg};

pub const EXECUTION_LOGS_DIRNAME: &str = "sessions";

pub fn process_logs_session_dir(session_id: Uuid) -> PathBuf {
    resolve_process_logs_session_dir(&asset_dir(), session_id)
}

pub fn process_log_file_path(session_id: Uuid, process_id: Uuid) -> PathBuf {
    process_log_file_path_in_root(&asset_dir(), session_id, process_id)
}

pub fn process_log_file_path_in_root(root: &Path, session_id: Uuid, process_id: Uuid) -> PathBuf {
    resolve_process_logs_session_dir(root, session_id)
        .join("processes")
        .join(format!("{}.jsonl", process_id))
}

pub struct ExecutionLogWriter {
    path: PathBuf,
    file: tokio::fs::File,
    initially_empty: bool,
    status_path: PathBuf,
}

impl ExecutionLogWriter {
    pub async fn new(path: PathBuf) -> std::io::Result<Self> {
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        let file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .await?;
        let initially_empty = file.metadata().await?.len() == 0;
        let status_path = path.with_extension("capture.json");
        if initially_empty {
            tokio::fs::write(&status_path, b"{\"capture_state\":\"pending\"}\n").await?;
        }
        Ok(Self {
            path,
            file,
            initially_empty,
            status_path,
        })
    }

    pub async fn new_for_execution(session_id: Uuid, execution_id: Uuid) -> std::io::Result<Self> {
        Self::new(process_log_file_path(session_id, execution_id)).await
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub async fn finish_for_review(&mut self) -> std::io::Result<()> {
        if !self.initially_empty {
            return Err(std::io::Error::other(
                "Cannot certify an appended pre-existing log",
            ));
        }
        self.file.flush().await?;
        self.file.sync_all().await?;
        tokio::fs::write(&self.status_path, b"{\"capture_state\":\"closed\"}\n").await
    }

    pub async fn append_jsonl_line(&mut self, jsonl_line: &str) -> std::io::Result<()> {
        self.file.write_all(jsonl_line.as_bytes()).await
    }
}

/// Preserve UTF-8 code points split across pipe reads; malformed stdout fails
/// capture rather than silently changing the exact assistant reply bytes.
pub fn decode_stdout<S>(stream: S) -> BoxStream<'static, std::io::Result<LogMsg>>
where
    S: futures::Stream<Item = std::io::Result<bytes::Bytes>> + Send + 'static,
{
    futures::stream::unfold(
        (stream.boxed(), Vec::<u8>::new(), false),
        |(mut stream, mut pending, done)| async move {
            if done {
                return None;
            }
            loop {
                match stream.next().await {
                    Some(Ok(chunk)) => pending.extend_from_slice(&chunk),
                    Some(Err(e)) => return Some((Err(e), (stream, pending, true))),
                    None if pending.is_empty() => return None,
                    None => {
                        return Some((
                            Err(std::io::Error::other("Incomplete UTF-8 stdout")),
                            (stream, pending, true),
                        ));
                    }
                }
                let valid = match std::str::from_utf8(&pending) {
                    Ok(_) => pending.len(),
                    Err(e) if e.error_len().is_none() => e.valid_up_to(),
                    Err(_) => {
                        return Some((
                            Err(std::io::Error::other("Invalid UTF-8 stdout")),
                            (stream, pending, true),
                        ));
                    }
                };
                if valid == 0 {
                    continue;
                }
                let suffix = pending.split_off(valid);
                let text = String::from_utf8(pending).expect("validated UTF-8 prefix");
                return Some((Ok(LogMsg::Stdout(text)), (stream, suffix, false)));
            }
        },
    )
    .boxed()
}

/// Presentation-only detection of a captured native stream prefix. This never
/// creates a writer-closure proof or repairs bytes from a native transcript.
pub async fn validate_native_capture(path: &Path, maximum: usize) -> std::io::Result<()> {
    // A writer interrupted on any boundary may leave syntactically valid JSON.
    // Its durable pending state is still not a completed capture. Historical
    // files without this sidecar retain framing detection, never gain a proof.
    let status_path = path.with_extension("capture.json");
    match tokio::fs::read(&status_path).await {
        Ok(bytes) => {
            let status: serde_json::Value = serde_json::from_slice(&bytes)
                .map_err(|_| std::io::Error::other("Damaged capture state"))?;
            if status["capture_state"] != "closed" {
                return Err(std::io::Error::other(
                    "Capture writer did not close successfully",
                ));
            }
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
        Err(e) => return Err(e),
    }
    let (_, messages) = read_execution_log_strict(path, maximum).await?;
    let stdout: String = messages
        .iter()
        .filter_map(|m| match m {
            LogMsg::Stdout(s) => Some(s.as_str()),
            _ => None,
        })
        .collect();
    if stdout.is_empty() || !stdout.ends_with('\n') {
        return Err(std::io::Error::other("Incomplete native log capture"));
    }
    for line in stdout.lines() {
        serde_json::from_str::<serde_json::Value>(line)
            .map_err(|_| std::io::Error::other("Damaged native log capture"))?;
    }
    Ok(())
}

pub async fn read_execution_log_file(path: &Path) -> std::io::Result<String> {
    tokio::fs::read_to_string(path).await
}

pub async fn stream_execution_log_file(
    path: &Path,
) -> std::io::Result<BoxStream<'static, std::io::Result<String>>> {
    let file = tokio::fs::File::open(path).await?;
    let reader = BufReader::new(file);

    Ok(LinesStream::new(reader.lines())
        .map(|line| line.map_err(|err| std::io::Error::new(std::io::ErrorKind::InvalidData, err)))
        .boxed())
}

pub fn parse_log_jsonl_lossy(execution_id: Uuid, jsonl: &str) -> Vec<LogMsg> {
    let mut messages = Vec::new();
    let mut bad_lines = 0usize;

    for line in jsonl.lines() {
        if line.trim().is_empty() {
            continue;
        }

        match serde_json::from_str::<LogMsg>(line) {
            Ok(msg) => messages.push(msg),
            Err(e) => {
                bad_lines += 1;
                if bad_lines <= 3 {
                    tracing::warn!(
                        "Skipping unparsable log line for execution {}: {}",
                        execution_id,
                        e
                    );
                }
            }
        }
    }

    if bad_lines > 3 {
        tracing::warn!(
            "Skipped {} unparsable log lines for execution {}",
            bad_lines,
            execution_id
        );
    }

    messages
}

fn uuid_prefix2(id: Uuid) -> String {
    let s = id.to_string();
    s.chars().take(2).collect()
}

fn resolve_process_logs_session_dir(root: &Path, session_id: Uuid) -> PathBuf {
    root.join(EXECUTION_LOGS_DIRNAME)
        .join(uuid_prefix2(session_id))
        .join(session_id.to_string())
}

/// Integrity reader for review only. UI recovery readers remain unchanged.
/// Read at most max_bytes + 1; reject blank, malformed, partial and unsupported
/// records instead of skipping them. The caller verifies the closed-writer hash.
pub async fn read_execution_log_strict(
    path: &Path,
    max_bytes: usize,
) -> std::io::Result<(Vec<u8>, Vec<LogMsg>)> {
    let file = tokio::fs::File::open(path).await?;
    let mut bytes = Vec::new();
    file.take(max_bytes as u64 + 1)
        .read_to_end(&mut bytes)
        .await?;
    if bytes.is_empty() || bytes.len() > max_bytes || bytes.last() != Some(&b'\n') {
        return Err(std::io::Error::other(
            "Empty, oversized or unterminated review log",
        ));
    }
    let text = std::str::from_utf8(&bytes)
        .map_err(|_| std::io::Error::other("Review log is not UTF-8"))?;
    let mut messages = Vec::new();
    for line in text.lines() {
        if messages.len() >= 100_000 {
            return Err(std::io::Error::other("Review log record bound exceeded"));
        }
        let msg: LogMsg = serde_json::from_str(line)
            .map_err(|_| std::io::Error::other("Invalid review log record"))?;
        if !matches!(msg, LogMsg::Stdout(_) | LogMsg::Stderr(_)) {
            return Err(std::io::Error::other("Unsupported review log record"));
        }
        messages.push(msg);
    }
    Ok((bytes, messages))
}

#[cfg(test)]
mod capture_tests {
    use super::*;
    #[tokio::test]
    async fn utf8_final_split_across_every_byte_is_exact() {
        let expected = "assistant final — ✓\n";
        let chunks = expected
            .as_bytes()
            .iter()
            .map(|b| Ok(bytes::Bytes::copy_from_slice(&[*b])))
            .collect::<Vec<_>>();
        let mut stream = decode_stdout(futures::stream::iter(chunks));
        let mut actual = String::new();
        while let Some(msg) = stream.next().await {
            if let LogMsg::Stdout(s) = msg.unwrap() {
                actual.push_str(&s);
            }
        }
        assert_eq!(actual, expected);
    }
    #[tokio::test]
    async fn partial_utf8_is_failure_not_fabricated_replacement() {
        let mut stream = decode_stdout(futures::stream::iter([Ok(bytes::Bytes::from_static(&[
            0xe2, 0x9c,
        ]))]));
        assert!(stream.next().await.unwrap().is_err());
    }
}
