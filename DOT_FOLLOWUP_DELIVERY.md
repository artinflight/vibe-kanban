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
