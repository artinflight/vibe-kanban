//! Shared serialization for ordinary input and bounded worker admission.
use std::{future::Future, sync::OnceLock};

use tokio::sync::Mutex;

static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
tokio::task_local! { static HELD: bool; }

pub async fn run<T>(work: impl Future<Output = T>) -> T {
    if HELD.try_with(|v| *v).unwrap_or(false) {
        return work.await;
    }
    let _guard = LOCK.get_or_init(|| Mutex::new(())).lock().await;
    HELD.scope(true, work).await
}
