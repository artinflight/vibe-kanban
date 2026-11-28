//! Pinned physical lifecycle driver and shared reader custody. No restoration
//! runs under global executor admission, and a protected reader never writes SQL.
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::{Arc, Mutex, OnceLock, Weak},
};

use serde::Deserialize;
use sha2::{Digest, Sha256};
use sqlx::{
    SqlitePool,
    sqlite::{SqliteConnectOptions, SqlitePoolOptions},
};
use tokio::{io::AsyncReadExt, process::Command};
use utils::workspace_custody::WorkspaceCustody;
use uuid::Uuid;

#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Writer,
    Reader,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Configuration {
    pub format: String,
    pub role: Role,
    pub database: PathBuf,
    pub custody_root: PathBuf,
    pub python: PathBuf,
    pub driver: PathBuf,
    pub driver_sha256: String,
    pub driver_configuration: PathBuf,
    pub driver_configuration_sha256: String,
    pub writer_url: Option<String>,
}

pub struct Runtime {
    pub config: Configuration,
    pub catalog: SqlitePool,
    owners: Mutex<HashMap<Uuid, Weak<tokio::sync::Mutex<()>>>>,
}

#[cfg(target_os = "linux")]
fn pinned(path: &Path, expected: Option<&str>) -> anyhow::Result<Vec<u8>> {
    use std::os::unix::fs::MetadataExt;
    let metadata = std::fs::symlink_metadata(path)?;
    if !path.is_absolute()
        || path.canonicalize()? != path
        || !metadata.is_file()
        || metadata.uid() != std::fs::metadata("/proc/self")?.uid()
        || metadata.nlink() != 1
        || metadata.mode() & 0o022 != 0
    {
        anyhow::bail!("Canonical owned archive configuration/source required");
    }
    let bytes = std::fs::read(path)?;
    let after = std::fs::symlink_metadata(path)?;
    if (
        metadata.dev(),
        metadata.ino(),
        metadata.len(),
        metadata.mtime(),
        metadata.mtime_nsec(),
        metadata.ctime(),
        metadata.ctime_nsec(),
    ) != (
        after.dev(),
        after.ino(),
        after.len(),
        after.mtime(),
        after.mtime_nsec(),
        after.ctime(),
        after.ctime_nsec(),
    ) || expected.is_some_and(|sha| format!("{:x}", Sha256::digest(&bytes)) != sha)
    {
        anyhow::bail!("Pinned archive configuration/source changed");
    }
    Ok(bytes)
}

#[cfg(not(target_os = "linux"))]
fn pinned(_path: &Path, _expected: Option<&str>) -> anyhow::Result<Vec<u8>> {
    anyhow::bail!("Workspace archive runtime requires qualified Linux custody")
}

pub fn configured() -> anyhow::Result<Option<Arc<Runtime>>> {
    static RUNTIME: OnceLock<Result<Option<Arc<Runtime>>, String>> = OnceLock::new();
    RUNTIME
        .get_or_init(|| {
            let Some(path) = std::env::var_os("VK_WORKSPACE_ARCHIVE_CONFIG") else {
                return Ok(None);
            };
            load(Path::new(&path))
                .map(|r| Some(Arc::new(r)))
                .map_err(|e| e.to_string())
        })
        .clone()
        .map_err(anyhow::Error::msg)
}

fn load(path: &Path) -> anyhow::Result<Runtime> {
    if utils::workspace_custody::PROTOCOL != 1 {
        anyhow::bail!("Qualified Linux archive custody required");
    }
    let config: Configuration = serde_json::from_slice(&pinned(path, None)?)?;
    if config.format != "vk-workspace-archive-runtime-v1" {
        anyhow::bail!("Unknown archive runtime protocol");
    }
    pinned(&config.driver, Some(&config.driver_sha256))?;
    pinned(
        &config.driver_configuration,
        Some(&config.driver_configuration_sha256),
    )?;
    if !config.python.is_absolute() || !config.database.is_absolute() || !config.database.is_file()
    {
        anyhow::bail!("Existing archive interpreter and catalog paths required");
    }
    if let Some(url) = &config.writer_url {
        let url = reqwest::Url::parse(url)?;
        let local = matches!(url.host_str(), Some("127.0.0.1" | "[::1]" | "localhost"));
        if !local
            || url.scheme() != "http"
            || url.path() != "/"
            || url.query().is_some()
            || url.fragment().is_some()
            || !url.username().is_empty()
            || url.password().is_some()
        {
            anyhow::bail!("Exact loopback writer origin required");
        }
    }
    if config.role == Role::Reader && config.writer_url.is_none() {
        anyhow::bail!("Protected history reader requires its existing writer origin");
    }
    // The protected reader sees the live catalog through an explicit read-only
    // binding. Its older history SQL snapshot cannot certify current cold state.
    let catalog = SqlitePoolOptions::new()
        .max_connections(2)
        .connect_lazy_with(
            SqliteConnectOptions::new()
                .filename(&config.database)
                .create_if_missing(false)
                .read_only(config.role == Role::Reader),
        );
    Ok(Runtime {
        config,
        catalog,
        owners: Mutex::new(HashMap::new()),
    })
}

impl Runtime {
    async fn owner(&self, workspace: Uuid) -> tokio::sync::OwnedMutexGuard<()> {
        let lock = {
            let mut owners = self.owners.lock().unwrap();
            owners.retain(|_, v| v.strong_count() > 0);
            let lock = owners
                .get(&workspace)
                .and_then(Weak::upgrade)
                .unwrap_or_default();
            owners.insert(workspace, Arc::downgrade(&lock));
            lock
        };
        lock.lock_owned().await
    }

    pub async fn phase(&self, workspace: Uuid) -> anyhow::Result<Option<String>> {
        Ok(
            sqlx::query_scalar("SELECT phase FROM workspace_archive_state WHERE workspace_id=?")
                .bind(workspace)
                .fetch_optional(&self.catalog)
                .await?,
        )
    }

    pub async fn helper(&self, workspace: Uuid, operation: &str) -> anyhow::Result<()> {
        if self.config.role != Role::Writer || !matches!(operation, "ensure" | "archive") {
            anyhow::bail!("Physical lifecycle belongs to the configured writer");
        }
        let _owner = self.owner(workspace).await;
        // Another reader may have completed the same restoration while this
        // request waited for its workspace owner. Do not invoke it a second time.
        if operation == "ensure"
            && self
                .phase(workspace)
                .await?
                .as_deref()
                .is_none_or(|p| p == "active")
        {
            return Ok(());
        }
        if self.invoke(workspace, operation).await.is_err() {
            let message =
                "Workspace recovery is pending; its source and retained input remain protected";
            sqlx::query("UPDATE workspace_archive_state SET last_error=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE workspace_id=?")
                .bind(message).bind(workspace).execute(&self.catalog).await?;
            sqlx::query("UPDATE workspace_archive_inputs SET error=? WHERE workspace_id=? AND state='waiting_restore'")
                .bind(message).bind(workspace).execute(&self.catalog).await?;
            anyhow::bail!(message);
        }
        Ok(())
    }

    async fn invoke(&self, workspace: Uuid, operation: &str) -> anyhow::Result<()> {
        pinned(&self.config.driver, Some(&self.config.driver_sha256))?;
        pinned(
            &self.config.driver_configuration,
            Some(&self.config.driver_configuration_sha256),
        )?;
        let mut child = Command::new(&self.config.python)
            .arg(&self.config.driver)
            .arg("--config")
            .arg(&self.config.driver_configuration)
            .arg("--workspace")
            .arg(workspace.to_string())
            .arg(operation)
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .kill_on_drop(true)
            .spawn()?;
        // Driver protocol is one small status object; private diagnostics stay
        // in its durable operation record, never in a public API error.
        let mut output = Vec::new();
        child
            .stdout
            .take()
            .ok_or_else(|| anyhow::anyhow!("Archive driver output missing"))?
            .take(65537)
            .read_to_end(&mut output)
            .await?;
        if output.len() > 65536 {
            child.kill().await?;
            anyhow::bail!("Archive driver response exceeded its protocol");
        }
        let result = child.wait().await?;
        let status = serde_json::from_slice::<serde_json::Value>(&output).ok();
        if !result.success()
            || status.as_ref().and_then(|s| s.get("complete"))
                != Some(&serde_json::Value::Bool(true))
        {
            anyhow::bail!("Physical driver did not confirm completion");
        }
        Ok(())
    }

    pub async fn readable(&self, workspace: Uuid) -> anyhow::Result<WorkspaceCustody> {
        loop {
            match WorkspaceCustody::try_acquire(&self.config.custody_root, workspace, false) {
                Ok(guard) => {
                    if self
                        .phase(workspace)
                        .await?
                        .as_deref()
                        .is_none_or(|p| p == "active")
                    {
                        if self.config.role == Role::Writer {
                            sqlx::query("DELETE FROM workspace_archive_reads WHERE workspace_id=?")
                                .bind(workspace)
                                .execute(&self.catalog)
                                .await?;
                        }
                        return Ok(guard);
                    }
                    drop(guard);
                }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {}
                Err(e) => return Err(e.into()),
            }
            if crate::services::admission::is_held() {
                anyhow::bail!("Restore this workspace before retrying execution admission");
            }
            if self.config.role == Role::Writer {
                sqlx::query(
                    "INSERT OR IGNORE INTO workspace_archive_reads(workspace_id) VALUES(?)",
                )
                .bind(workspace)
                .execute(&self.catalog)
                .await?;
                self.helper(workspace, "ensure").await?;
                // Acquire the shared guard before clearing read intent, so an
                // archive cannot race the reader's first lazy filesystem open.
                let guard =
                    WorkspaceCustody::try_acquire(&self.config.custody_root, workspace, false)?;
                if self
                    .phase(workspace)
                    .await?
                    .as_deref()
                    .is_some_and(|p| p != "active")
                {
                    anyhow::bail!("Workspace restore has not reached an active generation");
                }
                sqlx::query("DELETE FROM workspace_archive_reads WHERE workspace_id=?")
                    .bind(workspace)
                    .execute(&self.catalog)
                    .await?;
                return Ok(guard);
            }
            let origin = self.config.writer_url.as_ref().unwrap();
            let response = reqwest::Client::new()
                .post(format!(
                    "{}api/workspaces/{workspace}/archive-restore",
                    origin
                ))
                .send()
                .await?
                .error_for_status()?;
            let reply: serde_json::Value = response.json().await?;
            if reply.get("success") != Some(&serde_json::Value::Bool(true)) {
                anyhow::bail!("Writer is still restoring this workspace");
            }
            // Recheck the current shared catalog under the actual shared lock;
            // the writer's HTTP reply alone is not custody for this process.
        }
    }
}

pub async fn readable(
    pool: &SqlitePool,
    workspace: Uuid,
) -> anyhow::Result<Option<WorkspaceCustody>> {
    let Some(runtime) = configured()? else {
        return Ok(None);
    };
    if runtime.config.role == Role::Writer {
        let actual = pool.connect_options().get_filename().canonicalize()?;
        if actual != runtime.config.database.canonicalize()? {
            anyhow::bail!("Archive writer catalog differs from serving SQL");
        }
    }
    Ok(Some(runtime.readable(workspace).await?))
}

pub async fn execution_readable(
    pool: &SqlitePool,
    execution: Uuid,
) -> anyhow::Result<Option<WorkspaceCustody>> {
    if configured()?.is_none() {
        return Ok(None);
    }
    let workspace:Uuid=sqlx::query_scalar("SELECT s.workspace_id FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.id=?")
        .bind(execution).fetch_one(pool).await?;
    readable(pool, workspace).await
}

pub async fn requires_revival(pool: &SqlitePool, workspace: Uuid) -> anyhow::Result<bool> {
    let Some(runtime) = configured()? else {
        return Ok(false);
    };
    if runtime.config.role != Role::Writer {
        anyhow::bail!("Protected history reader cannot accept execution input");
    }
    let archived: bool = sqlx::query_scalar("SELECT archived FROM workspaces WHERE id=?")
        .bind(workspace)
        .fetch_one(pool)
        .await?;
    let pending:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspace_archive_inputs WHERE workspace_id=? AND state NOT IN ('dispatched','cancelled'))")
        .bind(workspace).fetch_one(pool).await?;
    Ok(archived
        || pending
        || runtime
            .phase(workspace)
            .await?
            .as_deref()
            .is_some_and(|p| p != "active"))
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use std::os::unix::fs::PermissionsExt;

    use tokio::io::AsyncWriteExt;

    use super::*;

    struct Fixture {
        folder: tempfile::TempDir,
        workspace: Uuid,
        runtime: Runtime,
    }

    impl Fixture {
        async fn new(role: Role, script: &str, writer: Option<String>) -> Self {
            let folder = tempfile::tempdir().unwrap();
            let root = folder.path().canonicalize().unwrap();
            let locks = root.join("custody");
            std::fs::create_dir(&locks).unwrap();
            std::fs::set_permissions(&locks, std::fs::Permissions::from_mode(0o700)).unwrap();
            let database = root.join("catalog.sqlite");
            let pool = SqlitePoolOptions::new()
                .connect_with(
                    SqliteConnectOptions::new()
                        .filename(&database)
                        .create_if_missing(true),
                )
                .await
                .unwrap();
            sqlx::raw_sql("CREATE TABLE workspace_archive_state(workspace_id BLOB PRIMARY KEY,phase TEXT,last_error TEXT,updated_at TEXT); CREATE TABLE workspace_archive_reads(workspace_id BLOB PRIMARY KEY); CREATE TABLE workspace_archive_inputs(workspace_id BLOB,payload TEXT,state TEXT,error TEXT);")
                .execute(&pool).await.unwrap();
            let workspace = Uuid::new_v4();
            sqlx::query("INSERT INTO workspace_archive_state VALUES(?,'cold',NULL,'old')")
                .bind(workspace)
                .execute(&pool)
                .await
                .unwrap();
            sqlx::query("INSERT INTO workspace_archive_inputs VALUES(?,'exact private input and settings','waiting_restore',NULL)").bind(workspace).execute(&pool).await.unwrap();
            pool.close().await;
            let driver = root.join("driver.py");
            let config = root.join("driver.json");
            std::fs::write(&driver, script).unwrap();
            std::fs::write(
                &config,
                serde_json::to_vec(&serde_json::json!({"database":database})).unwrap(),
            )
            .unwrap();
            let configuration = root.join("runtime.json");
            std::fs::write(&configuration, serde_json::to_vec(&serde_json::json!({
                "format":"vk-workspace-archive-runtime-v1", "role":if role==Role::Writer {"writer"}else{"reader"},
                "database":database,"custody_root":locks,"python":"/usr/bin/python3",
                "driver":driver,"driver_sha256":format!("{:x}",Sha256::digest(script)),
                "driver_configuration":config,"driver_configuration_sha256":format!("{:x}",Sha256::digest(std::fs::read(&config).unwrap())),
                "writer_url":writer,
            })).unwrap()).unwrap();
            for path in [&configuration, &driver, &config] {
                std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600)).unwrap();
            }
            Self {
                folder,
                workspace,
                runtime: load(&configuration).unwrap(),
            }
        }
    }

    const RESTORE: &str = r#"import json,sqlite3,sys,uuid
c=sqlite3.connect(json.load(open(sys.argv[2]))['database'])
w=uuid.UUID(sys.argv[4]).bytes
assert c.execute('select count(*) from workspace_archive_reads where workspace_id=?',(w,)).fetchone()==(1,)
c.execute("update workspace_archive_state set phase='active' where workspace_id=?",(w,))
c.commit()
print('{"complete":true}')
"#;

    #[tokio::test]
    async fn writer_restoration_hands_read_intent_to_shared_custody_without_altering_input() {
        let fixture = Fixture::new(Role::Writer, RESTORE, None).await;
        let runtime = &fixture.runtime;
        let guard = runtime.readable(fixture.workspace).await.unwrap();
        assert_eq!(
            runtime.phase(fixture.workspace).await.unwrap().as_deref(),
            Some("active")
        );
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT count(*) FROM workspace_archive_reads")
                .fetch_one(&runtime.catalog)
                .await
                .unwrap(),
            0
        );
        assert_eq!(
            sqlx::query_scalar::<_, String>("SELECT payload FROM workspace_archive_inputs")
                .fetch_one(&runtime.catalog)
                .await
                .unwrap(),
            "exact private input and settings"
        );
        assert!(
            WorkspaceCustody::try_acquire(&runtime.config.custody_root, fixture.workspace, true)
                .is_err()
        );
        // Warm history must not rerun the helper or require the destination.
        std::fs::remove_file(&runtime.config.driver).unwrap();
        let second = runtime.readable(fixture.workspace).await.unwrap();
        drop((guard, second));
        assert!(
            WorkspaceCustody::try_acquire(&runtime.config.custody_root, fixture.workspace, true)
                .is_ok()
        );
    }

    #[tokio::test]
    async fn concurrent_history_readers_share_one_restore_without_replaying_the_driver() {
        let script = format!(
            "{RESTORE}\nimport os\nmarker=sys.argv[2]+'.completed'\nfd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\nos.close(fd)\n"
        );
        let fixture = Fixture::new(Role::Writer, &script, None).await;
        let (a, b) = tokio::join!(
            fixture.runtime.readable(fixture.workspace),
            fixture.runtime.readable(fixture.workspace)
        );
        let a = a.unwrap();
        let b = b.unwrap();
        assert!(
            fixture
                .runtime
                .config
                .driver_configuration
                .with_extension("json.completed")
                .is_file()
        );
        assert!(
            WorkspaceCustody::try_acquire(
                &fixture.runtime.config.custody_root,
                fixture.workspace,
                true
            )
            .is_err()
        );
        drop((a, b));
    }

    #[tokio::test]
    async fn malformed_driver_reply_retains_input_and_visible_recovery_intent() {
        let fixture = Fixture::new(Role::Writer, "print('not a completion receipt')", None).await;
        assert!(fixture.runtime.readable(fixture.workspace).await.is_err());
        assert!(
            sqlx::query_scalar::<_, Option<String>>("SELECT error FROM workspace_archive_inputs")
                .fetch_one(&fixture.runtime.catalog)
                .await
                .unwrap()
                .is_some()
        );
        assert_eq!(
            fixture
                .runtime
                .phase(fixture.workspace)
                .await
                .unwrap()
                .as_deref(),
            Some("cold")
        );
        let (payload, state, error): (String, String, Option<String>) =
            sqlx::query_as("SELECT payload,state,error FROM workspace_archive_inputs")
                .fetch_one(&fixture.runtime.catalog)
                .await
                .unwrap();
        assert_eq!(payload, "exact private input and settings");
        assert_eq!(state, "waiting_restore");
        assert!(error.unwrap().contains("recovery is pending"));
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT count(*) FROM workspace_archive_reads")
                .fetch_one(&fixture.runtime.catalog)
                .await
                .unwrap(),
            1
        );
    }

    #[tokio::test]
    async fn changed_driver_and_held_global_admission_cannot_begin_restoration() {
        let fixture = Fixture::new(Role::Writer, RESTORE, None).await;
        let held =
            crate::services::admission::locked(fixture.runtime.readable(fixture.workspace)).await;
        assert!(
            held.unwrap_err()
                .to_string()
                .contains("before retrying execution admission")
        );
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT count(*) FROM workspace_archive_reads")
                .fetch_one(&fixture.runtime.catalog)
                .await
                .unwrap(),
            0
        );
        std::fs::write(&fixture.runtime.config.driver, "raise Exception('changed')").unwrap();
        assert!(fixture.runtime.readable(fixture.workspace).await.is_err());
        assert!(
            sqlx::query_scalar::<_, Option<String>>("SELECT error FROM workspace_archive_inputs")
                .fetch_one(&fixture.runtime.catalog)
                .await
                .unwrap()
                .is_some()
        );
        assert_eq!(
            fixture
                .runtime
                .phase(fixture.workspace)
                .await
                .unwrap()
                .as_deref(),
            Some("cold")
        );
    }

    #[tokio::test]
    async fn protected_reader_uses_writer_restore_and_current_readonly_catalog() {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let origin = format!("http://{}/", listener.local_addr().unwrap());
        let fixture = Fixture::new(
            Role::Reader,
            "raise Exception('reader cannot launch helper')",
            Some(origin),
        )
        .await;
        assert!(
            sqlx::query("UPDATE workspace_archive_state SET phase='active'")
                .execute(&fixture.runtime.catalog)
                .await
                .is_err()
        );
        let database = fixture.runtime.config.database.clone();
        let workspace = fixture.workspace;
        let server = tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await.unwrap();
            let mut request = vec![0; 4096];
            let length = socket.read(&mut request).await.unwrap();
            let request = String::from_utf8_lossy(&request[..length]);
            assert!(request.starts_with(&format!(
                "POST /api/workspaces/{workspace}/archive-restore "
            )));
            let pool = SqlitePoolOptions::new()
                .connect_with(SqliteConnectOptions::new().filename(database))
                .await
                .unwrap();
            sqlx::query("UPDATE workspace_archive_state SET phase='active'")
                .execute(&pool)
                .await
                .unwrap();
            let body = r#"{"success":true,"data":true}"#;
            socket.write_all(format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",body.len(),body).as_bytes()).await.unwrap();
            pool.close().await;
        });
        let guard = fixture.runtime.readable(workspace).await.unwrap();
        server.await.unwrap();
        assert!(
            WorkspaceCustody::try_acquire(&fixture.runtime.config.custody_root, workspace, true)
                .is_err()
        );
        drop(guard);
        assert!(fixture.folder.path().exists());
    }
}
