use std::collections::HashMap;

use chrono::{Duration as ChronoDuration, TimeZone, Utc};
use sqlx::{SqlitePool, sqlite::SqlitePoolOptions};
use uuid::Uuid;

use super::*;

async fn memory_pool() -> SqlitePool {
    SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap()
}

fn event(kind: &str, timestamp: &str) -> String {
    format!(
        "{{\"timestamp\":\"{timestamp}\",\"type\":\"event_msg\",\"payload\":{{\"type\":\"{kind}\",\"turn_id\":\"test-turn\"}}}}\n"
    )
}

async fn resolved_jobs(
    vk: &SqlitePool,
    codex: &SqlitePool,
    session: Uuid,
    persisted: Vec<SubagentJob>,
) -> Vec<SubagentJob> {
    let roots = find_agent_threads_for_sessions(vk, &[session])
        .await
        .unwrap();
    let children = find_codex_thread_jobs_in_pool(codex, roots).await.unwrap();
    reconcile_codex_jobs(persisted, children)
}

fn counts(jobs: &[SubagentJob], session: Uuid) -> (usize, usize) {
    let mut counts = HashMap::new();
    for job in jobs {
        increment_active_count(&mut counts, job.session_id, &job.status);
    }
    let count = counts.get(&session).cloned().unwrap_or_default();
    (count.running, count.unresolved)
}

#[tokio::test]
async fn autoswitch_resumed_parent_open_child_completion_and_followup() {
    let vk = memory_pool().await;
    let codex = memory_pool().await;
    let session = Uuid::new_v4();
    let old_execution = Uuid::new_v4();
    let new_execution = Uuid::new_v4();
    sqlx::raw_sql("CREATE TABLE execution_processes (id BLOB, session_id BLOB, dropped BOOLEAN, created_at TEXT, completed_at TEXT);
        CREATE TABLE coding_agent_turns (execution_process_id BLOB, agent_session_id TEXT);").execute(&vk).await.unwrap();
    // The newest completed execution has no agent_session_id, exactly as in
    // AutoSwitch. The only root association predates the child's final turn.
    for (execution, created, completed, root) in [
        (
            old_execution,
            "2026-10-14T20:00:00Z",
            "2026-10-14T20:51:31Z",
            Some("root"),
        ),
        (
            new_execution,
            "2026-10-15T21:00:00Z",
            "2026-10-15T21:24:51Z",
            None,
        ),
    ] {
        sqlx::query("INSERT INTO execution_processes VALUES (?, ?, FALSE, ?, ?)")
            .bind(execution)
            .bind(session)
            .bind(created)
            .bind(completed)
            .execute(&vk)
            .await
            .unwrap();
        sqlx::query("INSERT INTO coding_agent_turns VALUES (?, ?)")
            .bind(execution)
            .bind(root)
            .execute(&vk)
            .await
            .unwrap();
    }
    sqlx::raw_sql("CREATE TABLE thread_spawn_edges (parent_thread_id TEXT, child_thread_id TEXT, status TEXT);
        CREATE TABLE threads (id TEXT, agent_nickname TEXT, rollout_path TEXT, created_at_ms INTEGER, updated_at_ms INTEGER);
        INSERT INTO thread_spawn_edges VALUES ('root', 'reviewer', 'open');").execute(&codex).await.unwrap();
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("reviewer.jsonl");
    let transcript = event("task_started", "2026-10-15T21:00:01Z")
        + &event("task_complete", "2026-10-15T21:23:10.628Z");
    tokio::fs::write(&path, &transcript).await.unwrap();
    let child_updated = Utc.with_ymd_and_hms(2026, 10, 15, 21, 23, 10).unwrap();
    sqlx::query("INSERT INTO threads VALUES ('reviewer', 'autoswitch_release_review', ?, ?, ?)")
        .bind(path.to_str().unwrap())
        .bind(child_updated.timestamp_millis())
        .bind(child_updated.timestamp_millis())
        .execute(&codex)
        .await
        .unwrap();

    let mut stale = SubagentJob {
        id: Uuid::new_v4(),
        session_id: session,
        execution_process_id: old_execution,
        agent_id: "reviewer".into(),
        nickname: None,
        status: SubagentJobStatus::Running,
        completed_at: None,
        created_at: child_updated,
        updated_at: child_updated,
    };
    let jobs = resolved_jobs(&vk, &codex, session, vec![stale.clone()]).await;
    assert_eq!(counts(&jobs, session), (0, 0));
    assert_eq!(jobs[0].status, SubagentJobStatus::Completed);
    assert_eq!(
        jobs[0].completed_at.unwrap().timestamp_millis(),
        1792099390628
    );
    assert_eq!(tokio::fs::read_to_string(&path).await.unwrap(), transcript);
    let edge: String = sqlx::query_scalar("SELECT status FROM thread_spawn_edges")
        .fetch_one(&codex)
        .await
        .unwrap();
    assert_eq!(
        edge, "open",
        "status reads must not mutate Codex's thread graph"
    );

    // A later turn on the same child must override an earlier persisted
    // completion, even when the Codex SQLite updated_at has not advanced.
    stale.status = SubagentJobStatus::Completed;
    // A delayed wait result may be recorded after the next child turn starts.
    // Its database write timestamp is not the child's completion timestamp.
    stale.completed_at = Some(Utc.with_ymd_and_hms(2026, 10, 16, 9, 0, 1).unwrap());
    let resumed = transcript + &event("task_started", "2026-10-16T09:00:00Z");
    tokio::fs::write(&path, &resumed).await.unwrap();
    let jobs = resolved_jobs(&vk, &codex, session, vec![stale.clone()]).await;
    assert_eq!(counts(&jobs, session), (1, 0));

    // An explicit close acknowledged after that start remains terminal.
    stale.status = SubagentJobStatus::Failed;
    stale.completed_at = Some(Utc.with_ymd_and_hms(2026, 10, 16, 9, 1, 0).unwrap());
    let jobs = resolved_jobs(&vk, &codex, session, vec![stale]).await;
    assert_eq!(counts(&jobs, session), (0, 0));
    assert_eq!(jobs[0].status, SubagentJobStatus::Failed);

    tokio::fs::write(
        &path,
        resumed + &event("turn_aborted", "2026-10-16T09:02:00Z"),
    )
    .await
    .unwrap();
    let jobs = resolved_jobs(&vk, &codex, session, vec![]).await;
    assert_eq!(counts(&jobs, session), (0, 0));
    assert_eq!(jobs[0].status, SubagentJobStatus::Failed);

    // Unreadable evidence stays visible as uncertain; it is never guessed
    // complete from an old parent timestamp. Closed edges still stay terminal.
    tokio::fs::remove_file(&path).await.unwrap();
    let jobs = resolved_jobs(&vk, &codex, session, vec![]).await;
    assert_eq!(counts(&jobs, session), (0, 1));
    sqlx::query("UPDATE thread_spawn_edges SET status = 'closed'")
        .execute(&codex)
        .await
        .unwrap();
    let jobs = resolved_jobs(&vk, &codex, session, vec![]).await;
    assert_eq!(counts(&jobs, session), (0, 0));
}

#[test]
fn same_child_in_different_sessions_keeps_both_counts() {
    let now = Utc::now();
    let first = SubagentJob {
        id: Uuid::new_v4(),
        session_id: Uuid::new_v4(),
        execution_process_id: Uuid::new_v4(),
        agent_id: "shared-child".into(),
        nickname: None,
        status: SubagentJobStatus::Running,
        completed_at: None,
        created_at: now,
        updated_at: now,
    };
    let mut second = first.clone();
    second.session_id = Uuid::new_v4();
    second.updated_at += ChronoDuration::seconds(1);
    let jobs = deduplicate_jobs(vec![first.clone(), second.clone()]);
    assert_eq!(counts(&jobs, first.session_id), (1, 0));
    assert_eq!(counts(&jobs, second.session_id), (1, 0));
}

#[tokio::test]
async fn watcher_requires_complete_closed_producer_graph_at_every_depth() {
    let pool = memory_pool().await;
    sqlx::raw_sql("CREATE TABLE threads(id TEXT); CREATE TABLE thread_spawn_edges(parent_thread_id TEXT,child_thread_id TEXT,status TEXT);").execute(&pool).await.unwrap();
    let roots = vec![SessionAgentThreadRow {
        session_id: Uuid::new_v4(),
        execution_process_id: Uuid::new_v4(),
        agent_session_id: "root".into(),
    }];
    assert!(
        !closed_spawn_graph(&pool, &roots).await.unwrap(),
        "missing root is unknown"
    );
    sqlx::raw_sql("INSERT INTO threads VALUES ('root'); INSERT INTO thread_spawn_edges VALUES ('root','child','open');").execute(&pool).await.unwrap();
    assert!(
        !closed_spawn_graph(&pool, &roots).await.unwrap(),
        "open child remains a producer even after task_complete"
    );
    sqlx::query("UPDATE thread_spawn_edges SET status='closed'")
        .execute(&pool)
        .await
        .unwrap();
    assert!(closed_spawn_graph(&pool, &roots).await.unwrap());
    // Walk beyond the activity UI's four-level display horizon.
    for n in 0..8 {
        sqlx::query("INSERT INTO thread_spawn_edges VALUES (?,?,?)")
            .bind(if n == 0 {
                "child".into()
            } else {
                format!("child{n}")
            })
            .bind(format!("child{}", n + 1))
            .bind(if n == 7 { "open" } else { "closed" })
            .execute(&pool)
            .await
            .unwrap();
    }
    assert!(!closed_spawn_graph(&pool, &roots).await.unwrap());
    sqlx::query("UPDATE thread_spawn_edges SET status='closed'")
        .execute(&pool)
        .await
        .unwrap();
    assert!(closed_spawn_graph(&pool, &roots).await.unwrap());
    sqlx::query("DROP TABLE thread_spawn_edges")
        .execute(&pool)
        .await
        .unwrap();
    assert!(
        closed_spawn_graph(&pool, &roots).await.is_err(),
        "unreadable inventory never grants admission"
    );
}
