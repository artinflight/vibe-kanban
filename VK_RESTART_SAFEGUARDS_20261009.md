# Deferred restart safeguards — source only

This stream starts from Staging's published b2180dcf, outside Mission Perform.
No service, route, root payload, grant, backup payload, timer or production data
was changed. The previously denied capacity-updater material is not part of this
branch or its publication. OP's uninstalled updater remains internal.

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
owned Linux fixtures; these are not installed B acceptance. The actual mounted-B
adapter is absent in this execution. Filesystem compatibility is therefore a real
adoption blocker, not an assumption. Root-level helper acceptance/install was not
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
