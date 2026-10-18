//! Shared serialization for ordinary input and bounded worker admission.
use std::{
    collections::HashMap,
    future::Future,
    sync::{Arc, OnceLock, Weak},
};

use tokio::sync::Mutex;

static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
tokio::task_local! { static HELD: bool; }
tokio::task_local! { static OWNER: uuid::Uuid; }
type OwnerLocks = std::sync::Mutex<HashMap<uuid::Uuid, Weak<Mutex<()>>>>;
static OWNERS: OnceLock<OwnerLocks> = OnceLock::new();

/// Keep the idle check, queue mutation and launch indivisible for one workspace.
/// Unrelated owners retain their ordinary concurrent launch behavior.
pub async fn owner<T>(id: uuid::Uuid, work: impl Future<Output = T>) -> T {
    if OWNER.try_with(|current| *current == id).unwrap_or(false) {
        return work.await;
    }
    let lock = {
        let mut locks = OWNERS
            .get_or_init(Default::default)
            .lock()
            .expect("owner locks");
        locks.retain(|_, value| value.strong_count() > 0);
        let lock = locks
            .get(&id)
            .and_then(Weak::upgrade)
            .unwrap_or_else(|| Arc::new(Mutex::new(())));
        locks.insert(id, Arc::downgrade(&lock));
        lock
    };
    let _guard = lock.lock().await;
    OWNER.scope(id, work).await
}

pub async fn run<T>(work: impl Future<Output = T>) -> T {
    if automatic_git_sync() {
        return locked(work).await;
    }
    if super::original_worker::current().is_none() {
        return work.await;
    }
    if let Some(ledger) = super::original_worker::current()
        && matches!(ledger.terminal().await, Ok(true))
    {
        return work.await;
    }
    locked(work).await
}

/// The checkpoint worker shares normal input/launch serialization. Publication
/// policy is a separate setting; enabling scheduling does not authorize files.
pub fn automatic_git_sync() -> bool {
    std::env::var("VK_AUTOMATIC_GITHUB_SYNC").is_ok_and(|value| value == "1")
}

pub async fn locked<T>(work: impl Future<Output = T>) -> T {
    if HELD.try_with(|v| *v).unwrap_or(false) {
        return work.await;
    }
    let _guard = LOCK.get_or_init(|| Mutex::new(())).lock().await;
    HELD.scope(true, work).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn default_off_unrelated_starts_do_not_wait_for_slow_spawn() {
        assert!(crate::services::original_worker::current().is_none());
        let barrier = std::sync::Arc::new(tokio::sync::Barrier::new(2));
        tokio::time::timeout(std::time::Duration::from_secs(2), async {
            tokio::join!(
                run(async {
                    barrier.wait().await;
                }),
                run(async {
                    barrier.wait().await;
                })
            );
        })
        .await
        .expect("default-off starts must overlap");
    }
}
