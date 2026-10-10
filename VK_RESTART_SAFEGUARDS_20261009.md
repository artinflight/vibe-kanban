## October 10: Compressed independent current and content-verified transport delta

The read-only census is 103.87 GB / 490,552 files; JSONL histories account for
74.29 GB. No new data exclusions. The old failed 21.47 GB input set remains
untouched. New compressed acceptance uses a fresh B namespace, never the old
attempt, incident archives, incumbent/fallback or existing verified backups.

Implemented manifest-bound zlib-1 objects with exact decoded hash/size bounds,
independent native readback, hardlinked reuse and crash-safe physical-object
retention checks. Delta capture hashes source contents before reuse and rejects
journal/identity changes; a complete manifest owns all recovery objects with
parent=None. SQLite still uses fresh backup-API images on B. Backup-only indexing
preserves sparse selected paths/metadata as data and cannot authorize deployment;
the original candidate validator is unchanged. Unreadable subtrees fail closed.

A real-B two-generation fixture independently restores changed SQLite rows,
keeps one current, verifies all decoded objects and reuses 1.30 MB of history.
Same 40.97 MB SQLite image: synchronous 12.85 s; asynchronous 2.30/4.02 s, same
SHA and native integrity. Buffered metadata writes avoid tiny SSHFS round trips.
74 focused tests: OK, one opt-in disposable service test skipped. ops:check passed;
format ran Rust successfully, then blocked on missing Prettier; no dependencies
installed or heavy build. Whole-plan acceptance is still pending.

Byte-weighted samples estimate 38.5 GB encoded objects and 35.6 GB archive content.
Cold caps: 48 GiB input + 44 GiB objects + 256 MiB index + 6 GiB floor = 98.25 GiB;
B free 108,119,973,888 bytes. These are bounded estimates, not acceptance proof.
Cold timeout four hours; nightly delta two hours, 12 GiB input / 8 GiB changed
objects / 26.25 GiB reserve. CPU/IO/memory/health safeguards remain. Scheduling is
disabled, production and printer controls unchanged. No owner command requested.
Evidence: scripts/deployment/receipts/nightly-compressed-delta-readiness-20261010.json.
This is not evidence for the ten-minute FIX-READY-through-work-resumed goal.

# Deferred restart safeguards — source only

This stream starts from Staging's published b2180dcf, outside Mission Perform.
No service, route, root payload, grant, existing backup, timer or production data
was changed. Fresh normal-nightly acceptance artifacts are confined to B. The previously denied capacity-updater material is not part of this
branch or its publication. OP's uninstalled updater remains internal.

## October 10: Diagnostic whole-plan run — input-cap blocker, disabled

Exactly one active execution and an empty queue were reconciled before work.
Runtime `2f5847fdc524c41ebfefe7083d77d5bd649be40a` then ran the approved full plan
once under unchanged 25% CPU, nice 19/idle IO, 2 GiB soft/3 GiB hard memory and
7200-second bounds. All 79 SQLite snapshots passed native B full-hash/integrity
(7,754,559,488 bytes), including the prior failing historical file and actual
4,734,447,616-byte DB. The old readonly error remains unreproduced; no snapshot
semantics, source permissions or retries changed.

The attempt failed closed after 7183.77 seconds on the combined 20GiB input cap:
7,823,970,781 sealed bytes left 13,650,865,699 for the archive; its next 1MiB block
exceeded that allowance. The 13,650,362,368-byte unsealed archive and all 84
inputs remain as evidence (21,474,333,149 bytes). This is an input-representation
and throughput blocker, not a shortage of physical B space. Minimum sampled B
free was 108,244,684,800 bytes; 239 health samples returned 200 (maximum 42.7 ms).
Producer/mount closure and both exact leases were verified; no duplicate retry.

Precise failure-only SQLite diagnostics now include operation/extended code/name,
traceback, source/page/journal and registered destination/parent/native attributes.
Busy-image native inspection uses identity-matching metadata-only lstat. Future
archive-bound failures now report exact quantities; a real compressor regression
plus focused suite passed 26 tests. No schedule/deployment/security/production or
printer-control changes. Existing backups/incident/fallback and compressed f95
recovery survive. Full generation manifest/object validation, independent current
recovery and successful whole-plan runtime are NOT established. Do not enable
nightlies or repeat the full capture without first resolving these bounded costs
and preserving/reconciling only this recorded attempt, then rechecking reserve.

Evidence: scripts/deployment/receipts/nightly-diagnostic-whole-plan-capacity-blocker-20261010.json.
Package: /mnt/vk-storage/vk-restart-safeguards-20261009/real-plan-diagnostics-v2;
manifest SHA256 0b79be56006f3e2ec42f6faf11817d9d9de25c57ffe91dca1665a9de8c1f5d7d.
No owner command is requested. The ten-minute FIX-READY-to-work-resumed goal is
separate and remains unproven; this night-preparation attempt does not satisfy it.

## October 10: Bounded blocker diagnostics and lossless capacity recovery

Eight exact registered B captures of the failing 40.97MB historical SQLite file
passed (five with allocation metadata, three without a pre-open native roundtrip).
The original SQLite subcall/traceback/extended code were never captured; retired
original destination mode/Windows attributes remain unknown, not reconstructed.
New fixtures record every call, zero-byte Linux/native identity/mode/attributes,
mount and native full-hash/SQLite seals. Original runtime is unchanged; no blind
retry or speculative fix. See the bounded-blocker diagnostics receipt.

The closed 4.734GB recovery fixture now survives as a 591,731,561-byte lossless
zstd artifact, independently restored/full-hashed/SQLite verified against its
original f95d0c03 SHA. Only the two verified redundant raw fixture copies were
retired; the compressed equivalent and recovery procedure remain. Fixed a new
harness Windows read-only-fsync error using writable atomic receipt staging and
explicit SQLite close; seven small tests pass. B free129,719,201,792 exceeds the
unchanged initial reserve126,969,970,688 (2,749,231,104 bytes margin). Capacity
blocker closed; full-plan SQLite failure and complete whole-plan acceptance remain
open. No whole-plan rerun, schedule, production/root/security change. Existing
backups/incident/fallback survive. See scripts/deployment/receipts/nightly-bounded-blocker-diagnostics-20261010.json.

## October 10: Actual whole-plan acceptance — blocked, schedule disabled

Pinned runtime f85fe01684e1927fa054e8b7bb673d9d6d7b7ae5 was exercised against the
actual 77-root plan on B, under a disposable 25% CPU user scope, nice19/idle IO.
Fresh census: 488,978 files, 100,586,028,252 logical bytes, 79 SQLite databases.
The 4,734,447,616-byte DB passed online backup, independent native B hash/integrity
and an independent B-only restore/full-hash/integrity check. The whole attempt
stopped after 3471.05 seconds, with 37 DBs verified, on a historical SQLite file:
`attempt to write a readonly database`. The same file subsequently passed both
bounded in-memory and fresh B-destination diagnostics; root cause is unresolved.
Do not claim complete manifest/object verification, current publication, successful
whole-plan runtime or nightly readiness. No speculative source fix was made.

The reviewed source recovered the exact 40 recorded test inputs after producer
closure, returning first_capture_retry_ready in 58.02 seconds. Attempt metadata
and the independent 4.734GB recovery copy remain retained. B now has
125,904,814,080 bytes free versus the unchanged 126,969,970,688-byte first-run
reserve (1,065,156,608-byte deficit). Do not weaken that check or start another
large capture without rechecking capacity. Existing backups/incident/fallback,
production data/service, privileges and scheduling remain unchanged.

Package: /mnt/vk-storage/vk-restart-safeguards-20261009/real-plan-f85fe0168;
manifest SHA256 70facd475f317bab694bf8bbc307ff7814176b5fb4783ca9c389fc965f311bd0.
Safe evidence: scripts/deployment/receipts/nightly-real-plan-partial-acceptance-20261010.json.
Next: obtain exact phase/extended SQLite error if failure recurs, satisfy reserve,
then accept complete current/readback/recovery and measured whole-plan runtime
before the exact reviewed user-cron adoption action. No owner command is requested.

## Actual successful route and timing boundary

Read-only inspection of Staging's cutover.safe.json and live-acceptance.safe.json
confirms cutover at 2026-10-09T20:31:20Z in 9.937453607097268 seconds. Runtime
unit is vibe-kanban-current-state-production-20261009.service, observed active
with PID1254186. Backend source c3c48e6324f778ccd03a5761c2314b440e9ceac3 has SHA256
2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f;
frontend source is 5ce84ee21be814b1519cfb2715b50f3432c3e8ba. These are dated
observations, not hardcoded future targets or deployment authorization.

The route reused authoritative current roots, preserving incumbent, full B
baseline, isolated recovery tree and historical archive. The final consistent
92,372,992-byte primary DB snapshot is a DB preimage, not a new whole-state backup.
Old incumbent cannot parse the v2 capacity ledger. Compatible cutback SHA256
c6ebdd425e097f886cca8ae7781ddecb8b96cd96fde4e8c0f70362a5612faa91 must use latest
current data; never restore the earlier snapshot over new writes. Cleanup remains
disabled and human phone/PWA QA and historical recovery exceptions remain open.

TEN MINUTES means FIX READY through build, validation, deployment and blocked
production work resuming. The 9.94-second handoff proves no whole-pipeline SLA.
Nightly readiness cannot compile a future fix. Routine restart and disaster
recovery restoration are separate paths.

## Implemented source contracts

`vk_routine_restart.py` measures release build, validation/migrations, B backup,
independent review, held boundary, handover and work resumption. Caller MUST
provide a same-host FIX READY monotonic timestamp, including queued time.
The default total budget is 600 seconds. Preparation and switch are also reported
separately. Failures identify stage/reason and preserve latest data/fallback.
Existing authenticated action approval must bind the exact plan; a manifest
boolean alone is insufficient. Existing source adapters, not manifest commands,
perform actions. No production driver is supplied or silently adopted here.

The unprivileged wait helper reads real SQLite execution lifecycle rows, waits
for the exact preparation execution to complete and rejects new active work.
It never writes status. The existing ownership API remains the final atomic
admission/release gate. This is the successful Staging actor's sequencing lesson.
Compatible frontend-only plans require backend identity/API compatibility and
can use Staging's existing pointer switch. Routine plans reject restoration,
retirement and cleanup. No protected consumer check is needed without retirement.
Exceptional retirement still requires its approved protected coverage, preparation
first and immediate held-boundary continuation; this stream does not weaken it.

`vk_restart_build_benchmark.py` executes fixed offline/locked Cargo release builds
in an existing warm cache and a NEW cold cache. It never clears caches. It binds
clean source HEAD, bounds runtime/logs, places compiler scratch on SSD and preserves
the 8 GiB floor. Test timings are tiny Rust fixtures, not VK release measurements.
Full VK warm/cold and whole-pipeline measurements remain blocked by capacity;
latest test receipt records available bytes and the separate cold-build allowance.
No actual full-release build was started below the reserve or moved to an
unverified/privileged alternative route.

`vk_nightly_generation.py` consumes the existing DirectBProvider's authenticated
complete archive/hash/metadata proof and replays ONLY changed content. Metadata
updates reuse verified objects. Linux metadata and optional proof context remain
manifest data; symlinks are never recreated on the backup filesystem. Unchanged
objects acquire independent B-local hardlinks. The new generation has parent:null
and survives retirement of the previous generation without a missing baseline.

Publication requires full object readback, a separately bound physical-B readback
adapter, durable object/manifest directories and an atomic current pointer.
Capacity includes changed payload plus a 256 MiB index allowance. An interrupted
or rejected capture retains at most one additional generation; subsequent jobs
stop with an actionable reconciliation error rather than accumulate partials.
This intentionally preserves failed evidence; exceptional reconciliation needs
the applicable approval. Approved normal retention removes only explicitly
manifest-listed objects in the exact previous generated directory using pinned
FD-relative operations. Unexpected files, links, identities or evidence block
retention. Incident archives, original recovery evidence and protected fallback
live outside this NEW normal-nightly store and are never enrolled or deleted.

`render_schedule` produces a 02:00 UTC user-service/timer template: a bounded Python
oneshot with `TimeoutStartSec=7200` (two hours) and `TimeoutStopSec=30` (finite
shutdown grace), NoNewPrivileges, no LLM/agent invocation. `RuntimeMaxSec` is
intentionally absent because it does not bound oneshot execution. It writes/enables nothing.
Staging must bind its reviewed current direct-B capture/readback composition,
enroll a fresh nightly-only B directory, verify hardlinks/atomic rename/directory
fsync on the actual supported backing route, and obtain specific schedule and
nightly-only retention adoption authorization. No nightlies are enabled; schedule
and actual test-run receipts are absent. No new owner command is requested.

## Validation and remaining boundaries

The source receipt records focused tests, real subprocess/kernel-lease ordering,
real direct capture/provider/SQLite incremental recovery and a 537,739-path index
above the former 64 MiB limit. Windows B authentication/readback is modeled in the
owned Linux fixtures; these are not installed B acceptance. The production mounted-B job adapter remains absent. Synthetic acceptance below
now validates the existing WSL B drvfs route and independent native Windows
readback; this does not install or bind a production job. Root-level helper acceptance/install was not
attempted; routine non-retirement restart has an existing unprivileged route.

Independent review delegation was blocked by inherited qualification policy:
"Shadow recommendation exceeds inherited child qualification; do this work in
the parent or change the explicit policy". No second agent or execution started,
and model/effort/routing policy was not changed. Root's existing independent
internal review is still needed. Same-account review is advisory, not an
enforceable privilege boundary; this code does not confine all account activity.
Existing LXD administrative membership is a separate privilege boundary and was
never used to bypass sudo. No unrestricted/root executor is introduced.

Ops governance and focused Python/Rust fixtures pass. Rust formatting passed;
repository formatting/check/lint stop at missing Prettier/tsc/eslint. Full Cargo
workspace checks and actual full VK builds were not run: no Rust application
source changes, available SSD capacity below the protected floor. No dependency
installation, cache clearing or unrelated rebuild was performed.

## Running backend code changes: bounded existing capability

Read-only c3 source confirms routing-module protocol 2, 64 KiB input/output,
750 ms deadline, 512 MiB address space and 1 CPU-second budget. Worker runs through
prlimit/bubblewrap with unshared namespaces, read-only module/system files and
no production state or network access. Host retains qualification/safety checks,
native execution and manual/Recommend behavior. The retained matching protocol 2
validator successfully verified the existing reviewed combined worker in its
sandbox during this turn; no module pointer or backend changed.

Supported changes are pure routing/triage executable behavior, compatible model
policy and classifier instructions/settings inside that ABI. Next admissions can
load a verified release; corrupt/incompatible/oversized/slow workers retain safe
fallback. The existing source contains a same-process publication/rollback
integration test. A NEW full end-to-end execution of that Rust test is still
pending a supported build/test-capacity route. This fresh validator check alone
does not prove the complete backend/admission path.

Database migrations, Rust types/state layouts, HTTP/application behavior,
execution lifecycle and arbitrary backend code are outside this capability.
They retain explicit build/deployment/current-data compatibility boundaries.
No general live patching, major rewrite, Auto activation or privileged install
is proposed. Staging owns driver integration and any future adoption; Mission
Perform remains uninterrupted and human QA controls later cleanup.

## Timestamp test review correction

The original849a00024 tests used a local wrapper that supplied FIX READY. Positive
call sites now explicitly pass the intended timestamp to production run(), with
zero used for simulated clocks. A new negative regression verifies the mandatory
production keyword raises TypeError when omitted. Runtime source is unchanged.
The historical23-test receipt covers849a00024 only; use the fresh exact-head SSD
review receipt for the corrected source, never apply the old count to a new head.

### PR235 oneshot timeout review correction

Rendered-settings regressions pin the startup deadline and shutdown grace. The
opt-in `test_vk_nightly_service_timeout` uses only a unique transient user service
with one-second deadlines and a SIGTERM-ignoring sleeper: it verifies Result=timeout,
SIGKILL after the grace, finite elapsed time, and then stops/resets that fixture.
This validates user-manager timeout behavior, not a real B nightly capture or
schedule adoption. No persistent unit/timer, production service, or data changes.
Run with `VK_TEST_USER_SERVICE_TIMEOUT=1` and the focused Python suite; exact-head
command/output is saved in the adjacent mounted-SSD validation receipt.

### Actual B synthetic acceptance

The explicit `rehearse_vk_nightly_real_b.py --execute-synthetic-fixtures` harness
uses the unchanged direct capture, existing authenticated Desktop transport,
default archive reader and DirectBProvider to capture a fresh synthetic SQLite
source twice on actual B. The second capture changes the DB and deletes one
fixture file; unchanged content remains. Authenticated proofs/payloads are handed
to the exact nightly module in an existing WSL process dropped to UID/GID1000.
This small fixture transport is not a production data-stream adapter. Each new
generation is fully rehashed by a separate native Windows process before
publication. The actual WSL B mount is checked as B:\ / 9p, with a pinned native
B device and enrolled root identity. No root writes or persistent grants.

Four independent stores in the fresh test directory exercise the same two
captures. Successful retention removes only the synthetic first generation;
unchanged content retains its inode and the second manifest has no parent.
Native Windows recovers SQLite rows `before, second`, checks integrity, reads
only current-generation objects and confirms the deleted member is absent.
Actual fixture processes terminate at three injected boundaries: before atomic
pointer replacement (exit73; first stays valid), after replacement/root fsync
(exit74; second stays valid), and after one old-object unlink (exit75; second
stays valid). A fresh reader verifies each current; further captures fail closed
on the bounded old/partial overlap. Evidence lists exact remaining names and
instructs preservation/reconciliation, rather than retrying into more partials.
No partial cleanup automation is claimed. These are process-interruption tests,
not proof of NTFS/WSL survival through host power loss.

Receipt: `scripts/deployment/receipts/nightly-real-b-20261009.json`; full evidence
remains on SSD. Runtime source and test hashes bind the exact tested code. The
four cases completed in 21.39 seconds, not a release-pipeline measurement.
B contains 83,986 logical file bytes, 83,936 unique-content bytes and 105,560 bytes
of unique-file allocation reported by FileStandardInfo, excluding directory/MFT
metadata. A separate retained filesystem probe adds 40 logical bytes/32 allocation
bytes. Initial SSD capture fixture allocation was 122,880 bytes; later evidence
files add small metadata overhead. No fixture tree is broadly cleaned up.
An initial standalone rename/hardlink probe showed a transient Linux stat miss
while native Windows saw the file. Later open/stat checks and all store cases
passed; missing-file errors remain fail closed rather than being ignored.

Remaining adoption prerequisites: a reviewed real source plan and protected
exclusions; production capture/readback/lifecycle binding; bounded input capture
chain rebasing/retention so upstream archives do not grow or depend on a removed
baseline; safe interrupted-partial reconciliation; independent review and
specific schedule/retention adoption. The current tests retain their raw capture
archives as evidence, outside the generated nightly retention set. No nightly
is enabled, and no production test-run/schedule receipt exists.

### Bounded capture inputs and resumable nightly lifecycle

`NightlyJob` is a source library for an explicitly adopted NEW sibling jobs/store
scope. Each job reserves capacity for current plus changed generation data,
transient compressed input/B snapshots and metadata. It requests a parentless
independent capture and also checks the registered provider result has no parent.
Raw input archives are therefore not a retained baseline: after independently
verified publication, exact registered inputs are removed. Three consecutive
fixture captures recover current SQLite data after previous generations AND raw
archives disappear. This is incremental generation storage using B hardlinks;
it currently transfers a full capture each run. No network-delta efficiency is
claimed. No persistent journal/signing/root executor is added.

One nonce-bound ledger records old file/directory identities, candidate hashes
and exact transient file registrations. Small mutable progress records directory,
partial and pointer identities; the host-scale immutable inventory is not rewritten
per file. Exact FD-relative cleanup rechecks parent/file identities, hashes and
allowed names. Current generation is independently reverified before old retirement.
Missing previously recorded files permit resumable old-object retirement; arbitrary
paths, substituted files, symlinks, unknown evidence and replayed progress block
with actionable status. Unregistered creation/ledger-loss windows conservatively
preserve artifacts; no blanket cleanup of incomplete folders. Same-account code
and callbacks are cooperative operational controls, not a root security boundary.

The scripted `tick` attests actual completion of the prior producer against its
exact scope/input/candidate nonce before reconciliation. A live producer defers
work, preserving the single unfinished attempt. Known closed-producer failures
can reconcile and run a fresh independent capture without operator commands.
Actual fixture process deaths before publication, after publication and during
old retention preserve current, resume known cleanup and permit the next job.
First-capture failure, 71 snapshot registrations, insufficient reserve, missing
adoption/quiescence, raw parent reuse, unsealed inputs, symlink/hardlink substitution,
path traversal and progress replay have focused regressions. These are isolated
Linux tests; the changed lifecycle has not been rerun on real B or installed.

Read-only production discovery found no VK backup timer and proposed fresh
`B:/vk-backups/vk-normal-nightly-v1` absent. Historical plan digest
4a7abb5628f381d943acb51e2ffc00c250e11bfb0b71b29a1ff78c1df4865b0c
lists 77 source roots and 71 explicit DB paths; stat-only discovery found one
4,734,447,616-byte DB above the 1GiB memory capture limit. Existing B-disk snapshot
extension is required for that host scale. The proposal pins that extension and
existing transport, WSL UID/GID1000, planned new scope and existing user scheduler.
No credentials, payloads, production DB queries or existing generation writes.

Remaining adoption checklist is machine-readable in
`nightly-production-bindings-proposed-20261009.json`: independent exact-head
review; current source-plan/exclusion review; fixed bounded B-disk snapshot and
input-registration/MCP-to-WSL handoff/quiescence bindings; measured whole-state
capacity/time limits; fresh real-B lifecycle/producer/mount-restart recovery tests;
specific adoption/retention authorization; fixed-job test receipt followed by
actual timer verification. Production limits stay unset and adoption disabled
until measured. Rollback disables only the new timer/job, preserving all backup
and evidence. Old incident/fallback roots are outside this fresh scope; human QA
and previous no-cleanup policy remain. No owner command is requested.

### Fixed B-disk capture and user job — adoption still disabled

`vk_nightly_job.py` composes the existing B-disk capture and the reviewed
NightlyJob in an existing UID1000 WSL process. The resident creates and records
each input before the MCP writer can open it. A fresh, exact B input directory
is exposed through the existing unprivileged SSHFS route; SQLite backup API
images, path lists, warning logs, archive, descriptor and proof all stay on B.
SQLite uses small caches and serial disk images, not serialize()/RAM payloads.
Only a completed private image is read immutable for integrity validation; live
sources use ordinary read transactions. Aggregate byte reservations apply before
writes. Snapshot/time bounds fail closed and retain unaccepted registered inputs.

The original DirectBProvider fully verifies the independent parentless capture
on MCP. A compact, bounded proof passes through the authenticated live nonce
channel. B-local archive replay uses authenticated headers, avoiding a duplicate
host-scale location vector. SQLite connections, tar/compressor/readback children
and the foreground mount finish before exact bound completion. The resident
performs independent native Windows full object and private SQLite readback
before publication and recorded retention. MCP and B kernel leases serialize
cooperating producers; this is not a root boundary or a global process fence.
No privileges or source scope are expanded by this composition.

Actual-B synthetic acceptance covers two changed DB generations, unchanged
content/hardlinks, deletions and independent recovery from current alone. Real
process exits cover before/after publication, old-object retention, candidate
objects rmdir and pointer rename before store fsync. Recorded recovery is checked
from a new process; another capture then succeeds. The harness also interrupts
the MCP producer and tests scripted known-partial reconciliation without an
operator. Test artifacts remain in fresh `vk-nightly-lifecycle-*` B scopes;
existing backup, incident, incumbent and fallback evidence is untouched.
These are small fixture/actual-filesystem results, not full-host throughput or
power-loss/WSL-remount acceptance. An OS remount changing enrolled device/inode
bindings still blocks rather than silently rebinding existing backup data.

Read-only current census: 77 roots, 548,540 paths, 487,126 regular files,
96,144,285,466 logical bytes, 79 detected SQLite files totaling 7,451,316,224
bytes; largest SQLite 4,734,447,616 bytes. Census took 164.47 seconds; 14 paths
vanished during this online scan. It is sizing evidence, not a coherent backup.
The runnable proposed bindings preserve the source plan/root/exclusion identities
and pin scripts/binaries. Proposed limits: 6GiB per snapshot, 20GiB aggregate
transient capture, 96GiB initial changed objects, 8GiB routine changed objects,
256MiB metadata and a preserved 2GiB B floor. Initial/routine reservations are
126,969,970,688 / 32,480,690,176 bytes. Snapshot deadline 1800s, native readback
3600s and entire scheduled job 7200s with a 30s final kill grace. These are finite
proposed bounds informed by census; compressed size and complete production
runtime have not been measured with this new composition.

The existing UTC user cron daemon is active; its old VK entry remains disabled.
The proposed new entry is prepared as an artifact only and uses a pinned user
job/config, `/usr/bin/timeout`, and local `/usr/bin/logger`; no LLM calls. Syntax
can be checked with existing `crontab -n` without installing anything. The former
systemd template remains unchanged: its NoNewPrivileges=yes blocks the existing
FUSE helper, verified by a disposable failed mount probe. No security control was
relaxed to make that template work. The ordinary cron route uses the already
available user FUSE capability, not sudo or a new privilege grant.

Remaining exact adoption action: independent review of the final source/config
hashes, authorize enrollment and normal retention ONLY in fresh
`B:/vk-backups/vk-normal-nightly-v1`, run one complete real-plan backup and verify
its recovery/capacity/runtime receipt, then add ONLY the new bounded cron entry
while preserving all existing entries. Enablement is conditional on that test
passing; currently no enrollment/production capture/schedule is authorized or
performed. Rollback removes ONLY the new cron entry and stops its own job if
needed, preserving every backup, receipt and incident/fallback artifact. Initial
whole-plan fit, actual throughput and boot/remount identity acceptance remain
explicit adoption prerequisites. No owner command is requested.

Current-scope special-file probe found exactly one unsupported object: owned
Unix socket /home/mcp/.codex/app-server-daemon/daemon-updater.sock. The package
prepares a separate proposed nightly plan omitting only that transient endpoint;
the historical Staging plan remains untouched. A runtime type/owner guard rejects
regular-file/symlink substitution instead of dropping possible data. This exact
scope omission belongs in the final review/approval. Other future SQLite files
inside already approved canonical roots are automatically captured within the
same bounds; the observed 79-DB list is sizing evidence, not a recurring grant.

### Parent-only death and producer lease

The MCP lease descriptor is explicitly inherited by the fixed foreground SSHFS,
zstd and tar producers. They retain the same locked open-file description;
parent close/SIGKILL cannot release it, and no explicit LOCK_UN is issued. The
next entry point defers before creating a B resident or issuing quiescence
attestation while a holder survives. Normal cleanup/reaping and schedule-disabled
behavior are unchanged. This covers the current pinned binaries, not arbitrary
commands or a global consumer fence. It does not authorize recovery of unknown
legacy producers or create a production process reaper.

The real-B regression freezes the three actual children during active capture,
SIGKILLs ONLY the Python parent and proves retry is blocked. Each child is bound
by UID, PID/start ticks, executable hash and inherited lease device/inode/FD;
the mount additionally has its exact target and Desktop input source. Test-only
cleanup signals/unmounts only those matching isolated resources. After their
closure the scripted retry reconciles its registered partial and publishes a
verified independent current. No production resources or permission change.
A surviving orphan is an explicit exceptional deferral, not claimed automatic
production cleanup; routine successful jobs require no operator.
