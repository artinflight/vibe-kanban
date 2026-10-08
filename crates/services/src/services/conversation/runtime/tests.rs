use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use async_trait::async_trait;
use db::models::conversation::{
    AcceptConversationMessage, ConversationInputOrigin, ConversationScope, ConversationStore,
};
use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions};
use uuid::Uuid;

use super::*;
use crate::services::conversation::model::*;

async fn database(path: &std::path::Path) -> SqlitePool {
    let pool = SqlitePoolOptions::new()
        .max_connections(4)
        .connect_with(
            SqliteConnectOptions::new()
                .filename(path)
                .create_if_missing(true)
                .journal_mode(SqliteJournalMode::Wal)
                .busy_timeout(Duration::from_secs(5)),
        )
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    pool
}
async fn store(pool: &SqlitePool) -> ConversationStore {
    ConversationStore::new(
        pool.clone(),
        ConversationScope::local_operator(pool).await.unwrap(),
    )
}
fn input(body: &str) -> AcceptConversationMessage {
    AcceptConversationMessage {
        client_message_id: Uuid::new_v4(),
        body: body.into(),
        origin: ConversationInputOrigin::Typed,
        reply_to_id: None,
    }
}
async fn wait_status(store: &ConversationStore, id: Uuid, run: Uuid, status: &str) {
    tokio::time::timeout(Duration::from_secs(5), async {
        loop {
            if store.run(id, run).await.unwrap().status == status {
                break;
            }
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .expect("run did not reach expected durable status");
}
async fn stopped(runtime: &SupervisorRuntime) {
    tokio::time::timeout(Duration::from_secs(5), async {
        while runtime.0.task.as_ref().is_some_and(|t| !t.is_finished()) {
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .unwrap();
    assert!(!runtime.accepting_messages());
}
#[derive(Default)]
struct ReplyModel {
    calls: AtomicUsize,
}
#[async_trait]
impl ConversationModel for ReplyModel {
    fn identity(&self) -> ModelIdentity {
        ModelIdentity {
            provider: "fixture".into(),
            model: "runtime".into(),
        }
    }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        Ok(ModelResponse {
            step: ModelStep::Reply {
                text: format!("Reply to {}", request.input.body),
                evidence_ids: vec![],
            },
            usage: ModelUsage::default(),
            continuation: ModelContinuation::default(),
        })
    }
}

#[tokio::test]
async fn startup_resumes_durable_pending_work_once_across_two_consumers_and_preserves_cancelled_work()
 {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("runtime.sqlite");
    let pool = database(&path).await;
    let first_store = store(&pool).await;
    let id = first_store.resolve().await.unwrap().id;
    let first = first_store.accept(id, &input("first")).await.unwrap();
    let second = first_store.accept(id, &input("second")).await.unwrap();
    let cancelled = first_store.accept(id, &input("cancelled")).await.unwrap();
    first_store.cancel(id, cancelled.run.id).await.unwrap();
    drop(first_store);
    pool.close().await;
    let pool = database(&path).await;
    let store = store(&pool).await;
    let model = Arc::new(ReplyModel::default());
    let stop = CancellationToken::new();
    let a = SupervisorRuntime::start(pool.clone(), model.clone(), stop.child_token())
        .await
        .unwrap();
    let b = SupervisorRuntime::start(pool.clone(), model.clone(), stop.child_token())
        .await
        .unwrap();
    wait_status(&store, id, second.run.id, "completed").await;
    assert_eq!(
        store.run(id, first.run.id).await.unwrap().status,
        "completed"
    );
    assert_eq!(
        store.run(id, cancelled.run.id).await.unwrap().status,
        "cancelled"
    );
    assert_eq!(model.calls.load(Ordering::SeqCst), 2);
    assert_eq!(
        store
            .messages(id, None, 50)
            .await
            .unwrap()
            .iter()
            .filter(|m| m.role == "assistant")
            .count(),
        2
    );
    stop.cancel();
    stopped(&a).await;
    stopped(&b).await;
}

struct AuthFailure {
    calls: AtomicUsize,
}
#[async_trait]
impl ConversationModel for AuthFailure {
    fn identity(&self) -> ModelIdentity {
        ModelIdentity {
            provider: "fixture".into(),
            model: "auth".into(),
        }
    }
    async fn next(&self, _request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        Err(ModelError::Authentication)
    }
}
#[tokio::test]
async fn rejected_credentials_stop_acceptance_and_restart_does_not_retry_the_failed_turn() {
    let dir = tempfile::tempdir().unwrap();
    let pool = database(&dir.path().join("auth.sqlite")).await;
    let store = store(&pool).await;
    let id = store.resolve().await.unwrap().id;
    let original = input("first");
    let first = store.accept(id, &original).await.unwrap();
    let second = store.accept(id, &input("pending")).await.unwrap();
    let model = Arc::new(AuthFailure {
        calls: AtomicUsize::new(0),
    });
    let runtime = SupervisorRuntime::start(pool.clone(), model.clone(), CancellationToken::new())
        .await
        .unwrap();
    wait_status(&store, id, first.run.id, "failed").await;
    stopped(&runtime).await;
    assert_eq!(
        store.run(id, first.run.id).await.unwrap().error.as_deref(),
        Some("model_authentication_failed")
    );
    assert_eq!(
        store.run(id, second.run.id).await.unwrap().status,
        "pending"
    );
    assert_eq!(model.calls.load(Ordering::SeqCst), 1);
    assert!(matches!(
        store
            .accept_if_available(id, &input("new"), runtime.accepting_messages())
            .await,
        Err(ConversationError::WorkerUnavailable)
    ));
    assert_eq!(
        store
            .accept_if_available(id, &original, false)
            .await
            .unwrap()
            .run
            .id,
        first.run.id
    );
    let good = Arc::new(ReplyModel::default());
    let stop = CancellationToken::new();
    let repaired = SupervisorRuntime::start(pool.clone(), good.clone(), stop.clone())
        .await
        .unwrap();
    wait_status(&store, id, second.run.id, "completed").await;
    assert_eq!(good.calls.load(Ordering::SeqCst), 1);
    assert_eq!(store.run(id, first.run.id).await.unwrap().status, "failed");
    stop.cancel();
    stopped(&repaired).await;
}

struct BlockingModel {
    entered: Notify,
    dropped: Arc<AtomicBool>,
}
struct RequestGuard(Arc<AtomicBool>);
impl Drop for RequestGuard {
    fn drop(&mut self) {
        self.0.store(true, Ordering::SeqCst);
    }
}
#[async_trait]
impl ConversationModel for BlockingModel {
    fn identity(&self) -> ModelIdentity {
        ModelIdentity {
            provider: "fixture".into(),
            model: "blocked".into(),
        }
    }
    async fn next(&self, _request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        let _guard = RequestGuard(self.dropped.clone());
        self.entered.notify_one();
        std::future::pending().await
    }
}

#[tokio::test]
async fn shutdown_drops_active_transport_and_records_failure_without_an_assistant_reply() {
    let dir = tempfile::tempdir().unwrap();
    let pool = database(&dir.path().join("shutdown.sqlite")).await;
    let store = store(&pool).await;
    let id = store.resolve().await.unwrap().id;
    let accepted = store.accept(id, &input("wait")).await.unwrap();
    let model = Arc::new(BlockingModel {
        entered: Notify::new(),
        dropped: Arc::new(AtomicBool::new(false)),
    });
    let stop = CancellationToken::new();
    let runtime = SupervisorRuntime::start(pool.clone(), model.clone(), stop.clone())
        .await
        .unwrap();
    tokio::time::timeout(Duration::from_secs(5), model.entered.notified())
        .await
        .unwrap();
    stop.cancel();
    stopped(&runtime).await;
    assert!(model.dropped.load(Ordering::SeqCst));
    let run = store.run(id, accepted.run.id).await.unwrap();
    assert_eq!(run.status, "failed");
    assert_eq!(run.error.as_deref(), Some("worker_shutdown"));
    assert_eq!(store.messages(id, None, 50).await.unwrap().len(), 1);
}

#[tokio::test]
async fn deployment_drop_aborts_transport_and_restart_fences_expired_work_without_resending_it() {
    let dir = tempfile::tempdir().unwrap();
    let pool = database(&dir.path().join("drop.sqlite")).await;
    let store = store(&pool).await;
    let id = store.resolve().await.unwrap().id;
    let accepted = store.accept(id, &input("abandoned")).await.unwrap();
    let model = Arc::new(BlockingModel {
        entered: Notify::new(),
        dropped: Arc::new(AtomicBool::new(false)),
    });
    let runtime = SupervisorRuntime::start(pool.clone(), model.clone(), CancellationToken::new())
        .await
        .unwrap();
    tokio::time::timeout(Duration::from_secs(5), model.entered.notified())
        .await
        .unwrap();
    drop(runtime);
    tokio::time::timeout(Duration::from_secs(5), async {
        while !model.dropped.load(Ordering::SeqCst) {
            tokio::task::yield_now().await;
        }
    })
    .await
    .unwrap();
    sqlx::query("UPDATE conversation_runs SET lease_until=unixepoch()-1 WHERE id=?")
        .bind(accepted.run.id)
        .execute(&pool)
        .await
        .unwrap();
    let next = store.accept(id, &input("after restart")).await.unwrap();
    let good = Arc::new(ReplyModel::default());
    let stop = CancellationToken::new();
    let runtime = SupervisorRuntime::start(pool.clone(), good.clone(), stop.clone())
        .await
        .unwrap();
    wait_status(&store, id, next.run.id, "completed").await;
    assert_eq!(
        store.run(id, accepted.run.id).await.unwrap().status,
        "interrupted"
    );
    assert_eq!(good.calls.load(Ordering::SeqCst), 1);
    stop.cancel();
    stopped(&runtime).await;
}
