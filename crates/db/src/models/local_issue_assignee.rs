use chrono::{DateTime, Utc};
use serde::Serialize;
use sqlx::{FromRow, SqlitePool};
use uuid::Uuid;

pub const SEAMUS_ID: Uuid = Uuid::from_u128(0x5ea00000000040008000000000000001);

#[derive(Debug, FromRow)]
pub struct LocalParticipant {
    pub id: Uuid,
    pub username: String,
    pub display_name: String,
    pub created_at: DateTime<Utc>,
}

// Persist the existing IssueAssignee fields, without a second ownership model.
#[derive(Debug, Serialize, FromRow)]
pub struct LocalIssueAssignee {
    pub id: Uuid,
    pub issue_id: Uuid,
    pub user_id: Uuid,
    pub assigned_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, FromRow)]
pub struct WorkspaceIssueAssignee {
    pub workspace_id: Uuid,
    pub issue_id: Option<Uuid>,
    pub user_id: Option<Uuid>,
}

impl LocalIssueAssignee {
    pub async fn participants(pool: &SqlitePool) -> Result<Vec<LocalParticipant>, sqlx::Error> {
        sqlx::query_as("SELECT id, username, display_name, created_at FROM local_participants ORDER BY username")
            .fetch_all(pool).await
    }

    pub async fn for_project(
        pool: &SqlitePool,
        project_id: Uuid,
    ) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as("SELECT a.* FROM local_issue_assignees a JOIN tasks t ON t.id = a.issue_id WHERE t.project_id = ? ORDER BY a.assigned_at, a.id")
            .bind(project_id).fetch_all(pool).await
    }

    pub async fn for_issue(pool: &SqlitePool, issue_id: Uuid) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as(
            "SELECT * FROM local_issue_assignees WHERE issue_id = ? ORDER BY assigned_at, id",
        )
        .bind(issue_id)
        .fetch_all(pool)
        .await
    }

    pub async fn find(pool: &SqlitePool, id: Uuid) -> Result<Self, sqlx::Error> {
        sqlx::query_as("SELECT * FROM local_issue_assignees WHERE id = ?")
            .bind(id)
            .fetch_one(pool)
            .await
    }

    pub async fn create(
        pool: &SqlitePool,
        id: Uuid,
        issue_id: Uuid,
        user_id: Uuid,
    ) -> Result<Self, sqlx::Error> {
        // Retrying an assignment preserves the original row and timestamp.
        sqlx::query_as("INSERT INTO local_issue_assignees (id, issue_id, user_id) VALUES (?, ?, ?) ON CONFLICT(issue_id, user_id) DO UPDATE SET user_id = excluded.user_id RETURNING *")
            .bind(id).bind(issue_id).bind(user_id).fetch_one(pool).await
    }

    pub async fn delete(pool: &SqlitePool, id: Uuid) -> Result<(), sqlx::Error> {
        sqlx::query("DELETE FROM local_issue_assignees WHERE id = ?")
            .bind(id)
            .execute(pool)
            .await?;
        Ok(())
    }

    pub async fn workspace_links(
        pool: &SqlitePool,
    ) -> Result<Vec<WorkspaceIssueAssignee>, sqlx::Error> {
        // Use only actual task links. Synthetic/unlinked issues retain visibility.
        sqlx::query_as("SELECT w.id AS workspace_id, t.id AS issue_id, a.user_id FROM workspaces w LEFT JOIN tasks t ON t.id = w.task_id LEFT JOIN local_issue_assignees a ON a.issue_id = t.id ORDER BY w.id, a.user_id")
            .fetch_all(pool).await
    }
}

#[cfg(test)]
mod tests {
    use sqlx::sqlite::SqlitePoolOptions;

    use super::*;

    const DOT_ID: Uuid = Uuid::from_u128(0x5ea00000000040008000000000000002);

    async fn fixture() -> SqlitePool {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::raw_sql("PRAGMA foreign_keys=ON; CREATE TABLE tasks(id BLOB PRIMARY KEY, project_id BLOB); CREATE TABLE workspaces(id BLOB PRIMARY KEY, task_id BLOB); CREATE TABLE coding_agent_turns(id BLOB PRIMARY KEY, seen INTEGER);")
            .execute(&pool).await.unwrap();
        sqlx::raw_sql(include_str!(
            "../../migrations/20261009000000_local_issue_assignments.sql"
        ))
        .execute(&pool)
        .await
        .unwrap();
        pool
    }

    #[tokio::test]
    async fn assignments_inherit_task_links_and_preserve_unread_history() {
        let pool = fixture().await;
        let project = Uuid::new_v4();
        let participants = LocalIssueAssignee::participants(&pool).await.unwrap();
        assert_eq!(participants.len(), 2);
        assert!(
            participants
                .iter()
                .any(|p| p.id == SEAMUS_ID && p.display_name == "Seamus")
        );
        assert!(
            participants
                .iter()
                .any(|p| p.id == DOT_ID && p.username == "dot")
        );
        let mut workspace_ids = Vec::new();
        for users in [
            vec![DOT_ID],
            vec![SEAMUS_ID, DOT_ID],
            vec![SEAMUS_ID],
            vec![],
        ] {
            let task = Uuid::new_v4();
            let workspace = Uuid::new_v4();
            sqlx::query("INSERT INTO tasks VALUES (?, ?)")
                .bind(task)
                .bind(project)
                .execute(&pool)
                .await
                .unwrap();
            sqlx::query("INSERT INTO workspaces VALUES (?, ?)")
                .bind(workspace)
                .bind(task)
                .execute(&pool)
                .await
                .unwrap();
            for user in users {
                let record = LocalIssueAssignee::create(&pool, Uuid::new_v4(), task, user)
                    .await
                    .unwrap();
                let retry = LocalIssueAssignee::create(&pool, Uuid::new_v4(), task, user)
                    .await
                    .unwrap();
                assert_eq!(record.id, retry.id);
                assert_eq!(record.assigned_at, retry.assigned_at);
                assert_eq!(
                    LocalIssueAssignee::find(&pool, record.id)
                        .await
                        .unwrap()
                        .user_id,
                    user
                );
            }
            workspace_ids.push(workspace);
        }
        let unlinked = Uuid::new_v4();
        sqlx::query("INSERT INTO workspaces VALUES (?, NULL)")
            .bind(unlinked)
            .execute(&pool)
            .await
            .unwrap();
        sqlx::query("INSERT INTO coding_agent_turns VALUES (?, 0)")
            .bind(Uuid::new_v4())
            .execute(&pool)
            .await
            .unwrap();
        let links = LocalIssueAssignee::workspace_links(&pool).await.unwrap();
        let users_for = |id| {
            links
                .iter()
                .filter(|a| a.workspace_id == id)
                .filter_map(|a| a.user_id)
                .collect::<Vec<_>>()
        };
        assert_eq!(users_for(workspace_ids[0]), vec![DOT_ID]);
        assert_eq!(users_for(workspace_ids[1]), vec![SEAMUS_ID, DOT_ID]);
        assert_eq!(users_for(workspace_ids[2]), vec![SEAMUS_ID]);
        assert!(users_for(workspace_ids[3]).is_empty());
        assert!(
            links
                .iter()
                .any(|a| a.workspace_id == unlinked && a.issue_id.is_none())
        );
        let assignees = LocalIssueAssignee::for_project(&pool, project)
            .await
            .unwrap();
        assert_eq!(assignees.len(), 4);
        assert!(
            LocalIssueAssignee::for_project(&pool, Uuid::new_v4())
                .await
                .unwrap()
                .is_empty()
        );
        let record = &assignees[0];
        LocalIssueAssignee::delete(&pool, record.id).await.unwrap();
        LocalIssueAssignee::delete(&pool, record.id).await.unwrap();
        assert_eq!(
            LocalIssueAssignee::for_issue(&pool, record.issue_id)
                .await
                .unwrap()
                .len(),
            assignees
                .iter()
                .filter(|a| a.issue_id == record.issue_id)
                .count()
                - 1
        );
        let seen: i64 = sqlx::query_scalar("SELECT seen FROM coding_agent_turns")
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(seen, 0);
        sqlx::query("DELETE FROM tasks")
            .execute(&pool)
            .await
            .unwrap();
        assert!(
            LocalIssueAssignee::for_project(&pool, project)
                .await
                .unwrap()
                .is_empty()
        );
    }

    #[tokio::test]
    async fn assignment_foreign_keys_reject_unknown_participants_and_issues() {
        let pool = fixture().await;
        let task = Uuid::new_v4();
        sqlx::query("INSERT INTO tasks VALUES (?, ?)")
            .bind(task)
            .bind(Uuid::new_v4())
            .execute(&pool)
            .await
            .unwrap();
        assert!(
            LocalIssueAssignee::create(&pool, Uuid::new_v4(), task, Uuid::new_v4())
                .await
                .is_err()
        );
        assert!(
            LocalIssueAssignee::create(&pool, Uuid::new_v4(), Uuid::new_v4(), SEAMUS_ID)
                .await
                .is_err()
        );
    }
}
