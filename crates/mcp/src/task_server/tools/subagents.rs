use db::models::{session::Session, subagent_job::SubagentJob};
use rmcp::{
    ErrorData, handler::server::wrapper::Parameters, model::CallToolResult, schemars, tool,
    tool_router,
};
use serde::Deserialize;
use uuid::Uuid;

use super::{McpServer, ToolError};

#[derive(Debug, Deserialize, schemars::JsonSchema)]
struct ListSubagentsRequest {
    #[schemars(description = "VK session ID from list_sessions (not a Codex thread ID)")]
    session_id: Uuid,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
struct CloseSubagentRequest {
    #[schemars(description = "VK session ID used for list_subagents")]
    session_id: Uuid,
    #[schemars(description = "Exact agent_id from list_subagents; never a parent session ID")]
    agent_id: Uuid,
}

#[tool_router(router = subagent_tools_router, vis = "pub")]
impl McpServer {
    #[tool(
        description = "List tracked sub-agents for a workspace session, including stale and terminal entries. Use list_sessions to find the VK session ID. Inspect agent_id and status before closing a stale child."
    )]
    async fn list_subagents(
        &self,
        Parameters(request): Parameters<ListSubagentsRequest>,
    ) -> Result<CallToolResult, ErrorData> {
        if let Err(error) = self.check_subagent_session_scope(request.session_id).await {
            return Ok(Self::tool_error(error));
        }
        let url = self.url("/api/execution-processes/subagents/session");
        let jobs: Vec<SubagentJob> = match self
            .send_json(
                self.client
                    .get(url)
                    .query(&[("session_id", request.session_id)]),
            )
            .await
        {
            Ok(jobs) => jobs,
            Err(error) => return Ok(Self::tool_error(error)),
        };
        Self::success(&jobs)
    }

    #[tool(
        description = "Close a selected stale Codex sub-agent through its owning runtime so it no longer blocks waiting for that child. Requests shutdown, removes the loaded child, and archives its transcript without deleting files or stopping the parent. List sub-agents first. Close nested children individually. A 409 means the runtime is unavailable or the close timed out; do not assume the child stopped. Available only within the current workspace when workspace context exists."
    )]
    async fn close_subagent(
        &self,
        Parameters(request): Parameters<CloseSubagentRequest>,
    ) -> Result<CallToolResult, ErrorData> {
        if let Err(error) = self.check_subagent_session_scope(request.session_id).await {
            return Ok(Self::tool_error(error));
        }
        let url = self.url(&format!(
            "/api/execution-processes/subagents/session/{}/{}/close",
            request.session_id, request.agent_id,
        ));
        let result: serde_json::Value = match self
            .send_json(
                self.client
                    .post(url)
                    .timeout(std::time::Duration::from_secs(35)),
            )
            .await
        {
            Ok(result) => result,
            Err(error) => return Ok(Self::tool_error(error)),
        };
        Self::success(&result)
    }
}

impl McpServer {
    async fn check_subagent_session_scope(&self, session_id: Uuid) -> Result<(), ToolError> {
        let session: Session = self
            .send_json(
                self.client
                    .get(self.url(&format!("/api/sessions/{session_id}"))),
            )
            .await?;
        self.scope_allows_workspace(session.workspace_id)?;
        // Global-mode MCP also discovers workspace context for ordinary agents.
        // Keep their child-management tools within that workspace too.
        if self
            .scoped_workspace_id()
            .is_some_and(|id| id != session.workspace_id)
        {
            return Err(ToolError::message(
                "Sub-agent session is outside the current workspace",
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use serde_json::{Value, json};
    use tokio::{
        io::{AsyncReadExt, AsyncWriteExt},
        net::TcpListener,
    };

    use super::*;
    use crate::task_server::{McpContext, McpMode};

    async fn mock_api(responses: Vec<(String, Value)>) -> (String, tokio::task::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let url = format!("http://{}", listener.local_addr().unwrap());
        let task = tokio::spawn(async move {
            for (expected, data) in responses {
                let (mut stream, _) = listener.accept().await.unwrap();
                let mut request = Vec::new();
                while !request.ends_with(b"\r\n\r\n") {
                    request.push(stream.read_u8().await.unwrap());
                }
                assert_eq!(
                    String::from_utf8(request).unwrap().lines().next().unwrap(),
                    expected
                );
                let body = json!({"success": true, "data": data}).to_string();
                stream.write_all(format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    body.len(), body,
                ).as_bytes()).await.unwrap();
            }
        });
        (url, task)
    }

    fn session_response(session_id: Uuid, workspace_id: Uuid) -> (String, Value) {
        (
            format!("GET /api/sessions/{session_id} HTTP/1.1"),
            json!({
                "id": session_id, "workspace_id": workspace_id,
                "created_at": "2026-09-10T00:00:00Z", "updated_at": "2026-09-10T00:00:00Z",
            }),
        )
    }

    fn workspace_server(url: &str, workspace_id: Uuid, mode: McpMode) -> McpServer {
        // HTTP-only fixtures never perform TLS; installing once is shared with
        // other MCP tests which construct reqwest clients.
        super::super::tests::install_rustls_provider();
        let mut server = McpServer::new_global(url);
        server.mode = mode;
        server.context = Some(McpContext {
            organization_id: None,
            project_id: None,
            issue_id: None,
            orchestrator_session_id: None,
            workspace_id,
            workspace_branch: "test".into(),
            workspace_repos: vec![],
        });
        server
    }

    #[tokio::test]
    async fn close_subagent_checks_workspace_before_posting() {
        for mode in [McpMode::Global, McpMode::Orchestrator] {
            let session_id = Uuid::new_v4();
            let (url, fixture) = mock_api(vec![session_response(session_id, Uuid::new_v4())]).await;
            let server = workspace_server(&url, Uuid::new_v4(), mode);
            let result = server
                .close_subagent(Parameters(CloseSubagentRequest {
                    session_id,
                    agent_id: Uuid::new_v4(),
                }))
                .await
                .unwrap();
            assert_eq!(result.is_error, Some(true));
            assert!(serde_json::to_string(&result).unwrap().contains("outside"));
            fixture.await.unwrap();
        }
    }

    #[tokio::test]
    async fn close_subagent_posts_exact_selected_child() {
        let workspace_id = Uuid::new_v4();
        let session_id = Uuid::new_v4();
        let agent_id = Uuid::new_v4();
        let (url, fixture) = mock_api(vec![
            session_response(session_id, workspace_id),
            (format!("POST /api/execution-processes/subagents/session/{session_id}/{agent_id}/close HTTP/1.1"),
                json!({"agent_id": agent_id, "closed": true, "transcript_archived": true})),
        ]).await;
        let server = workspace_server(&url, workspace_id, McpMode::Global);
        let result = server
            .close_subagent(Parameters(CloseSubagentRequest {
                session_id,
                agent_id,
            }))
            .await
            .unwrap();
        assert_ne!(result.is_error, Some(true));
        assert!(
            serde_json::to_string(&result)
                .unwrap()
                .contains(&agent_id.to_string())
        );
        fixture.await.unwrap();
    }
}
