#!/usr/bin/env python3
"""Compile the actual local comment routes without the desktop/runtime graph.

The adapter substitutes only Deployment/ApiError and local participant constants;
SQL, HTTP handlers, migration, validation and inline regressions are product code.
Use --serve PORT to expose disposable SQLite data for browser acceptance.
"""
import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
parser.add_argument('--serve', type=int)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
output = Path(args.output).resolve()
if not str(output).startswith('/mnt/vk-storage/'):
    raise SystemExit('output must be on mounted secondary SSD')
if not os.path.ismount('/mnt/vk-storage'):
    raise SystemExit('secondary SSD is not mounted')
output.mkdir(parents=True, exist_ok=True)
crate = output / 'harness'
(crate / 'src').mkdir(parents=True, exist_ok=True)
(crate / 'Cargo.toml').write_text('''[package]
name = "local-comments-contract"
version = "0.0.0"
edition = "2024"
[workspace]
[profile.dev]
debug = 0
incremental = false
[dependencies]
api-types = {path = "ROOT/crates/api-types"}
axum = "0.8"
tokio = {version = "1", features = ["full"]}
chrono = {version = "0.4", features = ["serde"]}
serde = {version = "1", features = ["derive"]}
serde_json = "1"
sqlx = {version = "0.8.6", features = ["runtime-tokio", "sqlite", "uuid", "chrono"]}
uuid = {version = "1", features = ["v4", "serde"]}
reqwest = {version = "0.12", default-features = false, features = ["json", "rustls-tls"]}
tempfile = "3"
'''.replace('ROOT', str(root)))
source = r'''
extern crate self as deployment;
extern crate self as db;
use sqlx::SqlitePool;
#[derive(Clone)] pub struct DeploymentImpl { pub pool: SqlitePool }
pub trait Deployment { fn db(&self) -> &Self; }
impl Deployment for DeploymentImpl { fn db(&self) -> &Self {self} }
pub mod models { pub mod local_issue_assignee {
    pub const SEAMUS_ID: uuid::Uuid = uuid::Uuid::from_u128(0x5ea00000000040008000000000000001);
} }
pub mod error {
    pub enum ApiError { Database(sqlx::Error), BadRequest(String), Conflict(String) }
    impl From<sqlx::Error> for ApiError { fn from(e: sqlx::Error) -> Self {Self::Database(e)} }
    impl std::fmt::Debug for ApiError {fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {write!(f,"API error")}}
    impl axum::response::IntoResponse for ApiError {
        fn into_response(self)->axum::response::Response {
            use axum::http::StatusCode;
            let (status,message)=match self {
                Self::Database(sqlx::Error::RowNotFound)=>(StatusCode::NOT_FOUND,"Not found".into()),
                Self::Database(e)=>(StatusCode::INTERNAL_SERVER_ERROR,e.to_string()),
                Self::BadRequest(e)=>(StatusCode::BAD_REQUEST,e),
                Self::Conflict(e)=>(StatusCode::CONFLICT,e),
            };
            (status,axum::Json(serde_json::json!({"message":message}))).into_response()
        }
    }
}
#[path = "ROUTE"] mod local_comments;
#[tokio::main] async fn main() {
    let args:Vec<String>=std::env::args().collect();
    let database=&args[1];
    let port=&args[2];
    let pool=sqlx::sqlite::SqlitePoolOptions::new().max_connections(1).connect(database).await.unwrap();
    sqlx::raw_sql("CREATE TABLE IF NOT EXISTS tasks(id BLOB PRIMARY KEY, project_id BLOB); CREATE TABLE IF NOT EXISTS workspaces(id BLOB PRIMARY KEY, task_id BLOB);").execute(&pool).await.unwrap();
    let exists:bool=sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE name='local_issue_comments')").fetch_one(&pool).await.unwrap();
    if !exists {
        sqlx::raw_sql(include_str!("ASSIGNMENT")).execute(&pool).await.unwrap();
        sqlx::raw_sql(include_str!("MIGRATION")).execute(&pool).await.unwrap();
    }
    // Fixed IDs intentionally match the read-only source issue in the browser;
    // only this disposable database receives discussion writes.
    for id in ["b1fcd23b-b6b0-440c-80dd-ac646dbbec09","0da02ba1-7d50-4461-9a9b-0701e341c753"] {
        sqlx::query("INSERT OR IGNORE INTO tasks VALUES (?, ?)").bind(id.parse::<uuid::Uuid>().unwrap()).bind(uuid::Uuid::nil()).execute(&pool).await.unwrap();
    }
    let app=axum::Router::new().nest("/v1",local_comments::router().merge(local_comments::api_fallback()).with_state(DeploymentImpl{pool}));
    let listener=tokio::net::TcpListener::bind(format!("127.0.0.1:{port}")).await.unwrap();
    println!("Disposable comment routes ready on {}",listener.local_addr().unwrap());
    axum::serve(listener,app).await.unwrap();
}
'''
source = source.replace('ROUTE', str(root / 'crates/server/src/routes/local_comments.rs')).replace('ASSIGNMENT', str(root / 'crates/db/migrations/20261009000000_local_issue_assignments.sql')).replace('MIGRATION', str(root / 'crates/db/migrations/20261026193000_local_issue_comments.sql'))
(crate / 'src/main.rs').write_text(source)
if not (crate / 'Cargo.lock').exists():
    (crate / 'Cargo.lock').write_bytes((root / 'Cargo.lock').read_bytes())
env = {**os.environ, 'CARGO_TARGET_DIR': '/home/mcp/.local/share/vibe-kanban-green-build/cargo-target', 'CARGO_INCREMENTAL': '0', 'TMPDIR': str(output)}
cmd = ['cargo', 'run', '--offline', '--manifest-path', str(crate / 'Cargo.toml'), '--', f'sqlite://{output}/browser.sqlite3?mode=rwc', str(args.serve)] if args.serve else ['cargo', 'test', '--offline', '--manifest-path', str(crate / 'Cargo.toml')]
raise SystemExit(subprocess.call(cmd, env=env))
