//! Live attention projection for the global supervisor. This never marks raw
//! workspace turns seen, resumes a goal, or interprets unread work as a question.
use std::time::Duration;

use db::models::conversation::{ConversationError, ConversationRun, records::EvidenceSource};
use executors::executors::codex::client::GoalMessageAdmission;
use futures::{StreamExt, TryStreamExt};
use serde::Serialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::FromRow;
use uuid::Uuid;

use super::context::LocalContext;

const PAGE: usize = 20;

#[derive(FromRow, Serialize)]
struct SessionObservation {
    session_id: Uuid,
    session_name: Option<String>,
    executor: Option<String>,
    workspace_id: Uuid,
    workspace_name: Option<String>,
    branch: String,
    project_id: Option<Uuid>,
    project_name: Option<String>,
    process_id: Option<Uuid>,
    process_status: Option<String>,
    exit_code: Option<i64>,
    process_updated_at: Option<String>,
    has_report: bool,
    unread_completion: bool,
    waiting_capacity: i64,
    uncertain_deliveries: i64,
}

impl LocalContext {
    pub(super) async fn attention(
        &self,
        run: &ConversationRun,
        workspace: Option<Uuid>,
        offset: u32,
    ) -> Result<Value, ConversationError> {
        let observed_from = chrono::Utc::now();
        if offset > 10_000 {
            return Err(ConversationError::InvalidRecord);
        }
        if let Some(id) = workspace {
            let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM workspaces WHERE id=? AND archived=0 AND worktree_deleted=0)")
                .bind(id).fetch_one(&self.pool).await?;
            if !exists {
                return Err(ConversationError::NotFound);
            }
        }
        // Page sessions rather than only the latest process per workspace: two
        // agents in one workspace can independently need attention. Devservers
        // and setup processes cannot hide the latest coding result.
        let mut rows: Vec<SessionObservation> = sqlx::query_as(
            r#"SELECT s.id AS session_id, substr(s.name,1,512) AS session_name,
                s.executor, w.id AS workspace_id, substr(w.name,1,512) AS workspace_name,
                substr(w.branch,1,512) AS branch, t.project_id, substr(p.name,1,512) AS project_name,
                e.id AS process_id, e.status AS process_status, e.exit_code,
                e.updated_at AS process_updated_at, ct.summary IS NOT NULL AS has_report,
                EXISTS(SELECT 1 FROM execution_processes ue JOIN coding_agent_turns ut ON ut.execution_process_id=ue.id
                    WHERE ue.session_id=s.id AND ue.run_reason='codingagent' AND ue.dropped=0
                    AND ue.status='completed' AND ue.exit_code=0 AND ut.seen=0) AS unread_completion,
                (SELECT count(*) FROM agent_deliveries d WHERE d.session_id=s.id AND d.state='waiting_capacity') AS waiting_capacity,
                (SELECT count(*) FROM agent_deliveries d WHERE d.session_id=s.id AND d.state='unknown_delivery') AS uncertain_deliveries
            FROM sessions s JOIN workspaces w ON w.id=s.workspace_id
            LEFT JOIN tasks t ON t.id=w.task_id LEFT JOIN projects p ON p.id=t.project_id
            LEFT JOIN execution_processes e ON e.id=(SELECT ep.id FROM execution_processes ep
                WHERE ep.session_id=s.id AND ep.run_reason='codingagent' AND ep.dropped=0
                ORDER BY ep.created_at DESC,ep.id DESC LIMIT 1)
            LEFT JOIN coding_agent_turns ct ON ct.id=(SELECT turn.id FROM coding_agent_turns turn
                WHERE turn.execution_process_id=e.id ORDER BY turn.updated_at DESC,turn.id DESC LIMIT 1)
            WHERE w.archived=0 AND w.worktree_deleted=0 AND (? IS NULL OR w.id=?)
            ORDER BY w.id,s.id LIMIT ? OFFSET ?"#,
        ).bind(workspace).bind(workspace).bind(PAGE as i64 + 1).bind(offset).fetch_all(&self.pool).await?;
        let more = rows.len() > PAGE;
        rows.truncate(PAGE);
        let scanned = rows.len();
        let observations: Vec<Option<Value>> = futures::stream::iter(rows).map(|row| async move {
            let mut signals = Vec::new();
            if row.process_status.as_deref() == Some("failed")
                || (row.process_status.as_deref() == Some("completed")
                    && row.exit_code.is_some_and(|code| code != 0))
            {
                signals.push("execution_failed");
            } else if row.process_status.as_deref() == Some("killed") {
                signals.push("execution_interrupted");
            }
            if row.unread_completion {
                signals.push("unread_completion");
            }
            if row.waiting_capacity > 0 {
                signals.push("waiting_capacity");
            }
            if row.uncertain_deliveries > 0 {
                signals.push("delivery_uncertain");
            }
            // Include pending setup/cleanup approvals as well as coding-agent
            // approvals. Inspect only processes in this local session.
            let mut processes: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM execution_processes WHERE session_id=? AND status='running' AND dropped=0 AND run_reason!='devserver' ORDER BY id LIMIT 21")
                .bind(row.session_id).fetch_all(&self.pool).await?;
            let processes_truncated = processes.len() > 20;
            processes.truncate(20);
            let mut pending_responses: Option<Vec<Uuid>> = None;
            let mut capacity_managed = None;
            let mut goal_state = "not_inspected";
            if let Some(runtime) = &self.runtime {
                let mut pending: Vec<_> = runtime.approvals(&processes).into_iter()
                    .filter(|id| processes.contains(id)).collect();
                pending.sort();
                if !pending.is_empty() {
                    signals.push("pending_executor_response");
                }
                pending_responses = Some(pending);
                capacity_managed = tokio::time::timeout(Duration::from_secs(2), runtime.capacity_managed(row.session_id))
                    .await.ok().and_then(Result::ok);
                if row.executor.as_deref() == Some("CODEX")
                    && row.process_status.as_deref() == Some("running")
                    && let Some(process) = row.process_id
                {
                    goal_state = match tokio::time::timeout(Duration::from_secs(2), runtime.goal(process)).await {
                        Ok(Ok(GoalMessageAdmission::Allowed)) => "message_admissible",
                        Ok(Ok(GoalMessageAdmission::Paused)) => {
                            signals.push("native_goal_paused");
                            "paused"
                        }
                        _ => "unavailable",
                    };
                }
            }
            if goal_state != "not_inspected" {
                // A goal read can race with its execution finishing. Do not
                // present that former owner's pause as a current user blocker.
                let still_running: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM execution_processes WHERE id=? AND status='running' AND dropped=0)")
                    .bind(row.process_id).fetch_one(&self.pool).await?;
                if !still_running {
                    goal_state = "changed_during_observation";
                    signals.retain(|signal| *signal != "native_goal_paused");
                }
            }
            let runtime_complete = pending_responses.is_some() && capacity_managed.is_some()
                && !processes_truncated && !matches!(goal_state,"unavailable" | "changed_during_observation");
            if !runtime_complete {
                signals.push("runtime_state_incomplete");
            }
            // Quiet sessions consume the page cursor but do not clutter the
            // result. A caller must still follow next_offset on an empty page.
            if !signals.is_empty() {
                let repositories: Vec<(Uuid, String)> = sqlx::query_as("SELECT r.id, substr(r.display_name,1,512) FROM workspace_repos wr JOIN repos r ON r.id=wr.repo_id WHERE wr.workspace_id=? ORDER BY r.id LIMIT 21")
                    .bind(row.workspace_id).fetch_all(&self.pool).await?;
                Ok::<_,ConversationError>(Some(json!({"session":row,"signals":signals,
                    "workspace_path":format!("/workspaces/{}",row.workspace_id),
                    "pending_executor_response_process_ids":pending_responses,
                    "capacity_managed":capacity_managed,"native_goal":goal_state,
                    "running_processes_truncated":processes_truncated,
                    "repositories":repositories.iter().take(20).map(|(id,name)|json!({"repo_id":id,"name":name})).collect::<Vec<_>>(),
                    "repositories_truncated":repositories.len()>20})))
            } else {
                Ok(None)
            }
        }).buffered(4).try_collect().await?;
        let items: Vec<_> = observations.into_iter().flatten().collect();
        // Scope confirmations to this conversation. Include only still-effective
        // grants; stale cancelled/revised proposals are not outstanding decisions.
        let confirmations: Vec<Value> = if offset == 0 {
            let rows: Vec<(Uuid, Uuid, i64)> = sqlx::query_as(
                r#"SELECT c.id,c.action_id,c.expires_at FROM conversation_confirmations c
                JOIN conversation_actions a ON a.id=c.action_id AND a.conversation_id=c.conversation_id
                JOIN conversations owner ON owner.id=c.conversation_id AND owner.principal_id=c.principal_id
                WHERE c.conversation_id=? AND c.state='pending' AND c.expires_at>unixepoch()
                AND a.state='proposed' AND a.revision=c.action_revision AND a.payload_digest=c.payload_digest
                AND EXISTS(SELECT 1 FROM conversation_runs origin WHERE origin.id=a.run_id
                    AND origin.conversation_id=a.conversation_id AND origin.input_message_id=a.origin_message_id
                    AND (origin.status='completed' OR (origin.status='running' AND origin.lease_until>unixepoch())))
                AND (? IS NULL OR EXISTS(SELECT 1 FROM json_each(a.payload,'$.targets') target
                    WHERE json_extract(target.value,'$.workspace_id')=?))
                ORDER BY c.expires_at,c.id LIMIT 21"#,
            ).bind(run.conversation_id).bind(workspace).bind(workspace.map(|id|id.to_string()))
                .fetch_all(&self.pool).await?;
            rows.into_iter().map(|(id,action,expires)|json!({"confirmation_id":id,"action_id":action,"expires_at":expires})).collect()
        } else {
            Vec::new()
        };
        let data = json!({"items":items,"pending_supervisor_confirmations":confirmations.iter().take(20).collect::<Vec<_>>(),
            "confirmations_truncated":confirmations.len()>20,"confirmations_included":offset==0,
            "scanned_sessions":scanned,"next_offset":if more {Some(offset+PAGE as u32)} else {None},
            "observed_from":observed_from,"observed_at":chrono::Utc::now(),"snapshot_only":true,"snapshot_atomic":false,
            "coverage":{"authority":"local_operator","active_workspaces_only":true,
                "runtime_connected":self.runtime.is_some(),"pagination":"live_session_scan",
                "not_inspected":["inactive_native_goals","report_semantics","remote_hosts"],
                "meaning":"Unread completion is not a pending decision. Capacity waiting does not itself need a user response. Paused goals may be intentional. Read reports to assess prose questions, failed validation and rationale; absence of signals is not an all-clear."}});
        let raw =
            serde_json::to_string_pretty(&data).map_err(|_| ConversationError::InvalidRecord)?;
        let hash = format!("{:x}", Sha256::digest(raw.as_bytes()));
        let evidence = self
            .store
            .retain_run_evidence(run, &EvidenceSource::AttentionSnapshot, &hash, &raw)
            .await?;
        let mut result = data;
        result["evidence_id"] = json!(evidence.id);
        result["source_revision"] = json!(hash);
        Ok(result)
    }
}
