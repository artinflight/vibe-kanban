use std::{
    collections::{HashMap, HashSet, VecDeque},
    io,
    sync::{
        Arc, Mutex as StdMutex, OnceLock, Weak,
        atomic::{AtomicBool, Ordering},
    },
};

use async_trait::async_trait;
use codex_app_server_protocol::{
    ClientInfo, ClientNotification, ClientRequest, CommandExecutionApprovalDecision,
    CommandExecutionRequestApprovalResponse, ConfigBatchWriteParams, ConfigEdit, ConfigReadParams,
    ConfigReadResponse, ConfigWriteResponse, DynamicToolCallOutputContentItem,
    DynamicToolCallResponse, FileChangeApprovalDecision, FileChangeRequestApprovalResponse,
    GetAccountParams, GetAccountRateLimitsResponse, GetAccountResponse, InitializeCapabilities,
    InitializeParams, InitializeResponse, ItemCompletedNotification, JSONRPCError,
    JSONRPCNotification, JSONRPCRequest, JSONRPCResponse, ListMcpServerStatusParams,
    ListMcpServerStatusResponse, RequestId, ReviewStartParams, ReviewStartResponse, ReviewTarget,
    ServerRequest, ThreadCompactStartParams, ThreadCompactStartResponse, ThreadForkParams,
    ThreadForkResponse, ThreadItem, ThreadReadParams, ThreadReadResponse, ThreadResumeParams,
    ThreadResumeResponse, ThreadStartParams, ThreadStartResponse, ToolRequestUserInputAnswer,
    ToolRequestUserInputQuestion, ToolRequestUserInputResponse, TurnInterruptParams,
    TurnInterruptResponse, TurnStartParams, TurnStartResponse, TurnStartedNotification, TurnStatus,
    TurnSteerParams, TurnSteerResponse, UserInput,
};
use codex_protocol::config_types::{CollaborationMode, ModeKind, Settings};
use futures::TryFutureExt;
use serde::{Serialize, de::DeserializeOwned};
use serde_json::{self, Value};
use tokio::{
    io::{AsyncWrite, AsyncWriteExt, BufWriter},
    sync::Mutex,
    time::{Duration, sleep},
};
use tokio_util::sync::CancellationToken;
use uuid::Uuid;
use workspace_utils::approvals::{ApprovalStatus, QuestionStatus};

use super::{
    goals::{self, NativeGoal, Progress},
    jsonrpc::{ExitSignalSender, JsonRpcCallbacks, JsonRpcPeer},
};
use crate::{
    approvals::{ExecutorApprovalError, ExecutorApprovalService},
    env::RepoContext,
    executors::{ExecutorError, codex::normalize_logs::Approval},
};

struct PendingPlan {
    item_id: String,
}

// Only decode lifecycle fields; newer item variants must not hide completion.
#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct GoalTurnCompleted {
    thread_id: String,
    turn: GoalTurn,
}

#[derive(serde::Deserialize)]
struct GoalTurn {
    id: String,
    status: TurnStatus,
}

static ACTIVE_CODEX_CLIENTS: OnceLock<StdMutex<HashMap<Uuid, Weak<AppServerClient>>>> =
    OnceLock::new();

fn active_codex_clients() -> &'static StdMutex<HashMap<Uuid, Weak<AppServerClient>>> {
    ACTIVE_CODEX_CLIENTS.get_or_init(|| StdMutex::new(HashMap::new()))
}

pub struct AppServerClient {
    rpc: OnceLock<JsonRpcPeer>,
    delegation: OnceLock<Arc<super::delegation::Delegation>>,
    delegation_requests: Mutex<HashSet<RequestId>>,
    elicitation_seen: Mutex<HashSet<RequestId>>,
    elicitations: Mutex<HashMap<RequestId, CancellationToken>>,
    log_writer: LogWriter,
    approvals: Option<Arc<dyn ExecutorApprovalService>>,
    thread_id: Mutex<Option<String>>,
    current_turn_id: Mutex<Option<String>>,
    pending_feedback: Mutex<VecDeque<String>>,
    auto_approve: bool,
    plan_mode: bool,
    resolved_model: OnceLock<String>,
    routing_locked: AtomicBool,
    routing_telemetry: OnceLock<crate::routing_telemetry::NativeBinding>,
    routed_effort: OnceLock<codex_protocol::openai_models::ReasoningEffort>,
    pending_plan: Mutex<Option<PendingPlan>>,
    repo_context: RepoContext,
    commit_reminder: bool,
    commit_reminder_prompt: String,
    commit_reminder_sent: AtomicBool,
    cancel: CancellationToken,
    self_ref: OnceLock<Weak<AppServerClient>>,
    exit_signal: OnceLock<ExitSignalSender>,
    goal: Mutex<Option<(NativeGoal, Progress)>>,
    goal_pausing: AtomicBool,
    completion_reconciliation_sent: AtomicBool,
    capacity_stopped: AtomicBool,
    execution_id: OnceLock<Uuid>,
}

impl Drop for AppServerClient {
    fn drop(&mut self) {
        if let Some(id) = self.execution_id.get()
            && let Ok(mut clients) = active_codex_clients().lock()
        {
            clients.remove(id);
        }
    }
}

impl AppServerClient {
    /// Public control-plane pause for the owning execution, never prompt steering.
    /// The caller must separately verify process termination; RPC success is not
    /// evidence that model work or descendants have stopped.
    pub async fn suspend_capacity_execution(
        execution_id: Uuid,
        reason: String,
    ) -> Result<(), ExecutorError> {
        let client = active_codex_clients()
            .lock()
            .expect("active client registry")
            .get(&execution_id)
            .and_then(Weak::upgrade)
            .ok_or_else(|| {
                ExecutorError::Io(io::Error::other(
                    "No owning Codex client; reconcile execution state",
                ))
            })?;
        client.suspend_capacity(reason).await;
        Ok(())
    }

    async fn suspend_capacity(&self, reason: String) {
        if self.capacity_stopped.swap(true, Ordering::SeqCst) {
            return;
        }
        self.goal_pausing.store(true, Ordering::SeqCst);
        let thread_id = self.thread_id.lock().await.clone();
        if let Some(thread_id) = thread_id {
            // Bound each call independently. The OS guard remains armed even
            // if RPC or VK itself stalls during this graceful attempt.
            let paused = tokio::time::timeout(
                Duration::from_secs(1),
                self.goal_request(
                    "thread/goal/set",
                    serde_json::json!({"threadId": thread_id, "status": "paused"}),
                ),
            )
            .await;
            if !matches!(paused, Ok(Ok(_))) {
                tracing::warn!(
                    "Capacity stop could not confirm persisted goal pause; reconcile before resuming"
                );
            }
            let turn_id = self.current_turn_id.lock().await.clone();
            if let Some(turn_id) = turn_id {
                let _ = tokio::time::timeout(
                    Duration::from_secs(1),
                    self.goal_request(
                        "turn/interrupt",
                        serde_json::json!({"threadId": thread_id, "turnId": turn_id}),
                    ),
                )
                .await;
            }
        }
        let _ = super::slash_commands::log_event_raw(
            self.log_writer(),
            format!("Scheduled goal paused: {reason}"),
        )
        .await;
        if let Some(signal) = self.exit_signal.get() {
            signal
                .send_exit_signal(crate::executors::ExecutorExitResult::Success)
                .await;
        }
        // Intentionally remains pausing. This execution is never reactivated;
        // later runs use a new fenced execution of the same stored goal.
    }

    pub fn watch_capacity(self: &Arc<Self>, capacity: crate::capacity::PreparedCapacity) {
        let weak = Arc::downgrade(self);
        tokio::spawn(async move {
            let start = std::time::Instant::now();
            let mut fence = match capacity_guard::Fence::new(
                capacity.lease.clone(),
                crate::capacity::wall_ms(),
                0,
            ) {
                Ok(fence) => fence,
                Err(reason) => {
                    if let Some(client) = weak.upgrade() {
                        client.suspend_capacity(reason.into()).await;
                    }
                    return;
                }
            };
            loop {
                sleep(Duration::from_millis(100)).await;
                let Some(client) = weak.upgrade() else {
                    return;
                };
                if client.cancel.is_cancelled() {
                    return;
                }
                let now = crate::capacity::wall_ms();
                let next = capacity_guard::read_lease(&capacity.file);
                let reason = match next {
                    Err(_) => Some("Permission unavailable"),
                    Ok(next) => {
                        match fence.observe(&next, now, start.elapsed().as_millis() as u64) {
                            Err(reason) => Some(reason),
                            Ok(())
                                if next.expires_at_ms.saturating_sub(now) <= 2000
                                    || next.stop_at_ms.saturating_sub(now) <= 2000 =>
                            {
                                Some("Permission or overnight deadline reached")
                            }
                            Ok(()) => None,
                        }
                    }
                };
                if let Some(reason) = reason {
                    client.suspend_capacity(reason.into()).await;
                    return;
                }
            }
        });
    }

    #[allow(clippy::too_many_arguments)]
    pub fn new(
        log_writer: LogWriter,
        approvals: Option<Arc<dyn ExecutorApprovalService>>,
        auto_approve: bool,
        plan_mode: bool,
        repo_context: RepoContext,
        commit_reminder: bool,
        commit_reminder_prompt: String,
        cancel: CancellationToken,
    ) -> Arc<Self> {
        let client = Arc::new(Self {
            rpc: OnceLock::new(),
            delegation: OnceLock::new(),
            delegation_requests: Mutex::new(HashSet::new()),
            elicitation_seen: Mutex::new(HashSet::new()),
            elicitations: Mutex::new(HashMap::new()),
            log_writer,
            approvals,
            auto_approve,
            plan_mode,
            resolved_model: OnceLock::new(),
            routing_locked: AtomicBool::new(false),
            routing_telemetry: OnceLock::new(),
            routed_effort: OnceLock::new(),
            pending_plan: Mutex::new(None),
            thread_id: Mutex::new(None),
            current_turn_id: Mutex::new(None),
            pending_feedback: Mutex::new(VecDeque::new()),
            repo_context,
            commit_reminder,
            commit_reminder_prompt,
            commit_reminder_sent: AtomicBool::new(false),
            cancel,
            self_ref: OnceLock::new(),
            exit_signal: OnceLock::new(),
            goal: Mutex::new(None),
            goal_pausing: AtomicBool::new(false),
            completion_reconciliation_sent: AtomicBool::new(false),
            capacity_stopped: AtomicBool::new(false),
            execution_id: OnceLock::new(),
        });
        let _ = client.self_ref.set(Arc::downgrade(&client));
        client
    }

    pub async fn delegation_turn_current(&self, turn: &str) -> bool {
        !self.cancel.is_cancelled()
            && self.current_turn_id.lock().await.as_deref() == Some(turn)
            && self
                .goal
                .lock()
                .await
                .as_ref()
                .is_none_or(|(g, _)| g.status != "active")
    }

    pub fn set_delegation(&self, control: Arc<super::delegation::Delegation>) {
        let _ = self.delegation.set(control);
    }

    pub async fn abort_delegation_execution(&self, reason: &str) {
        tracing::error!(%reason, "Stopping execution with uncertain delegated state");
        let _ = super::slash_commands::log_event_raw(
            self.log_writer(),
            format!("Delegation stopped: {reason}"),
        )
        .await;
        if let Some(signal) = self.exit_signal.get() {
            signal
                .send_exit_signal(crate::executors::ExecutorExitResult::Failure)
                .await;
        }
        self.cancel.cancel();
    }

    pub async fn delegation_request(
        &self,
        method: &str,
        params: Value,
    ) -> Result<Value, ExecutorError> {
        let id = self.next_request_id();
        self.delegation_requests.lock().await.insert(id.clone());
        let request = serde_json::json!({"id":id,"method":method,"params":params});
        // Retain timed-out IDs until a late response arrives, so it cannot become a root session ID.
        tokio::time::timeout(
            Duration::from_secs(10),
            self.rpc()
                .request(id, &request, method, self.cancel.clone()),
        )
        .await
        .map_err(|_| ExecutorError::Io(io::Error::other("Delegation API timed out")))?
    }

    pub fn set_exit_signal(&self, signal: ExitSignalSender) {
        let _ = self.exit_signal.set(signal);
    }

    /// Goal APIs postdate our pinned protocol types; keep this narrow wire adapter
    /// rather than upgrading every executor protocol as part of this feature.
    pub async fn goal_request(&self, method: &str, params: Value) -> Result<Value, ExecutorError> {
        if method == "thread/goal/set"
            && params["status"] == "active"
            && self.capacity_stopped.load(Ordering::SeqCst)
        {
            return Err(ExecutorError::Io(io::Error::other(
                "Scheduled execution has stopped",
            )));
        }
        let id = self.next_request_id();
        let request = serde_json::json!({"id": id, "method": method, "params": params});
        tokio::time::timeout(
            Duration::from_secs(10),
            self.rpc()
                .request(id, &request, method, self.cancel.clone()),
        )
        .await
        .map_err(|_| ExecutorError::Io(io::Error::other("Goal API timed out")))?
    }

    pub async fn refresh_goal(&self) -> Result<(), ExecutorError> {
        let Some(thread_id) = self.thread_id.lock().await.clone() else {
            return Ok(());
        };
        match self
            .goal_request(
                "thread/goal/get",
                serde_json::json!({"threadId": thread_id}),
            )
            .await
        {
            Ok(value) => {
                self.accept_goal(value.get("goal").cloned().unwrap_or(Value::Null))
                    .await
            }
            // Older Codex versions have no goal API: ordinary sessions still work.
            Err(err)
                if err.to_string().contains("-32601")
                    || err.to_string().to_lowercase().contains("unknown method")
                    || err.to_string().to_lowercase().contains("method not found")
                    || err
                        .to_string()
                        .contains("unknown variant `thread/goal/get`")
                    || err.to_string().contains("goals feature is disabled") =>
            {
                Ok(())
            }
            Err(err) => Err(err),
        }
    }

    async fn accept_goal(&self, value: Value) -> Result<(), ExecutorError> {
        if value.is_null() {
            *self.goal.lock().await = None;
            return Ok(());
        }
        let goal: NativeGoal =
            serde_json::from_value(value).map_err(|e| ExecutorError::Io(io::Error::other(e)))?;
        if self.thread_id.lock().await.as_deref() != Some(goal.thread_id.as_str()) {
            return Ok(()); // Descendant agents never own the root goal.
        }
        if goal.status == "active"
            && let Some(control) = self.delegation.get()
            && control.active().await
        {
            control.close();
            self.abort_delegation_execution("Native goal activated with independent children; stop before bypassing goal accounting").await;
            return Err(ExecutorError::Io(io::Error::other(
                "Collect delegated work before starting a native goal",
            )));
        }
        let mut guard = self.goal.lock().await;
        if let Some((old, progress)) = guard.as_mut()
            && old.objective == goal.objective
            && old.created_at == goal.created_at
        {
            *old = goal;
            goals::save(&old.thread_id, progress).await?;
        } else {
            self.completion_reconciliation_sent
                .store(false, Ordering::SeqCst);
            let progress = goals::load(&goal).await?;
            *guard = Some((goal, progress));
        }
        Ok(())
    }

    // Steering stays in the current turn: no new goal, budget, or continuation loop.
    // Never await an RPC response in the notification reader itself.
    async fn reconcile_goal_completion(&self) {
        if self.goal_pausing.load(Ordering::SeqCst)
            || self.capacity_stopped.load(Ordering::SeqCst)
            || self.cancel.is_cancelled()
        {
            return;
        }
        let Some(turn_id) = self.current_turn_id.lock().await.clone() else {
            return;
        };
        let guard = self.goal.lock().await;
        let Some((goal, progress)) = guard.as_ref() else {
            return;
        };
        if goal.status != "complete"
            || progress.all_complete()
            || self
                .completion_reconciliation_sent
                .swap(true, Ordering::SeqCst)
        {
            return;
        }
        let thread_id = goal.thread_id.clone();
        let prompt = progress.reconciliation_prompt();
        let weak = self.self_ref.get().expect("client self reference").clone();
        tokio::spawn(async move {
            let Some(client) = weak.upgrade() else { return };
            if client.goal_pausing.load(Ordering::SeqCst)
                || client.capacity_stopped.load(Ordering::SeqCst)
                || client.cancel.is_cancelled()
            {
                return;
            }
            if let Err(err) = client
                .turn_steer(
                    thread_id,
                    turn_id,
                    vec![UserInput::Text {
                        text: prompt,
                        text_elements: vec![],
                    }],
                )
                .await
            {
                tracing::debug!("Completion reconciliation steer was not accepted: {err}");
            }
        });
    }

    pub async fn reset_goal_run(&self, scheduled: bool) -> Result<(), ExecutorError> {
        let mut guard = self.goal.lock().await;
        if let Some((goal, progress)) = guard.as_mut() {
            progress.resume(scheduled);
            goals::save(&goal.thread_id, progress).await?;
        }
        Ok(())
    }

    pub async fn pause_execution_goal(execution_process_id: Uuid) -> Result<(), ExecutorError> {
        let client = active_codex_clients()
            .lock()
            .expect("active client registry")
            .get(&execution_process_id)
            .and_then(Weak::upgrade);
        if let Some(client) = client {
            let thread_id = {
                let guard = client.goal.lock().await;
                guard
                    .as_ref()
                    .filter(|(goal, _)| goal.status == "active")
                    .map(|(goal, _)| goal.thread_id.clone())
            };
            if let Some(thread_id) = thread_id {
                client
                    .goal_request(
                        "thread/goal/set",
                        serde_json::json!({
                            "threadId": thread_id, "status": "paused"
                        }),
                    )
                    .await?;
            }
        }
        Ok(())
    }

    fn supply_goal_context(&self, turn_id: String) {
        let weak = self.self_ref.get().expect("client self reference").clone();
        tokio::spawn(async move {
            let Some(client) = weak.upgrade() else { return };
            let context = {
                let guard = client.goal.lock().await;
                guard.as_ref().filter(|(goal, _)| goal.status == "active")
                    .map(|(goal, progress)| (goal.thread_id.clone(), format!(
                        "VK durable goal checkpoint (supporting evidence; the full user objective and later corrections remain authoritative):\n{}\n{}",
                        serde_json::to_string(progress).unwrap_or_default(),
                        progress.guidance()
                    )))
            };
            if let Some((thread_id, text)) = context {
                // Pin the expected turn so a late snapshot cannot spill into a
                // later user turn. Native Codex remains the only scheduler.
                if let Err(err) = client
                    .turn_steer(
                        thread_id,
                        turn_id,
                        vec![UserInput::Text {
                            text,
                            text_elements: vec![],
                        }],
                    )
                    .await
                {
                    tracing::debug!("Goal context steer was not accepted: {err}");
                }
            }
        });
    }

    /// Must run outside the RPC reader callback: awaiting a response there would
    /// deadlock the same reader responsible for delivering that response.
    fn pause_goal(&self, reason: String, exit_after_pause: bool) {
        if self.goal_pausing.swap(true, Ordering::SeqCst) {
            return;
        }
        let weak = self.self_ref.get().expect("client self reference").clone();
        tokio::spawn(async move {
            let Some(client) = weak.upgrade() else { return };
            let Some(thread_id) = client.thread_id.lock().await.clone() else {
                return;
            };
            let result = client
                .goal_request(
                    "thread/goal/set",
                    serde_json::json!({
                        "threadId": thread_id, "status": "paused"
                    }),
                )
                .await;
            let message = match &result {
                Ok(_) => format!("Autonomous goal paused: {reason}"),
                Err(err) => format!(
                    "Autonomous execution stopped; could not persist goal pause: {err}. {reason}"
                ),
            };
            let _ = super::slash_commands::log_event_raw(client.log_writer(), message).await;
            if exit_after_pause || result.is_err() || client.current_turn_id.lock().await.is_none()
            {
                if let Some(turn_id) = client.current_turn_id.lock().await.clone() {
                    let _ = client
                        .goal_request(
                            "turn/interrupt",
                            serde_json::json!({
                                "threadId": thread_id, "turnId": turn_id
                            }),
                        )
                        .await;
                }
                if let Some(signal) = client.exit_signal.get() {
                    signal
                        .send_exit_signal(if result.is_ok() {
                            crate::executors::ExecutorExitResult::Success
                        } else {
                            crate::executors::ExecutorExitResult::Failure
                        })
                        .await;
                }
            }
            client.goal_pausing.store(false, Ordering::SeqCst);
        });
    }

    async fn goal_turn_completed(&self, turn_id: &str) -> Result<bool, ExecutorError> {
        if self.goal_pausing.load(Ordering::SeqCst) || self.capacity_stopped.load(Ordering::SeqCst)
        {
            return Ok(true);
        }
        let mut guard = self.goal.lock().await;
        let Some((goal, progress)) = guard.as_mut() else {
            return Ok(false);
        };
        if goal.status != "active" {
            if goal.status == "complete" {
                self.log_writer
                    .log_raw(
                        &serde_json::json!({
                            "method": "vk/goal/completion",
                            "params": {"metadata": progress.completion_metadata()}
                        })
                        .to_string(),
                    )
                    .await?;
            }
            return Ok(false);
        }
        let reason = progress.finish_turn(turn_id);
        goals::save(&goal.thread_id, progress).await?;
        if self.plan_mode {
            self.pause_goal(
                "Plan mode requires user review before autonomous implementation.".into(),
                true,
            );
        } else if let Some(reason) = reason {
            self.pause_goal(reason, true);
        } else {
            if progress.stagnant_turns == 3
                || (progress.stagnant_turns >= 6 && progress.stagnant_turns.is_multiple_of(6))
            {
                super::slash_commands::log_event_raw(self.log_writer(), progress.guidance())
                    .await?;
            }
            // Native Codex schedules the next turn. Never send a duplicate continue.
            let weak = self.self_ref.get().expect("client self reference").clone();
            let completed_id = turn_id.to_string();
            tokio::spawn(async move {
                sleep(Duration::from_secs(30)).await;
                let Some(client) = weak.upgrade() else { return };
                let guard = client.goal.lock().await;
                if let Some((goal, progress)) = guard.as_ref()
                    && goal.status == "active"
                    && progress.last_turn.as_deref() == Some(&completed_id)
                    && client.current_turn_id.lock().await.is_none()
                {
                    client.pause_goal("The native goal engine did not start another turn; inspect the session before resuming.".into(), true);
                }
            });
        }
        Ok(true)
    }

    pub fn connect(&self, peer: JsonRpcPeer) {
        let _ = self.rpc.set(peer);
    }

    pub fn register_active_execution(execution_process_id: Uuid, client: &Arc<Self>) {
        let _ = client.execution_id.set(execution_process_id);
        active_codex_clients()
            .lock()
            .expect("active Codex client registry poisoned")
            .insert(execution_process_id, Arc::downgrade(client));
    }

    pub fn unregister_active_execution(execution_process_id: Uuid) {
        active_codex_clients()
            .lock()
            .expect("active Codex client registry poisoned")
            .remove(&execution_process_id);
    }

    pub async fn steer_execution(
        execution_process_id: Uuid,
        message: String,
    ) -> Result<bool, ExecutorError> {
        const STEER_READY_ATTEMPTS: usize = 40;
        const STEER_READY_RETRY_DELAY: Duration = Duration::from_millis(50);

        for attempt in 0..STEER_READY_ATTEMPTS {
            let client = {
                let mut guard = active_codex_clients()
                    .lock()
                    .expect("active Codex client registry poisoned");
                match guard.get(&execution_process_id).and_then(Weak::upgrade) {
                    Some(client) => Some(client),
                    None => {
                        guard.remove(&execution_process_id);
                        None
                    }
                }
            };

            if let Some(client) = client
                && client.steer(message.clone()).await?
            {
                return Ok(true);
            }

            if attempt + 1 < STEER_READY_ATTEMPTS {
                sleep(STEER_READY_RETRY_DELAY).await;
            }
        }

        Ok(false)
    }

    pub fn set_routing_telemetry(&self, binding: crate::routing_telemetry::NativeBinding) {
        let _ = self.routing_telemetry.set(binding);
    }
    pub fn set_routed_effort(&self, effort: codex_protocol::openai_models::ReasoningEffort) {
        let _ = self.routed_effort.set(effort);
    }

    pub fn lock_routed_model(&self) {
        self.routing_locked.store(true, Ordering::SeqCst);
    }

    pub fn set_resolved_model(&self, model: String) {
        let _ = self.resolved_model.set(model);
    }

    fn rpc(&self) -> &JsonRpcPeer {
        self.rpc.get().expect("Codex RPC peer not attached")
    }

    pub fn log_writer(&self) -> &LogWriter {
        &self.log_writer
    }

    pub async fn initialize(&self) -> Result<(), ExecutorError> {
        let request = ClientRequest::Initialize {
            request_id: self.next_request_id(),
            params: InitializeParams {
                client_info: ClientInfo {
                    name: "vibe-codex-executor".to_string(),
                    title: None,
                    version: env!("CARGO_PKG_VERSION").to_string(),
                },
                capabilities: Some(InitializeCapabilities {
                    experimental_api: true,
                    ..Default::default()
                }),
            },
        };

        self.send_request::<InitializeResponse>(request, "initialize")
            .await?;
        self.send_message(&ClientNotification::Initialized).await
    }

    pub async fn thread_start(
        &self,
        params: ThreadStartParams,
    ) -> Result<ThreadStartResponse, ExecutorError> {
        let request = ClientRequest::ThreadStart {
            request_id: self.next_request_id(),
            params,
        };
        self.send_request(request, "thread/start").await
    }

    pub async fn thread_fork(
        &self,
        params: ThreadForkParams,
    ) -> Result<ThreadForkResponse, ExecutorError> {
        let request = ClientRequest::ThreadFork {
            request_id: self.next_request_id(),
            params,
        };
        self.send_request(request, "thread/fork").await
    }

    pub async fn thread_resume(
        &self,
        params: ThreadResumeParams,
    ) -> Result<ThreadResumeResponse, ExecutorError> {
        let request = ClientRequest::ThreadResume {
            request_id: self.next_request_id(),
            params,
        };
        self.send_request(request, "thread/resume").await
    }

    pub async fn turn_start_with_mode(
        &self,
        thread_id: String,
        input: Vec<UserInput>,
        collaboration_mode: Option<CollaborationMode>,
    ) -> Result<TurnStartResponse, ExecutorError> {
        if self.capacity_stopped.load(Ordering::SeqCst) {
            return Err(ExecutorError::Io(io::Error::other(
                "Scheduled execution has stopped",
            )));
        }
        let request = ClientRequest::TurnStart {
            request_id: self.next_request_id(),
            params: TurnStartParams {
                thread_id: thread_id.clone(),
                input,
                collaboration_mode,
                ..Default::default()
            },
        };
        let response: TurnStartResponse = self.send_request(request, "turn/start").await?;
        if let Some(binding) = self.routing_telemetry.get() {
            binding.turn(&thread_id, &response.turn.id).await;
        }
        Ok(response)
    }

    fn collaboration_mode(&self, mode: ModeKind) -> Result<CollaborationMode, ExecutorError> {
        let model = self.resolved_model.get().cloned().ok_or_else(|| {
            tracing::error!("collaboration_mode called before resolved_model was set");
            ExecutorError::Io(io::Error::other(
                "resolved model not available for collaboration mode",
            ))
        })?;
        Ok(CollaborationMode {
            mode,
            settings: Settings {
                model,
                reasoning_effort: self.routed_effort.get().copied(),
                developer_instructions: None,
            },
        })
    }

    pub fn initial_collaboration_mode(&self) -> Result<CollaborationMode, ExecutorError> {
        if self.plan_mode {
            self.collaboration_mode(ModeKind::Plan)
        } else {
            self.collaboration_mode(ModeKind::Default)
        }
    }

    pub async fn get_account(&self) -> Result<GetAccountResponse, ExecutorError> {
        let request = ClientRequest::GetAccount {
            request_id: self.next_request_id(),
            params: GetAccountParams {
                refresh_token: false,
            },
        };
        self.send_request(request, "account/read").await
    }

    pub async fn start_review(
        &self,
        thread_id: String,
        target: ReviewTarget,
    ) -> Result<ReviewStartResponse, ExecutorError> {
        let request = ClientRequest::ReviewStart {
            request_id: self.next_request_id(),
            params: ReviewStartParams {
                thread_id,
                target,
                delivery: None,
            },
        };
        self.send_request(request, "reviewStart").await
    }

    pub async fn list_mcp_server_status(
        &self,
        cursor: Option<String>,
    ) -> Result<ListMcpServerStatusResponse, ExecutorError> {
        let request = ClientRequest::McpServerStatusList {
            request_id: self.next_request_id(),
            params: ListMcpServerStatusParams {
                cursor,
                limit: None,
            },
        };
        self.send_request(request, "mcpServerStatus/list").await
    }

    pub async fn thread_compact_start(
        &self,
        thread_id: String,
    ) -> Result<ThreadCompactStartResponse, ExecutorError> {
        let request = ClientRequest::ThreadCompactStart {
            request_id: self.next_request_id(),
            params: ThreadCompactStartParams { thread_id },
        };
        self.send_request(request, "thread/compact/start").await
    }

    pub async fn thread_read(
        &self,
        thread_id: String,
    ) -> Result<ThreadReadResponse, ExecutorError> {
        let request = ClientRequest::ThreadRead {
            request_id: self.next_request_id(),
            params: ThreadReadParams {
                thread_id,
                include_turns: false,
            },
        };
        self.send_request(request, "thread/read").await
    }

    pub async fn turn_interrupt(
        &self,
        thread_id: String,
        turn_id: String,
    ) -> Result<TurnInterruptResponse, ExecutorError> {
        let request = ClientRequest::TurnInterrupt {
            request_id: self.next_request_id(),
            params: TurnInterruptParams { thread_id, turn_id },
        };
        self.send_request(request, "turn/interrupt").await
    }

    pub async fn turn_steer(
        &self,
        thread_id: String,
        turn_id: String,
        input: Vec<UserInput>,
    ) -> Result<TurnSteerResponse, ExecutorError> {
        let request = ClientRequest::TurnSteer {
            request_id: self.next_request_id(),
            params: TurnSteerParams {
                thread_id,
                input,
                expected_turn_id: turn_id,
            },
        };
        self.send_request(request, "turn/steer").await
    }

    pub async fn config_batch_write(
        &self,
        edits: Vec<ConfigEdit>,
    ) -> Result<ConfigWriteResponse, ExecutorError> {
        let request = ClientRequest::ConfigBatchWrite {
            request_id: self.next_request_id(),
            params: ConfigBatchWriteParams {
                edits,
                file_path: None,
                expected_version: None,
                reload_user_config: false,
            },
        };
        self.send_request(request, "config/batchWrite").await
    }

    pub async fn config_read(
        &self,
        cwd: Option<String>,
    ) -> Result<ConfigReadResponse, ExecutorError> {
        let request = ClientRequest::ConfigRead {
            request_id: self.next_request_id(),
            params: ConfigReadParams {
                include_layers: false,
                cwd,
            },
        };
        self.send_request(request, "config/read").await
    }

    pub async fn get_account_rate_limits(
        &self,
    ) -> Result<GetAccountRateLimitsResponse, ExecutorError> {
        let request = ClientRequest::GetAccountRateLimits {
            request_id: self.next_request_id(),
            params: None,
        };
        self.send_request(request, "account/rateLimits/read").await
    }

    async fn handle_server_request(
        &self,
        peer: &JsonRpcPeer,
        request: ServerRequest,
    ) -> Result<(), ExecutorError> {
        match request {
            ServerRequest::FileChangeRequestApproval { request_id, params } => {
                let call_id = params.item_id.clone();
                let status = self
                    .request_tool_approval("edit", "codex.apply_patch", &call_id)
                    .await
                    .inspect_err(|err| {
                        if !matches!(
                            err,
                            ExecutorError::ExecutorApprovalError(ExecutorApprovalError::Cancelled)
                        ) {
                            tracing::error!(
                                "Codex file_change approval failed for item_id={}: {err}",
                                call_id
                            );
                        }
                    })?;
                self.log_writer
                    .log_raw(
                        &Approval::approval_response(
                            call_id,
                            "codex.apply_patch".to_string(),
                            status.clone(),
                        )
                        .raw(),
                    )
                    .await?;
                let (decision, feedback) = self.file_change_decision(&status);
                let response = FileChangeRequestApprovalResponse { decision };
                send_server_response(peer, request_id, response).await?;
                if let Some(message) = feedback {
                    tracing::debug!("queueing file change denial feedback: {message}");
                    self.enqueue_feedback(format!("User feedback: {message}"))
                        .await;
                }
                Ok(())
            }
            ServerRequest::CommandExecutionRequestApproval { request_id, params } => {
                let call_id = params.item_id.clone();
                let status = self
                    .request_tool_approval("bash", "codex.exec_command", &call_id)
                    .await
                    .inspect_err(|err| {
                        if !matches!(
                            err,
                            ExecutorError::ExecutorApprovalError(ExecutorApprovalError::Cancelled)
                        ) {
                            tracing::error!(
                                "Codex command_execution approval failed for item_id={}: {err}",
                                call_id
                            );
                        }
                    })?;
                self.log_writer
                    .log_raw(
                        &Approval::approval_response(
                            call_id,
                            "codex.exec_command".to_string(),
                            status.clone(),
                        )
                        .raw(),
                    )
                    .await?;
                let (decision, feedback) = self.command_execution_decision(&status);
                let response = CommandExecutionRequestApprovalResponse { decision };
                send_server_response(peer, request_id, response).await?;
                if let Some(message) = feedback {
                    tracing::debug!("queueing exec denial feedback: {message}");
                    self.enqueue_feedback(format!("User feedback: {message}"))
                        .await;
                }
                Ok(())
            }
            ServerRequest::ToolRequestUserInput { request_id, params } => {
                let call_id = params.item_id.clone();
                let question_count = params.questions.len();
                let status = self
                    .request_question_answer(question_count, &call_id)
                    .await
                    .inspect_err(|err| {
                        if !matches!(
                            err,
                            ExecutorError::ExecutorApprovalError(ExecutorApprovalError::Cancelled)
                        ) {
                            tracing::error!(
                                "Codex question approval failed for call_id={}: {err}",
                                call_id
                            );
                        }
                    })?;
                self.log_writer
                    .log_raw(&Approval::question_response(call_id.clone(), status.clone()).raw())
                    .await?;
                let response = match &status {
                    QuestionStatus::Answered { answers } => {
                        let answers_map: HashMap<String, Vec<String>> = answers
                            .iter()
                            .map(|qa| (qa.question.clone(), qa.answer.clone()))
                            .collect();
                        answers_to_codex_format(&params.questions, &answers_map)
                    }
                    _ => ToolRequestUserInputResponse {
                        answers: HashMap::new(),
                    },
                };
                send_server_response(peer, request_id, response).await?;
                Ok(())
            }
            ServerRequest::DynamicToolCall { request_id, params } => {
                if params.tool == super::delegation::TOOL {
                    let root = self.thread_id.lock().await.as_deref()
                        == Some(params.thread_id.as_str())
                        && self.current_turn_id.lock().await.as_deref()
                            == Some(params.turn_id.as_str());
                    let goal_active = self
                        .goal
                        .lock()
                        .await
                        .as_ref()
                        .is_some_and(|(g, _)| g.status == "active");
                    let control = self.delegation.get().cloned();
                    if !root
                        || goal_active
                        || self.capacity_stopped.load(Ordering::SeqCst)
                        || control.is_none()
                    {
                        return send_server_response(peer, request_id, DynamicToolCallResponse {
                            content_items:vec![DynamicToolCallOutputContentItem::InputText {text:"Delegation requires the current root turn, a configured router, and no active native goal or scheduled capacity run.".into()}],success:false}).await;
                    }
                    let client = self
                        .self_ref
                        .get()
                        .and_then(Weak::upgrade)
                        .expect("live client");
                    let peer = peer.clone();
                    // Never block the JSON-RPC reader while the tool makes nested native requests.
                    tokio::spawn(async move {
                        let result = control
                            .unwrap()
                            .handle(client, params.turn_id, params.arguments)
                            .await;
                        let success = result.is_ok();
                        let text = result.map(|v| v.to_string()).unwrap_or_else(|e| e);
                        if let Err(error) = send_server_response(
                            &peer,
                            request_id,
                            DynamicToolCallResponse {
                                content_items: vec![DynamicToolCallOutputContentItem::InputText {
                                    text,
                                }],
                                success,
                            },
                        )
                        .await
                        {
                            tracing::warn!(%error,"Delegation tool response unavailable");
                        }
                    });
                    return Ok(());
                }
                if params.tool == goals::TOOL {
                    if self.thread_id.lock().await.as_deref() != Some(params.thread_id.as_str())
                        || self.current_turn_id.lock().await.as_deref()
                            != Some(params.turn_id.as_str())
                    {
                        return send_server_response(
                            peer,
                            request_id,
                            DynamicToolCallResponse {
                                content_items: vec![DynamicToolCallOutputContentItem::InputText {
                                    text: "Checkpoint must belong to the current root turn.".into(),
                                }],
                                success: false,
                            },
                        )
                        .await;
                    }
                    let mut guard = self.goal.lock().await;
                    let result = match guard.as_mut() {
                        Some((goal, progress)) if matches!(goal.status.as_str(), "active" | "complete") => {
                            let result = progress.checkpoint(params.arguments);
                            if result.is_ok() {
                                goals::save(&goal.thread_id, progress).await?;
                                if goal.status == "active"
                                    && let Some(reason) = progress.pause_reason.clone() {
                                    self.pause_goal(reason, false);
                                }
                            }
                            result
                        }
                        _ => Err("No active or completed native goal to checkpoint. Do not create a goal without user authorization.".into()),
                    };
                    let success = result.is_ok();
                    let text = match result {
                        Ok(value) => value.to_string(),
                        Err(err) => err,
                    };
                    send_server_response(
                        peer,
                        request_id,
                        DynamicToolCallResponse {
                            content_items: vec![DynamicToolCallOutputContentItem::InputText {
                                text,
                            }],
                            success,
                        },
                    )
                    .await?;
                    return Ok(());
                }
                tracing::warn!(
                    "received unsupported dynamic tool call: tool={} call_id={}",
                    params.tool,
                    params.call_id
                );
                let response = DynamicToolCallResponse {
                    content_items: vec![DynamicToolCallOutputContentItem::InputText {
                        text: format!(
                            "Dynamic tool '{}' is not supported by this client.",
                            params.tool
                        ),
                    }],
                    success: false,
                };
                send_server_response(peer, request_id, response).await?;
                Ok(())
            }
            ServerRequest::McpServerElicitationRequest { request_id, params } => {
                self.start_elicitation(peer, request_id, params).await
            }
            ServerRequest::ChatgptAuthTokensRefresh { .. }
            | ServerRequest::PermissionsRequestApproval { .. } => {
                tracing::warn!("received unhandled v2 server request: {:?}", request);
                let response = JSONRPCResponse {
                    id: request.id().clone(),
                    result: Value::Null,
                };
                peer.send(&response).await
            }
            ServerRequest::ApplyPatchApproval { .. }
            | ServerRequest::ExecCommandApproval { .. } => {
                tracing::error!(
                    "received deprecated v1 server request (session may have been started with legacy API): {:?}",
                    request
                );
                Err(ExecutorApprovalError::RequestFailed(
                    "deprecated v1 server request".to_string(),
                )
                .into())
            }
        }
    }

    async fn elicitation_diagnostic(&self, id: &RequestId, origin: &str) {
        tracing::info!(request_id = ?id, origin, "MCP approval bridge result");
        let _ = self
            .log_writer
            .log_raw(
                &serde_json::json!({
                    "McpApprovalDiagnostic": {"request_id": id, "origin": origin}
                })
                .to_string(),
            )
            .await;
    }

    async fn elicitation_context_valid(
        &self,
        params: &codex_app_server_protocol::McpServerElicitationRequestParams,
    ) -> bool {
        self.thread_id.lock().await.as_deref() == Some(params.thread_id.as_str())
            && self
                .current_turn_id
                .lock()
                .await
                .as_ref()
                .is_some_and(|turn| {
                    params
                        .turn_id
                        .as_ref()
                        .is_none_or(|requested| requested == turn)
                })
    }

    async fn start_elicitation(
        &self,
        peer: &JsonRpcPeer,
        id: RequestId,
        mut params: codex_app_server_protocol::McpServerElicitationRequestParams,
    ) -> Result<(), ExecutorError> {
        use codex_app_server_protocol::McpServerElicitationAction::Cancel;

        use super::elicitation;
        // IDs are scoped to this client/connection. Replayed IDs cannot create
        // another approval, reuse consent, or send a second conflicting response.
        if !self.elicitation_seen.lock().await.insert(id.clone()) {
            if let Some(cancel) = self.elicitations.lock().await.get(&id) {
                cancel.cancel();
            }
            self.elicitation_diagnostic(&id, "duplicate_request").await;
            return Ok(());
        }
        let consent_summary = elicitation::consent_summary(&params);
        let origin = if self.cancel.is_cancelled() || peer.disconnected().is_cancelled() {
            Some("process_stopped_or_disconnected")
        } else if !self.elicitation_context_valid(&params).await {
            Some("stale_context")
        } else if elicitation::supported_message(&params).is_none() {
            Some("unsupported_request")
        } else if consent_summary.is_none() {
            Some("insufficient_consent_context")
        } else {
            None
        };
        if let Some(origin) = origin {
            self.elicitation_diagnostic(&id, origin).await;
            return send_server_response(peer, id, elicitation::response(Cancel)).await;
        }
        // A nullable provider turn is best-effort correlation, not permission
        // to carry consent into a later turn.
        if params.turn_id.is_none() {
            params.turn_id = self.current_turn_id.lock().await.clone();
        }
        let client = self
            .self_ref
            .get()
            .and_then(Weak::upgrade)
            .expect("live client");
        let peer = peer.clone();
        let cancelled = self.cancel.child_token();
        self.elicitations
            .lock()
            .await
            .insert(id.clone(), cancelled.clone());
        // Keep reading lifecycle/stop messages and concurrent requests while
        // the operator decides. This is independent of command auto_approve.
        tokio::spawn(async move {
            let disconnected = peer.disconnected();
            let watcher_cancel = cancelled.clone();
            let watcher = tokio::spawn(async move {
                disconnected.cancelled().await;
                watcher_cancel.cancel();
            });
            let call_id = format!("vk-mcp-{}", Uuid::new_v4());
            let result = async {
                if cancelled.is_cancelled() {
                    return Err(ExecutorApprovalError::Cancelled);
                }
                let service = client
                    .approvals
                    .as_ref()
                    .ok_or(ExecutorApprovalError::ServiceUnavailable)?;
                let approval_id = service
                    .create_mcp_tool_approval(
                        consent_summary.as_deref().expect("validated context"),
                    )
                    .await?;
                if client
                    .log_writer
                    .log_raw(
                        &Approval::McpApprovalRequested {
                            call_id: call_id.clone(),
                            approval_id: approval_id.clone(),
                            message: consent_summary.expect("validated context"),
                            server_name: params.server_name.clone(),
                        }
                        .raw(),
                    )
                    .await
                    .is_err()
                {
                    cancelled.cancel();
                }
                // The normal bridge cancels/removes pending UI state when this
                // token fires, including disconnect, resolved request and stop.
                service
                    .wait_tool_approval(&approval_id, cancelled.clone())
                    .await
            }
            .await;
            watcher.abort();
            let (mut action, mut origin) = elicitation::outcome(result);
            if peer.disconnected().is_cancelled() {
                action = Cancel;
                origin = "disconnected";
            } else if client.cancel.is_cancelled() {
                action = Cancel;
                origin = "process_stopped";
            } else if cancelled.is_cancelled() {
                action = Cancel;
                origin = "request_cancelled";
            } else if !client.elicitation_context_valid(&params).await {
                action = Cancel;
                origin = "stale_context";
            }
            client.elicitations.lock().await.remove(&id);
            let _ = client
                .log_writer
                .log_raw(
                    &Approval::McpApprovalResolved {
                        call_id,
                        action,
                        origin: origin.to_owned(),
                    }
                    .raw(),
                )
                .await;
            client.elicitation_diagnostic(&id, origin).await;
            if send_server_response(&peer, id.clone(), elicitation::response(action))
                .await
                .is_err()
            {
                client
                    .elicitation_diagnostic(&id, "response_disconnected")
                    .await;
            }
        });
        Ok(())
    }

    async fn request_tool_approval(
        &self,
        tool_name: &str,
        display_tool_name: &str,
        tool_call_id: &str,
    ) -> Result<ApprovalStatus, ExecutorError> {
        if self.auto_approve {
            return Ok(ApprovalStatus::Approved);
        }
        let approval_service = self
            .approvals
            .as_ref()
            .ok_or(ExecutorApprovalError::ServiceUnavailable)?;

        let approval_id = approval_service
            .create_tool_approval(tool_name)
            .or_else(|err| async {
                self.handle_approval_error(display_tool_name, tool_call_id)
                    .await;
                Err(err)
            })
            .await?;

        let _ = self
            .log_writer
            .log_raw(
                &Approval::approval_requested(
                    tool_call_id.to_string(),
                    display_tool_name.to_string(),
                    approval_id.clone(),
                )
                .raw(),
            )
            .await;

        approval_service
            .wait_tool_approval(&approval_id, self.cancel.clone())
            .or_else(|err| async {
                self.handle_approval_error(display_tool_name, tool_call_id)
                    .await;
                Err(err)
            })
            .await
            .map_err(ExecutorError::from)
    }

    async fn handle_approval_error(&self, display_tool_name: &str, tool_call_id: &str) {
        let _ = self
            .log_writer
            .log_raw(
                &Approval::approval_response(
                    tool_call_id.to_string(),
                    display_tool_name.to_string(),
                    ApprovalStatus::TimedOut,
                )
                .raw(),
            )
            .await;
    }

    async fn request_question_answer(
        &self,
        question_count: usize,
        tool_call_id: &str,
    ) -> Result<QuestionStatus, ExecutorError> {
        let approval_service = self
            .approvals
            .as_ref()
            .ok_or(ExecutorApprovalError::ServiceUnavailable)?;

        let approval_id = approval_service
            .create_question_approval("question", question_count)
            .or_else(|err| async {
                self.handle_question_error(tool_call_id).await;
                Err(err)
            })
            .await?;

        let _ = self
            .log_writer
            .log_raw(
                &Approval::approval_requested(
                    tool_call_id.to_string(),
                    "codex.question".to_string(),
                    approval_id.clone(),
                )
                .raw(),
            )
            .await;

        approval_service
            .wait_question_answer(&approval_id, self.cancel.clone())
            .or_else(|err| async {
                self.handle_question_error(tool_call_id).await;
                Err(err)
            })
            .await
            .map_err(ExecutorError::from)
    }

    async fn handle_question_error(&self, tool_call_id: &str) {
        let _ = self
            .log_writer
            .log_raw(
                &Approval::question_response(tool_call_id.to_string(), QuestionStatus::TimedOut)
                    .raw(),
            )
            .await;
    }

    async fn handle_plan_completed(&self, plan: PendingPlan) -> Result<bool, ExecutorError> {
        let approval_service = self
            .approvals
            .as_ref()
            .ok_or(ExecutorApprovalError::ServiceUnavailable)?;

        let approval_id = approval_service
            .create_tool_approval("plan")
            .or_else(|err| async {
                self.handle_approval_error("codex.plan", &plan.item_id)
                    .await;
                Err(err)
            })
            .await?;

        let _ = self
            .log_writer
            .log_raw(
                &Approval::approval_requested(
                    plan.item_id.clone(),
                    "codex.plan".to_string(),
                    approval_id.clone(),
                )
                .raw(),
            )
            .await;

        let status = approval_service
            .wait_tool_approval(&approval_id, self.cancel.clone())
            .or_else(|err| async {
                self.handle_approval_error("codex.plan", &plan.item_id)
                    .await;
                Err(err)
            })
            .await
            .map_err(ExecutorError::from)?;

        self.log_writer
            .log_raw(
                &Approval::approval_response(
                    plan.item_id,
                    "codex.plan".to_string(),
                    status.clone(),
                )
                .raw(),
            )
            .await?;

        let Some(thread_id) = self.thread_id.lock().await.clone() else {
            return Ok(true);
        };

        match status {
            ApprovalStatus::Approved => {
                self.spawn_turn_start(
                    thread_id,
                    "Implement the plan.".to_string(),
                    Some(self.collaboration_mode(ModeKind::Default)?),
                );
                Ok(false)
            }
            ApprovalStatus::Denied { reason } => {
                let feedback = reason
                    .as_ref()
                    .map(|s| s.trim())
                    .filter(|s| !s.is_empty())
                    .map(|s| s.to_string());
                if let Some(feedback_text) = feedback {
                    self.spawn_turn_start(
                        thread_id,
                        format!("User feedback on the plan: {feedback_text}"),
                        Some(self.collaboration_mode(ModeKind::Plan)?),
                    );
                    Ok(false)
                } else {
                    Ok(true)
                }
            }
            ApprovalStatus::TimedOut | ApprovalStatus::Pending => Ok(true),
        }
    }

    pub async fn register_session(&self, thread_id: &str) -> Result<(), ExecutorError> {
        {
            let mut guard = self.thread_id.lock().await;
            guard.replace(thread_id.to_string());
        }
        self.flush_pending_feedback().await;
        Ok(())
    }

    async fn send_message<M>(&self, message: &M) -> Result<(), ExecutorError>
    where
        M: Serialize + Sync,
    {
        self.rpc().send(message).await
    }

    async fn send_request<R>(&self, request: ClientRequest, label: &str) -> Result<R, ExecutorError>
    where
        R: DeserializeOwned + std::fmt::Debug,
    {
        let request_id = request_id(&request);
        self.rpc()
            .request(request_id, &request, label, self.cancel.clone())
            .await
    }

    fn next_request_id(&self) -> RequestId {
        self.rpc().next_request_id()
    }

    fn command_execution_decision(
        &self,
        status: &ApprovalStatus,
    ) -> (CommandExecutionApprovalDecision, Option<String>) {
        if self.auto_approve {
            return (CommandExecutionApprovalDecision::AcceptForSession, None);
        }

        match status {
            ApprovalStatus::Approved => (CommandExecutionApprovalDecision::Accept, None),
            ApprovalStatus::Denied { reason } => {
                let feedback = reason
                    .as_ref()
                    .map(|s| s.trim())
                    .filter(|s| !s.is_empty())
                    .map(|s| s.to_string());
                if feedback.is_some() {
                    (CommandExecutionApprovalDecision::Cancel, feedback)
                } else {
                    (CommandExecutionApprovalDecision::Decline, None)
                }
            }
            ApprovalStatus::TimedOut => (CommandExecutionApprovalDecision::Decline, None),
            ApprovalStatus::Pending => (CommandExecutionApprovalDecision::Decline, None),
        }
    }

    fn file_change_decision(
        &self,
        status: &ApprovalStatus,
    ) -> (FileChangeApprovalDecision, Option<String>) {
        if self.auto_approve {
            return (FileChangeApprovalDecision::AcceptForSession, None);
        }

        match status {
            ApprovalStatus::Approved => (FileChangeApprovalDecision::Accept, None),
            ApprovalStatus::Denied { reason } => {
                let feedback = reason
                    .as_ref()
                    .map(|s| s.trim())
                    .filter(|s| !s.is_empty())
                    .map(|s| s.to_string());
                if feedback.is_some() {
                    (FileChangeApprovalDecision::Cancel, feedback)
                } else {
                    (FileChangeApprovalDecision::Decline, None)
                }
            }
            ApprovalStatus::TimedOut => (FileChangeApprovalDecision::Decline, None),
            ApprovalStatus::Pending => (FileChangeApprovalDecision::Decline, None),
        }
    }

    async fn enqueue_feedback(&self, message: String) {
        if message.trim().is_empty() {
            return;
        }
        let mut guard = self.pending_feedback.lock().await;
        guard.push_back(message);
    }

    pub async fn steer(&self, message: String) -> Result<bool, ExecutorError> {
        let message = message.trim();
        if message.is_empty() {
            return Ok(false);
        }
        let thread_id = self.thread_id.lock().await.clone();
        let turn_id = self.current_turn_id.lock().await.clone();
        let (Some(thread_id), Some(turn_id)) = (thread_id, turn_id) else {
            return Ok(false);
        };

        tracing::debug!(
            thread_id = %thread_id,
            turn_id = %turn_id,
            "steering active Codex turn"
        );
        self.turn_steer(
            thread_id,
            turn_id,
            vec![UserInput::Text {
                text: message.to_string(),
                text_elements: vec![],
            }],
        )
        .await?;
        Ok(true)
    }

    async fn has_pending_feedback(&self) -> bool {
        !self.pending_feedback.lock().await.is_empty()
    }

    async fn interrupt_current_turn_if_pending(&self) -> Result<(), ExecutorError> {
        if !self.has_pending_feedback().await {
            return Ok(());
        }

        let thread_id = self.thread_id.lock().await.clone();
        let turn_id = self.current_turn_id.lock().await.clone();
        if let (Some(thread_id), Some(turn_id)) = (thread_id, turn_id) {
            tracing::debug!(
                thread_id = %thread_id,
                turn_id = %turn_id,
                "interrupting Codex turn for pending follow-up"
            );
            if let Err(err) = self.turn_interrupt(thread_id, turn_id).await {
                tracing::warn!("failed to interrupt Codex turn for pending follow-up: {err}");
            }
        }

        Ok(())
    }

    /// Sends pending feedback messages as new turns.
    /// Returns `true` if any messages were sent.
    async fn flush_pending_feedback(&self) -> bool {
        let messages: Vec<String> = {
            let mut guard = self.pending_feedback.lock().await;
            guard.drain(..).collect()
        };

        if messages.is_empty() {
            return false;
        }

        let Some(thread_id) = self.thread_id.lock().await.clone() else {
            tracing::warn!(
                "pending Codex feedback but thread id unavailable; dropping {} messages",
                messages.len()
            );
            return false;
        };

        let mut sent = false;
        for message in messages {
            let trimmed = message.trim();
            if trimmed.is_empty() {
                continue;
            }
            self.spawn_user_message(thread_id.clone(), trimmed.to_string());
            sent = true;
        }
        sent
    }

    fn spawn_turn_start(
        &self,
        thread_id: String,
        message: String,
        collaboration_mode: Option<CollaborationMode>,
    ) {
        let peer = self.rpc().clone();
        let cancel = self.cancel.clone();
        let request = ClientRequest::TurnStart {
            request_id: peer.next_request_id(),
            params: TurnStartParams {
                thread_id,
                input: vec![UserInput::Text {
                    text: message,
                    text_elements: vec![],
                }],
                collaboration_mode,
                ..Default::default()
            },
        };
        tokio::spawn(async move {
            if let Err(err) = peer
                .request::<TurnStartResponse, _>(
                    request_id(&request),
                    &request,
                    "turn/start",
                    cancel,
                )
                .await
            {
                tracing::error!("failed to send user message: {err}");
            }
        });
    }

    fn spawn_user_message(&self, thread_id: String, message: String) {
        self.spawn_turn_start(thread_id, message, None);
    }
}

#[async_trait]
impl JsonRpcCallbacks for AppServerClient {
    async fn on_request(
        &self,
        peer: &JsonRpcPeer,
        raw: &str,
        request: JSONRPCRequest,
    ) -> Result<(), ExecutorError> {
        // Elicitation metadata may contain credentials, form values or tool prompts.
        // Only validated, redacted invocation context is retained for consent.
        if request.method == "mcpServer/elicitation/request" {
            return match ServerRequest::try_from(request.clone()) {
                Ok(ServerRequest::McpServerElicitationRequest { request_id, params }) => {
                    self.start_elicitation(peer, request_id, params).await
                }
                _ => {
                    if !self
                        .elicitation_seen
                        .lock()
                        .await
                        .insert(request.id.clone())
                    {
                        if let Some(cancel) = self.elicitations.lock().await.get(&request.id) {
                            cancel.cancel();
                        }
                        self.elicitation_diagnostic(&request.id, "duplicate_request")
                            .await;
                        return Ok(());
                    }
                    self.elicitation_diagnostic(&request.id, "malformed_or_unsupported")
                        .await;
                    send_server_response(
                        peer,
                        request.id,
                        super::elicitation::response(
                            codex_app_server_protocol::McpServerElicitationAction::Cancel,
                        ),
                    )
                    .await
                }
            };
        }
        self.log_writer.log_raw(raw).await?;
        match ServerRequest::try_from(request.clone()) {
            Ok(server_request) => self.handle_server_request(peer, server_request).await,
            Err(err) => {
                tracing::debug!("Unhandled server request `{}`: {err}", request.method);
                let response = JSONRPCResponse {
                    id: request.id,
                    result: Value::Null,
                };
                peer.send(&response).await
            }
        }
    }

    async fn on_response(
        &self,
        _peer: &JsonRpcPeer,
        raw: &str,
        response: &JSONRPCResponse,
    ) -> Result<(), ExecutorError> {
        if self.delegation_requests.lock().await.remove(&response.id) {
            return self.log_writer.log_raw(&serde_json::json!({"method":"vk/delegation/native","params":{"response":response}}).to_string()).await;
        }
        self.log_writer.log_raw(raw).await
    }

    async fn on_error(
        &self,
        _peer: &JsonRpcPeer,
        raw: &str,
        error: &JSONRPCError,
    ) -> Result<(), ExecutorError> {
        if self.delegation_requests.lock().await.remove(&error.id) {
            return self
                .log_writer
                .log_raw(
                    &serde_json::json!({"method":"vk/delegation/native","params":{"error":error}})
                        .to_string(),
                )
                .await;
        }
        self.log_writer.log_raw(raw).await
    }

    async fn on_notification(
        &self,
        _peer: &JsonRpcPeer,
        raw: &str,
        notification: JSONRPCNotification,
    ) -> Result<bool, ExecutorError> {
        if matches!(
            notification.method.as_str(),
            "turn/started" | "turn/completed"
        ) && notification
            .params
            .as_ref()
            .and_then(|p| p.get("threadId"))
            .and_then(Value::as_str)
            == self.thread_id.lock().await.as_deref()
        {
            for cancel in self.elicitations.lock().await.values() {
                cancel.cancel();
            }
        }
        if notification.method == "serverRequest/resolved"
            && let Some(params) = &notification.params
            && let Some(id) = params.get("requestId")
            && let Ok(id) = serde_json::from_value::<RequestId>(id.clone())
            && let Some(cancel) = self.elicitations.lock().await.get(&id)
        {
            cancel.cancel();
        }
        let method = notification.method.as_str();
        if let Some(control) = self.delegation.get() {
            match control
                .observe(
                    self,
                    method,
                    notification.params.as_ref().unwrap_or(&Value::Null),
                    raw,
                )
                .await
            {
                Ok(true) => return Ok(false),
                Ok(false) => {}
                Err(error) => {
                    self.abort_delegation_execution(&error).await;
                    return Err(ExecutorError::Io(io::Error::other(error)));
                }
            }
        }
        if should_log_notification(method) {
            self.log_writer.log_raw(raw).await?;
        }

        if method == "model/rerouted" && self.routing_locked.load(Ordering::SeqCst) {
            return Err(ExecutorError::Io(io::Error::other(
                "Provider changed an automatically routed model; execution stopped for review",
            )));
        }
        if method == "thread/goal/updated"
            && let Some(params) = notification.params.as_ref()
            && params.get("threadId").and_then(Value::as_str)
                == self.thread_id.lock().await.as_deref()
        {
            self.accept_goal(params.get("goal").cloned().unwrap_or(Value::Null))
                .await?;
            self.reconcile_goal_completion().await;
        }
        if method == "thread/goal/cleared"
            && let Some(params) = notification.params.as_ref()
            && params.get("threadId").and_then(Value::as_str)
                == self.thread_id.lock().await.as_deref()
        {
            *self.goal.lock().await = None;
        }
        // Existing threads cannot retrofit dynamic tools in Codex 0.153.4.
        // Accept the same checkpoint contract from a root assistant item only.
        if method == "item/completed"
            && let Some(params) = notification.params.as_ref()
            && params.get("threadId").and_then(Value::as_str)
                == self.thread_id.lock().await.as_deref()
            && params.get("turnId").and_then(Value::as_str)
                == self.current_turn_id.lock().await.as_deref()
            && params.pointer("/item/type").and_then(Value::as_str) == Some("agentMessage")
            && let Some(text) = params.pointer("/item/text").and_then(Value::as_str)
            && let Some(args) = goals::checkpoint_from_message(text)
        {
            let mut guard = self.goal.lock().await;
            if let Some((goal, progress)) = guard.as_mut()
                && matches!(goal.status.as_str(), "active" | "complete")
            {
                match progress.checkpoint(args) {
                    Ok(_) => {
                        goals::save(&goal.thread_id, progress).await?;
                        if goal.status == "active"
                            && let Some(reason) = progress.pause_reason.clone()
                        {
                            self.pause_goal(reason, false);
                        }
                    }
                    Err(error) => {
                        if goal.status == "active" {
                            self.pause_goal(format!("Invalid goal checkpoint: {error}"), false);
                        } else {
                            tracing::warn!("Invalid completion checkpoint: {error}");
                        }
                    }
                }
            }
        }

        if method == "turn/started"
            && let Some(ref params) = notification.params
            && let Ok(started) = serde_json::from_value::<TurnStartedNotification>(params.clone())
        {
            if self.thread_id.lock().await.as_deref() != Some(started.thread_id.as_str()) {
                return Ok(false);
            }
            {
                let mut guard = self.current_turn_id.lock().await;
                guard.replace(started.turn.id.clone());
            }
            if let Some(binding) = self.routing_telemetry.get() {
                binding.turn(&started.thread_id, &started.turn.id).await;
            }
            self.interrupt_current_turn_if_pending().await?;
            self.supply_goal_context(started.turn.id);
        }

        // Detect completed plan items in the notification stream
        if self.plan_mode
            && method == "item/completed"
            && let Some(ref params) = notification.params
            && let Ok(completed) =
                serde_json::from_value::<ItemCompletedNotification>(params.clone())
            && let ThreadItem::Plan { id, .. } = completed.item
        {
            *self.pending_plan.lock().await = Some(PendingPlan { item_id: id });
        }

        // V2 turn completion detection
        if method == "turn/completed" {
            let mut keep_alive = false;

            if let Some(params) = notification.params
                && let Ok(completed) = serde_json::from_value::<GoalTurnCompleted>(params)
            {
                if self.thread_id.lock().await.as_deref() != Some(completed.thread_id.as_str()) {
                    return Ok(false);
                }
                {
                    let mut guard = self.current_turn_id.lock().await;
                    if guard.as_deref() == Some(completed.turn.id.as_str()) {
                        guard.take();
                    }
                }

                if let Some(control) = self.delegation.get()
                    && control.active().await
                {
                    control.close();
                    let control = control.clone();
                    let client = self
                        .self_ref
                        .get()
                        .and_then(Weak::upgrade)
                        .expect("live client");
                    tokio::spawn(async move {
                        let _ = tokio::time::timeout(
                            Duration::from_secs(2),
                            control.cancel_all(&client),
                        )
                        .await;
                        client.abort_delegation_execution("Parent ended before collecting active children; children interrupted, working files preserved").await;
                    });
                    return Ok(false);
                }
                if completed.turn.status == TurnStatus::Failed {
                    return Err(ExecutorError::Io(io::Error::other(
                        "Codex native turn failed",
                    )));
                }
                if completed.turn.status == TurnStatus::Interrupted {
                    tracing::debug!("codex turn interrupted; flushing feedback queue");
                    if self.flush_pending_feedback().await {
                        keep_alive = true;
                    }
                } else if self.has_pending_feedback().await {
                    tracing::debug!(
                        "codex turn completed with pending follow-up; starting next turn"
                    );
                    if self.flush_pending_feedback().await {
                        keep_alive = true;
                    }
                }
                if !keep_alive {
                    if completed.turn.status == TurnStatus::Completed {
                        keep_alive = self.goal_turn_completed(&completed.turn.id).await?;
                    } else {
                        // Errors and user interrupts are never continuation signals.
                        return Ok(true);
                    }
                }
            }

            // Handle plan approval on turn completion
            let pending = if self.plan_mode {
                self.pending_plan.lock().await.take()
            } else {
                None
            };
            if let Some(plan) = pending {
                return self.handle_plan_completed(plan).await;
            }

            // Handle commit reminder on turn completion
            if !keep_alive
                && self.goal.lock().await.is_none()
                && self.commit_reminder
                && !self.commit_reminder_sent.swap(true, Ordering::SeqCst)
                && let status = self.repo_context.check_uncommitted_changes().await
                && !status.is_empty()
                && let Some(thread_id) = self.thread_id.lock().await.clone()
            {
                let prompt = format!("{}\n{}", self.commit_reminder_prompt, status);
                self.spawn_user_message(thread_id, prompt);
                return Ok(false);
            }

            return Ok(!keep_alive);
        }

        Ok(false)
    }

    async fn on_non_json(&self, raw: &str) -> Result<(), ExecutorError> {
        self.log_writer.log_raw(raw).await?;
        Ok(())
    }
}

async fn send_server_response<T>(
    peer: &JsonRpcPeer,
    request_id: RequestId,
    response: T,
) -> Result<(), ExecutorError>
where
    T: Serialize,
{
    let payload = JSONRPCResponse {
        id: request_id,
        result: serde_json::to_value(response)
            .map_err(|err| ExecutorError::Io(io::Error::other(err.to_string())))?,
    };

    peer.send(&payload).await
}

/// Convert our `HashMap<question_text, Vec<answer_labels>>` answer format to
/// Codex's `HashMap<question_id, ToolRequestUserInputAnswer>` format.
fn answers_to_codex_format(
    questions: &[ToolRequestUserInputQuestion],
    answers: &HashMap<String, Vec<String>>,
) -> ToolRequestUserInputResponse {
    let codex_answers = questions
        .iter()
        .filter_map(|q| {
            answers.get(&q.question).map(|answer_vec| {
                (
                    q.id.clone(),
                    ToolRequestUserInputAnswer {
                        answers: answer_vec.clone(),
                    },
                )
            })
        })
        .collect();

    ToolRequestUserInputResponse {
        answers: codex_answers,
    }
}

fn request_id(request: &ClientRequest) -> RequestId {
    request.id().clone()
}

fn should_log_notification(method: &str) -> bool {
    !matches!(method, "account/rateLimits/updated")
}

#[derive(Clone)]
pub struct LogWriter {
    writer: Arc<Mutex<BufWriter<Box<dyn AsyncWrite + Send + Unpin>>>>,
}

impl LogWriter {
    pub fn new(writer: impl AsyncWrite + Send + Unpin + 'static) -> Self {
        Self {
            writer: Arc::new(Mutex::new(BufWriter::new(Box::new(writer)))),
        }
    }

    pub async fn log_raw(&self, raw: &str) -> Result<(), ExecutorError> {
        let mut guard = self.writer.lock().await;
        guard
            .write_all(raw.as_bytes())
            .await
            .map_err(ExecutorError::Io)?;
        guard.write_all(b"\n").await.map_err(ExecutorError::Io)?;
        guard.flush().await.map_err(ExecutorError::Io)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use codex_app_server_protocol::ThreadResumeParams;

    use super::*;

    #[test]
    fn request_id_supports_thread_resume() {
        let expected_id = RequestId::Integer(42);
        let request = ClientRequest::ThreadResume {
            request_id: expected_id.clone(),
            params: ThreadResumeParams {
                thread_id: "thread-id".to_string(),
                ..Default::default()
            },
        };

        assert_eq!(expected_id, request_id(&request));
    }

    #[test]
    fn turn_steer_targets_the_expected_active_turn() {
        let expected_id = RequestId::Integer(43);
        let request = ClientRequest::TurnSteer {
            request_id: expected_id.clone(),
            params: TurnSteerParams {
                thread_id: "thread-id".to_string(),
                expected_turn_id: "active-turn-id".to_string(),
                input: vec![UserInput::Text {
                    text: "Use the existing API instead.".to_string(),
                    text_elements: vec![],
                }],
            },
        };

        assert_eq!(expected_id, request_id(&request));
        let serialized = serde_json::to_value(&request).expect("serialize turn/steer request");
        assert_eq!(serialized["method"], "turn/steer");
        assert_eq!(serialized["params"]["threadId"], "thread-id");
        assert_eq!(serialized["params"]["expectedTurnId"], "active-turn-id");
    }
}

#[cfg(test)]
mod goal_integration_tests {
    use tokio::process::Command;

    use super::*;

    #[tokio::test]
    async fn completion_reconciliation_steers_once_without_starting_a_turn() {
        use std::process::Stdio;

        use tokio::io::{AsyncBufReadExt, BufReader};
        let cancel = CancellationToken::new();
        let client = AppServerClient::new(
            LogWriter::new(tokio::io::sink()),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        *client.thread_id.lock().await = Some("root".into());
        *client.current_turn_id.lock().await = Some("finishing".into());
        *client.goal.lock().await = Some((
            NativeGoal {
                thread_id: "root".into(),
                objective: "Deliver feature".into(),
                status: "complete".into(),
                created_at: 1,
            },
            Progress::default(),
        ));
        // A stopped execution must not send any request (no peer attached yet).
        client.capacity_stopped.store(true, Ordering::SeqCst);
        client.reconcile_goal_completion().await;
        assert!(!client.completion_reconciliation_sent.load(Ordering::SeqCst));
        client.capacity_stopped.store(false, Ordering::SeqCst);
        let mut child = Command::new("python3")
            .args([
                "-u",
                "-c",
                r#"
import json, sys
for line in sys.stdin:
    request = json.loads(line)
    print(line.strip(), file=sys.stderr, flush=True)
    print(json.dumps({"id": request["id"], "result": {"turnId": "finishing"}}), flush=True)
"#,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .unwrap();
        let mut requests = BufReader::new(child.stderr.take().unwrap()).lines();
        let (exit_tx, _exit_rx) = tokio::sync::oneshot::channel();
        let peer = JsonRpcPeer::spawn(
            child.stdin.take().unwrap(),
            child.stdout.take().unwrap(),
            client.clone(),
            ExitSignalSender::new(exit_tx),
            cancel.clone(),
        );
        assert!(client.rpc.set(peer).is_ok());
        client.reconcile_goal_completion().await;
        client.reconcile_goal_completion().await;
        let raw = tokio::time::timeout(Duration::from_secs(5), requests.next_line())
            .await
            .unwrap()
            .unwrap()
            .unwrap();
        let request: Value = serde_json::from_str(&raw).unwrap();
        assert_eq!(request["method"], "turn/steer");
        assert_eq!(request["params"]["threadId"], "root");
        assert_eq!(request["params"]["expectedTurnId"], "finishing");
        assert!(
            tokio::time::timeout(Duration::from_millis(100), requests.next_line())
                .await
                .is_err()
        );
        cancel.cancel();
        child.kill().await.unwrap();
        child.wait().await.unwrap();
    }

    #[tokio::test]
    async fn incomplete_completion_is_metadata_and_does_not_continue_the_goal() {
        use tokio::io::AsyncReadExt;
        let (writer, mut reader) = tokio::io::duplex(8192);
        let client = AppServerClient::new(
            LogWriter::new(writer),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            CancellationToken::new(),
        );
        let mut progress = Progress::default();
        progress
            .requirements
            .insert("delivery".into(), "Verify deployment".into());
        *client.goal.lock().await = Some((
            NativeGoal {
                thread_id: "root".into(),
                objective: "Deliver feature".into(),
                status: "complete".into(),
                created_at: 1,
            },
            progress,
        ));
        assert!(!client.goal_turn_completed("finished").await.unwrap());
        let mut buffer = [0; 8192];
        let count = reader.read(&mut buffer).await.unwrap();
        let logged = String::from_utf8_lossy(&buffer[..count]);
        assert!(logged.contains("Completion:: Unverified"));
        assert!(logged.contains("delivery: Verify deployment"));
        assert!(!logged.contains("Codex reported completion"));
        // Stop and capacity guards take precedence even over completion handling.
        client.capacity_stopped.store(true, Ordering::SeqCst);
        assert!(client.goal_turn_completed("stopped").await.unwrap());
    }

    #[tokio::test]
    async fn ordinary_turns_remain_finite_and_descendant_goals_are_ignored() {
        let client = AppServerClient::new(
            LogWriter::new(tokio::io::sink()),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            CancellationToken::new(),
        );
        client.register_session("root").await.unwrap();
        // A peer is not needed for ordinary lifecycle events. Build a real peer
        // only in the native integration test below.
        for status in ["completed", "failed", "interrupted"] {
            let completed: GoalTurnCompleted = serde_json::from_value(serde_json::json!({
                "threadId":"root", "turn":{"id":"turn", "status":status,
                    "items":[{"type":"futureProtocolItem"}]}
            }))
            .unwrap();
            assert_eq!(completed.thread_id, "root");
        }
        assert!(!client.goal_turn_completed("ordinary").await.unwrap());
        client.accept_goal(serde_json::json!({"threadId":"child", "objective":"child task", "status":"active", "createdAt":1})).await.unwrap();
        assert!(client.goal.lock().await.is_none());
        let id = Uuid::new_v4();
        AppServerClient::register_active_execution(id, &client);
        assert!(
            active_codex_clients()
                .lock()
                .unwrap()
                .get(&id)
                .unwrap()
                .upgrade()
                .is_some()
        );
        drop(client);
        assert!(!active_codex_clients().lock().unwrap().contains_key(&id));
    }

    #[tokio::test]
    #[ignore = "requires isolated CODEX_HOME; offline unless VK_GOAL_TEST_SCENARIO=real explicitly opts into model usage"]
    async fn native_goal_runtime() {
        let home = std::env::var("CODEX_HOME").expect("isolated CODEX_HOME");
        assert!(
            home.contains("vk-continuation"),
            "Never test in the live Codex home"
        );
        let scenario = std::env::var("VK_GOAL_TEST_SCENARIO").unwrap_or_else(|_| "progress".into());
        let work = std::path::Path::new(&home).join("work");
        tokio::fs::create_dir_all(&work).await.unwrap();
        let real = scenario == "real";
        let mut command = if real {
            let mut command = Command::new("codex");
            command.arg("app-server");
            command
        } else {
            let mut command = Command::new("python3");
            command.arg(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../scripts/testing/codex_goal_provider.py"
            ));
            command
        };
        use workspace_utils::command_ext::GroupSpawnNoWindowExt;
        let guarded = std::env::var("VK_GOAL_TEST_GUARD").ok().map(|guard| {
            assert_eq!(scenario, "capacity-expiry");
            let now = crate::capacity::wall_ms();
            crate::capacity::CapacityExecution {
                issuer_epoch: crate::capacity::issuer_epoch().into(),
                id: Uuid::new_v4().to_string(),
                allocation_id: "old-week:day".into(),
                expires_at_ms: now + 6000,
                stop_at_ms: now + 8000,
                lease_file: std::path::Path::new(&home)
                    .join(format!("{}.json", Uuid::new_v4()))
                    .to_string_lossy()
                    .into_owned(),
                guard_binary: guard,
            }
            .prepare(&Uuid::new_v4().to_string())
            .unwrap()
        });
        let mut child = if let Some(capacity) = &guarded {
            let env = [
                "PATH",
                "HOME",
                "CODEX_HOME",
                "VK_GOAL_TEST_SCENARIO",
                "VK_GOAL_TEST_CODEX",
            ]
            .into_iter()
            .filter_map(|key| std::env::var(key).ok().map(|value| (key.to_owned(), value)))
            .collect();
            crate::systemd_run::spawn_capacity_unit(
                &crate::systemd_run::build_unit_name("capacity-native-test"),
                &work,
                std::path::Path::new("/usr/bin/python3"),
                &[concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/../../scripts/testing/codex_goal_provider.py"
                )
                .into()],
                &env,
                capacity,
            )
            .unwrap()
        } else {
            command
                .stdin(std::process::Stdio::piped())
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::null())
                .kill_on_drop(true)
                .group_spawn_no_window()
                .unwrap()
        };
        let (tx, mut rx) = tokio::sync::oneshot::channel();
        let signal = ExitSignalSender::new(tx);
        let cancel = CancellationToken::new();
        let client = AppServerClient::new(
            LogWriter::new(
                tokio::fs::File::create(std::path::Path::new(&home).join("protocol.jsonl"))
                    .await
                    .unwrap(),
            ),
            None,
            false,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        client.set_exit_signal(signal.clone());
        let peer = JsonRpcPeer::spawn(
            child.inner().stdin.take().unwrap(),
            child.inner().stdout.take().unwrap(),
            client.clone(),
            signal,
            cancel.clone(),
        );
        client.connect(peer);
        client.initialize().await.unwrap();
        let params = ThreadStartParams {
            model: if real { None } else { Some("fixture".into()) },
            model_provider: if real { None } else { Some("fixture".into()) },
            cwd: Some(work.to_string_lossy().into_owned()),
            approval_policy: Some(codex_app_server_protocol::AskForApproval::Never),
            sandbox: Some(codex_app_server_protocol::SandboxMode::DangerFullAccess),
            developer_instructions: Some(goals::INSTRUCTIONS.into()),
            dynamic_tools: Some(vec![goals::tool_spec()]),
            ..Default::default()
        };
        let resume_thread = std::env::var("VK_GOAL_TEST_RESUME_THREAD").ok();
        let id = if let Some(id) = resume_thread.as_ref() {
            let resumed = client
                .thread_resume(super::super::resume_params_from(id.clone(), params))
                .await
                .unwrap();
            assert_eq!(
                serde_json::to_value(&resumed.sandbox).unwrap()["type"],
                "dangerFullAccess",
                "An ordinary resume must restore its requested permissions"
            );
            resumed.thread.id
        } else {
            client.thread_start(params).await.unwrap().thread.id
        };
        client.register_session(&id).await.unwrap();
        let objective = if real {
            "Build a dependency-free Python 3 event_report CLI in the current directory. python3 -m event_report reads NDJSON from stdin or a filename argument. Each record has string id, string category, integer amount. Reject malformed records with a nonzero exit and a helpful line number. Trim and lowercase categories, keep the last record per id, and emit a JSON object keyed by sorted category with count and total (including negative amounts). Add unittest coverage and README usage. Do not access other directories, network, or install dependencies. For this continuation evaluation, implement and verify at most one material checklist requirement per turn, then checkpoint and end that turn with the goal active until the full objective is complete. Define requirements covering parsing, normalization, deduplication, aggregation, CLI, tests and documentation."
        } else {
            "Verify eight distinct parity requirements"
        };
        let params = if resume_thread.is_some() {
            client.refresh_goal().await.unwrap();
            client.reset_goal_run(false).await.unwrap();
            serde_json::json!({"threadId": id, "status":"active"})
        } else {
            serde_json::json!({"threadId": id, "objective":objective, "status":"active"})
        };
        client
            .goal_request("thread/goal/set", params)
            .await
            .unwrap();
        if scenario.starts_with("capacity") {
            let marker = std::path::Path::new(&home).join("capacity-request-active");
            for _ in 0..500 {
                if marker.exists() && client.current_turn_id.lock().await.is_some() {
                    break;
                }
                sleep(Duration::from_millis(10)).await;
            }
            assert!(
                marker.exists(),
                "Exercise a model request that is still active"
            );
            assert!(client.current_turn_id.lock().await.is_some());
            let execution_id = Uuid::new_v4();
            AppServerClient::register_active_execution(execution_id, &client);
            let snapshot = client
                .goal_request("thread/goal/get", serde_json::json!({"threadId": id}))
                .await
                .unwrap();
            let baseline = std::path::Path::new(&home).join("capacity-goal-before.json");
            if resume_thread.is_some() {
                let before: Value =
                    serde_json::from_slice(&std::fs::read(&baseline).unwrap()).unwrap();
                for key in ["threadId", "objective", "createdAt"] {
                    assert_eq!(
                        snapshot["goal"][key], before["goal"][key],
                        "Resume preserves {key}"
                    );
                }
            } else {
                std::fs::write(&baseline, serde_json::to_vec(&snapshot).unwrap()).unwrap();
            }
            std::fs::write(std::path::Path::new(&home).join("capacity-thread-id"), &id).unwrap();
            if scenario == "capacity-stop" {
                let before = std::time::Instant::now();
                AppServerClient::suspend_capacity_execution(
                    execution_id,
                    "Test overnight stop".into(),
                )
                .await
                .unwrap();
                assert!(
                    before.elapsed() < Duration::from_secs(3),
                    "Do not wait for 30-second model response"
                );
            } else if let Some(capacity) = &guarded {
                client.watch_capacity(capacity.clone());
            } else {
                use std::os::unix::fs::PermissionsExt;
                let now = crate::capacity::wall_ms();
                let file = std::path::Path::new(&home).join("capacity-permission.json");
                let lease = capacity_guard::Lease {
                    version: 1,
                    id: Uuid::new_v4().to_string(),
                    allocation_id: "old-week:day".into(),
                    execution_id: execution_id.to_string(),
                    expires_at_ms: now + 6000,
                    stop_at_ms: now + 8000,
                    sequence: 0,
                    revoked: false,
                };
                std::fs::write(&file, serde_json::to_vec(&lease).unwrap()).unwrap();
                std::fs::set_permissions(&file, std::fs::Permissions::from_mode(0o600)).unwrap();
                client.watch_capacity(crate::capacity::PreparedCapacity {
                    file,
                    guard: std::path::PathBuf::new(),
                    lease,
                });
            }
        }
        if scenario == "stop" {
            let execution_id = Uuid::new_v4();
            AppServerClient::register_active_execution(execution_id, &client);
            for _ in 0..200 {
                if client
                    .goal
                    .lock()
                    .await
                    .as_ref()
                    .is_some_and(|(_, p)| p.turns > 0)
                {
                    break;
                }
                sleep(Duration::from_millis(10)).await;
            }
            AppServerClient::pause_execution_goal(execution_id)
                .await
                .unwrap();
        }
        let outcome =
            tokio::time::timeout(Duration::from_secs(if real { 600 } else { 50 }), &mut rx).await;
        assert!(
            outcome.is_ok(),
            "native runtime failed to return control: {:?}",
            client.goal.lock().await
        );
        let guard = client.goal.lock().await;
        let (goal, progress) = guard.as_ref().expect("native goal snapshot");
        match scenario.as_str() {
            "real" => {
                assert_eq!(goal.status, "complete");
                assert!(progress.all_complete());
                assert!(progress.turns >= 3, "Exercise multiple actual goal turns");
                let check = Command::new("python3").arg("-c").arg(r#"
import json, subprocess, sys
payload='{"id":"a","category":" Food ","amount":9}\n{"id":"b","category":"FOOD","amount":-2}\n{"id":"a","category":" travel ","amount":4}\n'
p=subprocess.run([sys.executable,'-m','event_report'],input=payload,text=True,capture_output=True)
assert p.returncode==0, p.stderr
assert json.loads(p.stdout)=={'food':{'count':1,'total':-2},'travel':{'count':1,'total':4}},p.stdout
p=subprocess.run([sys.executable,'-m','event_report'],input=payload+'bad json\n',text=True,capture_output=True)
assert p.returncode!=0 and '4' in p.stderr, (p.returncode,p.stderr)
"#).current_dir(&work).output().await.unwrap();
                assert!(
                    check.status.success(),
                    "{}",
                    String::from_utf8_lossy(&check.stderr)
                );
            }
            "progress" | "tool" | "recover" => {
                assert_eq!(goal.status, "complete");
                assert_eq!(progress.completed.len(), 8);
                assert!(progress.turns >= 8);
                if scenario == "recover" {
                    let protocol = tokio::fs::read_to_string(
                        std::path::Path::new(&home).join("protocol.jsonl"),
                    )
                    .await
                    .unwrap();
                    assert!(
                        protocol.contains("AUTOMATIC RECOVERY 1/3"),
                        "Recover only after VK actually delivered the recovery instruction"
                    );
                    assert!(progress.pause_reason.is_none());
                    assert_eq!(progress.stagnant_turns, 0);
                }
            }
            "loop" => {
                assert_eq!(goal.status, "paused");
                assert_eq!(progress.completed.len(), 1);
                assert_eq!(progress.stagnant_turns, 24);
            }
            "needs_input" | "stop" | "capacity-stop" | "capacity-expiry" => {
                assert_eq!(goal.status, "paused")
            }
            _ => panic!("unknown scenario"),
        }
        let restored = goals::load(goal).await.unwrap();
        assert_eq!(restored.completed, progress.completed);
        if scenario.starts_with("capacity") {
            assert!(
                !restored.completed.is_empty(),
                "A scheduled pause must preserve actual completed checkpoint evidence"
            );
            assert!(
                client
                    .goal_request(
                        "thread/goal/set",
                        serde_json::json!({"threadId": id, "status":"active"})
                    )
                    .await
                    .is_err(),
                "Stopped execution must not reactivate even if ordinary goal-pause bookkeeping is reset"
            );
        }
        drop(guard);
        cancel.cancel();
        if let Some(capacity) = guarded {
            tokio::time::timeout(Duration::from_secs(10), child.wait())
                .await
                .unwrap()
                .unwrap();
            assert!(
                crate::capacity::wall_ms() < capacity.lease.stop_at_ms,
                "Guarded native work must exit before the hard deadline"
            );
        }
        child.kill().await.ok();
    }
}

#[cfg(test)]
mod delegation_tests {
    use super::*;
    use crate::{
        env::ExecutionEnv,
        executors::codex::delegation::Delegation,
        routing::{RoutingDecision, RoutingPolicy},
    };

    /// Two bounded native turns, no parent inference and no live VK server. Explicit opt-in only.
    #[tokio::test]
    #[ignore = "uses two native child inference turns; requires candidate launcher/proof and task artifact directory"]
    async fn native_delegation_boundaries() {
        eprintln!(
            "Native capacity inventory: {} app-server chains; configured limit {}",
            super::super::active_codex_execution_count(),
            super::super::codex_max_active_executions()
        );
        if let Some(error) = super::super::codex_execution_limit_error() {
            panic!("Native execution capacity unavailable; do not bypass it: {error}");
        }
        let dir = std::path::PathBuf::from(
            std::env::var("VK_DELEGATION_TEST_DIR").expect("artifact directory"),
        );
        assert!(dir.starts_with("/mnt/vk-storage/"));
        tokio::fs::create_dir_all(&dir).await.unwrap();
        let work = dir.join("work");
        tokio::fs::create_dir_all(&work).await.unwrap();
        if !work.join(".git").exists() {
            tokio::fs::write(work.join("dirty.txt"), "baseline\n")
                .await
                .unwrap();
            for args in [
                vec!["init", "-q"],
                vec!["add", "dirty.txt"],
                vec![
                    "-c",
                    "user.name=VK fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "Fixture baseline",
                ],
            ] {
                assert!(
                    tokio::process::Command::new("git")
                        .args(args)
                        .current_dir(&work)
                        .status()
                        .await
                        .unwrap()
                        .success()
                );
            }
        }
        tokio::fs::write(
            work.join("README.md"),
            "This is teh example.\nAnother teh example.\n",
        )
        .await
        .unwrap();
        tokio::fs::write(work.join("dirty.txt"), "operator work, preserve exactly\n")
            .await
            .unwrap();
        let launcher = std::env::var("VK_CODEX_BASE_COMMAND").unwrap();
        // The checked candidate launcher is an executable path, never shell-evaluated.
        let mut command = tokio::process::Command::new(&launcher);
        command
            .args([
                "app-server",
                "-c",
                "features.multi_agent=false",
                "-c",
                "features.multi_agent_v2=false",
            ])
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .kill_on_drop(true);
        use workspace_utils::command_ext::GroupSpawnNoWindowExt;
        let mut process = command.group_spawn_no_window().unwrap();
        let cancel = CancellationToken::new();
        let (tx, mut rx) = tokio::sync::oneshot::channel();
        let signal = ExitSignalSender::new(tx);
        let client = AppServerClient::new(
            LogWriter::new(
                tokio::fs::File::create(dir.join("native.jsonl"))
                    .await
                    .unwrap(),
            ),
            None,
            true,
            false,
            RepoContext::default(),
            false,
            String::new(),
            cancel.clone(),
        );
        let peer = JsonRpcPeer::spawn(
            process.inner().stdin.take().unwrap(),
            process.inner().stdout.take().unwrap(),
            client.clone(),
            signal.clone(),
            cancel.clone(),
        );
        client.connect(peer.clone());
        client.set_exit_signal(signal);
        client.initialize().await.unwrap();
        let account = client.get_account().await.unwrap();
        let proof = crate::routing::load_availability().unwrap();
        assert_eq!(
            crate::routing::account_fingerprint(&serde_json::to_value(account.account).unwrap()),
            proof.account_fingerprint
        );
        let config = client
            .goal_request("config/read", serde_json::json!({"includeLayers":false}))
            .await
            .unwrap();
        let mut overrides = std::collections::HashMap::new();
        for feature in [
            "multi_agent",
            "multi_agent_v2",
            "goals",
            "apps",
            "plugins",
            "hooks",
            "plugin_hooks",
        ] {
            overrides.insert(format!("features.{feature}"), serde_json::json!(false));
        }
        if let Some(servers) = config
            .pointer("/config/mcp_servers")
            .and_then(Value::as_object)
        {
            for name in servers.keys() {
                overrides.insert(
                    format!("mcp_servers.{name}.enabled"),
                    serde_json::json!(false),
                );
            }
        }
        overrides.insert("model_reasoning_effort".into(), serde_json::json!("medium"));
        let params = ThreadStartParams {
            model: Some("gpt-6.1-sol".into()),
            cwd: Some(work.to_string_lossy().into()),
            approval_policy: Some(codex_app_server_protocol::AskForApproval::Never),
            sandbox: Some(codex_app_server_protocol::SandboxMode::DangerFullAccess),
            config: Some(overrides),
            dynamic_tools: Some(vec![super::super::delegation::tool_spec()]),
            ..Default::default()
        };
        let root = client.thread_start(params.clone()).await.unwrap();
        client.register_session(&root.thread.id).await.unwrap();
        let parent_turn = "harness-parent-boundary";
        *client.current_turn_id.lock().await = Some(parent_turn.into());
        let policy: RoutingPolicy = serde_json::from_value(
            serde_json::json!({"mode":"auto","floor":"assessed","allow_escalation":true}),
        )
        .unwrap();
        let decision:RoutingDecision=serde_json::from_value(serde_json::json!({"version":2,"id":Uuid::new_v4(),"mode":"auto","floor":"workhorse","reason":"native development harness","assessed_envelope":"normal","service_tier":"standard","escalated":false,"account_fingerprint":proof.account_fingerprint})).unwrap();
        let mut env = ExecutionEnv::new(RepoContext::default(), false, String::new());
        let execution = Uuid::new_v4().to_string();
        env.insert("VK_EXECUTION_PROCESS_ID", execution.clone());
        let control=Delegation::new(policy,decision,root.thread.id.clone(),params,env,serde_json::json!({"model":"gpt-6.1-sol","reasoningEffort":"medium","accountFingerprint":proof.account_fingerprint}),1).await.unwrap();
        client.set_delegation(control.clone());
        let args = serde_json::json!({"action":"start","task":"spelling","message":"Fix spelling typos in README.md","context":"Replace both occurrences of teh with the. Preserve dirty.txt exactly. Use no network. Report the number of corrected occurrences.","paths":["README.md"],"independent":true,"size":"batch","read_only":false});
        let initial = tokio::time::timeout(
            Duration::from_secs(45),
            control.handle(client.clone(), parent_turn.into(), args.clone()),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(initial["effective"]["model"], "gpt-5.6-luna");
        assert_eq!(initial["effective"]["reasoningEffort"], "low");
        let deadline = tokio::time::Instant::now() + Duration::from_secs(90);
        while control.active().await {
            assert!(tokio::time::Instant::now() < deadline);
            sleep(Duration::from_millis(200)).await;
        }
        let initial = control
            .handle(
                client.clone(),
                parent_turn.into(),
                serde_json::json!({"action":"status","task":"spelling"}),
            )
            .await
            .unwrap();
        assert_eq!(initial["status"], "completed");
        assert!(rx.try_recv().is_err(), "Child completion must not end root");
        assert_eq!(
            client.thread_id.lock().await.as_deref(),
            Some(root.thread.id.as_str())
        );
        assert_eq!(
            tokio::fs::read_to_string(work.join("README.md"))
                .await
                .unwrap(),
            "This is the example.\nAnother the example.\n"
        );
        let duplicate = control
            .handle(client.clone(), parent_turn.into(), args.clone())
            .await
            .unwrap();
        assert_eq!(duplicate["reused"], true);
        // Deterministic fixture of two distinct native validation failures: test escalation admission
        // without manufacturing a destructive implementation or paying for repeated bad fixes.
        for item in ["validation-a", "validation-b", "validation-b"] {
            let params = serde_json::json!({"threadId":initial["native_thread_id"],"turnId":initial["native_turn_id"],"item":{"id":item,"type":"commandExecution","command":"node --test regression.js","exitCode":1}});
            let raw = serde_json::json!({"method":"item/completed","params":params}).to_string();
            control
                .observe(&client, "item/completed", &params, &raw)
                .await
                .unwrap();
        }
        let mut follow = args;
        follow["action"] = serde_json::json!("follow_up");
        follow["message"] = serde_json::json!(
            "Continue the spelling task. Verify the previous corrections and preserve all working files."
        );
        let follow = control
            .handle(client.clone(), parent_turn.into(), follow)
            .await
            .unwrap();
        assert_eq!(follow["effective"]["model"], "gpt-6.1-sol");
        assert_eq!(follow["effective"]["reasoningEffort"], "medium");
        assert_eq!(follow["native_thread_id"], initial["native_thread_id"]);
        assert_eq!(follow["delegation_id"], initial["delegation_id"]);
        assert_eq!(follow["recommended"]["escalated"], true);
        let deadline = tokio::time::Instant::now() + Duration::from_secs(90);
        while control.active().await {
            assert!(tokio::time::Instant::now() < deadline);
            sleep(Duration::from_millis(200)).await;
        }
        let follow = control
            .handle(
                client.clone(),
                parent_turn.into(),
                serde_json::json!({"action":"status","task":"spelling"}),
            )
            .await
            .unwrap();
        assert_eq!(follow["status"], "completed");
        assert_eq!(
            tokio::fs::read_to_string(work.join("dirty.txt"))
                .await
                .unwrap(),
            "operator work, preserve exactly\n"
        );
        assert_eq!(super::super::delegation::active_count(), 0);
        let evidence = serde_json::json!({"parentThreadId":root.thread.id,"parentTurn":"harness-only; no parent inference","executionId":execution,"initial":initial,"followup":follow,"failureEvidence":"two injected distinct command-completed failures, one duplicate ignored","dirtyStatePreserved":true,"duplicateStartReused":true});
        tokio::fs::write(
            dir.join("result.json"),
            serde_json::to_vec_pretty(&evidence).unwrap(),
        )
        .await
        .unwrap();
        cancel.cancel();
        process.kill().await.unwrap();
    }
}
