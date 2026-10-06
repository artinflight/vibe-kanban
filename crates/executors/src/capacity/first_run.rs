//! Identity and evidence gates for the one supervised first native turn.
//! Discovery is read-only; only the native worker can attest a root checkpoint.
use std::{fs, io, path::Path};

use serde::{Deserialize, Serialize};
use sqlx::{
    Connection, Row,
    sqlite::{SqliteConnectOptions, SqliteConnection},
};
use ts_rs::TS;
use uuid::Uuid;

use crate::executors::codex::{
    codex_home,
    goals::{NativeGoal, Progress, progress_path},
};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize, TS)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct FirstRun {
    pub goal_id: String,
    pub thread_id: String,
    pub objective: String,
    pub created_at: i64,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum InitializationState {
    Pending,
    #[default]
    Checkpointed,
    Held,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Binding {
    pub workspace_id: Uuid,
    pub workspace_root: String,
    pub agent_working_dir: Option<String>,
    pub account_home: String,
    pub database: String,
    pub anchor_execution_id: Uuid,
    pub anchor_turn_id: Uuid,
    pub anchor_message_id: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Receipt {
    pub grant_id: Uuid,
    pub execution_id: Option<Uuid>,
    pub checkpoint_turn_id: Option<String>,
}

fn invalid(message: &str) -> io::Error {
    io::Error::other(message)
}
fn db_error(error: sqlx::Error) -> io::Error {
    invalid(&error.to_string())
}

pub fn enabled() -> bool {
    // Rollout owner sets this only after compatible CU is deployed.
    std::env::var("VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION").as_deref() == Ok("1")
}

impl FirstRun {
    pub fn from_native(native: &NativeGoal) -> Self {
        Self {
            goal_id: native.goal_id.clone(),
            thread_id: native.thread_id.clone(),
            objective: native.objective.clone(),
            created_at: native.created_at,
        }
    }
    pub fn validate(&self) -> io::Result<()> {
        Uuid::parse_str(&self.goal_id).map_err(io::Error::other)?;
        progress_path(&self.thread_id)?;
        if self.objective.trim().is_empty() || self.objective.len() > 16_000 || self.created_at <= 0
        {
            return Err(invalid("Invalid native first-run identity"));
        }
        Ok(())
    }
}

/// Absent means ENOENT only. Never replace corrupt/empty/mismatched evidence.
pub fn read_progress(native: &NativeGoal) -> io::Result<Option<Progress>> {
    match fs::read(progress_path(&native.thread_id)?) {
        Ok(bytes) => {
            let p: Progress = serde_json::from_slice(&bytes)?;
            if p.objective != native.objective || p.created_at != native.created_at {
                return Err(invalid("Native goal and checkpoint identity differ"));
            }
            Ok(Some(p))
        }
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(e),
    }
}

pub fn valid_checklist(p: &Progress) -> io::Result<()> {
    if p.requirements.is_empty()
        || p.requirements.len() > 100
        || p.requirements
            .iter()
            .chain(p.completed.iter())
            .any(|(id, text)| {
                id.trim().is_empty()
                    || id.len() > 100
                    || text.trim().is_empty()
                    || text.len() > 4000
            })
        || p.completed
            .keys()
            .any(|id| !p.requirements.contains_key(id))
    {
        return Err(invalid("A real nonempty native checklist is required"));
    }
    Ok(())
}

pub fn classify(
    native: &NativeGoal,
    progress: Option<&Progress>,
) -> io::Result<InitializationState> {
    FirstRun::from_native(native).validate()?;
    match progress {
        Some(p) => {
            valid_checklist(p)?;
            super::controller::validate_native_readiness(native, p)?;
            Ok(InitializationState::Checkpointed)
        }
        None if native.status == "paused" && enabled() => Ok(InitializationState::Pending),
        None => Err(invalid(
            "Only an existing paused goal with absent progress can queue its first run",
        )),
    }
}

pub async fn native(thread: &str) -> io::Result<NativeGoal> {
    let home = codex_home().ok_or_else(|| invalid("Codex home unavailable"))?;
    let mut db = SqliteConnection::connect_with(
        &SqliteConnectOptions::new()
            .filename(home.join("goals_1.sqlite"))
            .read_only(true)
            .create_if_missing(false),
    )
    .await
    .map_err(db_error)?;
    let row = sqlx::query(
        "SELECT goal_id,objective,status,created_at_ms FROM thread_goals WHERE thread_id=?",
    )
    .bind(thread)
    .fetch_optional(&mut db)
    .await
    .map_err(db_error)?
    .ok_or_else(|| invalid("Native goal no longer exists"))?;
    let stored: String = row.try_get("status").map_err(db_error)?;
    Ok(NativeGoal {
        goal_id: row.try_get("goal_id").map_err(db_error)?,
        thread_id: thread.into(),
        objective: row.try_get("objective").map_err(db_error)?,
        created_at: row.try_get::<i64, _>("created_at_ms").map_err(db_error)? / 1000,
        status: match stored.as_str() {
            "usage_limited" => "usageLimited".into(),
            "budget_limited" => "budgetLimited".into(),
            _ => stored,
        },
    })
}

/// Installed Codex wire versions can omit goal_id. Resolve it from the same
/// original home, and require the wire identity to match before filling it in.
pub async fn resolve_wire(mut wire: NativeGoal) -> io::Result<NativeGoal> {
    let stored = native(&wire.thread_id).await?;
    if stored.objective != wire.objective
        || stored.created_at != wire.created_at
        || (!wire.goal_id.is_empty() && stored.goal_id != wire.goal_id)
    {
        return Err(invalid("Native wire/database identity differs"));
    }
    wire.goal_id = stored.goal_id;
    Ok(wire)
}

/// Current session, workspace, completed-turn anchor and original account home.
/// The worker excludes only its own new execution from the running-session gate.
pub async fn binding(
    database: &Path,
    session: Uuid,
    thread: &str,
    own: Option<Uuid>,
) -> io::Result<Binding> {
    let mut db = SqliteConnection::connect_with(
        &SqliteConnectOptions::new()
            .filename(database)
            .read_only(true)
            .create_if_missing(false),
    )
    .await
    .map_err(db_error)?;
    let row = sqlx::query("SELECT w.id,w.container_ref,w.archived,w.worktree_deleted,s.executor,s.agent_working_dir FROM sessions s JOIN workspaces w ON w.id=s.workspace_id WHERE s.id=?")
        .bind(session).fetch_optional(&mut db).await.map_err(db_error)?
        .ok_or_else(|| invalid("Session/workspace no longer exists"))?;
    if row.try_get::<bool, _>("archived").map_err(db_error)?
        || row
            .try_get::<bool, _>("worktree_deleted")
            .map_err(db_error)?
        || !row
            .try_get::<String, _>("executor")
            .map_err(db_error)?
            .eq_ignore_ascii_case("codex")
    {
        return Err(invalid("Workspace/executor unavailable"));
    }
    let workspace_id: Uuid = row.try_get("id").map_err(db_error)?;
    let root: String = row
        .try_get::<Option<String>, _>("container_ref")
        .map_err(db_error)?
        .ok_or_else(|| invalid("Existing workspace directory required"))?;
    let running: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes ep JOIN sessions s ON s.id=ep.session_id WHERE s.workspace_id=? AND ep.status='running' AND ep.run_reason='codingagent' AND ep.dropped=0 AND (? IS NULL OR ep.id!=?)")
        .bind(workspace_id).bind(own).bind(own).fetch_one(&mut db).await.map_err(db_error)?;
    if running != 0 {
        return Err(invalid("Workspace already has a running session"));
    }
    let anchor = sqlx::query("SELECT ep.id AS execution_id,cat.id AS turn_id,cat.agent_session_id,cat.agent_message_id FROM execution_processes ep JOIN coding_agent_turns cat ON cat.execution_process_id=ep.id WHERE ep.session_id=? AND ep.run_reason='codingagent' AND ep.dropped=0 AND ep.status='completed' AND ep.exit_code=0 AND cat.agent_session_id IS NOT NULL AND cat.summary IS NOT NULL AND trim(cat.summary)!='' ORDER BY ep.created_at DESC LIMIT 1")
        .bind(session).fetch_optional(&mut db).await.map_err(db_error)?
        .ok_or_else(|| invalid("No completed native turn anchor"))?;
    if anchor
        .try_get::<String, _>("agent_session_id")
        .map_err(db_error)?
        != thread
    {
        return Err(invalid("Completed-turn native thread changed"));
    }
    Ok(Binding {
        workspace_id,
        workspace_root: fs::canonicalize(root)?.to_string_lossy().into_owned(),
        agent_working_dir: row.try_get("agent_working_dir").map_err(db_error)?,
        account_home: fs::canonicalize(
            codex_home().ok_or_else(|| invalid("Codex home unavailable"))?,
        )?
        .to_string_lossy()
        .into_owned(),
        database: fs::canonicalize(database)?.to_string_lossy().into_owned(),
        anchor_execution_id: anchor.try_get("execution_id").map_err(db_error)?,
        anchor_turn_id: anchor.try_get("turn_id").map_err(db_error)?,
        anchor_message_id: anchor.try_get("agent_message_id").map_err(db_error)?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn absent_is_distinct_from_empty_held_completed_or_mismatched_progress() {
        let native = NativeGoal {
            goal_id: Uuid::new_v4().to_string(),
            thread_id: Uuid::new_v4().to_string(),
            objective: "Deliver the full outcome".into(),
            created_at: 123,
            status: "paused".into(),
        };
        assert_eq!(classify(&native, None).is_ok(), enabled());
        let mut p = Progress {
            objective: native.objective.clone(),
            created_at: native.created_at,
            ..Default::default()
        };
        assert!(classify(&native, Some(&p)).is_err());
        p.requirements
            .insert("delivery".into(), "Verify the outcome".into());
        assert_eq!(
            classify(&native, Some(&p)).unwrap(),
            InitializationState::Checkpointed
        );
        p.pause_reason = Some("Required input".into());
        assert!(classify(&native, Some(&p)).is_err());
        p.pause_reason = None;
        p.completed.insert("delivery".into(), "Verified".into());
        assert!(classify(&native, Some(&p)).is_err());
        p.completed.clear();
        p.objective.push('!');
        assert!(classify(&native, Some(&p)).is_err());
        for status in [
            "active",
            "complete",
            "blocked",
            "budgetLimited",
            "usageLimited",
        ] {
            let mut stopped = native.clone();
            stopped.status = status.into();
            assert!(classify(&stopped, None).is_err());
        }
    }
    #[test]
    fn corrupt_and_empty_files_never_qualify_as_missing() {
        // File-writing acceptance runs only under the explicit offline boundary.
        if !enabled() {
            return;
        }
        let native = NativeGoal {
            goal_id: Uuid::new_v4().to_string(),
            thread_id: Uuid::new_v4().to_string(),
            objective: "Deliver the full outcome".into(),
            created_at: 123,
            status: "paused".into(),
        };
        let path = progress_path(&native.thread_id).unwrap();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        assert!(read_progress(&native).unwrap().is_none());
        fs::write(&path, b"{}").unwrap();
        assert!(read_progress(&native).is_err());
        fs::write(&path, b"").unwrap();
        assert!(read_progress(&native).is_err());
        let p = Progress {
            objective: native.objective.clone(),
            created_at: native.created_at,
            ..Default::default()
        };
        fs::write(&path, serde_json::to_vec(&p).unwrap()).unwrap();
        assert!(read_progress(&native).unwrap().is_some());
        assert!(classify(&native, read_progress(&native).unwrap().as_ref()).is_err());
        fs::remove_file(path).unwrap();
    }
}
