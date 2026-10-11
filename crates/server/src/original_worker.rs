//! Release-adopted fixed grant. Backend/state integrity is the existing trust
//! boundary; this is not independent custody against backend-host compromise.
use std::{
    io,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};

use axum::{Extension, Json, extract::State};
use db::models::{execution_process::ExecutionProcess, session::Session, workspace::Workspace};
use deployment::Deployment;
use executors::{
    actions::ExecutorAction,
    env::ExecutionEnv,
    original_worker::{Backend, Transport},
};
use serde_json::Value;
use services::services::original_worker::{
    Contract, Engine, Identity, Ledger, Runtime, digest, invalid,
};
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::{
    DeploymentImpl,
    routes::sessions::{CreateFollowUpAttempt, follow_up_admitted},
};

pub async fn configure(deployment: DeploymentImpl) -> io::Result<()> {
    services::services::original_worker::start_input_coverage(&deployment.db().pool).await?;
    let Ok(path) = std::env::var("VK_BOUNDED_WORKER_CONTRACT") else {
        return Ok(());
    };
    #[cfg(not(unix))]
    {
        let _ = (deployment, path);
        return Err(invalid("Bounded stdio requires Unix"));
    }
    #[cfg(unix)]
    {
        let expected = std::env::var("VK_BOUNDED_WORKER_CONTRACT_SHA256")
            .map_err(|_| invalid("Missing release-adopted contract pin"))?;
        let path = std::path::Path::new(&path).canonicalize()?;
        let metadata = tokio::fs::metadata(&path).await?;
        if !metadata.is_file() || metadata.len() > 64 * 1024 {
            return Err(invalid("Invalid private contract size"));
        }
        let bytes = tokio::fs::read(&path).await?;
        if digest(&bytes) != expected {
            return Err(invalid("Private contract does not match adopted release"));
        }
        let contract: Contract =
            serde_json::from_slice(&bytes).map_err(|_| invalid("Invalid private contract"))?;
        // Startup settings are adopted by the release owner from verified dot
        // consent. Never accept this payload or digest from an agent/API request.
        for root in [&contract.manager.root, &contract.worker.root] {
            if path.starts_with(root) {
                return Err(invalid("Contract cannot be loaded from an agent worktree"));
            }
        }
        let ledger = Arc::new(Ledger::adopt(deployment.db().pool.clone(), contract).await?);
        let runtime = Arc::new(Live {
            deployment,
            ledger: ledger.clone(),
            sampled: Mutex::new(None),
            resources: Arc::new(HostResources),
        });
        let engine = Arc::new(Engine {
            ledger: ledger.clone(),
            runtime: runtime.clone(),
        });
        services::services::original_worker::register(ledger)?;
        executors::original_worker::register(Arc::new(Provider { runtime, engine }))?;
        Ok(())
    }
}

struct Live<D: Deployment = DeploymentImpl> {
    deployment: D,
    resources: Arc<dyn ResourceProbe>,
    ledger: Arc<Ledger>,
    sampled: Mutex<Option<(Instant, u64)>>,
}

impl<D: Deployment> Live<D> {
    async fn identity(&self, expected: &Identity) -> io::Result<(Session, Uuid)> {
        let pool = &self.deployment.db().pool;
        let session = Session::find_by_id(pool, expected.session)
            .await
            .map_err(|_| invalid("Session lookup unavailable"))?
            .ok_or_else(|| invalid("Original session missing"))?;
        let workspace = Workspace::find_by_id(pool, session.workspace_id)
            .await
            .map_err(|_| invalid("Workspace lookup unavailable"))?
            .ok_or_else(|| invalid("Original workspace missing"))?;
        let mut repositories: Vec<Uuid> = sqlx::query_scalar(
            "SELECT repo_id FROM workspace_repos WHERE workspace_id=? ORDER BY repo_id",
        )
        .bind(workspace.id)
        .fetch_all(pool)
        .await
        .map_err(|_| invalid("Repository ownership unknown"))?;
        let mut expected_repositories = expected.repositories.clone();
        repositories.sort();
        expected_repositories.sort();
        if session.workspace_id != expected.workspace
            || workspace.task_id != expected.task
            || repositories != expected_repositories
            || workspace.archived
            || workspace.worktree_deleted
            || session.agent_working_dir != expected.working_dir
            || workspace
                .container_ref
                .as_deref()
                .map(std::path::Path::new)
                .is_none_or(|p| p.canonicalize().ok().as_ref() != Some(&expected.root))
        {
            return Err(invalid("Original workspace binding changed"));
        }
        let row: (Uuid, String) = sqlx::query_as("SELECT id,executor_action FROM execution_processes WHERE session_id=? AND run_reason='codingagent' AND dropped=FALSE ORDER BY created_at DESC,rowid DESC LIMIT 1")
            .bind(session.id).fetch_one(pool).await.map_err(|_| invalid("Original execution anchor unavailable"))?;
        let action: ExecutorAction = serde_json::from_str(&row.1)
            .map_err(|_| invalid("Execution configuration unavailable"))?;
        if executors::routing::config(&action) != Some(&expected.config) {
            return Err(invalid("Original profile/configuration changed"));
        }
        let info = db::models::coding_agent_turn::CodingAgentTurn::find_latest_session_info(
            pool, session.id,
        )
        .await
        .map_err(|_| invalid("Native resume anchor unavailable"))?
        .ok_or_else(|| invalid("Missing original native thread"))?;
        if info.session_id != expected.thread {
            return Err(invalid("Original native thread changed"));
        }
        Ok((session, row.0))
    }

    async fn goal(&self) -> io::Result<()> {
        let c = &self.ledger.contract;
        let goal = executors::capacity::first_run::native(&c.manager.thread).await?;
        self.ledger.goal(&goal).await
    }

    async fn resource_freshness(&self) -> io::Result<()> {
        let sample = *self.sampled.lock().await;
        let (_, baseline) = sample
            .filter(|(stamp, _)| stamp.elapsed() <= Duration::from_secs(10))
            .ok_or_else(|| invalid("Resource evidence is stale"))?;
        if self.resources.sample().await? != baseline {
            return Err(invalid("Swap activity changed before native activation"));
        }
        Ok(())
    }

    async fn assets(&self) -> io::Result<()> {
        for pin in &self.ledger.contract.assets {
            let path = pin.path.canonicalize()?;
            let metadata = tokio::fs::metadata(&path).await?;
            if path != pin.path
                || !metadata.is_file()
                || metadata.len() > 128 * 1024 * 1024
                || digest(&tokio::fs::read(&path).await?) != pin.sha256
            {
                return Err(invalid("Required asset/access pin changed"));
            }
        }
        Ok(())
    }
}

#[executors::original_worker::async_trait]
impl<D: Deployment> Runtime for Live<D> {
    async fn prepare(&self) -> io::Result<()> {
        // No admission lock while sampling; ordinary input/lifecycle reads remain live.
        let mut previous = None;
        for index in 0..3 {
            let sample = self.resources.sample().await?;
            if previous.is_some_and(|p| p != sample) {
                return Err(invalid("Swap out activity blocks continuation"));
            }
            previous = Some(sample);
            if index != 2 {
                tokio::time::sleep(self.resources.interval()).await;
            }
        }
        *self.sampled.lock().await = Some((
            Instant::now(),
            previous.ok_or_else(|| invalid("Missing sample"))?,
        ));
        Ok(())
    }

    async fn check(&self, caller: Uuid) -> io::Result<()> {
        self.ledger.active().await?;
        self.ledger.manager_history().await?;
        self.ledger
            .native_inputs(&self.ledger.contract.manager)
            .await?;
        let (session, head) = self.identity(&self.ledger.contract.manager).await?;
        let process = ExecutionProcess::find_by_id(&self.deployment.db().pool, caller)
            .await
            .map_err(|_| invalid("Caller lookup unavailable"))?
            .ok_or_else(|| invalid("Caller missing"))?;
        if process.session_id != session.id
            || head != caller
            || process.status != db::models::execution_process::ExecutionProcessStatus::Running
        {
            return Err(invalid(
                "Caller is not the bound original manager execution",
            ));
        }
        let native =
            executors::executors::codex::client::original_worker_attestation(caller).await?;
        self.ledger.caller(caller, &native).await?;
        self.goal().await
    }

    async fn admit(&self) -> io::Result<()> {
        executors::capacity::controller::before_bounded_worker_launch().await?;
        let sample = *self.sampled.lock().await;
        if sample.is_none_or(|(stamp, _)| stamp.elapsed() > Duration::from_secs(10)) {
            return Err(invalid("Resource evidence is stale"));
        }
        if self.resources.sample().await?
            != sample.ok_or_else(|| invalid("Missing resource sample"))?.1
        {
            return Err(invalid("Swap activity changed before admission"));
        }
        self.goal().await?;
        let c = &self.ledger.contract;
        self.ledger.worker_history().await?;
        self.ledger.native_inputs(&c.worker).await?;
        self.ledger
            .workspace_idle(
                &self.deployment.queued_message_service().session_ids(),
                None,
            )
            .await?;
        let (_, head) = self.identity(&c.worker).await?;
        if !self.ledger.owns_head(head).await? {
            self.ledger
                .end("suspended", "worker_input_head_changed")
                .await?;
            return Err(invalid("Worker received unrelated/newer input"));
        }
        if ExecutionProcess::has_running_queue_consumer_for_session(
            &self.deployment.db().pool,
            c.worker.session,
        )
        .await
        .map_err(|_| invalid("Worker activity unknown"))?
            || self
                .deployment
                .queued_message_service()
                .has_queued(c.worker.session)
            || !executors::executors::codex::original_worker_capacity_available()
        {
            return Err(invalid("Worker collision or capacity guard blocked"));
        }
        let running = ExecutionProcess::find_running(&self.deployment.db().pool)
            .await
            .map_err(|_| invalid("Global activity unknown"))?;
        if running.len() >= 7 {
            return Err(invalid("Global capacity preserves the owner lane"));
        }
        self.assets().await
    }

    async fn dispatch(&self) -> io::Result<Uuid> {
        let c = &self.ledger.contract;
        let session = Session::find_by_id(&self.deployment.db().pool, c.worker.session)
            .await
            .map_err(|_| invalid("Worker missing"))?
            .ok_or_else(|| invalid("Worker missing"))?;
        let response = follow_up_admitted(
            Extension(session),
            State(self.deployment.clone()),
            Json(CreateFollowUpAttempt {
                prompt: c.continuation(),
                executor_config: c.worker.config.clone(),
                retry_process_id: None,
                force_when_dirty: None,
                perform_git_reset: Some(false),
            }),
        )
        .await
        .map_err(|_| invalid("Dispatch outcome requires reconciliation"))?
        .0;
        response
            .into_data()
            .map(|p| p.id)
            .ok_or_else(|| invalid("Continuation was not admitted; reconciliation required"))
    }
}

struct Provider<D: Deployment = DeploymentImpl> {
    runtime: Arc<Live<D>>,
    engine: Arc<Engine>,
}

#[executors::original_worker::async_trait]
impl<D: Deployment> Backend for Provider<D> {
    async fn launch_guard(
        &self,
        env: &ExecutionEnv,
    ) -> io::Result<Option<Arc<dyn executors::original_worker::LaunchGuard>>> {
        let c = &self.runtime.ledger.contract;
        let execution = env
            .get("VK_EXECUTION_PROCESS_ID")
            .and_then(|v| Uuid::parse_str(v).ok())
            .ok_or_else(|| invalid("Missing execution context"))?;
        let identity = match env.get("VK_SESSION_ID").map(String::as_str) {
            Some(id) if id == c.worker.session.to_string() => {
                let n: i64 = sqlx::query_scalar("SELECT count(*) FROM bounded_worker_attempts WHERE grant_id=? AND execution=? AND state='dispatching'")
                    .bind(c.id).bind(execution).fetch_one(&self.runtime.ledger.pool).await.map_err(|_| invalid("Launch receipt unavailable"))?;
                if n != 1 {
                    return Ok(None);
                }
                &c.worker
            }
            Some(id) if id == c.manager.session.to_string() => {
                if self.runtime.ledger.active().await.is_err() {
                    return Ok(None);
                }
                &c.manager
            }
            _ => return Ok(None),
        };
        if env.get("VK_WORKSPACE_ID") != Some(&identity.workspace.to_string())
            || env.capacity.is_some()
        {
            return Err(invalid("Launch workspace/capacity context changed"));
        }
        Ok(Some(Arc::new(BoundLaunch {
            runtime: self.runtime.clone(),
            identity: identity.clone(),
            execution,
            verified: AtomicBool::new(false),
            input: std::sync::Mutex::new(None),
        })))
    }

    async fn bind(&self, env: &ExecutionEnv) -> io::Result<Option<Transport>> {
        let c = &self.runtime.ledger.contract;
        if env.get("VK_SESSION_ID").map(String::as_str)
            != Some(c.manager.session.to_string().as_str())
        {
            return Ok(None);
        }
        if self.runtime.ledger.active().await.is_err() {
            return Ok(None);
        }
        // Supply the transport only for the original saved configuration; a
        // same-session owner send with changed configuration suspends the grant.
        if self.runtime.identity(&c.manager).await.is_err()
            || self.runtime.ledger.manager_history().await.is_err()
        {
            self.runtime
                .ledger
                .end("suspended", "manager_binding_changed")
                .await?;
            return Ok(None);
        }
        if env.get("VK_WORKSPACE_ID").map(String::as_str)
            != Some(c.manager.workspace.to_string().as_str())
            || env.capacity.is_some()
        {
            return Err(invalid(
                "Continuation caller context changed or is capacity-restricted",
            ));
        }
        let caller = Uuid::parse_str(
            env.get("VK_EXECUTION_PROCESS_ID")
                .ok_or_else(|| invalid("Missing execution identity"))?,
        )
        .map_err(|_| invalid("Invalid execution identity"))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            // Keep the Unix pathname below sun_path's bound on the established
            // long XDG asset root; no new network listener or access route.
            let root = utils::assets::asset_dir().join("bw");
            tokio::fs::create_dir_all(&root).await?;
            tokio::fs::set_permissions(&root, std::fs::Permissions::from_mode(0o700)).await?;
            let socket = root.join(format!("{}.s", Uuid::new_v4().simple()));
            if socket.as_os_str().as_encoded_bytes().len() > 100 {
                return Err(invalid("Private capability socket path is too long"));
            }
            let listener = tokio::net::UnixListener::bind(&socket)?;
            let token = format!("{}{}", Uuid::new_v4(), Uuid::new_v4());
            let expected = token.clone();
            let engine = self.engine.clone();
            let path = socket.clone();
            tokio::spawn(async move {
                loop {
                    let accepted =
                        tokio::time::timeout(Duration::from_secs(5), listener.accept()).await;
                    let running: i64 = sqlx::query_scalar("SELECT count(*) FROM execution_processes WHERE id=? AND status='running' AND dropped=FALSE")
                        .bind(caller).fetch_one(&engine.ledger.pool).await.unwrap_or(0);
                    if running != 1 {
                        break;
                    }
                    let Ok(Ok((stream, _))) = accepted else {
                        continue;
                    };
                    let token = expected.clone();
                    let engine = engine.clone();
                    tokio::spawn(async move {
                        engine.serve_connection(caller, &token, stream).await;
                    });
                }
                let _ = tokio::fs::remove_file(path).await;
            });
            Ok(Some(Transport { socket, token }))
        }
        #[cfg(not(unix))]
        {
            let _ = caller;
            Err(invalid("Bounded continuation requires Unix"))
        }
    }

    async fn native_started(
        &self,
        env: &ExecutionEnv,
        thread: &str,
        model: &str,
        effort: &Value,
    ) -> io::Result<()> {
        let c = &self.runtime.ledger.contract;
        let identity = match env.get("VK_SESSION_ID").map(String::as_str) {
            Some(id) if id == c.manager.session.to_string() => &c.manager,
            Some(id) if id == c.worker.session.to_string() => &c.worker,
            _ => return Ok(()),
        };
        let execution = env
            .get("VK_EXECUTION_PROCESS_ID")
            .and_then(|id| Uuid::parse_str(id).ok());
        let bounded_worker: i64 = match execution {
            Some(id) => sqlx::query_scalar("SELECT count(*) FROM bounded_worker_attempts WHERE execution=? AND grant_id=? AND state='dispatching'")
                .bind(id).bind(c.id).fetch_one(&self.runtime.ledger.pool).await.map_err(|_| invalid("Launch receipt unavailable"))?,
            None => 0,
        };
        if identity.session == c.worker.session && bounded_worker != 1 {
            return Ok(());
        }
        if identity.session == c.manager.session && self.runtime.ledger.active().await.is_err() {
            return Ok(());
        }
        self.runtime.ledger.active().await?;
        if env.original_worker.is_none() {
            return Err(invalid("Bound launch instance proof missing"));
        }
        if thread != identity.thread || model != "gpt-6.1-sol" || effort.as_str() != Some("high") {
            self.runtime
                .ledger
                .end("suspended", "native_profile_or_thread_changed")
                .await?;
            return Err(invalid(
                "Original native profile/thread changed before inference",
            ));
        }
        // A worker launch must still agree with the fixed manager goal immediately
        // before inference. Initial manager resumes can be paused until native activation.
        if identity.session == c.worker.session {
            let caller: Uuid = sqlx::query_scalar("SELECT caller FROM bounded_worker_attempts WHERE execution=? AND grant_id=? AND state='dispatching'")
                .bind(execution.ok_or_else(|| invalid("Missing bound worker execution"))?).bind(c.id)
                .fetch_one(&self.runtime.ledger.pool).await.map_err(|_| invalid("Missing caller receipt"))?;
            self.runtime.check(caller).await?;
            self.runtime.goal().await?;
            self.runtime.assets().await?;
            executors::capacity::controller::before_bounded_worker_launch().await?;
            self.runtime.resource_freshness().await?;
        } else {
            let goal = executors::capacity::first_run::native(&c.manager.thread).await?;
            if goal.goal_id != c.goal_id
                || goal.objective != c.objective
                || goal.created_at != c.goal_created_at
            {
                self.runtime
                    .ledger
                    .end("suspended", "native_goal_amended_before_launch")
                    .await?;
                return Err(invalid("Fixed goal changed before native launch"));
            }
        }
        Ok(())
    }
}

struct BoundLaunch<D: Deployment> {
    runtime: Arc<Live<D>>,
    identity: Identity,
    execution: Uuid,
    verified: AtomicBool,
    input: std::sync::Mutex<Option<String>>,
}
impl<D: Deployment> std::fmt::Debug for BoundLaunch<D> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("BoundLaunch")
    }
}
#[executors::original_worker::async_trait]
impl<D: Deployment> executors::original_worker::LaunchGuard for BoundLaunch<D> {
    fn worker(&self) -> bool {
        self.identity.session == self.runtime.ledger.contract.worker.session
    }
    async fn resolved(
        &self,
        agent: &executors::executors::CodingAgent,
        raw: &executors::profile::ExecutorConfig,
    ) -> io::Result<()> {
        self.runtime.ledger.active().await?;
        if executors::original_worker::verify_resolved(
            agent,
            raw,
            &self.identity.config,
            &self.identity.profile_digest,
        )
        .is_err()
        {
            self.runtime
                .ledger
                .end("suspended", "resolved_launch_profile_changed")
                .await?;
            return Err(invalid(
                "Actual resolved launch instance differs from fixed profile",
            ));
        }
        if self.worker() {
            let executors::executors::CodingAgent::Codex(codex) = agent else {
                return Err(invalid("Bounded executor changed"));
            };
            *self
                .input
                .lock()
                .map_err(|_| invalid("Launch input binding unavailable"))? = Some(
                codex
                    .append_prompt
                    .combine_prompt(&self.runtime.ledger.contract.continuation()),
            );
        }
        self.verified.store(true, Ordering::SeqCst);
        Ok(())
    }
    async fn receipt_uncertain(&self) -> io::Result<()> {
        self.runtime
            .ledger
            .native_receipt_uncertain(self.execution)
            .await
    }
    async fn activation(
        &self,
        thread: &str,
        input: Option<&str>,
    ) -> io::Result<executors::original_worker::ActivationFence> {
        let ledger = &self.runtime.ledger;
        ledger.activation_fence(async {
            if thread != self.identity.thread || input.is_some_and(|input| self.input.lock().ok().and_then(|pin| pin.as_ref().map(|pin| pin != input)).unwrap_or(true)) {
                ledger.end("suspended", "native_activation_input_or_target_changed").await?;
                return Err(invalid("Bounded native activation target or prompt changed"));
            }
            if !self.worker() || !self.verified.load(Ordering::SeqCst) { return Err(invalid("Exact resolved launch proof missing")); }
            let caller: Uuid = sqlx::query_scalar("SELECT caller FROM bounded_worker_attempts WHERE grant_id=? AND execution=? AND state='dispatching' AND activated=0")
                .bind(ledger.contract.id).bind(self.execution).fetch_one(&ledger.pool).await.map_err(|_| invalid("Launch receipt changed"))?;
            self.runtime.check(caller).await?;
            let (_, head) = self.runtime.identity(&self.identity).await?;
            let process = ExecutionProcess::find_by_id(&ledger.pool, self.execution).await.map_err(|_| invalid("Worker execution unavailable"))?.ok_or_else(|| invalid("Worker execution missing"))?;
            if head != self.execution || process.session_id != self.identity.session || process.status != db::models::execution_process::ExecutionProcessStatus::Running { return Err(invalid("Original worker execution binding changed")); }
            ledger.worker_history().await?;
            ledger.native_inputs(&self.identity).await?;
            ledger.workspace_idle(&self.runtime.deployment.queued_message_service().session_ids(), Some(self.execution)).await?;
            self.runtime.assets().await?;
            executors::capacity::controller::before_bounded_worker_launch().await?;
            if ExecutionProcess::find_running(&ledger.pool).await.map_err(|_| invalid("Global capacity unknown"))?.len() > 7 { return Err(invalid("Owner capacity lane unavailable")); }
            self.runtime.resource_freshness().await?;
            if let Some(input) = input { ledger.activate_input(self.execution, input).await?; }
            Ok(())
        }).await
    }
}

#[executors::original_worker::async_trait]
trait ResourceProbe: Send + Sync {
    async fn sample(&self) -> io::Result<u64>;
    fn interval(&self) -> Duration {
        Duration::from_secs(10)
    }
}
struct HostResources;
#[executors::original_worker::async_trait]
impl ResourceProbe for HostResources {
    async fn sample(&self) -> io::Result<u64> {
        resources().await
    }
}

async fn resources() -> io::Result<u64> {
    let mem = tokio::fs::read_to_string("/proc/meminfo").await?;
    let value = |key: &str| -> io::Result<u64> {
        mem.lines()
            .find_map(|l| l.strip_prefix(key))
            .and_then(|v| v.split_whitespace().next())
            .and_then(|v| v.parse().ok())
            .ok_or_else(|| invalid("Memory evidence unavailable"))
    };
    if value("MemAvailable:")? < 4 * 1024 * 1024 || value("SwapFree:")? < 1024 * 1024 {
        return Err(invalid("Memory/swap guard blocked"));
    }
    let psi = tokio::fs::read_to_string("/proc/pressure/memory").await?;
    let pressure: f64 = psi
        .lines()
        .find(|l| l.starts_with("some "))
        .and_then(|l| l.split_whitespace().find_map(|v| v.strip_prefix("avg10=")))
        .and_then(|v| v.parse().ok())
        .ok_or_else(|| invalid("PSI evidence unavailable"))?;
    if !pressure.is_finite() || pressure > 0.1 {
        return Err(invalid("Memory pressure guard blocked"));
    }
    let mounts = tokio::fs::read_to_string("/proc/self/mountinfo").await?;
    if !mounts
        .lines()
        .any(|l| l.split_whitespace().nth(4) == Some("/mnt/vk-storage"))
    {
        return Err(invalid("Secondary SSD unavailable"));
    }
    let disk = tokio::process::Command::new("/usr/bin/df")
        .args(["-B1", "--output=avail", "/mnt/vk-storage"])
        .output()
        .await?;
    let free = std::str::from_utf8(&disk.stdout)
        .ok()
        .and_then(|s| s.lines().last())
        .and_then(|s| s.trim().parse::<u64>().ok())
        .ok_or_else(|| invalid("Storage evidence unavailable"))?;
    if !disk.status.success() || free < 2 * 1024 * 1024 * 1024 {
        return Err(invalid("Storage guard blocked"));
    }
    let vm = tokio::fs::read_to_string("/proc/vmstat").await?;
    vm.lines()
        .find_map(|l| l.strip_prefix("pswpout "))
        .and_then(|v| v.parse().ok())
        .ok_or_else(|| invalid("Swap activity unavailable"))
}

#[cfg(test)]
mod tests;
