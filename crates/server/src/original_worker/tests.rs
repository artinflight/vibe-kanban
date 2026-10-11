//! Production Live + follow_up + ContainerService admission; only OS/native
//! processes and resource observations are replaced by synthetic adapters.
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    process::Stdio,
    sync::{OnceLock, atomic::AtomicUsize},
};

use db::{
    DBService,
    models::{
        coding_agent_turn::{CodingAgentTurn, CreateCodingAgentTurn},
        execution_process::{
            CreateExecutionProcess, ExecutionContext, ExecutionProcessRunReason,
            ExecutionProcessStatus,
        },
        repo::Repo,
        scratch::DraftFollowUpData,
        session::CreateSession,
        workspace::CreateWorkspace,
        workspace_repo::{CreateWorkspaceRepo, WorkspaceRepo},
    },
};
use executors::{
    actions::{ExecutorActionType, coding_agent_follow_up::CodingAgentFollowUpRequest},
    env::RepoContext,
    executors::codex::{
        client::{AppServerClient, LogWriter},
        jsonrpc::{ExitSignalSender, JsonRpcPeer},
    },
    original_worker::{LaunchGuard, TOOL},
    profile::ExecutorConfig,
};
use serde_json::json;
use services::services::{
    admission,
    config::Config,
    container::{ContainerError, ContainerRef, ContainerService},
    events::EventService,
    notification::NotificationService,
    queued_message::QueuedMessageService,
};
use tokio::{
    process::{Child, Command},
    sync::RwLock,
    task::JoinHandle,
};
use tokio_util::sync::CancellationToken;
use utils::{log_msg::LogMsg, msg_store::MsgStore};

use super::*;

#[derive(Clone)]
struct FixtureDeployment {
    container: Arc<FixtureContainer>,
    config: Arc<RwLock<Config>>,
    events: EventService,
    queue: QueuedMessageService,
    monitor: Arc<FixtureMonitor>,
}

#[derive(Default)]
struct FixtureMonitor {
    enabled: AtomicBool,
    handle: Mutex<Option<JoinHandle<()>>>,
}

macro_rules! unused_getter {
    ($name:ident, $ty:ty) => {
        fn $name(&self) -> &$ty {
            panic!(concat!(stringify!($name), " outside fixture boundary"))
        }
    };
}
#[executors::original_worker::async_trait]
impl Deployment for FixtureDeployment {
    async fn new(_: CancellationToken) -> Result<Self, deployment::DeploymentError> {
        panic!("No service startup in fixture")
    }
    async fn start_background_services(&self) -> Result<(), deployment::DeploymentError> {
        if self.monitor.enabled.load(Ordering::SeqCst) {
            let task = services::services::pr_monitor::PrMonitorService::spawn(
                self.container.db.clone(),
                None,
                self.container.as_ref().clone(),
                None,
                Arc::new(tokio::sync::Notify::new()),
            )
            .await;
            *self.monitor.handle.lock().await = Some(task);
        }
        Ok(())
    }
    fn user_id(&self) -> &str {
        "synthetic"
    }
    fn db(&self) -> &DBService {
        &self.container.db
    }
    fn config(&self) -> &Arc<RwLock<Config>> {
        &self.config
    }
    fn analytics(&self) -> &Option<services::services::analytics::AnalyticsService> {
        static NONE: Option<services::services::analytics::AnalyticsService> = None;
        &NONE
    }
    fn container(&self) -> &impl ContainerService {
        self.container.as_ref()
    }
    fn git(&self) -> &git::GitService {
        &self.container.git
    }
    fn events(&self) -> &EventService {
        &self.events
    }
    fn queued_message_service(&self) -> &QueuedMessageService {
        &self.queue
    }
    unused_getter!(repo, services::services::repo::RepoService);
    unused_getter!(file, services::services::file::FileService);
    unused_getter!(
        filesystem,
        services::services::filesystem::FilesystemService
    );
    unused_getter!(
        file_search_cache,
        Arc<services::services::file_search::FileSearchCache>
    );
    unused_getter!(approvals, services::services::approvals::Approvals);
    unused_getter!(auth_context, services::services::auth::AuthContext);
    unused_getter!(relay_control, Arc<relay_control::RelayControl>);
    unused_getter!(relay_signing, relay_control::signing::RelaySigningService);
    unused_getter!(client_info, client_info::ClientInfo);
    unused_getter!(remote_info, remote_info::RemoteInfo);
    unused_getter!(preview_proxy, preview_proxy::PreviewProxyService);
    unused_getter!(
        trusted_key_auth,
        trusted_key_auth::runtime::TrustedKeyAuthRuntime
    );
}

#[derive(Clone)]
struct FixtureContainer {
    db: DBService,
    git: git::GitService,
    stores: Arc<RwLock<HashMap<Uuid, Arc<MsgStore>>>>,
    provider: Arc<OnceLock<Arc<Provider<FixtureDeployment>>>>,
    launches: Arc<AtomicUsize>,
    worker_goal: Arc<AtomicBool>,
    peers: Arc<Mutex<Vec<NativePeer>>>,
    scripts: Arc<AtomicUsize>,
    script_done: Arc<tokio::sync::Notify>,
}

#[executors::original_worker::async_trait]
impl ContainerService for FixtureContainer {
    fn db(&self) -> &DBService {
        &self.db
    }
    fn git(&self) -> &git::GitService {
        &self.git
    }
    fn msg_stores(&self) -> &Arc<RwLock<HashMap<Uuid, Arc<MsgStore>>>> {
        &self.stores
    }
    fn notification_service(&self) -> &NotificationService {
        panic!("No notifications in fixture")
    }
    fn status_worktree_cleanup_enabled(&self) -> bool {
        false
    }
    fn workspace_to_current_dir(&self, w: &Workspace) -> PathBuf {
        w.container_ref.as_ref().unwrap().into()
    }
    async fn touch(&self, _: &Workspace) -> Result<(), ContainerError> {
        Ok(())
    }
    async fn store_db_stream_handle(&self, _: Uuid, _: JoinHandle<()>) {
        panic!("No log threads")
    }
    async fn take_db_stream_handle(&self, _: &Uuid) -> Option<JoinHandle<()>> {
        None
    }
    async fn create(&self, _: &Workspace) -> Result<ContainerRef, ContainerError> {
        panic!("No worktree creation")
    }
    async fn kill_all_running_processes(&self) -> Result<(), ContainerError> {
        panic!("No process recovery")
    }
    async fn delete_worktree(&self, _: &Workspace) -> Result<(), ContainerError> {
        panic!("No cleanup")
    }
    async fn delete(&self, _: &Workspace) -> Result<(), ContainerError> {
        panic!("No cleanup")
    }
    async fn ensure_container_exists(&self, w: &Workspace) -> Result<ContainerRef, ContainerError> {
        Ok(w.container_ref.clone().unwrap())
    }
    async fn is_container_clean(&self, _: &Workspace) -> Result<bool, ContainerError> {
        Ok(true)
    }
    async fn stop_execution(
        &self,
        _: &ExecutionProcess,
        _: ExecutionProcessStatus,
    ) -> Result<(), ContainerError> {
        panic!("No live stop")
    }
    async fn try_commit_changes(&self, _: &ExecutionContext) -> Result<bool, ContainerError> {
        panic!("No worktree commit")
    }
    async fn copy_project_files(&self, _: &Path, _: &Path, _: &str) -> Result<(), ContainerError> {
        panic!("No assets copied")
    }
    async fn stream_diff(
        &self,
        _: &Workspace,
        _: bool,
    ) -> Result<futures_util::stream::BoxStream<'static, Result<LogMsg, io::Error>>, ContainerError>
    {
        panic!("No diff streams")
    }
    async fn git_branch_prefix(&self) -> String {
        "synthetic".into()
    }
    async fn try_steer_active_turn(
        &self,
        session: &Session,
        data: &DraftFollowUpData,
    ) -> Result<bool, ContainerError> {
        let id: Uuid = sqlx::query_scalar("SELECT id FROM execution_processes WHERE session_id=? AND status='running' ORDER BY rowid DESC LIMIT 1").bind(session.id).fetch_one(&self.db.pool).await?;
        Ok(AppServerClient::steer_execution(id, data.message.clone()).await?)
    }
    async fn start_execution_inner(
        &self,
        workspace: &Workspace,
        process: &ExecutionProcess,
        action: &ExecutorAction,
    ) -> Result<(), ContainerError> {
        if let ExecutorActionType::ScriptRequest(request) = action.typ() {
            use executors::actions::Executable;
            use tokio::io::AsyncReadExt;
            services::services::original_worker::current()
                .expect("Monitor cannot launch before authority registration")
                .active()
                .await?;
            let approval =
                services::services::approvals::executor_approvals::ExecutorApprovalBridge::new(
                    services::services::approvals::Approvals::new(),
                    self.db.clone(),
                    NotificationService::new(Arc::new(RwLock::new(Config::default()))),
                    process.id,
                );
            let env = ExecutionEnv::new(RepoContext::default(), false, String::new());
            let mut child = request
                .spawn(&self.workspace_to_current_dir(workspace), approval, &env)
                .await?
                .child;
            let mut output = String::new();
            child
                .inner()
                .stdout
                .take()
                .unwrap()
                .read_to_string(&mut output)
                .await?;
            assert!(child.wait().await?.success());
            assert_eq!(output, "synthetic-startup-monitor");
            assert_eq!(process.run_reason, ExecutionProcessRunReason::ArchiveScript);
            ExecutionProcess::update_completion(
                &self.db.pool,
                process.id,
                ExecutionProcessStatus::Completed,
                Some(0),
            )
            .await?;
            self.scripts.fetch_add(1, Ordering::SeqCst);
            self.script_done.notify_one();
            return Ok(());
        }
        let ExecutorActionType::CodingAgentFollowUpRequest(request) = action.typ() else {
            panic!("Only synthetic follow-up")
        };
        let provider = self.provider.get().unwrap();
        let mut env = ExecutionEnv::new(RepoContext::default(), false, String::new());
        env.insert("VK_SESSION_ID", process.session_id.to_string());
        env.insert("VK_WORKSPACE_ID", workspace.id.to_string());
        env.insert("VK_EXECUTION_PROCESS_ID", process.id.to_string());
        env.original_worker = provider.launch_guard(&env).await?;
        // Same exact cache clone/verification helper used by follow-up spawn.
        let agent =
            executors::original_worker::resolve_for_launch(&request.executor_config, &env).await?;
        let executors::executors::CodingAgent::Codex(codex) = agent else {
            panic!("Synthetic Codex");
        };
        let combined_prompt = codex.append_prompt.combine_prompt(&request.prompt);
        self.launches.fetch_add(1, Ordering::SeqCst);
        let peer = native_peer(
            &request.session_id,
            self.worker_goal.load(Ordering::SeqCst),
            env.original_worker.clone(),
        )
        .await;
        let resumed = peer
            .client
            .thread_resume(serde_json::from_value(json!({"threadId":request.session_id})).unwrap())
            .await?;
        provider
            .native_started(
                &env,
                &resumed.thread.id,
                &resumed.model,
                &serde_json::to_value(resumed.reasoning_effort).unwrap(),
            )
            .await?;
        peer.client
            .turn_start_with_mode(
                request.session_id.clone(),
                serde_json::from_value(
                    json!([{"type":"text","text":combined_prompt,"text_elements":[]}]),
                )
                .unwrap(),
                None,
            )
            .await?;
        self.peers.lock().await.push(peer);
        Ok(())
    }
}

struct NativePeer {
    child: Child,
    client: Arc<AppServerClient>,
    cancel: CancellationToken,
}
impl Drop for NativePeer {
    fn drop(&mut self) {
        self.cancel.cancel();
        let _ = self.child.start_kill();
    }
}

async fn native_peer(
    thread: &str,
    active_goal: bool,
    guard: Option<Arc<dyn LaunchGuard>>,
) -> NativePeer {
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
    if let Some(guard) = guard {
        client.set_original_worker_guard(guard);
    }
    client.set_resolved_model("gpt-6.1-sol".into());
    client.set_routed_effort(serde_json::from_value(json!("high")).unwrap());
    let mut child = Command::new("python3").args(["-u", "-c", r#"
import json,sys
thread=sys.argv[1]; active=sys.argv[2]=='true'
for line in sys.stdin:
    q=json.loads(line); m=q.get('method'); p=q.get('params',{})
    if 'id' not in q: continue
    if m=='initialize': r={'userAgent':'codex_cli_rs/0.159.2 (synthetic)','platformFamily':'unix','platformOs':'linux'}
    elif m=='thread/goal/get': r={'goal':{'status':'active'} if active else None}
    elif m=='thread/resume':
        t={'id':thread,'preview':'synthetic','ephemeral':False,'modelProvider':'synthetic','createdAt':1,'updatedAt':1,'status':{'type':'idle'},'path':None,'cwd':'/synthetic','cliVersion':'0.159.2','source':'exec','turns':[]}
        r={'thread':t,'model':'gpt-6.1-sol','modelProvider':'synthetic','serviceTier':None,'cwd':'/synthetic','approvalPolicy':'on-request','approvalsReviewer':'user','sandbox':{'type':'readOnly'},'reasoningEffort':'high'}
    elif m=='turn/steer': r={'turnId':'synthetic-turn'}
    elif m=='turn/start':
        t={'id':'synthetic-turn','items':[],'status':'inProgress','error':None}
        print(json.dumps({'method':'turn/started','params':{'threadId':thread,'turn':t}}),flush=True)
        r={'turn':t}
    else: r={}
    print(json.dumps({'id':q['id'],'result':r}),flush=True)
"#, thread, if active_goal { "true" } else { "false" }]).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null()).kill_on_drop(true).spawn().unwrap();
    let (tx, _rx) = tokio::sync::oneshot::channel();
    client.connect(JsonRpcPeer::spawn(
        child.stdin.take().unwrap(),
        child.stdout.take().unwrap(),
        client.clone(),
        ExitSignalSender::new(tx),
        cancel.clone(),
    ));
    client.initialize().await.unwrap();
    client.register_session(thread).await.unwrap();
    NativePeer {
        child,
        client,
        cancel,
    }
}

struct SyntheticResources {
    failed: AtomicBool,
}
#[executors::original_worker::async_trait]
impl ResourceProbe for SyntheticResources {
    async fn sample(&self) -> io::Result<u64> {
        if self.failed.load(Ordering::SeqCst) {
            Err(invalid("Synthetic resource guard"))
        } else {
            Ok(0)
        }
    }
    fn interval(&self) -> Duration {
        Duration::ZERO
    }
}

fn call(id: usize) -> Value {
    json!({"jsonrpc":"2.0","id":id,"method":"tools/call","params":{"name":TOOL,"arguments":{}}})
}

#[tokio::test]
async fn production_follow_up_resolution_launch_and_workspace_races() {
    production_fixture(false, false).await;
}

#[tokio::test]
async fn production_timeout_receipt_recovery_and_revoke_endpoint() {
    production_fixture(true, false).await;
}

#[tokio::test]
async fn production_startup_holds_pr_monitor_archive_launch_until_adopted() {
    production_fixture(false, true).await;
}

async fn production_fixture(timeout_lifecycle: bool, monitor_startup: bool) {
    let dir = tempfile::tempdir().unwrap();
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(dir.path().join("fixture.sqlite"))
                .create_if_missing(true),
        )
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let db = DBService { pool: pool.clone() };
    let container = Arc::new(FixtureContainer {
        db: db.clone(),
        git: git::GitService::new(),
        stores: Arc::new(RwLock::new(HashMap::new())),
        provider: Arc::new(OnceLock::new()),
        launches: Arc::new(AtomicUsize::new(0)),
        worker_goal: Arc::new(AtomicBool::new(false)),
        peers: Arc::new(Mutex::new(Vec::new())),
        scripts: Arc::new(AtomicUsize::new(0)),
        script_done: Arc::new(tokio::sync::Notify::new()),
    });
    let deployment = FixtureDeployment {
        container: container.clone(),
        config: Arc::new(RwLock::new(Config::default())),
        events: EventService::new(db, Arc::new(MsgStore::new()), Arc::new(RwLock::new(0))),
        queue: QueuedMessageService::new(),
        monitor: Arc::new(FixtureMonitor::default()),
    };
    let raw: ExecutorConfig = serde_json::from_value(json!({"executor":"CODEX","variant":"DEFAULT","model_id":"gpt-6.1-sol","reasoning_id":"high"})).unwrap();
    let home = dir.path().join("native");
    tokio::fs::create_dir_all(&home).await.unwrap();
    // nextest isolates test processes; this fixture never opens the real native home.
    unsafe {
        std::env::set_var("CODEX_HOME", &home);
    }
    let native = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(home.join("state_5.sqlite"))
                .create_if_missing(true),
        )
        .await
        .unwrap();
    sqlx::query("CREATE TABLE threads(id TEXT PRIMARY KEY,rollout_path TEXT)")
        .execute(&native)
        .await
        .unwrap();
    let goals = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(home.join("goals_1.sqlite"))
                .create_if_missing(true),
        )
        .await
        .unwrap();
    sqlx::query("CREATE TABLE thread_goals(thread_id TEXT PRIMARY KEY,goal_id TEXT,objective TEXT,status TEXT,created_at_ms INTEGER)").execute(&goals).await.unwrap();
    // First upgrade has no journal epoch: bootstrap must establish it only
    // after proving quiescence and the exact release-pinned scope.
    let coverage = Uuid::new_v4();
    sqlx::raw_sql(
        "CREATE TABLE vk_runtime_identity(singleton INTEGER PRIMARY KEY,dataset_id TEXT)",
    )
    .execute(&pool)
    .await
    .unwrap();
    sqlx::query("INSERT INTO vk_runtime_identity VALUES(1,?)")
        .bind("a".repeat(32))
        .execute(&pool)
        .await
        .unwrap();
    let mut identities = Vec::new();
    let mut anchors = Vec::new();
    for name in ["manager", "worker"] {
        let root = dir.path().join(name);
        tokio::fs::create_dir_all(root.join("repo")).await.unwrap();
        let workspace = Workspace::create(
            &pool,
            &CreateWorkspace {
                branch: "synthetic".into(),
                name: Some(name.into()),
            },
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        sqlx::query("UPDATE workspaces SET container_ref=? WHERE id=?")
            .bind(root.to_str().unwrap())
            .bind(workspace.id)
            .execute(&pool)
            .await
            .unwrap();
        let repo = Repo::find_or_create(&pool, &root.join("repo"), "Synthetic repository")
            .await
            .unwrap();
        WorkspaceRepo::create_many(
            &pool,
            workspace.id,
            &[CreateWorkspaceRepo {
                repo_id: repo.id,
                target_branch: "synthetic".into(),
            }],
        )
        .await
        .unwrap();
        let session = Session::create(
            &pool,
            &CreateSession {
                executor: Some("CODEX".into()),
                name: Some(name.into()),
            },
            Uuid::new_v4(),
            workspace.id,
        )
        .await
        .unwrap();
        let thread = Uuid::new_v4().to_string();
        let rollout = home.join(format!("{name}.jsonl"));
        let input =
            json!({"type":"user_message","message":"Synthetic preapproved initial owner input"});
        let mut bytes = serde_json::to_vec(&json!({"type":"event_msg","payload":input})).unwrap();
        bytes.push(b'\n');
        tokio::fs::write(&rollout, bytes).await.unwrap();
        sqlx::query("INSERT INTO threads VALUES (?,?)")
            .bind(&thread)
            .bind(rollout.to_str().unwrap())
            .execute(&native)
            .await
            .unwrap();
        let action = ExecutorAction::new(
            ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                prompt: "Synthetic prior owner input".into(),
                session_id: thread.clone(),
                executor_config: raw.clone(),
                working_dir: session.agent_working_dir.clone(),
                reset_to_message_id: None,
                capacity: None,
            }),
            None,
        );
        let process = ExecutionProcess::create(
            &pool,
            &CreateExecutionProcess {
                session_id: session.id,
                executor_action: action,
                run_reason: ExecutionProcessRunReason::CodingAgent,
            },
            Uuid::new_v4(),
            &[],
        )
        .await
        .unwrap();
        let turn = CodingAgentTurn::create(
            &pool,
            &CreateCodingAgentTurn {
                execution_process_id: process.id,
                prompt: Some("Synthetic prior input".into()),
            },
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        sqlx::query("UPDATE coding_agent_turns SET agent_session_id=? WHERE id=?")
            .bind(&thread)
            .bind(turn.id)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query(
            "UPDATE coding_agent_turns SET summary='Synthetic completed prior turn' WHERE id=?",
        )
        .bind(turn.id)
        .execute(&pool)
        .await
        .unwrap();
        if name == "worker" {
            ExecutionProcess::update_completion(
                &pool,
                process.id,
                ExecutionProcessStatus::Completed,
                Some(0),
            )
            .await
            .unwrap();
        }
        let process = if name == "manager" {
            ExecutionProcess::update_completion(
                &pool,
                process.id,
                ExecutionProcessStatus::Completed,
                Some(0),
            )
            .await
            .unwrap();
            let resume = ExecutorAction::new(
                ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                    prompt: "/goal resume".into(),
                    session_id: thread.clone(),
                    executor_config: raw.clone(),
                    working_dir: session.agent_working_dir.clone(),
                    reset_to_message_id: None,
                    capacity: None,
                }),
                None,
            );
            ExecutionProcess::create(
                &pool,
                &CreateExecutionProcess {
                    session_id: session.id,
                    executor_action: resume,
                    run_reason: ExecutionProcessRunReason::CodingAgent,
                },
                Uuid::new_v4(),
                &[],
            )
            .await
            .unwrap()
        } else {
            process
        };
        identities.push(Identity {
            session: session.id,
            workspace: workspace.id,
            thread,
            root,
            working_dir: session.agent_working_dir,
            task: None,
            repositories: vec![repo.id],
            config: raw.clone(),
            profile_digest: services::services::original_worker::effective_profile_digest(&raw)
                .unwrap(),
            input_seal: services::services::original_worker::inputs::InputSeal {
                coverage_id: coverage,
                backend_sequence: 0,
                rollout,
                records: 1,
                prefix_digest: digest(&serde_json::to_vec(&vec![json!({"type":"user_message","message":"Synthetic preapproved initial owner input"})]).unwrap()),
            },
        });
        anchors.push(process.id);
    }
    let asset = dir.path().join("asset");
    tokio::fs::write(&asset, b"synthetic asset").await.unwrap();
    let contract = Contract {
        id: Uuid::new_v4(),
        manager: identities[0].clone(),
        worker: identities[1].clone(),
        goal_id: "synthetic-goal".into(),
        goal_created_at: 10,
        objective: "Synthetic fixed marketing revision".into(),
        revision: "synthetic-fixed-revision".into(),
        instructions: "Keep synthetic assets; grey date placeholders throughout marketing views."
            .into(),
        owner_evidence_digest: "a".repeat(64),
        manager_anchor: anchors[0],
        worker_anchor: anchors[1],
        assets: vec![services::services::original_worker::AssetPin {
            path: asset,
            sha256: digest(b"synthetic asset"),
        }],
        recommend: serde_json::from_value(json!({"mode":"shadow"})).unwrap(),
    };
    sqlx::query("INSERT INTO thread_goals VALUES (?,?,?,'active',10000)")
        .bind(&contract.manager.thread)
        .bind(&contract.goal_id)
        .bind(&contract.objective)
        .execute(&goals)
        .await
        .unwrap();
    if monitor_startup {
        exercise_monitor_startup(&deployment, &contract, dir.path()).await;
        native.close().await;
        goals.close().await;
        pool.close().await;
        return;
    }
    let ledger = exercise_bootstrap_acceptance(&deployment, &contract, dir.path()).await;

    let resources = Arc::new(SyntheticResources {
        failed: AtomicBool::new(false),
    });
    let runtime = Arc::new(Live {
        deployment: deployment.clone(),
        ledger: ledger.clone(),
        sampled: Mutex::new(None),
        resources: resources.clone(),
    });
    let engine = Arc::new(Engine {
        ledger: ledger.clone(),
        runtime: runtime.clone(),
    });
    let provider = Arc::new(Provider {
        runtime: runtime.clone(),
        engine: engine.clone(),
    });
    assert!(container.provider.set(provider).is_ok());
    services::services::original_worker::register(ledger.clone()).unwrap();
    let manager = native_peer(&ledger.contract.manager.thread, false, None).await;
    manager
        .client
        .turn_start_with_mode(
            ledger.contract.manager.thread.clone(),
            serde_json::from_value(
                json!([{"type":"text","text":"synthetic prior owner input","text_elements":[]}]),
            )
            .unwrap(),
            None,
        )
        .await
        .unwrap();
    AppServerClient::register_active_execution(anchors[0], &manager.client);
    assert!(engine.handle(Uuid::new_v4(), call(1)).await.is_err());
    runtime.check(anchors[0]).await.unwrap();
    resources.failed.store(true, Ordering::SeqCst);
    assert!(engine.handle(anchors[0], call(2)).await.is_err());
    resources.failed.store(false, Ordering::SeqCst);
    let asset = &ledger.contract.assets[0].path;
    tokio::fs::write(asset, b"synthetic altered asset")
        .await
        .unwrap();
    assert!(engine.handle(anchors[0], call(20)).await.is_err());
    tokio::fs::write(asset, b"synthetic asset").await.unwrap();
    let worker_action: String =
        sqlx::query_scalar("SELECT executor_action FROM execution_processes WHERE id=?")
            .bind(anchors[1])
            .fetch_one(&pool)
            .await
            .unwrap();
    let mut changed: ExecutorAction = serde_json::from_str(&worker_action).unwrap();
    if let ExecutorActionType::CodingAgentFollowUpRequest(r) = &mut changed.typ {
        r.executor_config.reasoning_id = Some("low".into());
    }
    sqlx::query("UPDATE execution_processes SET executor_action=? WHERE id=?")
        .bind(serde_json::to_string(&changed).unwrap())
        .bind(anchors[1])
        .execute(&pool)
        .await
        .unwrap();
    assert!(engine.handle(anchors[0], call(21)).await.is_err());
    sqlx::query("UPDATE execution_processes SET executor_action=? WHERE id=?")
        .bind(&worker_action)
        .bind(anchors[1])
        .execute(&pool)
        .await
        .unwrap();
    let sibling = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: Some("sibling".into()),
        },
        Uuid::new_v4(),
        ledger.contract.worker.workspace,
    )
    .await
    .unwrap();
    let queued = DraftFollowUpData {
        message: "Synthetic collision".into(),
        executor_config: raw.clone(),
    };
    let entered = Arc::new(tokio::sync::Notify::new());
    let release = Arc::new(tokio::sync::Notify::new());
    let writing = tokio::spawn({
        let entered = entered.clone();
        let release = release.clone();
        let queue = deployment.queue.clone();
        let sibling_id = sibling.id;
        async move {
            admission::run(async {
                entered.notify_one();
                release.notified().await;
                queue.queue_for_capacity(sibling_id, queued);
            })
            .await;
        }
    });
    entered.notified().await;
    let racing = tokio::spawn({
        let engine = engine.clone();
        let caller = anchors[0];
        async move { engine.handle(caller, call(3)).await }
    });
    release.notify_one();
    writing.await.unwrap();
    assert!(
        racing.await.unwrap().is_err(),
        "queued sibling admission wins atomically before bounded start"
    );
    deployment.queue.cancel_queued(sibling.id);
    let sibling_process = ExecutionProcess::create(
        &pool,
        &CreateExecutionProcess {
            session_id: sibling.id,
            executor_action: ExecutorAction::new(
                ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                    prompt: "Synthetic collision".into(),
                    executor_config: raw.clone(),
                    session_id: "synthetic-sibling".into(),
                    working_dir: sibling.agent_working_dir.clone(),
                    reset_to_message_id: None,
                    capacity: None,
                }),
                None,
            ),
            run_reason: ExecutionProcessRunReason::CodingAgent,
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    assert!(engine.handle(anchors[0], call(4)).await.is_err());
    ExecutionProcess::update_completion(
        &pool,
        sibling_process.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    let (a, b) = tokio::join!(
        engine.handle(anchors[0], call(5)),
        engine.handle(anchors[0], call(6))
    );
    assert_eq!(
        usize::from(a.is_ok()) + usize::from(b.is_ok()),
        1,
        "one actual follow-up admission: a={a:?}, b={b:?}"
    );
    assert_eq!(container.launches.load(Ordering::SeqCst), 1);
    assert!(
        admission::run(follow_up_admitted(
            Extension(sibling.clone()),
            State(deployment.clone()),
            Json(CreateFollowUpAttempt {
                prompt: "Synthetic ordinary sibling collision".into(),
                executor_config: raw.clone(),
                retry_process_id: None,
                force_when_dirty: None,
                perform_git_reset: Some(false)
            })
        ))
        .await
        .is_err(),
        "normal follow-up cannot start a sibling while the bound worker runs"
    );

    let action: String = sqlx::query_scalar("SELECT executor_action FROM execution_processes WHERE session_id=? ORDER BY rowid DESC LIMIT 1").bind(ledger.contract.worker.session).fetch_one(&pool).await.unwrap();
    let action: ExecutorAction = serde_json::from_str(&action).unwrap();
    assert_eq!(executors::routing::config(&action), Some(&raw));
    assert!(raw.routing.is_none());
    assert_eq!(
        action.routing_decision.as_ref().unwrap().mode,
        executors::routing::RoutingMode::Shadow
    );
    let activations: i64 = sqlx::query_scalar("SELECT sum(activated) FROM bounded_worker_attempts")
        .fetch_one(&pool)
        .await
        .unwrap();
    assert_eq!(activations, 1);
    if timeout_lifecycle {
        let first_execution: Uuid =
            sqlx::query_scalar("SELECT execution FROM bounded_worker_attempts WHERE activated=1")
                .fetch_one(&pool)
                .await
                .unwrap();
        ledger
            .native_receipt_uncertain(first_execution)
            .await
            .unwrap();
        assert!(ledger.active().await.is_ok());
        assert!(
            engine.handle(anchors[0], call(30)).await.is_err(),
            "uncertain original execution cannot replay"
        );
        ExecutionProcess::update_completion(
            &pool,
            first_execution,
            ExecutionProcessStatus::Completed,
            Some(0),
        )
        .await
        .unwrap();
        assert!(
            engine.handle(anchors[0], call(310)).await.is_err(),
            "exit alone cannot substitute for durable native completion"
        );
        ledger
            .active()
            .await
            .expect("missing native completion is not a terminal amendment");
        sqlx::query("UPDATE coding_agent_turns SET agent_session_id=?,summary='Synthetic completed bounded turn' WHERE execution_process_id=?")
            .bind(&ledger.contract.worker.thread).bind(first_execution).execute(&pool).await.unwrap();
        let recovered = engine.handle(anchors[0], call(31)).await;
        assert!(
            recovered.is_ok(),
            "actual Live/follow_up path recovers only from its exact successful receipt: {recovered:?}"
        );
        let second_execution:Uuid=sqlx::query_scalar("SELECT execution FROM bounded_worker_attempts WHERE state='dispatching' ORDER BY rowid DESC LIMIT 1").fetch_one(&pool).await.unwrap();
        ledger
            .native_receipt_uncertain(second_execution)
            .await
            .unwrap();
        let mut revoke = call(32);
        revoke["params"]["name"] = json!(executors::original_worker::REVOKE);
        assert!(
            engine.handle(anchors[0], revoke).await.is_ok(),
            "actual revoke endpoint remains reachable after native uncertainty"
        );
        assert!(engine.handle(anchors[0], call(33)).await.is_err());
        // Terminal authority stays terminal even after a later successful execution.
        ExecutionProcess::update_completion(
            &pool,
            second_execution,
            ExecutionProcessStatus::Completed,
            Some(0),
        )
        .await
        .unwrap();
        assert!(ledger.reconcile().await.is_err());

        drop(manager);
        container.peers.lock().await.clear();
        return;
    }

    // New native steering is rejected even though goal and executor_action did not change.
    tokio::fs::write(&ledger.contract.manager.input_seal.rollout, serde_json::to_vec(&json!({"type":"event_msg","payload":{"type":"user_message","message":"Synthetic unverified amendment"}})).unwrap()).await.unwrap();
    assert!(runtime.check(anchors[0]).await.is_err());
    assert!(ledger.active().await.is_err());
    let original_action: String =
        sqlx::query_scalar("SELECT executor_action FROM execution_processes WHERE id=?")
            .bind(anchors[0])
            .fetch_one(&pool)
            .await
            .unwrap();
    let steering = admission::run(crate::routes::sessions::queue::queue_message_admitted(
        Extension(
            Session::find_by_id(&pool, ledger.contract.manager.session)
                .await
                .unwrap()
                .unwrap(),
        ),
        State(deployment.clone()),
        Json(crate::routes::sessions::queue::QueueMessageRequest {
            message: "Synthetic owner input through actual queue steering".into(),
            executor_config: raw.clone(),
        }),
    ))
    .await
    .unwrap();
    assert!(steering.0.is_success());
    let same_action: String =
        sqlx::query_scalar("SELECT executor_action FROM execution_processes WHERE id=?")
            .bind(anchors[0])
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(same_action, original_action);
    let steering_events: i64 = sqlx::query_scalar(
        "SELECT count(*) FROM bounded_native_input_history WHERE session_id=? AND native_resume=0",
    )
    .bind(ledger.contract.manager.session)
    .fetch_one(&pool)
    .await
    .unwrap();
    assert_eq!(
        steering_events, 1,
        "durable evidence exists even when executor_action stays unchanged"
    );
    let barrier = Arc::new(tokio::sync::Barrier::new(2));
    tokio::time::timeout(Duration::from_secs(2), async {
        tokio::join!(
            admission::run(async {
                barrier.wait().await;
            }),
            admission::run(async {
                barrier.wait().await;
            })
        );
    })
    .await
    .expect("terminal grant must stop serializing unrelated ordinary starts");
    drop(manager);
    container.peers.lock().await.clear();
}

/// The actual loader used by both server entry points, with synthetic procfs.
/// Every failing bootstrap leaves ingress unregistered and creates no coverage.
async fn exercise_monitor_startup(
    deployment: &FixtureDeployment,
    contract: &Contract,
    directory: &Path,
) {
    use std::os::unix::fs::PermissionsExt;

    use db::models::pull_request::PullRequest;

    // Only GitHub's external receipt is synthetic. The production monitor,
    // archive policy, execution admission and script spawning remain real.
    let bin = directory.join("bin");
    tokio::fs::create_dir_all(&bin).await.unwrap();
    let gh = bin.join("gh");
    tokio::fs::write(
        &gh,
        b"#!/bin/sh\n[ \"$1\" = pr ] && [ \"$2\" = view ] || exit 1\ncat <<'JSON'\n{\"number\":1,\"url\":\"https://github.com/synthetic/fixture/pull/1\",\"state\":\"MERGED\",\"mergedAt\":\"2026-01-01T00:00:00Z\",\"mergeCommit\":{\"oid\":\"1111111111111111111111111111111111111111\"},\"title\":\"Synthetic\",\"baseRefName\":\"synthetic-review\",\"headRefName\":\"synthetic\"}\nJSON\n",
    )
    .await
    .unwrap();
    tokio::fs::set_permissions(&gh, std::fs::Permissions::from_mode(0o700))
        .await
        .unwrap();
    let previous_path = std::env::var_os("PATH").unwrap();
    let path =
        std::env::join_paths(std::iter::once(bin).chain(std::env::split_paths(&previous_path)))
            .unwrap();
    // nextest runs this fixture in its own process, never a shared backend.
    unsafe { std::env::set_var("PATH", path) };
    let pool = &deployment.db().pool;
    let root = directory.join("monitor");
    tokio::fs::create_dir_all(root.join("repo")).await.unwrap();
    let workspace = Workspace::create(
        pool,
        &CreateWorkspace {
            branch: "synthetic".into(),
            name: Some("monitor".into()),
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    sqlx::query("UPDATE workspaces SET container_ref=? WHERE id=?")
        .bind(root.to_str().unwrap())
        .bind(workspace.id)
        .execute(pool)
        .await
        .unwrap();
    let repo = Repo::find_or_create(pool, &root.join("repo"), "Synthetic monitor repository")
        .await
        .unwrap();
    sqlx::query("UPDATE repos SET archive_script=? WHERE id=?")
        .bind("printf synthetic-startup-monitor")
        .bind(repo.id)
        .execute(pool)
        .await
        .unwrap();
    WorkspaceRepo::create_many(
        pool,
        workspace.id,
        &[CreateWorkspaceRepo {
            repo_id: repo.id,
            target_branch: "synthetic-review".into(),
        }],
    )
    .await
    .unwrap();
    let url = "https://github.com/synthetic/fixture/pull/1";
    PullRequest::create_for_workspace(pool, workspace.id, repo.id, "synthetic-review", 1, url)
        .await
        .unwrap();
    deployment.monitor.enabled.store(true, Ordering::SeqCst);
    assert!(
        crate::startup::configured_background(deployment, async {
            Err(invalid("Synthetic failed configuration"))
        })
        .await
        .is_err()
    );
    assert!(deployment.monitor.handle.lock().await.is_none());
    assert_eq!(deployment.container.scripts.load(Ordering::SeqCst), 0);
    assert!(
        !Workspace::find_by_id(pool, workspace.id)
            .await
            .unwrap()
            .unwrap()
            .archived
    );

    let entered = Arc::new(tokio::sync::Notify::new());
    let release = Arc::new(tokio::sync::Notify::new());
    let task = {
        let deployment = deployment.clone();
        let contract = contract.clone();
        let directory = directory.to_owned();
        let entered = entered.clone();
        let release = release.clone();
        tokio::spawn(async move {
            crate::startup::configured_background(&deployment, async {
                entered.notify_one();
                release.notified().await;
                let ledger =
                    exercise_bootstrap_acceptance(&deployment, &contract, &directory).await;
                services::services::original_worker::register(ledger).unwrap();
                Ok(())
            })
            .await
        })
    };
    entered.notified().await;
    assert!(
        deployment.monitor.handle.lock().await.is_none(),
        "real monitor cannot start while adoption is pending"
    );
    assert_eq!(deployment.container.scripts.load(Ordering::SeqCst), 0);
    let grants: i64 = sqlx::query_scalar("SELECT count(*) FROM bounded_worker_grants")
        .fetch_one(pool)
        .await
        .unwrap();
    assert_eq!(grants, 0);
    assert!(
        !Workspace::find_by_id(pool, workspace.id)
            .await
            .unwrap()
            .unwrap()
            .archived
    );
    release.notify_one();
    task.await.unwrap().unwrap();
    tokio::time::timeout(
        Duration::from_secs(5),
        deployment.container.script_done.notified(),
    )
    .await
    .expect(
        "production monitor must reach archive admission and actual script launch after adoption",
    );
    assert_eq!(deployment.container.scripts.load(Ordering::SeqCst), 1);
    assert!(
        Workspace::find_by_id(pool, workspace.id)
            .await
            .unwrap()
            .unwrap()
            .archived
    );
    assert_eq!(
        PullRequest::count_open_for_workspace(pool, workspace.id)
            .await
            .unwrap(),
        0
    );
    let archives:i64=sqlx::query_scalar("SELECT count(*) FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.run_reason='archivescript' AND e.status='completed' AND e.exit_code=0")
        .bind(workspace.id).fetch_one(pool).await.unwrap();
    assert_eq!(archives, 1);
    assert_eq!(deployment.container.launches.load(Ordering::SeqCst), 0);
    // Stop only this fixture's monitor, not any production service or process.
    let handle = deployment.monitor.handle.lock().await.take().unwrap();
    handle.abort();
    let _ = handle.await;
    unsafe { std::env::set_var("PATH", previous_path) };
}

async fn exercise_bootstrap_acceptance(
    deployment: &FixtureDeployment,
    contract: &Contract,
    directory: &Path,
) -> Arc<Ledger> {
    let pool = &deployment.db().pool;
    let mut f =
        bootstrap::tests::Fixture::new(directory, contract, pool.connect_options().get_filename());
    let baseline = f.receipt.clone();
    let contract_bytes = tokio::fs::read(&f.files.contract).await.unwrap();
    let manager_bytes = tokio::fs::read(&contract.manager.input_seal.rollout)
        .await
        .unwrap();
    let worker_bytes = tokio::fs::read(&contract.worker.input_seal.rollout)
        .await
        .unwrap();
    let pin = f.files.contract_sha256.clone();
    for case in [
        "contract_pin",
        "proof_pin",
        "missing_proof",
        "changed_contract",
        "scope_pin",
        "dataset",
        "database",
        "database_object",
        "different_epoch",
        "future_watermark",
        "profile_pin",
        "home",
        "boot",
        "missing_ingress",
        "missing_writer",
        "wrong_writer",
        "live_ingress",
        "live_writer",
        "unlisted_writer",
        "unlisted_ingress",
        "unmarked_ingress",
        "unscoped_native",
        "forged_unrelated_session",
        "unknown_producer",
        "open_input_file",
        "changed_prefix",
        "truncated_prefix",
        "worker_input",
        "goal_amended",
        "goal_ready",
        "journal_amendment",
        "revoked",
        "ready",
        "suspended",
        "different_prior_contract",
    ] {
        f.receipt = baseline.clone();
        f.files.contract_sha256 = pin.clone();
        let mut process = None;
        match case {
            "contract_pin" => f.files.contract_sha256="b".repeat(64),
            "changed_contract" => { let mut c=contract.clone();c.instructions.push_str(" Synthetic unauthorized amendment");tokio::fs::write(&f.files.contract,serde_json::to_vec(&c).unwrap()).await.unwrap(); },
            "scope_pin" => f.receipt.contract_sha256="b".repeat(64),
            "dataset" => f.receipt.dataset_id="b".repeat(32),
            "database" => f.receipt.database=directory.join("other-dataset.sqlite"),
            "different_epoch"|"future_watermark"|"profile_pin" => {
                let mut c=contract.clone();
                if case=="different_epoch" {c.manager.input_seal.coverage_id=Uuid::new_v4();}
                if case=="future_watermark" {c.manager.input_seal.backend_sequence=1000;}
                if case=="profile_pin" {c.manager.profile_digest="d".repeat(64);}
                let bytes=serde_json::to_vec(&c).unwrap();
                f.files.contract_sha256=digest(&bytes);f.receipt.contract_sha256=f.files.contract_sha256.clone();
                tokio::fs::write(&f.files.contract,bytes).await.unwrap();
            },
            "database_object" => f.receipt.database_object="unknown:object".into(),
            "home" => f.receipt.native_home=directory.join("other-home"),
            "boot" => f.receipt.boot_id="11111111-2222-4333-8444-666666666666".into(),
            "missing_ingress" => f.receipt.old_ingress.clear(),
            "missing_writer" => { f.receipt.native_writers.pop(); },
            "wrong_writer" => f.receipt.native_writers[1].thread="unrelated-native-thread".into(),
            "live_ingress"|"live_writer"|"unlisted_writer"|"unlisted_ingress"|"unknown_producer"|"open_input_file" => {
                let pid=match case { "live_ingress"=>42,"live_writer"=>43,_=>88 };
                let ticks=if pid==43 {200} else {100};
                let env=match case {
                    "unlisted_writer"=>format!("VK_SESSION_ID={}\0",contract.worker.session),
                    "unlisted_ingress"=>"VK_RUNTIME_IDENTITY_FILE=/synthetic/runtime-pin\0".into(),
                    _=>String::new(),
                };
                f.process(pid,ticks,&env,directory,if case=="unlisted_ingress" {"server"} else {"synthetic-helper"});
                if case=="unknown_producer" { f.unknown_process(pid); }
                if case=="open_input_file" { f.held_rollout(pid,&contract.worker.input_seal.rollout); }
                process=Some(pid);
            },
            "changed_prefix" => tokio::fs::write(&contract.manager.input_seal.rollout,serde_json::to_vec(&json!({"type":"event_msg","payload":{"type":"user_message","message":"Synthetic changed owner history"}})).unwrap()).await.unwrap(),
            "truncated_prefix" => tokio::fs::write(&contract.manager.input_seal.rollout,b"").await.unwrap(),
            "worker_input" => tokio::fs::write(&contract.worker.input_seal.rollout,serde_json::to_vec(&json!({"type":"event_msg","payload":{"type":"user_message","message":"Synthetic unknown worker input"}})).unwrap()).await.unwrap(),
            "goal_amended"|"goal_ready" => {
                let home=executors::executors::codex::codex_home().unwrap();
                let goals=sqlx::sqlite::SqlitePoolOptions::new().max_connections(1).connect_with(sqlx::sqlite::SqliteConnectOptions::new().filename(home.join("goals_1.sqlite"))).await.unwrap();
                sqlx::query("UPDATE thread_goals SET objective=?,status=? WHERE thread_id=?")
                    .bind(if case=="goal_amended" {"Synthetic different objective"} else {&contract.objective})
                    .bind(if case=="goal_ready" {"completed"} else {"active"}).bind(&contract.manager.thread).execute(&goals).await.unwrap();
                goals.close().await;
            },
            "journal_amendment" => services::services::original_worker::record_input(pool,contract.manager.session,false).await.unwrap(),
            "revoked"|"ready"|"suspended"|"different_prior_contract" => {
                sqlx::query("INSERT INTO bounded_worker_grants(id,contract_digest,state) VALUES(?,?,?)")
                    .bind(contract.id).bind(if case=="different_prior_contract" {"different".into()} else {digest(&serde_json::to_vec(contract).unwrap())})
                    .bind(if case=="different_prior_contract" {"active"} else {case}).execute(pool).await.unwrap();
            },
            "unmarked_ingress" => { f.process(78,190,"",directory,"server");process=Some(78); },
            "unscoped_native" => { f.process(78,190,"",directory,"codex");process=Some(78); },
            "forged_unrelated_session" => { f.process(78,190,&format!("VK_SESSION_ID={}\0CODEX_HOME={}\0",Uuid::new_v4(),baseline_home(&f)),directory,"codex");process=Some(78); },
            _=>{},
        }
        f.save();
        if case == "proof_pin" {
            f.files.bootstrap_sha256 = "b".repeat(64);
        }
        if case == "missing_proof" {
            tokio::fs::remove_file(&f.files.bootstrap).await.unwrap();
        }
        let ingress = std::sync::atomic::AtomicBool::new(false);
        let result = async {
            let ledger = load_startup(deployment, &f.files, &f.processes).await?;
            ingress.store(true, Ordering::SeqCst);
            Ok::<_, io::Error>(ledger)
        }
        .await;
        assert!(result.is_err(), "bootstrap case {case} must fail closed");
        assert!(!ingress.load(Ordering::SeqCst));
        assert_eq!(deployment.container.launches.load(Ordering::SeqCst), 0);
        let coverage: i64 =
            sqlx::query_scalar("SELECT count(*) FROM bounded_native_input_coverage")
                .fetch_one(pool)
                .await
                .unwrap();
        assert_eq!(coverage, 0, "case {case} must fail before coverage");
        let grants: i64 = sqlx::query_scalar("SELECT count(*) FROM bounded_worker_grants")
            .fetch_one(pool)
            .await
            .unwrap();
        assert_eq!(
            grants,
            i64::from(matches!(
                case,
                "revoked" | "ready" | "suspended" | "different_prior_contract"
            )),
            "bootstrap must not mint/revive authority: {case}"
        );
        // Reset only this isolated fault fixture, not any live grant or history.
        if let Some(pid) = process {
            f.forget_process(pid);
        }
        tokio::fs::write(&f.files.contract, &contract_bytes)
            .await
            .unwrap();
        tokio::fs::write(&contract.manager.input_seal.rollout, &manager_bytes)
            .await
            .unwrap();
        tokio::fs::write(&contract.worker.input_seal.rollout, &worker_bytes)
            .await
            .unwrap();
        if matches!(case, "goal_amended" | "goal_ready") {
            let home = executors::executors::codex::codex_home().unwrap();
            let goals = sqlx::sqlite::SqlitePoolOptions::new()
                .max_connections(1)
                .connect_with(
                    sqlx::sqlite::SqliteConnectOptions::new().filename(home.join("goals_1.sqlite")),
                )
                .await
                .unwrap();
            sqlx::query("UPDATE thread_goals SET objective=?,status='active' WHERE thread_id=?")
                .bind(&contract.objective)
                .bind(&contract.manager.thread)
                .execute(&goals)
                .await
                .unwrap();
            goals.close().await;
        }
        if case == "journal_amendment" {
            sqlx::query("DELETE FROM bounded_native_input_history")
                .execute(pool)
                .await
                .unwrap();
        }
        if matches!(
            case,
            "revoked" | "ready" | "suspended" | "different_prior_contract"
        ) {
            sqlx::query("DELETE FROM bounded_worker_grants WHERE id=?")
                .bind(contract.id)
                .execute(pool)
                .await
                .unwrap();
        }
    }
    f.receipt = baseline;
    f.files.contract_sha256 = pin;
    f.save();
    let unrelated_root = directory.join("proven-unrelated");
    tokio::fs::create_dir_all(&unrelated_root).await.unwrap();
    let workspace = Workspace::create(
        pool,
        &CreateWorkspace {
            branch: "synthetic-unrelated".into(),
            name: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    sqlx::query("UPDATE workspaces SET container_ref=? WHERE id=?")
        .bind(unrelated_root.to_str().unwrap())
        .bind(workspace.id)
        .execute(pool)
        .await
        .unwrap();
    let session = Session::create(
        pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: None,
        },
        Uuid::new_v4(),
        workspace.id,
    )
    .await
    .unwrap();
    let thread = "synthetic-proven-unrelated-thread";
    let process = ExecutionProcess::create(
        pool,
        &CreateExecutionProcess {
            session_id: session.id,
            run_reason: ExecutionProcessRunReason::CodingAgent,
            executor_action: ExecutorAction::new(
                ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                    prompt: "Synthetic unrelated input".into(),
                    session_id: thread.into(),
                    executor_config: contract.worker.config.clone(),
                    working_dir: None,
                    reset_to_message_id: None,
                    capacity: None,
                }),
                None,
            ),
        },
        Uuid::new_v4(),
        &[],
    )
    .await
    .unwrap();
    let turn = CodingAgentTurn::create(
        pool,
        &CreateCodingAgentTurn {
            execution_process_id: process.id,
            prompt: Some("Synthetic unrelated input".into()),
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let native = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(f.receipt.native_home.join("state_5.sqlite")),
        )
        .await
        .unwrap();
    let rollout = f.receipt.native_home.join("unrelated.jsonl");
    tokio::fs::write(&rollout, b"").await.unwrap();
    sqlx::query("INSERT INTO threads VALUES (?,?)")
        .bind(thread)
        .bind(rollout.to_str().unwrap())
        .execute(&native)
        .await
        .unwrap();
    native.close().await;
    f.process(
        89,
        300,
        &format!(
            "VK_SESSION_ID={}\0VK_WORKSPACE_ID={}\0VK_EXECUTION_PROCESS_ID={}\0CODEX_HOME={}\0VK_RUNTIME_IDENTITY_FILE=/synthetic/runtime-pin\0",
            session.id,workspace.id,process.id,
            baseline_home(&f)
        ),
        &unrelated_root,
        "codex",
    );
    assert!(
        load_startup(deployment, &f.files, &f.processes)
            .await
            .is_err(),
        "existing execution labels alone cannot prove process ownership"
    );
    let unit = "vk-exec-codex-11111111222243338444555555555555.service";
    let unit_env = format!(
        "VK_SESSION_ID={} VK_WORKSPACE_ID={} VK_EXECUTION_PROCESS_ID={} CODEX_HOME={}",
        session.id,
        workspace.id,
        process.id,
        baseline_home(&f)
    );
    f.unit(89, unit, &unit_env);
    assert!(
        load_startup(deployment, &f.files, &f.processes)
            .await
            .is_err(),
        "service/execution receipt without native thread remains unknown"
    );
    sqlx::query("UPDATE coding_agent_turns SET agent_session_id=? WHERE id=?")
        .bind(thread)
        .bind(turn.id)
        .execute(pool)
        .await
        .unwrap();
    assert!(
        load_startup(deployment, &f.files, &f.processes)
            .await
            .is_err(),
        "index labels without a held rollout are not process/thread provenance"
    );
    f.held_rollout(89, &rollout);
    f.unit(
        89,
        unit,
        &format!(
            "VK_SESSION_ID={} VK_WORKSPACE_ID={} VK_EXECUTION_PROCESS_ID={} CODEX_HOME={}",
            session.id,
            workspace.id,
            Uuid::new_v4(),
            baseline_home(&f)
        ),
    );
    assert!(
        load_startup(deployment, &f.files, &f.processes)
            .await
            .is_err(),
        "forged process claims cannot replace backend service identity"
    );
    f.unit(89, unit, &unit_env);
    // Existing same-thread goals are paused during a safe restart. Adoption
    // validates their unchanged identity without activating native inference.
    let home = executors::executors::codex::codex_home().unwrap();
    let goals = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new().filename(home.join("goals_1.sqlite")),
        )
        .await
        .unwrap();
    sqlx::query("UPDATE thread_goals SET status='paused' WHERE thread_id=?")
        .bind(&contract.manager.thread)
        .execute(&goals)
        .await
        .unwrap();
    let ledger = load_startup(deployment, &f.files, &f.processes)
        .await
        .unwrap();
    ledger.active().await.unwrap();
    assert_eq!(
        deployment.container.launches.load(Ordering::SeqCst),
        0,
        "startup must not start either native target"
    );
    assert_eq!(
        tokio::fs::read(&f.files.contract).await.unwrap(),
        contract_bytes,
        "never rewrite the pinned contract"
    );
    assert_eq!(
        tokio::fs::read(&contract.manager.input_seal.rollout)
            .await
            .unwrap(),
        manager_bytes
    );
    // Same pinned startup is idempotent and retains the exact preallocated epoch.
    let restarted = load_startup(deployment, &f.files, &f.processes)
        .await
        .unwrap();
    restarted.active().await.unwrap();
    let epoch: Uuid = sqlx::query_scalar("SELECT id FROM bounded_native_input_coverage")
        .fetch_one(pool)
        .await
        .unwrap();
    assert_eq!(epoch, contract.manager.input_seal.coverage_id);
    assert_eq!(
        ExecutionProcess::find_by_id(pool, process.id)
            .await
            .unwrap()
            .unwrap()
            .status,
        ExecutionProcessStatus::Running,
        "proven unrelated work is left undisturbed"
    );
    // Fixture activity ends only after startup tests, so later collision tests
    // use their original synthetic global activity inventory.
    ExecutionProcess::update_completion(
        pool,
        process.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    sqlx::query("UPDATE thread_goals SET status='active' WHERE thread_id=?")
        .bind(&contract.manager.thread)
        .execute(&goals)
        .await
        .unwrap();
    goals.close().await;
    ledger
}

fn baseline_home(f: &bootstrap::tests::Fixture) -> String {
    f.receipt.native_home.to_string_lossy().into_owned()
}
