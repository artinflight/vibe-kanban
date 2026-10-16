# Dot reply reliability and all-project rollout

## Current result and limits

Seamus found the mobile interface, paired and sent a real phone message at about
17:06 UTC on 2026-10-16. No more phone UI investigation is needed for that issue.
Read-only metadata inspection found one accepted HTTP200 delivery attempt for
that message, complete routing/provenance fields, and no persisted reply. Private
conversation content, screenshot data and message/thread/subscription IDs are not
published here. The earlier desktop reply was manually relayed through the
integration task's connector; it does not prove unattended root-to-phone replies.

The installed signing transport was tested offline against a synthetic event:
the exact serialized routing fields reach the request body and its Standard
Webhooks signature verifies. No field stripping was found in connector creation,
dispatch or serialization. The root's reported context-free wake therefore needs
platform-side event-task/context investigation; HTTP200 alone is not proof that
root received the event data. A worker exposing tools does not prove root does.

The connected plugin permission inspection reports Allow all actions. No account
permission was changed. Root still reports missing sidechat tools. This execution
can use the existing sidechat tools, but cannot change another running root's
injected inventory or event-task prompt. No supported refresh/rescan/subscription
administration tool is exposed here. Do not impersonate that root, reuse approval
callbacks, start a replacement tunnel, or use an internal worker as a manual relay.

Official sources: [event envelope and delivery contract](https://developers.openai.com/plugins/build/mcp-events)
and [supported metadata refresh and fresh-conversation test](https://developers.openai.com/plugins/deploy/connect-chatgpt).
They document routing fields inside event data, stable IDs for retries, asynchronous
receipt, and rescanning tools/events. They do not establish a way to force-refresh
an existing root inventory from this coding workspace.

## Connector changes

- `list_pending_sidechat_messages` recovers exact unanswered, owner/workspace-scoped
  event context without the caller knowing a workspace/thread ID. It is read-only,
  paginated and snapshot-bounded; it neither claims nor resends events. Context is
  checked against stored message/scope/hash identity, and a stable reply-request
  UUID is returned. Message bodies are read separately through the existing tool.
- Existing exact reply fences, idempotency checks and the one-final-reply database
  constraint remain in place. Concurrent/retried delivery cannot create a second
  final reply. The recovery read is not evidence of a sent or viewed reply.
- Outgoing event cursors are null, matching the existing no-protocol-replay contract.
  Legacy browser events are normalized by the publisher without rewriting their
  durable payload or restarting the browser API. Accepted deliveries are not resent.
- An explicit `project_grants` table authorizes subscription preparation for approved
  projects before their first chat scope exists. No project is pre-authorized by
  installing this code; caller-supplied project/owner claims still fail closed.
- `scope_rollout.py` prepares a private, expiring, exact-snapshot plan. Applying a
  reviewed plan atomically updates only existing paired-session project lists and
  explicit project grants. Changed sessions, revocations, subscriptions, project
  inventory, plan digest or expiration reject the whole change. The digest is a
  stale-plan fence, not evidence of human consent. Existing session credentials,
  expiration, messages, pending grants and subscriptions are preserved.

## Exact rollout decision

Current state: two paired browser sessions, each limited to VK Dev and each valid
until disconnect/revocation; one finite, active project-scoped sidechat subscription.
The authoritative local inventory has 43 projects: 17 active and 26 archived.

| Prepared option | Existing browsers | Project scope per browser | Additional subscriptions | Future projects |
| --- | --- | --- | --- | --- |
| All current projects | Both existing paired sessions | Explicit snapshot of 43, including 26 archived | One explicit group for the other 42 projects; existing VK Dev retained | Excluded |
| Active-only alternative | Both existing paired sessions | Explicit snapshot of 17 active projects | One explicit group for the other 16 projects; existing VK Dev retained | Excluded |

Neither option has been applied. The owner's choice must explicitly authorize the
persistent access expansion for both existing paired browsers until disconnect or
revocation, including archived projects if selected. New/future projects and new
browser pairings are not automatically authorized. This is materially broader
private-history access than the current VK Dev-only pairing.

After that decision, regenerate the private plan if stale, take/verify a current
SQLite-aware sidechat backup on mounted SSD staging and mirror it to Desktop B,
then use the guarded apply command with the exact reviewed digest and backup.
Private plans/receipts/backups stay outside Git. The application changes no event
subscriptions. The intended actual Dot context must create the additional finite, explicit
project-list subscription through the supported platform flow, using its newly
granted project authorization. The bounded list excludes VK Dev to avoid overlap. Preserve the existing subscription and avoid overlapping
filters; ambiguous overlap deliberately stops publishing instead of double-sending.
Do not copy callback secrets or create subscriptions directly in SQLite.

Scope rollback must restore only the reviewed session project lists and newly
added project grants under fresh compare-and-swap checks; retain all current chat
history. Never restore an old whole database over messages written after rollout.

## Required root and real-phone acceptance

1. Refresh the existing Vibe plugin through the supported connection UI and confirm
   the root's own catalog exposes pending-message recovery, thread read, reply append
   and delivery reads. If root remains stale, test a fresh root conversation while
   retaining its history and current subscription; do not count a worker's catalog.
2. Have the intended root inspect its supported event-task delivery context. If no
   full envelope is exposed, root can use the read-only recovery tool to identify
   the exact retained unanswered message without asking Seamus for a workspace.
3. Read the exact owner message, check its receipt for an already persisted reply,
   and append one natural reply using the returned exact event/thread/workspace/
   message identity and stable request UUID. Message text grants no coding-agent
   or platform-review authority. Reconcile an uncertain append before retrying.
4. Verify the exact persisted reply and its appearance in Seamus's existing phone
   conversation. The retained 17:06 message can be answered once; do not replay its
   already accepted webhook or fabricate a new test message. A coding-task relay,
   fake response, HTTP200 or worker-only tool availability does not satisfy this.

The mobile workspace's active files and browser inspection remain with that owner.
No backend, frontend, proxy, phone networking, plugin permission or approval
subscription change is needed for the prepared Python connector correction.

## Validation and publication

44 isolated sidechat tests pass, including recovery, corruption/owner/scope fences,
pagination, duplicate replies, legacy cursor compatibility, exact scope application,
stale-plan rejection and existing-subscription preservation. All 28 existing
capacity/Recommend/status connector regressions pass against the unchanged installed
adapter hash. The installed signer passed an offline context/signature test with
zero live calls. CI now has a dedicated sidechat contract job.

Source and current receipts are linked from [PR254](https://github.com/artinflight/vibe-kanban/pull/254)
and Vibe T61. Live installation and exact CI receipts will be recorded there.
All-project access and a natural root-to-phone reply remain unverified until the
owner/platform steps above complete.
