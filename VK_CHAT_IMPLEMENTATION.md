# Implementation sequence and acceptance

Design source: [architecture](VK_CHAT_ARCHITECTURE.md),
[contracts](VK_CHAT_CONTRACTS.md), [voice](VK_CHAT_VOICE.md).
Implementation entry instruction: [handoff prompt](VK_CHAT_HANDOFF.md).

## Recommended first slice

Start with durable text acceptance and direct-session delivery, exercised end to
end in one workspace with a fake model/voice adapter. This proves persistence,
identity, queue ownership and restart behaviour against real VK execution seams
before natural-language routing or audio can conceal failures. Establish the
global conversation's independent identity at the same time, even though its
supervisor is initially a fake adapter. Do not begin with a Retell widget or a
hidden “supervisor project”.

Run a bounded voice API/SDK contract spike early, alongside that foundation when
credentials are available. It must settle server-created call joining, authenticated
custom-model ingress and transcript identity before committing to voice production
code. The text foundation can proceed without a funded provider. Each milestone
below has a demonstrable outcome; it is not a separate architecture exercise.

## Milestones

### 1. Durable conversation and direct delivery foundation

**Establishes:** additive conversation/event/run/action/evidence storage, one global
identity, direct session binding, message idempotency, replay, shared durable queue
and execution receipts. Extract dispatch from existing session handlers so legacy
and new callers share one admission path. Preserve Codex no-queue-fallback, safe
resume anchors, executor configuration and existing agent approvals.

**Dependencies:** source reconciliation against the design baseline; existing DB,
container and executor contracts. Use fake model/voice adapters and isolated test
data. Decide principal/authority mapping in code before opening routes.

**Likely areas:** `crates/db/migrations`, `crates/db/src/models`, new
`crates/services/src/services/conversation/` (store, dispatch, ingestion, replay),
`crates/services/src/services/queued_message.rs`,
`crates/server/src/routes/sessions/`, new `routes/conversations.rs`,
`crates/local-deployment/src/container.rs`, `crates/deployment/src/lib.rs`,
`crates/local-deployment/src/lib.rs`, `crates/server/src/bin/generate_types.rs`.
Wire workers into existing deployment startup/shutdown; no extra daemon.

**Works when:** two clients retry one message and only one delivery is admitted;
legacy direct chat still works; queued non-Codex messages survive restart; unavailable
Codex steering remains a visible conflict; capacity waits keep model/reasoning;
crash at the steering acknowledgement boundary produces honest unknown delivery;
replay after reconnect has no missing/duplicate messages; an archived/missing
workspace does not receive a delayed instruction. A failed/killed predecessor
retains an explicit failed/cancelled queue outcome instead of silently losing the
message (the present consumer discards these queues).

**Early voice spike output:** pinned SDK/API compatibility evidence and authenticated
call binding test, or a precise provider blocker; no invented SDK methods. This
is a development acceptance gate for the later adapter, not a dependency of text.

### 2. First-class text UI and legacy history integration

**Establishes:** persistent global rail/panel, direct session presentation, shared
composer transport, history pagination, activity drill-down and read watermarks.
Global state survives workspace/project/host navigation; direct chat stays pinned
to the selected session. Existing raw chat, attachments, retries and approvals
remain available.

**Dependencies:** milestone 1 APIs/replay. Global replies can remain deterministic
fixtures until the supervisor milestone; do not mislabel a fixture as a real agent.

**Likely areas:** `packages/local-web/src/app/entry/App.tsx`,
`packages/local-web/src/routes/_app.tsx`,
`packages/web-core/src/shared/components/ui-new/containers/SharedAppLayout.tsx`,
new `packages/web-core/src/features/conversation/`, existing `features/workspace-chat/`,
`shared/lib/api.ts`, `shared/lib/localApiTransport.ts`, UI components in
`packages/ui/src/components`, generated types and localisation resources.

**Works when:** desktop/mobile navigation, reload and two browser clients display
the same history; old turns are projected once; typed inputs do not duplicate their
executor prompt echoes; session switching visibly changes direct target; raw
report links retrieve exact evidence; keyboard focus and screen-reader live
announcements work without reading token-by-token noise; long histories stay
paged/virtualised. Text remains usable without voice/model credentials.

### 3. Supervisor routing and policy

**Establishes:** thin configured model adapter, bounded context directory, live
retrieval, topic focus, target resolution, structured message proposals, safeguards
and per-target result correlation. Native goals/capacity are inspected without
creating a second continuation loop. Direct sends still bypass this model.

**Dependencies:** milestones 1–2. Funded model credentials for live model acceptance;
fake-model contract tests remain runnable without them.

**Likely areas:** new conversation `context`, `resolver`, `model`, `policy`, `worker`
modules; existing workspace summary, project/task/repo models and local compatibility
links; read-only native goal adapter; service configuration/profile conventions;
confirmation/activity UI. Keep remote entity mapping behind an authority adapter.

**Works when:** the product examples resolve appropriate agents without UUIDs;
same-named repos and two active scheduler sessions cause useful clarification;
explicit multi-agent requests retain distinct outcomes; stale targets are
revalidated; an agent completing during routing remains the same session;
unauthorised or prompt-injected tool targets are rejected; paused native goals
remain paused after an informational request; exact ordinary instructions do not
require another confirmation; an indirect destructive instruction cannot bypass
policy by using the message tool.

### 4. Useful explanations, durable memory and attention

**Establishes:** natural summarisation based on full source evidence, raw drill-down,
scoped/versioned memory, read/review watermarks, result subscriptions and attention
classification. Add output presentation for direct voice without dispatch tools.

**Dependencies:** milestone 3 model and retrieval; milestone 1 evidence ingestion.

**Likely areas:** conversation `memory`, `summarise`, `evidence`, `attention` modules,
`coding_agent_turn`/log history consumers, memory settings and activity components,
existing notification integrations. Add scoped text indexes first; measure before
introducing embeddings.

**Works when:** “unless something fails, leave validation out” survives restarts and
new conversations in the right scope; fitRDY conventions do not leak elsewhere;
superseding/forgetting invalidates derived summaries; a long successful report is
concise but a failed test is disclosed; “what tests/files/why/exact words?” retrieves
source evidence; missing rationale causes a question to the agent; “since I last
checked” uses acknowledged source coverage; unread completion is not falsely
classified as a pending user decision.

### 5. Provider-neutral browser voice

**Establishes:** fake and Retell adapters, global/direct mic controls, selectable
voice with previews, transcript reconciliation, mixed input, interruption and
reconnect on the same conversation. Retell custom-model mode uses VK's existing
coordinator/presenter; it receives no separate orchestration prompt/tool authority.

**Dependencies:** milestones 1–4, successful early voice spike, funded provider,
approved processing/retention settings and reachable authenticated ingress. Implement
and test fixtures before external setup. Deployment follows the normal VK runbook.

**Likely areas:** new conversation `voice` service/adapters, narrow provider ingress
routes, server configuration, frontend `features/conversation/voice`, provider SDK
package/lockfile, settings and microphone UI. Keep vendor imports within adapters.

**Works when:** start a browser call without a telephone, see live captions, send
an instruction, end audio, then read/continue by text on another device; repeat in
a direct workspace without supervisor routing. Transcript snapshot replay,
response retries, reminders, webhook duplication, mid-sentence revisions and
barge-in never duplicate actions. Disconnection is recoverable and unknown
playback remains labelled. Operator accepts a convincing Irish-accent voice using
the actual realtime path. A fake replacement provider passes the same conversation
conformance tests without changing stored messages/memory/actions.

### 6. Recovery, privacy and controlled rollout

**Establishes:** integrated fault recovery, ownership isolation, exports/deletion,
usage controls, operational observability and release readiness. This milestone
validates the complete product, not only happy-path voice.

**Dependencies:** all preceding milestones and representative isolated executor and
provider acceptance. Remote-only/cloud-wide sharing is not silently included;
capability-gate unsupported authorities until their ownership adapter is validated.

**Likely areas:** existing test infrastructure across DB/services/server/frontend,
conversation worker startup/reconciliation, telemetry, settings, release guidance,
SQLite migration/offline query metadata and backup manifests.

**Works when:** the acceptance matrix below passes; no legacy direct chat/goal/
capacity/approval regressions; backup/restore preserves conversation and raw evidence;
voice failure leaves text usable; kill switches stop new model/voice actions without
losing accepted messages or stranding queued work. Record measured latency/cost and
remaining browser limitations. Promotion follows staging checks and explicit human
QA; production interruption follows the existing restart protocol.

## Acceptance matrix and testing strategy

| Layer | Required evidence |
| --- | --- |
| Schema/repositories | Empty and populated DB upgrades; uniqueness/FK/scope validation; sequence races; correction/supersession/deletion; idempotent rerun; SQLx metadata generation |
| Dispatch service | Idle/running/finished race; supported/unsupported steering; legacy queue consumption; queue cancellation race; capacity denial/recovery; executor config retention; paired global/direct sends |
| Crash boundaries | Stop after message commit, delivery claim, process admission, executor acknowledgement, result arrival and event commit; recover without false success or blind duplicate dispatch |
| Model tools/security | Typed argument rejection; fake authority IDs; prompt injection in reports/memory; inaccessible evidence excluded before inference; expired/changed confirmations; no model filesystem/shell authority |
| Retrieval/evaluation | Curated anonymised reports and routing cases; deterministic policy tests plus human-reviewed semantic outcomes. Grade relevance, groundedness, brevity, missed failures and memory leakage, not exact sentence matching |
| Raw evidence | Long/paged reports; command failure buried in logs; dropped retry; source unavailable; historical vs current diff; incomplete log persistence while process completes |
| Voice adapter | Full snapshot repeats; partial corrections; same words twice; silence reminders; interrupted/unspoken response; reconnect/new call; mismatched call identity; duplicate/out-of-order webhooks; forged/expired ingress |
| UI/accessibility | Desktop and narrow mobile; keyboard/panel focus; screen-reader captions; long history; navigation/host remount; microphone refusal; logout; offline draft; two-device mic takeover |
| Native goals | Interactive sessions and goal sessions; needs-input/budget/capacity pause; no inferred activation; existing stop/resume/checkpoint behaviour retained |
| Operator acceptance | All product examples, Irish voice audition, real phone/browser network transitions and documented background limitations, natural summaries with successful evidence drill-down |
| Operational | Backups/restores, mounted bulk storage, retention/export/deletion propagation, provider outage/rate limits, spend limits, event backlog recovery and no unauthorised local API exposure |

Test important policy/integration behaviour in Rust and UI transport/rendering in
the established package tests. Use deterministic model/provider fixtures in CI;
external acceptance is separately labelled and budgeted. Suggested initial service
objectives to measure, not provider guarantees: text durable acknowledgement under
500 ms p95 in local load tests; first audible acknowledgement under 2 seconds p95
after a stable speech boundary on the nominated network; no lost committed messages
and no unreported uncertain deliveries. Report provider/agent time separately.

Run narrow checks throughout. Before PR into `staging`, run repository baseline
`pnpm run format`, `pnpm run ops:check`, `pnpm run check`, `pnpm run lint`,
`cargo test --workspace`, affected type generation checks and `pnpm run prepare-db:check`.
Remote modifications additionally need the remote generation/DB checks specified
in AGENTS.md. Report environmental failures precisely. Use mounted SSD bulk test
artefacts and shared Cargo target with incremental compilation disabled. Use the
preview guide for UI smoke tests; never validate mutations against production data.

## Migration and rollout

1. Add tables and capability flags disabled by default; preserve existing routes.
2. Switch all session queue producers/consumers atomically in a release, with
   compatibility DTOs and one durable consumer. Existing queues are in memory:
   inventory/drain them before an authorised restart or provide an explicit
   operator-reviewed migration capture. Never claim SQLite migration saves them.
3. Lazily index old direct history with a source watermark; no wholesale log copy.
   Backfill in bounded batches and reconcile late final reports by revision.
4. Enable direct text for the operator, then global reads, then ordinary messaging,
   summarisation/memory and finally voice. Action policy stays enforced at every
   stage. Distinguish frontend visibility, model invocation and dispatch kill switches.
5. Disabling supervisor/voice leaves history readable and accepted delivery
   reconciliation running. Returning to legacy UI must still use durable queue
   endpoints. A binary rollback across queue migration requires draining/exporting
   pending deliveries; an older in-memory consumer cannot recover them. Prefer a
   forward fix; preserve DB/logs and post-release writes under the restart protocol.
6. Human QA precedes staging-to-main production promotion. Document actual provider
   versions, accepted voice and retention configuration when integrated. Rehearse
   coordinated backend/UI deployment and restore before requesting cutover.

## Operator decisions and defaults

| Decision | Recommendation | Needed by |
| --- | --- | --- |
| Supervisor model account/model and budget | One configurable streaming/tool-capable hosted model, separate from coding executors; fixtures until credentials exist | Live milestone 3 acceptance |
| Retell account, ingress hosting and external data processing | Server-created browser calls; narrowly authenticated ingress; no raw audio retention and minimal vendor storage, verified in account | External voice spike / milestone 5 |
| Irish voice | Audition natural Irish English voices, then select; retain per-conversation override | Milestone 5 human acceptance |
| Notification policy | Relevant result updates in history; no unsolicited speech outside an active call | Default can ship; user may change |
| Multi-user cloud-wide ownership and background native calling | Keep future extensions explicit; initial one trusted authority with foreground cross-device access | Only if that broader scope is requested |

No decision is required to begin the core text implementation. Provider choices
are real live-integration gates, not reasons to repeat architectural investigation.
