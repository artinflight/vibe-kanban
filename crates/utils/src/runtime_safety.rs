//! Side-effect-free server invocation and operator-pinned runtime validation.
//! An identity receipt is explicit deployment input, never discovered or enrolled
//! by startup. Unix device/inode pins survive SQLite writes, but deliberately
//! reject database replacement, recovery placement and a different namespace.
use std::{ffi::OsString, io, path::Path};
#[cfg(unix)]
use std::{fs, io::Read};

#[derive(Debug)]
pub struct RuntimeIdentity {
    pub database: std::path::PathBuf,
    pub dataset_id: String,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ServerInvocation {
    Serve,
    Help,
    Version,
    BuildInfo,
}

pub fn parse_server_invocation(
    args: impl IntoIterator<Item = OsString>,
) -> io::Result<ServerInvocation> {
    let args: Vec<_> = args.into_iter().collect();
    match args.as_slice() {
        [] => Ok(ServerInvocation::Serve),
        [arg] if arg == "--help" || arg == "-h" => Ok(ServerInvocation::Help),
        [arg] if arg == "--version" || arg == "-V" => Ok(ServerInvocation::Version),
        [arg] if arg == "--build-info" => Ok(ServerInvocation::BuildInfo),
        _ => Err(denied("unsupported server invocation; use --help")),
    }
}

fn denied(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::PermissionDenied, message)
}

#[cfg(unix)]
fn object_id(metadata: &fs::Metadata) -> String {
    use std::os::unix::fs::MetadataExt;
    format!("{}:{}", metadata.dev(), metadata.ino())
}

/// Validate before any stateful initialization. Missing paths are never created.
/// The receipt binds the *selected* database and configured root, rather than
/// treating an environment override or an empty legacy database as ownership.
#[cfg(unix)]
pub fn validate_runtime_identity(
    receipt: &Path,
    database: &Path,
    workspace_root: &Path,
) -> io::Result<RuntimeIdentity> {
    let pin_metadata = fs::symlink_metadata(receipt)?;
    if !pin_metadata.is_file() || pin_metadata.len() > 16384 {
        return Err(denied(
            "runtime receipt must be a small regular file, not a link",
        ));
    }
    let text = fs::read_to_string(receipt)?;
    let lines: Vec<_> = text.lines().collect();
    if lines.len() != 6 || lines[0] != "vk-runtime-identity-v1" {
        return Err(denied("invalid runtime identity receipt"));
    }
    let value = |index: usize, key: &str| -> io::Result<&str> {
        lines[index]
            .strip_prefix(key)
            .filter(|v| !v.is_empty())
            .ok_or_else(|| denied("missing runtime identity field"))
    };
    let expected_database = value(1, "database=")?;
    let expected_database_id = value(2, "database_id=")?;
    let expected_root = value(3, "workspace_root=")?;
    let expected_root_id = value(4, "workspace_root_id=")?;
    let dataset_id = value(5, "dataset_id=")?;
    if dataset_id.len() != 32 || !dataset_id.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(denied("missing or invalid dataset identity"));
    }
    if !database.is_absolute() || !workspace_root.is_absolute() {
        return Err(denied(
            "selected database and workspace root must be absolute",
        ));
    }
    let database = database.canonicalize()?;
    let workspace_root = workspace_root.canonicalize()?;
    let mut file = fs::File::open(&database)?;
    let db_metadata = file.metadata()?;
    let root_metadata = fs::metadata(&workspace_root)?;
    if database.to_str() != Some(expected_database)
        || workspace_root.to_str() != Some(expected_root)
        || !db_metadata.is_file()
        || db_metadata.len() < 512
        || !root_metadata.is_dir()
        || object_id(&db_metadata) != expected_database_id
        || object_id(&root_metadata) != expected_root_id
    {
        return Err(denied(
            "selected database/workspace identity does not match the pinned runtime",
        ));
    }
    let mut header = [0; 16];
    file.read_exact(&mut header)?;
    if &header != b"SQLite format 3\0" {
        return Err(denied("selected database is empty or is not SQLite"));
    }
    Ok(RuntimeIdentity {
        database,
        dataset_id: dataset_id.to_owned(),
    })
}

// No fallback to weaker path-only authority on platforms lacking Unix identity.
#[cfg(not(unix))]
pub fn validate_runtime_identity(
    _receipt: &Path,
    _database: &Path,
    _workspace_root: &Path,
) -> io::Result<RuntimeIdentity> {
    Err(denied(
        "runtime identity v1 requires Unix filesystem identity",
    ))
}

#[cfg(all(test, unix))]
mod tests {
    use std::{
        os::unix::fs::{PermissionsExt, symlink},
        sync::atomic::{AtomicUsize, Ordering},
    };

    use super::*;
    static NEXT: AtomicUsize = AtomicUsize::new(0);

    struct Fixture {
        path: std::path::PathBuf,
    }
    impl Fixture {
        fn new() -> Self {
            let base = std::env::var_os("VK_SAFETY_TEST_ROOT")
                .unwrap_or_else(|| std::env::temp_dir().into_os_string());
            let path = std::path::PathBuf::from(base).join(format!(
                "runtime-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&path).unwrap();
            fs::create_dir(path.join("workspaces")).unwrap();
            fs::write(path.join("workspaces/sentinel"), b"surviving newer work").unwrap();
            let mut db = vec![0; 512];
            db[..16].copy_from_slice(b"SQLite format 3\0");
            fs::write(path.join("db.sqlite"), db).unwrap();
            let fixture = Self { path };
            fixture.pin();
            fixture
        }
        fn pin(&self) {
            let db = self.path.join("db.sqlite");
            let root = self.path.join("workspaces");
            fs::write(self.path.join("identity"), format!("vk-runtime-identity-v1\ndatabase={}\ndatabase_id={}\nworkspace_root={}\nworkspace_root_id={}\ndataset_id=0123456789abcdef0123456789abcdef\n", db.display(), object_id(&fs::metadata(&db).unwrap()), root.display(), object_id(&fs::metadata(&root).unwrap()))).unwrap();
        }
        fn validate(&self) -> io::Result<()> {
            validate_runtime_identity(
                &self.path.join("identity"),
                &self.path.join("db.sqlite"),
                &self.path.join("workspaces"),
            )
            .map(|_| ())
        }
        fn sentinel(&self) {
            assert_eq!(
                fs::read(self.path.join("workspaces/sentinel")).unwrap(),
                b"surviving newer work"
            );
            assert!(
                fs::metadata(self.path.join("workspaces/sentinel"))
                    .unwrap()
                    .permissions()
                    .mode()
                    & 0o600
                    != 0
            );
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.path).unwrap();
        }
    }

    #[test]
    fn exact_invocation_only() {
        for (args, expected) in [
            (vec![], ServerInvocation::Serve),
            (vec!["--help"], ServerInvocation::Help),
            (vec!["--version"], ServerInvocation::Version),
            (vec!["--build-info"], ServerInvocation::BuildInfo),
        ] {
            assert_eq!(
                parse_server_invocation(args.into_iter().map(OsString::from)).unwrap(),
                expected
            );
        }
        for args in [
            vec!["--vk-build-info"],
            vec!["--capacity-build-info"],
            vec!["--build-info", "--vk-build-info"],
            vec!["--help", "x"],
            vec!["--"],
            vec![""],
            vec!["serve"],
        ] {
            assert!(parse_server_invocation(args.into_iter().map(OsString::from)).is_err());
        }
        use std::os::unix::ffi::OsStringExt;
        assert!(parse_server_invocation([OsString::from_vec(vec![0xff])]).is_err());
    }
    #[test]
    fn correct_identity_remains_usable_after_sqlite_writes() {
        let f = Fixture::new();
        assert!(f.validate().is_ok());
        let mut data = fs::read(f.path.join("db.sqlite")).unwrap();
        data[300] = 42;
        fs::write(f.path.join("db.sqlite"), data).unwrap();
        assert!(f.validate().is_ok());
        f.sentinel();
    }
    #[test]
    fn empty_missing_or_invalid_receipt_fails_closed() {
        let f = Fixture::new();
        for text in [
            "",
            "vk-runtime-identity-v1",
            "vk-runtime-identity-v1\ndatabase=\ndatabase_id=\nworkspace_root=\nworkspace_root_id=\n",
        ] {
            fs::write(f.path.join("identity"), text).unwrap();
            assert!(f.validate().is_err());
            f.sentinel();
        }
        fs::remove_file(f.path.join("identity")).unwrap();
        assert!(f.validate().is_err());
        f.sentinel();
    }
    #[test]
    fn wrong_empty_replaced_or_missing_database_fails_closed() {
        let f = Fixture::new();
        let wrong = f.path.join("legacy.sqlite");
        fs::copy(f.path.join("db.sqlite"), &wrong).unwrap();
        assert!(
            validate_runtime_identity(&f.path.join("identity"), &wrong, &f.path.join("workspaces"))
                .is_err()
        );
        fs::write(f.path.join("db.sqlite"), b"").unwrap();
        assert!(f.validate().is_err());
        fs::remove_file(f.path.join("db.sqlite")).unwrap();
        assert!(f.validate().is_err());
        fs::rename(wrong, f.path.join("db.sqlite")).unwrap();
        assert!(f.validate().is_err());
        f.sentinel();
    }
    #[test]
    fn missing_and_invalid_dataset_pin_fails_closed() {
        let f = Fixture::new();
        let valid = fs::read_to_string(f.path.join("identity")).unwrap();
        for bad in ["", "dataset_id=\n", "dataset_id=wrong\n"] {
            let text = valid.lines().take(5).collect::<Vec<_>>().join("\n") + "\n" + bad;
            fs::write(f.path.join("identity"), text).unwrap();
            assert!(f.validate().is_err());
            f.sentinel();
        }
    }

    #[test]
    fn wrong_root_and_link_receipt_fail_closed() {
        let f = Fixture::new();
        let other = f.path.join("other");
        fs::create_dir(&other).unwrap();
        assert!(
            validate_runtime_identity(&f.path.join("identity"), &f.path.join("db.sqlite"), &other)
                .is_err()
        );
        fs::rename(f.path.join("identity"), f.path.join("saved")).unwrap();
        symlink(f.path.join("saved"), f.path.join("identity")).unwrap();
        assert!(f.validate().is_err());
        f.sentinel();
    }
}
