# Persistent conversational orchestration

Design baseline: 2026-09-15, source commit `2fd585ac30bfa75975f6319585e4a66bb684fdcf`.
Status: proposed implementation design; existing capabilities and proposed additions
are distinguished below. This describes source, not the deployed runtime.

Read with [contracts](VK_CHAT_CONTRACTS.md), [voice](VK_CHAT_VOICE.md),
[implementation plan](VK_CHAT_IMPLEMENTATION.md), and
[implementation handoff](VK_CHAT_HANDOFF.md). These root-level design documents
follow the repository's `VK_*.md` architecture/runbook convention.

## Product and experience

VK gains one enduring assistant conversation above projects and a direct
conversation with the selected agent inside each workspace. Both accept text and
voice, persist in VK, and remain readable across devices connected to the same
VK authority. The supervisor is an application capability, with no artificial
project, repository, worktree, or coding-agent session.

Put a Chat entry in the application rail. On desktop it opens a resizable global
panel alongside the current page; on narrow screens it opens a full-height sheet.
Offer an expanded history view using the same conversation ID. Opening, closing,
changing projects, and changing input mode preserve history, draft and microphone
state. Closing a panel while voice remains active leaves a conspicuous mic/stop
control. Browser reload may end audio but must not end the conversation.

The global composer says “Supervisor”; the workspace composer names its selected
session. Switching sessions explicitly changes the direct target. Workspace chat
retains its existing transcript and advanced controls. Add voice and a readable
presentation of results there; the user's input goes directly to that session,
without a supervisor routing/model round trip. A lightweight presentation model
may translate the agent's output for speech; it has no dispatch tools.

A normal reply explains the material outcome, failure, decision or question in
natural language. Length follows the situation. Routine successful validation,
commit metadata and tool chatter stay in expandable evidence. An activity chip
such as “Sent to Android · onboarding” exposes exact recipients, transmitted
instruction, delivery status and linked result. A summary is visibly a summary;
“Original” opens the untouched report. These are affordances, not mandatory
sections in every response.

Examples and acceptance intent:

- “Tell the fitRDY Android agent web remains the source of truth”: resolve the
  named project and current Android session, send the instruction, retain its
  exact wording and source relationship in the appropriate project scope.
- “What happened with Mission Perform since I last checked?”: read live changes
  after this user's last acknowledged review watermark, summarise outcomes and
  outstanding requests; do not merely count unseen messages.
- “Ask the scheduler agent why”: link the question to its latest relevant report,
  dispatch to that session and return the eventual answer in this conversation.
- “Which projects are waiting on me?”: distinguish pending tool approval, explicit
  user question, goal needs-input, failure and merely unread successful work.
- “Check the two mobile parity agents”: intentionally resolve a set and summarise
  both, retaining separate outcomes if one is unreachable.

## Current architecture: evidence and reuse

Paths below are the investigation map for implementation. Read named symbols,
not old continuity claims about live service ports.

| Area | Source and observed behaviour | Classification / proposed use |
| --- | --- | --- |
| Local entities | [project.rs](crates/db/src/models/project.rs), [task.rs](crates/db/src/models/task.rs), [workspace.rs](crates/db/src/models/workspace.rs), [workspace_repo.rs](crates/db/src/models/workspace_repo.rs), [repo.rs](crates/db/src/models/repo.rs) | **Reuse** IDs and relationships; add a small context projection |
| Agent continuity | [session.rs](crates/db/src/models/session.rs), [execution_process.rs](crates/db/src/models/execution_process.rs), [coding_agent_turn.rs](crates/db/src/models/coding_agent_turn.rs) | **Reuse** sessions, executor configuration, safe resume anchors and interrupted-context recovery |
| Sending | [sessions/mod.rs](crates/server/src/routes/sessions/mod.rs) `follow_up`; [queue.rs](crates/server/src/routes/sessions/queue.rs) | **Small extension**: extract shared dispatch service and add durable receipts/idempotency |
| Running delivery | [container.rs](crates/local-deployment/src/container.rs) `try_steer_active_turn`, `consume_queued_follow_up`; [queued_message.rs](crates/services/src/services/queued_message.rs) | **Small extension with reliability risk**: persist queue and receipt state; keep existing capability decisions |
| Raw history | [execution_process.rs](crates/services/src/services/execution_process.rs), [execution_logs.rs](crates/utils/src/execution_logs.rs), [log_history.rs](crates/server/src/routes/execution_processes/log_history.rs) | **Reuse** JSONL logs and finite normalised-history pages; add stable evidence references |
| Direct frontend | [SessionChatBoxContainer.tsx](packages/web-core/src/features/workspace-chat/ui/SessionChatBoxContainer.tsx), [useSessionSend.ts](packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts), [useSessionQueueInteraction.ts](packages/web-core/src/features/workspace-chat/model/hooks/useSessionQueueInteraction.ts), [useConversationHistory.ts](packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory.ts) | **Small extension**: shared transport, transcript identity and voice controls; retain editor/attachments/retry behaviours |
| Summary evidence | [workspace_summary.rs](crates/server/src/routes/workspaces/workspace_summary.rs), `CodingAgentTurn.summary`, [DisplayConversationEntry.tsx](packages/web-core/src/features/workspace-chat/ui/DisplayConversationEntry.tsx) | **Reuse** status and raw report, **new** semantic translation; existing summary is not a conversational synopsis |
| Shell | [SharedAppLayout.tsx](packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx), [_app.tsx](packages/local-web/src/routes/_app.tsx), [App.tsx](packages/local-web/src/app/entry/App.tsx) | **Small extension**: rail/panel and provider above route/host remounts |
| Local persistence | [db/lib.rs](crates/db/src/lib.rs), [migrations](crates/db/migrations), [saved_chat_message.rs](crates/db/src/models/saved_chat_message.rs), [scratch.rs](crates/db/src/models/scratch.rs) | **Reuse** SQLx/SQLite; **new** conversation/memory tables. Saved messages are reusable composer snippets, scratch is draft/UI state, neither is conversation storage |
| Events | [events.rs](crates/services/src/services/events.rs), [events route](crates/server/src/routes/events.rs), [execution routes](crates/server/src/routes/execution_processes.rs) | **Reuse** event plumbing: SSE `/api/events`, JSON-patch WebSocket execution/log streams. **Small extension**: committed conversation sequence/replay |
| Local/remote bridge | [local_compat.rs](crates/server/src/routes/local_compat.rs), [remote/workspaces.rs](crates/server/src/routes/remote/workspaces.rs), [localApiTransport.ts](packages/web-core/src/shared/lib/localApiTransport.ts) | **Reuse** actual links and host-aware transport; never infer shared IDs by name |
| Cloud | [remote guide](crates/remote/AGENTS.md), [shapes.rs](crates/remote/src/shapes.rs), [remote auth](crates/remote/src/auth) | **Reuse when remote support is enabled**: Postgres, membership checks, Electric read sync and REST mutations; no new cloud conversation replica initially |
| Permissions | [routes/mod.rs](crates/server/src/routes/mod.rs), [origin.rs](crates/server/src/middleware/origin.rs), [relay_request_signature.rs](crates/server/src/middleware/relay_request_signature.rs), [approvals.rs](crates/services/src/services/approvals.rs) | **Reuse** request and executor approval boundaries; **new** durable orchestration confirmation grants |
| Autonomous/child agents | [Codex client](crates/executors/src/executors/codex/client.rs), [goals.rs](crates/executors/src/executors/codex/goals.rs), [capacity.rs](crates/server/src/routes/capacity.rs), [subagent_job.rs](crates/db/src/models/subagent_job.rs) | **Reuse** native goals/checkpoints, capacity admission, root/child relationships; no second goal continuation loop |
| Supervisor, memory, voice | No first-class equivalent in the inspected paths | **New subsystems** inside existing backend/frontend packages, not new independently deployed services by default |

### Entity relationships that routing must respect

Local `Project` has `Task` rows; a workspace optionally links a task. A workspace
has multiple repositories through `WorkspaceRepo`, including a target branch per
repo, and multiple `Session` rows. A session has multiple `ExecutionProcess` rows;
processes include coding runs, setup, cleanup, archive and dev servers. Coding
turns hold prompts, final reports and provider thread/message resume identifiers.
A process being completed does not prove the user's task or native goal is done.

`Workspace.branch` and `container_ref` are branch/filesystem context, not agent
identity. A provider thread ID is not a VK session ID. The existing
`WorkspaceContext.orchestrator_session_id` is simply the first workspace session;
it is not a global supervisor. `SubagentJob` represents children of a session,
including reconstructed Codex thread edges; do not assume each child is a
separately addressable workspace. Route through its owning session unless its
executor exposes a supported child-message capability.

Cloud uses project/issue/workspace link entities, including `local_workspace_id`;
local `/v1` compatibility maps local tasks and can expose synthetic contexts.
Local `Project.remote_project_id` is another explicit mapping. Repository
membership is not a reliable project identity: several workspaces/projects can
share a repo. Keep entity keys as `(authority_id, kind, id)`; retain link provenance
and distinguish local task IDs, remote issue IDs and synthetic IDs.

## System boundaries and ownership

```text
Global panel ──┐                         ┌── bounded context/read tools
              ├── VK Conversation API ─┼── supervisor model ── action proposal
Direct chat ──┘          │              └── direct target ──────┐
                        │                                     v
Browser audio <-> Voice adapter                       policy + dispatcher
                        │                                     │
                        v                                     v
             SQLite conversation/events              existing sessions/container
             memory/actions/evidence                 steering/queue/follow-up
                        ^                                     │
                        └──── result ingestion <── turns/logs/events
```

VK owns identity, history, memory, routing candidates, permissions, action
lifecycle, retrieval and delivery receipts. The supervisor model interprets
intent, asks meaningful clarifications, proposes tools and explains results.
Existing coding agents retain implementation judgment and executor permissions.
Voice infrastructure owns audio transport, speech recognition, synthesis,
endpointing and interruption detection. It never owns dispatch authority or the
canonical conversation.

Recommend a small server-side `ConversationModel` interface for streaming text,
typed tool proposals, cancellation and usage reporting. Implement one configured
hosted-model adapter first. Existing executor integrations are coding-agent
runtimes with workspace/process lifecycles; using a hidden coding workspace for
the supervisor would add filesystem authority, startup latency and misleading
identity. Do not generalise or replace those executors. API model credentials and
costs are separate from existing coding-agent accounts. Keep provider/model
selection configurable; obtain the operator's funded provider before live model
acceptance. A deterministic adapter supports earlier development/tests.

The supervisor receives compact intent, applicable preferences, relevant state,
source reports and tool capabilities. Application code enforces schemas,
authorisation, deduplication and concurrency. Prompts explain why concise,
evidence-grounded communication matters, rather than prescribing a response
checklist or micromanaging reasoning. Tool results and repository instructions
are labelled evidence from their scope, not higher-authority supervisor policy.

## Context and natural-language routing

Maintain a bounded, rebuildable entity directory from existing database state and
explicit remote links. Store names/aliases, project and repo relations, workspace
lifecycle, session/executor identity, latest relevant activity and source revision.
Use indexed name/alias lookup and filtered SQL first; semantic search is an
optional later improvement, not a mandatory vector database.

For each turn:

1. Load conversation focus, explicit references and authorised recent entities.
2. Narrow by project/repository names, issue/workspace title, branch, activity and
   session. Current page is a hint in global mode, a pinned target in direct mode.
3. Give the model a bounded candidate set with differentiating names and dates.
   Active work ranks ahead of archived work unless the user asks historically.
4. Resolve one target or an intentional set. “The two parity agents” is a set;
   two equally plausible scheduler sessions is a clarification. Clarify using
   human names and recent work, not UUIDs.
5. Reload target lifecycle, running process, executor choice, access and native
   goal state immediately before an action. Freeze recipient IDs on the action.

Conversation focus is versioned, scoped to topic segments and expires as a
routing assumption after inactivity (default 30 minutes). Named references still
work after expiry. Navigation or a topic change never silently rewrites an
already accepted action. Changing topics while speaking can cancel an uncommitted
proposal; already delivered instructions require an explicit corrective message.
A new session replacing a completed one requires a new resolution, not automatic
retargeting of pending delivery.

Build context on demand from summaries plus relevant full reports, goals and
approval state. Use per-source `observed_at` and revision, not one invented
universal “current” timestamp. Invalidate on VK events, reconcile on startup and
periodically (initial 15-second active-directory refresh), and query authoritative
state before mutation. Remote unavailability means “last observed” with timestamp.
Running status, files changed, branch head, tests and capacity are live facts,
never durable memory. Group cross-agent changes using explicit issue/repo/branch
relations and evidence; overlapping repos are a warning signal, not proof of a
conflict. Ask owners for a decision when required; no automatic merges.

## History, memory and evidence

[Contracts](VK_CHAT_CONTRACTS.md) specifies the persistence model. One default
global conversation per principal/authority retains topic segments and searchable
history. Direct conversations are one per VK session; a workspace entry resolves
the selected session rather than flattening independent agents into one history.
A direct result can be referenced in global history without duplicating dispatch.

Keep four distinct things:

- **History:** user/assistant utterances, transcript revisions and activity.
- **Knowledge:** durable preferences, conventions, decisions and relationships.
- **Working context:** compact derived summaries/focus with source coverage.
- **Live state:** fetched projects, approvals, goals, processes and repository state.

Memory scopes are principal-global, project, repository, workspace, conversation
and session, represented by typed scope references rather than six new stores.
Scope is mandatory. Prefer the smallest applicable scope: “web is authoritative
for fitRDY onboarding” is a project relationship, not a rule for every Android repo.
A repository convention crossing projects must be explicitly repository-scoped.
A memory involving two entities is retrievable only when access permits both.

Explicit “remember”, durable preference corrections and clear standing instructions
create active memories with a visible undo/edit activity. Inferred long-term facts
become proposed memories; temporary status does not. Save the source utterance,
claim, scope, author, confidence, revision, validity and any entity links. Updates
supersede an old revision transactionally; deletion creates a tombstone and removes
it from retrieval. User corrections outrank inferred memories. More specific
scope overrides a general default where compatible; unresolved contradictory
instructions are presented as a conflict, never silently blended. Policy and live
facts cannot be overridden by remembered preferences. Users can list, edit,
rescope, forget and inspect memory provenance from chat or settings.

Retrieve active applicable memories under a token budget, recording exact versions
used. Summaries have coverage cursors and evidence references, never replace
history, and are invalidated by corrected/deleted source content. No training on
personal memory is needed. Forgetting must invalidate summaries/search caches and
prevent automatic re-extraction from a forgotten source.

### Conversational translation

On result ingestion, read the complete final report and relevant failure/status
signals. If needed inspect logs/diffs, with finite pages and bounded hierarchical
summarisation for large reports; record any coverage gap. Identify what addresses
the user's intent and what needs attention. Suppress routine passing validation by
default, while surfacing failures or missing validation that materially limits the
claim. Preserve uncertainty: “the agent reports” is different from independently
verified success. A parser for fixed completion-report headings is not sufficient.

Link the answer to the exact report revision, execution, log entries or repo-state
evidence used. “Show exactly what it said” retrieves the raw report; “what tests?”
retrieves the relevant command/results; “what files?” fetches the relevant diff or
recorded repo state, explicitly distinguishing current files from completion-time
files. “Why?” uses stated rationale; if absent, ask the agent rather than inventing
its reasoning. Record source selection and summarisation version in activity, not
private model chain-of-thought. Missing/deleted evidence is reported as unavailable.

## Actions, autonomy and permission

Reads normally run immediately within access scope. Explicit ordinary messages
and questions to an unambiguous session need no extra confirmation, including a
small explicitly named recipient set. Sending a question may start an agent turn;
represent that honestly. A request for status should first retrieve existing
information and should not wake every agent unnecessarily.

Application policy classifies semantic action intent, not just transport. Sending
“delete every workspace” to an agent is not a loophole around destructive-action
confirmation. Broad inferred broadcasts, stopping active work, reset/retry with Git
reset, deletion, merge/deploy and permission changes require an exact reviewed
scope and consequence. Initial tool surface supports reads and agent messages;
other operations remain deep links to existing VK controls until dedicated typed
and tested adapters exist. Repeated “yes” cannot authorise a changed target set.

Confirmation grants bind principal, action payload digest, recipient set, state
revision and expiry. Record when the initial user request itself supplies exact
authorisation; avoid redundant confirmation. Executor tool approvals remain with
the existing agent approval mechanism. Surface pending questions/approvals with
their exact context; never approve tools based only on a summarised explanation.

The supervisor works with interactive sessions and native autonomous goals. It
does not create goals from ordinary chat or own a second continuation loop. Goal
creation/resume is an explicit user action through the native mechanism. Respect
needs-input, budget/capacity pauses and selected-session scheduling constraints.
A conversational question must not silently reactivate a paused goal. Report a
blocked delivery with a resume choice when that distinction matters.

## Frontend and authority

Mount the conversation coordinator above the `key={hostId ?? 'local'}` providers
in `_app.tsx`, ideally under authenticated `App.tsx` providers. Render the panel in
`SharedAppLayout`; store selected authority explicitly instead of taking whatever
host the current route happens to use. Reuse TanStack Query, existing host-aware
transport, UI components, virtualised history patterns and design tokens. Zustand
or scratch may hold panel width/draft/focus, never authoritative messages/actions.

Initial deployment has one authoritative local backend and its existing trusted
operator boundary. Desktop and phone access the same backend through the existing
protected access path. “Global” spans its visible projects/workspaces; it does not
mean an unauthenticated internet-wide assistant. Remote-only web and multiple
execution hosts use explicit capability detection. Extend existing relay transport
for authorised remote targets later, with principal mapping and per-target receipts;
never create separate global histories simply because navigation changes host.
Cloud-wide multi-user aggregation is a genuine later scope decision, not required
for one operator's cross-device conversation.

## Tradeoffs and decisions

| Choice | Reason / consequence |
| --- | --- |
| New conversation tables in existing SQLite | Global history cannot satisfy a workspace session's foreign keys; avoids fake workspaces and whole-scratch overwrites |
| Durable shared queue/dispatch extension | Changes a sensitive execution boundary but avoids two competing queue consumers and false delivery promises |
| New thin supervisor model adapter | Avoids coding-runtime authority and launch latency; requires separate model credentials/budget |
| Direct session bypass plus optional output presentation | Retains direct agent semantics without speaking raw test logs; presentation model cannot issue actions |
| Append-only events with queryable rows | Reliable replay without a new message broker or replatforming all VK state into event sourcing |
| Scoped relational memory first | Easier provenance/deletion/isolation; semantic search can be added after measuring retrieval misses |
| Retell custom-model integration | More integration responsibility than a managed vendor agent; keeps VK's conversation and action logic shared with text |
| Preserve canonical text separately from speech delivery | Honest interruption history; neither generated text nor provider playback alone is the entire conversation |

Real operator decisions are the funded supervisor model account, voice account and
acceptable external processing/retention, and the auditioned Irish voice. Recommend
one local authority, no raw audio retention, user-requested summaries plus relevant
instruction-result updates, and no unsolicited spoken announcements outside an
active voice conversation. Optional cloud-wide sharing, telephone access and
background mobile calling can be chosen later without blocking the core design.
