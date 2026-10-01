//! VK-controlled leaf turns on the existing app-server connection. No scheduler or retry loop.
use std::{
    collections::{BTreeMap, HashMap},
    path::PathBuf,
    sync::{
        Arc, Mutex as StdMutex,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
};

use codex_app_server_protocol::{DynamicToolSpec, ThreadStartParams};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::Digest;
use tokio::sync::{Mutex, Notify};
use uuid::Uuid;

use super::client::AppServerClient;
use crate::{
    env::ExecutionEnv,
    routing::{RoutingDecision, RoutingMode, RoutingPolicy},
    routing_delegation::{Assignment, ChildChoice},
};

pub const TOOL: &str = "vk_delegate";
pub const INSTRUCTIONS: &str = "AutoSwitch controls delegation through vk_delegate. Native collaboration tools are disabled for this execution. Delegate only independent, substantial work or a useful batch; perform tiny operations yourself. Supply a compact requirements/decisions brief and repository-relative scope paths. Do not copy conversation history. Scope paths are ownership declarations, not permission to ignore repository instructions. Use start, then status to collect results; cancel work that has become obsolete. Do not finish while a child remains active. Use follow_up on the same task for corrections; observable failure can raise its model at that boundary if the operator permits escalation. Do not relaunch duplicates under new task names or invoke another Codex CLI to evade these controls. You own review, integration and final acceptance. Children cannot delegate or own native goals. Do not delegate while a native goal owns this execution.";
static ACTIVE: AtomicUsize = AtomicUsize::new(0);
static ADMISSION: StdMutex<()> = StdMutex::new(());
pub fn active_count() -> usize {
    ACTIVE.load(Ordering::SeqCst)
}
struct Permit;
impl Drop for Permit {
    fn drop(&mut self) {
        ACTIVE.fetch_sub(1, Ordering::SeqCst);
    }
}
fn permit() -> Result<Permit, String> {
    let _guard = ADMISSION
        .lock()
        .map_err(|_| "Delegation admission lock unavailable")?;
    if let Some(error) = super::codex_execution_limit_error() {
        return Err(error.to_string());
    }
    ACTIVE.fetch_add(1, Ordering::SeqCst);
    Ok(Permit)
}

pub fn tool_spec() -> DynamicToolSpec {
    DynamicToolSpec { name: TOOL.into(), defer_loading: false,
        description: "Route an independent delegated leaf task through AutoSwitch. start returns a handle; status waits for up to 30 seconds by default (maximum 60). follow_up preserves its thread/files and may escalate on observed failure. cancel interrupts obsolete work. Tiny or overlapping work belongs in the parent; collect every child before finishing.".into(),
        input_schema: json!({"type":"object","additionalProperties":false,"properties":{
            "action":{"type":"string","enum":["start","status","follow_up","cancel"]},
            "task":{"type":"string"},"message":{"type":"string"},"context":{"type":"string"},
            "paths":{"type":"array","items":{"type":"string"}},"independent":{"type":"boolean"},
            "size":{"type":"string","enum":["tiny","batch","substantial"]},"read_only":{"type":"boolean"},
            "wait_ms":{"type":"integer","minimum":0,"maximum":60000}
        },"required":["action","task"]}) }
}

#[derive(Clone, Serialize, Deserialize)]
struct Record {
    id: String,
    assignment: Assignment,
    fingerprint: String,
    attempt: u32,
    thread: Option<String>,
    turn: Option<String>,
    status: String,
    choice: Option<ChildChoice>,
    effective: Value,
    parent_turn: String,
    execution: String,
    result: String,
    usage: Option<Value>,
    validation_failures: u32,
    #[serde(default)]
    failed_validation_items: Vec<String>,
    cancel_requested: bool,
    #[serde(default)]
    pending_failure: bool,
}
impl Record {
    fn active(&self) -> bool {
        matches!(self.status.as_str(), "starting" | "launching" | "running")
    }
    fn summary(&self) -> Value {
        json!({"task":self.assignment.task,"delegation_id":self.id,"attempt":self.attempt,
        "native_thread_id":self.thread,"native_turn_id":self.turn,"status":self.status,
        "recommended":self.choice,"effective":self.effective,"result":self.result,"usage":self.usage,
        "validation_failures":self.validation_failures,"cancel_requested":self.cancel_requested})
    }
}
struct State {
    records: BTreeMap<String, Record>,
    permits: HashMap<String, Permit>,
}

pub struct Delegation {
    policy: RoutingPolicy,
    parent: RoutingDecision,
    pub root_thread: String,
    root: PathBuf,
    params: ThreadStartParams,
    env: ExecutionEnv,
    path: PathBuf,
    max_children: usize,
    state: Mutex<State>,
    changed: Notify,
    closing: AtomicBool,
}
impl Delegation {
    pub async fn new(
        policy: RoutingPolicy,
        parent: RoutingDecision,
        root_thread: String,
        mut params: ThreadStartParams,
        env: ExecutionEnv,
        inherited: Value,
        max_children: usize,
    ) -> Result<Arc<Self>, String> {
        let root = PathBuf::from(
            params
                .cwd
                .as_deref()
                .ok_or("Delegation needs a working directory")?,
        )
        .canonicalize()
        .map_err(|e| e.to_string())?;
        let availability = crate::routing::load_availability()?;
        let dir = PathBuf::from(
            std::env::var("VK_CODEX_ROUTING_AVAILABILITY").map_err(|e| e.to_string())?,
        )
        .parent()
        .ok_or("Availability needs a parent path")?
        .join("delegation");
        tokio::fs::create_dir_all(&dir)
            .await
            .map_err(|e| e.to_string())?;
        // Native UUID is validated before it becomes a filename.
        Uuid::parse_str(&root_thread).map_err(|_| "Unexpected native thread identifier")?;
        let path = dir.join(format!("{root_thread}.json"));
        let mut records: BTreeMap<String, Record> = match tokio::fs::read(&path).await {
            Ok(bytes) if bytes.len() <= 2 * 1024 * 1024 => serde_json::from_slice(&bytes)
                .map_err(|_| "Delegation journal is invalid; inspect it before delegating")?,
            Ok(_) => {
                return Err(
                    "Delegation journal exceeds its bound; inspect before delegating".into(),
                );
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => BTreeMap::new(),
            Err(e) => return Err(e.to_string()),
        };
        for record in records.values_mut() {
            if record.active() {
                record.status = "interrupted_unconfirmed".into();
            }
        }
        params.model = inherited["model"].as_str().map(str::to_owned);
        let config = params.config.get_or_insert_default();
        config.insert(
            "model_reasoning_effort".into(),
            inherited["reasoningEffort"].clone(),
        );
        config.insert("features.multi_agent".into(), json!(false));
        config.insert("features.multi_agent_v2".into(), json!(false));
        config.insert("features.goals".into(), json!(false));
        params.dynamic_tools = Some(vec![]);
        params.developer_instructions = Some(format!(
            "{}\n\nYou are a delegated leaf. Follow the supplied assignment and repository instructions. Never create goals or delegate. Stop and report discovered risk/scope changes. Preserve existing uncommitted work.",
            params
                .developer_instructions
                .as_deref()
                .unwrap_or_default()
                .replace(INSTRUCTIONS, "")
                .replace(super::goals::INSTRUCTIONS, "")
        ));
        // Keep the same home/account proof; the root already verified its account.
        if inherited["accountFingerprint"].as_str()
            != Some(availability.account_fingerprint.as_str())
            || parent
                .account_fingerprint
                .as_deref()
                .is_some_and(|p| p != availability.account_fingerprint)
        {
            return Err("Delegation account proof differs from parent routing".into());
        }
        Ok(Arc::new(Self {
            policy,
            parent,
            root_thread,
            root,
            params,
            env,
            path,
            max_children,
            state: Mutex::new(State {
                records,
                permits: HashMap::new(),
            }),
            changed: Notify::new(),
            closing: AtomicBool::new(false),
        }))
    }
    async fn save(&self, state: &State) -> Result<(), String> {
        let bytes = serde_json::to_vec(&state.records).map_err(|e| e.to_string())?;
        if bytes.len() > 2 * 1024 * 1024 {
            return Err("Delegation journal full; collect work before adding tasks".into());
        }
        let temporary = self.path.with_extension("json.tmp");
        use tokio::io::AsyncWriteExt;
        let mut options = tokio::fs::OpenOptions::new();
        options.create(true).truncate(true).write(true);
        #[cfg(unix)]
        options.mode(0o600);
        let mut file = options.open(&temporary).await.map_err(|e| e.to_string())?;
        file.write_all(&bytes).await.map_err(|e| e.to_string())?;
        file.sync_data().await.map_err(|e| e.to_string())?;
        drop(file);
        tokio::fs::rename(temporary, &self.path)
            .await
            .map_err(|e| e.to_string())
    }
    async fn event(&self, client: &AppServerClient, kind: &str, r: &Record, data: Value) {
        let event = json!({"schema":"vk.delegation.v1","eventId":format!("{}:{}:{}:{}:{:x}",r.execution,r.id,r.attempt,kind,sha2::Sha256::digest(data.to_string())),
            "timestamp":chrono::Utc::now().to_rfc3339(),"kind":kind,"executionId":r.execution,"routingId":self.parent.id,
            "delegationId":r.id,"attempt":r.attempt,"taskKey":r.assignment.task,"parentNativeThreadId":self.root_thread,
            "parentNativeTurnId":r.parent_turn,"nativeThreadId":r.thread,"nativeTurnId":r.turn,
            "mode":self.policy.mode,"data":data});
        if let Err(error) = client
            .log_writer()
            .log_raw(&json!({"method":"vk/delegation","params":event}).to_string())
            .await
        {
            tracing::warn!(%error,"Delegation log delivery failed");
        }
        if let Ok(path) = std::env::var("VK_ROUTING_EVENTS_FILE") {
            let path = PathBuf::from(path).with_extension("delegation.jsonl");
            let result = tokio::task::spawn_blocking(move || {
                crate::routing_telemetry::append_once(&path, &event)
            })
            .await;
            if !matches!(result, Ok(Ok(()))) {
                tracing::warn!(?result, "Delegation telemetry delivery failed");
            }
        }
    }
    pub async fn handle(
        self: &Arc<Self>,
        client: Arc<AppServerClient>,
        parent_turn: String,
        args: Value,
    ) -> Result<Value, String> {
        let action = args["action"].as_str().ok_or("Missing delegation action")?;
        let task = args["task"].as_str().ok_or("Missing task key")?.to_owned();
        match action {
            "status" => {
                let wait = args["wait_ms"].as_u64().unwrap_or(30000).min(60000);
                let _ = tokio::time::timeout(std::time::Duration::from_millis(wait), async {
                    loop {
                        let changed = self.changed.notified();
                        tokio::pin!(changed);
                        changed.as_mut().enable();
                        if !self
                            .state
                            .lock()
                            .await
                            .records
                            .get(&task)
                            .ok_or("Unknown task")?
                            .active()
                        {
                            return Ok::<(), String>(());
                        }
                        changed.await;
                    }
                })
                .await;
                Ok(self
                    .state
                    .lock()
                    .await
                    .records
                    .get(&task)
                    .ok_or("Unknown task")?
                    .summary())
            }
            "cancel" => self.cancel(&client, &task).await,
            "start" | "follow_up" => {
                let mut assignment = args.clone();
                assignment
                    .as_object_mut()
                    .ok_or("Invalid assignment")?
                    .remove("action");
                assignment.as_object_mut().unwrap().remove("wait_ms");
                let assignment: Assignment =
                    serde_json::from_value(assignment).map_err(|e| e.to_string())?;
                self.start(&client, parent_turn, assignment, action == "follow_up")
                    .await
            }
            _ => Err("Unknown delegation action".into()),
        }
    }
    async fn start(
        &self,
        client: &AppServerClient,
        parent_turn: String,
        assignment: Assignment,
        follow_up: bool,
    ) -> Result<Value, String> {
        if self.closing.load(Ordering::SeqCst) {
            return Err("Parent execution is ending".into());
        }
        if !client.delegation_turn_current(&parent_turn).await {
            return Err("Parent turn is no longer eligible for delegation".into());
        }
        assignment.validate(&self.root)?;
        let task = assignment.task.clone();
        let fingerprint = assignment.fingerprint();
        let execution = self
            .env
            .get("VK_EXECUTION_PROCESS_ID")
            .ok_or("Delegation needs persisted VK execution identity")?
            .clone();
        let (previous, failed, reuse) = {
            let mut state = self.state.lock().await;
            if !follow_up
                && let Some(r) = state
                    .records
                    .values()
                    .find(|r| r.fingerprint == fingerprint)
            {
                return Ok(json!({"reused":true,"existing":r.summary()}));
            }
            if state.permits.len() >= self.max_children {
                return Err(
                    "Delegation capacity reached; collect an existing child or work in the parent"
                        .into(),
                );
            }
            if state.records.values().any(|r| {
                r.active()
                    && r.assignment.task != task
                    && assignment.overlaps(&r.assignment)
                    && (!r.assignment.read_only || !assignment.read_only)
            }) {
                return Err(
                    "Concurrent editing scopes overlap; serialize or divide ownership".into(),
                );
            }
            let previous = state.records.get(&task).cloned();
            if follow_up != previous.is_some() {
                return Err("Use start for a new task and follow_up for an existing task".into());
            }
            if previous.as_ref().is_some_and(Record::active) {
                return Err(
                    "Child is still active; collect or cancel it before a follow-up".into(),
                );
            }
            let same = previous
                .as_ref()
                .is_some_and(|p| p.fingerprint == fingerprint);
            let failed = previous.as_ref().is_some_and(|p| {
                p.pending_failure || p.status == "failed" || p.validation_failures >= 2
            });
            let permit = tokio::task::spawn_blocking(permit)
                .await
                .map_err(|e| e.to_string())??;
            let record = Record {
                id: previous
                    .as_ref()
                    .map_or_else(|| Uuid::new_v4().to_string(), |p| p.id.clone()),
                assignment: assignment.clone(),
                fingerprint,
                attempt: previous.as_ref().map_or(1, |p| p.attempt + 1),
                thread: previous.as_ref().and_then(|p| p.thread.clone()),
                turn: None,
                status: "starting".into(),
                choice: previous.as_ref().and_then(|p| p.choice.clone()),
                effective: Value::Null,
                parent_turn,
                execution,
                result: String::new(),
                usage: None,
                validation_failures: 0,
                failed_validation_items: vec![],
                cancel_requested: false,
                pending_failure: failed,
            };
            state.records.insert(task.clone(), record);
            if let Err(error) = self.save(&state).await {
                state.records.remove(&task);
                if let Some(p) = previous.clone() {
                    state.records.insert(task.clone(), p);
                }
                return Err(error);
            }
            state.permits.insert(task.clone(), permit);
            (previous, failed, same)
        };
        let result = self
            .launch(client, &assignment, previous.as_ref(), failed, reuse)
            .await;
        if let Err(error) = &result {
            let uncertain = self
                .state
                .lock()
                .await
                .records
                .get(&task)
                .is_some_and(|r| matches!(r.status.as_str(), "launching" | "running"));
            if uncertain {
                self.close();
                client.abort_delegation_execution(error).await;
                return result;
            }
            let record = {
                let mut state = self.state.lock().await;
                let r = state.records.get_mut(&task).unwrap();
                r.status = "blocked".into();
                r.result = error.clone();
                let blocked = r.clone();
                // A refused escalation must not erase failure evidence or turn into a cheap retry.
                if failed {
                    r.choice = previous.as_ref().and_then(|p| p.choice.clone());
                }
                state.permits.remove(&task);
                if let Err(error) = self.save(&state).await {
                    self.close();
                    tracing::warn!(%error,"Delegation journal unavailable; further child admission closed");
                }
                blocked
            };
            self.event(
                client,
                "blocked",
                &record,
                json!({"reason":error,"recommendation":record.choice}),
            )
            .await;
        }
        result
    }
    async fn launch(
        &self,
        client: &AppServerClient,
        assignment: &Assignment,
        previous: Option<&Record>,
        failed: bool,
        reuse: bool,
    ) -> Result<Value, String> {
        let mut assessed = assignment.clone();
        if reuse && previous.and_then(|p| p.choice.as_ref()).is_some() && !failed {
            assessed.message = "continue".into();
            assessed.context.clear();
        }
        let root = self.root.clone();
        let policy = self.policy.clone();
        let parent = self.parent.clone();
        let prior = previous.and_then(|p| p.choice.clone());
        let choice = tokio::task::spawn_blocking(move || {
            crate::routing_delegation::choose(
                &assessed,
                &root,
                &policy,
                &parent,
                prior.as_ref(),
                failed,
                !reuse,
            )
        })
        .await
        .map_err(|e| e.to_string())??;
        {
            let mut state = self.state.lock().await;
            state.records.get_mut(&assignment.task).unwrap().choice = Some(choice.clone());
            self.save(&state).await?;
        }
        self.launch_choice(client, assignment, previous, choice)
            .await
    }

    /// Transport boundary isolated from assessment, also used by the offline protocol fixture.
    async fn launch_choice(
        &self,
        client: &AppServerClient,
        assignment: &Assignment,
        previous: Option<&Record>,
        choice: ChildChoice,
    ) -> Result<Value, String> {
        let mut params = self.params.clone();
        let (model, effort) = if self.policy.mode == RoutingMode::Auto {
            (choice.model.clone(), choice.effort.clone())
        } else {
            let model = params
                .model
                .clone()
                .ok_or("Shadow child requires resolved parent model")?;
            let effort = params
                .config
                .as_ref()
                .and_then(|c| c.get("model_reasoning_effort"))
                .and_then(Value::as_str)
                .ok_or("Shadow child requires resolved parent effort")?
                .to_owned();
            if !crate::routing_delegation::actual_pair_qualified(
                &choice,
                &model,
                &effort,
                &self.policy,
            )? {
                return Err("Shadow recommendation exceeds inherited child qualification; do this work in the parent or change the explicit policy".into());
            }
            (model, effort)
        };
        params.model = Some(model.clone());
        params.service_tier = Some(None);
        params
            .config
            .get_or_insert_default()
            .insert("model_reasoning_effort".into(), json!(effort));
        if assignment.read_only {
            params.sandbox = Some(codex_app_server_protocol::SandboxMode::ReadOnly);
        }
        let task = &assignment.task;
        {
            let mut state = self.state.lock().await;
            let r = state.records.get_mut(task).unwrap();
            if r.cancel_requested || self.closing.load(Ordering::SeqCst) {
                return Err("Delegation cancelled before inference".into());
            }
            r.choice = Some(choice.clone());
            self.save(&state).await?;
        }
        let parent_turn = self
            .state
            .lock()
            .await
            .records
            .get(task)
            .unwrap()
            .parent_turn
            .clone();
        if !client.delegation_turn_current(&parent_turn).await {
            return Err("Parent turn ended during classification".into());
        }
        let mut wire = serde_json::to_value(params).map_err(|e| e.to_string())?;
        let thread = if let Some(id) = previous.and_then(|p| p.thread.as_ref()) {
            wire.as_object_mut().unwrap().remove("dynamicTools");
            wire["threadId"] = json!(id);
            client
                .delegation_request("thread/resume", wire)
                .await
                .map_err(|e| e.to_string())?
        } else {
            client
                .delegation_request("thread/start", wire)
                .await
                .map_err(|e| e.to_string())?
        };
        if thread["model"] != model
            || thread["reasoningEffort"] != effort
            || thread["modelProvider"] != "openai"
            || !thread["serviceTier"].is_null()
        {
            return Err("Native child settings differ from admitted model/effort/standard tier; stopped before inference".into());
        }
        let native = thread["thread"]["id"]
            .as_str()
            .ok_or("Missing native child thread ID")?
            .to_owned();
        if native == self.root_thread
            || Uuid::parse_str(&native).is_err()
            || previous
                .and_then(|r| r.thread.as_deref())
                .is_some_and(|old| old != native)
        {
            return Err("Native child identity changed; stopped before inference".into());
        }
        let record = {
            let mut state = self.state.lock().await;
            let r = state.records.get_mut(task).unwrap();
            r.thread = Some(native.clone());
            r.effective = json!({"model":model,"reasoningEffort":effort,"serviceTier":null});
            if r.cancel_requested || self.closing.load(Ordering::SeqCst) {
                return Err("Delegation cancelled before inference".into());
            }
            let r = r.clone();
            self.save(&state).await?;
            r
        };
        self.event(client,"decision",&record,json!({"selected":{"model":choice.model,"reasoningEffort":choice.effort,"serviceTier":"standard"},"effective":record.effective,
            "envelope":choice.envelope,"floor":choice.floor,"classificationSource":choice.source,"classifierId":choice.semantic.as_ref().map(|s|&s.id),"semanticStatus":choice.semantic.as_ref().map(|s|&s.status),"semanticClassification":choice.semantic.as_ref().and_then(|s|s.classification.as_ref()),"escalated":choice.escalated,
            "contextMode":"brief_no_parent_history","contextBytes":assignment.brief(crate::routing_delegation::hard_floor(&self.policy,&self.parent)).len(),"assignmentHash":record.fingerprint})).await;
        if !client.delegation_turn_current(&parent_turn).await {
            return Err("Parent turn ended before child inference".into());
        }
        {
            let mut state = self.state.lock().await;
            if self.closing.load(Ordering::SeqCst) {
                return Err("Parent execution is ending".into());
            }
            state.records.get_mut(task).unwrap().status = "launching".into();
            self.save(&state).await?;
        }
        let turn=client.delegation_request("turn/start",json!({"threadId":native,"model":model,"effort":effort,"serviceTier":null,"input":[{"type":"text","text":assignment.brief(crate::routing_delegation::hard_floor(&self.policy,&self.parent)),"text_elements":[]}]})).await.map_err(|e|e.to_string())?;
        let turn_id = turn["turn"]["id"]
            .as_str()
            .ok_or("Missing native child turn ID")?
            .to_owned();
        // A turn/started notification may already have bound this exact pair.
        self.bind(client, task, &turn_id).await?;
        let cancelled = self
            .state
            .lock()
            .await
            .records
            .get(task)
            .unwrap()
            .cancel_requested;
        if cancelled {
            self.cancel(client, task).await?;
        }
        Ok(self.state.lock().await.records.get(task).unwrap().summary())
    }
    async fn bind(&self, client: &AppServerClient, task: &str, turn: &str) -> Result<(), String> {
        let record = {
            let mut state = self.state.lock().await;
            let r = state.records.get_mut(task).ok_or("Unknown child")?;
            if r.turn.as_deref() == Some(turn) {
                return Ok(());
            }
            if r.turn.is_some() {
                return Err("Unexpected child turn transition".into());
            }
            r.turn = Some(turn.into());
            r.status = "running".into();
            r.pending_failure = false;
            let r = r.clone();
            self.save(&state).await?;
            r
        };
        if let Some(binding) = crate::routing_telemetry::NativeBinding::new(
            &self.env,
            Some(&self.parent),
            record.effective.clone(),
        ) {
            binding.turn(record.thread.as_deref().unwrap(), turn).await;
        }
        self.event(
            client,
            "turn_bound",
            &record,
            json!({"effective":record.effective,"settingsSource":"runtime_confirmed"}),
        )
        .await;
        Ok(())
    }
    pub async fn observe(
        &self,
        client: &AppServerClient,
        method: &str,
        params: &Value,
        raw: &str,
    ) -> Result<bool, String> {
        let thread = params["threadId"]
            .as_str()
            .or_else(|| params["thread"]["id"].as_str())
            .or_else(|| params["conversationId"].as_str())
            .or_else(|| params["msg"]["session_id"].as_str());
        let Some(thread) = thread.filter(|t| *t != self.root_thread) else {
            return Ok(false);
        };
        // Keep child lifecycle/raw items out of the root session-ID and goal normalizers.
        if let Err(error)=client.log_writer().log_raw(&json!({"method":"vk/delegation/native","params":{"notification":serde_json::from_str::<Value>(raw).ok()}}).to_string()).await {tracing::warn!(%error,"Child raw-log delivery failed");}
        let task = self
            .state
            .lock()
            .await
            .records
            .iter()
            .find(|(_, r)| r.thread.as_deref() == Some(thread))
            .map(|(k, _)| k.clone());
        let Some(task) = task else {
            return Ok(true);
        };
        if method == "turn/started" {
            if let Some(turn) = params["turn"]["id"].as_str() {
                self.bind(client, &task, turn).await?;
            }
            return Ok(true);
        }
        let record = {
            let mut state = self.state.lock().await;
            let r = state.records.get_mut(&task).unwrap();
            let turn = params["turnId"]
                .as_str()
                .or_else(|| params["turn"]["id"].as_str());
            if method != "model/rerouted" && (turn.is_none() || r.turn.as_deref() != turn) {
                // Never attach an unbound usage/item event to the most recent turn by timing.
                return Ok(true);
            }
            match method {
                "item/completed" if params["item"]["type"] == "agentMessage" => {
                    r.result = params["item"]["text"]
                        .as_str()
                        .unwrap_or("")
                        .chars()
                        .take(16000)
                        .collect()
                }
                "item/completed" if params["item"]["type"] == "commandExecution" => {
                    if params["item"]["exitCode"].as_i64().is_some_and(|n| n != 0)
                        && validation_command(params["item"]["command"].as_str().unwrap_or(""))
                        && let Some(id) = params["item"]["id"].as_str()
                        && r.validation_failures < 2
                        && !r.failed_validation_items.iter().any(|old| old == id)
                    {
                        r.failed_validation_items.push(id.into());
                        r.validation_failures += 1;
                    }
                }
                "thread/tokenUsage/updated" => r.usage = Some(params["tokenUsage"]["last"].clone()),
                "turn/completed" => {
                    if !matches!(
                        params["turn"]["status"].as_str(),
                        Some("completed" | "failed" | "interrupted")
                    ) {
                        return Err(
                            "Unknown child terminal status; stop the owner for reconciliation"
                                .into(),
                        );
                    }
                    r.status = params["turn"]["status"]
                        .as_str()
                        .unwrap_or("unknown")
                        .into();
                }
                "model/rerouted" => {
                    return Err(
                        "Native child model changed after admission; stop the owning execution"
                            .into(),
                    );
                }
                _ => return Ok(true),
            }
            let r = r.clone();
            if !r.active() {
                state.permits.remove(&task);
            }
            self.save(&state).await?;
            r
        };
        if method == "thread/tokenUsage/updated" {
            self.event(
                client,
                "usage",
                &record,
                json!({"nativeUsage":record.usage}),
            )
            .await;
        }
        if method == "turn/completed" {
            self.event(client,"attempt_end",&record,json!({"outcome":record.status,"validationFailures":record.validation_failures,"nativeUsage":record.usage})).await;
        }
        self.changed.notify_waiters();
        Ok(true)
    }
    pub async fn cancel(&self, client: &AppServerClient, task: &str) -> Result<Value, String> {
        let record = {
            let mut state = self.state.lock().await;
            let r = state.records.get_mut(task).ok_or("Unknown child")?;
            if !r.active() {
                return Ok(r.summary());
            }
            r.cancel_requested = true;
            let r = r.clone();
            self.save(&state).await?;
            r
        };
        self.event(
            client,
            "cancel_requested",
            &record,
            json!({"reason":"obsolete_or_parent_ended"}),
        )
        .await;
        if let (Some(thread), Some(turn)) = (&record.thread, &record.turn) {
            client
                .delegation_request("turn/interrupt", json!({"threadId":thread,"turnId":turn}))
                .await
                .map_err(|e| e.to_string())?;
        }
        Ok(record.summary())
    }
    pub async fn active(&self) -> bool {
        self.state.lock().await.records.values().any(Record::active)
    }
    pub fn close(&self) {
        self.closing.store(true, Ordering::SeqCst);
    }
    pub async fn cancel_all(&self, client: &AppServerClient) {
        self.close();
        let tasks: Vec<_> = self
            .state
            .lock()
            .await
            .records
            .iter()
            .filter(|(_, r)| r.active())
            .map(|(k, _)| k.clone())
            .collect();
        for task in tasks {
            if let Err(error) = self.cancel(client, &task).await {
                tracing::warn!(%error,"Child interrupt not confirmed; executor shutdown remains authoritative");
            }
        }
    }
}
fn validation_command(command: &str) -> bool {
    if command.contains([';', '|', '&', '$', '`', '\n']) {
        return false;
    }
    [
        "cargo test",
        "cargo check",
        "pnpm test",
        "pnpm run check",
        "npm test",
        "pytest",
        "node --test",
        "tsc --noEmit",
    ]
    .iter()
    .any(|s| {
        command
            .trim()
            .strip_prefix(s)
            .is_some_and(|rest| rest.is_empty() || rest.starts_with(char::is_whitespace))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn delegation_validation_evidence_is_not_arbitrary_output_text() {
        for command in [
            "cargo test router",
            "node --test regression.js",
            "pnpm run check",
        ] {
            assert!(validation_command(command));
        }
        for command in [
            "echo cargo test",
            "cat test-output.txt",
            "pytest_fake",
            "npm testing",
            "cargo test && false",
        ] {
            assert!(!validation_command(command));
        }
    }
    #[tokio::test]
    async fn delegation_cancel_dispatch_keeps_reader_and_parent_alive() {
        use codex_app_server_protocol::{JSONRPCNotification, JSONRPCRequest};
        use tokio_util::sync::CancellationToken;

        use super::super::{
            client::LogWriter,
            jsonrpc::{ExitSignalSender, JsonRpcCallbacks, JsonRpcPeer},
        };
        use crate::env::RepoContext;
        let dir = std::env::temp_dir().join(format!("vk-delegation-test-{}", Uuid::new_v4()));
        std::fs::create_dir(&dir).unwrap();
        let mut process=tokio::process::Command::new("python3").args(["-u","-c",r#"
import sys,json
for line in sys.stdin:
    d=json.loads(line)
    if d.get('method') in ('thread/start','thread/resume'):
        p=d['params']
        assert p['model']=='gpt-5.6-luna' and p['config']['model_reasoning_effort']=='low'
        assert p['config']['features.multi_agent'] is False and p['config']['features.multi_agent_v2'] is False
        assert 'PARENT_PRIVATE_HISTORY' not in json.dumps(p)
        print(json.dumps({'id':d['id'],'result':{'thread':{'id':'11111111-1111-4111-8111-111111111111'},'model':p['model'],'reasoningEffort':p['config']['model_reasoning_effort'],'modelProvider':'openai','serviceTier':None}}),flush=True)
    elif d.get('method')=='turn/start':
        p=d['params']; assert p['model']=='gpt-5.6-luna' and p['effort']=='low'
        assert 'Delegated assignment:' in p['input'][0]['text']
        print(json.dumps({'id':d['id'],'result':{'turn':{'id':'native-fixture-turn'}}}),flush=True)
        print(json.dumps({'method':'turn/started','params':{'threadId':p['threadId'],'turn':{'id':'native-fixture-turn','status':'inProgress'}}}),flush=True)
        print(json.dumps({'method':'thread/tokenUsage/updated','params':{'threadId':p['threadId'],'turnId':'native-fixture-turn','tokenUsage':{'last':{'inputTokens':42,'cachedInputTokens':11,'outputTokens':7,'reasoningOutputTokens':2}}}}),flush=True)
        print(json.dumps({'method':'turn/completed','params':{'threadId':p['threadId'],'turn':{'id':'native-fixture-turn','status':'completed'}}}),flush=True)
    elif d.get('method')=='turn/interrupt':
        print(json.dumps({'id':d['id'],'result':{}}),flush=True)
        print(json.dumps({'method':'turn/completed','params':{'threadId':'child','turn':{'id':'child-turn','status':'interrupted'}}}),flush=True)
"#]).stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).kill_on_drop(true).spawn().unwrap();
        let cancel = CancellationToken::new();
        let (tx, mut rx) = tokio::sync::oneshot::channel();
        let signal = ExitSignalSender::new(tx);
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
        let peer = JsonRpcPeer::spawn(
            process.stdin.take().unwrap(),
            process.stdout.take().unwrap(),
            client.clone(),
            signal.clone(),
            cancel.clone(),
        );
        client.connect(peer.clone());
        client.set_exit_signal(signal);
        client.register_session("root").await.unwrap();
        client.on_notification(&peer,"{}",JSONRPCNotification{method:"turn/started".into(),params:Some(json!({"threadId":"root","turn":{"id":"parent-turn","status":"inProgress","items":[],"error":null}}))}).await.unwrap();
        let assignment = Assignment {
            task: "child".into(),
            message: "Fix spelling typos in README.md".into(),
            context: String::new(),
            paths: vec!["README.md".into()],
            independent: true,
            size: "batch".into(),
            read_only: true,
        };
        let record = Record {
            id: Uuid::new_v4().to_string(),
            fingerprint: assignment.fingerprint(),
            assignment,
            attempt: 1,
            thread: Some("child".into()),
            turn: Some("child-turn".into()),
            status: "running".into(),
            choice: None,
            effective: json!({"model":"gpt-5.6-luna","reasoningEffort":"low"}),
            parent_turn: "parent-turn".into(),
            execution: Uuid::new_v4().to_string(),
            result: String::new(),
            usage: None,
            validation_failures: 0,
            failed_validation_items: vec![],
            cancel_requested: false,
            pending_failure: false,
        };
        let policy = serde_json::from_value(json!({"mode":"auto","floor":"assessed"})).unwrap();
        let parent=serde_json::from_value(json!({"version":2,"id":"root-route","mode":"auto","floor":"workhorse","reason":"test","service_tier":"standard","escalated":false})).unwrap();
        let control = Arc::new(Delegation {
            policy,
            parent,
            root_thread: "root".into(),
            root: dir.clone(),
            params: ThreadStartParams {
                config: Some(HashMap::from([
                    ("features.multi_agent".into(), json!(false)),
                    ("features.multi_agent_v2".into(), json!(false)),
                ])),
                ..Default::default()
            },
            env: ExecutionEnv::new(RepoContext::default(), false, String::new()),
            path: dir.join("journal.json"),
            max_children: 1,
            state: Mutex::new(State {
                records: BTreeMap::from([("child".into(), record)]),
                permits: HashMap::new(),
            }),
            changed: Notify::new(),
            closing: AtomicBool::new(false),
        });
        client.set_delegation(control.clone());
        let request = JSONRPCRequest {
            trace: None,
            id: codex_app_server_protocol::RequestId::String("dynamic-call".into()),
            method: "item/tool/call".into(),
            params: Some(
                json!({"threadId":"root","turnId":"parent-turn","callId":"call","tool":TOOL,"arguments":{"action":"cancel","task":"child"}}),
            ),
        };
        tokio::time::timeout(
            std::time::Duration::from_secs(1),
            client.on_request(&peer, &serde_json::to_string(&request).unwrap(), request),
        )
        .await
        .unwrap()
        .unwrap();
        tokio::time::timeout(std::time::Duration::from_secs(3), async {
            while control.active().await {
                tokio::time::sleep(std::time::Duration::from_millis(10)).await;
            }
        })
        .await
        .unwrap();
        assert_eq!(
            control.state.lock().await.records["child"].status,
            "interrupted"
        );
        assert!(client.delegation_turn_current("parent-turn").await);
        assert!(
            rx.try_recv().is_err(),
            "A child completion cannot end the owner"
        );
        // Child native responses are tracked separately from root session responses.
        let response = client
            .delegation_request(
                "turn/interrupt",
                json!({"threadId":"child","turnId":"child-turn"}),
            )
            .await
            .unwrap();
        assert_eq!(response, json!({}));
        let assignment = {
            let mut state = control.state.lock().await;
            let r = state.records.get_mut("child").unwrap();
            r.turn = None;
            r.thread = None;
            r.status = "starting".into();
            r.cancel_requested = false;
            r.assignment.clone()
        };
        let choice = ChildChoice {
            envelope: "mechanical".into(),
            floor: crate::routing::CapabilityFloor::Routine,
            model: "gpt-5.6-luna".into(),
            effort: "low".into(),
            source: "fixture".into(),
            semantic: None,
            escalated: false,
        };
        let bound = control
            .launch_choice(&client, &assignment, None, choice)
            .await
            .unwrap();
        assert_eq!(bound["effective"]["model"], "gpt-5.6-luna");
        assert_eq!(
            bound["native_thread_id"],
            "11111111-1111-4111-8111-111111111111"
        );
        tokio::time::timeout(std::time::Duration::from_secs(3), async {
            while control.active().await {
                tokio::time::sleep(std::time::Duration::from_millis(10)).await;
            }
        })
        .await
        .unwrap();
        let record = control.state.lock().await.records["child"].clone();
        assert_eq!(record.status, "completed");
        assert_eq!(record.usage.unwrap()["cachedInputTokens"], 11);
        assert!(client.delegation_turn_current("parent-turn").await);
        control.close();
        assert!(
            control
                .start(
                    &client,
                    "parent-turn".into(),
                    control.state.lock().await.records["child"]
                        .assignment
                        .clone(),
                    true
                )
                .await
                .is_err()
        );
        cancel.cancel();
        process.kill().await.unwrap();
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
