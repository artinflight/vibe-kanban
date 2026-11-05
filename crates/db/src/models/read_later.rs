//! Per-item durable bookmarks; never reads or updates workspace read/attention state.
use serde::{Deserialize, Serialize};
use sqlx::{Row, SqlitePool};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ReadLaterKind {
    Workspace,
    Project,
    Issue,
    Notification,
}

impl ReadLaterKind {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Workspace => "workspace",
            Self::Project => "project",
            Self::Issue => "issue",
            Self::Notification => "notification",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ReadLaterItem {
    pub kind: ReadLaterKind,
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_id: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ReadLaterRecord {
    pub item: ReadLaterItem,
    pub saved: bool,
    pub revision: i64,
}

impl ReadLaterRecord {
    pub async fn list(pool: &SqlitePool, scope: &str) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query(
            "SELECT item_json, saved, revision FROM read_later_preferences WHERE user_scope = ?1",
        )
        .bind(scope)
        .fetch_all(pool)
        .await?
        .into_iter()
        .map(|row| {
            Ok(Self {
                item: serde_json::from_str(row.get("item_json"))
                    .map_err(|error| sqlx::Error::Decode(Box::new(error)))?,
                saved: row.get("saved"),
                revision: row.get("revision"),
            })
        })
        .collect()
    }

    /// Each explicit action updates one item, so two devices editing different
    /// bookmarks cannot replace each other's list. Last committed action wins.
    pub async fn set(
        pool: &SqlitePool,
        scope: &str,
        item: &ReadLaterItem,
        saved: bool,
        change_id: &str,
    ) -> Result<(), sqlx::Error> {
        let json =
            serde_json::to_string(item).map_err(|error| sqlx::Error::Encode(Box::new(error)))?;
        let mut tx = pool.begin().await?;
        let receipt = sqlx::query("INSERT INTO read_later_action_receipts (user_scope, change_id) VALUES (?1, ?2) ON CONFLICT DO NOTHING")
            .bind(scope).bind(change_id).execute(&mut *tx).await?;
        if receipt.rows_affected() == 0 {
            return Ok(());
        }
        sqlx::query(
            "INSERT INTO read_later_preferences (user_scope, item_kind, item_id, item_json, saved)
             VALUES (?1, ?2, ?3, ?4, ?5)
             ON CONFLICT(user_scope, item_kind, item_id) DO UPDATE SET
               item_json = excluded.item_json, saved = excluded.saved,
               revision = read_later_preferences.revision + 1,
               updated_at = datetime('now', 'subsec')",
        )
        .bind(scope)
        .bind(item.kind.as_str())
        .bind(&item.id)
        .bind(json)
        .bind(saved)
        .execute(&mut *tx)
        .await?;
        tx.commit().await
    }

    /// Import browser-local bookmarks once without overwriting server choices,
    /// including removals. A transaction keeps a failed import retryable.
    pub async fn import(
        pool: &SqlitePool,
        scope: &str,
        items: &[ReadLaterItem],
    ) -> Result<(), sqlx::Error> {
        let mut tx = pool.begin().await?;
        for item in items {
            let json = serde_json::to_string(item)
                .map_err(|error| sqlx::Error::Encode(Box::new(error)))?;
            sqlx::query(
                "INSERT INTO read_later_preferences
                   (user_scope, item_kind, item_id, item_json, saved)
                 VALUES (?1, ?2, ?3, ?4, 1)
                 ON CONFLICT(user_scope, item_kind, item_id) DO NOTHING",
            )
            .bind(scope)
            .bind(item.kind.as_str())
            .bind(&item.id)
            .bind(json)
            .execute(&mut *tx)
            .await?;
        }
        tx.commit().await
    }
}

#[cfg(test)]
mod tests {
    use sqlx::sqlite::SqlitePoolOptions;

    use super::*;

    fn item(id: &str) -> ReadLaterItem {
        ReadLaterItem {
            kind: ReadLaterKind::Workspace,
            id: id.into(),
            name: Some("Premiere Pro to mobile".into()),
            project_id: None,
        }
    }

    #[tokio::test]
    async fn devices_share_choices_and_old_import_cannot_resurrect_removals() {
        let dir = tempfile::tempdir().unwrap();
        let url = format!(
            "sqlite://{}?mode=rwc",
            dir.path().join("bookmarks.sqlite").display()
        );
        let desktop = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .unwrap();
        sqlx::raw_sql(include_str!(
            "../../migrations/20261105110000_read_later_preferences.sql"
        ))
        .execute(&desktop)
        .await
        .unwrap();
        // Read flags live in a separate table; neither imports nor actions touch it.
        sqlx::query("CREATE TABLE workspaces (id TEXT PRIMARY KEY, unread INTEGER)")
            .execute(&desktop)
            .await
            .unwrap();
        sqlx::query("INSERT INTO workspaces VALUES ('premiere', 1)")
            .execute(&desktop)
            .await
            .unwrap();
        let mobile = SqlitePoolOptions::new()
            .max_connections(1)
            .connect(&url)
            .await
            .unwrap();
        ReadLaterRecord::import(&desktop, "owner", &[item("premiere")])
            .await
            .unwrap();
        ReadLaterRecord::set(&desktop, "owner", &item("premiere"), true, "save")
            .await
            .unwrap();
        assert!(ReadLaterRecord::list(&mobile, "owner").await.unwrap()[0].saved);
        ReadLaterRecord::set(&mobile, "owner", &item("premiere"), false, "remove")
            .await
            .unwrap();
        ReadLaterRecord::import(&desktop, "owner", &[item("premiere")])
            .await
            .unwrap();
        // Retry a save whose response was lost after the mobile removal.
        ReadLaterRecord::set(&desktop, "owner", &item("premiere"), true, "save")
            .await
            .unwrap();
        let rows = ReadLaterRecord::list(&desktop, "owner").await.unwrap();
        assert!(!rows[0].saved);
        assert_eq!(rows[0].revision, 3);
        ReadLaterRecord::set(&desktop, "owner", &item("second"), true, "second")
            .await
            .unwrap();
        ReadLaterRecord::set(&mobile, "owner", &item("third"), true, "third")
            .await
            .unwrap();
        assert_eq!(
            ReadLaterRecord::list(&mobile, "owner").await.unwrap().len(),
            3
        );
        assert!(
            ReadLaterRecord::list(&mobile, "other-user")
                .await
                .unwrap()
                .is_empty()
        );
        assert_eq!(
            sqlx::query_scalar::<_, i64>("SELECT unread FROM workspaces WHERE id = 'premiere'")
                .fetch_one(&desktop)
                .await
                .unwrap(),
            1
        );
        desktop.close().await;
        mobile.close().await;
        let reopened = SqlitePoolOptions::new().connect(&url).await.unwrap();
        assert_eq!(
            ReadLaterRecord::list(&reopened, "owner")
                .await
                .unwrap()
                .len(),
            3
        );
    }
}
