//! Lossless completed-log storage. Manifests stay at the original JSONL path;
//! objects are shared only within its processes directory, never across sessions.
use std::{
    collections::VecDeque,
    fs::File,
    io::{self, BufRead, BufReader, Cursor, Read},
    path::{Path, PathBuf},
};

use flate2::read::GzDecoder;
use serde::Deserialize;
use sha2::{Digest, Sha256};

pub const MAGIC: &[u8] = b"VKLOGCAS1\n";
const MAX_MANIFEST: u64 = 16 * 1024 * 1024;
const MAX_CHUNK: u64 = 256 * 1024;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Chunk {
    sha256: String,
    bytes: u64,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    version: u32,
    raw_bytes: u64,
    sha256: String,
    chunks: VecDeque<Chunk>,
}

fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}

fn valid_hash(hash: &str) -> bool {
    hash.len() == 64
        && hash
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

pub fn is_archive(path: &Path) -> io::Result<bool> {
    let mut prefix = [0; 10];
    match File::open(path) {
        Ok(mut file) => Ok(file.read(&mut prefix)? == MAGIC.len() && prefix == MAGIC),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(false),
        Err(e) => Err(e),
    }
}

/// Authenticate each chunk before returning it. Check the full-stream length
/// and hash at EOF; prefix consumers retain their existing bounded reads.
struct ArchiveReader {
    directory: PathBuf,
    chunks: VecDeque<Chunk>,
    pending: Cursor<Vec<u8>>,
    expected_hash: String,
    digest: Sha256,
    remaining: u64,
    verified: bool,
}

impl Read for ArchiveReader {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        if output.is_empty() {
            return Ok(0);
        }
        loop {
            let count = self.pending.read(output)?;
            if count != 0 {
                return Ok(count);
            }
            let Some(chunk) = self.chunks.front() else {
                if !self.verified {
                    if self.remaining != 0
                        || format!("{:x}", self.digest.clone().finalize()) != self.expected_hash
                    {
                        return Err(invalid("Log archive length/hash mismatch"));
                    }
                    self.verified = true;
                }
                return Ok(0);
            };
            let path = self.directory.join(format!("{}.gz", chunk.sha256));
            if !std::fs::symlink_metadata(&path)?.is_file() {
                return Err(invalid("Log archive object must be a regular file"));
            }
            let file = File::open(path)?;
            if file.metadata()?.len() > MAX_CHUNK + 1024 {
                return Err(invalid("Log archive object exceeds bound"));
            }
            let mut bytes = Vec::new();
            GzDecoder::new(file)
                .take(chunk.bytes + 1)
                .read_to_end(&mut bytes)?;
            if bytes.len() as u64 != chunk.bytes
                || format!("{:x}", Sha256::digest(&bytes)) != chunk.sha256
            {
                return Err(invalid("Log archive object length/hash mismatch"));
            }
            self.remaining = self
                .remaining
                .checked_sub(chunk.bytes)
                .ok_or_else(|| invalid("Log archive exceeds declared length"))?;
            self.digest.update(&bytes);
            self.pending = Cursor::new(bytes);
            self.chunks.pop_front();
        }
    }
}

pub fn open(path: &Path) -> io::Result<Box<dyn Read + Send>> {
    open_file(path, File::open(path)?)
}

/// Accept the caller's descriptor so integrity readers keep their inode binding.
pub fn open_file(path: &Path, file: File) -> io::Result<Box<dyn Read + Send>> {
    let mut input = BufReader::new(file);
    if !input.fill_buf()?.starts_with(MAGIC) {
        return Ok(Box::new(input));
    }
    input.consume(MAGIC.len());
    let mut bytes = Vec::new();
    input.take(MAX_MANIFEST + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_MANIFEST {
        return Err(invalid("Log archive manifest exceeds bound"));
    }
    let manifest: Manifest =
        serde_json::from_slice(&bytes).map_err(|_| invalid("Invalid log archive manifest JSON"))?;
    if manifest.version != 1
        || !valid_hash(&manifest.sha256)
        || manifest.chunks.len() > 100_000
        || manifest
            .chunks
            .iter()
            .any(|c| c.bytes == 0 || c.bytes > MAX_CHUNK || !valid_hash(&c.sha256))
        || manifest
            .chunks
            .iter()
            .try_fold(0u64, |n, c| n.checked_add(c.bytes))
            != Some(manifest.raw_bytes)
    {
        return Err(invalid("Invalid log archive manifest"));
    }
    let directory = path
        .parent()
        .ok_or_else(|| invalid("Log archive parent missing"))?
        .join(".log-objects");
    if !std::fs::symlink_metadata(&directory)?.is_dir() {
        return Err(invalid("Log archive store must be a directory"));
    }
    Ok(Box::new(ArchiveReader {
        directory,
        chunks: manifest.chunks,
        pending: Cursor::new(Vec::new()),
        expected_hash: manifest.sha256,
        digest: Sha256::new(),
        remaining: manifest.raw_bytes,
        verified: false,
    }))
}

#[cfg(test)]
mod tests {
    use std::io::Write;

    use flate2::{Compression, write::GzEncoder};
    use futures::StreamExt;
    use serde_json::json;
    use uuid::Uuid;

    use super::*;
    use crate::{execution_logs, log_msg::LogMsg};

    struct Fixture(PathBuf);
    impl Drop for Fixture {
        fn drop(&mut self) {
            std::fs::remove_dir_all(&self.0).unwrap();
        }
    }
    fn fixture(raw: &[u8], cut: usize) -> (Fixture, PathBuf) {
        let root = std::env::temp_dir().join(format!("vk-log-cas-test-{}", Uuid::new_v4()));
        let objects = root.join(".log-objects");
        std::fs::create_dir_all(&objects).unwrap();
        let mut chunks = Vec::new();
        for block in raw.chunks(cut) {
            let hash = format!("{:x}", Sha256::digest(block));
            let mut encoder = GzEncoder::new(Vec::new(), Compression::fast());
            encoder.write_all(block).unwrap();
            std::fs::write(
                objects.join(format!("{hash}.gz")),
                encoder.finish().unwrap(),
            )
            .unwrap();
            chunks.push(json!({"sha256":hash,"bytes":block.len()}));
        }
        let path = root.join("capture.jsonl");
        let manifest = json!({"version":1,"raw_bytes":raw.len(),
            "sha256":format!("{:x}",Sha256::digest(raw)),"chunks":chunks});
        let mut data = MAGIC.to_vec();
        data.extend(serde_json::to_vec(&manifest).unwrap());
        std::fs::write(&path, data).unwrap();
        (Fixture(root), path)
    }
    fn raw() -> Vec<u8> {
        let mut bytes = Vec::new();
        for text in ["{\"reply\":\"readable — ✓\"}\n", "{\"delta\":true}\n"] {
            serde_json::to_writer(&mut bytes, &LogMsg::Stdout(text.into())).unwrap();
            bytes.push(b'\n');
        }
        bytes
    }

    #[tokio::test]
    async fn all_readers_preserve_exact_bytes_and_capture_semantics() {
        let raw = raw();
        // Split UTF-8, escaped strings and JSONL records across objects.
        let (_root, path) = fixture(&raw, 7);
        assert_eq!(
            execution_logs::read_execution_log_file(&path)
                .await
                .unwrap()
                .as_bytes(),
            raw
        );
        let (bytes, messages) = execution_logs::read_execution_log_strict(&path, 4096)
            .await
            .unwrap();
        assert_eq!(bytes, raw);
        assert_eq!(messages.len(), 2);
        let mut stream = execution_logs::stream_execution_log_file(&path)
            .await
            .unwrap();
        let mut streamed = Vec::new();
        while let Some(line) = stream.next().await {
            streamed.extend(line.unwrap().as_bytes());
            streamed.push(b'\n');
        }
        assert_eq!(streamed, raw);
        execution_logs::validate_native_capture(&path, 4096)
            .await
            .unwrap();
        std::fs::write(
            path.with_extension("capture.json"),
            b"{\"capture_state\":\"pending\"}",
        )
        .unwrap();
        assert!(
            execution_logs::validate_native_capture(&path, 4096)
                .await
                .is_err()
        );
        assert!(execution_logs::ExecutionLogWriter::new(path).await.is_err());
    }

    #[tokio::test]
    async fn reconstructed_size_limits_are_not_manifest_size_limits() {
        let raw = raw();
        let (_root, path) = fixture(&raw, 7);
        assert!(
            execution_logs::read_execution_log_strict(&path, raw.len() - 1)
                .await
                .is_err()
        );
        let (_root, path) = fixture(b"{\"Stdout\":\"partial\"}", 7);
        assert!(
            execution_logs::read_execution_log_strict(&path, 4096)
                .await
                .is_err()
        );
    }

    #[tokio::test]
    async fn corruption_and_missing_objects_reach_every_reader() {
        let (_root, path) = fixture(&raw(), 256);
        let object = std::fs::read_dir(path.parent().unwrap().join(".log-objects"))
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        std::fs::write(&object, b"corrupt").unwrap();
        assert!(
            execution_logs::read_execution_log_file(&path)
                .await
                .is_err()
        );
        assert!(
            execution_logs::read_execution_log_strict(&path, 4096)
                .await
                .is_err()
        );
        assert!(
            execution_logs::validate_native_capture(&path, 4096)
                .await
                .is_err()
        );
        let mut stream = execution_logs::stream_execution_log_file(&path)
            .await
            .unwrap();
        assert!(stream.next().await.unwrap().is_err());
        std::fs::remove_file(object).unwrap();
        assert!(
            execution_logs::read_execution_log_file(&path)
                .await
                .is_err()
        );
    }

    #[test]
    fn invalid_references_and_full_hash_fail_closed() {
        let (_root, path) = fixture(&raw(), 256);
        let bytes = std::fs::read(&path).unwrap();
        let mut manifest: serde_json::Value =
            serde_json::from_slice(&bytes[MAGIC.len()..]).unwrap();
        manifest["sha256"] = json!("0".repeat(64));
        let mut changed = MAGIC.to_vec();
        changed.extend(serde_json::to_vec(&manifest).unwrap());
        std::fs::write(&path, &changed).unwrap();
        assert!(open(&path).unwrap().read_to_end(&mut Vec::new()).is_err());
        manifest["chunks"][0]["sha256"] = json!("../outside");
        changed.truncate(MAGIC.len());
        changed.extend(serde_json::to_vec(&manifest).unwrap());
        std::fs::write(&path, &changed).unwrap();
        assert!(open(&path).is_err());
    }

    #[tokio::test]
    async fn legacy_raw_and_new_capture_still_work() {
        let (root, path) = fixture(&raw(), 256);
        let legacy = root.0.join("legacy.jsonl");
        std::fs::write(&legacy, raw()).unwrap();
        assert!(!is_archive(&legacy).unwrap());
        assert_eq!(
            execution_logs::read_execution_log_file(&legacy)
                .await
                .unwrap()
                .as_bytes(),
            raw()
        );
        let new = root.0.join("new.jsonl");
        let mut writer = execution_logs::ExecutionLogWriter::new(new.clone())
            .await
            .unwrap();
        writer
            .append_jsonl_line(std::str::from_utf8(&raw()).unwrap())
            .await
            .unwrap();
        writer.finish_for_review().await.unwrap();
        execution_logs::validate_native_capture(&new, 4096)
            .await
            .unwrap();
        assert!(is_archive(&path).unwrap());
    }

    #[cfg(unix)]
    #[test]
    fn symlink_objects_are_rejected() {
        let (_root, path) = fixture(&raw(), 256);
        let object = std::fs::read_dir(path.parent().unwrap().join(".log-objects"))
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        let other = object.with_extension("moved");
        std::fs::rename(&object, &other).unwrap();
        std::os::unix::fs::symlink(other, object).unwrap();
        assert!(open(&path).unwrap().read_to_end(&mut Vec::new()).is_err());
    }
}
