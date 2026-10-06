# Scheduled native goal first run (development only)

Authoritative CU wire contract: [a495dd05 scheduled-first-run contract](https://github.com/artinflight/codexusage/blob/a495dd05d8eb9d58d3be5ea232bb7fa4c8098fbc/docs/scheduled-first-run-vk-contract.md).

This stream starts at fork staging `8b562265d`. No production restart, deploy,
settings write, Android goal initialization, rejected-prompt retry or paid model
request is authorized. Recommend remains unchanged. Staging owns rollout.

## Provenance

Read-only discovery on October 6, 2026 found routed Green
`vibe-kanban-green-production-20261005.service`, PID `3027197`, binary
`/mnt/vk-storage/vk-green-cutover-20261005/release/server`, SHA-256
`5e7948921f962b9ea74597781ca2e1b0c7bd745edc0d1901a8274dab444097a2`.
The release identity receipt names build source `a661a8156`, staging
`8b562265d`, main `fa8122a50`. `/api/info` reports VK `0.1.42`.
The frontend current link resolves to that release's frontend. Dated historical
STATE/HANDOFF inventories are not current process evidence. There is no local
`.agents` directory; the host `.agents/skills` has only the unrelated power-outage
skill. The retained CU reviewed boundary is used explicitly, not a new fixture
backend with unrestricted access to the host manager.

## Interface and authority

`VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION=1` is a **default-off service rollout
gate**, to be installed only after compatible CU is deployed and combined
acceptance passes. `/api/capacity` advertises numeric
`capabilities.scheduledGoalInitialization` (`0` while disabled, `1` when enabled).

The HTTP protocol and wire `state.version` stay at 1 for CU's existing parser;
this is separate from the version-2 durable disk ledger. All status, mutation
and ownership responses use this wire projection without changing persistence.

Pending candidates and durable managed goals carry `initializationState:
pending`, `goalId`, `threadId`, `objective`, `createdAt`. `createdAt` retains the
existing native wire unit (seconds); goal ID distinguishes replacements even
within a second. The original account home and current native SQLite record
supply the ID when the installed app-server wire omits it. Wire/database
thread/objective/creation must match before filling an omitted ID.

`POST /eligibility` and `POST /start` accept optional `firstRun` with exactly
`{goalId, threadId, objective, createdAt}`. It is mandatory and must match the
current native record for pending enrollment and every pending start, in
addition to the usual epoch/revision and bounded grant. Legacy pending starts
are rejected. Checkpointed starts omit it. Removal omits it and is allowed
regardless of rollout capability or a deleted session, provided no grant needs
stop reconciliation. No enrollment operation loads the native engine, writes
progress, changes paused status or launches any process.

Opaque server bindings retain session, workspace, canonical workspace path,
relative working directory, original account home, database, and the successful
completed-turn execution/turn/message anchor. Discovery, enrollment, dispatch,
lease creation and native activation recheck them. The pending anchor cannot
advance implicitly. Checkpointed dispatch may advance its completed anchor only
with unchanged native goal identity. A removed/archived/running workspace is
unavailable; scheduled admission cannot recreate it. Actual worker directories
must stay within the bound workspace. Pending action revision changes fail
closed, and grant IDs/receipts cannot be replayed.

Missing progress means ENOENT, never a decode error, an empty checklist, a
mismatched identity, a completed goal/checklist, a substantive input hold or a
native budget/blocked state. Only an existing **paused** goal qualifies without
progress. Existing checkpointed usage-limited continuation remains supported.
The scheduled loader does not reset mismatched progress.

Issuance stores an owned receipt before dispatch. An empty bootstrap sidecar is
allowed only after the owning execution is bound and only at its last native
activation check. It is never promotion evidence. The root native tool/message
checkpoint path attests a nonempty validated checklist and its actual turn ID;
only successful completion of that same turn, with matching native identity and
unexpired authority, promotes the ledger. VK never manufactures a checklist to bypass the native root-turn boundary.
Offline validation uses a synthetic provider with the actual native tool/turn
path. A checklist file alone cannot attest success.

Revocation, cutoff, failed/input-held first turns, interruption, and an ambiguous
restart preserve the native goal and sidecar and leave a durable `held` state.
Receipt-bearing pending goals are held on restart even if no provider dispatch
was confirmed. Held identities cannot be laundered by removal/reselection.
New identities require explicit selection. No initialization is blindly replayed.
First-run request and stream retries are set to zero at process startup and
verified from effective native configuration. Provider error/retry notifications
withdraw pending authority; later ordinary grants retain their existing policy.
The existing included-quota/window decision, short leases, two-goal maximum,
foreground priority, workspace concurrency, guard, native permission policy,
account, model/reasoning and Recommend routing restrictions remain authoritative.

## Isolation and validation

`scripts/testing/scheduled-first-run-validation.py` runs compiled tests with
CU's explicitly supplied reviewed `fixture_isolation.py` / fixture supervisor.
Only a new SSD fixture root and its private temporary mount are writable; host
worktrees/Git are read-only, `/run` and live pathname sockets are masked, PID and
network namespaces are private, and arbitrary host manager requests are denied.
The trusted parent can operate only supervisor-registered fixture units. Each
run records source hashes, binary hash, isolation probes, canary hashes, and
results. No fixture production backend is started. Review the supplied boundary
before running the driver; it is an explicit external dependency.

Evidence root: `/mnt/vk-storage/vk-scheduled-first-run-20261006`;
short socket-compatible fixture root: `/mnt/vk-storage/vk-sfr-20261006`.
The SSD initially had approximately 520 MiB free; an initial debug-heavy test
link exhausted it. Only the exact unused output generated by this task was
removed, and test linking now strips debug symbols. Existing worktrees,
attachments, databases and shared cache contents were preserved.

Initial source `27d9562d2` local results: 155 executor unit tests pass (seven opt-in tests skipped);
six real-native offline scenarios pass on the same test binary: successful
initialization/promotion/later resume, input hold, single-request provider
failure, and native identity replacement after lease preparation rejected before
model work; plan mode held before model work; and a completed native turn without
a checklist held without promotion. Each receipt has passed kernel/manager isolation and zero real
workspace mutation attempts. Initial test-binary SHA-256:
`a854d6158f061d8fa60c14f5badfbf6cbe0b99b5f5036eccd16b1c0775f6c787`.
See `acceptance.json` under the evidence root for exact fixture/proof paths.

Focused executor/server all-target Clippy, all four frontend type checks,
frontend lint, `pnpm run format`, `pnpm run ops:check`, and diff whitespace checks
pass. Full `pnpm run check` and `pnpm run lint` stop on missing host GTK/GLib/GIO
libraries. Full workspace tests and generated-type CI checks remain required;
the host SSD cannot safely hold their additional builds. Shared frontend types
are unchanged: private persisted firstRun/revision worker metadata is excluded
from the frontend projection. No generated file was edited manually.

Reproduction (compile separately with the shared Cargo target/incremental off;
use a stripped test link if space is constrained):

```sh
python3 -B scripts/testing/scheduled-first-run-validation.py \
  --boundary-dir /home/mcp/code/worktrees/d750-cu-credit-aware/codexusage/ops \
  --binary /mnt/vk-storage/cargo-target/debug/deps/executors-ea5da41c91a59f7a \
  --guard /mnt/vk-storage/vk-green-cutover-20261005/release/vk-capacity-guard \
  -- --test-threads=1
# Add --native --variant success|input|failure|race|plan|empty before the final --,
# and use scheduled_first_run_runtime --ignored --nocapture as test arguments.
```

The external reviewed boundary hashes are retained in each result receipt.
No private HTTP/CU combined rehearsal or production acceptance is claimed.

## PR147 acceptance repair and artifact delivery

The initial backend-test CI failed in
`routing_triage::tests::simple_language_and_discovered_protected_context_raise_the_floor`
(line 509, Workhorse versus Frontier), not a first-run test. The test required a
positive discovery despite the production 40 ms inspection budget. Semantic
inspection is now asserted independently; deadline exhaustion must retain the
conservative unknown-context fallback. A zero-budget test verifies the boundary.
Production's 40 ms budget, entry/file bounds and Recommend policy are retained.
Final CI is mandatory; the prior local suite does not supersede that failure.

`.github/workflows/scheduled-goal-artifacts.yml` builds the exact PR head on a
hosted Ubuntu 24.04 runner, outside source, with incremental disabled and the
stripped `acceptance` profile. `scripts/build-scheduled-goal-artifacts.py`
fences clean tracked source and records commit/tree, every tracked input hash,
compiler, commands, artifact hashes/sizes and embedded read-only build identity.
It does not launch an HTTP fixture, access native state or run startup cleanup.
The embedded frontend is a placeholder: this is an HTTP acceptance bundle,
not a complete deployment package.

The immutable bundle `scheduled-goal-<sourceCommit>` contains:

- `candidate/server`: full matching HTTP backend; runtime gate remains default-off.
- `rollback/server`: full v2-compatible HTTP reader built with
  `scheduled-goal-initialization-disabled`; even a service flag of `1` cannot
  advertise or admit initialization. No ledger downgrade is performed.
- `candidate/executor-tests`, `rollback/executor-tests`: same-source portable
  test binaries for the existing reviewed driver. The first-run fixture uses
  that driver's approved provider path, not the builder's absolute source path.
- `vk-capacity-guard` and `manifest.json`: matching guard and provenance.

Run both executor binaries through the reviewed boundary. The rollback build
adds a feature-specific regression proving v2 pending/held intent, binding,
root-turn receipt and issued IDs survive reopen/removal, and both explicit and
legacy pending launches are denied with the fixture service flag set to `1`.
Run all eight actual-native first-run cases on the candidate, including
stalled graceful stop after revocation and after last-lease expiry. Then staging must
exercise both real HTTP servers with CU inside the same boundary; unit or build
metadata output is not combined acceptance.

The initial host inventory found 27 MiB free on mounted SSD, 43 GiB on the protected
system disk, 66 GiB in the shared Cargo target, 97 MiB of task fixtures, and
approximately 97 MiB of task-source-associated build outputs. Shared cache and
all worktrees/user data are retained. No bulk build falls back to the root disk.
Desktop B: has approximately 304 GiB free and is the artifact destination:
`desktop:B:/vk-builds/scheduled-first-run-pr147/<sourceCommit>/`.
Three exact task-owned compilation files (90,032,674 bytes total: the old
47,387,656-byte test executable and two obsolete utils archives) were removed
only after checksum-verified Desktop copies and inactive-file checks. Frozen
allowlists and receipts are retained in the evidence root. Other shared cache,
all fixture databases/proofs/logs, worktrees, attachments, application data and
services were retained. Independent host free-space increases later permitted
regular verified artifacts on mounted SSD; current exact paths and source/hash
receipts are in the delivery handoff. No root-disk bulk fallback was used.

Artifact checksums/source must be verified after transfer. The reviewed driver
also supports `--binary-stdin --expected-sha256 <manifest hash>`: sealed memfd
bytes (maximum 256 MiB) mount read-only within the original boundary; host
root/socket/PID/network/supervisor restrictions remain intact. Bubblewrap 0.9's
bind-data temporary is in its private namespace tmpfs. Both server metadata
checks and transport tamper probes pass. However, controller unit fixtures use
`current_exe` as an existing guard path, and memory bind-data resolves to a deleted
inode; those fixtures correctly reject it. Use the original reviewed `--binary`
file transport for executor/native regressions. The failed memory unit attempt
and partial transfers are retained; do not bypass guard checks or open the host
manager to work around it. Staging must verify actual isolated HTTP/CU behavior;
metadata or unit results do not replace it.
Retain latest v2 data on rollback, including post-cutover writes.

## Combined acceptance and release requirements (staging owner)

1. Pin CU stale-card identity-binding fix `95e7aea47e137015daa8efcbb210184ee7ce723c`
   (verified local source; deployed adoption must be confirmed) and this VK commit, the existing
   release-matched guard and complete build/runtime manifests. Keep paid credits
   OFF and Recommend; do not enroll the real Android goal during acceptance.
2. Re-run the reviewed kernel boundary and source-hash receipts. Exercise the
   authenticated capacity routes against a newly seeded isolated synthetic VK
   database and actual native offline worker. A copied host database, open
   manager socket or unrestricted backend is unacceptable.
3. Against that exact VK build, run CU's actual saved-night-window scheduler and
   control handler. Verify selection persists but issues no launch; firstRun
   reaches both eligibility and start; mismatched/stale card identity cannot
   enroll; current included quota is fresh; manual trials/one-time weekly and
   credit phases cannot initialize. Capability loss cancels pending admission.
4. Verify races for all four native fields, session/workspace/relative directory,
   completed anchor and original account home at enrollment, dispatch and worker.
   Verify corrupt/empty/mismatched/held/completed/budget-limited exclusions,
   revocation/cutoff/stale quota, cross-session same-workspace concurrency,
   first-turn failure/input hold, restart before and after ambiguous dispatch,
   removal across restart, authentic nonempty promotion, and later normal resume.
5. Run baseline CI/check/lint/workspace tests and applicable type/schema checks.
   Record exact results and any environment exclusions. A native unit receipt
   alone does not establish private HTTP/CU end-to-end or production acceptance.
6. Deploy CU compatibility **before** installing/enabling the VK first-run gate.
   Fresh preflight and separate rollout approval remain with staging. Confirm
   legacy CU rollback cannot start pending goals. Only then expose pending
   candidates; explicit later user selection remains necessary.

## Rollback requirements

The durable controller ledger upgrades to version 2 on any write. Previous
binaries deny unknown fields/version rather than silently dropping first-run
intent or holds. Do not restore a pre-upgrade ledger or erase receipts to make
an old binary start. The rollback binary must understand version 2 while
withholding scheduled initialization, retain native goal/checkpoint identity,
issued grant IDs, holds, and latest writes, and reject pending legacy launches.

Before rollback: revoke and drain grants through the current owner, confirm all
fixture/production execution containment exits as applicable, retain latest VK,
Codex and controller data, and obtain the usual explicit rollout authorization.
Disable first-run exposure and return CU to its compatible fallback. Test
rollback decoding and removal with version-2 pending and held records. An older
unmodified controller is not a safe unattended rollback target. If a migration
is proposed, review it separately; no destructive downgrade is included here.


## Bounded graceful stop and independent containment

The complete `suspend_capacity` attempt now has one 2-second deadline covering
thread/current-turn mutexes, both RPCs, log I/O and exit-signal delivery. The
client registry lookup is nonblocking. Timeout leaves execution stop/pausing
latches set and cannot replay delayed initialization. Stop logs describe a stop
request rather than claiming a persisted native pause.

HTTP stop revokes permission first, then runs worker stops concurrently using the
same helper as foreground preemption. Each graceful attempt is followed by
independent OS stop (3 seconds) and verification (2 seconds, including cgroup
filesystem reads). Controller acquisition and final reconciliation each have a
500 ms lock deadline. Two workers therefore share the 7-second worker budget;
lock waits bring the designed aggregate to at most 8 seconds within CU's actual
10-second VK fetch budget, with remaining transport/scheduling headroom. This is
an async deadline budget, not a hard realtime guarantee for synchronous durable
filesystem writes or an unscheduled runtime.

Only verified inactive/unloaded and empty worker containment permits same-grant
reconciliation. OS timeout, verification failure or a busy controller leaves
stopping grants intact or returns a stop-unconfirmed error. CU already treats
retained grants as unconfirmed. No permission, lease or hard-stop limit changes.
The independent guard still polls at 100 ms, sends TERM then KILL after 250 ms,
and uses control-group cleanup with TimeoutStopSec=1s, RuntimeMaxSec and the
pre-armed immutable absolute KILL timer.

Focused regressions hold thread, log and exit-signal mutexes through timeout and
assert no late success signal. Native offline variants `stalled-revocation`,
`stalled-two` and `stalled-expiry` use authentic matching goals and outstanding
private provider requests. One/two-worker stop uses the actual HTTP stop helper,
measures aggregate response/reconciliation, verifies unconfirmed grants survive,
and independently observes provider activity and cgroup exit. Expiry retains the
no-explicit-OS-stop proof. Per-worker measurements are in
`home/stalled-stop-measurements-N.json`, provider timelines in
`home/stalled-provider-timeline-N.jsonl`, and aggregate responses in
`home/stop-response.json`. All retain identity, held intent, receipts and issued
IDs, deny replay/promotion, and leave native stored status untouched. Original
successful initialization and later checkpointed resume remain separate checks.

A failed pause RPC can leave native status active after verified worker exit.
Recovery must inspect/reconcile this exact goal and its existing hold/receipt;
active status is neither proof of liveness nor authority for automatic resume.
Do not erase the goal, fabricate paused state, promote an empty checklist or
replay uncertain initialization. Latest-v2 compile-disabled rollback must retain
these records and deny initialization even with the environment flag enabled.

Independent review of staging's retained incident at `22034d9b6` cleared the
observed containment concern: the original worker exited before its lease
deadline. Exact original revoke-write and last provider-request timestamps are
unavailable; synthetic timestamps must never be substituted for them. HTTP
timeout alone is neither a worker-exit receipt nor proof of runaway spending.

Current final-source CI/artifact hashes and measured receipts are in
`/mnt/vk-storage/vk-scheduled-first-run-20261006/stop-response-handoff.md`.
Staging must exercise real CU/HTTP with one/two workers in its isolated fixture,
including unconfirmed verification, exact-goal recovery and latest-v2 rollback.
Compatible CU identity binding must be deployed before exposing pending
candidates. Recommend mode remains required. No production rollout, real Android,
provider spending, live settings or shared-service changes are authorized.
