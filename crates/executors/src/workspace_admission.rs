//! Shared native owner serialization and durable controlled-job lifetime leases.
//! A lease is committed before child work; dropping a future never certifies exit.
use std::{
    collections::HashMap,
    future::Future,
    sync::{Arc, OnceLock, Weak},
};

use sqlx::SqlitePool;
use tokio::sync::Mutex;
use uuid::Uuid;

type OwnerLocks = std::sync::Mutex<HashMap<Uuid, Weak<Mutex<()>>>>;
static OWNERS: OnceLock<OwnerLocks> = OnceLock::new();
tokio::task_local! { static OWNER: Uuid; }
// Only runtime-confirmed child turns with a live lease object count as positive
// activity. Drop/restart removes this projection, leaving the durable unknown
// lifetime fence intact. This is neither a queue nor a second job launcher.
static RUNNING_JOBS: OnceLock<std::sync::Mutex<HashMap<Uuid, Uuid>>> = OnceLock::new();
pub fn running_jobs(workspace: Uuid) -> Result<bool, String> {
    let jobs = RUNNING_JOBS
        .get_or_init(Default::default)
        .lock()
        .map_err(|_| "Job activity inventory unavailable")?;
    Ok(jobs.values().any(|owner| *owner == workspace))
}

pub async fn owner<T>(id: Uuid, work: impl Future<Output = T>) -> T {
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

#[derive(Clone, Debug)]
pub struct JobAdmission {
    pub pool: SqlitePool,
    pub workspace: Uuid,
    pub session: Uuid,
    pub execution: Uuid,
}

#[derive(Debug)]
pub struct JobLease {
    pool: SqlitePool,
    id: Uuid,
    workspace: Uuid,
}
impl Drop for JobLease {
    fn drop(&mut self) {
        if let Ok(mut jobs) = RUNNING_JOBS.get_or_init(Default::default).lock() {
            jobs.remove(&self.id);
        }
    }
}
impl JobAdmission {
    pub async fn reserve(&self) -> Result<JobLease, String> {
        owner(self.workspace,async {
            let mut tx=self.pool.begin_with("BEGIN IMMEDIATE").await.map_err(|e|e.to_string())?;
            // The parent must still own a running native execution. Late tools,
            // resumed stale clients and handlers after parent exit have no authority.
            let parent:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.id=? AND s.id=? AND s.workspace_id=? AND e.status='running' AND e.run_reason='codingagent')")
                .bind(self.execution).bind(self.session).bind(self.workspace).fetch_one(&mut *tx).await.map_err(|e|e.to_string())?;
            let reserved:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM storage_alert_batches b JOIN storage_alert_attempts a ON a.attempt_id=b.latest_attempt_id WHERE b.workspace_id=? AND a.candidate_execution_id != ? AND (a.state='in_flight' OR (a.state='accepted' AND (NOT EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=a.execution_id) OR EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=a.execution_id AND e.status='running')))))")
                .bind(self.workspace).bind(self.execution).fetch_one(&mut *tx).await.map_err(|e|e.to_string())?;
            let count:i64=sqlx::query_scalar("SELECT count(*) FROM watcher_job_leases WHERE workspace_id=?")
                .bind(self.workspace).fetch_one(&mut *tx).await.map_err(|e|e.to_string())?;
            if !parent || reserved || count>=4096 {return Err("Native job admission held: parent, watcher reservation or bounded lease quota".into());}
            let id=Uuid::new_v4();
            sqlx::query("INSERT INTO watcher_job_leases(id,workspace_id,session_id,execution_id) VALUES (?,?,?,?)")
                .bind(id).bind(self.workspace).bind(self.session).bind(self.execution).execute(&mut *tx).await.map_err(|e|e.to_string())?;
            tx.commit().await.map_err(|e|e.to_string())?;
            Ok(JobLease {pool:self.pool.clone(),id,workspace:self.workspace})
        }).await
    }
}
impl JobLease {
    /// Called only after the existing producer binds a real native thread/turn
    /// acknowledgment and saves its journal. A reservation alone is not activity.
    pub fn mark_running(&self) -> Result<(), String> {
        RUNNING_JOBS
            .get_or_init(Default::default)
            .lock()
            .map_err(|_| "Job activity inventory unavailable")?
            .insert(self.id, self.workspace);
        Ok(())
    }
    /// Only a confirmed terminal child result (or refusal before inference) may
    /// close this lease. Cancellation requests, timeout and Drop leave it open.
    pub async fn close(self) -> Result<(), String> {
        sqlx::query("UPDATE watcher_job_leases SET closed_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=? AND closed_at IS NULL")
            .bind(self.id).execute(&self.pool).await.map_err(|e|e.to_string())?;
        Ok(())
    }
}
