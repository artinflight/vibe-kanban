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
    // Review materialization keeps its existing whole-file bound. Presentation
    // validates every byte while bounding each outer record and streaming each
    // native JSON line without retaining historical response bodies.
    let owned = path.to_path_buf();
    tokio::task::spawn_blocking(move || validate_native_capture_streaming(&owned, maximum))
        .await
        .map_err(|e| std::io::Error::other(format!("Capture verifier failed: {e}")))?
}

struct NativeCaptureReader<R> {
    outer: R,
    pending: std::io::Cursor<Vec<u8>>,
    maximum_record: usize,
    records: usize,
    saw_stdout: bool,
    last_stdout_byte: Option<u8>,
}

impl<R: std::io::BufRead> std::io::Read for NativeCaptureReader<R> {
    fn read(&mut self, output: &mut [u8]) -> std::io::Result<usize> {
        if output.is_empty() {
            return Ok(0);
        }
        loop {
            let read = std::io::Read::read(&mut self.pending, output)?;
            if read != 0 {
                return Ok(read);
            }
            let mut line = Vec::new();
            loop {
                let available = self.outer.fill_buf()?;
                if available.is_empty() {
                    if !line.is_empty() {
                        return Err(std::io::Error::other("Unterminated outer capture record"));
                    }
                    if !self.saw_stdout || self.last_stdout_byte != Some(b'\n') {
                        return Err(std::io::Error::other("Incomplete native log capture"));
                    }
                    return Ok(0);
                }
                let count = available
                    .iter()
                    .position(|&b| b == b'\n')
                    .map_or(available.len(), |p| p + 1);
                if line
                    .len()
                    .checked_add(count)
                    .is_none_or(|n| n > self.maximum_record)
                {
                    return Err(std::io::Error::other(
                        "Capture record exceeds existing materialization bound",
                    ));
                }
                let complete = available[count - 1] == b'\n';
                line.extend_from_slice(&available[..count]);
                self.outer.consume(count);
                if complete {
                    break;
                }
            }
            if self.records >= 100_000 {
                return Err(std::io::Error::other("Capture record bound exceeded"));
            }
            self.records += 1;
            let message: LogMsg = serde_json::from_slice(&line)
                .map_err(|_| std::io::Error::other("Invalid outer capture record"))?;
            match message {
                LogMsg::Stdout(text) => {
                    if let Some(last) = text.as_bytes().last() {
                        self.saw_stdout = true;
                        self.last_stdout_byte = Some(*last);
                    }
                    self.pending = std::io::Cursor::new(text.into_bytes());
                }
                LogMsg::Stderr(_) => {}
                _ => return Err(std::io::Error::other("Unsupported capture record")),
            }
        }
    }
}

// Expose exactly one newline-terminated native JSON record as a finite reader.
// serde's IgnoredAny validates all JSON syntax without allocating response trees.
struct NativeLine<'a, R> {
    input: &'a mut R,
    ended: bool,
    depth: usize,
    quoted: bool,
    escaped: bool,
    number: Vec<u8>,
    maximum_number: usize,
}
impl<R> NativeLine<'_, R> {
    fn check_bytes(&mut self, bytes: &[u8]) -> std::io::Result<()> {
        for &byte in bytes {
            if self.quoted {
                if self.escaped {
                    self.escaped = false;
                } else if byte == b'\\' {
                    self.escaped = true;
                } else if byte == b'"' {
                    self.quoted = false;
                }
                continue;
            }
            if !self.number.is_empty()
                && !matches!(byte, b'0'..=b'9' | b'-' | b'+' | b'.' | b'e' | b'E')
            {
                let value: serde_json::Value =
                    serde_json::from_slice(&self.number).map_err(|_| {
                        std::io::Error::other("Native JSON number out of range or invalid")
                    })?;
                if !value.is_number() {
                    return Err(std::io::Error::other("Invalid native JSON number"));
                }
                self.number.clear();
            }
            if !self.number.is_empty() || matches!(byte, b'0'..=b'9' | b'-') {
                if self.number.len() >= self.maximum_number {
                    return Err(std::io::Error::other(
                        "Native number exceeds existing materialization bound",
                    ));
                }
                self.number.push(byte);
            }
            match byte {
                b'"' => self.quoted = true,
                b'[' | b'{' => {
                    self.depth += 1;
                    if self.depth >= 128 {
                        return Err(std::io::Error::other(
                            "Native JSON recursion limit exceeded",
                        ));
                    }
                }
                b']' | b'}' => self.depth = self.depth.saturating_sub(1),
                _ => {}
            }
        }
        Ok(())
    }
}
impl<R: std::io::BufRead> std::io::Read for NativeLine<'_, R> {
    fn read(&mut self, output: &mut [u8]) -> std::io::Result<usize> {
        if output.is_empty() || self.ended {
            return Ok(0);
        }
        let available = self.input.fill_buf()?;
        if available.is_empty() {
            return Err(std::io::Error::other("Unterminated native JSON record"));
        }
        let count = output.len().min(
            available
                .iter()
                .position(|&b| b == b'\n')
                .map_or(available.len(), |p| p + 1),
        );
        self.ended = available[count - 1] == b'\n';
        output[..count].copy_from_slice(&available[..count]);
        self.check_bytes(&output[..count])?;
        self.input.consume(count);
        Ok(count)
    }
}

fn same_capture_version(a: &std::fs::Metadata, b: &std::fs::Metadata) -> bool {
    let mut same = a.len() == b.len() && a.modified().ok() == b.modified().ok();
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        same &= a.dev() == b.dev()
            && a.ino() == b.ino()
            && a.ctime_nsec() == b.ctime_nsec()
            && a.ctime() == b.ctime();
    }
    same
}

fn validate_native_capture_streaming(path: &Path, maximum_record: usize) -> std::io::Result<()> {
    use std::io::BufRead;

    use serde::Deserialize;
    let file = std::fs::File::open(path)?;
    let before = file.metadata()?;
    let input = NativeCaptureReader {
        outer: std::io::BufReader::with_capacity(65536, file),
        pending: std::io::Cursor::new(Vec::new()),
        maximum_record,
        records: 0,
        saw_stdout: false,
        last_stdout_byte: None,
    };
    let mut input = std::io::BufReader::with_capacity(65536, input);
    let mut records = 0;
    while !input.fill_buf()?.is_empty() {
        let mut line = NativeLine {
            input: &mut input,
            ended: false,
            depth: 0,
            quoted: false,
            escaped: false,
            number: Vec::new(),
            maximum_number: maximum_record,
        };
        let mut buffered = std::io::BufReader::with_capacity(65536, &mut line);
        let mut decoder = serde_json::Deserializer::from_reader(&mut buffered);
        serde::de::IgnoredAny::deserialize(&mut decoder)
            .map_err(|_| std::io::Error::other("Damaged native log capture"))?;
        decoder.end().map_err(|_| {
            std::io::Error::other("Multiple/invalid native JSON records on one line")
        })?;
        drop(decoder);
        drop(buffered);
        if !line.ended {
            return Err(std::io::Error::other("Incomplete native JSON record"));
        }
        records += 1;
    }
    if records == 0 {
        return Err(std::io::Error::other("Empty native log capture"));
    }
    let opened = input.get_ref().outer.get_ref().metadata()?;
    let named = std::fs::metadata(path)?;
    if !same_capture_version(&before, &opened) || !same_capture_version(&before, &named) {
        return Err(std::io::Error::other("Capture changed during validation"));
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

#[cfg(test)]
mod bounded_native_capture_tests {
    use std::io::Write;

    use super::*;

    struct FixtureRoot(PathBuf);
    impl Drop for FixtureRoot {
        fn drop(&mut self) {
            std::fs::remove_dir_all(&self.0).expect("remove only this synthetic fixture");
        }
    }
    fn fixture(chunks: &[&str]) -> (FixtureRoot, PathBuf) {
        let root = FixtureRoot(
            PathBuf::from(std::env::var_os("VK_CAPTURE_TEST_ROOT").expect("owned test RAM root"))
                .join(format!("capture-stream-test-{}", Uuid::new_v4())),
        );
        std::fs::create_dir(&root.0).unwrap();
        let path = root.0.join("capture.jsonl");
        let mut file = std::fs::File::create(&path).unwrap();
        for chunk in chunks {
            serde_json::to_writer(&mut file, &LogMsg::Stdout((*chunk).into())).unwrap();
            writeln!(file).unwrap();
        }
        (root, path)
    }

    #[test]
    fn streaming_total_exceeds_record_bound_without_raising_it() {
        let chunks = vec!["{\"ok\":true}\n"; 100];
        let (_root, path) = fixture(&chunks);
        assert!(path.metadata().unwrap().len() > 64);
        validate_native_capture_streaming(&path, 64).unwrap();
    }

    #[test]
    fn streaming_large_native_value_across_small_outer_records() {
        let (_root, path) = fixture(&["{\"body\":\"", &"a".repeat(200_000), "\"}\n"]);
        // Split the large outer record as a normal captured native pipe does.
        let file = std::fs::File::create(&path).unwrap();
        let mut file = std::io::BufWriter::new(file);
        let document = format!("{{\"body\":\"{}\"}}\n", "x".repeat(200_000));
        for chunk in document.as_bytes().chunks(512) {
            serde_json::to_writer(
                &mut file,
                &LogMsg::Stdout(std::str::from_utf8(chunk).unwrap().into()),
            )
            .unwrap();
            writeln!(file).unwrap();
        }
        file.flush().unwrap();
        validate_native_capture_streaming(&path, 1024).unwrap();
    }

    #[test]
    fn streaming_malformed_outer_refuses() {
        let (_root, path) = fixture(&["{}\n"]);
        std::fs::OpenOptions::new()
            .append(true)
            .open(&path)
            .unwrap()
            .write_all(b"BROKEN\n")
            .unwrap();
        assert!(validate_native_capture_streaming(&path, 1024).is_err());
    }

    #[test]
    fn streaming_malformed_native_refuses() {
        let (_root, path) = fixture(&["{bad}\n"]);
        assert!(validate_native_capture_streaming(&path, 1024).is_err());
    }

    #[test]
    fn streaming_partial_native_refuses() {
        let (_root, path) = fixture(&["{}"]);
        assert!(validate_native_capture_streaming(&path, 1024).is_err());
    }

    #[test]
    fn streaming_partial_outer_refuses() {
        let (_root, path) = fixture(&["{}\n"]);
        let f = std::fs::OpenOptions::new().write(true).open(&path).unwrap();
        f.set_len(f.metadata().unwrap().len() - 1).unwrap();
        assert!(validate_native_capture_streaming(&path, 1024).is_err());
    }

    #[test]
    fn streaming_native_line_boundary_remains_strict() {
        for value in ["{}{}\n", "{}\n\n", "{\n}\n"] {
            let (_root, path) = fixture(&[value]);
            assert!(
                validate_native_capture_streaming(&path, 1024).is_err(),
                "framing accepted"
            );
        }
    }

    #[test]
    fn streaming_outer_record_bound_remains_strict() {
        let (_root, path) = fixture(&[&format!("{{\"body\":\"{}\"}}\n", "x".repeat(1024))]);
        assert!(validate_native_capture_streaming(&path, 128).is_err());
    }

    #[test]
    fn streaming_unsupported_outer_refuses() {
        let (_root, path) = fixture(&["{}\n"]);
        std::fs::OpenOptions::new()
            .append(true)
            .open(&path)
            .unwrap()
            .write_all(b"\"Finished\"\n")
            .unwrap();
        assert!(validate_native_capture_streaming(&path, 1024).is_err());
    }

    #[tokio::test]
    async fn streaming_pending_writer_stays_unavailable() {
        let (_root, path) = fixture(&["{}\n"]);
        std::fs::write(
            path.with_extension("capture.json"),
            br#"{"capture_state":"pending"}"#,
        )
        .unwrap();
        assert!(validate_native_capture(&path, 1024).await.is_err());
        std::fs::write(
            path.with_extension("capture.json"),
            br#"{"capture_state":"closed"}"#,
        )
        .unwrap();
        validate_native_capture(&path, 1024).await.unwrap();
    }

    #[test]
    fn streaming_replaced_source_version_refuses() {
        let (_root, path) = fixture(&["{}\n"]);
        let old = path.metadata().unwrap();
        std::fs::write(path.with_extension("next"), b"other").unwrap();
        std::fs::rename(path.with_extension("next"), &path).unwrap();
        assert!(!same_capture_version(&old, &path.metadata().unwrap()));
    }

    #[test]
    fn streaming_preserves_original_recursion_and_number_semantics() {
        for document in [
            format!("{}0{}\n", "[".repeat(128), "]".repeat(128)),
            "{\"n\":1e400}\n".into(),
        ] {
            let (_root, path) = fixture(&[&document]);
            assert!(validate_native_capture_streaming(&path, 4096).is_err());
        }
        let (_root, path) = fixture(&["{\"text\":\"[{\\\"—\",\"n\":-1.25e2}\n"]);
        validate_native_capture_streaming(&path, 4096).unwrap();
    }

    #[test]
    #[ignore = "explicit admitted read-only retained-capture probe only"]
    fn streaming_actual_retained_capture() {
        let path = PathBuf::from(
            std::env::var_os("VK_NATIVE_CAPTURE_TEST_PATH")
                .expect("explicit readonly retained capture binding"),
        );
        validate_native_capture_streaming(&path, 32 * 1024 * 1024)
            .expect("full retained outer/native integrity");
    }
}
