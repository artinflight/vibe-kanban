//! Fixed release-adopted authority inside the existing trusted backend boundary.
//! A digest is integrity evidence, not consent. No agent-facing grant mutation API.
use std::{
    io,
    path::PathBuf,
    sync::{Arc, OnceLock},
};

use executors::{
    actions::{ExecutorAction, ExecutorActionType},
    profile::ExecutorConfig,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sqlx::SqlitePool;
use uuid::Uuid;

use super::admission;

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub input_seal: inputs::InputSeal,
    pub session: Uuid,
    pub workspace: Uuid,
    pub thread: String,
    pub root: PathBuf,
    pub working_dir: Option<String>,
    pub task: Option<Uuid>,
    pub repositories: Vec<Uuid>,
    pub config: ExecutorConfig,
    /// Effective saved profile, including launch and permission settings.
    pub profile_digest: String,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AssetPin {
    pub path: PathBuf,
    pub sha256: String,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contract {
    pub recommend: executors::routing::RoutingPolicy,
    pub id: Uuid,
    pub manager: Identity,
    pub worker: Identity,
    pub goal_id: String,
    pub goal_created_at: i64,
    pub objective: String,
    pub revision: String,
    pub instructions: String,
    pub owner_evidence_digest: String,
    pub manager_anchor: Uuid,
    pub worker_anchor: Uuid,
    pub assets: Vec<AssetPin>,
}

impl Contract {
    pub fn validate(&self) -> io::Result<()> {
        if self.id.is_nil()
            || self.recommend.mode != executors::routing::RoutingMode::Shadow
            || self.manager.session == self.worker.session
            || self.manager.workspace == self.worker.workspace
            || self.goal_id.is_empty()
            || self.objective.trim().is_empty()
            || self.revision.is_empty()
            || self.instructions.trim().is_empty()
            || self.instructions.len() > 48 * 1024
            || self.owner_evidence_digest.len() != 64
            || self.assets.is_empty()
            || self.assets.len() > 64
        {
            return Err(invalid("Incomplete fixed contract"));
        }
        for identity in [&self.manager, &self.worker] {
            if identity.thread.is_empty()
                || !identity.root.is_absolute()
                || identity.repositories.is_empty()
                || identity.profile_digest.len() != 64
                || identity.input_seal.coverage_id.is_nil()
                || identity.input_seal.backend_sequence < 0
                || identity.input_seal.prefix_digest.len() != 64
                || !identity.input_seal.rollout.is_absolute()
                || identity.config.executor != executors::executors::BaseCodingAgent::Codex
                || identity.config.model_id.as_deref() != Some("gpt-6.1-sol")
                || identity.config.reasoning_id.as_deref() != Some("high")
                || identity.config.variant.as_deref().unwrap_or("DEFAULT") != "DEFAULT"
                || identity
                    .config
                    .routing
                    .as_ref()
                    .is_some_and(|p| p.as_ref() != &self.recommend)
            {
                return Err(invalid(
                    "Fixed profile must preserve original Recommend settings",
                ));
            }
        }
        Ok(())
    }

    pub fn continuation(&self) -> String {
        format!(
            "Continue your original current revision goal under this fixed owner-authorized contract (revision {}).\n\n{}\n\nPreserve original profile/model/effort and Recommend routing, existing access/resource/capacity/collision guards and assets. Marketing dates use grey placeholders across headers, chart date axes and task dates; literal dates remain only in unchanged QA sources. Stop at owner review readiness. Figma/AE retain their existing review/approval gates. No new access, restarts, purchases, publication, destructive actions, unrelated targets or scope amendments are authorized. If new or ambiguous instructions conflict, stop for verified owner direction.",
            self.revision, self.instructions
        )
    }
}

pub fn invalid(message: &str) -> io::Error {
    io::Error::other(message)
}
pub fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn verify_profile(identity: &Identity) -> io::Result<()> {
    if effective_profile_digest(&identity.config)? != identity.profile_digest {
        return Err(invalid(
            "Original effective launch/permission profile changed",
        ));
    }
    Ok(())
}

pub fn effective_profile_digest(config: &ExecutorConfig) -> io::Result<String> {
    use executors::executors::StandardCodingAgentExecutor;
    let mut agent = executors::profile::ExecutorConfigs::get_cached()
        .get_coding_agent(&config.profile_id())
        .ok_or_else(|| invalid("Original effective profile unavailable"))?;
    agent.apply_overrides(config);
    // Hash only; never log profile contents, which can include environment data.
    executors::original_worker::profile_digest(&agent)
}

pub struct Ledger {
    activation: Arc<tokio::sync::Mutex<()>>,
    pub pool: SqlitePool,
    pub contract: Contract,
}
static LEDGER: OnceLock<Arc<Ledger>> = OnceLock::new();
tokio::task_local! { static ATTEMPT: Uuid; }
tokio::task_local! { static ACTIVATING: Uuid; }

pub fn current() -> Option<&'static Arc<Ledger>> {
    LEDGER.get()
}
pub fn in_dispatch() -> bool {
    ATTEMPT.try_with(|_| ()).is_ok()
}
pub fn register(ledger: Arc<Ledger>) -> io::Result<()> {
    LEDGER
        .set(ledger)
        .map_err(|_| invalid("Authority already registered"))
}

impl Ledger {
    pub async fn activation_fence(
        &self,
        checks: impl std::future::Future<Output = io::Result<()>>,
    ) -> io::Result<executors::original_worker::ActivationFence> {
        let fence = self.activation.clone().lock_owned().await;
        ACTIVATING.scope(self.contract.id, checks).await?;
        self.active().await?;
        Ok(fence)
    }

    pub async fn native_inputs(&self, identity: &Identity) -> io::Result<()> {
        let coverage: Option<Uuid> =
            sqlx::query_scalar("SELECT id FROM bounded_native_input_coverage WHERE singleton=1")
                .fetch_optional(&self.pool)
                .await
                .map_err(db_error)?;
        let latest: i64 =
            sqlx::query_scalar("SELECT COALESCE(max(id),0) FROM bounded_native_input_history")
                .fetch_one(&self.pool)
                .await
                .map_err(db_error)?;
        if coverage != Some(identity.input_seal.coverage_id)
            || latest < identity.input_seal.backend_sequence
        {
            self.end("suspended", "input_producer_coverage_changed")
                .await?;
            return Err(invalid(
                "Native input journal coverage changed or is unknown",
            ));
        }

        let unowned: i64 = sqlx::query_scalar("SELECT count(*) FROM bounded_native_input_history WHERE session_id=? AND id>? AND native_resume=0")
            .bind(identity.session).bind(identity.input_seal.backend_sequence).fetch_one(&self.pool).await.map_err(db_error)?;
        if unowned != 0 {
            self.end("suspended", "durable_input_amendment").await?;
            return Err(invalid("Input or steering accepted after contract capture"));
        }
        let allowed: Vec<String> = if identity.session == self.contract.worker.session {
            sqlx::query_scalar("SELECT input_digest FROM bounded_worker_attempts WHERE grant_id=? AND activated=1 AND input_digest IS NOT NULL ORDER BY rowid")
                .bind(self.contract.id).fetch_all(&self.pool).await.map_err(db_error)?
        } else {
            Vec::new()
        };
        let bytes = match inputs::read(&identity.thread, &identity.input_seal).await {
            Ok(bytes) => bytes,
            Err(_) => {
                self.end("suspended", "native_input_source_unavailable")
                    .await?;
                return Err(invalid("Native input freshness cannot be proved"));
            }
        };
        if inputs::verify(&bytes, &identity.input_seal, &allowed).is_err() {
            self.end("suspended", "native_input_freshness_unproved")
                .await?;
            return Err(invalid(
                "Unverified native input or steering after contract capture",
            ));
        }
        Ok(())
    }

    /// Covers all sessions in the original workspace and canonical worktree aliases.
    /// Queue snapshots and start callers must hold common admission.
    pub async fn workspace_idle(&self, queued: &[Uuid], own: Option<Uuid>) -> io::Result<()> {
        let roots: Vec<(Uuid, Option<String>)> =
            sqlx::query_as("SELECT id,container_ref FROM workspaces WHERE archived=FALSE AND worktree_deleted=FALSE")
                .fetch_all(&self.pool)
                .await
                .map_err(db_error)?;
        let mut shared = vec![self.contract.worker.workspace];
        for (id, root) in roots {
            if let Some(root) = root {
                let Ok(root) = PathBuf::from(root).canonicalize() else {
                    if id == self.contract.worker.workspace {
                        return Err(invalid("Original worktree ownership unknown"));
                    }
                    continue;
                };
                if root.starts_with(&self.contract.worker.root)
                    || self.contract.worker.root.starts_with(&root)
                {
                    shared.push(id);
                }
            }
        }
        let rows: Vec<(Uuid, Uuid, String)> = sqlx::query_as("SELECT e.id,s.workspace_id,e.run_reason FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.status='running' AND e.dropped=FALSE")
            .fetch_all(&self.pool).await.map_err(db_error)?;
        if rows
            .iter()
            .any(|(id, w, reason)| Some(*id) != own && shared.contains(w) && reason != "devserver")
        {
            return Err(invalid(
                "Original worker workspace/worktree is already running",
            ));
        }
        for session in queued {
            let workspace: Uuid =
                sqlx::query_scalar("SELECT workspace_id FROM sessions WHERE id=?")
                    .bind(session)
                    .fetch_one(&self.pool)
                    .await
                    .map_err(db_error)?;
            if shared.contains(&workspace) {
                return Err(invalid(
                    "Original worker workspace/worktree has queued input",
                ));
            }
        }
        Ok(())
    }

    pub async fn worker_history(&self) -> io::Result<()> {
        let rows: Vec<(Uuid, bool)> = sqlx::query_as("SELECT id,dropped FROM execution_processes WHERE session_id=? AND run_reason='codingagent' AND rowid >= (SELECT rowid FROM execution_processes WHERE id=? AND session_id=?)")
            .bind(self.contract.worker.session).bind(self.contract.worker_anchor).bind(self.contract.worker.session).fetch_all(&self.pool).await.map_err(db_error)?;
        if rows.is_empty() {
            return Err(invalid("Worker history anchor missing"));
        }
        for (id, dropped) in rows {
            let owned = id == self.contract.worker_anchor
                || sqlx::query_scalar::<_, i64>(
                    "SELECT count(*) FROM bounded_worker_attempts WHERE grant_id=? AND execution=?",
                )
                .bind(self.contract.id)
                .bind(id)
                .fetch_one(&self.pool)
                .await
                .map_err(db_error)?
                    == 1;
            if dropped || !owned {
                self.end("suspended", "worker_history_amended").await?;
                return Err(invalid("Worker input history changed"));
            }
        }
        Ok(())
    }

    pub async fn activate_input(&self, execution: Uuid, input: &str) -> io::Result<()> {
        let n = sqlx::query("UPDATE bounded_worker_attempts SET activated=1,input_digest=? WHERE grant_id=? AND execution=? AND state='dispatching' AND activated=0")
            .bind(digest(input.as_bytes())).bind(self.contract.id).bind(execution).execute(&self.pool).await.map_err(db_error)?.rows_affected();
        if n != 1 {
            return Err(invalid(
                "Native activation already consumed or outcome uncertain",
            ));
        }
        Ok(())
    }
    /// Catch input accepted before this optional capability was loaded, too.
    /// Only native resume may follow the release-adopted manager anchor.
    pub async fn manager_history(&self) -> io::Result<()> {
        let rows: Vec<(Option<String>, bool)> = sqlx::query_as("SELECT executor_action,dropped FROM execution_processes WHERE session_id=? AND run_reason='codingagent' AND rowid > (SELECT rowid FROM execution_processes WHERE id=? AND session_id=?) ORDER BY rowid")
            .bind(self.contract.manager.session).bind(self.contract.manager_anchor)
            .bind(self.contract.manager.session).fetch_all(&self.pool).await.map_err(db_error)?;
        let anchor: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes WHERE id=? AND session_id=? AND run_reason='codingagent' AND dropped=FALSE")
            .bind(self.contract.manager_anchor).bind(self.contract.manager.session).fetch_one(&self.pool).await.map_err(db_error)?;
        let valid = anchor == 1 && rows.iter().all(|(json,dropped)| {
            !dropped &&
            json.as_deref().and_then(|v| serde_json::from_str::<ExecutorAction>(v).ok()).is_some_and(|action| {
                matches!(action.typ(), ExecutorActionType::CodingAgentFollowUpRequest(a)
                    if a.prompt.trim() == "/goal resume" && a.session_id == self.contract.manager.thread
                    && a.executor_config == self.contract.manager.config && a.capacity.is_none()
                    && a.reset_to_message_id.is_none())
            })
        });
        if !valid {
            self.end("suspended", "manager_history_amended_or_unknown")
                .await?;
            return Err(invalid("Unverified manager input after adopted anchor"));
        }
        Ok(())
    }

    pub async fn caller(
        &self,
        caller: Uuid,
        native: &(String, String, String, String, String),
    ) -> io::Result<()> {
        let row: (Uuid, Uuid, String, Uuid) = sqlx::query_as("SELECT e.session_id,s.workspace_id,e.status,(SELECT id FROM execution_processes WHERE session_id=e.session_id AND run_reason='codingagent' AND dropped=FALSE ORDER BY created_at DESC,rowid DESC LIMIT 1) FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.id=? AND e.dropped=FALSE")
            .bind(caller).fetch_one(&self.pool).await.map_err(db_error)?;
        if row.0 != self.contract.manager.session
            || row.1 != self.contract.manager.workspace
            || row.2 != "running"
            || row.3 != caller
            || native.0 != self.contract.manager.thread
            || native.1.is_empty()
            || native.2 != "gpt-6.1-sol"
            || native.3 != "high"
            || !native
                .4
                .split(|c: char| !c.is_ascii_digit() && c != '.')
                .any(|v| v == "0.159.2")
        {
            return Err(invalid(
                "Caller is not the attested original manager execution",
            ));
        }
        Ok(())
    }

    pub async fn goal(
        &self,
        goal: &executors::executors::codex::goals::NativeGoal,
    ) -> io::Result<()> {
        let c = &self.contract;
        if goal.status == "complete" || goal.status == "completed" {
            self.end("ready", "native_goal_completed").await?;
            return Err(invalid("Original goal ended"));
        }
        if goal.thread_id != c.manager.thread
            || goal.goal_id != c.goal_id
            || goal.created_at != c.goal_created_at
            || goal.objective != c.objective
        {
            self.end("suspended", "native_goal_amended_or_unknown")
                .await?;
            return Err(invalid(
                "Fixed native goal changed; verified owner direction required",
            ));
        }
        if goal.status != "active" {
            return Err(invalid("Original goal is not active"));
        }
        Ok(())
    }

    pub async fn bind_receipt(&self, attempt: Uuid, execution: Uuid) -> io::Result<()> {
        let n = sqlx::query("UPDATE bounded_worker_attempts SET execution=? WHERE id=? AND grant_id=? AND state='dispatching' AND execution IS NULL")
            .bind(execution).bind(attempt).bind(self.contract.id).execute(&self.pool).await.map_err(db_error)?.rows_affected();
        if n != 1 {
            return Err(invalid("Attempt receipt already bound"));
        }
        Ok(())
    }
    pub async fn adopt(pool: SqlitePool, contract: Contract) -> io::Result<Self> {
        contract.validate()?;
        let coverage: Uuid =
            sqlx::query_scalar("SELECT id FROM bounded_native_input_coverage WHERE singleton=1")
                .fetch_one(&pool)
                .await
                .map_err(|_| invalid("Contract capture predates proven input journal coverage"))?;
        if [&contract.manager, &contract.worker]
            .iter()
            .any(|identity| identity.input_seal.coverage_id != coverage)
        {
            return Err(invalid(
                "Contract input capture belongs to another or unproved producer epoch",
            ));
        }
        let latest: i64 =
            sqlx::query_scalar("SELECT COALESCE(max(id),0) FROM bounded_native_input_history")
                .fetch_one(&pool)
                .await
                .map_err(db_error)?;
        if [&contract.manager, &contract.worker]
            .iter()
            .any(|identity| identity.input_seal.backend_sequence > latest)
        {
            return Err(invalid("Input capture watermark exceeds producer evidence"));
        }
        let hash = digest(&serde_json::to_vec(&contract)?);
        let mut tx = pool.begin().await.map_err(db_error)?;
        sqlx::query("INSERT OR IGNORE INTO bounded_worker_grants(id,contract_digest,state) VALUES (?,?,'active')")
            .bind(contract.id).bind(&hash).execute(&mut *tx).await.map_err(db_error)?;
        let saved: String =
            sqlx::query_scalar("SELECT contract_digest FROM bounded_worker_grants WHERE id=?")
                .bind(contract.id)
                .fetch_one(&mut *tx)
                .await
                .map_err(db_error)?;
        if saved != hash {
            return Err(invalid("Existing authority cannot be amended"));
        }
        // Reservations never replay after backend loss. Reconciliation is by actual receipt.
        sqlx::query("UPDATE bounded_worker_attempts SET state='uncertain' WHERE grant_id=? AND state IN ('reserved','dispatching')")
            .bind(contract.id).execute(&mut *tx).await.map_err(db_error)?;
        tx.commit().await.map_err(db_error)?;
        Ok(Self {
            pool,
            contract,
            activation: Arc::new(tokio::sync::Mutex::new(())),
        })
    }

    pub async fn terminal(&self) -> io::Result<bool> {
        let state: String =
            sqlx::query_scalar("SELECT state FROM bounded_worker_grants WHERE id=?")
                .bind(self.contract.id)
                .fetch_one(&self.pool)
                .await
                .map_err(db_error)?;
        Ok(matches!(state.as_str(), "revoked" | "ready" | "suspended"))
    }

    pub async fn active(&self) -> io::Result<()> {
        let state: String =
            sqlx::query_scalar("SELECT state FROM bounded_worker_grants WHERE id=?")
                .bind(self.contract.id)
                .fetch_one(&self.pool)
                .await
                .map_err(db_error)?;
        if state != "active" {
            return Err(invalid("Continuation authority is not active"));
        }
        Ok(())
    }

    pub async fn end(&self, state: &str, reason: &str) -> io::Result<()> {
        let _fence = if ACTIVATING
            .try_with(|id| *id == self.contract.id)
            .unwrap_or(false)
        {
            None
        } else {
            Some(self.activation.clone().lock_owned().await)
        };
        if !matches!(state, "revoked" | "ready" | "suspended") {
            return Err(invalid("Invalid terminal authority transition"));
        }
        sqlx::query("UPDATE bounded_worker_grants SET state=?,reason=? WHERE id=? AND state IN ('active','suspended')")
            .bind(state).bind(reason).bind(self.contract.id).execute(&self.pool).await.map_err(db_error)?;
        Ok(())
    }

    pub async fn reserve(&self, caller: Uuid, invocation: &str) -> io::Result<Uuid> {
        self.active().await?;
        if invocation.is_empty() || invocation.len() > 128 {
            return Err(invalid("Invalid invocation identity"));
        }
        let id = Uuid::new_v4();
        sqlx::query("INSERT INTO bounded_worker_attempts(id,grant_id,caller,invocation,state) VALUES (?,?,?,?,'reserved')")
            .bind(id).bind(self.contract.id).bind(caller).bind(invocation).execute(&self.pool).await.map_err(|_| invalid("Duplicate, concurrent or uncertain continuation"))?;
        Ok(id)
    }

    pub async fn dispatch<T>(
        &self,
        id: Uuid,
        work: impl std::future::Future<Output = io::Result<T>>,
    ) -> io::Result<T> {
        self.active().await?;
        let n = sqlx::query("UPDATE bounded_worker_attempts SET state='dispatching' WHERE id=? AND grant_id=? AND state='reserved'")
            .bind(id).bind(self.contract.id).execute(&self.pool).await.map_err(db_error)?.rows_affected();
        if n != 1 {
            return Err(invalid("Attempt cannot dispatch twice"));
        }
        let result = ATTEMPT.scope(id, work).await;
        if result.is_err() {
            sqlx::query("UPDATE bounded_worker_attempts SET state='uncertain' WHERE id=? AND state='dispatching'")
                .bind(id).execute(&self.pool).await.map_err(db_error)?;
        }
        result
    }

    pub async fn reconcile(&self) -> io::Result<()> {
        // Only a durable completed successful execution can clear an attempt.
        // Missing, failed, running, killed and unreturned receipts remain closed.
        sqlx::query("UPDATE bounded_worker_attempts SET state='completed' WHERE grant_id=? AND state IN ('dispatching','uncertain') AND execution IN (SELECT id FROM execution_processes WHERE status='completed' AND exit_code=0 AND dropped=FALSE AND session_id=?)")
            .bind(self.contract.id).bind(self.contract.worker.session).execute(&self.pool).await.map_err(db_error)?;
        Ok(())
    }

    pub async fn owns_head(&self, head: Uuid) -> io::Result<bool> {
        Ok(head == self.contract.worker_anchor || sqlx::query_scalar::<_, i64>("SELECT count(*) FROM bounded_worker_attempts WHERE grant_id=? AND execution=? AND state='completed'")
            .bind(self.contract.id).bind(head).fetch_one(&self.pool).await.map_err(db_error)? == 1)
    }
}

fn db_error(_: sqlx::Error) -> io::Error {
    invalid("Continuation state unavailable")
}

/// All callers hold the common admission lock, including ordinary input paths.
/// Establish durable provenance even with the continuation feature disabled.
/// First adoption requires a release-owner snapshot taken after this producer
/// has begun journaling. A legacy history-only contract cannot prove pending
/// steering that the old backend accepted without persisting it.
pub async fn start_input_coverage(pool: &SqlitePool) -> io::Result<Uuid> {
    sqlx::query("INSERT OR IGNORE INTO bounded_native_input_coverage(singleton,id) VALUES (1,?)")
        .bind(Uuid::new_v4())
        .execute(pool)
        .await
        .map_err(db_error)?;
    sqlx::query_scalar("SELECT id FROM bounded_native_input_coverage WHERE singleton=1")
        .fetch_one(pool)
        .await
        .map_err(db_error)
}

pub async fn record_input(
    pool: &SqlitePool,
    session: Uuid,
    unchanged_native_resume: bool,
) -> io::Result<()> {
    if !in_dispatch() {
        sqlx::query(
            "INSERT INTO bounded_native_input_history(session_id,native_resume) VALUES (?,?)",
        )
        .bind(session)
        .bind(unchanged_native_resume)
        .execute(pool)
        .await
        .map_err(db_error)?;
    }
    Ok(())
}

/// Apply the sole-owner guard only to starts sharing the bound worker worktree.
pub async fn workspace_start(session: Uuid) -> io::Result<()> {
    let Some(ledger) = current() else {
        return Ok(());
    };
    if ledger.terminal().await? {
        return Ok(());
    }
    let root: (Uuid, Option<String>) = sqlx::query_as("SELECT w.id,w.container_ref FROM sessions s JOIN workspaces w ON w.id=s.workspace_id WHERE s.id=?")
        .bind(session).fetch_one(&ledger.pool).await.map_err(db_error)?;
    let shared = root.0 == ledger.contract.worker.workspace
        || root
            .1
            .as_ref()
            .and_then(|r| PathBuf::from(r).canonicalize().ok())
            .is_some_and(|r| {
                r.starts_with(&ledger.contract.worker.root)
                    || ledger.contract.worker.root.starts_with(&r)
            });
    if shared {
        ledger.workspace_idle(&[], None).await?;
    }
    Ok(())
}

pub async fn ordinary_input(session: Uuid, prompt: &str) -> io::Result<()> {
    if let Some(ledger) = current()
        && (session == ledger.contract.worker.session || session == ledger.contract.manager.session)
        && ATTEMPT.try_with(|_| ()).is_err()
        && !(session == ledger.contract.manager.session && prompt.trim() == "/goal resume")
    {
        ledger.end("suspended", "new_or_ambiguous_input").await?;
    }
    Ok(())
}

/// Apply effective Recommend only to a temporary resolver copy. Persist and
/// launch the exact original raw configuration (which may omit routing).
pub fn routing_action(action: &ExecutorAction) -> ExecutorAction {
    let mut action = action.clone();
    if in_dispatch()
        && let Some(ledger) = current()
        && let ExecutorActionType::CodingAgentFollowUpRequest(request) = &mut action.typ
    {
        request.executor_config.routing = Some(Box::new(ledger.contract.recommend.clone()));
    }
    action
}

pub fn restore_raw_action(
    action: &mut ExecutorAction,
    original: &ExecutorAction,
) -> io::Result<()> {
    if in_dispatch() {
        if action
            .routing_decision
            .as_ref()
            .is_none_or(|d| d.mode != executors::routing::RoutingMode::Shadow)
        {
            return Err(invalid(
                "Bounded effective Recommend resolution unavailable",
            ));
        }
        action.typ = original.typ.clone();
    }
    Ok(())
}

pub async fn before_start(session: Uuid, action: &ExecutorAction) -> io::Result<()> {
    let Some(ledger) = current() else {
        return Ok(());
    };
    workspace_start(session).await?;
    if let Ok(id) = ATTEMPT.try_with(|id| *id) {
        ledger.before_bounded_start(id, session, action).await
    } else {
        let prompt = match action.typ() {
            ExecutorActionType::CodingAgentInitialRequest(a) => &a.prompt,
            ExecutorActionType::CodingAgentFollowUpRequest(a) => &a.prompt,
            ExecutorActionType::ReviewRequest(a) => &a.prompt,
            _ => return Ok(()),
        };
        ordinary_input(session, prompt).await
    }
}

impl Ledger {
    /// The exact gate called by ContainerService before creating/spawning work.
    pub async fn before_bounded_start(
        &self,
        id: Uuid,
        session: Uuid,
        action: &ExecutorAction,
    ) -> io::Result<()> {
        let ledger = self;
        ledger.active().await?;
        match action.typ() {
            ExecutorActionType::CodingAgentFollowUpRequest(a)
                if session == ledger.contract.worker.session
                    && a.session_id == ledger.contract.worker.thread
                    && a.prompt == ledger.contract.continuation()
                    && a.executor_config == ledger.contract.worker.config
                    && a.working_dir == ledger.contract.worker.working_dir
                    && a.capacity.is_none()
                    && a.reset_to_message_id.is_none() =>
            {
                let state: String = sqlx::query_scalar(
                    "SELECT state FROM bounded_worker_attempts WHERE id=? AND grant_id=?",
                )
                .bind(id)
                .bind(ledger.contract.id)
                .fetch_one(&ledger.pool)
                .await
                .map_err(db_error)?;
                if state != "dispatching" {
                    return Err(invalid("Invalid dispatch reservation"));
                }
                Ok(())
            }
            _ => Err(invalid("Bounded dispatch action changed")),
        }
    }
}

/// Persist receipt before process spawn, so transport loss cannot create a blind retry.
pub async fn record_execution(execution: Uuid) -> io::Result<()> {
    if let (Some(ledger), Ok(attempt)) = (current(), ATTEMPT.try_with(|id| *id)) {
        ledger.bind_receipt(attempt, execution).await?;
    }
    Ok(())
}

pub async fn serialized<T>(work: impl std::future::Future<Output = T>) -> T {
    admission::run(work).await
}

#[executors::original_worker::async_trait]
pub trait Runtime: Send + Sync {
    async fn prepare(&self) -> io::Result<()>;
    async fn check(&self, caller: Uuid) -> io::Result<()>;
    async fn admit(&self) -> io::Result<()>;
    async fn dispatch(&self) -> io::Result<Uuid>;
}

pub struct Engine {
    pub ledger: Arc<Ledger>,
    pub runtime: Arc<dyn Runtime>,
}

impl Engine {
    /// Exact backend side of the process-scoped stdio proxy, also exercised in
    /// isolated socket fixtures. The caller comes from bind(), never the frame.
    #[cfg(unix)]
    pub async fn serve_connection(
        &self,
        caller: Uuid,
        token: &str,
        mut stream: tokio::net::UnixStream,
    ) {
        use tokio::io::{AsyncReadExt, AsyncWriteExt};
        let mut bytes = Vec::new();
        let read = tokio::time::timeout(
            std::time::Duration::from_secs(5),
            (&mut stream)
                .take(executors::original_worker::LIMIT as u64 + 1)
                .read_to_end(&mut bytes),
        )
        .await;
        if !matches!(read, Ok(Ok(_))) || bytes.len() > executors::original_worker::LIMIT {
            return;
        }
        let Ok(wire) = serde_json::from_slice::<serde_json::Value>(&bytes) else {
            return;
        };
        if wire["token"].as_str() != Some(token)
            || wire
                .as_object()
                .is_none_or(|v| v.keys().any(|k| !matches!(k.as_str(), "token" | "request")))
        {
            return;
        }
        let request = wire["request"].clone();
        let reply = self
            .handle(caller, request.clone())
            .await
            .unwrap_or_else(|_| {
                executors::original_worker::error(
                    &request,
                    "Continuation blocked; no permission granted. Inspect backend state.",
                )
            });
        if let Ok(reply) = serde_json::to_vec(&reply) {
            let _ = stream.write_all(&reply).await;
        }
    }

    pub async fn handle(
        &self,
        caller: Uuid,
        request: serde_json::Value,
    ) -> io::Result<serde_json::Value> {
        use executors::original_worker::{READY, REVOKE, TOOL, tool};
        let name = tool(&request)?;
        let id = request
            .get("id")
            .filter(|v| v.is_string() || v.is_number())
            .ok_or_else(|| invalid("Missing invocation identity"))?;
        if name == TOOL {
            self.runtime.prepare().await?;
        }
        admission::locked(async {
            self.runtime.check(caller).await?;
            if name != TOOL {
                self.ledger.end(if name == READY { "ready" } else if name == REVOKE { "revoked" } else { return Err(invalid("Unsupported action")); }, "explicit_terminal_decision").await?;
                return Ok(serde_json::json!({"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text":"Continuation authority ended permanently."}],"isError":false}}));
            }
            self.ledger.active().await?;
            self.ledger.reconcile().await?;
            self.runtime.admit().await?;
            let attempt = self.ledger.reserve(caller, &id.to_string()).await?;
            let execution = self.ledger.dispatch(attempt, self.runtime.dispatch()).await?;
            let n = sqlx::query("UPDATE bounded_worker_attempts SET execution=? WHERE id=? AND state='dispatching' AND (execution IS NULL OR execution=?)")
                .bind(execution).bind(attempt).bind(execution).execute(&self.ledger.pool).await.map_err(db_error)?.rows_affected();
            if n != 1 { return Err(invalid("Dispatch receipt mismatch; reconciliation required")); }
            Ok(serde_json::json!({"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text":serde_json::json!({"attempt_id":attempt,"execution_id":execution,"state":"dispatching"}).to_string()}],"isError":false}}))
        }).await
    }
}

pub mod inputs;
#[cfg(test)]
mod tests;
