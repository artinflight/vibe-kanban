use std::time::Duration;

use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions};

use super::*;

async fn database() -> SqlitePool {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    // Exercise the actual additive migration, not a test-only replica.
    sqlx::raw_sql(include_str!(
        "../../../migrations/20260926000000_supervisor_conversation_foundation.sql"
    ))
    .execute(&pool)
    .await
    .unwrap();
    pool
}

fn scope() -> ConversationScope {
    ConversationScope {
        authority_id: Uuid::new_v4(),
        principal_id: Uuid::new_v4(),
    }
}

fn input(body: &str) -> AcceptConversationMessage {
    AcceptConversationMessage {
        client_message_id: Uuid::new_v4(),
        body: body.to_owned(),
        origin: ConversationInputOrigin::Typed,
        reply_to_id: None,
    }
}

#[tokio::test]
async fn resolve_and_accept_are_idempotent_without_losing_original_text() {
    let store = ConversationStore::new(database().await, scope());
    let conversation = store.resolve().await.unwrap();
    assert_eq!(store.resolve().await.unwrap().id, conversation.id);
    let request = input(" Keep this exact instruction.\n");
    let first = store.accept(conversation.id, &request).await.unwrap();
    let retry = store.accept(conversation.id, &request).await.unwrap();
    assert_eq!(first.message.id, retry.message.id);
    assert_eq!(first.run.id, retry.run.id);
    assert_eq!(first.message.body, request.body);
    assert_eq!(store.get(conversation.id).await.unwrap().next_seq, 3);
    assert_eq!(
        store.events(conversation.id, 0, 200).await.unwrap().len(),
        2
    );
    for conflicting in [
        AcceptConversationMessage {
            body: "Different instruction".into(),
            ..request.clone()
        },
        AcceptConversationMessage {
            origin: ConversationInputOrigin::Voice,
            ..request.clone()
        },
        AcceptConversationMessage {
            reply_to_id: Some(first.message.id),
            ..request.clone()
        },
    ] {
        assert!(matches!(
            store.accept(conversation.id, &conflicting).await,
            Err(ConversationError::IdempotencyConflict)
        ));
    }
    let run = store
        .claim_next(conversation.id, Uuid::new_v4())
        .await
        .unwrap()
        .unwrap();
    store
        .complete(&run, "I have the instruction.")
        .await
        .unwrap();
    let retry = store.accept(conversation.id, &request).await.unwrap();
    assert_eq!(retry.run.status, "completed");
    assert_eq!(retry.message.id, first.message.id);
}

#[tokio::test]
async fn scope_is_required_for_reads_writes_and_replies() {
    let pool = database().await;
    let owner_scope = scope();
    let owner = ConversationStore::new(pool.clone(), owner_scope);
    let conversation = owner.resolve().await.unwrap();
    let accepted = owner
        .accept(conversation.id, &input("Private instruction"))
        .await
        .unwrap();
    for other_scope in [
        ConversationScope {
            principal_id: Uuid::new_v4(),
            ..owner_scope
        },
        ConversationScope {
            authority_id: Uuid::new_v4(),
            ..owner_scope
        },
    ] {
        let other = ConversationStore::new(pool.clone(), other_scope);
        assert!(matches!(
            other.get(conversation.id).await,
            Err(ConversationError::NotFound)
        ));
        assert!(matches!(
            other.events(conversation.id, 0, 10).await,
            Err(ConversationError::NotFound)
        ));
        assert!(matches!(
            other.messages(conversation.id, None, 10).await,
            Err(ConversationError::NotFound)
        ));
        assert!(matches!(
            other.accept(conversation.id, &input("intrusion")).await,
            Err(ConversationError::NotFound)
        ));
        assert!(matches!(
            other.claim_next(conversation.id, Uuid::new_v4()).await,
            Err(ConversationError::NotFound)
        ));
        assert!(matches!(
            other.cancel(conversation.id, accepted.run.id).await,
            Err(ConversationError::NotFound)
        ));
        let theirs = other.resolve().await.unwrap();
        let mut reply = input("Cross-conversation reply");
        reply.reply_to_id = Some(accepted.message.id);
        assert!(matches!(
            other.accept(theirs.id, &reply).await,
            Err(ConversationError::NotFound)
        ));
        assert_eq!(other.get(theirs.id).await.unwrap().next_seq, 1);
    }
}

#[tokio::test]
async fn sequence_pagination_remains_stable_after_new_writes() {
    let store = ConversationStore::new(database().await, scope());
    let conversation = store.resolve().await.unwrap();
    let mut ids = Vec::new();
    for text in ["first", "second", "third", "fourth"] {
        ids.push(
            store
                .accept(conversation.id, &input(text))
                .await
                .unwrap()
                .message
                .id,
        );
    }
    let latest = store.messages(conversation.id, None, 2).await.unwrap();
    assert_eq!(latest.iter().map(|m| m.id).collect::<Vec<_>>(), ids[2..]);
    store
        .accept(conversation.id, &input("newer"))
        .await
        .unwrap();
    let older = store
        .messages(conversation.id, Some(latest[0].created_seq), 2)
        .await
        .unwrap();
    assert_eq!(older.iter().map(|m| m.id).collect::<Vec<_>>(), ids[..2]);
    let events = store.events(conversation.id, 4, 200).await.unwrap();
    assert_eq!(
        events.iter().map(|e| e.seq).collect::<Vec<_>>(),
        vec![5, 6, 7, 8, 9, 10]
    );
    assert_eq!(
        serde_json::from_str::<ConversationMessage>(&events[0].payload)
            .unwrap()
            .id,
        ids[2]
    );
}

#[tokio::test]
async fn failed_event_commit_rolls_back_message_run_and_sequence() {
    let pool = database().await;
    let store = ConversationStore::new(pool.clone(), scope());
    let conversation = store.resolve().await.unwrap();
    sqlx::query("CREATE TRIGGER reject_event BEFORE INSERT ON conversation_events BEGIN SELECT RAISE(ABORT, 'injected write failure'); END")
        .execute(&pool).await.unwrap();
    let request = input("Must not be partially accepted");
    assert!(store.accept(conversation.id, &request).await.is_err());
    assert!(
        store
            .messages(conversation.id, None, 10)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(store.get(conversation.id).await.unwrap().next_seq, 1);
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM conversation_runs")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
    sqlx::query("DROP TRIGGER reject_event")
        .execute(&pool)
        .await
        .unwrap();
    store.accept(conversation.id, &request).await.unwrap();
    assert_eq!(store.events(conversation.id, 0, 10).await.unwrap().len(), 2);
}

#[tokio::test]
async fn cancelled_or_expired_workers_cannot_publish_or_renew() {
    let pool = database().await;
    let store = ConversationStore::new(pool.clone(), scope());
    let conversation = store.resolve().await.unwrap();
    let first = store
        .accept(conversation.id, &input("first"))
        .await
        .unwrap();
    let second = store
        .accept(conversation.id, &input("second"))
        .await
        .unwrap();
    let running = store
        .claim_next(conversation.id, Uuid::new_v4())
        .await
        .unwrap()
        .unwrap();
    assert_eq!(running.id, first.run.id);
    assert!(
        store
            .claim_next(conversation.id, Uuid::new_v4())
            .await
            .unwrap()
            .is_none()
    );
    store.renew(&running).await.unwrap();
    let cancelled = store.cancel(conversation.id, running.id).await.unwrap();
    assert_eq!(cancelled.status, "cancelled");
    let last_seq = store.get(conversation.id).await.unwrap().next_seq;
    assert_eq!(
        store
            .cancel(conversation.id, running.id)
            .await
            .unwrap()
            .generation,
        cancelled.generation
    );
    assert_eq!(store.get(conversation.id).await.unwrap().next_seq, last_seq);
    assert!(matches!(
        store.complete(&running, "late").await,
        Err(ConversationError::StaleLease)
    ));
    assert!(matches!(
        store.renew(&running).await,
        Err(ConversationError::StaleLease)
    ));
    let running = store
        .claim_next(conversation.id, Uuid::new_v4())
        .await
        .unwrap()
        .unwrap();
    assert_eq!(running.id, second.run.id);
    sqlx::query("UPDATE conversation_runs SET lease_until = unixepoch() - 1 WHERE id = ?")
        .bind(running.id)
        .execute(&pool)
        .await
        .unwrap();
    assert!(matches!(
        store.complete(&running, "expired").await,
        Err(ConversationError::StaleLease)
    ));
    assert!(matches!(
        store.renew(&running).await,
        Err(ConversationError::StaleLease)
    ));
    assert!(
        store
            .claim_next(conversation.id, Uuid::new_v4())
            .await
            .unwrap()
            .is_none()
    );
    let recovered = store.cancel(conversation.id, running.id).await.unwrap();
    assert_eq!(recovered.status, "interrupted");
    assert_eq!(recovered.error.as_deref(), Some("worker_lease_expired"));
    assert_eq!(
        store
            .messages(conversation.id, None, 10)
            .await
            .unwrap()
            .len(),
        2
    );
}

#[tokio::test]
async fn invalid_inputs_and_archived_conversations_do_not_admit_work() {
    let pool = database().await;
    let store = ConversationStore::new(pool.clone(), scope());
    let conversation = store.resolve().await.unwrap();
    for text in [String::new(), " \n\t".into(), "é".repeat(32769)] {
        assert!(matches!(
            store.accept(conversation.id, &input(&text)).await,
            Err(ConversationError::InvalidBody)
        ));
    }
    let boundary = input(&"é".repeat(32768));
    store.accept(conversation.id, &boundary).await.unwrap();
    sqlx::query("UPDATE conversations SET archived_at = datetime('now') WHERE id = ?")
        .bind(conversation.id)
        .execute(&pool)
        .await
        .unwrap();
    assert!(matches!(
        store.accept(conversation.id, &input("new")).await,
        Err(ConversationError::Archived)
    ));
    store.accept(conversation.id, &boundary).await.unwrap();
    assert!(
        store
            .claim_next(conversation.id, Uuid::new_v4())
            .await
            .unwrap()
            .is_none()
    );
}

#[tokio::test]
async fn concurrent_clients_retry_and_restart_without_duplicate_work() {
    let path = std::env::temp_dir().join(format!("vk-chat-test-{}.sqlite", Uuid::new_v4()));
    let options = SqliteConnectOptions::new()
        .filename(&path)
        .create_if_missing(true)
        .foreign_keys(true)
        .journal_mode(SqliteJournalMode::Wal)
        .busy_timeout(Duration::from_secs(10));
    let pool = SqlitePoolOptions::new()
        .max_connections(8)
        .connect_with(options.clone())
        .await
        .unwrap();
    // Also validates this migration alongside every existing VK migration.
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    let owner = scope();
    let store = ConversationStore::new(pool.clone(), owner);
    let conversation = store.resolve().await.unwrap();
    let request = input("one logical request from several clients");
    let mut jobs = Vec::new();
    for _ in 0..12 {
        let store = store.clone();
        let request = request.clone();
        jobs.push(tokio::spawn(async move {
            assert_eq!(store.resolve().await.unwrap().id, conversation.id);
            store.accept(conversation.id, &request).await.unwrap()
        }));
    }
    let mut ids = Vec::new();
    for job in jobs {
        ids.push(job.await.unwrap().run.id);
    }
    assert!(ids.iter().all(|id| *id == ids[0]));
    assert_eq!(
        store
            .messages(conversation.id, None, 200)
            .await
            .unwrap()
            .len(),
        1
    );
    // Concurrent different messages get contiguous, non-overlapping event sequences.
    let mut jobs = Vec::new();
    for n in 0..10 {
        let store = store.clone();
        jobs.push(tokio::spawn(async move {
            store
                .accept(conversation.id, &input(&format!("request {n}")))
                .await
                .unwrap()
        }));
    }
    for job in jobs {
        job.await.unwrap();
    }
    let last_seq = store.get(conversation.id).await.unwrap().next_seq - 1;
    assert_eq!(last_seq, 22);
    pool.close().await;
    let pool = SqlitePoolOptions::new()
        .max_connections(2)
        .connect_with(options)
        .await
        .unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    let restarted = ConversationStore::new(pool.clone(), owner);
    assert_eq!(restarted.resolve().await.unwrap().id, conversation.id);
    assert_eq!(
        restarted
            .accept(conversation.id, &request)
            .await
            .unwrap()
            .run
            .id,
        ids[0]
    );
    assert_eq!(
        restarted
            .events(conversation.id, 0, 200)
            .await
            .unwrap()
            .iter()
            .map(|e| e.seq)
            .collect::<Vec<_>>(),
        (1..=last_seq).collect::<Vec<_>>()
    );
    let (left, right) = tokio::join!(
        restarted.claim_next(conversation.id, Uuid::new_v4()),
        restarted.claim_next(conversation.id, Uuid::new_v4())
    );
    let claims: Vec<_> = [left.unwrap(), right.unwrap()]
        .into_iter()
        .flatten()
        .collect();
    assert_eq!(claims.len(), 1, "Only one process can own the conversation");
    let run = &claims[0];
    assert_eq!(run.id, ids[0]);
    let reply = restarted
        .complete(run, "I have your request.")
        .await
        .unwrap();
    assert_eq!(reply.created_seq, 24); // claim contributes its own committed event
    assert!(matches!(
        restarted.complete(run, "duplicate").await,
        Err(ConversationError::StaleLease)
    ));
    assert!(
        sqlx::query("PRAGMA foreign_key_check")
            .fetch_all(&pool)
            .await
            .unwrap()
            .is_empty()
    );
    pool.close().await;
    std::fs::remove_file(&path).unwrap();
}

#[tokio::test]
async fn populated_upgrade_preserves_existing_raw_session_history() {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    let mut baseline = sqlx::migrate!("./migrations");
    baseline.migrations = std::borrow::Cow::Owned(
        baseline
            .migrations
            .iter()
            .filter(|migration| migration.version < 20260926000000)
            .cloned()
            .collect(),
    );
    baseline.run(&pool).await.unwrap();
    let workspace = Uuid::new_v4();
    let session = Uuid::new_v4();
    let process = Uuid::new_v4();
    let turn = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces (id, branch, name) VALUES (?, 'existing-work', 'Detailed raw chat')")
        .bind(workspace).execute(&pool).await.unwrap();
    sqlx::query("INSERT INTO sessions (id, workspace_id, executor, name) VALUES (?, ?, 'CODEX', 'Existing session')")
        .bind(session).bind(workspace).execute(&pool).await.unwrap();
    sqlx::query("INSERT INTO execution_processes (id, session_id, run_reason, executor_action, status) VALUES (?, ?, 'codingagent', '{}', 'completed')")
        .bind(process).bind(session).execute(&pool).await.unwrap();
    let raw = "Validation:: 42 tests passed\nCommit:: abc123\n```rust\nfn main() {}\n```";
    sqlx::query("INSERT INTO coding_agent_turns (id, execution_process_id, prompt, summary) VALUES (?, ?, 'original prompt', ?)")
        .bind(turn).bind(process).bind(raw).execute(&pool).await.unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    let preserved: (String, String) =
        sqlx::query_as("SELECT prompt, summary FROM coding_agent_turns WHERE id = ?")
            .bind(turn)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(preserved, ("original prompt".into(), raw.into()));
    assert_eq!(
        sqlx::query_scalar::<_, i64>(
            "SELECT count(*) FROM sessions WHERE id = ? AND workspace_id = ?"
        )
        .bind(session)
        .bind(workspace)
        .fetch_one(&pool)
        .await
        .unwrap(),
        1
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM conversations")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
    assert!(
        sqlx::query("PRAGMA foreign_key_check")
            .fetch_all(&pool)
            .await
            .unwrap()
            .is_empty()
    );
}
