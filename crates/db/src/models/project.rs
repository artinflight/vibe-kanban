use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, SqlitePool};
use ts_rs::TS;
use uuid::Uuid;

#[derive(Debug, Clone, FromRow, Serialize, Deserialize, TS)]
pub struct Project {
    pub id: Uuid,
    pub name: String,
    pub archived: bool,
    pub default_agent_working_dir: Option<String>,
    pub remote_project_id: Option<Uuid>,
    #[ts(type = "Date")]
    pub created_at: DateTime<Utc>,
    #[ts(type = "Date")]
    pub updated_at: DateTime<Utc>,
}

impl Project {
    pub async fn find_all(pool: &SqlitePool) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as::<_, Project>(
            r#"SELECT id,
                      name,
                      archived,
                      default_agent_working_dir,
                      remote_project_id,
                      created_at,
                      updated_at
               FROM projects
               ORDER BY created_at DESC"#,
        )
        .fetch_all(pool)
        .await
    }

    pub async fn find_by_id(pool: &SqlitePool, id: Uuid) -> Result<Self, sqlx::Error> {
        sqlx::query_as::<_, Project>(
            r#"SELECT id,
                      name,
                      archived,
                      default_agent_working_dir,
                      remote_project_id,
                      created_at,
                      updated_at
               FROM projects
               WHERE id = ?"#,
        )
        .bind(id)
        .fetch_one(pool)
        .await
    }

    pub async fn set_remote_project_id(
        pool: &SqlitePool,
        id: Uuid,
        remote_project_id: Option<Uuid>,
    ) -> Result<(), sqlx::Error> {
        sqlx::query!(
            r#"UPDATE projects
               SET remote_project_id = $2
               WHERE id = $1"#,
            id,
            remote_project_id
        )
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn set_archived(
        pool: &SqlitePool,
        id: Uuid,
        archived: bool,
    ) -> Result<Self, sqlx::Error> {
        sqlx::query_as::<_, Project>(
            r#"UPDATE projects
               SET archived = $2,
                   updated_at = datetime('now', 'subsec')
               WHERE id = $1
               RETURNING id,
                         name,
                         archived,
                         default_agent_working_dir,
                         remote_project_id,
                         created_at,
                         updated_at"#,
        )
        .bind(id)
        .bind(archived)
        .fetch_one(pool)
        .await
    }

    pub async fn materialize_synthetic(
        pool: &SqlitePool,
        synthetic_project: &Project,
        archived: bool,
    ) -> Result<Self, sqlx::Error> {
        sqlx::query_as::<_, Project>(
            r#"INSERT INTO projects (
                   id,
                   name,
                   archived,
                   default_agent_working_dir,
                   remote_project_id,
                   created_at,
                   updated_at
               )
               VALUES ($1, $2, $3, $4, NULL, $5, datetime('now', 'subsec'))
               ON CONFLICT(id) DO UPDATE SET
                   archived = excluded.archived,
                   default_agent_working_dir = COALESCE(
                       NULLIF(projects.default_agent_working_dir, ''),
                       excluded.default_agent_working_dir
                   ),
                   updated_at = datetime('now', 'subsec')
               RETURNING id,
                         name,
                         archived,
                         default_agent_working_dir,
                         remote_project_id,
                         created_at,
                         updated_at"#,
        )
        .bind(synthetic_project.id)
        .bind(&synthetic_project.name)
        .bind(archived)
        .bind(&synthetic_project.default_agent_working_dir)
        .bind(synthetic_project.created_at)
        .fetch_one(pool)
        .await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    async fn setup_pool() -> SqlitePool {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        sqlx::query(
            r#"CREATE TABLE projects (
                   id BLOB PRIMARY KEY,
                   name TEXT NOT NULL,
                   archived INTEGER NOT NULL DEFAULT 0,
                   default_agent_working_dir TEXT DEFAULT '',
                   remote_project_id BLOB,
                   created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
                   updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
               )"#,
        )
        .execute(&pool)
        .await
        .unwrap();
        pool
    }

    #[tokio::test]
    async fn materialize_synthetic_project_archives_and_restores() {
        let pool = setup_pool().await;
        let project = Project {
            id: Uuid::new_v4(),
            name: "Synthetic".to_string(),
            archived: false,
            default_agent_working_dir: Some("app".to_string()),
            remote_project_id: None,
            created_at: Utc::now(),
            updated_at: Utc::now(),
        };

        let archived = Project::materialize_synthetic(&pool, &project, true)
            .await
            .unwrap();
        assert_eq!(archived.id, project.id);
        assert!(archived.archived);
        assert_eq!(archived.default_agent_working_dir.as_deref(), Some("app"));

        let restored = Project::set_archived(&pool, project.id, false)
            .await
            .unwrap();
        assert!(!restored.archived);
        assert_eq!(restored.name, "Synthetic");
    }
}
