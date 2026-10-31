//! Shared serialization for ordinary input and bounded worker admission.
use std::{future::Future, sync::OnceLock};

use tokio::sync::Mutex;
static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
tokio::task_local! { static HELD: bool; }

/// Same workspace lock for ordinary native input, watcher admission and child
/// producer authority. Unrelated workspaces remain concurrent.
pub async fn owner<T>(id: uuid::Uuid, work: impl Future<Output = T>) -> T {
    // Existing provider/fixed-baseline admission takes LOCK before the owner
    // lock. Keep that order even when automatic Git sync is disabled, so a
    // watcher cannot hold the owner lock while waiting for a provider holder.
    locked(executors::workspace_admission::owner(id, work)).await
}

pub async fn run<T>(work: impl Future<Output = T>) -> T {
    if automatic_git_sync() || super::fixed_baseline::configured() {
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

// Upgraded interactive writers outlive an HTTP response. Their read leases cover
// the complete PTY/SSH lifetime; fixed launch takes an exclusive lease without
// waiting for or killing any session. HTTP/background mutations use LOCK above.
// Existing PTY/embedded-SSH child teardown does not prove all descendants ended.
// Therefore this exceptional launch is refused after ANY interactive session
// was admitted in this process, even after disconnect. There is no clear API.
// A reviewed release must establish a fresh, drained process epoch; ordinary
// terminal/SSH operation is unchanged and no child is killed for admission.
static INTERACTIVE_EVER_ADMITTED: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
static INTERACTIVE: OnceLock<std::sync::Arc<tokio::sync::RwLock<()>>> = OnceLock::new();
fn interactive_lock() -> std::sync::Arc<tokio::sync::RwLock<()>> {
    INTERACTIVE
        .get_or_init(|| std::sync::Arc::new(tokio::sync::RwLock::new(())))
        .clone()
}
pub fn interactive_writer() -> Result<tokio::sync::OwnedRwLockReadGuard<()>, String> {
    let lease = interactive_lock()
        .try_read_owned()
        .map_err(|_| "fixed admission currently owns native writer custody".to_owned())?;
    INTERACTIVE_EVER_ADMITTED.store(true, std::sync::atomic::Ordering::SeqCst);
    Ok(lease)
}
pub fn fixed_writer_custody() -> Result<tokio::sync::OwnedRwLockWriteGuard<()>, String> {
    let lease = interactive_lock()
        .try_write_owned()
        .map_err(|_| "active PTY/SSH session prevents fixed admission".to_owned())?;
    if INTERACTIVE_EVER_ADMITTED.load(std::sync::atomic::Ordering::SeqCst) {
        return Err(
            "interactive child termination unproven in this process epoch; fixed admission held"
                .into(),
        );
    }
    Ok(lease)
}
#[cfg(test)]
mod writer_tests {
    use super::*;
    #[tokio::test]
    async fn interactive_and_fixed_leases_exclude_each_other() {
        let write = fixed_writer_custody().unwrap();
        assert!(interactive_writer().is_err());
        drop(write);
        let read = interactive_writer().unwrap();
        assert!(fixed_writer_custody().is_err());
        drop(read);
        // Disconnect is NOT proof that shell children stopped.
        assert!(fixed_writer_custody().is_err());
        assert!(interactive_writer().is_ok());
    }
}

#[cfg(test)]
mod combined_owner_tests {
    use super::*;
    #[tokio::test]
    async fn watcher_and_provider_paths_share_lock_order_and_reenter() {
        let id = uuid::Uuid::new_v4();
        tokio::time::timeout(std::time::Duration::from_secs(2), async {
            tokio::join!(
                owner(id, async { locked(owner(id, async { 1 })).await }),
                locked(owner(id, async { 2 }))
            );
        })
        .await
        .expect("combined admission must not deadlock");
    }
}
