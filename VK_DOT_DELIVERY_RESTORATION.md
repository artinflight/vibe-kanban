# Dot delivery restoration — 3 November 2026

## Cause and separation

The existing VK Dev event subscription was still marked active but its finite
lease had expired on 17 October. The separate all-projects-excluding-VK-Dev
subscription remained valid until 4 November. This was a partial registration
failure, not a loss of browser pairing or all-project authorization. Eight retained
events were waiting for a usable binding.

`Events.subscribe` permits one minute to seven days, defaults to one day, and
previously returned the actual expiry as `refreshBefore`. There is no local
renewal scheduler. Retained state proves the VK Dev lease was not successfully
renewed; it does not establish why the platform failed to renew that trigger.
No unsupported platform renewal API is assumed.

The installed T66 workspace-creation workflow also called `delivery_binding`
inside its required local chat-scope step, before native agent launch. Consequently
an expired notification lease blocked an otherwise authorized launch. The repair
retains project authorization, issue assignment, verified current issue/workspace
links, private local conversation scope, native chat acknowledgement and atomic
launch receipts. Optional notification setup and dispatch-note observation run
separately after the native operation. Their failure cannot erase or reinterpret
an accepted execution receipt. Other prompt paths have no `delivery_binding` gate.

## Live repair and acceptance

Both original subscriptions were renewed using the normal signed callback
challenge flow. Both callbacks returned HTTP 200 verification. Subscription IDs,
owner, distinct existing destinations and secrets, disjoint project filters,
all-project policy and access grants were retained. No permanent subscription,
new credential, workspace or replacement request was introduced. Both finite
leases now expire **10 November 2026 at 10:00:51 UTC**.

The existing publisher accepted all eight retained events with their original
identities: its accepted count moved from 51 to 59, with no pending events left.
These are actual retained messages, not synthetic validation notes. HTTP acceptance
proves callback receipt; it does not prove owner reading or a natural root reply.
All 1,300 pre-existing message rows remained byte-for-byte unchanged.

The previously reserved, authorized original investigation request was submitted
through the registered MCP tool with its unchanged request identity and arguments.
It retained its original issue, workspace and session. The native receipt identified
the initial setup execution; readback then showed that setup completed and exactly
one downstream coding-agent execution was running. No validation agent was launched
and no replacement request was used. Subsequent checks were read-only.

Only the connector was reloaded for the two scoped source adoptions (HTTP readiness
0.71 seconds and 0.48 seconds). Vibe, browser, publisher, frontend gateway/notifier
and existing agent service identities remained unchanged. CU, Stop, authentication,
permissions, queues, saved model/effort and Recommend routing were preserved.

## Renewal prevention and remaining dependency

Finite authority remains the deployed policy. `refreshBefore` now precedes actual
expiry by the smaller of one hour or one fifth of the lease. A normal seven-day
renewal therefore asks the platform to refresh by 09:00:51 UTC on 10 November.
The initial restoration happened before this response fix; it returned the old
exact-expiry deadline. The platform must use the advance deadline on subsequent
renewals and maintain **both** existing automation triggers. A local status read
does not renew either subscription.

The already-discoverable `get_workspace_reconciliation_status` now adds
`sidechat.delivery_registration` for an available, owner-authorized conversation.
It reports observed time, registration status/expiry, renewal due, and explicitly
`agent_prompt_dependency: false` and `delivery: not_confirmed`. It reads no callback
URL or secret and performs no subscription writes or schema initialization. The
actual cached registered tool returned this field; all original status fields,
holds and `readback_fresh: false` were unchanged.

Platform automation renewal inspection/update is not exposed in this execution's
supported tools. The advance deadline and health signal improve detection and
renewal safety; they cannot guarantee the platform will renew a missed trigger.
An independently prepared no-expiry proposal remains **uninstalled** pending an
explicit owner decision about persistent destination access. No daemon, timer or
invented subscription route was added. Failure to renew can no longer block the
authorized agent launch path.

## Source and adoption contract

The runtime retains newer private adapter and backend bindings absent from public
staging. This PR publishes a narrow runtime overlay and its testable source;
merging it is not an instruction to replace a complete live package from staging.

- `scripts/dot-connector/templates/issue_workflow.py` is the exact deployed T66
  replacement, originally prepared in `81f25eb9a52141d00d141e9800b576d158a9a709`.
  SHA256: `b53fb4fb9f919a4799c16017c7fc9fd3c703e1850fbf7e66b7b9fa56535e9a4e`.
- `patches/notification-independence.patch` records the minimal delta.
  `prepare_notification_recovery.py` requires the exact prior module hash,
  checks the replacement hash and AST preservation outside the reviewed methods
  and exact tool-description clarification, and writes a fresh candidate only.
  It does not install or reload. The existing native issue-workflow backend remains
  a runtime dependency; this overlay neither adds nor rebuilds that backend.
- `scripts/dot-sidechat/events.py` changes only the refresh response deadline.
  Deployed SHA256: `59464fa0b4288344fc3ea0478a09c59a53f229e450530d2b3846c398332659ef`.
- `delivery_health.py` SHA256:
  `2a942ba3bfe57d3ed3d7aa91a3125a393b261def6cb327ec47e28eb7bc500039`.
  `prepare_delivery_recovery.py` patches the existing private connector's single
  status hook against a supplied exact baseline hash; it preserves all other AST
  nodes. Deployed composed connector SHA256:
  `45daf67430f65687d8b97a6babee6f3edf5df55e5dbbf8bd22f278f887e6cd24`.

Fresh preparations must reconcile current installed hashes, preserve the complete
shared sidechat package and use the established guarded connector-only cutover.
Do not overwrite the adapter or replace current SQLite with an old snapshot.
Before/after code, consistent SQLite and private acceptance receipts are retained
on the mounted SSD and verified by Desktop B upload, download and isolated restore.
Callback addresses/secrets, prompts, message IDs and runtime receipt IDs are omitted
from public source and this report.

## Validation and limits

The published overlay passes 24 mocked native protocol tests: unavailable, expired
and ambiguous notification setup, note errors, denied scope, changed identity,
reservation/launch response loss, same-ID retries, zero launch before verified
local chat scope, and native execution receipt preservation. Three new health tests
cover read-only operation, owner isolation, ambiguity, expiry, missing registration
storage and renewal deadline/TTL bounds. The exact prepared module equals the live
module hash. No mocked test makes an agent launch.

The original complete T66 fixture suites passed 67 connector and 92 sidechat tests
before this public overlay was isolated; those larger private-baseline suites are
not represented as reproducible public-staging tests. `ops:check` and whitespace
checks pass. Required `pnpm run format` reaches Rust formatting but frontend
formatting is unavailable because Prettier/dependencies are absent. Full frontend
check/lint, Rust workspace tests and private deployment CI were not run for this
Python-only overlay. No frontend/backend build, phone UI testing or main-dot
natural-reply acceptance is claimed. Hosted PR checks are reported separately.

## GitHub integration

[PR #289](https://github.com/artinflight/vibe-kanban/pull/289) targets staging.
At head `f9211b5e61851c3aa24411179f37b094cadb33c4`, hosted connector/deployed-source
contracts (including the 24 new mocks), sidechat contracts, branch policy/freshness
and ops governance pass. Remaining Test jobs were still running at handoff.
The recovery workflow's later `Published source inventories` step fails because
its October 29 catalog expects earlier hashes for seven frontend files. Every one
of those files is byte-identical to the fetched staging base `d90e34746` and is
unchanged by this repair. The first mismatch is `WorkspacesSidebar.tsx`:
expected `69efec5b20ca312056319c6c9139d3b988d7b1fe2dbdc2ee2bc438945a031179`,
actual `fde2d0df022fb9275753103c5be810b19add9c4393f9ae618d3fd52937175acb`.
[Recovery run](https://github.com/artinflight/vibe-kanban/actions/runs/41619728207)
records the successful test steps and that baseline inventory failure. The other
six mismatches are the kanban/workspace sidebar/container changes from newer
frontend work. Historical custody hashes were not rewritten to make CI green;
their release owner must reconcile preservation of the original catalog sources.
The PR's latest exact-head checks remain authoritative. No merge is claimed.
