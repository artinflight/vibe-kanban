# Existing conversations and later Dot updates

## Failure and repair

A pending-message queue is not a conversation directory. After Dot acknowledges
an owner request, `list_pending_sidechat_messages` correctly excludes that
message. Previously there was no supported workspace-to-existing-thread lookup,
and the acknowledgment consumed the only permitted reply slot. A promise to
return later could therefore become undeliverable through the original target.

The existing `get_workspace_reconciliation_status({workspace_id})` now supports
an additive `sidechat` lookup. `available` supplies the existing authorized
`thread_id`; `not_found` means no existing conversation for this owner's scope;
`unavailable` means lookup could not be read safely. It never creates a thread,
changes access, marks anything read, or changes delivery/CU freshness. Original
hold, receipt, readback, credit and report fields keep their original meaning.
The tool's input schema remains unchanged, so cached callers can use the lookup.

Read `read_sidechat_thread` with that thread ID, following pagination. Each
owner message includes `reply_context` with the stored original event, exact
workspace, chain tip and stable request UUID. Select the actual requested work,
including its workspace when an issue has multiple linked workspaces. Check
`get_sidechat_delivery` for that owner message before writing.

An initial reply still targets the owner message. An explicitly requested later
update targets the previous Dot reply supplied as `reply_context.reply_to`,
retaining the **original owner event and workspace**. `append_dot_reply` needs no
new argument. Same-key, same-content retries return the already-persisted reply;
a second writer using a stale target is rejected. After an uncertain write,
keep the original target/request/content and reconcile it; do not take a newly
advanced tip as permission to send the same update again. Ancestry is bounded
and checked against the authenticated thread, scope and workspace. No follow-up
creates a new owner event or webhook loop.

The delivery receipt preserves its original first-reply fields and adds a
`continuation` context with reply count/latest reply identity. Persisted does not
mean spoken, displayed or read by the human. Each actual new Dot reply gets its
own normal unread/attention state; retrying does not reset those states.

## Monitoring boundary

Neither reading a report nor saying “I'll watch” registers a scheduler. The
sidechat publisher wakes Dot for owner messages, not coding-agent completion.
This repair supports exact-thread recovery and delivery when Dot is invoked;
it does not invent a background model or claim that future promised updates
will run automatically. A supported platform automation/completion wake must be
explicitly established before promising unattended monitoring.

## Voice handoff evidence boundary

`dot_voice.notify_parent` is not implemented or advertised by this Vibe
connector. Its uncertain-outcome warning must not trigger an automatic retry or
an alternative action route. No downstream execution or queued action was found
for the reported incident window in the three requested workspaces. That does
not distinguish missing voice delivery from receipt/acknowledgment loss before
Vibe dispatch. The connector's method-only journal lacks the platform voice
call/delegation ID and parent acceptance receipt needed to resolve that gap.
A running Windows ChatGPT application alone does not identify the voice client.

The supported escalation is the original voice conversation's Feedback flow,
including its private session identifier, exact UTC window, tool/warning and
expected parent action. Do not publish conversation or receipt identifiers in
GitHub. Voice dictation into a normal text prompt is a supported alternative for
**new** requests; do not reissue the uncertain request until its original parent
receipt/action state is reconciled. Official guidance:
[Voice](https://learn.chatgpt.com/docs/features/voice) and
[Troubleshooting](https://learn.chatgpt.com/docs/reference/troubleshooting).

## Validation and release

72 Python sidechat tests pass, including read-only answered-thread lookup,
authenticated isolation, exact-event/workspace continuations, concurrent retry,
restart, snapshot and original-receipt preservation. All incumbent project
sidebar, browser API, subscriptions, notifications and publisher suites are
included. No Rust/frontend source or Stop/CU helper changes are required.

Prepare the exact-baseline status overlay with `prepare_context_status.py` and
export `workspace_context` from the existing sidechat shim. Keep the adapter,
CU/Stop modules, legacy input schemas and event definition unchanged. Before
activation verify Desktop B backup/readback and current pins. Adopt the complete
sidechat bundle, retain the latest database and restart only the existing Dot
connector to reload its persistent handler. The browser and publisher can retain
their existing code: the database schema and owner-event behavior are unchanged.
Verify the actual cached status/read/write/receipt path after activation; a
server-side tools listing is insufficient. No Vibe/backend/agent/frontend
restart or model/permission/subscription change is needed. Code-only rollback
retains all later database writes, including valid continuation messages.

## Live acceptance — October 17, 23:04–23:07 UTC

Functional source `831cd88d92aa6495362e9501a634ba4f7c9a73be` is deployed through
connector-only adoption. [PR270](https://github.com/artinflight/vibe-kanban/pull/270)
targets staging. The connector still advertises protocol/version 1.6; the added
behavior is additive, with no new tool-input discovery requirement.

Installed status SHA256:
`f43e9aab0790d8ab735272f1744e7548961794ad4c549f1b7725014b4b7c1289`.
Installed shim SHA256:
`84f72d229b71ff00480c712e571aa593965f9cca3966e0810d1f366aaad5671b`.
The adapter, all CU/report/budget helpers and Stop control retain their prior
hashes. Only the connector process restarted; backend, agents, browser,
publisher, notifier, static server, gateway and frontend retained their identity.
Desktop B before/after backups passed readback; the before archive also passed
isolated restoration and SQLite integrity checks. Private installed pins and
registered-call receipts are retained in the owning Vibe issue handoff.

**Actual cached tool acceptance passed:** workspace status recovered the existing
answered conversation; thread history and original-owner delivery were read;
one later report summary was posted into that exact conversation; receipt and
history returned the same persisted update. Retrying the identical write returned
the same message. Database comparison found exactly one new Dot reply and zero
new owner events. The reply was unread at acceptance; human viewing is not proven.
Original delivery/hold/receipt fields compared equal for three existing
workspaces. CU reporting remained `cu.dot-report.v1`, and its separate stale
credit-budget status and original `readback_fresh:false` were preserved.

The first post-reload remote status read timed out, despite the tunnel recording
one successful enqueue-to-response under 2.5 seconds and the handler returning
to its input wait. A subsequent identical **read** succeeded in 0.467 seconds;
other registered history/write/receipt calls succeeded. This is separate evidence
of a remote read acknowledgment problem, not a correlation proving why the
reported voice delegation failed. No voice action was retried or rerouted.

For the original voice incident, the three target queues were empty and no new
target execution was found in the reported window. Parent delivery versus lost
acknowledgment is still unknown; the platform's original voice session/call and
acceptance receipt are required. Device identity is also unconfirmed. No real
voice-to-main-to-Vibe acknowledgment test has passed, and no unattended monitor
completion trigger was established by this repair.

Local `ops:check`, diff checks and all 72 Python tests passed. The exact functional
source's sidechat, governance, policy, freshness and preservation CI checks
passed; broad backend/frontend jobs were still pending at the handoff. Full
`pnpm run format` ran Rust formatting successfully and then stopped because
Prettier is absent from this checkout. No Cargo compilation or frontend build
was run locally.
