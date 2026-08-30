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
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct UpsertSavedChatMessage {
    pub id: String,
    pub title: String,
    pub content: String,
    pub position: i64,
}

impl SavedChatMessage {
    pub async fn find_all(pool: &SqlitePool) -> Result<Vec<Self>, sqlx::Error> {
        sqlx::query_as::<_, Self>(
            r#"SELECT id, title, content, position, created_at, updated_at
               FROM saved_chat_messages
               ORDER BY position ASC, created_at ASC, id ASC"#,
        )
        .fetch_all(pool)
        .await
    }

    pub async fn upsert(
        pool: &SqlitePool,
        input: &UpsertSavedChatMessage,
    ) -> Result<Self, sqlx::Error> {
        sqlx::query_as::<_, Self>(
            r#"INSERT INTO saved_chat_messages (id, title, content, position)
               VALUES (?1, ?2, ?3, ?4)
               ON CONFLICT(id) DO UPDATE SET
                   title = excluded.title,
                   content = excluded.content,
                   position = excluded.position,
                   updated_at = datetime('now', 'subsec')
               RETURNING id, title, content, position, created_at, updated_at"#,
        )
        .bind(&input.id)
        .bind(input.title.trim())
        .bind(&input.content)
        .bind(input.position)
        .fetch_one(pool)
        .await
    }

    pub async fn delete(pool: &SqlitePool, id: &str) -> Result<u64, sqlx::Error> {
        Ok(sqlx::query("DELETE FROM saved_chat_messages WHERE id = ?1")
            .bind(id)
            .execute(pool)
            .await?
            .rows_affected())
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
        };
        SavedChatMessage::upsert(&pool, &first).await.unwrap();
        let second = UpsertSavedChatMessage {
            id: "message-2".to_string(),
            title: "Second".to_string(),
            content: "two".to_string(),
            position: 1,
        };
        SavedChatMessage::upsert(&pool, &second).await.unwrap();

        let updated = UpsertSavedChatMessage {
            content: "updated".to_string(),
            ..first
        };
        SavedChatMessage::upsert(&pool, &updated).await.unwrap();

        let messages = SavedChatMessage::find_all(&pool).await.unwrap();
        assert_eq!(messages.len(), 2);
        assert_eq!(messages[0].title, "First");
        assert_eq!(messages[0].content, "updated");

        assert_eq!(
            SavedChatMessage::delete(&pool, "message-1").await.unwrap(),
            1
        );
        let messages = SavedChatMessage::find_all(&pool).await.unwrap();
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0].id, "message-2");
    }
}
