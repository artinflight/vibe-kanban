# Dot reply reliability and all-project rollout

## Current verified result

Root's view caught up at 18:07 UTC on 2026-10-16 without another refresh. Root now
exposes `read_sidechat_thread`, `append_dot_reply` and `get_sidechat_delivery` and
sees the complete event schema, including `all_projects` and
`exclude_project_ids`. Root directly read the retained AutoSwitch phone test,
checked that it had no reply, appended one reply and verified
`reply_persisted=true`. This was a direct root reply, unlike the earlier desktop
integration-task relay. The earlier claim that root cannot reply or register the
broader scope is superseded.

Root also updated the existing enabled **Reply to Vibe chats** automation through
the supported platform flow. Its two triggers retain VK Dev and add all projects
excluding VK Dev. Server state was independently checked read-only at 18:23 UTC.
No new refresh, pairing, activation or scope decision is needed.

| Capability | Current evidence |
| --- | --- |
| Paired browser access | Both existing sessions cover all 43 current projects, including 26 archived |
| Future project access | Persistent policy enabled; publisher reconciles authoritative projects every five seconds into those sessions |
| Notification registration | Exactly two active, unexpired subscriptions for the same owner: original VK Dev plus all projects excluding exactly VK Dev |
| Existing subscription preservation | Original subscription identity and project filter remain intact |
| Scope coverage | Installed matcher gives exactly one destination for each of the 43 current projects, with zero gaps or overlaps; broad filter and future policy are enabled |
| Existing message-thread bindings | Match their unique active destination; publisher is active with zero scan/delivery errors in the observed interval |
| Retained phone reply | Exactly one persisted reply, in the original thread and workspace; webhook remains accepted with one attempt |
| Root pending-message discovery | `list_pending_sidechat_messages` remains absent from root; the connector and this coding execution expose it |
| Fresh automatic roundtrip | Pending: a new owner message must wake root and receive a same-conversation reply without manually naming its workspace |
| User-visible receipt | Pending: persisted reply evidence does not establish that Seamus saw the reply on the phone |

The automation's enabled status and root tool usage are owner-reported platform
observations. Subscription filters/lifetimes, unique routing, reply persistence and
same-thread/workspace identity were independently checked on the server. Local
subscription state does not independently prove platform automation execution.
No private message text, screenshot, event/thread/receipt identifier, callback URL,
signing secret or pairing data is published here.

## What remains to accept

Seamus has already been asked for a fresh message in any project. Do not duplicate
that request or ask for pairing/UI debugging. For that existing acceptance check:

1. Observe its normal subscription delivery and confirm root gets enough exact
   event context to identify the conversation without a manual workspace hint.
2. Root reads the owner message, checks delivery for an existing reply, and appends
   one natural reply with the exact event/message/thread/workspace identity and a
   stable request UUID. Reconcile an uncertain append before retrying.
3. Verify the exact persisted reply, its original conversation identity and the
   absence of duplicate final replies or a reply-triggered event loop.
4. Record Seamus's confirmation that the reply is visible in the phone conversation.
   Webhook HTTP200 and `reply_persisted=true` are separate from that observation.

A fresh test outside VK Dev exercises the broad trigger; a fresh test in VK Dev
exercises the preserved trigger. Keep track of which path was actually exercised.
Registration and matcher coverage support all current/future projects, but do not
substitute for a fresh automatic end-to-end sample.

Pending-message recovery is the remaining root tool-availability limitation. The
installed connector advertises it and this coding execution successfully called
it, but root cannot yet use it as a fallback for a context-free wake. If a new wake
lacks event details, preserve that evidence; do not ask Seamus to guess a workspace,
replay accepted webhooks or substitute a worker/coding-task relay. The root's
missing recovery tool can be investigated separately through the prepared
[discovery trace](DOT_DISCOVERY_TRACE.md). A specific platform cache cause has not
been proven. No repeated refresh, credential replacement or permission change is
prescribed.

## Exact access and notification scope

Before the approved rollout, both existing indefinite browser sessions were
limited to VK Dev, with one finite VK Dev notification subscription. The owner
explicitly approved every current project, archived projects and automatic future
projects. Both reviewed sessions were expanded to the authoritative 43-project
inventory (17 active, 26 archived), with explicit project grants and a persistent
owner policy tied to those existing session IDs. Credentials, CSRF, expiration
and revocation were preserved. Future projects, including projects created
archived, are added automatically within five seconds; there is no 43-project
ceiling. Later device pairings remain a separate authorization from project growth.

The existing enabled automation now has these supported filters:

```json
{"project_id": "<original VK Dev project ID>"}
```

```json
{"all_projects": true, "exclude_project_ids": ["<same VK Dev project ID>"]}
```

The broad filter's exact exclusion preserves the original destination and prevents
overlap. These are actual registered subscriptions, not just a prepared plan. The
server check found exactly two active, unexpired subscriptions, all 43 current
projects matching one destination, and no project matching both. The future filter
has no finite project list; the enabled reconciler grants authoritative new
projects automatically. Archived projects are included. Existing message-bearing
threads remain bound to their unique active subscription. Ambiguous destinations
and implicit destination migration continue to fail closed; accepted events are
not resent.

Both subscriptions remain finite and require normal platform renewal. The earliest
observed expiry is 2026-10-17 at 11:52:12 UTC. This is subscription lifecycle,
separate from browser sessions remaining authorized until revocation. Keep the
existing enabled automation and both triggers; do not recreate them to test.

`scope_rollout.py plan --all-projects` and `apply` supplied the exact-snapshot,
backed-up version-2 browser-access rollout. Its private plan is an applied historical
receipt, not a command to reapply or create another subscription. The persistent
reconciler never creates sessions, revives revocations, changes tokens, writes
messages or creates platform subscriptions. Removed projects retain historical
grants while authoritative workspace resolution still gates access. Inventory read
failures retain existing scope and log a sanitized scan error.

## Delivery and duplicate protection

Stored and signed events retain exact thread/project/issue/workspace/message,
sequence, author, intent, reply scope and message-hash provenance. The installed
signer passed offline serialization/signature verification; no connector field
stripping was found. Whether fresh event data reaches root's automatic task is
still part of the new-message acceptance check.

The installed connector exposes pending recovery plus thread read, reply append
and delivery read. Pending recovery is owner-scoped, read-only, snapshot-paginated
and validates event/message/scope/hash identity. It does not acknowledge, claim,
resend or reply. Root's access to that fourth tool remains missing.

Exact reply fences, request idempotency and the database one-final-reply constraint
remain in force. The retained phone message has exactly one reply; this audit did
not append another. Legacy cursors are normalized to null on the wire without
rewriting durable events or restarting the browser. Replies do not create owner
wake events. Do not infer human viewing from webhook or persistence receipts.

## Activation, backup and readback

Installed runtime source remains `d2c79543ea373680da79944bd98756639d23cc0c` under
`/mnt/vk-storage/vk-dot-sidechat-live/releases/d2c79543e`. Seamus's 17:39 approval
resolved the earlier activation rejection; the one authorized retry succeeded.
Only the connector and publisher restarted during that rollout. Browser API,
frontend, Vibe backend, workspace agents and mobile-owner files/browser were
preserved. This handoff reconciliation made no runtime changes or new activation.

The private pre-scope SQLite backup passed integrity verification and its Desktop B
mirror checksum matched. Activation receipts and current sanitized server readback
are retained under `/mnt/vk-storage/vk-dot-all-projects-20261016`; the independent
root-success readback is `root-success-final-readback.json`. The older discovery
trace is retained separately. No backup, runtime database or private plan is in Git.

For a deliberate rollback, compare current session/policy state, stop future
expansion only if explicitly requested, and change only reviewed scope/grant
additions. Keep current chat history and subscriptions. Do not restore an old
whole SQLite database over new messages or choose an older worker unable to
maintain the approved future-project policy. Browser revocation and subscription
cancellation are separate actions.

## Validation and publication

The unchanged implementation passed full GitHub CI, 49 sidechat cases and 28
existing connector regressions. All six advertised schemas pass standard JSON
Schema validation. Formatting, governance and full-preservation secret scanning
also pass. This reconciliation adds independent read-only checks of live
subscription scope/expiry/coverage, message-thread bindings and the retained root
reply. It does not add a synthetic owner message or claim fresh automatic or
user-visible acceptance. Local full Rust checks remain limited by missing GLib
development dependencies; hosted CI receipts are tracked in the PR.

[PR254](https://github.com/artinflight/vibe-kanban/pull/254) targets `staging`; Vibe
T61 carries the handoff. Eleven original changes remain accounted for, and the
original clean API/UI worktrees and active mobile owner's work remain preserved.
