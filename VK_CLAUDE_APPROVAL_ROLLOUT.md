# T68 Claude/Codex approval rollout preparation

This extends existing draft PR281 on `vk/695f-vk-direct-launch`, issue T68
`0eb31691-b6e1-406a-a2b9-a4b9bf5ca1f2`, workspace
`695fabe4-fc8b-43f0-9267-a70efd487173`. The user explicitly authorized the routing
source correction and compatible rollout preparation. No backend/notifier
cutover, merge, live MP experiment or global permission edit is performed here.

## Compatibility contract

Read [the policy matrix and diagnosis](VK_CLAUDE_APPROVAL_ROUTING.md).
Claude uses pinned 2.1.62 supported native rules, modes and stdio callbacks;
Codex retains its own native reviewer, sandbox, protocol alias and human fallback.
The goal is equivalent treatment of authorized work and preserved real denials,
not an invented Claude risk classifier. No model, effort, owner, native history,
Recommend-only policy, allowlist, capacity/collision threshold or billing changes.

No new executor field, generated schema, API endpoint or permission migration
is required for this approval delta. Existing profiles deserialize unchanged.
Legacy bypass fields are constrained at execution, not rewritten in storage.
Custom conflicting permission flags fail before process creation; never silently
switch that custom preset to DEFAULT. Initial/follow-up use the same mode argv,
and continuation retains the exact native session ID/history.

Notifications use the existing optional approval context plus an additive
bounded `action` payload. Install preview helpers before engines/readers import
them. Old records remain unavailable; do not rewrite/replay requests, events,
subscriptions or outcomes. New reader with old backend works but lacks native
command detail. New backend with old reader preserves approval semantics but
cannot prove notification detail. Human-visible delivery requires all components.

## Exact source validation

The final source-bound receipts and workflow links are recorded in draft PR281
and the private package manifest. Check their exact source SHA before use. Earlier
CI evidence in the diagnosis guide is historical and does not validate this delta.
Local native fixtures use the installed pinned CLI, an empty dedicated HOME,
synthetic key and loopback mock Messages API. They make no paid/provider request
and exercise actual native rules and resume history, independently of Rust unit
fixtures. This is native compatibility evidence, not live connector acceptance.

Use the existing hosted `dot-steering-acceptance.yml` and Test workflows for
Claude profile/callback/bridge, Codex native-review and broad regressions. The
existing `native-review-compatibility.yml` builds a source/tree/hash-bound server
and executor-test artifact and checks actual isolated startup. Reuse that build;
do not start another compiler or cold local Cargo build on this near-full SSD.
The exported server embeds a placeholder frontend and requires the current
verified external frontend; never replace live assets with the placeholder.

## Current live baseline (read-only October 26)

- Backend `vibe-kanban-native-review-20261015.service`: PID615441, started
  October25 18:20:40UTC, unchanged. Sanitized receipt source
  `efe719151f6db9f6c7197e3a0f72a24a0a8451da`, server SHA256
  `6f0230111142d6a002c1108e69ddc3e871951d1ef2f21f472619cc9fb75731c7`,
  76,861,552 bytes. Freshly reverify executable hash before accepting rollback.
- Connector PID2629290, started October26 15:05:35UTC. Existing approved
  adapter/launcher hashes stay as recorded in the launcher guide.
- Notifier PID7415, started October23 21:53:04UTC. Both event engines still
  match `540eeadc46f1670301d28e70a79e4d7cbdbf7443929742b18ada250138947e23`;
  reader matches `b0ef05682f34e20259da38930465999467d99711ecc1aa838860cf3949e3d1f9`.

The live private source commit is absent from this checkout and its build
namespace source directory is empty after completion. This branch is not proven
to include every private/live integration at that source. A hosted artifact is an isolated acceptance candidate, not permission to
replace the current backend wholesale. Release owner must reconcile the precise
source delta and retained private integrations against the current combined
candidate, then rerun exact integrated-head checks. Approval-only delta adds no
migration; the entire PR includes an earlier handoff migration. Do not assume
that migration exists live or downgrade data for a binary rollback.

## Prepared files and rollback

`prepare_approval_notifications.py` stages five mode-0600 modules plus three
hash-verified rollback copies and source/tree manifest in a new separate
SSD-backed output directory. It refuses dirty relevant source, a changed live
baseline, existing output or output under either live component. No installation,
service call, credential, global setting or database edit occurs. The manifest
explicitly remains `cutover_ready: false` until a compatible backend and the
following acceptance receipts are bound. Packaging command:

```sh
python3 -B scripts/dot-connector/prepare_approval_notifications.py \
  --connector-source /home/mcp/code/vibe-dot-connector \
  --notifier-source /mnt/vk-storage/vk-approval-notifier/app \
  --output "$NEW_TASK_SSD_DIRECTORY"
```

Rollback after an authorized cutover restores only verified previous component
code/modes and the release owner's compatible backend/frontend pairing at a fresh
safe idle boundary. Preserve current DBs, approval/event ledgers, native sessions,
worktrees and credentials. Never restore a pre-cutover data snapshot over later
writes. If the old backend cannot read current data, stop admission through the
existing owner-controlled procedure and forward-fix/rebuild a compatible rollback;
do not improvise a schema downgrade. Unused new preview helper files can remain;
removing them is unnecessary for rollback. Restoring old routing reintroduces
blanket Claude prompts and must be reported as a rollback limitation.

## Release-owner activation and live verification

1. Bind reviewed integrated source, all test runs, artifact hashes, current-data
   backup/restore evidence, existing private-reader compatibility and paired
   rollback. Recheck exact running units, active/queued work, approvals, writers,
   native owners/leases and resource admission. Never stop agents to manufacture
   idle or bypass the seven-lane/user-reserve and collision guards. Unknown
   quota/capacity remains unknown; it never permits purchases or added workers.
2. Rehearse startup and rollback in the supported isolated boundary. Preserve
   current runtime homes, native permissions, frontend routing, accounts and
   history contracts. Require explicit release-owner cutover authorization under
   `VK_BACKEND_RESTART_PROTOCOL.md`; preparation is not restart approval.
3. At an admitted idle checkpoint, activate only the approved backend and paired
   connector/notifier modules through their existing owners. Read back exact
   file/binary hashes, PIDs, health, no duplicate watchers/deliveries and current
   API schema. No broad global grants or permission-service disablement.
4. Use a bounded disposable workspace/session with explicit provider/model/effort
   and owner. Establish a private marker in the first turn; continue the same
   native session without restating it. Confirm exact context/selection/owner,
   one coding job per requested turn, and no generated hidden retry. Test a
   routine authorized read and a scoped native allow. Equivalent Codex fixture
   must retain native-review evidence and effective sandbox/reviewer, not merely
   a successful in-sandbox command. Set an explicit turn/time/cost ceiling before
   any paid acceptance; previous two-turn authorization was already consumed.
5. Force a harmless synthetic genuine ask and explicit deny in disposable policy
   only. Before owner action, the ask remains pending and the tool has not run;
   Dot must deliver the complete safe command/path and exact session/execution/
   approval IDs. Reject with its exact owner/principal binding; confirm no side
   effect and no persisted grant. Test timeout separately with no owner reply;
   request disappearance is not approval. Verify notification retries dedupe.
6. Verify Plan/read-only and Auto native behavior, including explicit deny/ask
   rules overriding allows. Record human-visible notification receipt separately
   from webhook ACK/listing. Only after disposable acceptance and the MP owner's
   natural idle boundary observe its next authorized routine work; never create
   an unbudgeted production probe or answer another owner's approval.

The final live receipt must state exact issue/workspace/session/execution/native
IDs, selected model/effort/policy, source/artifact/runtime hashes, request outcomes,
side effects, job counts and remaining unsupported custom/router capabilities.
Successful model-free tests do not close these deployment acceptance gates.
