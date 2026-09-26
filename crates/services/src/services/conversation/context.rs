//! Bounded local entity projection. The trusted local operator can read local VK
//! rows; relay or remote principals must not be mapped to this context service.
use db::models::conversation::{
    ConversationError, ConversationRun, ConversationScope, ConversationStore,
    records::{EvidenceSource, MemoryScope},
};
use serde::Serialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

use super::model::ReadTool;

type Result<T> = std::result::Result<T, ConversationError>;
const PAGE: i64 = 20;
const REPORT_PAGE_CHARS: usize = 16_384;

#[derive(Clone)]
pub struct LocalContext {
    pool: SqlitePool,
    pub(super) store: ConversationStore,
}

#[derive(Debug, FromRow, Serialize)]
struct Candidate {
    workspace_id: Uuid,
    name: Option<String>,
    branch: String,
    archived: bool,
    worktree_deleted: bool,
    updated_at: String,
    task_id: Option<Uuid>,
    task_title: Option<String>,
    project_id: Option<Uuid>,
    project_name: Option<String>,
    session_count: i64,
}

const CANDIDATE: &str = "SELECT w.id AS workspace_id, substr(w.name,1,512) AS name, substr(w.branch,1,512) AS branch, w.archived, w.worktree_deleted, w.updated_at, w.task_id, substr(t.title,1,512) AS task_title, t.project_id, substr(p.name,1,512) AS project_name, (SELECT count(*) FROM sessions s WHERE s.workspace_id = w.id) AS session_count FROM workspaces w LEFT JOIN tasks t ON t.id = w.task_id LEFT JOIN projects p ON p.id = t.project_id ";

#[derive(Debug, FromRow, Serialize)]
struct SessionState {
    session_id: Uuid,
    name: Option<String>,
    executor: Option<String>,
    updated_at: String,
    latest_process_id: Option<Uuid>,
    latest_status: Option<String>,
    latest_run_reason: Option<String>,
    running_processes: i64,
    queued_messages: i64,
}

#[derive(Debug, FromRow, Serialize)]
struct ReportRef {
    process_id: Uuid,
    turn_id: Option<Uuid>,
    status: String,
    exit_code: Option<i64>,
    updated_at: String,
    has_report: bool,
    report_chars: i64,
}

#[derive(Debug, FromRow)]
struct Report {
    session_id: Uuid,
    summary: Option<String>,
    status: String,
    updated_at: String,
    report_bytes: i64,
}

impl LocalContext {
    pub async fn new(pool: SqlitePool) -> Result<Self> {
        let scope = ConversationScope::local_operator(&pool).await?;
        Ok(Self {
            store: ConversationStore::new(pool.clone(), scope),
            pool,
        })
    }

    pub async fn execute(&self, run: &ConversationRun, tool: &ReadTool) -> Result<Value> {
        // Recheck scope and cancellation before each read or retained-evidence write.
        self.store.renew(run).await?;
        let data = match tool {
            ReadTool::FindContext {
                query,
                include_archived,
                offset,
            } => self.find(query, *include_archived, *offset).await?,
            ReadTool::ReadWorkspaceState {
                workspace_id,
                offset,
            } => self.workspace(*workspace_id, *offset).await?,
            ReadTool::ReadAgentHistory { session_id, offset } => {
                self.history(*session_id, *offset).await?
            }
            ReadTool::ReadAgentReport { process_id, offset } => {
                self.report(run, *process_id, *offset).await?
            }
            ReadTool::ReadEvidence {
                evidence_id,
                offset,
            } => {
                let evidence = self
                    .store
                    .evidence(run.conversation_id, *evidence_id)
                    .await?;
                match evidence.raw_report {
                    Some(body) => report_page(evidence.id, &body, *offset)?,
                    None => json!({"evidence_id":evidence.id,"availability":"unavailable"}),
                }
            }
            ReadTool::SearchMemory { workspace_id } => {
                let mut scopes = vec![MemoryScope::Conversation(run.conversation_id)];
                if let Some(id) = workspace_id {
                    let row = self.candidate(*id).await?;
                    scopes.push(MemoryScope::Workspace(*id));
                    if let Some(project) = row.project_id {
                        scopes.push(MemoryScope::Project(project));
                    }
                    let repos: Vec<Uuid> = sqlx::query_scalar("SELECT repo_id FROM workspace_repos WHERE workspace_id = ? ORDER BY repo_id LIMIT 20")
                        .bind(id).fetch_all(&self.pool).await?;
                    scopes.extend(repos.into_iter().map(MemoryScope::Repository));
                }
                json!({"memories":self.store.memories(run.conversation_id, &scopes, 16384).await?})
            }
        };
        Ok(
            json!({"data":data, "observed_at":chrono::Utc::now(), "authority":"local_operator", "trust":"source_data"}),
        )
    }

    async fn candidate(&self, id: Uuid) -> Result<Candidate> {
        sqlx::query_as(&format!("{CANDIDATE} WHERE w.id = ?"))
            .bind(id)
            .fetch_optional(&self.pool)
            .await?
            .ok_or(ConversationError::NotFound)
    }

    async fn find(&self, query: &str, archived: bool, offset: u32) -> Result<Value> {
        check_offset(offset)?;
        if query.len() > 128 {
            return Err(ConversationError::InvalidRecord);
        }
        // Literal substring lookup: user/model '%' and '_' never broaden the query.
        let query = format!(
            "%{}%",
            query
                .replace('\\', "\\\\")
                .replace('%', "\\%")
                .replace('_', "\\_")
        );
        let rows: Vec<Candidate> = sqlx::query_as(&format!("{CANDIDATE} WHERE (? OR (w.archived = 0 AND w.worktree_deleted = 0)) AND (coalesce(w.name,'') LIKE ? ESCAPE '\\' OR w.branch LIKE ? ESCAPE '\\' OR coalesce(t.title,'') LIKE ? ESCAPE '\\' OR coalesce(p.name,'') LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM workspace_repos wr JOIN repos r ON r.id = wr.repo_id WHERE wr.workspace_id = w.id AND (r.name LIKE ? ESCAPE '\\' OR r.display_name LIKE ? ESCAPE '\\')) OR EXISTS (SELECT 1 FROM sessions s WHERE s.workspace_id = w.id AND coalesce(s.name,'') LIKE ? ESCAPE '\\')) ORDER BY w.archived, w.worktree_deleted, w.updated_at DESC, w.id LIMIT ? OFFSET ?"))
            .bind(archived).bind(&query).bind(&query).bind(&query).bind(&query).bind(&query).bind(&query).bind(&query)
            .bind(PAGE + 1).bind(offset).fetch_all(&self.pool).await?;
        page(rows, offset)
    }

    async fn workspace(&self, id: Uuid, offset: u32) -> Result<Value> {
        check_offset(offset)?;
        let workspace = self.candidate(id).await?;
        let sessions: Vec<SessionState> = sqlx::query_as("SELECT s.id AS session_id, substr(s.name,1,512) AS name, s.executor, s.updated_at, e.id AS latest_process_id, e.status AS latest_status, e.run_reason AS latest_run_reason, (SELECT count(*) FROM execution_processes ep WHERE ep.session_id = s.id AND ep.status = 'running' AND ep.dropped = 0) AS running_processes, (SELECT count(*) FROM agent_deliveries d WHERE d.session_id = s.id AND d.state IN ('queued','waiting_capacity','dispatching')) AS queued_messages FROM sessions s LEFT JOIN execution_processes e ON e.id = (SELECT ep.id FROM execution_processes ep WHERE ep.session_id = s.id AND ep.dropped = 0 ORDER BY ep.created_at DESC,ep.id DESC LIMIT 1) WHERE s.workspace_id = ? ORDER BY s.updated_at DESC,s.id LIMIT ? OFFSET ?")
            .bind(id).bind(PAGE + 1).bind(offset).fetch_all(&self.pool).await?;
        // Include exact repo IDs and names, not host paths or setup scripts.
        let repos: Vec<(Uuid, String, String)> = sqlx::query_as("SELECT r.id, substr(r.display_name,1,512), substr(wr.target_branch,1,512) FROM workspace_repos wr JOIN repos r ON r.id = wr.repo_id WHERE wr.workspace_id = ? ORDER BY r.id LIMIT 21")
            .bind(id).fetch_all(&self.pool).await?;
        let mut data = json!({"workspace":workspace,"sessions":page(sessions, offset)?,"repositories":repos.iter().take(20).map(|(id,name,branch)|json!({"repo_id":id,"name":name,"target_branch":branch})).collect::<Vec<_>>(),"repositories_truncated":repos.len()>20});
        // Hash the observed fields, not just workspace.updated_at: processes can
        // finish without touching that timestamp. Dispatch must revalidate later.
        let version = format!("{:x}", Sha256::digest(serde_json::to_vec(&data).unwrap()));
        data["version"] = json!(version);
        Ok(data)
    }

    async fn history(&self, id: Uuid, offset: u32) -> Result<Value> {
        check_offset(offset)?;
        let exists: bool = sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM sessions WHERE id = ?)")
            .bind(id)
            .fetch_one(&self.pool)
            .await?;
        if !exists {
            return Err(ConversationError::NotFound);
        }
        let reports: Vec<ReportRef> = sqlx::query_as("SELECT e.id AS process_id, t.id AS turn_id, e.status, e.exit_code, e.updated_at, t.summary IS NOT NULL AS has_report, coalesce(length(t.summary),0) AS report_chars FROM execution_processes e LEFT JOIN coding_agent_turns t ON t.id = (SELECT ct.id FROM coding_agent_turns ct WHERE ct.execution_process_id = e.id ORDER BY ct.updated_at DESC,ct.id DESC LIMIT 1) WHERE e.session_id = ? AND e.run_reason = 'codingagent' AND e.dropped = 0 ORDER BY e.created_at DESC,e.id DESC LIMIT ? OFFSET ?")
            .bind(id).bind(PAGE + 1).bind(offset).fetch_all(&self.pool).await?;
        page(reports, offset)
    }

    async fn report(&self, run: &ConversationRun, id: Uuid, offset: u32) -> Result<Value> {
        let row: Report = sqlx::query_as("SELECT e.session_id, CASE WHEN length(CAST(t.summary AS BLOB)) <= 1048576 THEN t.summary ELSE NULL END AS summary, coalesce(length(CAST(t.summary AS BLOB)),0) AS report_bytes, e.status, e.updated_at FROM execution_processes e LEFT JOIN coding_agent_turns t ON t.id = (SELECT ct.id FROM coding_agent_turns ct WHERE ct.execution_process_id = e.id ORDER BY ct.updated_at DESC,ct.id DESC LIMIT 1) WHERE e.id = ? AND e.run_reason = 'codingagent' AND e.dropped = 0")
            .bind(id).fetch_optional(&self.pool).await?.ok_or(ConversationError::NotFound)?;
        let Some(body) = row.summary else {
            return Ok(
                json!({"process_id":id,"status":row.status,"availability":if row.report_bytes>1048576 {"too_large"} else {"not_yet_available"}}),
            );
        };
        let hash = format!("{:x}", Sha256::digest(body.as_bytes()));
        let source = EvidenceSource::AgentReport {
            session_id: row.session_id,
            process_id: id,
        };
        let evidence = self
            .store
            .retain_run_evidence(run, &source, &hash, &body)
            .await?;
        let mut data = report_page(evidence.id, &body, offset)?;
        data["process_id"] = json!(id);
        data["status"] = json!(row.status);
        data["updated_at"] = json!(row.updated_at);
        data["source_revision"] = json!(hash);
        Ok(data)
    }
}

fn check_offset(offset: u32) -> Result<()> {
    if offset > 10_000 {
        Err(ConversationError::InvalidRecord)
    } else {
        Ok(())
    }
}

fn page<T: Serialize>(mut rows: Vec<T>, offset: u32) -> Result<Value> {
    let more = rows.len() > PAGE as usize;
    rows.truncate(PAGE as usize);
    Ok(json!({"items":rows,"next_offset":if more { Some(offset+PAGE as u32) } else {None}}))
}

fn report_page(id: Uuid, body: &str, offset: u32) -> Result<Value> {
    let total = body.chars().count();
    if offset as usize > total {
        return Err(ConversationError::InvalidRecord);
    }
    let excerpt: String = body
        .chars()
        .skip(offset as usize)
        .take(REPORT_PAGE_CHARS)
        .collect();
    let end = offset as usize + excerpt.chars().count();
    Ok(
        json!({"evidence_id":id,"text":excerpt,"offset":offset,"total_chars":total,
        "next_offset":if end<total {Some(end)} else {None},"availability":"retained","is_complete":offset==0 && end==total}),
    )
}
