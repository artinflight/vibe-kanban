//! Live runtime gates for supervisor-origin instructions only. They do not grant
//! executor approvals, activate goals, or replace ordinary workspace behavior.
use std::{collections::HashSet, sync::Arc};

use async_trait::async_trait;
use db::models::{
    agent_delivery::AgentDelivery, execution_process::ExecutionProcess, session::Session,
};
use executors::executors::codex::client::{AppServerClient, GoalMessageAdmission};
use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use uuid::Uuid;

use crate::services::approvals::Approvals;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, thiserror::Error)]
#[serde(rename_all = "snake_case")]
pub enum DispatchBlock {
    #[error("supervisor_message_cannot_invoke_session_controls")]
    SessionControl,
    #[error("pending_executor_approval")]
    PendingApproval,
    #[error("native_goal_managed_by_capacity")]
    CapacityManaged,
    #[error("native_goal_paused")]
    GoalPaused,
    #[error("native_goal_state_unavailable")]
    GoalUnavailable,
    #[error("target_unavailable")]
    TargetUnavailable,
    #[error("runtime_state_unavailable")]
    RuntimeUnavailable,
}

#[async_trait]
pub trait RuntimeState: Send + Sync {
    fn approvals(&self, processes: &[Uuid]) -> HashSet<Uuid>;
    async fn capacity_managed(&self, session: Uuid) -> Result<bool, DispatchBlock>;
    async fn goal(&self, process: Uuid) -> Result<GoalMessageAdmission, DispatchBlock>;
}
struct LiveState {
    approvals: Approvals,
}
#[async_trait]
impl RuntimeState for LiveState {
    fn approvals(&self, processes: &[Uuid]) -> HashSet<Uuid> {
        self.approvals.get_pending_execution_process_ids(processes)
    }
    async fn capacity_managed(&self, session: Uuid) -> Result<bool, DispatchBlock> {
        let state = executors::capacity::controller::configured()
            .map_err(|_| DispatchBlock::RuntimeUnavailable)?;
        match state {
            Some(state) => Ok(state
                .lock()
                .await
                .state
                .goals
                .get(&session)
                .is_some_and(|goal| goal.eligible || goal.grant.is_some())),
            None => Ok(false),
        }
    }
    async fn goal(&self, process: Uuid) -> Result<GoalMessageAdmission, DispatchBlock> {
        AppServerClient::execution_goal_admission(process)
            .await
            .map_err(|_| DispatchBlock::GoalUnavailable)
    }
}

#[derive(Clone)]
pub struct DispatchGate {
    pub(super) pool: SqlitePool,
    pub(super) runtime: Arc<dyn RuntimeState>,
}
impl DispatchGate {
    /// Runtime projection is supplied by deployment code, never request/model data.
    pub fn with_runtime(pool: SqlitePool, runtime: Arc<dyn RuntimeState>) -> Self {
        Self { pool, runtime }
    }

    pub fn local(pool: SqlitePool, approvals: Approvals) -> Self {
        Self {
            pool,
            runtime: Arc::new(LiveState { approvals }),
        }
    }
    pub async fn delivery(&self, delivery: &AgentDelivery) -> Result<(), DispatchBlock> {
        if delivery.source_kind != "supervisor" {
            return Ok(());
        }
        if executors::executors::codex::slash_commands::CodexSlashCommand::parse(
            &delivery.data.message,
        )
        .is_some()
        {
            return Err(DispatchBlock::SessionControl);
        }
        self.session(
            delivery.session_id,
            delivery.workspace_id,
            delivery.data.executor_config.executor,
            if delivery.delivery_mode == "queue" {
                delivery.execution_process_id
            } else {
                None
            },
        )
        .await
    }
    pub async fn message(
        &self,
        message: &db::models::conversation::actions::AgentMessage,
    ) -> Result<(), DispatchBlock> {
        if executors::executors::codex::slash_commands::CodexSlashCommand::parse(&message.message)
            .is_some()
        {
            return Err(DispatchBlock::SessionControl);
        }
        for target in &message.targets {
            self.session(
                target.session_id,
                target.workspace_id,
                target.executor_config.executor,
                None,
            )
            .await?;
        }
        Ok(())
    }
    async fn session(
        &self,
        session_id: Uuid,
        workspace_id: Uuid,
        executor: executors::executors::BaseCodingAgent,
        own_process: Option<Uuid>,
    ) -> Result<(), DispatchBlock> {
        let session = Session::find_by_id(&self.pool, session_id)
            .await
            .map_err(|_| DispatchBlock::RuntimeUnavailable)?
            .ok_or(DispatchBlock::TargetUnavailable)?;
        if session.workspace_id != workspace_id {
            return Err(DispatchBlock::TargetUnavailable);
        }
        let available:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspaces WHERE id=? AND archived=0 AND worktree_deleted=0)").bind(workspace_id).fetch_one(&self.pool).await.map_err(|_|DispatchBlock::RuntimeUnavailable)?;
        if !available {
            return Err(DispatchBlock::TargetUnavailable);
        }
        let processes:Vec<ExecutionProcess>=sqlx::query_as("SELECT p.* FROM execution_processes p JOIN sessions s ON s.id=p.session_id WHERE s.workspace_id=? AND p.status='running' AND p.dropped=0 AND p.run_reason!='devserver'")
            .bind(workspace_id).fetch_all(&self.pool).await.map_err(|_|DispatchBlock::RuntimeUnavailable)?;
        let ids: Vec<_> = processes.iter().map(|process| process.id).collect();
        if !self.runtime.approvals(&ids).is_empty() {
            return Err(DispatchBlock::PendingApproval);
        }
        if self.runtime.capacity_managed(session_id).await? {
            return Err(DispatchBlock::CapacityManaged);
        }
        if executor == executors::executors::BaseCodingAgent::Codex {
            let process = processes.iter().find(|process| {
                process.session_id == session_id
                    && Some(process.id) != own_process
                    && process.run_reason
                        == db::models::execution_process::ExecutionProcessRunReason::CodingAgent
            });
            if let Some(process) = process {
                match self.runtime.goal(process.id).await? {
                    GoalMessageAdmission::Allowed => {}
                    GoalMessageAdmission::Paused => return Err(DispatchBlock::GoalPaused),
                    GoalMessageAdmission::Unavailable => {
                        return Err(DispatchBlock::GoalUnavailable);
                    }
                }
            }
            // Inactive sessions are checked by the same configured executor's
            // native thread/goal/get before thread/resume. A local progress file
            // cannot establish whether a native goal is paused or even exists.
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests;
