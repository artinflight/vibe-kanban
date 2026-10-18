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

Smallest later activation requirements: reviewed fresh authoritative physical/
remaining-allocation producer and its bounded update procedure; Staging's combined
forward/rollback and native resource/preservation/queue/approval acceptance;
exact saved owner/config/freshness binding through reviewed existing ingress;
then separately explicit release, monitor tuning/access/timer/automatic-response
approval. Keep existing phone alerts, saved model/effort/Recommend, cleanup
ownership and genuine approval boundaries intact. Source/paired isolated CI
acceptance cannot approve these runtime steps.
