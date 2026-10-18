# Frozen physical-policy paired validation checkpoint

Current client: Operations PR215 `81887d38d238ce3b0665092bf38a482284441062`.
All fifteen published Python source/test hashes match. The disabled published
example config needed by a new test is also mirrored exactly; provenance contains
sixteen hashes. Hosted CI runs the 103 Python tests with accurate pass/skip counts,
then actual mixed OS/physical-SSD Store/Bridge/HTTP/native admission. Current exact
native commit/result will be recorded on PR277 and existing private handoffs;
pending validation is not acceptance. No native implementation, wire, fixture
report ABI or production migration change is required.

The driver supplies `os_percent` plus `ssd_physical_free_proposal_v1` in every
scenario. It asserts the exact policy set in the queued batch, ordinary queue
preservation, strict fresh retry, busy/interrupted continuity, real committed
reply loss/GET-only reconciliation, four first deliveries/one execution and
accepted replay. Native success and original-WAL reopen retain TWO open incidents.
Reports remain initial10/reopened2 named groups; executor I/O, OS inventory and
physical readings are synthetic, not live policy/runtime acceptance.

Predecessor native `b2497288fb7f8fc8d2c6023eb625e6f2c9a354f6` / client
`7a02102d6ccf55f2c91223c5128599cefa6492fc` passed
[Test39148120424](https://github.com/artinflight/vibe-kanban/actions/runs/39148120424):
633 main native passed/15skipped, Python87run/**86passed/1optional connector skipped**,
one actual paired test passed, scheduling15passed/118filtered. The earlier summary
incorrectly called all87 Python tests passed; this corrects it from completed logs.
One main skip was the adapter explicitly run separately;14preexisting ignored
native cases remain unrun. Substantive remote checks and conditional combined-
consent acceptance were skipped. This predecessor is not physical-policy proof.

Physical rollout has NO allocation-producer requirement. It never loads allocation
input; normal remediation still protects owner/shared allocations, resource/budget
and approval boundaries. Physical recovery is no claim future writes fit. Only
2GiB floor is established; proposed2.25/2.5GiB,2/3samples,60s spacing/90s maxgap
need tuning approval. OS unchanged. Optional reserve-aware mode remains separately
disabled without explicit enablement/valid input. Both production transport gates
and SSD tuning gate stay false. No existing journal transition is performed.

Staging's existing20copied-data SQL checks passed; production migration/native
bytes unchanged at b2497288. This repin changes only test snapshot/workflow/docs.
Private candidate and receipt-safe latest-data rollback native acceptance remain
separate and owned by Staging. Do not duplicate or overlay its preparation.
Remaining release/activation requirements: combined native/private-reader/queue/
resource/budget/approval and current-data forward/cutback runtime acceptance;
review existing unauthenticated direct gateway/broad listener boundary (any changed
security boundary needs separate approval); exact saved owner/config/freshness and
minimal state/existing-phone permissions; approved physical tuning and explicit
release/automatic-response/timer enablement. No allocation producer or updater.
Host-heavy/shared-target hold remains; local aggregate format/check/build held,
normal hosted checks supply native evidence. No live migration/binding/access/
service/timer/deployment/dispatch action.

--- Earlier source-bound checkpoints; reserve-aware producer requirements in
historical context do not apply to the selected physical rollout. ---

# Prepared disabled transport validation checkpoint

Current exact Operations PR215 pin: `7a02102d6ccf55f2c91223c5128599cefa6492fc`.
Its fourteen mirrored executable/test files equal `f6b800175d41a22528626f8a6ce708271f015f33`;
the final commit changes only TRANSPORT.md. Hosted CI verifies provenance,
runs 87 Python regressions and exercises the actual Bridge/Store/bounded HTTP
codec against isolated native HTTP/SQLite/queue/default launch/approval code.
Only the test driver remaps its HTTPConnection to the ephemeral listener.
No native wire, fixture ABI, migration or admission behavior changes here.
The new exact native head and hosted result will be recorded on PR277 and in
the existing private handoffs; pending validation is not a pass.

Predecessor native `6c658d1b915b7ec91e7f33ad984236a7846c54b5` / client
`5c2ee7f5f561a943d123fcc09d5ee8098cbeab20` passed
[Test39145016865](https://github.com/artinflight/vibe-kanban/actions/runs/39145016865):
633 main native tests, 76 Python tests, one paired test (10 initial/2 reopen
groups) and 15 scheduling-enabled tests. This result predates Bridge wiring;
it is not acceptance for the changed transport. Earlier checkpoints below
retain their original source boundaries.

The contract now accurately documents the existing access boundary. Direct
no-Origin requests are not application-authenticated; relay checks are
conditional, and the gateway is not loopback-only. No per-UID/client gate is
demonstrated. Client request restrictions and exact owner binding do not supply
server access control. Boundary acceptance remains a separate activation review;
no production endpoint was probed and no access change was made.

Staging already owns source-only additive compatibility and copied-data migration/
receipt-safe rollback preparation. The nominated release remains PR276/366cfd243;
its prior applicability findings below remain scoped to that source. This delta
changes only the test snapshot, additive workflow pin and documentation, leaving
native/migration source unchanged. Do not duplicate preparation or overlay the
release. Combined acceptance, physical-policy tuning approval, exact saved
binding/freshness, permissions and separately approved release/tuning/timer
activation remain outstanding. Both production transport gates stay disabled.
Host Cargo/compiler/linker/aggregate/shared-target hold remains; local aggregate
format/check commands are held and normal hosted checks supply native evidence.

--- Previous exact source checkpoints follow. ---

# Final exact client validation checkpoint

Current client pin: `5c2ee7f5f561a943d123fcc09d5ee8098cbeab20`, Operations PR215.
The six driver dependencies, read-only status helper and five published Python
test modules are byte-exact, with all twelve SHA256 hashes in provenance.json.
Hosted CI now runs those 76 tests, including failed-live-recheck debounce/audit,
before the actual native HTTP/SQLite/queue adapter integration. T90 reports76
Python passes; that report is separate from this checkout's pending hosted run.

The native protocol/fixture is unchanged. The predecessor exact pair
native `59e64543ab12bedf055849b1a4fa9f5d5f518d57` / client
`a345ca8dc1c5f50eab3afdc7db214ff3b923e7fd` passed
[Test39143813217](https://github.com/artinflight/vibe-kanban/actions/runs/39143813217):
633 main tests, one real adapter test (10initial/2reopen assertion groups),
15 scheduling-enabled tests. That result does **not** establish this changed
client's exact-pair acceptance. The fresh run/result will be linked on PR277
and in the existing private T90/Staging handoffs with its exact native commit.
No predecessor result is relabelled as a final-client pass.

## Current release source comparison

The nominated Staging release is [PR276](https://github.com/artinflight/vibe-kanban/pull/276)
source `366cfd243dcf561c399c7ed0d1b6d442d771110b`. Its common source baseline
with this stream is `5b43524ea35b2eb5dd80d0881dc8445489f4442f`.
Read-only temporary-index checks passed for the native crate patch and additive
test workflow against that exact source; no checkout or live bundle changed.
The only shared source paths are `.github/workflows/test.yml` and the four
continuity files `STATE.md`, `STREAM.md`, `HANDOFF.md`, `DELTA.md`. Preserve
PR276's workflow additions and reconcile these notes; this feature changes no
PR276 frontend, connector or sidechat source. This is source applicability,
not a combined compiled-runtime or rollback acceptance claim.

Smallest next reconciliation: Staging incorporates the additive native patch
and test checks into its exact release source while preserving private readers,
Reply/acknowledgement/Stop/reporting and current data. Build/test the combined
candidate under separately coordinated resources, rehearse migrated copied-data
queue/resource/budget/approval and private-route acceptance, and prove forward
and latest-data cutback recognize the same receipt migration/checksum and retain
all receipt/attempt/incident data and execution fences. Never restore older data
or use an old SQLx binary's migration check as rollback proof. This turn changes
no release bundle or live schema, and authorizes no build on the held host.

Pinned snapshot AST/provenance, governance and whitespace checks are lightweight;
all native/aggregate compilation and tests run only on hosted runners. Local
`pnpm run format` invokes Cargo and remains overridden by the no-host-Cargo hold;
normal hosted format checks are required. Model/effort/Recommend, native admission
and genuine approvals are unchanged. Producer authority, exact private binding,
ingress/access, release and timer activation remain separate and unperformed.

--- Prior passing pair and history follow with their exact source boundaries. ---

# Storage admission source validation

Source/tests only. Normal fork staging was reverified as
`5b43524ea35b2eb5dd80d0881dc8445489f4442f`. The
[native contract](VK_STORAGE_ALERT_ADMISSION.md) defines `storage-admission-v2`.
T90 reviewed that unchanged wire contract at native source
`45cffa379d836a553f20bb46d7c96e5953558de0` for adapter source integration.
Operations PR215 publishes the coordinated client/driver at
`a345ca8dc1c5f50eab3afdc7db214ff3b923e7fd`. This is neither release nor
activation acceptance; production Bridge remains disabled.

## Passing hosted native evidence

[Test run39141895388](https://github.com/artinflight/vibe-kanban/actions/runs/39141895388)
at exact continuity-fix source `45cffa379d836a553f20bb46d7c96e5953558de0`
completed successfully. [Native job117717927750](https://github.com/artinflight/vibe-kanban/actions/runs/39141895388/job/117717927750)
reported **633 passed, 14 skipped** in the main no-fail-fast suite and
**15 passed, 118 filtered/skipped** in the scheduling-enabled persistence subset.
The old fail-fast omissions were run, including all **25 new admission cases**:
14 service/SQLite/queue tests, nine actual native HTTP/default-launch tests and
two executor controller/goal-hold tests. The prior broken race assertion and
original-WAL restart test both passed. Native LocalContainer queue wakeup,
uncertain-restoration and user-work preservation regressions passed in both
normal and scheduling-enabled modes. The remaining 14 main-suite skips are
preexisting ignored/environment-dependent tests; they are not a runtime pass.

Backend Clippy/format, schema generation, remote, frontend, Tauri, governance,
branch policy/freshness and preservation/sidechat checks passed in that run.
Combined-capture-consent acceptance was conditionally skipped, not proven.
Hosted evidence uses disposable Ubuntu runners, not the held shared host target.

Covered native admission behavior includes competing same/different batches,
incident deduplication, owner busy versus unrelated owner, memory/durable/
incoming user queues, changed intent/owner/hash, strict fresh deferred attempts,
real capacity and own-goal/budget holds, timeout after committed binding,
in-flight cancellation/late insertion fences, failure before versus after binding,
missing/conflicting/history-loss uncertainty, close/reopen retention, canonical
Unicode fingerprints, configuration drift, real interactive approval wait/denial,
and ordinary user/alert contention. Alert recovery retains ordered failed/killed
user prompts and partial text in the persisted action/coding turn. Accepted
replay keeps the original immutable intent and execution with no second launch.

## Coordinated real adapter integration on this source

The test-only six-file snapshot is byte-exact Operations source
`a345ca8dc1c5f50eab3afdc7db214ff3b923e7fd`, with commit/path/SHA256 provenance.
T90 reports 75 client fixtures passing; that count alone is not native evidence.
The snapshot avoids new cross-repository credentials or runner access.

The new Rust fixture serves the actual registered Axum router over ephemeral
loopback with migrated on-disk SQLite, native QueuedMessageService, default
ContainerService start and real ExecutorApprovalBridge. The exact Python
Store/NativeAdapter submits real POST/GET requests. Its ten initial named
assertion groups cover entire queued-user receipt preservation, definite
queue/busy deferral with zero launch, strictly newer same-intent retry,
interrupted-user recovery, native success without false pressure recovery,
real commit followed by lost response/client reopen/GET, four competing first
POST deliveries and accepted replay with one native execution. The listener,
pool, deployment and memory queue are then replaced using the original WAL
database. Two reopen groups require exact intent/attempt/execution identity,
one GET and zero POST/new launch; Rust additionally checks unchanged execution
row count. These are twelve assertion groups, not twelve full runtime tests.

Normal hosted CI verifies snapshot hashes and explicitly runs the otherwise
ignored integration test, even after a preceding native-suite failure. Missing
inputs cannot silently pass. The main suite remains no-fail-fast. At this
commit's preparation this new paired fixture requires its own hosted run;
latest exact source/CI results are recorded on [PR277](https://github.com/artinflight/vibe-kanban/pull/277)
and in the existing private T90/Staging handoffs. The earlier passing run above
predates this fixture and cannot establish its integration success.

Only executor/process I/O, OS inventory and incident observations are synthetic.
The real producer, deployment ingress and live resource environment are not
certified by these tests. Setup controls compile only under cfg(test), never
product ingress. No live model, owner, credential or allocation feed is used.

## First paired hosted result and correction

[Run39142867234](https://github.com/artinflight/vibe-kanban/actions/runs/39142867234)
at native `18456f017b042f2b20b833ac113694b393f9ff5e` passed the complete main
suite (**633 passed, 15 skipped**, including the explicitly ignored adapter
case). The explicit adapter case then failed before its first HTTP request:
client `42bc9ceb10c978094992cee1d6284f5ea43b9bd9`'s local `http()` function shadowed its imported module,
raising `AttributeError: function object has no attribute client`. This is not
paired integration acceptance. The scheduling-enabled subset after that new
step was skipped in this run; its earlier passing evidence remains separate.

The driver correction is coordinated with T90 and repinned only from their
published source. The ignored-test command now uses the same workspace/feature
selection as the main suite to reuse its compiled test artifacts. Scheduling-
enabled persistence checks also run after earlier failure so a client-test
error cannot hide native queue regressions. Both initial/reopened evidence
records are preserved even when libtest prefixes the first output line with
the test name. None of these changes weaken the actual client assertions.

## Earlier failures and lightweight checks

The original host services command ran14 tests:13passed/1restart fixture failed
SQLite14 opening a VACUUM snapshot. It was replaced with original migrated-WAL
close/reopen, now passing in the hosted run above. af7b35d's hosted test had
474passes/one race-assertion failure/14skips/157unrun after fail-fast. Ordinary
follow-up correctly recovered interrupted alert context; the assertion expected
raw text. Source45cffa379 corrected it without weakening continuity and added
ordinary interrupted-turn recovery to alert launch. No earlier partial run is
represented as a full native or client pass.

Pinned direct rustfmt, Python AST syntax/snapshot provenance, ops governance,
branch policy and whitespace checks pass for the adapter fixture preparation.
The explicit no-host-Cargo instruction overrides local `pnpm run format`, whose
backend formatter invokes Cargo; hosted format checks remain required.
Aggregate typecheck/lint/native builds run on hosted CI only.

## Resource and release boundaries

The original owned host Cargo run exited; no further host Cargo/compiler/linker
or aggregate build is started. All source/shared outputs remain retained. No
cache deletion, file move, allocation reset or service action was used.

The additive receipt migration, native execution fences, owner serialization,
controller/goal checks and API must be reconciled with Staging's evolving Dot
release. They do not replace its bundle. Forward and compatible rollback must
recognize the exact migration/checksum and retain receipts/tombstones/triggers;
an old binary's strict SQLx migration check is not rollback acceptance. No live
migration, private binding installation, owner dispatch, deploy, restart, timer,
credentials or access change occurred.

Smallest later activation requirements (updated for the selected physical mode):
reviewed physical thresholds/counts/gap and exact mount/freshness validation; no
allocation producer is required; Staging's combined
forward/rollback and native resource/preservation/queue/approval acceptance;
exact saved owner/config/freshness binding through reviewed existing ingress;
then separately explicit release, monitor tuning/access/timer/automatic-response
approval. Keep existing phone alerts, saved model/effort/Recommend, cleanup
ownership and genuine approval boundaries intact. Source/paired isolated CI
acceptance cannot approve these runtime steps.
