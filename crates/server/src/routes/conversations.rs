//! Global supervisor API. Workspace chat retains its existing routes/history.
//! Initially supports the trusted local operator only; a relay signature proves
//! transport authenticity, not ownership of that operator's private history.
use axum::{
    Extension, Json, Router,
    extract::{
        Path, Query, State, WebSocketUpgrade,
        ws::{Message, WebSocket},
    },
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
};
use db::models::conversation::{
    AcceptConversationMessage, Conversation, ConversationError, ConversationInputOrigin,
    ConversationMessage, ConversationScope, ConversationStore,
    records::{
        ConversationAction, ConversationEvidence, ConversationExport, ConversationMemory,
        MessageEvidenceRef,
    },
};
use futures_util::SinkExt;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sqlx::SqlitePool;
use ts_rs::TS;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, middleware::RelayRequestSignatureContext};

#[derive(Clone)]
struct ConversationApiState {
    pool: SqlitePool,
    enabled: bool,
    accepting_messages: bool,
}

#[derive(Debug, Serialize, TS)]
pub struct SupervisorCapabilities {
    pub enabled: bool,
    pub accepting_messages: bool,
    pub agent_actions: bool,
    pub voice: bool,
    pub authority: String,
}

#[derive(Debug, Serialize, TS)]
pub struct SupervisorSnapshot {
    pub conversation: Conversation,
    #[ts(type = "number")]
    pub last_seq: i64,
    pub capabilities: SupervisorCapabilities,
}

#[derive(Debug, Serialize, TS)]
pub struct SupervisorMessageReceipt {
    pub message: ConversationMessage,
    pub run_id: Uuid,
}

#[derive(Debug, Serialize, TS)]
pub struct SupervisorEvent {
    pub conversation_id: Uuid,
    #[ts(type = "number")]
    pub seq: i64,
    pub event_id: Uuid,
    #[serde(rename = "type")]
    pub event_type: String,
    #[ts(type = "number")]
    pub schema_version: i64,
    pub entity_id: Uuid,
    #[ts(type = "number")]
    pub revision: i64,
    pub occurred_at: chrono::DateTime<chrono::Utc>,
    #[ts(type = "unknown")]
    pub payload: Value,
}

#[derive(Debug, Deserialize, Default)]
struct HistoryQuery {
    before_seq: Option<i64>,
    limit: Option<u32>,
}
#[derive(Debug, Deserialize, Default)]
struct ReplayQuery {
    #[serde(default)]
    after_seq: i64,
}

type Relay = Option<Extension<RelayRequestSignatureContext>>;

struct ChatApiError(StatusCode, &'static str);
impl IntoResponse for ChatApiError {
    fn into_response(self) -> Response {
        (self.0, Json(ApiResponse::<()>::error(self.1))).into_response()
    }
}
impl From<ConversationError> for ChatApiError {
    fn from(error: ConversationError) -> Self {
        match error {
            ConversationError::NotFound => {
                Self(StatusCode::NOT_FOUND, "Conversation or message not found")
            }
            ConversationError::IdempotencyConflict => Self(
                StatusCode::CONFLICT,
                "Message ID already has different content",
            ),
            ConversationError::Archived => Self(StatusCode::CONFLICT, "Conversation is archived"),
            ConversationError::StaleLease => {
                Self(StatusCode::CONFLICT, "Response was cancelled or superseded")
            }
            ConversationError::RevisionConflict => Self(
                StatusCode::CONFLICT,
                "Record changed; reload before updating",
            ),
            ConversationError::InvalidRecord => Self(
                StatusCode::BAD_REQUEST,
                "Invalid supervisor record or scope",
            ),
            ConversationError::ActiveDeliveries => Self(
                StatusCode::CONFLICT,
                "Resolve active or uncertain deliveries before deleting history",
            ),
            ConversationError::InvalidBody => Self(
                StatusCode::BAD_REQUEST,
                "Message must contain text and be at most 64 KiB",
            ),
            ConversationError::Database(error) => error.into(),
        }
    }
}
impl From<sqlx::Error> for ChatApiError {
    fn from(error: sqlx::Error) -> Self {
        tracing::error!(?error, "Supervisor persistence failed");
        Self(
            StatusCode::INTERNAL_SERVER_ERROR,
            "Could not persist or load supervisor history",
        )
    }
}

impl ConversationApiState {
    fn capabilities(&self) -> SupervisorCapabilities {
        SupervisorCapabilities {
            enabled: self.enabled,
            accepting_messages: self.enabled && self.accepting_messages,
            agent_actions: false,
            voice: false,
            authority: "local_operator".into(),
        }
    }

    async fn store(&self, relay: Relay) -> Result<ConversationStore, ChatApiError> {
        if relay.is_some() {
            return Err(ChatApiError(
                StatusCode::FORBIDDEN,
                "Supervisor relay ownership is not configured",
            ));
        }
        if !self.enabled {
            return Err(ChatApiError(
                StatusCode::SERVICE_UNAVAILABLE,
                "Supervisor is disabled",
            ));
        }
        let scope = ConversationScope::local_operator(&self.pool).await?;
        Ok(ConversationStore::new(self.pool.clone(), scope))
    }
}

async fn capabilities(
    State(state): State<ConversationApiState>,
) -> Json<ApiResponse<SupervisorCapabilities>> {
    Json(ApiResponse::success(state.capabilities()))
}

async fn resolve(
    State(state): State<ConversationApiState>,
    relay: Relay,
) -> Result<Json<ApiResponse<SupervisorSnapshot>>, ChatApiError> {
    let conversation = state.store(relay).await?.resolve().await?;
    Ok(Json(ApiResponse::success(SupervisorSnapshot {
        last_seq: conversation.next_seq - 1,
        conversation,
        capabilities: state.capabilities(),
    })))
}

async fn snapshot(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
) -> Result<Json<ApiResponse<SupervisorSnapshot>>, ChatApiError> {
    let conversation = state.store(relay).await?.get(id).await?;
    Ok(Json(ApiResponse::success(SupervisorSnapshot {
        last_seq: conversation.next_seq - 1,
        conversation,
        capabilities: state.capabilities(),
    })))
}

async fn messages(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
    Query(query): Query<HistoryQuery>,
) -> Result<Json<ApiResponse<Vec<ConversationMessage>>>, ChatApiError> {
    let messages = state
        .store(relay)
        .await?
        .messages(id, query.before_seq, query.limit.unwrap_or(50))
        .await?;
    Ok(Json(ApiResponse::success(messages)))
}

async fn export(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
) -> Result<Json<ApiResponse<ConversationExport>>, ChatApiError> {
    Ok(Json(ApiResponse::success(
        state.store(relay).await?.export(id).await?,
    )))
}

#[derive(Debug, Deserialize, TS)]
pub struct DeleteSupervisorHistory {
    #[ts(type = "number")]
    pub expected_revision: i64,
}

/// Clears supervisor history, memories and retained evidence together. Original
/// session logs are separate records and never included in this deletion.
async fn delete_history(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
    Json(input): Json<DeleteSupervisorHistory>,
) -> Result<Json<ApiResponse<SupervisorSnapshot>>, ChatApiError> {
    let conversation = state
        .store(relay)
        .await?
        .delete_content(id, input.expected_revision)
        .await?;
    Ok(Json(ApiResponse::success(SupervisorSnapshot {
        last_seq: conversation.next_seq - 1,
        conversation,
        capabilities: state.capabilities(),
    })))
}

async fn actions(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
) -> Result<Json<ApiResponse<Vec<ConversationAction>>>, ChatApiError> {
    Ok(Json(ApiResponse::success(
        state.store(relay).await?.actions(id).await?,
    )))
}

async fn evidence(
    State(state): State<ConversationApiState>,
    Path((id, evidence_id)): Path<(Uuid, Uuid)>,
    relay: Relay,
) -> Result<Json<ApiResponse<ConversationEvidence>>, ChatApiError> {
    Ok(Json(ApiResponse::success(
        state.store(relay).await?.evidence(id, evidence_id).await?,
    )))
}

async fn message_evidence(
    State(state): State<ConversationApiState>,
    Path((id, message_id)): Path<(Uuid, Uuid)>,
    relay: Relay,
) -> Result<Json<ApiResponse<Vec<MessageEvidenceRef>>>, ChatApiError> {
    Ok(Json(ApiResponse::success(
        state
            .store(relay)
            .await?
            .message_evidence(id, message_id)
            .await?,
    )))
}

async fn memories(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
) -> Result<Json<ApiResponse<Vec<ConversationMemory>>>, ChatApiError> {
    Ok(Json(ApiResponse::success(
        state.store(relay).await?.list_memories(id).await?,
    )))
}

#[derive(Debug, Deserialize, TS)]
pub struct ForgetSupervisorMemory {
    #[ts(type = "number")]
    pub expected_revision: i64,
}

async fn forget_memory(
    State(state): State<ConversationApiState>,
    Path((id, memory_id)): Path<(Uuid, Uuid)>,
    relay: Relay,
    Json(input): Json<ForgetSupervisorMemory>,
) -> Result<Json<ApiResponse<()>>, ChatApiError> {
    state
        .store(relay)
        .await?
        .forget_memory(id, memory_id, input.expected_revision)
        .await?;
    Ok(Json(ApiResponse::success(())))
}

async fn private_response(
    request: axum::extract::Request,
    next: axum::middleware::Next,
) -> Response {
    let mut response = next.run(request).await;
    response.headers_mut().insert(
        axum::http::header::CACHE_CONTROL,
        axum::http::HeaderValue::from_static("no-store"),
    );
    response
}

async fn accept(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
    Json(input): Json<AcceptConversationMessage>,
) -> Result<(StatusCode, Json<ApiResponse<SupervisorMessageReceipt>>), ChatApiError> {
    let store = state.store(relay).await?;
    if !state.accepting_messages {
        return Err(ChatApiError(
            StatusCode::SERVICE_UNAVAILABLE,
            "Supervisor model is not configured; saved history remains available",
        ));
    }
    // Voice input must arrive through the authenticated voice adapter and its
    // segment idempotency contract, not by self-labelling an arbitrary request.
    if input.origin != ConversationInputOrigin::Typed {
        return Err(ChatApiError(
            StatusCode::BAD_REQUEST,
            "Voice transcripts require a bound voice session",
        ));
    }
    let accepted = store.accept(id, &input).await?;
    Ok((
        StatusCode::ACCEPTED,
        Json(ApiResponse::success(SupervisorMessageReceipt {
            message: accepted.message,
            run_id: accepted.run.id,
        })),
    ))
}

async fn replay(
    store: &ConversationStore,
    id: Uuid,
    cursor: i64,
) -> Result<Vec<SupervisorEvent>, ChatApiError> {
    store.events(id, cursor, 200).await?.into_iter().map(|event| {
        let mut payload: Value = serde_json::from_str(&event.payload).map_err(|_| ChatApiError(StatusCode::INTERNAL_SERVER_ERROR, "Stored supervisor event is invalid"))?;
        // Worker leases and full context/model manifests are internal, not UI
        // content. Event payloads expose only the durable status projection.
        if event.event_type == "run.status" {
            payload = json!({"id": payload["id"], "input_message_id": payload["input_message_id"],
                "status": payload["status"], "generation": payload["generation"],
                "output_message_id": payload["output_message_id"], "error": payload["error"]});
        }
        Ok(SupervisorEvent { conversation_id: event.conversation_id, seq: event.seq, event_id: event.event_id,
            event_type: event.event_type, schema_version: event.schema_version, entity_id: event.entity_id,
            revision: event.revision, occurred_at: event.occurred_at, payload })
    }).collect()
}

async fn events(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
    Query(query): Query<ReplayQuery>,
) -> Result<Json<ApiResponse<Vec<SupervisorEvent>>>, ChatApiError> {
    let store = state.store(relay).await?;
    validate_cursor(&store, id, query.after_seq).await?;
    Ok(Json(ApiResponse::success(
        replay(&store, id, query.after_seq).await?,
    )))
}

async fn validate_cursor(
    store: &ConversationStore,
    id: Uuid,
    cursor: i64,
) -> Result<(), ChatApiError> {
    let conversation = store.get(id).await?;
    if cursor < 0 || cursor >= conversation.next_seq {
        return Err(ChatApiError(
            StatusCode::BAD_REQUEST,
            "Replay cursor is outside conversation history",
        ));
    }
    Ok(())
}

async fn events_ws(
    State(state): State<ConversationApiState>,
    Path(id): Path<Uuid>,
    relay: Relay,
    Query(query): Query<ReplayQuery>,
    upgrade: WebSocketUpgrade,
) -> Result<Response, ChatApiError> {
    let store = state.store(relay).await?;
    validate_cursor(&store, id, query.after_seq).await?;
    Ok(upgrade.on_upgrade(move |socket| stream(socket, store, id, query.after_seq)))
}

async fn stream(mut socket: WebSocket, store: ConversationStore, id: Uuid, mut cursor: i64) {
    let mut interval = tokio::time::interval(std::time::Duration::from_secs(1));
    loop {
        tokio::select! {
            incoming = socket.recv() => match incoming {
                None | Some(Err(_)) | Some(Ok(Message::Close(_))) => break,
                _ => {}
            },
            _ = interval.tick() => {
                let Ok(snapshot) = store.get(id).await else { break; };
                if snapshot.next_seq - 1 - cursor > 2000 {
                    let _ = socket.send(Message::Text(json!({"type":"resync_required", "snapshot_cursor": snapshot.next_seq - 1}).to_string().into())).await;
                    break;
                }
                let Ok(events) = replay(&store, id, cursor).await else { break; };
                for event in events {
                    let Ok(text) = serde_json::to_string(&event) else { return; };
                    match tokio::time::timeout(std::time::Duration::from_secs(10), socket.send(Message::Text(text.into()))).await {
                        Ok(Ok(())) => cursor = event.seq,
                        _ => return,
                    }
                }
            }
        }
    }
    let _ = socket.close().await;
}

fn api_router<S: Clone + Send + Sync + 'static>(state: ConversationApiState) -> Router<S> {
    Router::new()
        .route("/conversations/capabilities", get(capabilities))
        .route("/conversations/resolve", post(resolve))
        .route("/conversations/{id}", get(snapshot))
        .route("/conversations/{id}/messages", get(messages).post(accept))
        .route(
            "/conversations/{id}/messages/{message_id}/evidence",
            get(message_evidence),
        )
        .route("/conversations/{id}/export", get(export))
        .route(
            "/conversations/{id}/history",
            axum::routing::delete(delete_history),
        )
        .route("/conversations/{id}/actions", get(actions))
        .route("/conversations/{id}/evidence/{evidence_id}", get(evidence))
        .route("/conversations/{id}/memories", get(memories))
        .route(
            "/conversations/{id}/memories/{memory_id}",
            axum::routing::delete(forget_memory),
        )
        .route("/conversations/{id}/events", get(events))
        .route("/conversations/{id}/events/ws", get(events_ws))
        .layer(axum::middleware::from_fn(private_response))
        .with_state(state)
}

pub fn router(pool: SqlitePool) -> Router<DeploymentImpl> {
    api_router(ConversationApiState {
        pool,
        enabled: std::env::var("VK_SUPERVISOR_ENABLED").is_ok_and(|value| value == "1"),
        // Set from the configured model worker when it is integrated. Never
        // acknowledge user requests into a queue that has no response consumer.
        accepting_messages: false,
    })
}

#[cfg(test)]
mod tests;
