//! Actual route service, native default ContainerService launch, migrated SQLite
//! and QueuedMessageService. Only executor/process I/O is synthetic.
use std::{
    collections::HashMap,
    io,
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    },
};

use db::{
    DBService,
    models::{
        coding_agent_turn::CreateCodingAgentTurn,
        execution_process::{CreateExecutionProcess, ExecutionContext, ExecutionProcessStatus},
        repo::Repo,
        scratch::DraftFollowUpData,
        session::CreateSession,
        workspace::CreateWorkspace,
        workspace_repo::CreateWorkspaceRepo,
    },
};
use executors::{
    actions::coding_agent_initial::CodingAgentInitialRequest, profile::ExecutorConfig,
};
use services::services::{
    approvals::{Approvals, executor_approvals::ExecutorApprovalBridge},
    config::Config,
    container::ContainerRef,
    events::EventService,
    notification::NotificationService,
    queued_message::QueuedMessageService,
};
use tokio::{sync::RwLock, task::JoinHandle};
use tokio_util::sync::CancellationToken;
use utils::{log_msg::LogMsg, msg_store::MsgStore};

use super::*;

#[derive(Clone)]
struct FixtureDeployment {
    container: Arc<FixtureContainer>,
    config: Arc<RwLock<Config>>,
    events: EventService,
    queue: QueuedMessageService,
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
        panic!("No background services in isolation")
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

struct FixtureContainer {
    db: DBService,
    git: git::GitService,
    stores: Arc<RwLock<HashMap<Uuid, Arc<MsgStore>>>>,
    notifications: NotificationService,
    approvals: Approvals,
    launches: AtomicUsize,
    fail_spawn: std::sync::atomic::AtomicBool,
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
        &self.notifications
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

    async fn start_execution_inner(
        &self,
        _: &Workspace,
        process: &ExecutionProcess,
        action: &ExecutorAction,
    ) -> Result<(), ContainerError> {
        // The real production default start has already run capacity/routing,
        // persistence, receipt binding, repository and coding-turn creation.
        let ExecutorActionType::CodingAgentFollowUpRequest(request) = action.typ() else {
            panic!("Must continue existing native owner")
        };
        assert_eq!(request.session_id, "synthetic-existing-thread");
        assert!(request.reset_to_message_id.is_none());
        assert!(request.capacity.is_none());
        assert_eq!(request.executor_config.variant.as_deref(), Some("DEFAULT"));
        assert_eq!(
            request.executor_config.model_id.as_deref(),
            Some("synthetic-saved-model")
        );
        assert_eq!(
            request.executor_config.reasoning_id.as_deref(),
            Some("synthetic-saved-effort")
        );
        assert_eq!(
            request.executor_config.routing.as_ref().unwrap().mode,
            RoutingMode::Shadow
        );
        if let Some(receipt) = admission::candidate_execution_id() {
            assert_eq!(receipt, process.id);
        }
        if self.fail_spawn.load(Ordering::SeqCst) {
            return Err(ContainerError::Other(anyhow::anyhow!(
                "Synthetic executor refusal"
            )));
        }
        // Use the same real interactive bridge as LocalContainerService. A
        // storage alert must not make a permission request approve itself.
        use executors::approvals::ExecutorApprovalService;
        let bridge = ExecutorApprovalBridge::new(
            self.approvals.clone(),
            self.db.clone(),
            self.notifications.clone(),
            process.id,
        );
        assert!(bridge.supports_interactive_approvals());
        let approval = bridge
            .create_tool_approval("synthetic-uncovered-deletion")
            .await
            .unwrap();
        assert!(
            tokio::time::timeout(
                std::time::Duration::from_millis(10),
                bridge.wait_tool_approval(&approval, CancellationToken::new())
            )
            .await
            .is_err(),
            "No automatic permission grant"
        );
        self.approvals
            .respond(
                &approval,
                utils::approvals::ApprovalResponse {
                    execution_process_id: process.id,
                    status: utils::approvals::ApprovalOutcome::Denied {
                        reason: Some("Synthetic denial".into()),
                    },
                },
            )
            .await
            .unwrap();
        self.launches.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }
}

async fn fixture() -> (tempfile::TempDir, FixtureDeployment, OwnerBinding, Request) {
    let dir = tempfile::tempdir().unwrap();
    let native_path = PathBuf::from(std::env::var_os("CODEX_HOME").expect("isolated child home"))
        .join("goals_1.sqlite");
    let native = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(&native_path)
                .create_if_missing(true),
        )
        .await
        .unwrap();
    sqlx::query("CREATE TABLE IF NOT EXISTS thread_goals(thread_id TEXT PRIMARY KEY,status TEXT)")
        .execute(&native)
        .await
        .unwrap();
    native.close().await;
    let pool = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(4)
        .connect_with(
            sqlx::sqlite::SqliteConnectOptions::new()
                .filename(dir.path().join("isolated.sqlite"))
                .create_if_missing(true)
                .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal),
        )
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let db = DBService { pool: pool.clone() };
    let mut config = Config::default();
    config.notifications.sound_enabled = false;
    config.notifications.push_enabled = false;
    let config = Arc::new(RwLock::new(config));
    let container = Arc::new(FixtureContainer {
        db: db.clone(),
        git: git::GitService::new(),
        stores: Arc::new(RwLock::new(HashMap::new())),
        notifications: NotificationService::new(config.clone()),
        approvals: Approvals::new(),
        launches: AtomicUsize::new(0),
        fail_spawn: std::sync::atomic::AtomicBool::new(false),
    });
    let deployment = FixtureDeployment {
        container,
        config,
        events: EventService::new(db, Arc::new(MsgStore::new()), Arc::new(RwLock::new(0))),
        queue: QueuedMessageService::new(),
    };
    tokio::fs::create_dir(dir.path().join("repo"))
        .await
        .unwrap();
    let w = Workspace::create(
        &pool,
        &CreateWorkspace {
            branch: "isolated-storage-route".into(),
            name: None,
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    Workspace::update_container_ref(&pool, w.id, dir.path().to_str().unwrap())
        .await
        .unwrap();
    let repo = Repo::find_or_create(&pool, &dir.path().join("repo"), "Synthetic repository")
        .await
        .unwrap();
    WorkspaceRepo::create_many(
        &pool,
        w.id,
        &[CreateWorkspaceRepo {
            repo_id: repo.id,
            target_branch: "fixture".into(),
        }],
    )
    .await
    .unwrap();
    let s = Session::create(
        &pool,
        &CreateSession {
            executor: Some("CODEX".into()),
            name: None,
        },
        Uuid::new_v4(),
        w.id,
    )
    .await
    .unwrap();
    let saved: ExecutorConfig = serde_json::from_value(serde_json::json!({"executor":"CODEX","variant":"DEFAULT","model_id":"synthetic-saved-model","reasoning_id":"synthetic-saved-effort","routing":{"mode":"shadow"}})).unwrap();
    let anchor = ExecutionProcess::create(
        &pool,
        &CreateExecutionProcess {
            session_id: s.id,
            executor_action: ExecutorAction::new(
                ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
                    prompt: "Existing synthetic owner".into(),
                    executor_config: saved.clone(),
                    working_dir: None,
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
    ExecutionProcess::update_completion(
        &pool,
        anchor.id,
        ExecutionProcessStatus::Completed,
        Some(0),
    )
    .await
    .unwrap();
    let turn = CodingAgentTurn::create(
        &pool,
        &CreateCodingAgentTurn {
            execution_process_id: anchor.id,
            prompt: Some("Existing synthetic owner".into()),
        },
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    sqlx::query("UPDATE coding_agent_turns SET agent_session_id='synthetic-existing-thread',summary='Verified synthetic final' WHERE id=?").bind(turn.id).execute(&pool).await.unwrap();
    let binding = OwnerBinding {
        workspace_id: w.id,
        session_id: s.id,
        executor_config: saved.clone(),
        max_validation_age_seconds: 60,
    };
    let intent = admission::Intent {
        workspace_id: w.id,
        session_id: s.id,
        incidents: vec![admission::Incident {
            incident_id: Uuid::new_v4(),
            filesystem_uuid: "synthetic-volume".into(),
            policy: "synthetic-pressure".into(),
            opened_at: chrono::Utc::now() - chrono::Duration::minutes(1),
        }],
        receipt_ref: "synthetic-only".into(),
        prompt: "Inspect verified synthetic pressure under existing cleanup and approval authority"
            .into(),
        executor_config_sha256: admission::fingerprint(&saved),
    };
    let request = Request {
        protocol: admission::PROTOCOL.into(),
        batch_id: Uuid::new_v4(),
        attempt_id: Uuid::new_v4(),
        intent_sha256: admission::fingerprint(&intent),
        validation: admission::Validation {
            observed_at: chrono::Utc::now(),
            eligible_incident_ids: intent.incidents.iter().map(|i| i.incident_id).collect(),
            evidence_sha256: "a".repeat(64),
        },
        intent,
    };
    (dir, deployment, binding, request)
}

#[tokio::test]
async fn native_route_duplicate_race_uses_saved_config_and_real_permission_bridge() {
    if !isolated(
        "native_route_duplicate_race_uses_saved_config_and_real_permission_bridge",
        false,
    ) {
        return;
    }
    let (_dir, d, b, r) = fixture().await;
    let (a, c) = tokio::join!(submit_bound(&d, &b, &r), submit_bound(&d, &b, &r));
    let (a, c) = (a.unwrap(), c.unwrap());
    assert_eq!(a.outcome, "accepted");
    assert_eq!(c.outcome, "accepted");
    assert_eq!(
        a.receipt.unwrap().execution_id,
        c.receipt.unwrap().execution_id
    );
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 1);
    assert!(!d.queue.has_queued(b.session_id));
}

#[tokio::test]
async fn native_route_user_work_and_owner_activity_win_without_queue_changes() {
    if !isolated(
        "native_route_user_work_and_owner_activity_win_without_queue_changes",
        false,
    ) {
        return;
    }
    let (_dir, d, b, r) = fixture().await;
    let data = DraftFollowUpData {
        message: "Existing user queued input".into(),
        executor_config: b.executor_config.clone(),
    };
    d.queue.queue_for_capacity(b.session_id, data);
    let queued = serde_json::to_value(d.queue.get_status(b.session_id)).unwrap();
    let result = submit_bound(&d, &b, &r).await.unwrap();
    assert_eq!(result.outcome, "deferred");
    assert!(result.no_admission);
    assert_eq!(
        queued,
        serde_json::to_value(d.queue.get_status(b.session_id)).unwrap()
    );
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn native_route_executor_failure_after_binding_remains_accepted_with_failed_status() {
    if !isolated(
        "native_route_executor_failure_after_binding_remains_accepted_with_failed_status",
        false,
    ) {
        return;
    }
    let (_dir, d, b, r) = fixture().await;
    d.container.fail_spawn.store(true, Ordering::SeqCst);
    let a = submit_bound(&d, &b, &r).await.unwrap();
    assert_eq!(a.outcome, "accepted");
    assert_eq!(a.execution_status.as_deref(), Some("failed"));
    assert!(!a.no_admission);
    assert!(a.receipt.unwrap().execution_id.is_some());
    assert!(!d.queue.has_queued(b.session_id));
}

#[tokio::test]
async fn native_route_selection_drift_is_definitely_rejected_before_binding() {
    if !isolated(
        "native_route_selection_drift_is_definitely_rejected_before_binding",
        false,
    ) {
        return;
    }
    let (_dir, d, mut b, mut r) = fixture().await;
    b.executor_config.reasoning_id = Some("changed-synthetic-effort".into());
    r.intent.executor_config_sha256 = admission::fingerprint(&b.executor_config);
    r.intent_sha256 = admission::fingerprint(&r.intent);
    let a = submit_bound(&d, &b, &r).await.unwrap();
    assert_eq!(a.outcome, "rejected");
    assert!(a.no_admission);
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 0);
}

// Keep every test child away from the live native home, controller, catalogue,
// telemetry and systemd. The production capacity gate itself runs unchanged.
fn isolated(name: &str, capacity_hold: bool) -> bool {
    if std::env::var("VK_STORAGE_TEST_CHILD").as_deref() == Ok(name) {
        return true;
    }
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("native");
    std::fs::create_dir(&home).unwrap();
    let bin = dir.path().join("bin");
    std::fs::create_dir(&bin).unwrap();
    std::fs::write(
        bin.join("systemctl"),
        if capacity_hold {
            "#!/bin/sh\nprintf 'synthetic-capacity-unit.service loaded active running\\n'\n"
        } else {
            "#!/bin/sh\nexit 0\n"
        },
    )
    .unwrap();
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(
            bin.join("systemctl"),
            std::fs::Permissions::from_mode(0o700),
        )
        .unwrap();
    }
    let output = std::process::Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            &format!(
                "{}::{name}",
                module_path!().split_once("::").expect("crate module").1
            ),
            "--nocapture",
            "--test-threads=1",
        ])
        .env("VK_STORAGE_TEST_CHILD", name)
        .env("CODEX_HOME", &home)
        .env("VK_STORAGE_ALERT_OWNER_FILE", dir.path().join("owner.json"))
        .env("XDG_DATA_HOME", dir.path().join("xdg"))
        .env("VK_DISABLE_CODEX_EXECUTIONS", "1")
        .env("VK_USE_SYSTEMD_RUN", "1")
        .env("VK_CODEX_MAX_ACTIVE_EXECUTIONS", "1")
        .env(
            "PATH",
            format!(
                "{}:{}",
                bin.display(),
                std::env::var("PATH").unwrap_or_default()
            ),
        )
        .env_remove("VK_CAPACITY_STATE_DIR")
        .env_remove("VK_AUTOMATIC_GITHUB_SYNC")
        .env_remove("VK_CODEX_ROUTING_MODULE")
        .env_remove("VK_CODEX_ROUTING_AVAILABILITY")
        .env_remove("VK_CODEX_ROUTING_TELEMETRY")
        .env_remove("VK_ROUTING_EVENTS_FILE")
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        String::from_utf8_lossy(&output.stdout).contains("1 passed"),
        "Child must execute the exact native test, not an empty filter: {}",
        String::from_utf8_lossy(&output.stdout)
    );
    false
}

#[tokio::test]
async fn native_capacity_hold_has_definite_no_admission_and_no_auto_queue() {
    if !isolated(
        "native_capacity_hold_has_definite_no_admission_and_no_auto_queue",
        true,
    ) {
        return;
    }
    let (_dir, d, b, r) = fixture().await;
    let a = submit_bound(&d, &b, &r).await.unwrap();
    assert_eq!(a.outcome, "deferred");
    assert_eq!(a.reason, "native_capacity_hold");
    assert!(a.no_admission);
    assert!(!a.automatic_launch_queued);
    assert!(!d.queue.has_queued(b.session_id));
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn actual_http_contract_replays_queries_cancels_and_reports_unknown_without_resend_authority()
{
    if !isolated(
        "actual_http_contract_replays_queries_cancels_and_reports_unknown_without_resend_authority",
        false,
    ) {
        return;
    }
    use tower::ServiceExt;
    let (_dir, d, b, r) = fixture().await;
    std::fs::write(
        std::env::var_os("VK_STORAGE_ALERT_OWNER_FILE").unwrap(),
        serde_json::to_vec(&b).unwrap(),
    )
    .unwrap();
    let app = super::router::<FixtureDeployment>().with_state(d.clone());
    let send = || {
        axum::http::Request::builder()
            .uri("/storage-alerts/batches")
            .method("POST")
            .header("Content-Type", "application/json")
            .body(axum::body::Body::from(serde_json::to_vec(&r).unwrap()))
            .unwrap()
    };
    let result = app.clone().oneshot(send()).await.unwrap();
    assert_eq!(result.status(), axum::http::StatusCode::OK);
    let a: serde_json::Value = serde_json::from_slice(
        &axum::body::to_bytes(result.into_body(), 65536)
            .await
            .unwrap(),
    )
    .unwrap();
    assert_eq!(a["protocol"], admission::PROTOCOL);
    assert_eq!(a["outcome"], "accepted");
    assert!(a["receipt"]["execution_id"].is_string());
    let result = app.clone().oneshot(send()).await.unwrap();
    let replay: serde_json::Value = serde_json::from_slice(
        &axum::body::to_bytes(result.into_body(), 65536)
            .await
            .unwrap(),
    )
    .unwrap();
    assert_eq!(replay["replay"], true);
    assert_eq!(
        a["receipt"]["execution_id"],
        replay["receipt"]["execution_id"]
    );
    for method in ["GET", "DELETE"] {
        let result = app
            .clone()
            .oneshot(
                axum::http::Request::builder()
                    .uri(format!(
                        "/storage-alerts/batches/{}?intent_sha256={}",
                        r.batch_id, r.intent_sha256
                    ))
                    .method(method)
                    .body(axum::body::Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(
            &axum::body::to_bytes(result.into_body(), 65536)
                .await
                .unwrap(),
        )
        .unwrap();
        assert_eq!(body["outcome"], "accepted");
        assert_eq!(body["no_admission"], false);
    }
    let result = app
        .oneshot(
            axum::http::Request::builder()
                .uri(format!(
                    "/storage-alerts/batches/{}?intent_sha256={}",
                    Uuid::new_v4(),
                    r.intent_sha256
                ))
                .body(axum::body::Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let missing: serde_json::Value = serde_json::from_slice(
        &axum::body::to_bytes(result.into_body(), 65536)
            .await
            .unwrap(),
    )
    .unwrap();
    assert_eq!(missing["outcome"], "uncertain");
    assert_eq!(missing["no_admission"], false);
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 1);
}

#[tokio::test]
async fn native_budget_hold_is_readonly_and_unrelated_nightly_goal_is_not_a_veto() {
    if !isolated(
        "native_budget_hold_is_readonly_and_unrelated_nightly_goal_is_not_a_veto",
        false,
    ) {
        return;
    }
    let (_dir, d, b, mut r) = fixture().await;
    let native = sqlx::sqlite::SqlitePoolOptions::new()
        .max_connections(1)
        .connect_with(sqlx::sqlite::SqliteConnectOptions::new().filename(
            PathBuf::from(std::env::var_os("CODEX_HOME").unwrap()).join("goals_1.sqlite"),
        ))
        .await
        .unwrap();
    sqlx::query("INSERT INTO thread_goals VALUES ('unrelated-nightly','active')")
        .execute(&native)
        .await
        .unwrap();
    for status in ["budgetLimited", "paused", "active", "blocked"] {
        sqlx::query("INSERT OR REPLACE INTO thread_goals VALUES ('synthetic-existing-thread',?)")
            .bind(status)
            .execute(&native)
            .await
            .unwrap();
        r.attempt_id = Uuid::new_v4();
        r.validation.observed_at = chrono::Utc::now();
        let a = submit_bound(&d, &b, &r).await.unwrap();
        assert_eq!(a.outcome, "deferred");
        assert!(a.no_admission);
        assert_eq!(a.reason, "native_goal_or_observation_hold");
        assert!(!d.queue.has_queued(b.session_id));
        let actual: String = sqlx::query_scalar(
            "SELECT status FROM thread_goals WHERE thread_id='synthetic-existing-thread'",
        )
        .fetch_one(&native)
        .await
        .unwrap();
        assert_eq!(actual, status);
    }
    sqlx::query("DELETE FROM thread_goals WHERE thread_id='synthetic-existing-thread'")
        .execute(&native)
        .await
        .unwrap();
    r.attempt_id = Uuid::new_v4();
    r.validation.observed_at = chrono::Utc::now();
    assert_eq!(submit_bound(&d, &b, &r).await.unwrap().outcome, "accepted");
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 1);
    let status: String =
        sqlx::query_scalar("SELECT status FROM thread_goals WHERE thread_id='unrelated-nightly'")
            .fetch_one(&native)
            .await
            .unwrap();
    assert_eq!(status, "active");
}

#[tokio::test]
async fn native_ordinary_user_followup_races_alert_and_is_preserved_by_normal_capacity_queue() {
    if !isolated(
        "native_ordinary_user_followup_races_alert_and_is_preserved_by_normal_capacity_queue",
        false,
    ) {
        return;
    }
    let (_dir, d, b, r) = fixture().await;
    let session = Session::find_by_id(&d.db().pool, b.session_id)
        .await
        .unwrap()
        .unwrap();
    let ordinary = services::services::admission::run(services::services::admission::owner(
        b.workspace_id,
        crate::routes::sessions::follow_up_admitted(
            axum::Extension(session),
            State(d.clone()),
            Json(crate::routes::sessions::CreateFollowUpAttempt {
                prompt: "Existing user's next instruction".into(),
                executor_config: b.executor_config.clone(),
                retry_process_id: None,
                force_when_dirty: None,
                perform_git_reset: None,
            }),
        ),
    ));
    let (alert, user) = tokio::join!(submit_bound(&d, &b, &r), ordinary);
    let alert = alert.unwrap();
    let user = user.unwrap().0;
    if alert.outcome == "accepted" {
        assert!(!user.is_success());
        let queued = d
            .queue
            .get_queued(b.session_id)
            .expect("User input was retained");
        let interrupted = CodingAgentTurn::find_interrupted_context_since_latest_success(
            &d.db().pool,
            b.session_id,
        )
        .await
        .unwrap();
        assert_eq!(interrupted.len(), 1);
        assert_eq!(
            interrupted[0].prompt.as_deref(),
            Some(r.intent.prompt.as_str())
        );
        let expected = CodingAgentTurn::prompt_with_interrupted_context(
            "Existing user's next instruction".into(),
            &interrupted,
        );
        assert_eq!(queued.data.message, expected);
        assert!(queued.data.message.starts_with("Context recovery:"));
        assert!(
            queued
                .data
                .message
                .ends_with("Current user prompt:\nExisting user's next instruction")
        );
        assert_eq!(queued.data.executor_config, b.executor_config);
    } else {
        assert_eq!(alert.outcome, "deferred");
        assert!(alert.no_admission);
        assert!(user.is_success());
    }
    assert_eq!(
        d.container.launches.load(Ordering::SeqCst),
        1,
        "Only one owner run"
    );
}

#[tokio::test]
async fn native_alert_recovers_interrupted_user_prompts_without_changing_intent_or_replay() {
    if !isolated(
        "native_alert_recovers_interrupted_user_prompts_without_changing_intent_or_replay",
        false,
    ) {
        return;
    }
    let (_dir, d, b, r) = fixture().await;
    let now = chrono::Utc::now();
    // Make ordering deterministic even on a coarse SQLite clock.
    sqlx::query("UPDATE execution_processes SET created_at=? WHERE session_id=?")
        .bind(now - chrono::Duration::minutes(3))
        .bind(b.session_id)
        .execute(&d.db().pool)
        .await
        .unwrap();
    for (index, status, prompt, summary) in [
        (
            0,
            ExecutionProcessStatus::Failed,
            "Preserve the user's earlier work",
            Some("Partial verification evidence"),
        ),
        (
            1,
            ExecutionProcessStatus::Killed,
            "Continue the user's pending inspection",
            None,
        ),
    ] {
        let process = ExecutionProcess::create(
            &d.db().pool,
            &CreateExecutionProcess {
                session_id: b.session_id,
                executor_action: ExecutorAction::new(
                    ExecutorActionType::CodingAgentFollowUpRequest(CodingAgentFollowUpRequest {
                        capacity: None,
                        prompt: prompt.into(),
                        session_id: "synthetic-existing-thread".into(),
                        reset_to_message_id: None,
                        executor_config: b.executor_config.clone(),
                        working_dir: None,
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
        ExecutionProcess::update_completion(&d.db().pool, process.id, status, Some(1))
            .await
            .unwrap();
        sqlx::query("UPDATE execution_processes SET created_at=? WHERE id=?")
            .bind(now - chrono::Duration::minutes(2 - index))
            .bind(process.id)
            .execute(&d.db().pool)
            .await
            .unwrap();
        let turn = CodingAgentTurn::create(
            &d.db().pool,
            &CreateCodingAgentTurn {
                execution_process_id: process.id,
                prompt: Some(prompt.into()),
            },
            Uuid::new_v4(),
        )
        .await
        .unwrap();
        sqlx::query("UPDATE coding_agent_turns SET summary=? WHERE id=?")
            .bind(summary)
            .bind(turn.id)
            .execute(&d.db().pool)
            .await
            .unwrap();
    }
    let interrupted =
        CodingAgentTurn::find_interrupted_context_since_latest_success(&d.db().pool, b.session_id)
            .await
            .unwrap();
    assert_eq!(interrupted.len(), 2);
    let expected =
        CodingAgentTurn::prompt_with_interrupted_context(r.intent.prompt.clone(), &interrupted);
    let admitted = submit_bound(&d, &b, &r).await.unwrap();
    assert_eq!(admitted.outcome, "accepted");
    let receipt = admitted.receipt.unwrap();
    assert_eq!(receipt.intent_sha256, admission::fingerprint(&r.intent));
    let process = ExecutionProcess::find_by_id(&d.db().pool, receipt.execution_id.unwrap())
        .await
        .unwrap()
        .unwrap();
    let ExecutorActionType::CodingAgentFollowUpRequest(action) =
        process.executor_action().unwrap().typ()
    else {
        panic!("Must persist the ordinary native continuation");
    };
    assert_eq!(action.prompt, expected);
    assert!(action.prompt.contains("Preserve the user's earlier work"));
    assert!(action.prompt.contains("Partial verification evidence"));
    assert!(
        action
            .prompt
            .contains("Continue the user's pending inspection")
    );
    assert!(
        action
            .prompt
            .ends_with(&format!("Current user prompt:\n{}", r.intent.prompt))
    );
    assert!(!action.prompt.contains("Existing synthetic owner"));
    assert_eq!(action.executor_config, b.executor_config);
    let turn = CodingAgentTurn::find_by_execution_process_id(&d.db().pool, process.id)
        .await
        .unwrap()
        .unwrap();
    assert_eq!(turn.prompt.as_deref(), Some(expected.as_str()));
    let replay = submit_bound(&d, &b, &r).await.unwrap();
    assert!(replay.replay);
    assert_eq!(replay.receipt.unwrap().execution_id, Some(process.id));
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 1);
    assert!(!d.queue.has_queued(b.session_id));
}
