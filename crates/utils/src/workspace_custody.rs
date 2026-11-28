//! Cross-process workspace custody shared with scripts/workspace-archive/custody.py.
//! Permanent lock inodes live outside payload roots. Hold shared guards for the
//! complete reader/admission lifetime; the mover takes exclusive custody.
use std::{
    fs::{self, File, OpenOptions},
    io,
    path::{Path, PathBuf},
};

pub const PROTOCOL: u32 = if cfg!(target_os = "linux") { 1 } else { 0 };

#[derive(Debug)]
pub struct WorkspaceCustody {
    file: File,
    path: PathBuf,
    root: PathBuf,
    root_identity: (u64, u64),
}

impl WorkspaceCustody {
    #[cfg(target_os = "linux")]
    pub fn try_acquire(root: &Path, workspace: uuid::Uuid, exclusive: bool) -> io::Result<Self> {
        use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
        let uid = fs::metadata("/proc/self")?.uid();
        let metadata = fs::symlink_metadata(root)?;
        if !root.is_absolute()
            || root.canonicalize()? != root
            || !metadata.is_dir()
            || metadata.uid() != uid
            || metadata.mode() & 0o077 != 0
        {
            return Err(io::Error::other(
                "Private canonical workspace custody root required",
            ));
        }
        let path = root.join(format!("{workspace}.lock"));
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(0o400000)
            .open(&path)?;
        let guard = Self {
            file,
            path,
            root: root.into(),
            root_identity: (metadata.dev(), metadata.ino()),
        };
        guard.check()?;
        let result = if exclusive {
            guard.file.try_lock()
        } else {
            guard.file.try_lock_shared()
        };
        result.map_err(|error| match error {
            std::fs::TryLockError::WouldBlock => io::ErrorKind::WouldBlock.into(),
            std::fs::TryLockError::Error(error) => error,
        })?;
        guard.check()?;
        Ok(guard)
    }

    #[cfg(not(target_os = "linux"))]
    pub fn try_acquire(_root: &Path, _workspace: uuid::Uuid, _exclusive: bool) -> io::Result<Self> {
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "Workspace archive custody requires qualified Linux flock",
        ))
    }

    pub fn check(&self) -> io::Result<()> {
        let root = fs::symlink_metadata(&self.root)?;
        let named = fs::symlink_metadata(&self.path)?;
        let opened = self.file.metadata()?;
        if !root.is_dir()
            || !named.is_file()
            || !opened.is_file()
            || self.root.canonicalize()? != self.root
        {
            return Err(io::Error::other("Workspace custody path changed"));
        }
        #[cfg(target_os = "linux")]
        {
            use std::os::unix::fs::MetadataExt;
            let uid = fs::metadata("/proc/self")?.uid();
            if (root.dev(), root.ino()) != self.root_identity
                || root.uid() != uid
                || root.mode() & 0o077 != 0
                || (named.dev(), named.ino()) != (opened.dev(), opened.ino())
                || opened.nlink() != 1
                || opened.uid() != uid
                || opened.mode() & 0o077 != 0
            {
                return Err(io::Error::other(
                    "Workspace custody identity or ownership changed",
                ));
            }
        }
        Ok(())
    }
}

impl Drop for WorkspaceCustody {
    fn drop(&mut self) {
        // An unrelated concurrent fork can briefly inherit this open-file
        // description before exec closes it. Release custody at the owner's
        // actual lifetime boundary instead of waiting for that child to exec.
        let _ = self.file.unlock();
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use std::os::unix::fs::{MetadataExt, PermissionsExt};

    use super::*;

    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let path =
                std::env::temp_dir().join(format!("vk-workspace-custody-{}", uuid::Uuid::new_v4()));
            fs::create_dir(&path).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
            Self(path)
        }
        fn path(&self) -> &Path {
            &self.0
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }

    #[test]
    fn shared_readers_exclude_mover_but_not_other_workspaces() {
        let folder = Fixture::new();
        fs::set_permissions(folder.path(), fs::Permissions::from_mode(0o700)).unwrap();
        let id = uuid::Uuid::new_v4();
        let a = WorkspaceCustody::try_acquire(folder.path(), id, false).unwrap();
        let b = WorkspaceCustody::try_acquire(folder.path(), id, false).unwrap();
        assert_eq!(
            WorkspaceCustody::try_acquire(folder.path(), id, true)
                .unwrap_err()
                .kind(),
            io::ErrorKind::WouldBlock
        );
        let _other =
            WorkspaceCustody::try_acquire(folder.path(), uuid::Uuid::new_v4(), true).unwrap();
        let inode = fs::metadata(folder.path().join(format!("{id}.lock")))
            .unwrap()
            .ino();
        drop((a, b));
        let exclusive = WorkspaceCustody::try_acquire(folder.path(), id, true).unwrap();
        assert_eq!(exclusive.file.metadata().unwrap().ino(), inode);
        assert_eq!(
            WorkspaceCustody::try_acquire(folder.path(), id, false)
                .unwrap_err()
                .kind(),
            io::ErrorKind::WouldBlock
        );
    }

    #[test]
    fn python_and_rust_share_the_same_kernel_lock() {
        let folder = Fixture::new();
        fs::set_permissions(folder.path(), fs::Permissions::from_mode(0o700)).unwrap();
        let id = uuid::Uuid::new_v4();
        let guard = WorkspaceCustody::try_acquire(folder.path(), id, false).unwrap();
        let path = folder.path().join(format!("{id}.lock"));
        let script = "import fcntl,sys\nf=open(sys.argv[1], 'r+')\ntry: fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(23)\n";
        let run = || {
            std::process::Command::new("python3")
                .args(["-c", script])
                .arg(&path)
                .status()
                .unwrap()
                .code()
        };
        assert_eq!(run(), Some(23));
        drop(guard);
        assert_eq!(run(), Some(0));
    }
}
