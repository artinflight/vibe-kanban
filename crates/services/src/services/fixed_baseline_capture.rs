//! Native-only capture. No API accepts a precomputed baseline or database rows.
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
    process::Stdio,
    time::Duration,
};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::{Column, Row, SqlitePool, TypeInfo, ValueRef};
use tokio::io::AsyncReadExt;
use uuid::Uuid;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(super) struct CaptureSpec {
    pub workspace_root: PathBuf,
    pub database_path: PathBuf,
    // Exact reviewed private ledger/config/toolchain inputs, including latest.json.
    pub retained_files: BTreeMap<PathBuf, String>,
    pub original_objects: BTreeMap<String, Vec<String>>,
    pub excluded_cache_roots: BTreeMap<String, Vec<String>>,
}
fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn bounded_read(path: &Path, limit: u64) -> Result<Vec<u8>, String> {
    use std::io::Read;
    let mut bytes = Vec::new();
    std::fs::File::open(path)
        .map_err(|e| e.to_string())?
        .take(limit + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() as u64 > limit {
        return Err("native input grew beyond capture limit".into());
    }
    Ok(bytes)
}
async fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>, String> {
    let mut child = tokio::process::Command::new("git")
        .arg("--no-optional-locks")
        .arg("-C")
        .arg(root)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .map_err(|e| e.to_string())?;
    let mut out = child
        .stdout
        .take()
        .ok_or("git stdout missing")?
        .take(4 * 1024 * 1024 + 1);
    let result = tokio::time::timeout(Duration::from_secs(15), async {
        let mut bytes = Vec::new();
        out.read_to_end(&mut bytes)
            .await
            .map_err(|e| e.to_string())?;
        if bytes.len() > 4 * 1024 * 1024 {
            return Err("git capture exceeds bound".into());
        }
        let status = child.wait().await.map_err(|e| e.to_string())?;
        if !status.success() {
            return Err("native git capture failed".into());
        }
        Ok(bytes)
    })
    .await;
    match result {
        Ok(Ok(bytes)) => Ok(bytes),
        other => {
            let _ = child.kill().await;
            let _ = child.wait().await;
            Err(match other {
                Ok(Err(e)) => e,
                _ => "native git capture timed out".into(),
            })
        }
    }
}
async fn rows(
    conn: &mut sqlx::SqliteConnection,
    query: &str,
    workspace: Uuid,
    excluded: Uuid,
) -> Result<serde_json::Value, String> {
    let data = sqlx::query(query)
        .bind(workspace)
        .bind(excluded)
        .fetch_all(&mut *conn)
        .await
        .map_err(|e| e.to_string())?;
    if data.len() > 10000 {
        return Err("native history exceeds bounded capture".into());
    }
    let mut result = Vec::new();
    for row in data {
        let mut fields = BTreeMap::new();
        for (i, c) in row.columns().iter().enumerate() {
            let raw = row.try_get_raw(i).map_err(|e| e.to_string())?;
            let value = if raw.is_null() {
                serde_json::json!(["null"])
            } else {
                match raw.type_info().name() {
                    "INTEGER" => serde_json::json!([
                        "integer",
                        row.try_get::<i64, _>(i).map_err(|e| e.to_string())?
                    ]),
                    "REAL" => serde_json::json!([
                        "real_bits",
                        row.try_get::<f64, _>(i)
                            .map_err(|e| e.to_string())?
                            .to_bits()
                            .to_string()
                    ]),
                    "BLOB" => serde_json::json!([
                        "blob",
                        row.try_get::<Vec<u8>, _>(i).map_err(|e| e.to_string())?
                    ]),
                    "TEXT" => serde_json::json!([
                        "text",
                        row.try_get::<String, _>(i).map_err(|e| e.to_string())?
                    ]),
                    _ => return Err("unsupported native SQLite type".into()),
                }
            };
            fields.insert(c.name().to_owned(), value);
        }
        result.push(fields);
    }
    serde_json::to_value(result).map_err(|e| e.to_string())
}
pub(super) async fn capture(
    pool: &SqlitePool,
    spec: &CaptureSpec,
    workspace: Uuid,
    session: Uuid,
    excluded: Option<Uuid>,
) -> Result<String, String> {
    let excluded = excluded.unwrap_or(Uuid::nil());
    let databases = sqlx::query("PRAGMA database_list")
        .fetch_all(pool)
        .await
        .map_err(|e| e.to_string())?;
    let main = databases
        .iter()
        .find(|r| r.try_get::<String, _>("name").ok().as_deref() == Some("main"))
        .ok_or("main dataset missing")?;
    let actual_db: String = main.try_get("file").map_err(|e| e.to_string())?;
    if Path::new(&actual_db)
        .canonicalize()
        .map_err(|e| e.to_string())?
        != spec.database_path
    {
        return Err("authoritative database path mismatch".into());
    }
    let root = spec
        .workspace_root
        .canonicalize()
        .map_err(|e| e.to_string())?;
    if root != spec.workspace_root {
        return Err("native workspace root drift".into());
    }
    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    let archived: bool = sqlx::query_scalar("SELECT archived FROM workspaces WHERE id=?")
        .bind(workspace)
        .fetch_one(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    if archived {
        return Err("fixed launch requires existing unarchived workspace".into());
    }
    let actual: Option<String> =
        sqlx::query_scalar("SELECT container_ref FROM workspaces WHERE id=?")
            .bind(workspace)
            .fetch_optional(&mut *tx)
            .await
            .map_err(|e| e.to_string())?;
    if actual.as_deref() != root.to_str() {
        return Err("native workspace binding mismatch".into());
    }
    let owner: Option<Uuid> = sqlx::query_scalar("SELECT workspace_id FROM sessions WHERE id=?")
        .bind(session)
        .fetch_optional(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    if owner != Some(workspace) {
        return Err("native session binding mismatch".into());
    }
    let running: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM execution_processes WHERE status='running' AND id!=?",
    )
    .bind(excluded)
    .fetch_one(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;
    if running != 0 {
        return Err("another native owner is active".into());
    }
    let queries = [
        (
            "workspace",
            "SELECT * FROM workspaces WHERE id=?1 AND ?2 IS NOT NULL ORDER BY rowid LIMIT 10001",
        ),
        (
            "sessions",
            "SELECT * FROM sessions WHERE workspace_id=?1 AND ?2 IS NOT NULL ORDER BY rowid LIMIT 10001",
        ),
        (
            "mapping",
            "SELECT * FROM workspace_repos WHERE workspace_id=?1 AND ?2 IS NOT NULL ORDER BY rowid LIMIT 10001",
        ),
        (
            "repos",
            "SELECT * FROM repos WHERE id IN (SELECT repo_id FROM workspace_repos WHERE workspace_id=?1) AND ?2 IS NOT NULL ORDER BY rowid LIMIT 10001",
        ),
        (
            "executions",
            "SELECT * FROM execution_processes WHERE session_id IN (SELECT id FROM sessions WHERE workspace_id=?1) AND id!=?2 ORDER BY rowid LIMIT 10001",
        ),
        (
            "repo_states",
            "SELECT * FROM execution_process_repo_states WHERE execution_process_id IN (SELECT e.id FROM execution_processes e JOIN sessions s ON e.session_id=s.id WHERE s.workspace_id=?1 UNION SELECT execution_process_id FROM turn_github_sync WHERE workspace_id=?1) AND execution_process_id!=?2 ORDER BY rowid LIMIT 10001",
        ),
        (
            "history",
            "SELECT * FROM turn_github_sync WHERE workspace_id=?1 AND execution_process_id!=?2 ORDER BY rowid LIMIT 10001",
        ),
        (
            "incoming",
            "SELECT * FROM turn_github_sync_incoming WHERE workspace_id=?1 AND ?2 IS NOT NULL ORDER BY rowid LIMIT 10001",
        ),
        (
            "queue",
            "SELECT * FROM turn_github_sync_user_queue WHERE workspace_id=?1 AND ?2 IS NOT NULL ORDER BY rowid LIMIT 10001",
        ),
    ];
    let mut before = BTreeMap::new();
    for (name, q) in queries {
        before.insert(name, rows(&mut *tx, q, workspace, excluded).await?);
    }
    let names:Vec<String>=sqlx::query_scalar("SELECT r.name FROM repos r JOIN workspace_repos wr ON r.id=wr.repo_id WHERE wr.workspace_id=? ORDER BY r.name")
        .bind(workspace).fetch_all(&mut *tx).await.map_err(|e|e.to_string())?;
    if names.is_empty() || names.len() != spec.original_objects.len() {
        return Err("native repository set mismatch".into());
    }
    let mut git_state = BTreeMap::new();
    for name in names {
        let path = root.join(&name).canonicalize().map_err(|e| e.to_string())?;
        if !path.starts_with(&root) || Path::new(&name).components().count() != 1 {
            return Err("repository containment mismatch".into());
        }
        let objects = spec
            .original_objects
            .get(&name)
            .ok_or("unbound native repository")?;
        if objects.is_empty() {
            return Err("retained original object set is empty".into());
        }
        for oid in objects {
            if ![40, 64].contains(&oid.len()) || !oid.bytes().all(|b| b.is_ascii_hexdigit()) {
                return Err("invalid retained object identity".into());
            }
            git(&path, &["cat-file", "-e", &format!("{oid}^{{commit}}")]).await?;
        }
        let branch = git(&path, &["symbolic-ref", "--quiet", "HEAD"]).await?;
        let ignored = git(
            &path,
            &[
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "--directory",
                "-z",
            ],
        )
        .await?;
        for raw in ignored.split(|b| *b == 0).filter(|p| !p.is_empty()) {
            let rel = std::str::from_utf8(raw).map_err(|_| "ignored non-UTF8 path")?;
            let explicitly_excluded = spec
                .excluded_cache_roots
                .get(&name)
                .is_some_and(|roots| roots.iter().any(|r| r == rel));
            if !explicitly_excluded && !spec.retained_files.contains_key(&path.join(rel)) {
                return Err("ignored input is neither pinned nor explicitly excluded cache".into());
            }
        }
        let head = git(&path, &["rev-parse", "--verify", "HEAD"]).await?;
        let index = git(&path, &["ls-files", "--stage", "-z"]).await?;
        let files = git(
            &path,
            &[
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
        )
        .await?;
        let mut working = BTreeMap::new();
        let mut total = 0u64;
        for raw in files.split(|b| *b == 0).filter(|p| !p.is_empty()) {
            let rel = std::str::from_utf8(raw).map_err(|_| "unsupported non-UTF8 native path")?;
            if Path::new(rel).is_absolute()
                || Path::new(rel)
                    .components()
                    .any(|c| matches!(c, std::path::Component::ParentDir))
            {
                return Err("working path escapes repository".into());
            }
            let file = path.join(rel);
            match std::fs::symlink_metadata(&file) {
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                    working.insert(rel.to_owned(), "missing".to_owned());
                }
                Err(e) => return Err(e.to_string()),
                Ok(meta) => {
                    total = total
                        .checked_add(meta.len())
                        .ok_or("capture size overflow")?;
                    if total > 256 * 1024 * 1024 {
                        return Err("working inventory exceeds capture envelope".into());
                    }
                    if meta.file_type().is_symlink() {
                        return Err("symlink requires explicit native capture support".into());
                    }
                    if !meta.is_file() {
                        return Err("non-file worktree entry requires explicit support".into());
                    }
                    if file.canonicalize().map_err(|e| e.to_string())? != file {
                        return Err("working parent path changed".into());
                    }
                    let bytes = bounded_read(&file, 256 * 1024 * 1024 - total + meta.len())?;
                    {
                        #[cfg(unix)]
                        let mode = {
                            use std::os::unix::fs::PermissionsExt;
                            meta.permissions().mode()
                        };
                        #[cfg(not(unix))]
                        let mode = if meta.permissions().readonly() { 1 } else { 0 };
                        working.insert(rel.to_owned(), format!("{}:{mode}", digest(&bytes)));
                    }
                }
            }
        }
        if head != git(&path, &["rev-parse", "--verify", "HEAD"]).await?
            || index != git(&path, &["ls-files", "--stage", "-z"]).await?
        {
            return Err("Git changed during native capture".into());
        }
        git_state.insert(name,serde_json::json!({"branch":branch,"head":head,"index":index,"working":working,"ignored":ignored}));
    }
    let mut retained = BTreeMap::new();
    for (path, expected) in &spec.retained_files {
        if !path.is_absolute() || path.canonicalize().map_err(|e| e.to_string())? != *path {
            return Err("retained source path changed".into());
        }
        if std::fs::metadata(path).map_err(|e| e.to_string())?.len() > 16 * 1024 * 1024 {
            return Err("retained input exceeds bound".into());
        }
        let actual = digest(&bounded_read(path, 16 * 1024 * 1024)?);
        if &actual != expected {
            return Err("retained ledger/config/toolchain preimage drift".into());
        }
        retained.insert(path, actual);
    }
    tx.commit().await.map_err(|e| e.to_string())?;
    let mut check = pool.begin().await.map_err(|e| e.to_string())?;
    for (name, q) in queries {
        if before.get(name) != Some(&rows(&mut *check, q, workspace, excluded).await?) {
            return Err("native database changed during capture".into());
        }
    }
    check.commit().await.map_err(|e| e.to_string())?;
    let bytes = serde_json::to_vec(&(before, git_state, retained)).map_err(|e| e.to_string())?;
    Ok(digest(&bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    async fn fixture() -> (tempfile::TempDir, SqlitePool, CaptureSpec, Uuid, Uuid) {
        let d = tempfile::tempdir().unwrap();
        let db = d.path().join("test.sqlite");
        let pool = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&format!("sqlite://{}?mode=rwc", db.display()))
            .await
            .unwrap();
        sqlx::raw_sql("CREATE TABLE workspaces(id BLOB PRIMARY KEY,container_ref TEXT,archived INTEGER); CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB); CREATE TABLE workspace_repos(workspace_id BLOB,repo_id BLOB); CREATE TABLE repos(id BLOB PRIMARY KEY,name TEXT); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT); CREATE TABLE execution_process_repo_states(execution_process_id BLOB,before_head_commit TEXT,after_head_commit TEXT); CREATE TABLE turn_github_sync(execution_process_id BLOB,workspace_id BLOB,observation_state TEXT,observation_report TEXT); CREATE TABLE turn_github_sync_incoming(id BLOB,workspace_id BLOB,state TEXT); CREATE TABLE turn_github_sync_user_queue(id BLOB,workspace_id BLOB);")
            .execute(&pool).await.unwrap();
        let root = d.path().join("workspace");
        let repo = root.join("repo");
        std::fs::create_dir_all(&repo).unwrap();
        git(&repo, &["init", "-b", "main"]).await.unwrap();
        std::fs::write(repo.join("tracked.txt"), b"original").unwrap();
        git(&repo, &["add", "tracked.txt"]).await.unwrap();
        git(
            &repo,
            &[
                "-c",
                "user.name=Synthetic",
                "-c",
                "user.email=synthetic@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "fixture",
            ],
        )
        .await
        .unwrap();
        let oid = String::from_utf8(git(&repo, &["rev-parse", "HEAD"]).await.unwrap())
            .unwrap()
            .trim()
            .to_owned();
        let w = Uuid::new_v4();
        let session = Uuid::new_v4();
        let rid = Uuid::new_v4();
        sqlx::query("INSERT INTO workspaces VALUES(?,?,0)")
            .bind(w)
            .bind(root.to_str().unwrap())
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO sessions VALUES(?,?)")
            .bind(session)
            .bind(w)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO repos VALUES(?,'repo')")
            .bind(rid)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO workspace_repos VALUES(?,?)")
            .bind(w)
            .bind(rid)
            .execute(&pool)
            .await
            .unwrap();
        let spec = CaptureSpec {
            workspace_root: root,
            database_path: db,
            retained_files: BTreeMap::new(),
            original_objects: BTreeMap::from([("repo".into(), vec![oid])]),
            excluded_cache_roots: BTreeMap::new(),
        };
        (d, pool, spec, w, session)
    }
    #[tokio::test]
    async fn actual_single_connection_git_sqlite_capture_and_drift() {
        let (_d, p, s, w, session) = fixture().await;
        let first =
            tokio::time::timeout(Duration::from_secs(10), capture(&p, &s, w, session, None))
                .await
                .unwrap()
                .unwrap();
        assert_eq!(first, capture(&p, &s, w, session, None).await.unwrap());
        std::fs::write(s.workspace_root.join("repo/tracked.txt"), b"changed").unwrap();
        assert_ne!(first, capture(&p, &s, w, session, None).await.unwrap());
    }
    #[tokio::test]
    async fn history_unknowns_preserved_and_active_owner_rejected() {
        let (_d, p, s, w, session) = fixture().await;
        let first = capture(&p, &s, w, session, None).await.unwrap();
        sqlx::query("INSERT INTO turn_github_sync VALUES(?,?,'failed',NULL)")
            .bind(Uuid::new_v4())
            .bind(w)
            .execute(&p)
            .await
            .unwrap();
        assert_ne!(first, capture(&p, &s, w, session, None).await.unwrap());
        let report: Option<String> =
            sqlx::query_scalar("SELECT observation_report FROM turn_github_sync")
                .fetch_one(&p)
                .await
                .unwrap();
        assert!(report.is_none());
        sqlx::query("INSERT INTO execution_processes VALUES(?,?,'running')")
            .bind(Uuid::new_v4())
            .bind(session)
            .execute(&p)
            .await
            .unwrap();
        assert!(
            capture(&p, &s, w, session, None)
                .await
                .unwrap_err()
                .contains("owner")
        );
    }
    #[tokio::test]
    async fn missing_original_and_unbound_ignored_inputs_refused() {
        let (_d, p, mut s, w, session) = fixture().await;
        let old = s.original_objects.clone();
        s.original_objects
            .insert("repo".into(), vec!["f".repeat(40)]);
        assert!(capture(&p, &s, w, session, None).await.is_err());
        s.original_objects = old;
        std::fs::write(s.workspace_root.join("repo/.gitignore"), b"private-input\n").unwrap();
        std::fs::write(s.workspace_root.join("repo/private-input"), b"synthetic").unwrap();
        assert!(
            capture(&p, &s, w, session, None)
                .await
                .unwrap_err()
                .contains("ignored input")
        );
    }
}
