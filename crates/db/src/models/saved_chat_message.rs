use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{FromRow, SqlitePool};
use ts_rs::TS;

#[derive(Debug, Clone, Serialize, Deserialize, TS, FromRow)]
pub struct SavedChatMessage {
    pub id: String,
    pub title: String,
    pub content: String,
    pub position: i64,
    pub revision: i64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct UpsertSavedChatMessage {
    pub id: String,
    pub title: String,
    pub content: String,
    pub position: i64,
    #[serde(default)]
    pub expected_revision: Option<i64>,
}

#[derive(Debug, thiserror::Error)]
pub enum SavedChatMessageError {
    #[error("Saved message revision conflict")]
    Conflict,
    #[error(transparent)]
    Database(#[from] sqlx::Error),
}

impl SavedChatMessage {
    pub async fn find_all(pool: &SqlitePool) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as::<_, Self>(
            r#"SELECT id, title, content, position, revision, created_at, updated_at
               FROM saved_chat_messages
               ORDER BY position ASC, created_at ASC, id ASC"#,
        )
        .fetch_all(pool)
        .await
    }

    pub async fn upsert(
        pool: &SqlitePool,
        input: &UpsertSavedChatMessage,
    ) -> Result<Self, SavedChatMessageError> {
        let result = if let Some(expected_revision) = input.expected_revision {
            sqlx::query_as::<_, Self>(
                r#"UPDATE saved_chat_messages SET
                   title = ?2, content = ?3, position = ?4,
                   revision = revision + 1,
                   updated_at = datetime('now', 'subsec')
               WHERE id = ?1 AND revision = ?5
               RETURNING id, title, content, position, revision, created_at, updated_at"#,
            )
            .bind(&input.id)
            .bind(input.title.trim())
            .bind(&input.content)
            .bind(input.position)
            .bind(expected_revision)
            .fetch_optional(pool)
            .await
        } else {
            sqlx::query_as::<_, Self>(
                r#"INSERT INTO saved_chat_messages (id, title, content, position)
               VALUES (?1, ?2, ?3, ?4)
               RETURNING id, title, content, position, revision, created_at, updated_at"#,
            )
            .bind(&input.id)
            .bind(input.title.trim())
            .bind(&input.content)
            .bind(input.position)
            .fetch_optional(pool)
            .await
        };
        match result {
            Ok(Some(message)) => Ok(message),
            Ok(None) => Err(SavedChatMessageError::Conflict),
            Err(sqlx::Error::Database(error)) if error.is_unique_violation() => {
                Err(SavedChatMessageError::Conflict)
            }
            Err(error) => Err(error.into()),
        }
    }

    pub async fn delete(
        pool: &SqlitePool,
        id: &str,
        expected_revision: Option<i64>,
    ) -> Result<u64, SavedChatMessageError> {
        let Some(expected_revision) = expected_revision else {
            let exists = sqlx::query_scalar::<_, bool>(
                "SELECT EXISTS(SELECT 1 FROM saved_chat_messages WHERE id = ?1)",
            )
            .bind(id)
            .fetch_one(pool)
            .await?;
            return if exists {
                Err(SavedChatMessageError::Conflict)
            } else {
                Ok(0)
            };
        };
        let deleted =
            sqlx::query("DELETE FROM saved_chat_messages WHERE id = ?1 AND revision = ?2")
                .bind(id)
                .bind(expected_revision)
                .execute(pool)
                .await?
                .rows_affected();
        if deleted == 0 {
            return Err(SavedChatMessageError::Conflict);
        }
        Ok(deleted)
    }
}

#[cfg(test)]
mod tests {
    use sqlx::sqlite::SqlitePoolOptions;

    use super::*;

    #[tokio::test]
    async fn saved_messages_are_independently_upserted_and_deleted() {
        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect("sqlite::memory:")
            .await
            .unwrap();
        sqlx::query(
            r#"CREATE TABLE saved_chat_messages (
                id TEXT PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
            )"#,
        )
        .execute(&pool)
        .await
        .unwrap();

        let first = UpsertSavedChatMessage {
            id: "message-1".to_string(),
            title: " First ".to_string(),
            content: "one".to_string(),
            position: 0,
            expected_revision: None,
        };
        SavedChatMessage::upsert(&pool, &first).await.unwrap();
        let second = UpsertSavedChatMessage {
            id: "message-2".to_string(),
            title: "Second".to_string(),
            content: "two".to_string(),
            position: 1,
            expected_revision: None,
        };
        SavedChatMessage::upsert(&pool, &second).await.unwrap();

        let stale = UpsertSavedChatMessage {
            content: "stale".to_string(),
            expected_revision: None,
            ..first.clone()
        };
        assert!(matches!(
            SavedChatMessage::upsert(&pool, &stale).await,
            Err(SavedChatMessageError::Conflict)
        ));

        let updated = UpsertSavedChatMessage {
            content: "updated".to_string(),
            expected_revision: Some(1),
            ..first
        };
        SavedChatMessage::upsert(&pool, &updated).await.unwrap();

        let messages = SavedChatMessage::find_all(&pool).await.unwrap();
        assert_eq!(messages.len(), 2);
        assert_eq!(messages[0].title, "First");
        assert_eq!(messages[0].content, "updated");

        assert_eq!(
            SavedChatMessage::delete(&pool, "message-1", Some(2))
                .await
                .unwrap(),
            1
        );
        let messages = SavedChatMessage::find_all(&pool).await.unwrap();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0].id, "message-2");
    }
}
