//! Packed completed logs: bounded immutable gzip slices, shared per session.
use std::{
    collections::{HashSet, VecDeque},
    fs::File,
    io::{self, BufRead, BufReader, Cursor, Read, Seek, SeekFrom},
    path::{Path, PathBuf},
};

use flate2::bufread::GzDecoder;
use serde::Deserialize;
use sha2::{Digest, Sha256};

pub(crate) const MAGIC: &[u8] = b"VKLOGCAS2\n";
const PACK_MAGIC: &[u8] = b"VKLOGPACK1\n";
const MAX_PACK: u64 = 64 * 1024 * 1024;
const MAX_CHUNK: u64 = 256 * 1024;

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Chunk {
    sha256: String,
    bytes: u64,
    pack: usize,
    offset: u64,
    encoded_bytes: u64,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    version: u32,
    raw_bytes: u64,
    sha256: String,
    packs: Vec<String>,
    chunks: VecDeque<Chunk>,
}

fn invalid(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}

fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

struct Reader {
    directory: PathBuf,
    manifest: Manifest,
    handles: VecDeque<(usize, File)>,
    pending: Cursor<Vec<u8>>,
    digest: Sha256,
    remaining: u64,
    verified: bool,
    // Retain the original manifest inode for the entire lazy stream lifetime.
    // Declared last so object descriptors close before the manifest pin.
    _manifest: File,
}

impl Reader {
    fn object(&mut self, chunk: &Chunk) -> io::Result<Vec<u8>> {
        let mut file = match self.handles.iter().position(|(key, _)| *key == chunk.pack) {
            Some(index) => self.handles.remove(index).unwrap().1,
            None => {
                if self.handles.len() == 4 {
                    self.handles.pop_front();
                }
                let path = self
                    .directory
                    .join(format!("{}.pack", self.manifest.packs[chunk.pack]));
                let before = std::fs::symlink_metadata(&path)?;
                if !before.is_file()
                    || !(PACK_MAGIC.len() as u64..=MAX_PACK).contains(&before.len())
                {
                    return Err(invalid("Log archive pack must be a bounded regular file"));
                }
                let mut options = std::fs::OpenOptions::new();
                options.read(true);
                #[cfg(unix)]
                {
                    use std::os::unix::fs::OpenOptionsExt;
                    options.custom_flags(nix::libc::O_NOFOLLOW);
                }
                let mut file = options.open(path)?;
                let actual = file.metadata()?;
                if !actual.is_file() || actual.len() != before.len() {
                    return Err(invalid("Log archive pack changed during open"));
                }
                #[cfg(unix)]
                {
                    use std::os::unix::fs::MetadataExt;
                    if (actual.dev(), actual.ino()) != (before.dev(), before.ino()) {
                        return Err(invalid("Log archive pack identity changed"));
                    }
                }
                let mut header = [0; PACK_MAGIC.len()];
                file.read_exact(&mut header)?;
                if header != PACK_MAGIC {
                    return Err(invalid("Invalid log archive pack header"));
                }
                file
            }
        };
        if chunk.offset + chunk.encoded_bytes > file.metadata()?.len() {
            return Err(invalid("Log archive reference exceeds pack"));
        }
        file.seek(SeekFrom::Start(chunk.offset))?;
        let mut encoded = vec![0; chunk.encoded_bytes as usize];
        file.read_exact(&mut encoded)?;
        self.handles.push_back((chunk.pack, file));
        let mut decoder = GzDecoder::new(Cursor::new(encoded));
        let mut decoded = Vec::new();
        (&mut decoder)
            .take(chunk.bytes + 1)
            .read_to_end(&mut decoded)?;
        if decoded.len() as u64 != chunk.bytes
            || decoder.get_ref().position() != chunk.encoded_bytes
            || format!("{:x}", Sha256::digest(&decoded)) != chunk.sha256
        {
            return Err(invalid("Packed log object frame/hash/length mismatch"));
        }
        Ok(decoded)
    }
}

impl Read for Reader {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        if output.is_empty() {
            return Ok(0);
        }
        loop {
            let count = self.pending.read(output)?;
            if count != 0 {
                return Ok(count);
            }
            let Some(chunk) = self.manifest.chunks.front().cloned() else {
                if !self.verified {
                    if self.remaining != 0
                        || format!("{:x}", self.digest.clone().finalize()) != self.manifest.sha256
                    {
                        return Err(invalid("Packed log archive full length/hash mismatch"));
                    }
                    self.verified = true;
                }
                return Ok(0);
            };
            let bytes = self.object(&chunk)?;
            self.remaining = self
                .remaining
                .checked_sub(chunk.bytes)
                .ok_or_else(|| invalid("Packed log exceeds declared length"))?;
            self.digest.update(&bytes);
            self.pending = Cursor::new(bytes);
            self.manifest.chunks.pop_front();
        }
    }
}

pub(crate) fn open_buffered(
    path: &Path,
    mut input: BufReader<File>,
) -> io::Result<Box<dyn Read + Send>> {
    input.consume(MAGIC.len());
    let mut raw = Vec::new();
    (&mut input)
        .take(16 * 1024 * 1024 + 1)
        .read_to_end(&mut raw)?;
    if raw.len() > 16 * 1024 * 1024 {
        return Err(invalid("Packed log manifest exceeds bound"));
    }
    let manifest: Manifest =
        serde_json::from_slice(&raw).map_err(|_| invalid("Invalid packed log manifest JSON"))?;
    if manifest.version != 2
        || !valid_hash(&manifest.sha256)
        || manifest.packs.len() > 1024
        || manifest.packs.iter().any(|p| !valid_hash(p))
        || manifest.packs.iter().collect::<HashSet<_>>().len() != manifest.packs.len()
        || manifest.chunks.len() > 100_000
        || manifest.chunks.iter().any(|c| {
            !valid_hash(&c.sha256)
                || c.bytes == 0
                || c.bytes > MAX_CHUNK
                || c.pack >= manifest.packs.len()
                || c.offset < PACK_MAGIC.len() as u64
                || c.encoded_bytes == 0
                || c.encoded_bytes > MAX_CHUNK + 1024
                || c.offset
                    .checked_add(c.encoded_bytes)
                    .is_none_or(|end| end > MAX_PACK)
        })
        || manifest
            .chunks
            .iter()
            .try_fold(0u64, |n, c| n.checked_add(c.bytes))
            != Some(manifest.raw_bytes)
    {
        return Err(invalid("Invalid packed log manifest"));
    }
    let directory = path
        .parent()
        .ok_or_else(|| invalid("Packed log parent missing"))?
        .join(".log-packs");
    if !std::fs::symlink_metadata(&directory)?.is_dir() {
        return Err(invalid("Log pack store must be a directory"));
    }
    let remaining = manifest.raw_bytes;
    Ok(Box::new(Reader {
        _manifest: input.into_inner(),
        directory,
        manifest,
        remaining,
        handles: VecDeque::new(),
        pending: Cursor::new(Vec::new()),
        digest: Sha256::new(),
        verified: false,
    }))
}

#[cfg(test)]
mod tests {
    use std::io::Write;

    use flate2::{Compression, write::GzEncoder};
    use serde_json::{Value, json};
    use uuid::Uuid;

    use super::*;
    use crate::{execution_logs, log_archive, log_msg::LogMsg};

    struct Fixture(PathBuf);
    impl Drop for Fixture {
        fn drop(&mut self) {
            std::fs::remove_dir_all(&self.0).unwrap();
        }
    }
    fn fixture(raw: &[u8]) -> (Fixture, PathBuf, PathBuf) {
        let root = std::env::temp_dir().join(format!("vk-packed-test-{}", Uuid::new_v4()));
        std::fs::create_dir_all(root.join(".log-packs")).unwrap();
        let mut pack = PACK_MAGIC.to_vec();
        let mut chunks = Vec::new();
        for block in raw.chunks(7) {
            let mut encoder = GzEncoder::new(Vec::new(), Compression::fast());
            encoder.write_all(block).unwrap();
            let encoded = encoder.finish().unwrap();
            chunks.push(
                json!({"sha256":format!("{:x}",Sha256::digest(block)),"bytes":block.len(),
                "pack":0,"offset":pack.len(),"encoded_bytes":encoded.len()}),
            );
            pack.extend(encoded);
        }
        let key = format!("{:x}", Sha256::digest(&pack));
        let object = root.join(".log-packs").join(format!("{key}.pack"));
        std::fs::write(&object, pack).unwrap();
        let manifest = json!({"version":2,"raw_bytes":raw.len(),"sha256":format!("{:x}",Sha256::digest(raw)),
            "packs":[key],"chunks":chunks});
        let path = root.join("capture.jsonl");
        write_manifest(&path, &manifest);
        (Fixture(root), path, object)
    }
    fn write_manifest(path: &Path, manifest: &Value) {
        let mut data = MAGIC.to_vec();
        data.extend(serde_json::to_vec(manifest).unwrap());
        std::fs::write(path, data).unwrap();
    }
    fn read_manifest(path: &Path) -> Value {
        serde_json::from_slice(&std::fs::read(path).unwrap()[MAGIC.len()..]).unwrap()
    }
    fn raw() -> Vec<u8> {
        let mut data = Vec::new();
        for text in ["{\"reply\":\"readable — ✓\"}\n", "{\"delta\":true}\n"] {
            serde_json::to_writer(&mut data, &LogMsg::Stdout(text.into())).unwrap();
            data.push(b'\n');
        }
        data
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn packed_reader_prevents_retirement_after_manifest_replacement() {
        let original = raw();
        let (_root, path, _) = fixture(&original);
        log_archive::tests::assert_manifest_pinned_until_drop(&path, &original);
    }

    #[tokio::test]
    async fn packed_logs_preserve_real_readers_and_refuse_append() {
        let original = raw();
        let (_root, path, _) = fixture(&original);
        assert!(log_archive::is_archive(&path).unwrap());
        let text = execution_logs::read_execution_log_file(&path)
            .await
            .unwrap();
        assert_eq!(text.as_bytes(), original);
        let (bytes, messages) = execution_logs::read_execution_log_strict(&path, original.len())
            .await
            .unwrap();
        assert_eq!(bytes, original);
        assert_eq!(messages.len(), 2);
        execution_logs::validate_native_capture(&path, original.len())
            .await
            .unwrap();
        assert!(
            execution_logs::read_execution_log_strict(&path, original.len() - 1)
                .await
                .is_err()
        );
        assert!(execution_logs::ExecutionLogWriter::new(path).await.is_err());
    }

    #[test]
    fn packed_prefix_and_exact_full_hash_have_separate_acceptance() {
        let original = raw();
        let (_root, path, _) = fixture(&original);
        let mut manifest = read_manifest(&path);
        manifest["sha256"] = json!("0".repeat(64));
        write_manifest(&path, &manifest);
        let mut reader = log_archive::open(&path).unwrap();
        let mut prefix = [0; 3];
        reader.read_exact(&mut prefix).unwrap();
        assert_eq!(&prefix, &original[..3]);
        assert!(reader.read_to_end(&mut Vec::new()).is_err());
    }

    #[test]
    fn packed_invalid_references_and_corruption_fail_closed() {
        let (_root, path, object) = fixture(&raw());
        let original = read_manifest(&path);
        for (field, value) in [
            ("offset", json!(u64::MAX)),
            ("encoded_bytes", json!(0)),
            ("pack", json!(1)),
            ("bytes", json!(262145)),
        ] {
            let mut manifest = original.clone();
            manifest["chunks"][0][field] = value;
            write_manifest(&path, &manifest);
            assert!(log_archive::open(&path).is_err());
        }
        write_manifest(&path, &original);
        let pack = std::fs::read(&object).unwrap();
        std::fs::write(&object, &pack[..pack.len() - 1]).unwrap();
        assert!(
            log_archive::open(&path)
                .unwrap()
                .read_to_end(&mut Vec::new())
                .is_err()
        );
        std::fs::write(&object, b"wrong pack header").unwrap();
        assert!(
            log_archive::open(&path)
                .unwrap()
                .read_to_end(&mut Vec::new())
                .is_err()
        );
    }

    #[cfg(unix)]
    #[test]
    fn packed_symlink_and_directory_escape_are_rejected() {
        let (_root, path, object) = fixture(&raw());
        let saved = object.with_extension("saved");
        std::fs::rename(&object, &saved).unwrap();
        std::os::unix::fs::symlink(&saved, &object).unwrap();
        assert!(
            log_archive::open(&path)
                .unwrap()
                .read_to_end(&mut Vec::new())
                .is_err()
        );
        let mut manifest = read_manifest(&path);
        manifest["packs"][0] = json!("../escape");
        write_manifest(&path, &manifest);
        assert!(log_archive::open(&path).is_err());
    }
}
