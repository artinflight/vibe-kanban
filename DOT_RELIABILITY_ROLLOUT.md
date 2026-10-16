# Dot reply reliability and all-project rollout

## Discovery follow-up

Seamus performed Refresh Tools at about 17:54 UTC. The configured facade exposes
the complete schema and the registered coding-plugin recovery call now succeeds;
root and an earlier fresh internal worker still report stale inventories/event
filters. Read [the timestamped trace and supported resolution](DOT_DISCOVERY_TRACE.md).
Do not repeat the same refresh or assume an exact platform cache root cause.
No runtime/permission/credential/subscription changes were made while tracing.

## Current result

Seamus approved connector-only activation at 17:39 UTC on 2026-10-16 and explicitly
included every current project, archived projects and automatic future projects.
The earlier finite-only alternatives are superseded. No further scope approval,
phone pairing or phone UI investigation is required for this work.

The previously denied activation was retried once with that exact authorization
and succeeded. Recovery source `d8ceceb8f` was installed first; complete-scope source
`d2c79543ea373680da79944bd98756639d23cc0c` is now selected by the sidechat module
pointer. Only `vibe-dot-connector.service` and
`vibe-dot-sidechat-publisher.service` restarted. Browser API process, frontend
pointer, Vibe backend and workspace agents were preserved. The mobile owner's
files and browser work were not touched.

| Capability | Verified status |
| --- | --- |
| Existing paired browser access | Both sessions expanded from VK Dev only to all 43 current projects, including 26 archived |
| Future project access | Persistent policy enabled; publisher reconciles authoritative projects every five seconds into the same approved sessions |
| Existing notification subscription | Preserved exactly; VK Dev delivery remains on its original destination |
| Other current/future notifications | Supported all-project event filter is installed and tested; its platform subscription is still required |
| Owner-message context | Complete fields preserved by stored and signed events; pending-message recovery works locally without workspace input |
| Root tool inventory/event-task context | Platform verification still required; this execution cannot refresh another running root |
| Real phone reply | Unverified: the retained 17:06 message has one accepted webhook attempt and no persisted reply |
| Earlier desktop reply | Successful manual integration-task relay, confirmed in Seamus's screenshot; not unattended root acceptance |

## Exact persistent-access change

The two existing paired browser sessions previously carried a finite VK Dev-only
project list and remained valid until disconnect or revocation. The guarded,
backed-up application changed each list to the authoritative inventory of 43
projects (17 active, 26 archived), granted those projects for event preparation,
and enabled a persistent owner policy tied to those exact reviewed session IDs.
Credentials, CSRF values, expiration and revocation were not changed. Future
projects, including projects created archived, are added automatically within the
publisher's five-second scan interval. There is no fixed 43-project ceiling.

This is materially broader private-history access. The owner's explicit current,
archived and future-project instruction authorizes it; no additional access
choice is pending. Revoked or expired sessions stay revoked or expired. A later
browser pairing is not silently added to the reviewed-session policy; pairing
and device authorization remain separate from automatic project coverage.
Removed projects retain historical grants, while the authoritative workspace
resolver still requires a real project/issue/workspace mapping. An inventory read
failure retains existing scope and logs a sanitized scan error.

`scope_rollout.py plan --all-projects` creates a private, expiring version-2 plan
with exact session/grant/policy/subscription/project snapshots. `apply` fences its
digest, expiry and snapshots in one transaction and requires a matching private
backup through its CLI. The digest prevents stale application; owner authorization
is separate. The legacy finite-plan mode remains available but was not used for
this rollout. `reconcile_projects` never creates sessions, revives revocations,
changes tokens, writes messages or creates subscriptions.

## Supported notification rollout and remaining platform dependency

The actual platform must create the private plan's one additional event request:

```json
{
  "name": "vk.sidechat.owner_message.created",
  "arguments": {
    "all_projects": true,
    "exclude_project_ids": ["<existing VK Dev project ID from the private plan>"]
  }
}
```

The exclusion preserves the current subscription, avoids a second wake for its
messages, and covers every other current and future project without editing a
finite list. The union covers every project. All-project subscriptions require
the authenticated owner's enabled persistent policy and project grants. Existing
finite subscriptions retain their normal renewal responsibilities; the new broad
subscription also needs ordinary platform renewal. Overlapping destinations fail
closed. A thread cannot silently change an already-bound destination, and a
migration conflict cannot starve other threads. Accepted events are never replayed.

**This subscription has not been created.** This coding session has no supported
connection-refresh, event-subscribe or subscription-admin tool. It cannot invent
the platform's callback credentials, copy an existing callback, or insert a
subscription directly into SQLite. All-project browser access is active; complete
all-project notifications remain blocked on this platform operation. This is a
platform capability boundary, not a missing owner approval.

The approved private plan is at
`/mnt/vk-storage/vk-dot-all-projects-20261016/approved-all-projects-plan.json`.
Only its event request is needed for platform registration; the already-applied
expiring access plan must not be reapplied. Reconcile current subscription metadata
before registration and use the real platform verification/secret flow. Private
IDs and callback credentials stay outside GitHub.

## Delivery context and supported tools

Read-only inspection of the retained phone message found its exact routing and
provenance in `data`: thread, project, issue, workspace, message, sequence, author,
intent, reply scope and message hash. An offline test against the installed signer
proved those fields survive serialization and its Standard Webhooks signature
verifies. No connector field stripping was found. HTTP200 is asynchronous webhook
acceptance; it does not prove that the root's task received details or replied.

The installed connector exposes `list_pending_sidechat_messages` in addition to
`read_sidechat_thread`, `append_dot_reply` and `get_sidechat_delivery`. Recovery is
read-only, owner-scoped, snapshot-paginated and verifies stored event/message/scope/
hash identity. It returns exact reply context and a stable request UUID without
requiring the user to name a workspace. It neither claims nor resends events.
The existing one-final-reply constraint, exact event/workspace/message fences and
idempotent retry rules remain in force. Legacy browser cursors are normalized to
null on the wire without rewriting durable messages or restarting the browser.

Root previously lacked those tools although a new worker exposed them. Permission
inspection reported Allow all actions; no account permissions were changed. The
installed discovery/dispatch checks prove connector availability, not injection
into a different running root. Root's context-free event wake and missing inventory
therefore still require actual platform/root verification. No worker or coding-task
manual relay counts as a repair of that boundary.

Official sources: [event envelope and asynchronous delivery](https://developers.openai.com/plugins/build/mcp-events)
and [connection metadata refresh and fresh-conversation testing](https://developers.openai.com/plugins/deploy/connect-chatgpt).
They describe the supported refresh flow; they do not establish an API here for
forcing another root's tool inventory or event-task hydration.

## Required real-phone acceptance

1. The existing connection was refreshed at about 17:54 UTC. Resolve the remaining
   metadata/root-inventory discrepancy through the supported escalation above;
   another identical refresh is not the next step. Confirm root's own inventory
   exposes all four tools and the current event schema. Preserve subscriptions
   and history; do not pair again.
2. Root inspects its actual event-task context. If the envelope remains absent,
   use pending-message recovery to identify the retained unanswered message.
3. Root reads the exact owner message, checks whether a reply already exists,
   and appends one natural reply with the exact returned context and stable
   request UUID. Reconcile an uncertain append before retrying. Message content
   does not grant coding-agent or platform-review authority.
4. Verify the exact persisted reply and its appearance in the existing phone
   conversation. Do not replay its accepted webhook or fabricate a new owner
   message. HTTP200, fixtures and manual integration-worker relays do not pass.
5. Register the broad platform event request above and verify notification coverage
   in addition to the existing VK Dev subscription. Preserve normal renewal.

This execution cannot complete those platform steps with its available tool
inventory. It has requested root verification; no real phone reply is claimed.

## Activation, backup and rollback evidence

Immutable installed source is under
`/mnt/vk-storage/vk-dot-sidechat-live/releases/d2c79543e`.
Private receipts and the pre-scope SQLite backup are retained under
`/mnt/vk-storage/vk-dot-all-projects-20261016`; integrity passed and the Desktop B
mirror checksum matched at
`desktop:B:/vk-backups/dot-sidechat-all-projects-20261016/sidechat-before.sqlite`.
The earlier connector-only activation has its separate staged receipt/backup.
No runtime database, private message, screenshot, receipt identifier, pairing code,
callback secret or private plan is published in this repository.

Post-activation checks verified both services active, both reviewed sessions at
43 projects, 43 explicit grants, enabled future policy for those two sessions,
unchanged browser PID/frontend/adapter and subscription metadata, and unchanged
accepted-event attempts. One retained unanswered message remains. The exact
installed adapter is unchanged from its reviewed baseline.

Before access application, a failed module health check could restore only the
previous module pointer and those same two services. Now that persistent scope
is applied, do not select an older worker incapable of reconciling it. A deliberate
scope rollback must compare current session/policy state, disable future expansion,
and restore only the reviewed scope/grant additions without overwriting messages.
Never restore the whole old SQLite database over new conversations. Browser
revocation and subscription cancellation are separate explicit actions.

## Validation and publication

49 isolated sidechat tests pass, including future archived-project access through
the unchanged browser, session revocation, unchanged subscription credentials,
one-time routing across old/broad subscriptions, corrupt-context rejection,
pagination and final-reply idempotency. All 28 existing capacity/Recommend/status
connector regressions pass against the unchanged installed adapter. The installed
signer passed offline context/signature verification with zero network calls.
Repository formatting, governance and diff checks pass. Full local Rust validation
remains limited by missing GLib development dependencies; hosted CI is tracked
on the PR rather than represented as local validation.

[PR254](https://github.com/artinflight/vibe-kanban/pull/254) targets `staging` and
Vibe T61 carries this handoff. The preserved eleven original changes remain
accounted for; the original clean API/UI worktrees and mobile ownership are intact.
