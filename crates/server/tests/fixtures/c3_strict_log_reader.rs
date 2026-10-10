// Exact incumbent c3c48e63 strict reader; compiled rollback-format compatibility fixture.
use std::path::Path;

use tokio::io::AsyncReadExt;
use utils::log_msg::LogMsg;

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
