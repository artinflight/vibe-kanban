use sqlx::sqlite::SqlitePoolOptions;

use super::*;

async fn fixture() -> (SqlitePool, ConversationStore, Uuid, Uuid) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    let scope = ConversationScope::local_operator(&pool).await.unwrap();
    let store = ConversationStore::new(pool.clone(), scope);
    let id = store.resolve().await.unwrap().id;
    let message = store
        .accept(
            id,
            &input("Remember: omit routine successful validation from supervisor updates."),
        )
        .await
        .unwrap()
        .message
        .id;
    (pool, store, id, message)
}
fn input(body: &str) -> AcceptConversationMessage {
    AcceptConversationMessage {
        client_message_id: Uuid::new_v4(),
        body: body.into(),
        origin: ConversationInputOrigin::Typed,
        reply_to_id: None,
    }
}
fn change(message: Uuid) -> MemoryChange {
    MemoryChange {
        scope: MemoryScope::Global,
        claim_key: "communication.validation".into(),
        body: "Leave out successful validation unless I ask.".into(),
        entity_refs: vec![],
        source_message_id: message,
        replaces: None,
        explicit: true,
        valid_until: None,
    }
}
async fn workspace(pool: &SqlitePool) -> Uuid {
    let id = Uuid::new_v4();
    sqlx::query("INSERT INTO workspaces (id,branch) VALUES (?, 'memory-test')")
        .bind(id)
        .execute(pool)
        .await
        .unwrap();
    id
}
async fn report(pool: &SqlitePool) -> (EvidenceSource, Uuid, String) {
    let workspace = workspace(pool).await;
    let session = Uuid::new_v4();
    let process = Uuid::new_v4();
    let turn = Uuid::new_v4();
    sqlx::query("INSERT INTO sessions (id,workspace_id,executor) VALUES (?, ?, 'CODEX')")
        .bind(session)
        .bind(workspace)
        .execute(pool)
        .await
        .unwrap();
    sqlx::query("INSERT INTO execution_processes (id,session_id,run_reason,executor_action,status) VALUES (?, ?, 'codingagent', '{}', 'completed')").bind(process).bind(session).execute(pool).await.unwrap();
    let raw =
        "Validation:: 42 tests passed\nCommit:: 123abc\n```rust\nfn exact() {}\n```\n".to_owned();
    sqlx::query("INSERT INTO coding_agent_turns (id,execution_process_id,prompt,summary) VALUES (?, ?, 'original request', ?)").bind(turn).bind(process).bind(&raw).execute(pool).await.unwrap();
    (
        EvidenceSource::AgentReport {
            session_id: session,
            process_id: process,
        },
        turn,
        raw,
    )
}

#[tokio::test]
async fn corrections_supersede_exact_revision_and_inferences_never_override_users() {
    let (_, store, id, message) = fixture().await;
    let first = store.put_memory(id, &change(message)).await.unwrap();
    let mut update = change(message);
    update.body = "Mention validation only when it failed or I ask.".into();
    update.replaces = Some((first.id, first.revision));
    update.explicit = false;
    assert!(matches!(
        store.put_memory(id, &update).await,
        Err(ConversationError::InvalidRecord)
    ));
    update.explicit = true;
    let revised = store.put_memory(id, &update).await.unwrap();
    assert_eq!(revised.revision, 2);
    assert_eq!(revised.supersedes_id, Some(first.id));
    assert!(matches!(
        store.put_memory(id, &update).await,
        Err(ConversationError::RevisionConflict)
    ));
    let retrieved = store.memories(id, &[], 8000).await.unwrap();
    assert_eq!(retrieved.len(), 1);
    assert_eq!(retrieved[0].body, update.body);
    let exported = store.export(id).await.unwrap();
    assert_eq!(exported.memories.len(), 2);
    assert_eq!(exported.memories[0].state, "superseded");
}

#[tokio::test]
async fn scoped_retrieval_excludes_other_work_and_requires_all_linked_entities() {
    let (pool, store, id, message) = fixture().await;
    let a = MemoryScope::Workspace(workspace(&pool).await);
    let b = MemoryScope::Workspace(workspace(&pool).await);
    store.put_memory(id, &change(message)).await.unwrap();
    let mut project = change(message);
    project.scope = a.clone();
    project.claim_key = "source_of_truth".into();
    project.body = "Web defines the onboarding behavior.".into();
    project.entity_refs = vec![a.clone(), b.clone()];
    store.put_memory(id, &project).await.unwrap();
    assert_eq!(
        store
            .memories(id, std::slice::from_ref(&a), 8000)
            .await
            .unwrap()
            .len(),
        1
    );
    let all = store.memories(id, &[a.clone(), b], 8000).await.unwrap();
    assert_eq!(all.len(), 2);
    assert_eq!(all[0].claim_key, "source_of_truth");
    assert!(store.memories(id, &[a], 0).await.unwrap().is_empty());
    project.scope = MemoryScope::Workspace(Uuid::new_v4());
    assert!(matches!(
        store.put_memory(id, &project).await,
        Err(ConversationError::NotFound)
    ));
    project.scope = MemoryScope::Global;
    project.claim_key = "inferred".into();
    project.entity_refs.clear();
    project.explicit = false;
    assert_eq!(
        store.put_memory(id, &project).await.unwrap().state,
        "proposed"
    );
    assert_eq!(store.memories(id, &[], 8000).await.unwrap().len(), 1);
}

#[tokio::test]
async fn forgetting_scrubs_versions_and_replay_and_blocks_reextraction() {
    let (pool, store, id, message) = fixture().await;
    let original = change(message);
    let memory = store.put_memory(id, &original).await.unwrap();
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    sqlx::query("INSERT INTO conversation_context (conversation_id, summary, source_versions) VALUES (?, 'old cached knowledge', '{}')").bind(id).execute(&pool).await.unwrap();
    let last_seq = store.get(id).await.unwrap().next_seq;
    store
        .forget_memory(id, memory.id, memory.revision)
        .await
        .unwrap();
    assert!(store.memories(id, &[], 8000).await.unwrap().is_empty());
    assert!(matches!(
        store.complete(&run, "An obsolete preference").await,
        Err(ConversationError::StaleLease)
    ));
    assert!(matches!(
        store.put_memory(id, &original).await,
        Err(ConversationError::InvalidRecord)
    ));
    let exported = store.export(id).await.unwrap();
    assert_eq!(exported.memories[0].body, "");
    assert_eq!(exported.memories[0].state, "retracted");
    assert!(
        exported
            .events
            .iter()
            .filter(|e| e.seq < last_seq)
            .all(|e| !e.payload.contains(&original.body))
    );
    let summary: String =
        sqlx::query_scalar("SELECT summary FROM conversation_context WHERE conversation_id = ?")
            .bind(id)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(summary, "");
    // A later explicit instruction can restore the preference with new provenance.
    let newer = store
        .accept(id, &input("Please remember that preference again."))
        .await
        .unwrap();
    let mut restored = original;
    restored.source_message_id = newer.message.id;
    store.put_memory(id, &restored).await.unwrap();
}

#[tokio::test]
async fn retains_exact_report_and_rejects_changed_revision_or_foreign_links() {
    let (pool, store, id, message) = fixture().await;
    let (source, turn, raw) = report(&pool).await;
    let evidence = store
        .retain_evidence(id, &source, "completed:1", &raw)
        .await
        .unwrap();
    assert_eq!(
        store
            .retain_evidence(id, &source, "completed:1", &raw)
            .await
            .unwrap()
            .id,
        evidence.id
    );
    assert!(matches!(
        store
            .retain_evidence(id, &source, "completed:1", "different")
            .await,
        Err(ConversationError::IdempotencyConflict)
    ));
    store
        .link_evidence(id, message, evidence.id, "supporting")
        .await
        .unwrap();
    store
        .link_evidence(id, message, evidence.id, "supporting")
        .await
        .unwrap();
    assert_eq!(store.export(id).await.unwrap().message_evidence.len(), 1);
    let other = ConversationStore::new(
        pool.clone(),
        ConversationScope {
            authority_id: Uuid::new_v4(),
            principal_id: Uuid::new_v4(),
        },
    );
    let other_id = other.resolve().await.unwrap().id;
    assert!(matches!(
        other.evidence(id, evidence.id).await,
        Err(ConversationError::NotFound)
    ));
    assert!(matches!(
        other
            .link_evidence(other_id, message, evidence.id, "quoted")
            .await,
        Err(ConversationError::NotFound)
    ));
    sqlx::query("DELETE FROM coding_agent_turns WHERE id = ?")
        .bind(turn)
        .execute(&pool)
        .await
        .unwrap();
    assert_eq!(
        store.evidence(id, evidence.id).await.unwrap().raw_report,
        Some(raw)
    );
}

#[tokio::test]
async fn proposals_are_immutable_idempotent_and_fenced_by_run_generation() {
    let (_, store, id, message) = fixture().await;
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    let mut proposal = ActionProposal {
        request_id: Uuid::new_v4(),
        origin_message_id: message,
        intent_kind: "send_agent_message".into(),
        payload: json!({"message":"web is authoritative"}),
        route_evidence: json!({"ambiguity":"none"}),
    };
    let action = store.propose_action(&run, &proposal).await.unwrap();
    assert_eq!(action.state, "proposed");
    assert!(action.authorisation_source.is_none());
    assert_eq!(
        store.propose_action(&run, &proposal).await.unwrap().id,
        action.id
    );
    proposal.payload = json!({"message":"change everything"});
    assert!(matches!(
        store.propose_action(&run, &proposal).await,
        Err(ConversationError::IdempotencyConflict)
    ));
    store.cancel(id, run.id).await.unwrap();
    proposal.request_id = Uuid::new_v4();
    assert!(matches!(
        store.propose_action(&run, &proposal).await,
        Err(ConversationError::StaleLease)
    ));
    assert_eq!(store.actions(id).await.unwrap().len(), 1);
}

#[tokio::test]
async fn export_and_deletion_erase_supervisor_content_but_preserve_raw_workspace() {
    let (pool, store, id, message) = fixture().await;
    let (source, turn, raw) = report(&pool).await;
    let evidence = store
        .retain_evidence(id, &source, "final", &raw)
        .await
        .unwrap();
    store
        .link_evidence(id, message, evidence.id, "supporting")
        .await
        .unwrap();
    store.put_memory(id, &change(message)).await.unwrap();
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    let proposal = ActionProposal {
        request_id: Uuid::new_v4(),
        origin_message_id: message,
        intent_kind: "send_agent_message".into(),
        payload: json!({"message":"private instruction"}),
        route_evidence: json!({}),
    };
    store.propose_action(&run, &proposal).await.unwrap();
    let reply = store
        .complete(&run, "I will keep future updates concise.")
        .await
        .unwrap();
    store
        .link_evidence(id, reply.id, evidence.id, "summarised")
        .await
        .unwrap();
    let export = store.export(id).await.unwrap();
    assert_eq!(export.messages.len(), 2);
    assert_eq!(export.evidence[0].raw_report, Some(raw.clone()));
    assert_eq!(export.actions.len(), 1);
    assert!(matches!(
        store.delete_content(id, 1).await,
        Err(ConversationError::RevisionConflict)
    ));
    let deleted = store
        .delete_content(id, export.conversation.revision)
        .await
        .unwrap();
    assert!(deleted.next_seq > export.conversation.next_seq);
    let after = store.export(id).await.unwrap();
    assert!(
        after.messages.is_empty()
            && after.runs.is_empty()
            && after.actions.is_empty()
            && after.evidence.is_empty()
            && after.memories.is_empty()
    );
    assert!(
        after
            .events
            .iter()
            .all(|e| e.payload == "{}" || e.event_type == "history.cleared")
    );
    let preserved: String =
        sqlx::query_scalar("SELECT summary FROM coding_agent_turns WHERE id = ?")
            .bind(turn)
            .fetch_one(&pool)
            .await
            .unwrap();
    assert_eq!(preserved, raw);
    assert!(matches!(
        store.complete(&run, "late completion").await,
        Err(ConversationError::StaleLease)
    ));
    assert!(
        sqlx::query("PRAGMA foreign_key_check")
            .fetch_all(&pool)
            .await
            .unwrap()
            .is_empty()
    );
    assert_eq!(store.resolve().await.unwrap().id, id);
    store.accept(id, &input("Start again")).await.unwrap();
}

#[tokio::test]
async fn failed_event_commit_rolls_back_memory_supersession() {
    let (pool, store, id, message) = fixture().await;
    let original = store.put_memory(id, &change(message)).await.unwrap();
    let mut update = change(message);
    update.body = "updated preference".into();
    update.replaces = Some((original.id, original.revision));
    sqlx::query("CREATE TRIGGER fail_memory_event BEFORE INSERT ON conversation_events WHEN NEW.type = 'memory.changed' BEGIN SELECT RAISE(ABORT, 'injected'); END").execute(&pool).await.unwrap();
    assert!(store.put_memory(id, &update).await.is_err());
    let current = store.memories(id, &[], 8000).await.unwrap();
    assert_eq!(current.len(), 1);
    assert_eq!(current[0].id, original.id);
    assert_eq!(current[0].state, "active");
}

#[tokio::test]
async fn deletion_rejects_unreconciled_actions_and_other_principals() {
    let (pool, store, id, message) = fixture().await;
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    let action = store
        .propose_action(
            &run,
            &ActionProposal {
                request_id: Uuid::new_v4(),
                origin_message_id: message,
                intent_kind: "send_agent_message".into(),
                payload: json!({}),
                route_evidence: json!({}),
            },
        )
        .await
        .unwrap();
    sqlx::query("UPDATE conversation_actions SET state = 'unknown_delivery' WHERE id = ?")
        .bind(action.id)
        .execute(&pool)
        .await
        .unwrap();
    let revision = store.get(id).await.unwrap().revision;
    assert!(matches!(
        store.delete_content(id, revision).await,
        Err(ConversationError::ActiveDeliveries)
    ));
    let other = ConversationStore::new(
        pool,
        ConversationScope {
            authority_id: store.scope.authority_id,
            principal_id: Uuid::new_v4(),
        },
    );
    assert!(matches!(
        other.export(id).await,
        Err(ConversationError::NotFound)
    ));
    assert!(matches!(
        other.put_memory(id, &change(message)).await,
        Err(ConversationError::NotFound)
    ));
    assert!(matches!(
        other.delete_content(id, revision).await,
        Err(ConversationError::NotFound)
    ));
}

#[tokio::test]
async fn concurrent_memory_edits_restart_export_and_erase_on_disk() {
    use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode};
    let path = std::env::temp_dir().join(format!("vk-chat-records-{}.sqlite", Uuid::new_v4()));
    let options = SqliteConnectOptions::new()
        .filename(&path)
        .create_if_missing(true)
        .foreign_keys(true)
        .journal_mode(SqliteJournalMode::Wal)
        .busy_timeout(std::time::Duration::from_secs(10));
    let pool = SqlitePoolOptions::new()
        .max_connections(4)
        .connect_with(options.clone())
        .await
        .unwrap();
    sqlx::migrate!("./migrations").run(&pool).await.unwrap();
    let scope = ConversationScope::local_operator(&pool).await.unwrap();
    let store = ConversationStore::new(pool.clone(), scope);
    let id = store.resolve().await.unwrap().id;
    let message = store
        .accept(id, &input("Remember this preference"))
        .await
        .unwrap()
        .message
        .id;
    let memory = store.put_memory(id, &change(message)).await.unwrap();
    let mut left = change(message);
    left.replaces = Some((memory.id, memory.revision));
    left.body = "Keep updates brief".into();
    let mut right = left.clone();
    right.body = "Explain major decisions".into();
    let (a, b) = tokio::join!(store.put_memory(id, &left), store.put_memory(id, &right));
    assert_eq!(usize::from(a.is_ok()) + usize::from(b.is_ok()), 1);
    let winner = a.or(b).unwrap();
    let (source, _, raw) = report(&pool).await;
    let evidence = store
        .retain_evidence(id, &source, "final:1", &raw)
        .await
        .unwrap();
    let run = store.claim_next(id, Uuid::new_v4()).await.unwrap().unwrap();
    let action = store
        .propose_action(
            &run,
            &ActionProposal {
                request_id: Uuid::new_v4(),
                origin_message_id: message,
                intent_kind: "send_agent_message".into(),
                payload: json!({"message":"retained request"}),
                route_evidence: json!({}),
            },
        )
        .await
        .unwrap();
    let response = store
        .complete(&run, "I have saved the preference.")
        .await
        .unwrap();
    store
        .link_evidence(id, response.id, evidence.id, "supporting")
        .await
        .unwrap();
    pool.close().await;
    let reopened = SqlitePoolOptions::new()
        .max_connections(2)
        .connect_with(options)
        .await
        .unwrap();
    sqlx::migrate!("./migrations").run(&reopened).await.unwrap();
    let reopened_scope = ConversationScope::local_operator(&reopened).await.unwrap();
    assert_eq!(reopened_scope.authority_id, scope.authority_id);
    assert_eq!(reopened_scope.principal_id, scope.principal_id);
    let recovered = ConversationStore::new(reopened.clone(), reopened_scope);
    let export = recovered.export(id).await.unwrap();
    assert_eq!(export.actions[0].id, action.id);
    assert_eq!(export.evidence[0].raw_report, Some(raw));
    assert_eq!(export.message_evidence.len(), 1);
    assert_eq!(
        recovered.memories(id, &[], 8000).await.unwrap()[0].id,
        winner.id
    );
    let sequences: Vec<_> = export.events.iter().map(|e| e.seq).collect();
    assert_eq!(
        sequences,
        (1..export.conversation.next_seq).collect::<Vec<_>>()
    );
    recovered
        .delete_content(id, export.conversation.revision)
        .await
        .unwrap();
    assert!(recovered.export(id).await.unwrap().messages.is_empty());
    reopened.close().await;
    std::fs::remove_file(path).unwrap();
}
