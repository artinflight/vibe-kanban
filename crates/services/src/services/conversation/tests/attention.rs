use std::collections::HashSet;

use executors::executors::codex::client::GoalMessageAdmission;

use super::*;
use crate::services::conversation::dispatch_gate::{DispatchBlock, RuntimeState};

#[derive(Default)]
struct Runtime {
    pending: Mutex<HashSet<Uuid>>,
    paused: AtomicBool,
    unavailable: AtomicBool,
    inspected: Mutex<Vec<Uuid>>,
    finish_during_read: Option<SqlitePool>,
}
#[async_trait]
impl RuntimeState for Runtime {
    fn approvals(&self, ids: &[Uuid]) -> HashSet<Uuid> {
        self.pending
            .lock()
            .unwrap()
            .iter()
            .filter(|id| ids.contains(id))
            .copied()
            .collect()
    }
    async fn capacity_managed(&self, _: Uuid) -> Result<bool, DispatchBlock> {
        if self.unavailable.load(Ordering::SeqCst) {
            Err(DispatchBlock::RuntimeUnavailable)
        } else {
            Ok(false)
        }
    }
    async fn goal(&self, process: Uuid) -> Result<GoalMessageAdmission, DispatchBlock> {
        self.inspected.lock().unwrap().push(process);
        if let Some(pool) = &self.finish_during_read {
            sqlx::query("UPDATE execution_processes SET status='completed',exit_code=0 WHERE id=?")
                .bind(process)
                .execute(pool)
                .await
                .unwrap();
        }
        Ok(if self.unavailable.load(Ordering::SeqCst) {
            GoalMessageAdmission::Unavailable
        } else if self.paused.load(Ordering::SeqCst) {
            GoalMessageAdmission::Paused
        } else {
            GoalMessageAdmission::Allowed
        })
    }
}

async fn read(
    f: &Fixture,
    run: &ConversationRun,
    workspace_id: Option<Uuid>,
    offset: u32,
) -> Value {
    f.context
        .execute(
            run,
            &SupervisorTool::ListAttention {
                workspace_id,
                offset,
            },
        )
        .await
        .unwrap()["data"]
        .clone()
}
fn signals(data: &Value, session: Uuid) -> Vec<String> {
    data["items"]
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["session"]["session_id"] == session.to_string())
        .map(|item| {
            item["signals"]
                .as_array()
                .unwrap()
                .iter()
                .map(|s| s.as_str().unwrap().into())
                .collect()
        })
        .unwrap_or_default()
}

#[tokio::test]
async fn attention_separates_unread_results_failures_and_real_pending_responses() {
    let mut f = fixture().await;
    let state = Arc::new(Runtime::default());
    f.context.runtime = Some(state.clone());
    sqlx::query("UPDATE execution_processes SET exit_code=0 WHERE id=?")
        .bind(f.process)
        .execute(&f.pool)
        .await
        .unwrap();
    let second = Uuid::new_v4();
    let failed = Uuid::new_v4();
    let setup = Uuid::new_v4();
    sqlx::query("INSERT INTO sessions(id,workspace_id,name) VALUES (?,?,'second agent')")
        .bind(second)
        .bind(f.workspace)
        .execute(&f.pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO execution_processes(id,session_id,run_reason,executor_action,status,exit_code) VALUES (?,?,'codingagent','{}','failed',1)").bind(failed).bind(second).execute(&f.pool).await.unwrap();
    sqlx::query("INSERT INTO execution_processes(id,session_id,run_reason,executor_action,status) VALUES (?,?,'setupscript','{}','running')").bind(setup).bind(second).execute(&f.pool).await.unwrap();
    // A newer successful devserver cannot hide the failed coding process.
    sqlx::query("INSERT INTO execution_processes(id,session_id,run_reason,executor_action,status,exit_code,created_at) VALUES (?,?,'devserver','{}','completed',0,datetime('now','+1 minute'))").bind(Uuid::new_v4()).bind(second).execute(&f.pool).await.unwrap();
    state.pending.lock().unwrap().insert(setup);
    let run = lease(&f).await;
    let data = read(&f, &run, None, 0).await;
    assert_eq!(signals(&data, f.session), vec!["unread_completion"]);
    assert_eq!(
        signals(&data, second),
        vec!["execution_failed", "pending_executor_response"]
    );
    let item = data["items"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["session"]["session_id"] == second.to_string())
        .unwrap();
    assert_eq!(item["session"]["process_id"], failed.to_string());
    assert_eq!(
        item["pending_executor_response_process_ids"],
        json!([setup])
    );
    assert!(
        state.inspected.lock().unwrap().is_empty(),
        "do not resume/probe inactive native threads"
    );
    let before = Uuid::parse_str(data["evidence_id"].as_str().unwrap()).unwrap();
    let snapshot = f
        .context
        .store
        .evidence(f.id, before)
        .await
        .unwrap()
        .raw_report
        .unwrap();
    state.pending.lock().unwrap().clear();
    sqlx::query("UPDATE execution_processes SET status='completed',exit_code=0 WHERE id=?")
        .bind(failed)
        .execute(&f.pool)
        .await
        .unwrap();
    let current = read(&f, &run, None, 0).await;
    assert!(signals(&current, second).is_empty());
    assert_ne!(data["source_revision"], current["source_revision"]);
    assert_eq!(
        f.context
            .store
            .evidence(f.id, before)
            .await
            .unwrap()
            .raw_report
            .unwrap(),
        snapshot
    );
    let raw: (String, bool) =
        sqlx::query_as("SELECT summary,seen FROM coding_agent_turns WHERE execution_process_id=?")
            .bind(f.process)
            .fetch_one(&f.pool)
            .await
            .unwrap();
    assert_eq!(raw, (f.raw.clone(), false));
    for state in ["waiting_capacity", "unknown_delivery"] {
        sqlx::query("INSERT INTO agent_deliveries(id,source_kind,source_id,idempotency_key,session_id,workspace_id,data,state,requested_capacity,wait_for_capacity) VALUES (?,'session',?,?,?,?,'{}',?,0,1)")
            .bind(Uuid::new_v4()).bind(f.session).bind(Uuid::new_v4()).bind(f.session).bind(f.workspace).bind(state).execute(&f.pool).await.unwrap();
    }
    assert_eq!(
        signals(&read(&f, &run, None, 0).await, f.session),
        vec![
            "unread_completion",
            "waiting_capacity",
            "delivery_uncertain"
        ]
    );
}

#[tokio::test]
async fn attention_reports_unknown_runtime_and_paused_goals_without_inventing_a_question() {
    let mut f = fixture().await;
    sqlx::query("UPDATE execution_processes SET status='running' WHERE id=?")
        .bind(f.process)
        .execute(&f.pool)
        .await
        .unwrap();
    let run = lease(&f).await;
    let absent = read(&f, &run, Some(f.workspace), 0).await;
    assert_eq!(
        signals(&absent, f.session),
        vec!["runtime_state_incomplete"]
    );
    assert!(absent["items"][0]["pending_executor_response_process_ids"].is_null());
    assert_eq!(absent["coverage"]["runtime_connected"], false);
    let state = Arc::new(Runtime::default());
    state.paused.store(true, Ordering::SeqCst);
    f.context.runtime = Some(state.clone());
    let paused = read(&f, &run, None, 0).await;
    assert_eq!(signals(&paused, f.session), vec!["native_goal_paused"]);
    assert_eq!(*state.inspected.lock().unwrap(), vec![f.process]);
    state.unavailable.store(true, Ordering::SeqCst);
    assert_eq!(
        signals(&read(&f, &run, None, 0).await, f.session),
        vec!["runtime_state_incomplete"]
    );
    assert!(
        read(&f, &run, None, 0).await["coverage"]["not_inspected"]
            .as_array()
            .unwrap()
            .contains(&json!("report_semantics"))
    );
}

#[tokio::test]
async fn attention_pages_quiet_sessions_and_excludes_archived_or_deleted_workspaces() {
    let mut f = fixture().await;
    f.context.runtime = Some(Arc::new(Runtime::default()));
    let run = lease(&f).await;
    sqlx::query("UPDATE workspaces SET archived=1 WHERE id=?")
        .bind(f.workspace)
        .execute(&f.pool)
        .await
        .unwrap();
    let workspace = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces(id,branch) VALUES (?,'quiet')")
        .bind(workspace)
        .execute(&f.pool)
        .await
        .unwrap();
    for _ in 0..21 {
        sqlx::query("INSERT INTO sessions(id,workspace_id) VALUES (?,?)")
            .bind(Uuid::new_v4())
            .bind(workspace)
            .execute(&f.pool)
            .await
            .unwrap();
    }
    let first = read(&f, &run, None, 0).await;
    assert_eq!(first["items"], json!([]));
    assert_eq!(first["scanned_sessions"], 20);
    assert_eq!(first["next_offset"], 20);
    let last = read(&f, &run, None, 20).await;
    assert_eq!(last["scanned_sessions"], 1);
    assert!(last["next_offset"].is_null());
    assert_eq!(last["confirmations_included"], false);
    assert!(matches!(
        f.context
            .execute(
                &run,
                &SupervisorTool::ListAttention {
                    workspace_id: Some(f.workspace),
                    offset: 0
                }
            )
            .await,
        Err(ConversationError::NotFound)
    ));
    sqlx::query("UPDATE workspaces SET worktree_deleted=1 WHERE id=?")
        .bind(workspace)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(read(&f, &run, None, 0).await["scanned_sessions"], 0);
}

#[tokio::test]
async fn attention_filters_confirmation_scope_expiry_and_revised_or_cancelled_actions() {
    let f = fixture().await;
    let run = lease(&f).await;
    let input = f.context.store.run_input(&run).await.unwrap();
    let action = f
        .context
        .store
        .propose_action(
            &run,
            &db::models::conversation::records::ActionProposal {
                request_id: Uuid::new_v4(),
                origin_message_id: input.id,
                intent_kind: "agent_message".into(),
                payload: json!({"targets":[{"workspace_id":f.workspace}]}),
                route_evidence: json!({}),
            },
        )
        .await
        .unwrap();
    let confirmation = Uuid::new_v4();
    sqlx::query("INSERT INTO conversation_confirmations(id,conversation_id,action_id,principal_id,payload_digest,action_revision,expires_at,state) VALUES (?,?,?,?,?,?,unixepoch()+300,'pending')")
        .bind(confirmation).bind(f.id).bind(action.id).bind(f.context.store.get(f.id).await.unwrap().principal_id).bind(&action.payload_digest).bind(action.revision).execute(&f.pool).await.unwrap();
    assert_eq!(
        read(&f, &run, Some(f.workspace), 0).await["pending_supervisor_confirmations"][0]["confirmation_id"],
        confirmation.to_string()
    );
    let unrelated = Uuid::new_v4();
    sqlx::query("UPDATE conversation_actions SET run_id=NULL WHERE id=?")
        .bind(action.id)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        read(&f, &run, None, 0).await["pending_supervisor_confirmations"],
        json!([])
    );
    sqlx::query("UPDATE conversation_actions SET run_id=? WHERE id=?")
        .bind(run.id)
        .bind(action.id)
        .execute(&f.pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO workspaces(id,branch) VALUES (?,'unrelated')")
        .bind(unrelated)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        read(&f, &run, Some(unrelated), 0).await["pending_supervisor_confirmations"],
        json!([])
    );
    sqlx::query("UPDATE conversation_confirmations SET principal_id=? WHERE id=?")
        .bind(Uuid::new_v4())
        .bind(confirmation)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        read(&f, &run, None, 0).await["pending_supervisor_confirmations"],
        json!([])
    );
    sqlx::query("UPDATE conversation_confirmations SET principal_id=? WHERE id=?")
        .bind(f.context.store.get(f.id).await.unwrap().principal_id)
        .bind(confirmation)
        .execute(&f.pool)
        .await
        .unwrap();
    sqlx::query("UPDATE conversation_actions SET revision=revision+1 WHERE id=?")
        .bind(action.id)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        read(&f, &run, None, 0).await["pending_supervisor_confirmations"],
        json!([])
    );
    sqlx::query("UPDATE conversation_actions SET revision=?,state='cancelled' WHERE id=?")
        .bind(action.revision)
        .bind(action.id)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        read(&f, &run, None, 0).await["pending_supervisor_confirmations"],
        json!([])
    );
    sqlx::query("UPDATE conversation_actions SET state='proposed' WHERE id=?")
        .bind(action.id)
        .execute(&f.pool)
        .await
        .unwrap();
    sqlx::query("UPDATE conversation_confirmations SET expires_at=unixepoch()-1 WHERE id=?")
        .bind(confirmation)
        .execute(&f.pool)
        .await
        .unwrap();
    assert_eq!(
        read(&f, &run, None, 0).await["pending_supervisor_confirmations"],
        json!([])
    );
}

struct AttentionModel;
#[async_trait]
impl ConversationModel for AttentionModel {
    fn identity(&self) -> ModelIdentity {
        identity()
    }
    async fn next(&self, request: &ModelRequest) -> Result<ModelResponse, ModelError> {
        if request.exchanges.is_empty() {
            Ok(ModelResponse {
                continuation: ModelContinuation::default(),
                usage: ModelUsage::default(),
                step: ModelStep::Tool {
                    call: ToolCall {
                        id: "attention".into(),
                        tool: SupervisorTool::ListAttention {
                            workspace_id: None,
                            offset: 0,
                        },
                    },
                },
            })
        } else {
            let evidence = Uuid::parse_str(
                request.exchanges[0].result["data"]["evidence_id"]
                    .as_str()
                    .unwrap(),
            )
            .unwrap();
            Ok(ModelResponse {
                continuation: ModelContinuation::default(),
                usage: ModelUsage::default(),
                step: ModelStep::Reply {
                    text: "I can see the stored results, but live attention state is unavailable."
                        .into(),
                    evidence_ids: vec![evidence],
                },
            })
        }
    }
}

#[tokio::test]
async fn attention_reply_retains_citable_snapshot_and_cancelled_runs_cannot_write_one() {
    let f = fixture().await;
    f.context
        .store
        .accept(f.id, &input("Which projects are waiting on me?"))
        .await
        .unwrap();
    let worker = SupervisorWorker::new(f.pool.clone(), Arc::new(AttentionModel))
        .await
        .unwrap();
    let RunOutcome::Completed { message_id } = worker
        .run_one(f.id, &CancellationToken::new())
        .await
        .unwrap()
    else {
        panic!("expected reply")
    };
    let refs = f
        .context
        .store
        .message_evidence(f.id, message_id)
        .await
        .unwrap();
    assert_eq!(refs.len(), 1);
    assert_eq!(refs[0].source.0, EvidenceSource::AttentionSnapshot);
    let evidence = f
        .context
        .store
        .evidence(f.id, refs[0].evidence_id)
        .await
        .unwrap();
    assert!(
        evidence
            .raw_report
            .unwrap()
            .contains("runtime_state_incomplete")
    );
    let run = lease(&f).await;
    sqlx::query("UPDATE conversation_runs SET status='cancelled',lease_owner=NULL,lease_until=NULL WHERE id=?").bind(run.id).execute(&f.pool).await.unwrap();
    assert!(matches!(
        f.context
            .execute(
                &run,
                &SupervisorTool::ListAttention {
                    workspace_id: None,
                    offset: 0
                }
            )
            .await,
        Err(ConversationError::StaleLease)
    ));
}

#[tokio::test]
async fn attention_does_not_report_a_finished_goal_as_currently_paused() {
    let mut f = fixture().await;
    sqlx::query("UPDATE execution_processes SET status='running' WHERE id=?")
        .bind(f.process)
        .execute(&f.pool)
        .await
        .unwrap();
    let state = Runtime {
        paused: AtomicBool::new(true),
        finish_during_read: Some(f.pool.clone()),
        ..Default::default()
    };
    f.context.runtime = Some(Arc::new(state));
    let run = lease(&f).await;
    let result = read(&f, &run, None, 0).await;
    assert_eq!(
        signals(&result, f.session),
        vec!["runtime_state_incomplete"]
    );
    assert_eq!(
        result["items"][0]["native_goal"],
        "changed_during_observation"
    );
    assert!(result["snapshot_only"].as_bool().unwrap());
    assert!(!result["snapshot_atomic"].as_bool().unwrap());
}
