//! Inert by default. The private fixed JSON is replaced only by an exact reviewed
//! release artifact, never by a runtime request, environment variable or API.
//! This module grants no history repair, publication, cleanup or chained launch.
use executors::actions::{ExecutorAction, ExecutorActionType};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::{Row, SqlitePool};
use uuid::Uuid;

const FIXED: &str = include_str!("fixed_baseline_manifest.json");

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    manifest_id: String,
    workspace: Uuid,
    session: Uuid,
    input_id: String,
    incoming_data_sha256: String,
    dataset_id: String,
    original_action_sha256: String,
    resolved_action_sha256: String,
    native_baseline_sha256: String,
    operator_decision_sha256: String,
    expires_at: i64,
    capture: super::fixed_baseline_capture::CaptureSpec,
    witness_root: std::path::PathBuf,
    dataset_marker: std::path::PathBuf,
    dataset_marker_sha256: String,
}

/// Cannot be constructed by API deserialization. Only load_fixed creates it.
#[derive(Clone, Debug)]
pub struct FixedAcceptance {
    manifest: Manifest,
    bytes_sha256: String,
}

#[derive(Clone, Debug)]
pub struct ReservedLaunch {
    execution: Uuid,
    manifest_id: String,
    manifest_sha256: String,
    workspace: Uuid,
    session: Uuid,
}
impl ReservedLaunch {
    pub fn execution_id(&self) -> Uuid {
        self.execution
    }
    pub fn matches_owner(&self, workspace: Uuid, session: Uuid) -> bool {
        self.workspace == workspace && self.session == session
    }
}

fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn action_hash(action: &ExecutorAction) -> Result<String, String> {
    serde_json::to_vec(action)
        .map(|bytes| hash(&bytes))
        .map_err(|e| e.to_string())
}
fn digest_valid(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn decode_fixed(bytes: &str) -> Result<Option<FixedAcceptance>, String> {
    if bytes.trim() == "null" {
        return Ok(None);
    }
    let manifest: Manifest = serde_json::from_str(bytes).map_err(|e| e.to_string())?;
    if manifest.manifest_id.is_empty()
        || manifest.input_id.is_empty()
        || manifest.dataset_id.is_empty()
        || ![
            &manifest.original_action_sha256,
            &manifest.resolved_action_sha256,
            &manifest.native_baseline_sha256,
            &manifest.incoming_data_sha256,
            &manifest.operator_decision_sha256,
            &manifest.dataset_marker_sha256,
        ]
        .iter()
        .all(|s| digest_valid(s))
    {
        return Err("incomplete fixed release binding".into());
    }
    Ok(Some(FixedAcceptance {
        manifest,
        bytes_sha256: hash(bytes.as_bytes()),
    }))
}
pub fn load_fixed() -> Result<Option<FixedAcceptance>, String> {
    decode_fixed(FIXED)
}

// Hash contract: serde_json::to_vec of the actual typed ExecutorAction with
// this pinned source/toolchain. Arbitrary caller JSON is never hashed directly.
fn one_action(action: &ExecutorAction) -> bool {
    action.next_action.is_none()
        && match &action.typ {
            ExecutorActionType::CodingAgentInitialRequest(_) => true,
            ExecutorActionType::CodingAgentFollowUpRequest(r) => {
                r.capacity.is_none() && r.reset_to_message_id.is_none()
            }
            _ => false,
        }
}
fn wall_seconds() -> i64 {
    chrono::Utc::now().timestamp()
}
impl FixedAcceptance {
    fn verify(
        &self,
        workspace: Uuid,
        session: Uuid,
        input_id: &str,
        dataset_id: &str,
        original: &ExecutorAction,
        resolved: &ExecutorAction,
        native_baseline: &str,
        now: i64,
    ) -> Result<(), String> {
        let m = &self.manifest;
        if m.workspace != workspace
            || m.session != session
            || m.input_id != input_id
            || m.dataset_id != dataset_id
            || now >= m.expires_at
            || m.native_baseline_sha256 != native_baseline
            || !one_action(original)
            || !one_action(resolved)
            || action_hash(original)? != m.original_action_sha256
            || action_hash(resolved)? != m.resolved_action_sha256
        {
            return Err("fixed acceptance identity/action/baseline/expiry mismatch".into());
        }
        Ok(())
    }
}

fn witness_path(fixed: &FixedAcceptance) -> Result<std::path::PathBuf, String> {
    let m = &fixed.manifest;
    if !m.witness_root.is_absolute() || !m.dataset_marker.is_absolute() {
        return Err("witness/dataset path must be release-bound absolute paths".into());
    }
    let root = m.witness_root.canonicalize().map_err(|e| e.to_string())?;
    let database = m
        .capture
        .database_path
        .canonicalize()
        .map_err(|e| e.to_string())?;
    if database != m.capture.database_path || database.parent().is_some_and(|d| root.starts_with(d))
    {
        return Err("witness root must be outside the restored database directory".into());
    }
    if root != m.witness_root || !root.is_dir() {
        return Err("witness root changed or is not a directory".into());
    }
    let marker = m.dataset_marker.canonicalize().map_err(|e| e.to_string())?;
    if marker != m.dataset_marker
        || hash(&std::fs::read(&marker).map_err(|e| e.to_string())?) != m.dataset_marker_sha256
    {
        return Err("authoritative dataset marker changed".into());
    }
    Ok(root.join(format!("{}.spent", hash(m.manifest_id.as_bytes()))))
}
fn witness_bytes(fixed: &FixedAcceptance, execution: Uuid) -> Result<Vec<u8>, String> {
    serde_json::to_vec(&(
        "fixed-baseline-spent-v1",
        &fixed.bytes_sha256,
        &fixed.manifest.dataset_id,
        &fixed.manifest.dataset_marker_sha256,
        execution,
    ))
    .map_err(|e| e.to_string())
}
fn record_spent_witness(fixed: &FixedAcceptance, execution: Uuid) -> Result<(), String> {
    use std::io::Write;
    let path = witness_path(fixed)?;
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
        .map_err(|e| format!("spent witness unavailable/already exists: {e}"))?;
    file.write_all(&witness_bytes(fixed, execution)?)
        .map_err(|e| e.to_string())?;
    file.sync_all().map_err(|e| e.to_string())?;
    std::fs::File::open(path.parent().ok_or("missing witness parent")?)
        .and_then(|f| f.sync_all())
        .map_err(|e| e.to_string())?;
    Ok(())
}
fn verify_spent_witness(fixed: &FixedAcceptance, execution: Uuid) -> Result<(), String> {
    let bytes = std::fs::read(witness_path(fixed)?).map_err(|e| e.to_string())?;
    if bytes != witness_bytes(fixed, execution)? {
        return Err("spent witness binding mismatch".into());
    }
    Ok(())
}

// Retained hold bindings are separate from launch authority. The reviewed
// replacement AND fallback retain every previously admitted manifest verbatim.
// No runtime endpoint, profile, or environment can add/re-arm an acceptance.
const HOLD_ARCHIVE: &str = include_str!("fixed_baseline_hold_archive.json");
pub struct StartupHolds {
    entries: Vec<FixedAcceptance>,
}
fn parse_startup_holds(active: &str, archive: &str) -> Result<StartupHolds, String> {
    let archived: Vec<String> = serde_json::from_str(archive).map_err(|e| e.to_string())?;
    let mut entries: Vec<FixedAcceptance> = Vec::new();
    for bytes in archived
        .iter()
        .map(String::as_str)
        .chain(std::iter::once(active))
    {
        let Some(fixed) = decode_fixed(bytes)? else {
            continue;
        };
        if let Some(prior) = entries
            .iter()
            .find(|p| p.manifest.manifest_id == fixed.manifest.manifest_id)
        {
            if prior.bytes_sha256 != fixed.bytes_sha256 {
                return Err("hold archive immutable binding mismatch".into());
            }
            continue;
        }
        // Validate locations and dataset before migrations/config/background work.
        witness_path(&fixed)?;
        entries.push(fixed);
    }
    let allowed: std::collections::BTreeSet<_> =
        entries.iter().map(witness_path).collect::<Result<_, _>>()?;
    let roots: std::collections::BTreeSet<_> = entries
        .iter()
        .map(|f| f.manifest.witness_root.clone())
        .collect();
    for root in roots {
        for item in std::fs::read_dir(root).map_err(|e| e.to_string())? {
            let path = item.map_err(|e| e.to_string())?.path();
            if path.extension().is_some_and(|e| e == "spent") && !allowed.contains(&path) {
                return Err("unbound spent witness: release archive incomplete".into());
            }
        }
    }
    Ok(StartupHolds { entries })
}
pub fn startup_holds() -> Result<StartupHolds, String> {
    parse_startup_holds(FIXED, HOLD_ARCHIVE)
}
/// Read-only startup reconciliation. A restored DB missing any spent row refuses
/// startup; it is never repaired into unused state or silently re-authorized.
pub async fn verify_startup_holds(pool: &SqlitePool, holds: &StartupHolds) -> Result<(), String> {
    let rows=sqlx::query("SELECT authorization_id,workspace_id,session_id,execution_id,reviewed_sha256,binding_json,state FROM workspace_baseline_acceptance")
        .fetch_all(pool).await.map_err(|e|e.to_string())?;
    for row in &rows {
        let id: String = row.try_get("authorization_id").map_err(|e| e.to_string())?;
        let fixed = holds
            .entries
            .iter()
            .find(|f| f.manifest.manifest_id == id)
            .ok_or("database hold missing from immutable release archive")?;
        let execution: Uuid = row.try_get("execution_id").map_err(|e| e.to_string())?;
        let workspace: Uuid = row.try_get("workspace_id").map_err(|e| e.to_string())?;
        let session: Uuid = row.try_get("session_id").map_err(|e| e.to_string())?;
        let digest: String = row.try_get("reviewed_sha256").map_err(|e| e.to_string())?;
        let binding: String = row.try_get("binding_json").map_err(|e| e.to_string())?;
        let state: String = row.try_get("state").map_err(|e| e.to_string())?;
        if workspace != fixed.manifest.workspace
            || session != fixed.manifest.session
            || digest != fixed.bytes_sha256
            || binding != serde_json::to_string(&fixed.manifest).map_err(|e| e.to_string())?
            || !matches!(state.as_str(), "spent_held" | "spawn_confirmed")
        {
            return Err("database hold drift; startup refused".into());
        }
        verify_spent_witness(fixed, execution)?;
    }
    for fixed in &holds.entries {
        let path = witness_path(fixed)?;
        if path.try_exists().map_err(|e| e.to_string())?
            && !rows.iter().any(|r| {
                r.try_get::<String, _>("authorization_id").ok().as_deref()
                    == Some(&fixed.manifest.manifest_id)
            })
        {
            return Err("orphan spent witness/old database restore: startup held".into());
        }
    }
    Ok(())
}

pub async fn reserve_native(
    pool: &SqlitePool,
    fixed: &FixedAcceptance,
    workspace: Uuid,
    session: Uuid,
    input_id: &str,
    original: &ExecutorAction,
    resolved: &ExecutorAction,
) -> Result<ReservedLaunch, String> {
    super::admission::locked(async {
        let first = super::fixed_baseline_capture::capture(
            pool,
            &fixed.manifest.capture,
            workspace,
            session,
            None,
        )
        .await?;
        let second = super::fixed_baseline_capture::capture(
            pool,
            &fixed.manifest.capture,
            workspace,
            session,
            None,
        )
        .await?;
        if first != second {
            return Err("native capture changed before reservation".into());
        }
        reserve_exact(
            pool,
            fixed,
            workspace,
            session,
            input_id,
            &fixed.manifest.dataset_id,
            original,
            resolved,
            &second,
        )
        .await
    })
    .await
}

/// First preparation boundary only. Native capture and the caller's entire
/// setup/spawn sequence must share admission::locked in the final adapter.
/// No runtime caller can supply a FixedAcceptance; default builds load None.
/// Witness root and dataset marker require exact reviewed deployment bindings;
/// neither is supplied by an API, environment or mutable runtime profile.
async fn reserve_exact(
    pool: &SqlitePool,
    fixed: &FixedAcceptance,
    workspace: Uuid,
    session: Uuid,
    input_id: &str,
    dataset_id: &str,
    original: &ExecutorAction,
    resolved: &ExecutorAction,
    native_baseline: &str,
) -> Result<ReservedLaunch, String> {
    super::admission::locked(async {
        fixed.verify(workspace, session, input_id, dataset_id, original, resolved, native_baseline, wall_seconds())?;
        let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
        // Acquire SQLite's writer lock before inspecting existing state. Stable
        // manifest ID is never replaced or rearmed, even after a backend restart.
        sqlx::query("UPDATE workspace_baseline_acceptance SET state=state WHERE authorization_id=?")
            .bind(&fixed.manifest.manifest_id).execute(&mut *tx).await.map_err(|e| e.to_string())?;
        fixed.verify(workspace, session, input_id, dataset_id, original, resolved, native_baseline, wall_seconds())?;
        if let Some(row) = sqlx::query("SELECT reviewed_sha256,state FROM workspace_baseline_acceptance WHERE authorization_id=?")
            .bind(&fixed.manifest.manifest_id).fetch_optional(&mut *tx).await.map_err(|e| e.to_string())? {
            let prior: String = row.try_get("reviewed_sha256").map_err(|e| e.to_string())?;
            return Err(if prior == fixed.bytes_sha256 { "acceptance already recorded; never rearm" }
                       else { "immutable manifest ID binding mismatch" }.into());
        }
        let execution = Uuid::new_v4();
        // The permanent create-only marker precedes the DB commit. A crash here
        // is deliberately spent/held, including after restoration of an old DB.
        // The reviewed release must keep this root OUTSIDE database rollback.
        record_spent_witness(fixed, execution)?;
        let binding = serde_json::to_string(&fixed.manifest).map_err(|e| e.to_string())?;
        // A single insert durably allocates the UUID and spends the exact input.
        // There is no separate approved state that restart can consume twice.
        sqlx::query("INSERT INTO workspace_baseline_acceptance (authorization_id,workspace_id,session_id,execution_id,reviewed_sha256,binding_json,operator_evidence_sha256,expires_at,state) VALUES (?,?,?,?,?,?,?,?,'spent_held')")
            .bind(&fixed.manifest.manifest_id).bind(workspace).bind(session).bind(execution)
            .bind(&fixed.bytes_sha256).bind(binding).bind(&fixed.manifest.operator_decision_sha256)
            .bind(fixed.manifest.expires_at).execute(&mut *tx).await.map_err(|e| e.to_string())?;
        fixed.verify(workspace, session, input_id, dataset_id, original, resolved, native_baseline, wall_seconds())?;
        tx.commit().await.map_err(|e| e.to_string())?;
        Ok(ReservedLaunch { execution, manifest_id: fixed.manifest.manifest_id.clone(),
            manifest_sha256: fixed.bytes_sha256.clone(), workspace, session })
    }).await
}

/// Inert adapter primitive: caller must hold admission custody across native
/// recapture, this recheck, and the existing sole spawn. This does not capture
/// native state itself and is not yet connected to a production launch path.
pub async fn revalidate_after_setup(
    pool: &SqlitePool,
    fixed: &FixedAcceptance,
    reserved: &ReservedLaunch,
    input_id: &str,
    dataset_id: &str,
    original: &ExecutorAction,
    resolved: &ExecutorAction,
    native_baseline: &str,
) -> Result<(), String> {
    super::admission::locked(async {
        fixed.verify(reserved.workspace, reserved.session, input_id, dataset_id,
            original, resolved, native_baseline, wall_seconds())?;
        if reserved.manifest_id != fixed.manifest.manifest_id || reserved.manifest_sha256 != fixed.bytes_sha256 {
            return Err("reserved fixed artifact mismatch".into());
        }
        verify_spent_witness(fixed,reserved.execution)?;
        let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM workspace_baseline_acceptance WHERE authorization_id=? AND reviewed_sha256=? AND execution_id=? AND workspace_id=? AND session_id=? AND binding_json=? AND state='spent_held'")
            .bind(&reserved.manifest_id).bind(&reserved.manifest_sha256).bind(reserved.execution)
            .bind(reserved.workspace).bind(reserved.session)
            .bind(serde_json::to_string(&fixed.manifest).map_err(|e| e.to_string())?)
            .fetch_one(pool).await.map_err(|e| e.to_string())?;
        if count != 1 { return Err("reserved launch state/binding drift".into()); }
        fixed.verify(reserved.workspace, reserved.session, input_id, dataset_id,
            original, resolved, native_baseline, wall_seconds())
    }).await
}

/// Confirmation cannot rearm or grant another action. Failure/timeout leaves spent_held.
pub async fn confirm_spawn(pool: &SqlitePool, reserved: &ReservedLaunch) -> Result<(), String> {
    super::admission::locked(async {
        let result = sqlx::query("UPDATE workspace_baseline_acceptance SET state='spawn_confirmed' WHERE authorization_id=? AND reviewed_sha256=? AND execution_id=? AND workspace_id=? AND session_id=? AND state='spent_held'")
            .bind(&reserved.manifest_id).bind(&reserved.manifest_sha256).bind(reserved.execution)
            .bind(reserved.workspace).bind(reserved.session).execute(pool).await.map_err(|e| e.to_string())?;
        if result.rows_affected() != 1 { return Err("spent launch confirmation mismatch".into()); }
        Ok(())
    }).await
}

struct LaunchContext {
    fixed: FixedAcceptance,
    original: ExecutorAction,
    reserved: Option<ReservedLaunch>,
    spawn_claimed: bool,
    spawn_issued: bool,
}
tokio::task_local! { static CURRENT: std::cell::RefCell<LaunchContext>; }
/// Invalid non-null embedded artifacts also force serialization; no env switch.
pub fn configured() -> bool {
    FIXED.trim() != "null"
}
pub fn in_request() -> bool {
    CURRENT.try_with(|_| true).unwrap_or(false)
}
pub async fn with_request<T>(
    pool: &SqlitePool,
    workspace: Uuid,
    session: Uuid,
    original: &ExecutorAction,
    run_reason: &db::models::execution_process::ExecutionProcessRunReason,
    work: impl std::future::Future<Output = T>,
) -> Result<T, String> {
    let Some(fixed) = load_fixed()? else {
        return Ok(work.await);
    };
    if fixed.manifest.workspace != workspace {
        return Ok(work.await);
    }
    if !matches!(
        run_reason,
        db::models::execution_process::ExecutionProcessRunReason::CodingAgent
    ) {
        return Err("fixed launch requires ordinary coding-agent run reason".into());
    }
    let _writer_custody = super::admission::fixed_writer_custody()?;
    if in_request() {
        return Err("fixed launch cannot nest or chain".into());
    }
    if fixed.manifest.session != session
        || !one_action(original)
        || action_hash(original)? != fixed.manifest.original_action_sha256
    {
        return Err("fixed original request mismatch".into());
    }
    let id = Uuid::parse_str(&fixed.manifest.input_id)
        .map_err(|_| "fixed input must be retained incoming UUID")?;
    let row: Option<(String, String, Uuid, Uuid)> = sqlx::query_as(
        "SELECT data,state,session_id,workspace_id FROM turn_github_sync_incoming WHERE id=?",
    )
    .bind(id)
    .fetch_optional(pool)
    .await
    .map_err(|e| e.to_string())?;
    let Some((data, state, actual_session, actual_workspace)) = row else {
        return Err("fixed input not retained".into());
    };
    if state != "received"
        || actual_session != session
        || actual_workspace != workspace
        || hash(data.as_bytes()) != fixed.manifest.incoming_data_sha256
    {
        return Err("fixed incoming request drift".into());
    }
    let competing:i64=sqlx::query_scalar("SELECT (SELECT COUNT(*) FROM turn_github_sync_incoming WHERE workspace_id=?1 AND state='received' AND id!=?2)+(SELECT COUNT(*) FROM turn_github_sync_user_queue WHERE workspace_id=?1)")
        .bind(workspace).bind(id).fetch_one(pool).await.map_err(|e|e.to_string())?;
    if competing != 0 {
        return Err("competing native input/queue".into());
    }
    Ok(CURRENT
        .scope(
            std::cell::RefCell::new(LaunchContext {
                fixed,
                original: original.clone(),
                reserved: None,
                spawn_claimed: false,
                spawn_issued: false,
            }),
            work,
        )
        .await)
}
pub async fn reserve_current(
    pool: &SqlitePool,
    resolved: &ExecutorAction,
) -> Result<Option<Uuid>, String> {
    let Some((fixed, original)) = CURRENT
        .try_with(|c| {
            let c = c.borrow();
            (c.fixed.clone(), c.original.clone())
        })
        .ok()
    else {
        return Ok(None);
    };
    let token = reserve_native(
        pool,
        &fixed,
        fixed.manifest.workspace,
        fixed.manifest.session,
        &fixed.manifest.input_id,
        &original,
        resolved,
    )
    .await?;
    let id = token.execution;
    CURRENT.with(|c| {
        let mut c = c.borrow_mut();
        c.reserved = Some(token);
    });
    Ok(Some(id))
}
/// Narrow task-local exception, never a workspace-wide or persisted green.
pub fn history_exception(workspace: Uuid, execution: Uuid) -> bool {
    CURRENT
        .try_with(|c| {
            let c = c.borrow();
            !c.spawn_claimed
                && c.reserved
                    .as_ref()
                    .is_some_and(|r| r.workspace == workspace && r.execution == execution)
        })
        .unwrap_or(false)
}
pub async fn before_spawn(
    pool: &SqlitePool,
    workspace: Uuid,
    execution: Uuid,
    resolved: &ExecutorAction,
) -> Result<bool, String> {
    if !in_request() {
        return Ok(false);
    }
    let (fixed, original, token) = CURRENT.with(|c| {
        let mut c = c.borrow_mut();
        if c.spawn_claimed {
            return Err("fixed spawn already claimed");
        }
        let token = c.reserved.clone().ok_or("fixed reservation missing")?;
        if token.workspace != workspace || token.execution != execution {
            return Err("fixed execution mismatch");
        }
        c.spawn_claimed = true;
        Ok((c.fixed.clone(), c.original.clone(), token))
    })?;
    let native = super::fixed_baseline_capture::capture(
        pool,
        &fixed.manifest.capture,
        workspace,
        token.session,
        Some(execution),
    )
    .await?;
    let fresh = super::fixed_baseline_capture::capture(
        pool,
        &fixed.manifest.capture,
        workspace,
        token.session,
        Some(execution),
    )
    .await?;
    if native != fresh {
        return Err("post-setup native capture drift".into());
    }
    revalidate_after_setup(
        pool,
        &fixed,
        &token,
        &fixed.manifest.input_id,
        &fixed.manifest.dataset_id,
        &original,
        resolved,
        &native,
    )
    .await?;
    Ok(true)
}
/// Non-awaiting final boundary after the last SQL operation and immediately
/// before the sole normal spawn. A second invocation fails even in this task.
pub fn issue_spawn_once(
    workspace: Uuid,
    execution: Uuid,
    resolved: &ExecutorAction,
) -> Result<(), String> {
    if !in_request() {
        return Ok(());
    }
    CURRENT.with(|c| {
        let mut c = c.borrow_mut();
        if !c.spawn_claimed || c.spawn_issued {
            return Err("fixed spawn is absent or already issued".into());
        }
        c.spawn_issued = true;
        let token = c.reserved.as_ref().ok_or("fixed reservation absent")?;
        if token.execution != execution || token.workspace != workspace {
            return Err("fixed spawn identity mismatch".into());
        }
        if wall_seconds() >= c.fixed.manifest.expires_at
            || action_hash(resolved)? != c.fixed.manifest.resolved_action_sha256
        {
            return Err("fixed spawn expired or action changed".into());
        }
        verify_spent_witness(&c.fixed, execution)?;
        if wall_seconds() >= c.fixed.manifest.expires_at {
            return Err("fixed spawn expired during witness check".into());
        }
        Ok(())
    })
}
pub async fn after_tracked_spawn(pool: &SqlitePool, execution: Uuid) -> Result<(), String> {
    let Some(token) = CURRENT
        .try_with(|c| {
            let c = c.borrow();
            c.spawn_claimed.then(|| c.reserved.clone()).flatten()
        })
        .ok()
        .flatten()
    else {
        return Ok(());
    };
    if token.execution != execution {
        return Err("tracked child execution mismatch".into());
    }
    confirm_spawn(pool, &token).await
}

#[cfg(test)]
mod tests {
    use executors::{
        actions::coding_agent_initial::CodingAgentInitialRequest, executors::BaseCodingAgent,
        profile::ExecutorConfig,
    };

    use super::*;
    async fn pool(url: &str) -> SqlitePool {
        let p = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(2)
            .connect(url)
            .await
            .unwrap();
        sqlx::raw_sql(include_str!(
            "../../../db/migrations/20261022093000_workspace_baseline_acceptance.sql"
        ))
        .execute(&p)
        .await
        .unwrap();
        p
    }
    fn fixture_in(d: &std::path::Path) -> (FixedAcceptance, ExecutorAction) {
        let marker = d.join("dataset");
        std::fs::write(&marker, b"synthetic-dataset").unwrap();
        let dbdir = d.join("database");
        std::fs::create_dir_all(&dbdir).unwrap();
        let dbfile = dbdir.join("test.sqlite");
        if !dbfile.exists() {
            std::fs::write(&dbfile, b"").unwrap();
        }
        let action = ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                prompt: "synthetic".into(),
                executor_config: ExecutorConfig::new(BaseCodingAgent::Codex),
                working_dir: None,
            }),
            None,
        );
        let m = Manifest {
            manifest_id: "synthetic-only".into(),
            workspace: Uuid::new_v4(),
            session: Uuid::new_v4(),
            input_id: "exact-input".into(),
            incoming_data_sha256: "d".repeat(64),
            dataset_id: "synthetic-dataset".into(),
            original_action_sha256: action_hash(&action).unwrap(),
            resolved_action_sha256: action_hash(&action).unwrap(),
            native_baseline_sha256: "a".repeat(64),
            operator_decision_sha256: "b".repeat(64),
            expires_at: wall_seconds() + 120,
            capture: super::super::fixed_baseline_capture::CaptureSpec {
                workspace_root: d.to_path_buf(),
                database_path: d.join("database/test.sqlite"),
                retained_files: Default::default(),
                original_objects: Default::default(),
                excluded_cache_roots: Default::default(),
            },
            witness_root: d.to_path_buf(),
            dataset_marker: marker,
            dataset_marker_sha256: hash(b"synthetic-dataset"),
        };
        (
            decode_fixed(&serde_json::to_string(&m).unwrap())
                .unwrap()
                .unwrap(),
            action,
        )
    }
    async fn reserve(
        p: &SqlitePool,
        f: &FixedAcceptance,
        a: &ExecutorAction,
    ) -> Result<ReservedLaunch, String> {
        reserve_exact(
            p,
            f,
            f.manifest.workspace,
            f.manifest.session,
            "exact-input",
            "synthetic-dataset",
            a,
            a,
            &"a".repeat(64),
        )
        .await
    }
    #[tokio::test]
    async fn production_migration_startup_preserves_spent_and_uncertain() {
        let d = tempfile::tempdir().unwrap();
        let (fixed, action) = fixture_in(d.path());
        let url = format!(
            "sqlite://{}?mode=rwc",
            d.path().join("database/test.sqlite").display()
        );
        let p = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .unwrap();
        let migrations = sqlx::migrate!("../db/migrations");
        migrations.run(&p).await.unwrap();
        let migration: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM _sqlx_migrations WHERE version=20261022093000 AND success=1",
        )
        .fetch_one(&p)
        .await
        .unwrap();
        assert_eq!(migration, 1);
        let token = reserve(&p, &fixed, &action).await.unwrap();
        let archive =
            serde_json::to_string(&vec![serde_json::to_string(&fixed.manifest).unwrap()]).unwrap();
        let holds = parse_startup_holds("null", &archive).unwrap();
        verify_startup_holds(&p, &holds).await.unwrap();
        let before: String = sqlx::query_scalar("SELECT state FROM workspace_baseline_acceptance")
            .fetch_one(&p)
            .await
            .unwrap();
        assert_eq!(before, "spent_held");
        p.close().await;
        let reopened = sqlx::sqlite::SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .unwrap();
        migrations.run(&reopened).await.unwrap();
        verify_startup_holds(&reopened, &holds).await.unwrap();
        assert!(reserve(&reopened, &fixed, &action).await.is_err());
        confirm_spawn(&reopened, &token).await.unwrap();
        verify_startup_holds(&reopened, &holds).await.unwrap();
        assert!(reserve(&reopened, &fixed, &action).await.is_err());
        reopened.close().await;
        let restored = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
        migrations.run(&restored).await.unwrap();
        assert!(verify_startup_holds(&restored, &holds).await.is_err());
        assert!(reserve(&restored, &fixed, &action).await.is_err());
    }
    #[test]
    fn public_build_disabled() {
        assert!(load_fixed().unwrap().is_none());
    }
    #[test]
    fn typed_action_roundtrip_hash() {
        let d = tempfile::tempdir().unwrap();
        let (_, a) = fixture_in(d.path());
        let bytes = serde_json::to_vec(&a).unwrap();
        let decoded: ExecutorAction = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(action_hash(&a).unwrap(), action_hash(&decoded).unwrap());
    }
    #[tokio::test]
    async fn database_reopen_does_not_rearm() {
        let d = tempfile::tempdir().unwrap();
        let (f, a) = fixture_in(d.path());
        let url = format!(
            "sqlite://{}?mode=rwc",
            d.path().join("database/test.sqlite").display()
        );
        let p = pool(&url).await;
        let first = reserve(&p, &f, &a).await.unwrap();
        assert!(first.matches_owner(f.manifest.workspace, f.manifest.session));
        p.close().await;
        let reopened = SqlitePool::connect(&url).await.unwrap();
        let reloaded = decode_fixed(&serde_json::to_string(&f.manifest).unwrap())
            .unwrap()
            .unwrap();
        assert!(reserve(&reopened, &reloaded, &a).await.is_err());
        confirm_spawn(&reopened, &first).await.unwrap();
        assert!(reserve(&reopened, &f, &a).await.is_err());
    }
    #[tokio::test]
    async fn concurrent_duplicate_is_serialized() {
        let d = tempfile::tempdir().unwrap();
        let p = pool("sqlite::memory:").await;
        let (f, a) = fixture_in(d.path());
        let (x, y) = tokio::join!(reserve(&p, &f, &a), reserve(&p, &f, &a));
        assert_ne!(x.is_ok(), y.is_ok());
    }
    #[tokio::test]
    async fn drift_chain_and_expiry_refused() {
        let d = tempfile::tempdir().unwrap();
        let p = pool("sqlite::memory:").await;
        let (mut f, a) = fixture_in(d.path());
        let mut changed = a.clone();
        if let ExecutorActionType::CodingAgentInitialRequest(r) = &mut changed.typ {
            r.prompt = "other".into();
        }
        assert!(reserve(&p, &f, &changed).await.is_err());
        changed = a.clone();
        changed.next_action = Some(Box::new(a.clone()));
        assert!(!one_action(&changed));
        f.manifest.expires_at = wall_seconds() - 1;
        assert!(reserve(&p, &f, &a).await.is_err());
    }
    #[tokio::test]
    async fn post_setup_drift_and_uncertainty_hold() {
        let d = tempfile::tempdir().unwrap();
        let p = pool("sqlite::memory:").await;
        let (f, a) = fixture_in(d.path());
        let token = reserve(&p, &f, &a).await.unwrap();
        revalidate_after_setup(
            &p,
            &f,
            &token,
            "exact-input",
            "synthetic-dataset",
            &a,
            &a,
            &"a".repeat(64),
        )
        .await
        .unwrap();
        assert!(
            revalidate_after_setup(
                &p,
                &f,
                &token,
                "exact-input",
                "synthetic-dataset",
                &a,
                &a,
                &"c".repeat(64)
            )
            .await
            .is_err()
        );
        assert!(reserve(&p, &f, &a).await.is_err());
        let state: String = sqlx::query_scalar("SELECT state FROM workspace_baseline_acceptance")
            .fetch_one(&p)
            .await
            .unwrap();
        assert_eq!(state, "spent_held");
    }
    #[tokio::test]
    async fn old_database_restore_cannot_replay() {
        let d = tempfile::tempdir().unwrap();
        let (f, a) = fixture_in(d.path());
        let first = pool("sqlite::memory:").await;
        let _ = reserve(&first, &f, &a).await.unwrap();
        let restored_old = pool("sqlite::memory:").await;
        assert!(
            reserve(&restored_old, &f, &a)
                .await
                .unwrap_err()
                .contains("witness")
        );
    }
    #[tokio::test]
    async fn crash_after_witness_before_database_stays_held() {
        let d = tempfile::tempdir().unwrap();
        let (f, a) = fixture_in(d.path());
        record_spent_witness(&f, Uuid::new_v4()).unwrap();
        let p = pool("sqlite::memory:").await;
        assert!(reserve(&p, &f, &a).await.unwrap_err().contains("witness"));
    }

    #[tokio::test]
    async fn startup_archive_preserves_spent_and_restored_database_hold() {
        let d = tempfile::tempdir().unwrap();
        let (f, a) = fixture_in(d.path());
        let p = pool("sqlite::memory:").await;
        let token = reserve(&p, &f, &a).await.unwrap();
        let original = serde_json::to_string(&f.manifest).unwrap();
        let archive = serde_json::to_string(&vec![original]).unwrap();
        let holds = parse_startup_holds("null", &archive).unwrap();
        verify_startup_holds(&p, &holds).await.unwrap();
        confirm_spawn(&p, &token).await.unwrap();
        verify_startup_holds(&p, &holds).await.unwrap();
        let old = pool("sqlite::memory:").await;
        assert!(
            verify_startup_holds(&old, &holds)
                .await
                .unwrap_err()
                .contains("old database restore")
        );
        assert!(
            verify_startup_holds(&p, &parse_startup_holds("null", "[]").unwrap())
                .await
                .is_err()
        );
    }
    #[tokio::test]
    async fn incomplete_witness_fails_closed_on_startup() {
        let d = tempfile::tempdir().unwrap();
        let (f, _) = fixture_in(d.path());
        let p = pool("sqlite::memory:").await;
        std::fs::write(witness_path(&f).unwrap(), b"partial").unwrap();
        let archive =
            serde_json::to_string(&vec![serde_json::to_string(&f.manifest).unwrap()]).unwrap();
        let holds = parse_startup_holds("null", &archive).unwrap();
        assert!(verify_startup_holds(&p, &holds).await.is_err());
    }
    #[test]
    fn archive_mismatch_and_unknown_witness_refuse() {
        let d = tempfile::tempdir().unwrap();
        let (f, _) = fixture_in(d.path());
        let original = serde_json::to_string(&f.manifest).unwrap();
        let mut changed = f.manifest.clone();
        changed.expires_at += 1;
        let archive =
            serde_json::to_string(&vec![serde_json::to_string(&changed).unwrap()]).unwrap();
        assert!(parse_startup_holds(&original, &archive).is_err());
        std::fs::write(d.path().join("unknown.spent"), b"unknown").unwrap();
        assert!(parse_startup_holds(&original, "[]").is_err());
    }
}
