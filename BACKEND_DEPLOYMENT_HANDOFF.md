# Reproducing and managing the recovered Vibe deployment

Checked October 30, 2026. The repaired October 29 new release is serving the public
site. Source reconciliation does not constitute a new deployment. Read
[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json) for exact hashes, paths, selected
environment, fallback identity and unresolved items; verify them before acting.

## Serving components and data

Public `https://vibe.local` → gateway 4720. The gateway serves the current paired
frontend (`index-BBpTkgZU.js`, `index-CUBB2mA2.css`) and routes API through retained
history proxy 5640 → backend 5621, service `vibe-kanban-native-review-20261015.service`.
Backend/history-proxy root pages still serve legacy assets (`index-Djfpggqs.js`);
they are not public frontend acceptance endpoints. Preserve gateway routing.

The live backend source is `ddaaf64a5870124842c385e490a0b40e1174db86`; binary SHA256
`a63eb3a68173d90b894bd933b6676d989ec8325d7ba31135ea52b214bd06c336`.
The 0.1.42 label is shared with the fallback and cannot identify the build.
At last check PID 2100850/invocation `b2a146863e794d86acb393f19decc4c9` was unchanged
from promotion. These are observations, never authority for a future stop/kill.

The existing green DB path resolves to
`/mnt/vk-storage/vk-original-access-recovery-20261025T1748/working90.sqlite`.
It contains 99 applied migrations. Preserve its latest writes, SQLite sidecars,
native Codex home, original rollout paths, attachments, review/attention state,
queues and settings. Preserve `vk-chat-history-readonly-20261010.service` and the
reader/proxy dependencies. Never launch a second writer against this database.
Blue remains retired. Status-triggered cleanup is currently disabled by live
configuration; do not re-enable it based on old documentation.

## Source and incident custody

The clean reconciliation branch starts at fork/staging`2bf2676d2d3841c252fa7f2a9b4e7993128bb093`.
`fork` is artinflight/vibe-kanban; `origin` is upstream BloopAI here. Resolve the
remote URL before syncing. The canonical checkout contains unrelated dirty work
and was preserved. Reference main/staging checkouts were refreshed separately.

- `scripts/deployment/releases/20261029-source.json`:134 deployed source changes,
  generated types/schema included from the actual generation output. Each has
  deployed/public hashes. Ordinary-send repair was carried as exact commits.
- Public `additional-reviewed-requests.json` is empty. The private deployment has
  sixteen exact retained-history bindings, and its test asserts that cardinality.
  That private input and test-only assertion are the two semantic/test source
  differences; one frontend file also has formatting-only Prettier reflow. Do not replace the retained reader with an ordinary public build.
  Recover the exact input from the retained private source or verified B package,
  compare its catalog hash, and repeat all protected-history acceptance.
- `scripts/deployment/`: recovered queue/writer/ingress fences, history acceptance,
  proven orphan reconciliation, SQL/native-B update/reuse/tracking helpers,
  independent no-progress supervision and bounded recovery-control records.
  Some adapters still require the exact retained host/Nightly profile; imports
  are inert. They are not a generic one-command installer.
- `scripts/deployment/incidents/20261029/`:27 inert source templates covering
  recovery, stale-child repair,409 cutback, latest-data roundtrip, bounded build,
  native fenced backup, promotion, CU fence, verification and B mirroring.
  Old PIDs/leases/manifests are consumed. Do not execute an archived controller.
- `scripts/dot-connector/deployed-20261029/`:50 hash-bound source/test files for
  deployed adapter and paired sidechat. One private usage-workspace binding is
  omitted. Existing authenticated tunnel, approval-event bridge, Node24, MCP
  binary, subscriptions and receipt stores remain separate dependencies.

Verify published bytes without touching production:

```sh
python3 -B scripts/deployment/source_custody.py --root . --catalog scripts/deployment/releases/20261029-source.json
python3 -B scripts/deployment/source_custody.py --root scripts/deployment/incidents/20261029 --catalog scripts/deployment/incidents/20261029/sources.json
python3 -B scripts/deployment/source_custody.py --root scripts/dot-connector/deployed-20261029 --catalog scripts/dot-connector/deployed-20261029/sources.json
```

Private token maps are retained under
`/mnt/vk-storage/vk-deployment-reconcile-20261030/{INCIDENT_TEMPLATE_BINDINGS,CONNECTOR_BINDINGS}.private.json`.
`source_custody.py --bindings PRIVATE_MAP` verifies exact original hashes without
writing them. Optional`--output NEW_SSD_DIRECTORY` reconstructs only after every
hash passes, with restrictive modes and inert suffixes. It never executes or
installs. Backend private JSON is a separate exact input, not a token map.
The source and binary provenance is established; byte-identical rebuild of the
new public checkout is not claimed.

## Rebuild procedure

1. Start a clean worktree on mounted SSD from the intended reviewed branch.
   Reconcile current staging before promotion; do not force-reset canonical work.
   Check every intended feature and private runtime dependency against the catalog.
2. Recover exact private history input and preserve generated types from matching
   source. Run type generation when changing schemas; never hand-edit them.
3. Reuse the proven network-isolated build recipe archived as
   `promotion/build-command.json.txt`, with `guest.py.txt`, `build-v3.py.txt` and
   `prepare.py.txt`. Inventory/pin every referenced tool/config/mount before use.
   It used nightly2025-12-04, the existing recovered offline Cargo registry,
   SQLX_OFFLINE, one job, profile `acceptance`, incremental off, and the existing
   shared target under the combined-ag-custody preparation. Do not copy/run its
   stale source paths or live PID guard; prepare a fresh command/manifest.
4. Hold the existing owned-build lock and shared target lease; verify no competing
   compiler, mounted SSD, >3 GiB free SSD and >3 GiB MemAvailable continuously.
   Use a bounded user service: MemoryHigh 4G, MemoryMax 5G, MemorySwapMax 0,
   CPUQuota 100%, Nice 15, TasksMax 160. Build/test with no production DB or account
   material writable inside the sandbox. Do not create another large target.
5. Run scoped native/source tests and required branch CI. Copy the successful
   immutable artifact once, fsync/hash it, record source/tool/config identity.
   Do not deploy mutable shared-target output directly. Match the frontend and
   connector contract; verify public JS/CSS bytes, not only a version label.

The current live service itself has unlimited systemd MemoryHigh/MemoryMax.
Per-executor1500M/3000M and native capacity admission are separate safeguards.
This task did not change that configuration or certify whole-host OOM resilience.

## Fresh cutover and failure recovery

Follow [VK_BACKEND_RESTART_PROTOCOL.md](VK_BACKEND_RESTART_PROTOCOL.md) and the
operator's current authorization. Finish slow preparation online. Immediately
before interruption, prove exact owner identity, drained turns/queues/native
jobs, capacity custody and actual physical writer fencing. Preserve the live
service when any assumption changes. Never infer idle from a stale DB row alone.

The October 29 transaction froze only owned/drained consumers, preserved the
original CU monitor process while freezing it for stable native capture, fenced
ingress, took a current SQLite snapshot plus six native SQLite backups/eight
changed rollouts, and independently reopened the native B store. Source-stability
checks remain mandatory; an earlier unfenced capture was rejected and not reused.
Receipt `native-recovery-fenced/RECEIPT.private.json` is the accepted one.

The 50-minute overall cutoff was removed. Completion-driven plans carry no total
data/operation deadline; a separate supervisor still terminates its owned worker
group after 600 seconds without verified progress and invokes separate recovery
with a 300-second limit. Progress must mean completed work/data, never a heartbeat.
The reusable legacy `final_deadlines` helper still supports older finite plans;
it is not the policy used by the successful October 29 promoter. Tests prove real
stalls terminate, real progress may exceed the idle budget, child failures surface,
and changed CU owners are never thawed. Recovery failure must remain visible;
do not clear its receipt or blindly retry a consumed operation.

Fallback source `d154fe9d83c136acb83012914e1b544898ba4c84`, binary SHA256
`95312f4f3be43cdc109159acc680dc6be73daed0f162e3a220eb5ac6a936cddc`,
paired with the T63 frontend, remains retained in
`/mnt/vk-storage/vk-cutback-ready-20261029/bundle`.
The isolated latest-data new→fallback→new rehearsal preserved all 59 application
tables, migrations, protected replies and a sentinel written after the snapshot.
For future cutback, first recheck schema/data compatibility on a fresh copy and
take a fresh backup. Switch the binary/frontend pair on the current database.
Never replace current data with the pre-cutover snapshot to roll back executable
code. The retained `cutback_preflight.py` is read-only readiness, not authorization
or proof of a fresh writer boundary.

Post-switch, verify exact running executable, public assets/routes, capability
contracts, ordinary send in an isolated fixture, protected/recent native histories,
review flags/settings/queues, consumer resumption and no uncertain-input replay.
Retain failures and original metadata; only proven orphan child runs may become
failed/interrupted. Never invent completed results to remove an active badge.

## Evidence locations and remaining work

Private deployment evidence: `/mnt/vk-storage/vk-new-build-repair-20261029`.
Accepted records include `RESULT.private.json`, `ACCEPTED.private.json`,
`LIVE_VERIFIED.private.json`, `LATEST_PRINT_HISTORIES.private.json`,
`roundtrip/RESULT.private.json`, `CURRENT_BACKUP.private.json`,
`native-recovery-fenced/RECEIPT.private.json`, `RELEASE_B.private.json` and
`TERMINAL_B.private.json`. B objects are under
`desktop:B:/vk-backups/vk-nightly-efficiency-20261026/objects-v1`; use the receipts'
exact object hashes and independent readback, never a directory name as proof.
The170,962,944-byte current DB snapshot hash is
`2dd65fbb75de1c529a68dde08f6de1b2705fdbe4cf15e20237780389d50ecfb5`.
Consult the receipt if this copied reference disagrees; hash the actual object.

Current investigation evidence lives in `/mnt/vk-storage/vk-deployment-reconcile-20261030`.
Antigravity sign-in and supervised model/mode/resume acceptance remain unresolved;
see [its guide](VK_ANTIGRAVITY_ACP.md). Automatic provider failover and external-
effect continuation remain disabled/unqualified. Hosted full-workspace checks,
private release acceptance and staging/main promotion are separate from this
repository sync. Do not infer that every 0.1.42 feature has real paid-provider QA.
