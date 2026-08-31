use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, SqlitePool};
use ts_rs::TS;

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct ProjectNavigationOrder {
    #[sqlx(json)]
    pub project_ids: Vec<String>,
    pub revision: i64,
    pub updated_at: DateTime<Utc>,
}

#[cfg(test)]
mod tests {
    use sqlx::sqlite::SqlitePoolOptions;

    use super::*;

    async fn test_pool() -> SqlitePool {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        for statement in [
            r#"CREATE TABLE project_navigation_order (
                id INTEGER PRIMARY KEY, project_ids TEXT NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"#,
            r#"CREATE TABLE project_navigation_order_history (
                revision INTEGER PRIMARY KEY, project_ids TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"#,
            r#"CREATE TABLE workspace_card_colors (
                workspace_id TEXT PRIMARY KEY, color TEXT NOT NULL,
                revision INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"#,
            r#"CREATE TABLE workspace_card_color_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL,
                color TEXT, revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"#,
            r#"INSERT INTO project_navigation_order (id, project_ids, revision)
                VALUES (1, '[\"project-a\"]', 1)"#,
        ] {
            sqlx::query(statement).execute(&pool).await.unwrap();
        }
        pool
    }

    #[tokio::test]
    async fn project_order_rejects_stale_writes_and_keeps_history() {
        let pool = test_pool().await;
        let updated = DurableUiPreferences::update_project_order(
            &pool,
            &UpdateProjectNavigationOrder {
                project_ids: vec!["project-b".into(), "project-a".into()],
                expected_revision: 1,
            },
        )
        .await
        .unwrap();
        assert_eq!(updated.revision, 2);
        assert_eq!(updated.project_ids, vec!["project-b", "project-a"]);

        let stale = DurableUiPreferences::update_project_order(
            &pool,
            &UpdateProjectNavigationOrder {
                project_ids: vec!["project-a".into()],
                expected_revision: 1,
            },
        )
        .await;
        assert!(matches!(stale, Err(DurablePreferenceError::Conflict)));
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM project_navigation_order_history")
                .fetch_one(&pool)
                .await
                .unwrap(),
            1
        );
    }

    #[tokio::test]
    async fn workspace_colors_are_independent_and_revision_checked() {
        let pool = test_pool().await;
        let created = DurableUiPreferences::update_workspace_color(
            &pool,
            "workspace-a",
            &UpdateWorkspaceCardColor {
                color: Some("blue".into()),
                expected_revision: None,
            },
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(created.revision, 1);

        let stale = DurableUiPreferences::update_workspace_color(
            &pool,
            "workspace-a",
            &UpdateWorkspaceCardColor {
                color: Some("red".into()),
                expected_revision: None,
            },
        )
        .await;
        assert!(matches!(stale, Err(DurablePreferenceError::Conflict)));

        DurableUiPreferences::update_workspace_color(
            &pool,
            "workspace-a",
            &UpdateWorkspaceCardColor {
                color: None,
                expected_revision: Some(1),
            },
        )
        .await
        .unwrap();
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM workspace_card_color_history")
                .fetch_one(&pool)
                .await
                .unwrap(),
            2
        );
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct WorkspaceCardColor {
    pub workspace_id: String,
    pub color: String,
    pub revision: i64,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct DurableUiPreferences {
    pub project_order: ProjectNavigationOrder,
    pub workspace_colors: HashMap<String, WorkspaceCardColor>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct UpdateProjectNavigationOrder {
    pub project_ids: Vec<String>,
    pub expected_revision: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct UpdateWorkspaceCardColor {
    pub color: Option<String>,
    pub expected_revision: Option<i64>,
}

#[derive(Debug, thiserror::Error)]
pub enum DurablePreferenceError {
    #[error("Preference revision conflict")]
    Conflict,
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}

impl DurableUiPreferences {
    pub async fn get(pool: &SqlitePool) -> Result<Self, DurablePreferenceError> {
        let project_order = sqlx::query_as::<_, ProjectNavigationOrder>(
            r#"SELECT project_ids, revision, updated_at
               FROM project_navigation_order WHERE id = 1"#,
        )
        .fetch_one(pool)
        .await?;
        let colors = sqlx::query_as::<_, WorkspaceCardColor>(
            r#"SELECT workspace_id, color, revision, updated_at
               FROM workspace_card_colors ORDER BY workspace_id"#,
        )
        .fetch_all(pool)
        .await?;

        Ok(Self {
            project_order,
            workspace_colors: colors
                .into_iter()
                .map(|color| (color.workspace_id.clone(), color))
                .collect(),
        })
    }

    pub async fn update_project_order(
        pool: &SqlitePool,
        input: &UpdateProjectNavigationOrder,
    ) -> Result<ProjectNavigationOrder, DurablePreferenceError> {
        let project_ids = serde_json::to_string(&input.project_ids)?;
        let mut tx = pool.begin().await?;
        let result = sqlx::query(
            r#"UPDATE project_navigation_order
               SET project_ids = ?1, revision = revision + 1,
                   updated_at = datetime('now', 'subsec')
               WHERE id = 1 AND revision = ?2"#,
        )
        .bind(&project_ids)
        .bind(input.expected_revision)
        .execute(&mut *tx)
        .await?;
        if result.rows_affected() != 1 {
            return Err(DurablePreferenceError::Conflict);
        }
        let updated = sqlx::query_as::<_, ProjectNavigationOrder>(
            r#"SELECT project_ids, revision, updated_at
               FROM project_navigation_order WHERE id = 1"#,
        )
        .fetch_one(&mut *tx)
        .await?;
        sqlx::query(
            r#"INSERT INTO project_navigation_order_history (revision, project_ids)
               VALUES (?1, ?2)"#,
        )
        .bind(updated.revision)
        .bind(&project_ids)
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(updated)
    }

    pub async fn update_workspace_color(
        pool: &SqlitePool,
        workspace_id: &str,
        input: &UpdateWorkspaceCardColor,
    ) -> Result<Option<WorkspaceCardColor>, DurablePreferenceError> {
        let mut tx = pool.begin().await?;
        let existing = sqlx::query_as::<_, WorkspaceCardColor>(
            r#"SELECT workspace_id, color, revision, updated_at
               FROM workspace_card_colors WHERE workspace_id = ?1"#,
        )
        .bind(workspace_id)
        .fetch_optional(&mut *tx)
        .await?;

        if existing.as_ref().map(|value| value.revision) != input.expected_revision {
            return Err(DurablePreferenceError::Conflict);
        }

        let next_revision = existing.as_ref().map_or(1, |value| value.revision + 1);
        let updated = if let Some(color) = input.color.as_deref() {
            sqlx::query_as::<_, WorkspaceCardColor>(
                r#"INSERT INTO workspace_card_colors (workspace_id, color, revision)
                   VALUES (?1, ?2, ?3)
                   ON CONFLICT(workspace_id) DO UPDATE SET
                       color = excluded.color,
                       revision = excluded.revision,
                       updated_at = datetime('now', 'subsec')
                   RETURNING workspace_id, color, revision, updated_at"#,
            )
            .bind(workspace_id)
            .bind(color)
            .bind(next_revision)
            .fetch_one(&mut *tx)
            .await
            .map(Some)?
        } else {
            sqlx::query("DELETE FROM workspace_card_colors WHERE workspace_id = ?1")
                .bind(workspace_id)
                .execute(&mut *tx)
                .await?;
            None
        };
        sqlx::query(
            r#"INSERT INTO workspace_card_color_history
               (workspace_id, color, revision, deleted)
               VALUES (?1, ?2, ?3, ?4)"#,
        )
        .bind(workspace_id)
        .bind(input.color.as_deref())
        .bind(next_revision)
        .bind(i64::from(input.color.is_none()))
        .execute(&mut *tx)
        .await?;
        tx.commit().await?;
        Ok(updated)
    }
}
