//! Scoped supervisor knowledge. Model proposals are data, not their own authority.
use db::models::conversation::{
    ConversationError, ConversationRun,
    records::{MemoryChange, MemoryScope},
};
use serde_json::{Value, json};

use super::{WorkError, context::LocalContext, model::*};

impl LocalContext {
    pub(super) async fn control_memory(
        &self,
        run: &ConversationRun,
        request: &ModelRequest,
        model: &dyn ConversationModel,
        reference: &MemoryRevision,
        destination: Option<(&MemoryScope, &[MemoryScope])>,
    ) -> Result<(Value, ModelUsage, Option<TurnEffect>), WorkError> {
        self.store.renew(run).await?;
        if reference.revision < 1 || destination.is_some_and(|(_, refs)| refs.len() > 16) {
            return Ok((
                json!({"error":"invalid_memory_proposal"}),
                ModelUsage::default(),
                None,
            ));
        }
        if destination.is_none() && request.effects.iter().any(|effect| matches!(effect,
            TurnEffect::MemoryForgotten { memory } if memory.id == reference.id && memory.revision == reference.revision)) {
            return Ok((json!({"data":{"forgotten":true,"already_recorded":true}}), ModelUsage::default(), None));
        }
        let records = self.store.list_memories(run.conversation_id).await?;
        if let Some((scope, refs)) = destination
            && let Some(saved) = records.iter().find(|m| {
                m.source_message_id == run.input_message_id
                    && m.supersedes_id == Some(reference.id)
                    && m.revision == reference.revision.saturating_add(1)
                    && memory_scope(m).as_ref() == Some(scope)
                    && m.entity_refs.0 == refs
            })
        {
            return Ok((
                json!({"data":{"already_recorded":true,"memory_id":saved.id,"revision":saved.revision}}),
                ModelUsage::default(),
                Some(TurnEffect::MemoryRescoped {
                    previous: reference.clone(),
                    memory: MemoryRevision {
                        id: saved.id,
                        revision: saved.revision,
                    },
                }),
            ));
        }
        let Some(existing) = self
            .store
            .current_memory(run.conversation_id, reference.id)
            .await?
            .filter(|m| m.revision == reference.revision)
        else {
            return Ok((
                json!({"error":"memory_changed_reload"}),
                ModelUsage::default(),
                None,
            ));
        };
        let Some(old_scope) = memory_scope(&existing) else {
            return Err(WorkError::Safe("context_unavailable"));
        };
        let proposal = MemoryProposal {
            scope: destination.map_or(old_scope, |(scope, _)| scope.clone()),
            entity_refs: destination
                .map_or_else(|| existing.entity_refs.0.clone(), |(_, refs)| refs.to_vec()),
            claim_key: existing.claim_key.clone(),
            body: existing.body.clone(),
            replaces: Some(reference.clone()),
        };
        let response = model
            .assess_memory(&assessment_request(
                request,
                if destination.is_some() {
                    MemoryOperation::Rescope
                } else {
                    MemoryOperation::Forget
                },
                Some(existing),
                proposal,
            ))
            .await
            .map_err(|e| WorkError::Safe(super::model_failure(e)))?;
        self.store.renew(run).await?;
        if !matches!(response.assessment.decision, MemoryDecision::Apply) {
            return Ok((
                json!({"data":{"assessment":response.assessment,"saved":false}}),
                response.usage,
                None,
            ));
        }
        let effect = if let Some((scope, refs)) = destination {
            self.store
                .rescope_run_memory(run, reference.id, reference.revision, scope, refs)
                .await
                .map(|saved| TurnEffect::MemoryRescoped {
                    previous: reference.clone(),
                    memory: MemoryRevision {
                        id: saved.id,
                        revision: saved.revision,
                    },
                })
        } else {
            self.store
                .forget_run_memory(run, reference.id, reference.revision)
                .await
                .map(|()| TurnEffect::MemoryForgotten {
                    memory: reference.clone(),
                })
        };
        match effect {
            Ok(effect) => Ok((
                json!({"data":{"saved":true,"effect":effect}}),
                response.usage,
                Some(effect),
            )),
            Err(ConversationError::RevisionConflict) => Ok((
                json!({"error":"memory_changed_reload"}),
                response.usage,
                None,
            )),
            Err(ConversationError::NotFound | ConversationError::InvalidRecord) => Ok((
                json!({"error":"memory_scope_or_source_invalid"}),
                response.usage,
                None,
            )),
            Err(error) => Err(error.into()),
        }
    }

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
        let existing = if let Some(reference) = &proposal.replaces {
            self.store
                .current_memory(run.conversation_id, reference.id)
                .await?
                .filter(|m| m.revision == reference.revision)
        } else {
            None
        };
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
            .assess_memory(&assessment_request(
                request,
                MemoryOperation::Save,
                existing,
                proposal.clone(),
            ))
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
                    explicit: matches!(response.assessment.decision, MemoryDecision::Apply),
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

fn assessment_request(
    request: &ModelRequest,
    operation: MemoryOperation,
    existing: Option<db::models::conversation::records::ConversationMemory>,
    proposed: MemoryProposal,
) -> MemoryAssessmentRequest {
    MemoryAssessmentRequest {
        operation,
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
                    SupervisorTool::FindContext { .. } | SupervisorTool::ReadWorkspaceState { .. }
                )
            })
            .map(|e| e.result.clone())
            .collect(),
        existing,
        proposed,
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
