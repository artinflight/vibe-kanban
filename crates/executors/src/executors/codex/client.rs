use std::{
    collections::{HashMap, VecDeque},
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
    log_writer: LogWriter,
    approvals: Option<Arc<dyn ExecutorApprovalService>>,
    thread_id: Mutex<Option<String>>,
    current_turn_id: Mutex<Option<String>>,
    pending_feedback: Mutex<VecDeque<String>>,
    auto_approve: bool,
    plan_mode: bool,
    resolved_model: OnceLock<String>,
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
            log_writer,
            approvals,
            auto_approve,
            plan_mode,
            resolved_model: OnceLock::new(),
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
            execution_id: OnceLock::new(),
        });
        let _ = client.self_ref.set(Arc::downgrade(&client));
        client
    }

    pub fn set_exit_signal(&self, signal: ExitSignalSender) {
        let _ = self.exit_signal.set(signal);
    }

    /// Goal APIs postdate our pinned protocol types; keep this narrow wire adapter
    /// rather than upgrading every executor protocol as part of this feature.
    pub async fn goal_request(&self, method: &str, params: Value) -> Result<Value, ExecutorError> {
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
        let mut guard = self.goal.lock().await;
        if let Some((old, progress)) = guard.as_mut()
            && old.objective == goal.objective
            && old.created_at == goal.created_at
        {
            *old = goal;
            goals::save(&old.thread_id, progress).await?;
        } else {
            let progress = goals::load(&goal).await?;
            *guard = Some((goal, progress));
        }
        Ok(())
    }

    pub async fn reset_goal_run(&self) -> Result<(), ExecutorError> {
        let mut guard = self.goal.lock().await;
        if let Some((goal, progress)) = guard.as_mut() {
            progress.resume();
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
        if self.goal_pausing.load(Ordering::SeqCst) {
            return Ok(true);
        }
        let mut guard = self.goal.lock().await;
        let Some((goal, progress)) = guard.as_mut() else {
            return Ok(false);
        };
        if goal.status != "active" {
            if goal.status == "complete" && !progress.all_complete() {
                super::slash_commands::log_event_raw(self.log_writer(),
                    "Codex reported completion, but the VK checklist is incomplete. Completion needs review against the full objective.".into()).await?;
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
        let request = ClientRequest::TurnStart {
            request_id: self.next_request_id(),
            params: TurnStartParams {
                thread_id,
                input,
                collaboration_mode,
                ..Default::default()
            },
        };
        self.send_request(request, "turn/start").await
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
                reasoning_effort: None,
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
                        Some((goal, progress)) if goal.status == "active" => {
                            let result = progress.checkpoint(params.arguments);
                            if result.is_ok() {
                                goals::save(&goal.thread_id, progress).await?;
                                if let Some(reason) = progress.pause_reason.clone() {
                                    self.pause_goal(reason, false);
                                }
                            }
                            result
                        }
                        _ => Err("No active native goal. Do not create a goal without user authorization.".into()),
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
            ServerRequest::ChatgptAuthTokensRefresh { .. }
            | ServerRequest::McpServerElicitationRequest { .. }
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
        _response: &JSONRPCResponse,
    ) -> Result<(), ExecutorError> {
        self.log_writer.log_raw(raw).await
    }

    async fn on_error(
        &self,
        _peer: &JsonRpcPeer,
        raw: &str,
        _error: &JSONRPCError,
    ) -> Result<(), ExecutorError> {
        self.log_writer.log_raw(raw).await
    }

    async fn on_notification(
        &self,
        _peer: &JsonRpcPeer,
        raw: &str,
        notification: JSONRPCNotification,
    ) -> Result<bool, ExecutorError> {
        let method = notification.method.as_str();
        if should_log_notification(method) {
            self.log_writer.log_raw(raw).await?;
        }

        if method == "thread/goal/updated"
            && let Some(params) = notification.params.as_ref()
            && params.get("threadId").and_then(Value::as_str)
                == self.thread_id.lock().await.as_deref()
        {
            self.accept_goal(params.get("goal").cloned().unwrap_or(Value::Null))
                .await?;
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
                && goal.status == "active"
            {
                match progress.checkpoint(args) {
                    Ok(_) => {
                        goals::save(&goal.thread_id, progress).await?;
                        if let Some(reason) = progress.pause_reason.clone() {
                            self.pause_goal(reason, false);
                        }
                    }
                    Err(error) => {
                        self.pause_goal(format!("Invalid goal checkpoint: {error}"), false);
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
        let mut child = command
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .kill_on_drop(true)
            .spawn()
            .unwrap();
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
            child.stdin.take().unwrap(),
            child.stdout.take().unwrap(),
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
            client
                .thread_resume(super::super::resume_params_from(id.clone(), params))
                .await
                .unwrap()
                .thread
                .id
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
            client.reset_goal_run().await.unwrap();
            serde_json::json!({"threadId": id, "status":"active"})
        } else {
            serde_json::json!({"threadId": id, "objective":objective, "status":"active"})
        };
        client
            .goal_request("thread/goal/set", params)
            .await
            .unwrap();
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
            "needs_input" | "stop" => assert_eq!(goal.status, "paused"),
            _ => panic!("unknown scenario"),
        }
        let restored = goals::load(goal).await.unwrap();
        assert_eq!(restored.completed, progress.completed);
        drop(guard);
        cancel.cancel();
        child.kill().await.ok();
    }
}
