//! Scoped supervisor knowledge. Model proposals are data, not their own authority.
use db::models::conversation::{ConversationError, ConversationRun, records::MemoryChange};
use serde_json::{Value, json};

use super::{WorkError, context::LocalContext, model::*};

impl LocalContext {
    pub(super) async fn change_memory(
        &self,
        run: &ConversationRun,
        request: &ModelRequest,
        model: &dyn ConversationModel,
        proposal: &MemoryProposal,
    ) -> Result<(Value, ModelUsage), WorkError> {
        self.store.renew(run).await?;
        if proposal.body.trim().is_empty()
            || proposal.body.len() > 4096
            || proposal.claim_key.trim().is_empty()
            || proposal.claim_key.len() > 200
            || proposal.entity_refs.len() > 16
            || proposal.replaces.as_ref().is_some_and(|r| r.revision < 1)
        {
            return Ok((
                json!({"error":"invalid_memory_proposal"}),
                ModelUsage::default(),
            ));
        }
        let records = self.store.list_memories(run.conversation_id).await?;
        let existing = proposal
            .replaces
            .as_ref()
            .and_then(|reference| {
                records
                    .iter()
                    .find(|r| r.id == reference.id && r.revision == reference.revision)
            })
            .cloned();
        // Repeated identical tool calls in one user turn recover the persisted
        // receipt. They neither bill a second assessment nor supersede again.
        if let Some(saved) = records.iter().find(|r| {
            r.source_message_id == request.input.id
                && r.claim_key == proposal.claim_key
                && r.body == proposal.body
                && r.entity_refs.0 == proposal.entity_refs
                && memory_scope(r) == Some(proposal.scope.clone())
                && r.supersedes_id == proposal.replaces.as_ref().map(|v| v.id)
                && r.revision
                    == proposal
                        .replaces
                        .as_ref()
                        .map_or(1, |r| r.revision.saturating_add(1))
        }) {
            return Ok((
                json!({"data":{"memory":saved,"memories":[saved],"already_recorded":true}}),
                ModelUsage::default(),
            ));
        }
        if proposal.replaces.is_some() && existing.is_none() {
            return Ok((
                json!({"error":"memory_changed_reload"}),
                ModelUsage::default(),
            ));
        }
        let response = model
            .assess_memory(&MemoryAssessmentRequest {
                current_user_request: request.input.body.clone(),
                previous_user_requests: request
                    .history
                    .iter()
                    .filter(|m| m.role == "user")
                    .map(|m| m.body.clone())
                    .collect(),
                entity_context: request
                    .exchanges
                    .iter()
                    .filter(|e| {
                        matches!(
                            e.call.tool,
                            SupervisorTool::FindContext { .. }
                                | SupervisorTool::ReadWorkspaceState { .. }
                        )
                    })
                    .map(|e| e.result.clone())
                    .collect(),
                existing,
                proposed: proposal.clone(),
            })
            .await
            .map_err(|e| WorkError::Safe(super::model_failure(e)))?;
        self.store.renew(run).await?;
        if matches!(
            response.assessment.decision,
            MemoryDecision::Clarify | MemoryDecision::Decline
        ) {
            return Ok((
                json!({"data":{"assessment":response.assessment,"saved":false}}),
                response.usage,
            ));
        }
        let result = self
            .store
            .put_run_memory(
                run,
                &MemoryChange {
                    scope: proposal.scope.clone(),
                    claim_key: proposal.claim_key.clone(),
                    body: proposal.body.clone(),
                    entity_refs: proposal.entity_refs.clone(),
                    source_message_id: request.input.id,
                    replaces: proposal.replaces.as_ref().map(|r| (r.id, r.revision)),
                    explicit: matches!(response.assessment.decision, MemoryDecision::Remember),
                    valid_until: None,
                },
            )
            .await;
        let data = match result {
            Ok(record) => {
                json!({"data":{"memory":record,"memories":[record],"assessment":response.assessment,"saved":true}})
            }
            Err(ConversationError::RevisionConflict) => json!({"error":"memory_changed_reload"}),
            Err(ConversationError::NotFound | ConversationError::InvalidRecord) => {
                json!({"error":"memory_scope_or_source_invalid"})
            }
            Err(error) => return Err(error.into()),
        };
        Ok((data, response.usage))
    }
}

fn memory_scope(
    memory: &db::models::conversation::records::ConversationMemory,
) -> Option<db::models::conversation::records::MemoryScope> {
    use db::models::conversation::records::MemoryScope;
    Some(match memory.scope_kind.as_str() {
        "global" => MemoryScope::Global,
        "project" => MemoryScope::Project(memory.scope_id),
        "repository" => MemoryScope::Repository(memory.scope_id),
        "workspace" => MemoryScope::Workspace(memory.scope_id),
        "conversation" => MemoryScope::Conversation(memory.scope_id),
        "session" => MemoryScope::Session(memory.scope_id),
        _ => return None,
    })
}
