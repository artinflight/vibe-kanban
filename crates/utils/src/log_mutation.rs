//! Cross-process exclusion for one execution log and its capture/recovery sidecars.
//! Protocol 1 uses Linux flock on a permanent sibling `<execution>.mutation.lock`.
//! Never unlink a lock: replacing it would create two independent lock domains.
use std::{
    fs::{self, File, OpenOptions},
    io,
    path::{Path, PathBuf},
};

pub const PROTOCOL: u32 = if cfg!(target_os = "linux") { 1 } else { 0 };

#[derive(Debug)]
pub struct LogMutationGuard {
    file: File,
    path: PathBuf,
}

impl LogMutationGuard {
    /// Nonblocking acquisition. Async callers retry without occupying a runtime
    /// thread; cancellation leaves no worker behind waiting to acquire the lock.
    pub fn try_acquire(log: &Path) -> io::Result<Self> {
        let path = log.with_extension("mutation.lock");
        let mut options = OpenOptions::new();
        options.read(true).write(true).create(true).truncate(false);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
            #[cfg(target_os = "linux")]
            // Linux O_NOFOLLOW. No new dependency for this OS-specific protocol.
            options.custom_flags(0o400000);
        }
        let file = options.open(&path)?;
        let guard = Self { file, path };
        guard.check()?;
        guard.file.try_lock().map_err(|e| match e {
            std::fs::TryLockError::WouldBlock => io::ErrorKind::WouldBlock.into(),
            std::fs::TryLockError::Error(error) => error,
        })?;
        guard.check()?;
        Ok(guard)
    }

    pub fn check(&self) -> io::Result<()> {
        let named = fs::symlink_metadata(&self.path)?;
        let opened = self.file.metadata()?;
        if !named.is_file() || !opened.is_file() {
            return Err(io::Error::other("Log mutation lock is not a regular file"));
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            if (named.dev(), named.ino()) != (opened.dev(), opened.ino())
                || opened.nlink() != 1
                || opened.mode() & 0o022 != 0
            {
                return Err(io::Error::other("Log mutation lock changed or is shared"));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use std::{
        io::Write,
        sync::atomic::{AtomicUsize, Ordering},
    };

    use super::*;
    static NEXT: AtomicUsize = AtomicUsize::new(0);
    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let p = std::env::temp_dir().join(format!(
                "log-mutation-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&p).unwrap();
            Self(p)
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }
    #[test]
    fn same_execution_excludes_while_other_execution_and_readers_continue() {
        let f = Fixture::new();
        let a = f.0.join("a.jsonl");
        let b = f.0.join("b.jsonl");
        fs::write(&a, b"history").unwrap();
        let held = LogMutationGuard::try_acquire(&a).unwrap();
        assert_eq!(
            LogMutationGuard::try_acquire(&a).unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        let _other = LogMutationGuard::try_acquire(&b).unwrap();
        assert_eq!(fs::read(&a).unwrap(), b"history");
        drop(held);
        let _again = LogMutationGuard::try_acquire(&a).unwrap();
    }
    #[test]
    fn atomic_log_replacement_does_not_replace_the_lock() {
        let f = Fixture::new();
        let log = f.0.join("a.jsonl");
        fs::write(&log, b"raw").unwrap();
        let held = LogMutationGuard::try_acquire(&log).unwrap();
        let mut old_reader = File::open(&log).unwrap();
        let next = f.0.join("next");
        fs::write(&next, b"archive").unwrap();
        fs::rename(next, &log).unwrap();
        held.check().unwrap();
        assert_eq!(
            LogMutationGuard::try_acquire(&log).unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        let mut old = Vec::new();
        std::io::Read::read_to_end(&mut old_reader, &mut old).unwrap();
        assert_eq!(old, b"raw");
        assert_eq!(fs::read(log).unwrap(), b"archive");
    }
    #[cfg(unix)]
    #[test]
    fn aliases_and_foreign_replacements_fail_closed() {
        use std::os::unix::fs::symlink;
        let f = Fixture::new();
        let log = f.0.join("a.jsonl");
        let lock = log.with_extension("mutation.lock");
        let other = f.0.join("other");
        fs::write(&other, b"untouched").unwrap();
        symlink(&other, &lock).unwrap();
        assert!(LogMutationGuard::try_acquire(&log).is_err());
        fs::remove_file(&lock).unwrap();
        fs::hard_link(&other, &lock).unwrap();
        assert!(LogMutationGuard::try_acquire(&log).is_err());
        fs::remove_file(&lock).unwrap();
        let held = LogMutationGuard::try_acquire(&log).unwrap();
        fs::rename(&other, &lock).unwrap();
        assert!(held.check().is_err());
        assert_eq!(fs::read(lock).unwrap(), b"untouched");
    }
    #[test]
    fn lock_drop_keeps_permanent_inode() {
        let f = Fixture::new();
        let log = f.0.join("a.jsonl");
        let held = LogMutationGuard::try_acquire(&log).unwrap();
        let mut lock = OpenOptions::new()
            .append(true)
            .open(log.with_extension("mutation.lock"))
            .unwrap();
        lock.write_all(b"identity sentinel").unwrap();
        drop(held);
        let _again = LogMutationGuard::try_acquire(&log).unwrap();
        assert_eq!(
            fs::read(log.with_extension("mutation.lock")).unwrap(),
            b"identity sentinel"
        );
    }
}
