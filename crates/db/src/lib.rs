use std::{str::FromStr, sync::Arc, time::Duration};

use sqlx::{
    ConnectOptions, Error, Pool, Sqlite,
    migrate::MigrateError,
    sqlite::{SqliteConnectOptions, SqliteConnection, SqliteJournalMode, SqlitePoolOptions},
};
use utils::assets::asset_dir;

pub mod models;

async fn run_migrations(pool: &Pool<Sqlite>) -> Result<(), Error> {
    use std::collections::HashSet;

    let migrator = sqlx::migrate!("./migrations");
    let mut processed_versions: HashSet<i64> = HashSet::new();

    loop {
        match migrator.run(pool).await {
            Ok(()) => return Ok(()),
            Err(MigrateError::VersionMismatch(version)) => {
                if cfg!(debug_assertions) {
                    // return the error in debug mode to catch migration issues early
                    return Err(sqlx::Error::Migrate(Box::new(
                        MigrateError::VersionMismatch(version),
                    )));
                }

                if !cfg!(windows) {
                    // On non-Windows platforms, we do not attempt to auto-fix checksum mismatches
                    return Err(sqlx::Error::Migrate(Box::new(
                        MigrateError::VersionMismatch(version),
                    )));
                }

                // Guard against infinite loop
                if !processed_versions.insert(version) {
                    return Err(sqlx::Error::Migrate(Box::new(
                        MigrateError::VersionMismatch(version),
                    )));
                }

                // On Windows, there can be checksum mismatches due to line ending differences
                // or other platform-specific issues. Update the stored checksum and retry.
                tracing::warn!(
                    "Migration version {} has checksum mismatch, updating stored checksum (likely platform-specific difference)",
                    version
                );

                // Find the migration with the mismatched version and get its current checksum
                if let Some(migration) = migrator.iter().find(|m| m.version == version) {
                    // Update the checksum in _sqlx_migrations to match the current file
                    sqlx::query("UPDATE _sqlx_migrations SET checksum = ? WHERE version = ?")
                        .bind(&*migration.checksum)
                        .bind(version)
                        .execute(pool)
                        .await?;
                } else {
                    // Migration not found in current set, can't fix
                    return Err(sqlx::Error::Migrate(Box::new(
                        MigrateError::VersionMismatch(version),
                    )));
                }
            }
            Err(e) => return Err(e.into()),
        }
    }
}

#[derive(Clone)]
pub struct DBService {
    pub pool: Pool<Sqlite>,
}

impl DBService {
    /// Read intrinsic identity without migrations, creation or a writable connection.
    /// Filesystem pins alone cannot detect an in-place dataset replacement.
    pub async fn verify_dataset_identity(
        database: &std::path::Path,
        expected: &str,
    ) -> std::io::Result<()> {
        // Filesystem pins alone cannot detect an in-place replacement/truncation.
        // Read the intrinsic dataset token through a read-only connection before any
        // migration/configuration write. Never provision missing identity at startup.
        use sqlx::Connection;
        let options = sqlx::sqlite::SqliteConnectOptions::new()
            .filename(database)
            .read_only(true)
            .create_if_missing(false);
        let mut connection = sqlx::SqliteConnection::connect_with(&options)
            .await
            .map_err(|e| std::io::Error::other(format!("cannot read dataset identity: {e}")))?;
        let ids = sqlx::query_scalar::<_, String>(
            "SELECT dataset_id FROM vk_runtime_identity WHERE singleton = 1",
        )
        .fetch_all(&mut connection)
        .await
        .map_err(|e| std::io::Error::other(format!("dataset identity is not established: {e}")))?;
        connection.close().await.map_err(std::io::Error::other)?;
        if ids.len() != 1 || ids[0] != expected {
            return Err(std::io::Error::new(
                std::io::ErrorKind::PermissionDenied,
                "database dataset identity does not match the pinned runtime",
            ));
        }
        Ok(())
    }

    pub async fn new() -> Result<DBService, Error> {
        let database_url = format!(
            "sqlite://{}",
            asset_dir().join("db.v2.sqlite").to_string_lossy()
        );
        let options = SqliteConnectOptions::from_str(&database_url)?
            .create_if_missing(true)
            .journal_mode(SqliteJournalMode::Wal)
            .busy_timeout(Duration::from_secs(15));
        let pool = SqlitePoolOptions::new()
            .max_connections(8)
            .connect_with(options)
            .await?;
        run_migrations(&pool).await?;
        Ok(DBService { pool })
    }

    pub async fn new_migration_pool() -> Result<Pool<Sqlite>, Error> {
        let database_url = format!(
            "sqlite://{}",
            asset_dir().join("db.v2.sqlite").to_string_lossy()
        );
        let options = SqliteConnectOptions::from_str(&database_url)?
            .create_if_missing(true)
            .journal_mode(SqliteJournalMode::Wal)
            .busy_timeout(Duration::from_secs(15))
            .disable_statement_logging();
        SqlitePoolOptions::new()
            .max_connections(8)
            .connect_with(options)
            .await
    }

    pub async fn new_with_after_connect<F>(after_connect: F) -> Result<DBService, Error>
    where
        F: for<'a> Fn(
                &'a mut SqliteConnection,
            ) -> std::pin::Pin<
                Box<dyn std::future::Future<Output = Result<(), Error>> + Send + 'a>,
            > + Send
            + Sync
            + 'static,
    {
        let pool = Self::create_pool(Some(Arc::new(after_connect))).await?;
        Ok(DBService { pool })
    }

    async fn create_pool<F>(after_connect: Option<Arc<F>>) -> Result<Pool<Sqlite>, Error>
    where
        F: for<'a> Fn(
                &'a mut SqliteConnection,
            ) -> std::pin::Pin<
                Box<dyn std::future::Future<Output = Result<(), Error>> + Send + 'a>,
            > + Send
            + Sync
            + 'static,
    {
        let database_url = format!(
            "sqlite://{}",
            asset_dir().join("db.v2.sqlite").to_string_lossy()
        );
        let options = SqliteConnectOptions::from_str(&database_url)?
            .create_if_missing(true)
            .journal_mode(SqliteJournalMode::Wal)
            .busy_timeout(Duration::from_secs(15));

        let pool = if let Some(hook) = after_connect {
            SqlitePoolOptions::new()
                .max_connections(8)
                .after_connect(move |conn, _meta| {
                    let hook = hook.clone();
                    Box::pin(async move {
                        hook(conn).await?;
                        Ok(())
                    })
                })
                .connect_with(options)
                .await?
        } else {
            SqlitePoolOptions::new()
                .max_connections(8)
                .connect_with(options)
                .await?
        };

        run_migrations(&pool).await?;
        Ok(pool)
    }
}
