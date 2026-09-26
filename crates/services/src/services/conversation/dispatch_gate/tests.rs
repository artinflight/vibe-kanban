use std::sync::{
    Mutex,
    atomic::{AtomicBool, Ordering},
};

use db::models::scratch::DraftFollowUpData;
use executors::{
    actions::{
        ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
    },
    executors::BaseCodingAgent,
    profile::ExecutorConfig,
};
use sqlx::sqlite::SqlitePoolOptions;

use super::*;

struct State {
    approval: AtomicBool,
    capacity: AtomicBool,
    goal: Mutex<GoalMessageAdmission>,
    inspected: Mutex<Vec<Uuid>>,
}
#[async_trait]
impl RuntimeState for State {
    fn approvals(&self, ids: &[Uuid]) -> HashSet<Uuid> {
        if self.approval.load(Ordering::SeqCst) {
            ids.iter().copied().collect()
        } else {
            HashSet::new()
        }
    }
    async fn capacity_managed(&self, _: Uuid) -> Result<bool, DispatchBlock> {
        Ok(self.capacity.load(Ordering::SeqCst))
    }
    async fn goal(&self, process: Uuid) -> Result<GoalMessageAdmission, DispatchBlock> {
        self.inspected.lock().unwrap().push(process);
        Ok(*self.goal.lock().unwrap())
    }
}
async fn fixture() -> (DispatchGate, Arc<State>, AgentDelivery, Uuid) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let (workspace, session, process) = (Uuid::new_v4(), Uuid::new_v4(), Uuid::new_v4());
    sqlx::query("INSERT INTO workspaces(id,branch) VALUES (?,'test')")
        .bind(workspace)
        .execute(&pool)
        .await
        .unwrap();
    // Legacy sessions may have no executor column; the frozen configuration owns it.
    sqlx::query("INSERT INTO sessions(id,workspace_id) VALUES (?,?)")
        .bind(session)
        .bind(workspace)
        .execute(&pool)
        .await
        .unwrap();
    let config = ExecutorConfig::new(BaseCodingAgent::Codex);
    let action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: "raw original".into(),
            executor_config: config.clone(),
            working_dir: None,
        }),
        None,
    );
    sqlx::query("INSERT INTO execution_processes(id,session_id,executor_action,run_reason,status) VALUES (?,?,?,'codingagent','running')").bind(process).bind(session).bind(sqlx::types::Json(action)).execute(&pool).await.unwrap();
    let mut deliveries = AgentDelivery::enqueue(
        &pool,
        session,
        DraftFollowUpData {
            message: "requested instruction".into(),
            executor_config: config,
        },
        false,
        Uuid::new_v4(),
    )
    .await
    .unwrap();
    let mut delivery = deliveries.remove(0);
    delivery.source_kind = "supervisor".into();
    let state = Arc::new(State {
        approval: AtomicBool::new(false),
        capacity: AtomicBool::new(false),
        goal: Mutex::new(GoalMessageAdmission::Allowed),
        inspected: Mutex::new(vec![]),
    });
    (
        DispatchGate {
            pool,
            runtime: state.clone(),
        },
        state,
        delivery,
        process,
    )
}

#[tokio::test]
async fn approvals_and_capacity_precede_goal_inspection() {
    let (gate, state, delivery, _) = fixture().await;
    state.approval.store(true, Ordering::SeqCst);
    state.capacity.store(true, Ordering::SeqCst);
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::PendingApproval)
    );
    state.approval.store(false, Ordering::SeqCst);
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::CapacityManaged)
    );
    assert!(state.inspected.lock().unwrap().is_empty());
    state.capacity.store(false, Ordering::SeqCst);
    assert_eq!(gate.delivery(&delivery).await, Ok(()));
}

#[tokio::test]
async fn live_goal_is_rechecked_and_null_legacy_executor_does_not_bypass_it() {
    let (gate, state, delivery, process) = fixture().await;
    assert_eq!(gate.delivery(&delivery).await, Ok(()));
    *state.goal.lock().unwrap() = GoalMessageAdmission::Paused;
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::GoalPaused)
    );
    *state.goal.lock().unwrap() = GoalMessageAdmission::Unavailable;
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::GoalUnavailable)
    );
    assert_eq!(*state.inspected.lock().unwrap(), vec![process; 3]);
}

#[tokio::test]
async fn pending_approval_in_another_session_of_workspace_blocks_instruction() {
    let (gate, state, delivery, process) = fixture().await;
    let session = Uuid::new_v4();
    sqlx::query("INSERT INTO sessions(id,workspace_id) VALUES (?,?)")
        .bind(session)
        .bind(delivery.workspace_id)
        .execute(&gate.pool)
        .await
        .unwrap();
    sqlx::query("UPDATE execution_processes SET session_id=? WHERE id=?")
        .bind(session)
        .bind(process)
        .execute(&gate.pool)
        .await
        .unwrap();
    state.approval.store(true, Ordering::SeqCst);
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::PendingApproval)
    );
}

#[tokio::test]
async fn inactive_or_newly_correlated_session_defers_native_read_to_executor_before_resume() {
    let (gate, state, mut delivery, process) = fixture().await;
    *state.goal.lock().unwrap() = GoalMessageAdmission::Unavailable;
    delivery.execution_process_id = Some(process);
    assert_eq!(gate.delivery(&delivery).await, Ok(()));
    delivery.execution_process_id = None;
    sqlx::query("UPDATE execution_processes SET status='completed' WHERE id=?")
        .bind(process)
        .execute(&gate.pool)
        .await
        .unwrap();
    assert_eq!(gate.delivery(&delivery).await, Ok(()));
    assert!(state.inspected.lock().unwrap().is_empty());
}

#[tokio::test]
async fn workspace_lifecycle_and_session_identity_are_checked_again() {
    let (gate, _, mut delivery, _) = fixture().await;
    sqlx::query("UPDATE workspaces SET archived=1 WHERE id=?")
        .bind(delivery.workspace_id)
        .execute(&gate.pool)
        .await
        .unwrap();
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::TargetUnavailable)
    );
    sqlx::query("UPDATE workspaces SET archived=0,worktree_deleted=1 WHERE id=?")
        .bind(delivery.workspace_id)
        .execute(&gate.pool)
        .await
        .unwrap();
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::TargetUnavailable)
    );
    delivery.workspace_id = Uuid::new_v4();
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::TargetUnavailable)
    );
}

#[tokio::test]
async fn ordinary_direct_delivery_has_no_supervisor_gate_dependency() {
    let (gate, state, mut delivery, _) = fixture().await;
    state.approval.store(true, Ordering::SeqCst);
    state.capacity.store(true, Ordering::SeqCst);
    *state.goal.lock().unwrap() = GoalMessageAdmission::Paused;
    delivery.source_kind = "session".into();
    assert_eq!(gate.delivery(&delivery).await, Ok(()));
    assert!(state.inspected.lock().unwrap().is_empty());
}

#[tokio::test]
async fn steering_checks_its_correlated_process_and_rejects_session_control_commands() {
    let (gate, state, mut delivery, process) = fixture().await;
    delivery.delivery_mode = "steer".into();
    delivery.execution_process_id = Some(process);
    *state.goal.lock().unwrap() = GoalMessageAdmission::Paused;
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::GoalPaused)
    );
    *state.goal.lock().unwrap() = GoalMessageAdmission::Allowed;
    delivery.data.message = "/goal resume".into();
    assert_eq!(
        gate.delivery(&delivery).await,
        Err(DispatchBlock::SessionControl)
    );
}
