use axum::{
    body::{Body, to_bytes},
    http::Request,
};
use sqlx::sqlite::SqlitePoolOptions;
use tower::ServiceExt;

use super::*;

async fn fixture(accepting_messages: bool) -> (SqlitePool, Router) {
    let pool = SqlitePoolOptions::new()
        .max_connections(1)
        .connect("sqlite::memory:")
        .await
        .unwrap();
    sqlx::migrate!("../db/migrations").run(&pool).await.unwrap();
    let router = api_router(ConversationApiState {
        pool: pool.clone(),
        enabled: true,
        accepting_messages,
    });
    (pool, router)
}

async fn call(router: &Router, method: &str, path: &str, body: Value) -> (StatusCode, Value) {
    let response = router
        .clone()
        .oneshot(
            Request::builder()
                .method(method)
                .uri(path)
                .header("content-type", "application/json")
                .body(Body::from(body.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    let status = response.status();
    let value = serde_json::from_slice(&to_bytes(response.into_body(), 1024 * 1024).await.unwrap())
        .unwrap();
    (status, value)
}

#[tokio::test]
async fn api_accepts_once_and_replays_committed_records_across_clients() {
    let (pool, router) = fixture(true).await;
    let (status, resolved) = call(&router, "POST", "/conversations/resolve", json!({})).await;
    assert_eq!(status, StatusCode::OK);
    let id = resolved["data"]["conversation"]["id"].as_str().unwrap();
    let path = format!("/conversations/{id}/messages");
    let input = json!({"client_message_id": Uuid::new_v4(), "body": "Tell the Android agent web remains authoritative.", "origin":"typed"});
    let (status, first) = call(&router, "POST", &path, input.clone()).await;
    assert_eq!(status, StatusCode::ACCEPTED);
    let (_, retry) = call(&router, "POST", &path, input.clone()).await;
    assert_eq!(
        first["data"]["message"]["id"],
        retry["data"]["message"]["id"]
    );
    assert_eq!(first["data"]["run_id"], retry["data"]["run_id"]);
    let mut changed = input;
    changed["body"] = json!("Different instruction");
    assert_eq!(
        call(&router, "POST", &path, changed).await.0,
        StatusCode::CONFLICT
    );
    let (_, history) = call(&router, "GET", &path, json!({})).await;
    assert_eq!(history["data"].as_array().unwrap().len(), 1);
    let (_, events) = call(
        &router,
        "GET",
        &format!("/conversations/{id}/events?after_seq=0"),
        json!({}),
    )
    .await;
    assert_eq!(events["data"].as_array().unwrap().len(), 2);
    assert_eq!(events["data"][0]["type"], "message.created");
    assert!(events["data"][0]["payload"].is_object());
    assert!(events["data"][1]["payload"].get("lease_owner").is_none());
    assert!(
        events["data"][1]["payload"]
            .get("context_manifest")
            .is_none()
    );
    let fresh_client: Router = api_router(ConversationApiState {
        pool,
        enabled: true,
        accepting_messages: true,
    });
    let (_, same) = call(&fresh_client, "POST", "/conversations/resolve", json!({})).await;
    assert_eq!(same["data"]["conversation"]["id"], id);
    let (_, remainder) = call(
        &fresh_client,
        "GET",
        &format!("/conversations/{id}/events?after_seq=1"),
        json!({}),
    )
    .await;
    assert_eq!(remainder["data"].as_array().unwrap().len(), 1);
    assert_eq!(remainder["data"][0]["seq"], 2);
}

#[tokio::test]
async fn unavailable_model_keeps_history_readable_without_accepting_unconsumed_work() {
    let (pool, router) = fixture(false).await;
    let (_, resolved) = call(&router, "POST", "/conversations/resolve", json!({})).await;
    let id = resolved["data"]["conversation"]["id"].as_str().unwrap();
    assert_eq!(
        resolved["data"]["capabilities"]["accepting_messages"],
        false
    );
    let input =
        json!({"client_message_id": Uuid::new_v4(), "body":"Don't drop this", "origin":"typed"});
    assert_eq!(
        call(
            &router,
            "POST",
            &format!("/conversations/{id}/messages"),
            input
        )
        .await
        .0,
        StatusCode::SERVICE_UNAVAILABLE
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM conversation_messages")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
    assert_eq!(
        call(&router, "GET", &format!("/conversations/{id}"), json!({}))
            .await
            .0,
        StatusCode::OK
    );
}

#[tokio::test]
async fn disabled_or_relay_request_cannot_resolve_local_operator_history() {
    let (pool, router) = fixture(true).await;
    let mut request = Request::builder()
        .method("POST")
        .uri("/conversations/resolve")
        .body(Body::empty())
        .unwrap();
    // Outer relay middleware supplies this only after validating the signature.
    request
        .extensions_mut()
        .insert(RelayRequestSignatureContext {
            signing_session_id: Uuid::new_v4(),
            timestamp: 1,
            nonce: Uuid::new_v4(),
            signature_b64: "already verified by outer middleware".into(),
        });
    assert_eq!(
        router.oneshot(request).await.unwrap().status(),
        StatusCode::FORBIDDEN
    );
    let disabled: Router = api_router(ConversationApiState {
        pool: pool.clone(),
        enabled: false,
        accepting_messages: false,
    });
    assert_eq!(
        call(&disabled, "POST", "/conversations/resolve", json!({}))
            .await
            .0,
        StatusCode::SERVICE_UNAVAILABLE
    );
    assert_eq!(
        sqlx::query_scalar::<_, i64>("SELECT count(*) FROM conversations")
            .fetch_one(&pool)
            .await
            .unwrap(),
        0
    );
}

#[tokio::test]
async fn reject_foreign_conversation_invalid_cursor_and_unbound_voice_input() {
    let (pool, router) = fixture(true).await;
    let other = ConversationStore::new(
        pool,
        ConversationScope {
            authority_id: Uuid::new_v4(),
            principal_id: Uuid::new_v4(),
        },
    )
    .resolve()
    .await
    .unwrap();
    assert_eq!(
        call(
            &router,
            "GET",
            &format!("/conversations/{}", other.id),
            json!({})
        )
        .await
        .0,
        StatusCode::NOT_FOUND
    );
    let (_, resolved) = call(&router, "POST", "/conversations/resolve", json!({})).await;
    let id = resolved["data"]["conversation"]["id"].as_str().unwrap();
    for cursor in [-1, 1, i64::MAX] {
        assert_eq!(
            call(
                &router,
                "GET",
                &format!("/conversations/{id}/events?after_seq={cursor}"),
                json!({})
            )
            .await
            .0,
            StatusCode::BAD_REQUEST
        );
    }
    let input =
        json!({"client_message_id": Uuid::new_v4(), "body":"unbound transcript", "origin":"voice"});
    assert_eq!(
        call(
            &router,
            "POST",
            &format!("/conversations/{id}/messages"),
            input
        )
        .await
        .0,
        StatusCode::BAD_REQUEST
    );
}

#[tokio::test]
async fn export_delete_and_forget_require_owner_and_current_revision() {
    use db::models::conversation::records::{MemoryChange, MemoryScope};
    let (pool, router) = fixture(true).await;
    let scope = ConversationScope::local_operator(&pool).await.unwrap();
    let store = ConversationStore::new(pool, scope);
    let id = store.resolve().await.unwrap().id;
    let accepted = store
        .accept(
            id,
            &AcceptConversationMessage {
                client_message_id: Uuid::new_v4(),
                body: "Keep it brief".into(),
                origin: ConversationInputOrigin::Typed,
                reply_to_id: None,
            },
        )
        .await
        .unwrap();
    let memory = store
        .put_memory(
            id,
            &MemoryChange {
                scope: MemoryScope::Global,
                claim_key: "style".into(),
                body: "Concise updates".into(),
                entity_refs: vec![],
                source_message_id: accepted.message.id,
                replaces: None,
                explicit: true,
                valid_until: None,
            },
        )
        .await
        .unwrap();
    let (_, listed) = call(
        &router,
        "GET",
        &format!("/conversations/{id}/memories"),
        json!({}),
    )
    .await;
    assert_eq!(listed["data"].as_array().unwrap().len(), 1);
    let path = format!("/conversations/{id}/memories/{}", memory.id);
    assert_eq!(
        call(&router, "DELETE", &path, json!({"expected_revision":99}))
            .await
            .0,
        StatusCode::CONFLICT
    );
    assert_eq!(
        call(
            &router,
            "DELETE",
            &path,
            json!({"expected_revision":memory.revision})
        )
        .await
        .0,
        StatusCode::OK
    );
    let (_, export) = call(
        &router,
        "GET",
        &format!("/conversations/{id}/export"),
        json!({}),
    )
    .await;
    assert_eq!(export["data"]["memories"][0]["body"], "");
    let path = format!("/conversations/{id}/history");
    assert_eq!(
        call(&router, "DELETE", &path, json!({"expected_revision":1}))
            .await
            .0,
        StatusCode::CONFLICT
    );
    let revision = export["data"]["conversation"]["revision"].as_i64().unwrap();
    assert_eq!(
        call(
            &router,
            "DELETE",
            &path,
            json!({"expected_revision":revision})
        )
        .await
        .0,
        StatusCode::OK
    );
    let (_, messages) = call(
        &router,
        "GET",
        &format!("/conversations/{id}/messages"),
        json!({}),
    )
    .await;
    assert_eq!(messages["data"], json!([]));
    assert_eq!(
        call(
            &router,
            "GET",
            &format!("/conversations/{}/export", Uuid::new_v4()),
            json!({})
        )
        .await
        .0,
        StatusCode::NOT_FOUND
    );
    let response = router
        .oneshot(
            Request::builder()
                .uri(format!("/conversations/{id}/export"))
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.headers()["cache-control"], "no-store");
}
