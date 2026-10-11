//! Shared serialization for ordinary input and bounded worker admission.
use std::{future::Future, sync::OnceLock};

use tokio::sync::Mutex;

static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
tokio::task_local! { static HELD: bool; }

pub async fn run<T>(work: impl Future<Output = T>) -> T {
    if super::original_worker::current().is_none() {
        return work.await;
    }
    locked(work).await
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
