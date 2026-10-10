## October 10: Failure-only SQLite diagnostics before whole-plan acceptance

Active-session reconciliation found exactly one execution and an empty follow-up
queue; no duplicate producer or continuation was started. SQLite failures now
preserve the original error and exact operation, extended code/name, traceback,
RO source journal/page size, source/destination/parent identities and bounded
native Windows metadata of only the registered live input. No success-path extra
SQLite query, retry, new snapshot semantics, permissions or scope. Three new
regressions verify unchanged success calls, original exception preservation and
secondary metadata failure isolation. Whole-plan acceptance remains required;
schedule/production/printer controls remain untouched. Limits stay unchanged.

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

## October 9: Fixed B-disk nightly composition — source only

The runnable user job binds registered B inputs, serial bounded SQLite disk
snapshots, full verified parentless capture, live producer completion and B-local
NightlyJob publication/recovery. Real-B isolated fixtures cover normal replacement,
protected old/current separation and reviewed interruption windows. Current
read-only scope measures 96.14GB logical/79 SQLite DBs, largest4.734GB. Full real
plan throughput/first adoption remain untested and disabled. Existing UTC user
cron is supported; NoNewPrivileges systemd mount probe fails closed and that
control remains unchanged. See VK_RESTART_SAFEGUARDS_20261009.md. No production
backup, schedule, service, privileged code/settings or fallback mutation.

## October 9: Bounded nightly lifecycle — source only

NightlyJob now records one attempt, rebases each capture with parent=None,
atomically promotes a fully verified independent generation, and removes only
recorded transient inputs/old normal-nightly objects. Scripted tick can reconcile
known closed-producer failures without operator commands. Unknown artifacts,
changed identities or replayed progress preserve data and block another capture.
New actual-process interruption/retry tests are isolated Linux fixtures; earlier
real-B primitive acceptance is historical, not new lifecycle acceptance. No
production backup, timer, service, privilege or evidence mutation.
Production binding proposal/checklist:
scripts/deployment/receipts/nightly-production-bindings-proposed-20261009.json.
Historical plan has 77 roots/71 explicit DBs, one 4.734GB DB: memory-only capture
is unsupported; B-disk snapshot/registration/handoff adapters must be bound and
accepted before adoption. Storage is incremental; transfer currently full.
Full release timing and real job/schedule adoption remain open.

## October 9: Synthetic real-B nightly acceptance

PR235 nightly runtime bcf8f1f951 now passed two-generation synthetic acceptance
on actual B NTFS through existing WSL drvfs, UID/GID1000, with independent native
Windows object/SQLite readback. Hardlinks, atomic pointer replace and directory
fsync succeeded. Actual process exits before/after publication and during exact
fixture retention preserved valid current and blocked further capture with
reconciliation status. Original capture archives/interrupted fixtures retained.
No production inputs, backup roots, incident/fallback evidence, schedules,
installation or privilege settings changed. This is not power-loss proof or
nightly job adoption. Production plan/exclusions, lifecycle binding, input-chain
rebasing/bounded retention and partial reconciliation remain open. See
scripts/deployment/receipts/nightly-real-b-20261009.json and
VK_RESTART_SAFEGUARDS_20261009.md. Full release timing remains unmeasured.

## October 9: PR235 oneshot deadline correction

Rendered nightly service now uses TimeoutStartSec=7200 and TimeoutStopSec=30;
RuntimeMaxSec does not bound oneshot execution. Regression checks pin these
settings. An opt-in disposable user-manager test shortens both deadlines to one
second, verifies timeout/SIGKILL, and stops/resets only its unique transient unit.
No nightly job/timer is installed or enabled. Real B bindings and lifecycle
acceptance remain required. Exact-head validation is recorded separately under
/mnt/vk-storage/vk-restart-safeguards-20261009/oneshot-validation-<HEAD>.safe.json.

## October 9: Review correction — explicit FIX READY test timestamps

PR235 review found timestamp call sites obscured by a test-local wrapper. The
849a00024 wrapper supplied the mandatory argument; remove that ambiguity by
calling production run() directly with explicit timestamps in every positive
case. The sole omitted argument is a negative TypeError regression. Production
signature and runtime source remain unchanged. Historical23-test receipt binds
849a00024 only. Fresh exact-head validation is saved under mounted SSD at
/mnt/vk-storage/vk-restart-safeguards-20261009/review-timestamp-validation-<HEAD>.safe.json.
No deployment, scheduling, root/security change or production cleanup occurred.
Further independent backup/failure-path findings remain pending.

## October 9: Deferred restart safeguards — source only

The successful current-data cutover completed at 20:31:20 UTC in 9.94 seconds;
this does not establish the ten-minute FIX READY/build/validation/work-resumed
pipeline goal. Current service is vibe-kanban-current-state-production-20261009;
backend c3c48e63, authoritative roots retained, incumbent frozen and compatible
latest-data cutback retained. Archive untouched; cleanup and human QA unchanged.

Branch fix/restart-safeguards-20261009 implements bounded routine orchestration,
real lifecycle drain waiting, self-contained incremental normal-nightly B
publication/retention, source-only scripted schedule rendering and cache-preserving
warm/cold build measurement. Read VK_RESTART_SAFEGUARDS_20261009.md and its source
validation receipt. No production driver/timer/root code/security change was
adopted. Physical-B mount/readback/atomic hardlink compatibility, independent
internal review and actual full-VK warm/cold/whole-pipeline timing remain open.
Build capacity is below the preserved 8 GiB floor; do not clear caches/evidence.
The denied capacity updater remains on its separate internal branch, excluded
from this source stream. No new owner command is requested.

Older dated entries below are historical and do not override this observation.

Current October9 restart gate update: Desktop SSH/B works; whole-state online
backup accepted (77roots/76DBs), archive SHA735e2115. Read
VK_RESTART_PROGRESS_20261009.md before older entries. Exact offline application
commit f8fd5032 is bound on B; tools1a3d3064 are locally committed/B-preserved.
Workflow grant and new candidate source/test UID1000 ownership approvals remain
pending. Full restoration/metadata/application and real controller/final writer
fence acceptance are unrun. No deployment/restart/cutover/cleanup has occurred.

# October 9: Authorized safe restart preparation

Read [VK_RESTART_PROGRESS_20261009.md](VK_RESTART_PROGRESS_20261009.md).
Established Desktop SSH/B works independently of Dot. B Linux/storage and a
verified large-DB snapshot are prepared; whole-state capture is in progress.
Workflow publication and non-root source ownership approvals remain pending.
No operational restart/cutover or historical-loss acceptance; earlier offline
Desktop statements below are superseded by actual successful SSH observations.

# October 8: Offline direct-B candidate integration (current isolated branch)

Branch `fix/candidate-direct-b-integration-20261008` extends be704f9c with exact
PR229 tools and fail-closed candidate archive/supervisor/package contracts.
Read [VK_CANDIDATE_DIRECT_B_INTEGRATION_20261008.md](VK_CANDIDATE_DIRECT_B_INTEGRATION_20261008.md).
The prepared combined release and B overlay are preserved. This standalone
baseline checkout is not a new prerequisite merge or a deployable application.
Older entries below describe earlier branch scopes and releases.

# October 8: Candidate generation application tooling (isolated branch)

Branch `fix/candidate-generation-20261008` starts at staging `5a887abf8`.
See [VK_CANDIDATE_GENERATION_20261008.md](VK_CANDIDATE_GENERATION_20261008.md)
for implemented controller/path bindings, dependency accounting, retained tests
and exact adapter/integration/space/authentication limitations. Production,
fallback and historical recovery exceptions are preserved. This standalone patch
does not edit OP's PR229 or replace the existing B-backed 149-file overlay.
Historical stream entries below do not define this branch's intent.

# October 8: Phone frontend deployed

The operator-approved phone redesign/style pass is live at `https://vibe.local`
following rebase merges of PR224 into staging and PR226 into main. Production
frontend source is main `22f09e245`; its entire tree matches clean build source
`bdf6346d3`. Read VK_MOBILE_RELEASE_20261008.md for hashes, backup, activation,
regression coverage and remaining limits. Earlier preparation/no-deploy entries
below are historical.

At 17:41 UTC, an atomic directory/symlink exchange activated
`/mnt/vk-storage/vk-mobile-release-20261008/release/frontend` at the actual runtime
frontend path. The general `frontend-dist/current` pointer also resolves there.
The prior directory and hashed assets remain available. Backend service
`vibe-kanban-green-production-20261005.service`, PID 3027197, binary, database,
route 5511/5512 and execution/routing configuration were preserved. No restart
or inference request was made; Recommend-only and configured model/effort remain
unchanged. Future backend packages must retain this new frontend source/assets.

Candidate and live Chromium acceptance passed at 360/390/412/1440px and 390px dark,
including project/task/workspace navigation, state/Back, conversation reading,
composing, local attachment simulation and keyboard viewport geometry. HTTPS
asset hashes, 12 saved messages, 16 active/27 archived project order, configuration
and backend identity matched. Full implementation/promotion CI, production build,
format/governance checks passed. Physical Android keyboard/browser chrome,
Safari/Firefox and production write/drag/queue/review mutations remain unverified.

Rollback archive SHA256 is verified locally and on Desktop at
`desktop:B:/vk-backups/vk-phone-frontend-20261008/frontend-before.tar.gz`. This
artifact-only rollback preserves current application data; no full mutable-state
backup/restore or backend continuity rehearsal was performed. Evidence and
rollback commands are under `/mnt/vk-storage/vk-mobile-release-20261008`.

# October 8: Phone screen redesign

Branch `vk/eb7d-vk-native-feelin` replaces the initial size-focused mobile pass
with dedicated task-feed, workspace-list and compact conversation layouts.
Status/activity chips, clear titles, a thumb-level New task action and progressive
disclosure replace stacked panels, nested cards and persistent composer toolbars.
Retain history-aware sheets, feed/draft/search state, safe areas and visible
viewport behavior. Desktop and configured execution model/effort stay intact;
model routing stays Recommend-only. No merge or deployment is authorized.
Read VK_MOBILE_UX.md for the current design and validation.
Review: [draft PR #224](https://github.com/artinflight/vibe-kanban/pull/224) into
`staging`. Historical entries below do not define this stream.

The follow-up style pass reduces search/chip visual bulk while preserving 48px
input/control targets. Search icons, lighter surfaces, aligned 24px headings,
softer card borders and tighter row spacing refine the new phone layouts.
Style evidence is in `/mnt/vk-storage/vk-mobile-style-20261008`.

# October 5: AutoSwitch reloadable module

Development branch `feat/autoswitch-reload-module` starts at staging `6af55a461`.
See VK_AUTOSWITCH_RELOAD.md. The next restart candidate must include this backend
hook, a published module and its verified service setting; backend-only adoption
will not activate reloads. VK::Staging owns installation/cutover/live acceptance.
Recommend remains required; no Auto activation is authorized. Full useful router
readiness is due before October 30, 2026 (allowance reduces 20x to 10x).
Remaining dependencies: CI/integration, owner adoption, one genuine complete V2
Recommend acceptance with native/CU/child attribution, practical cheaper-step
corrections and net usage/quality evidence. CU expiring-credit budgeting remains
separate in issue `0aeb028e-2856-40c3-943b-aacf32ec4808`.
Older entries below are historical and do not describe this delivery's scope.

Local development validation passed: 55 routing regressions (one existing opt-in
native test not repeated), the opt-in real-worker reload/admission test, executor
all-target Clippy, formatting/governance and unchanged CU contract/fixture.
The reload test stayed in one PID; code/prompt/model-policy/classifier-settings
updates affected subsequent admissions, manual/Shadow choices and child floors
remained authoritative, failure fallback/rollback preserved the dirty sentinel.
The observed initial before/after helper stages took 33/18 ms in the latest run;
this is local timing, not a production guarantee or savings measurement. No paid
inference was performed. Generic CI/staging integration and owner live acceptance
remain release dependencies until their receipts are recorded.
Prepared initial package: `/mnt/vk-storage/vk-autoswitch-reload-design-20261005/package`;
rendered next-candidate setting: adjacent `candidate-autoswitch.conf`. No service
file was installed. The read-only current-production readiness check correctly
rejected the absent module setting; live backend PID1369037 remains unchanged.

# October 4: AutoSwitch risk and diagnostic-phase correction

Branch `fix/autoswitch-negated-risk` starts from `fork/staging` at `86d1c083a`.
Scope: correct the non-destructive false positive and allow a clearly limited
post-operation diagnostic phase to release an inferred Frontier floor to
Workhorse. Existing manual constraints, protected risks, failure escalation,
qualification registry and CU wire contract remain authoritative.

Development only. No main/staging merge, live configuration change, deployment,
restart, or contact with staging/deployment agents. VK::Staging owns activation.
See VK_AUTOSWITCH_RISK_PHASE.md for bounded replay evidence and limitations.
Older preparation/runtime entries below are historical.

# October 3 Restart Candidate

Prepare current staging AutoSwitch changes together with the live PR138 attention
fix, preserving the current review journal. Keep production usable and measure
the whole preparation. Do not activate the candidate without separate approval.
The source-stream notes below are retained as history.

## October 3: AutoSwitch staging integration

Clean branch `fix/autoswitch-followup-staging` starts at staging `b0f4c10a9`.
It carries the exact AutoSwitch source from `dd41b5de1`, including the October 2
Recommended default/selector behavior, Sol6.1 High default, terminal-independent
runtime identity, and completed-context follow-up repair. Original development
branch `fix/autoswitch-recommended-default` remains preserved. No source conflicts
or routing changes were introduced when extracting this release scope.

The unrelated attention/sidebar changes from open PR138 are deliberately excluded.
They are already in the live frontend; VK::Staging must account for PR138 before
replacing that frontend to avoid losing the live attention fixes. This integration
does not merge or modify that separate PR. It also does not restart services,
change main, or contact/trigger staging or deployment agents.

Existing focused/native evidence is in VK_AUTOSWITCH_FOLLOWUP_CONTEXT.md and
`/mnt/vk-storage/vk-autoswitch-context-20261002`; no inference acceptance is repeated
because the source is byte-identical. Fresh integration checks and PR metadata
are recorded under `/mnt/vk-storage/vk-autoswitch-staging-20261003` and in the PR.
The host lacks Tauri GTK development packages and has under 1 GiB free SSD space;
full workspace/desktop checks therefore rely on the repository CI runners rather
than risking the live host. Local checks cover the changed executor, services and
frontend sources, formatting/governance, and byte-identical CU wire compatibility.

# Workspace Attention Preservation

Branch `fix/workspace-attention-preservation` starts at staging `b0f4c10a9`.
Scope: intentional review clearing and actionable sidebar pagination, with
focused tests and evidence-backed flag recovery. No backend, schema, model,
capacity, restart controller or issue-status changes belong in this stream.
See VK_ATTENTION_PRESERVATION.md. Older stream entries below are historical.

## AutoSwitch release compatibility (2026-10-01)

Scope/savings fixes are merged through PR134 (staging) and PR135 (main).
The live backend is still PID1504649/sourceadfa7c051; the release has not switched.
Release preparation found a rollback reader incompatibility: the old binary
rejects added fields inside `SemanticClass`. Scope relationship now persists on
its extensible parent `SemanticTrace`; native classification and safety logic are
unchanged. The generated API types follow that persisted shape.

Release artifacts and current evidence live at
`/mnt/vk-storage/vk-autoswitch-scope-release-20261001`. Desktop has the verified
checkpoint and delta under `B:/vk-backups/vk-autoswitch-scope-release-20261001/`.
The full checkpoint restored successfully into an isolated directory. These are
online backups, not the final fenced cutover capture. Read-only inventory found
an unexpectedly restarted September14 standby (PID2828009); it had no clients or
children and was returned to its frozen state. The routed server and data remain
unchanged. No candidate production startup or route switch has occurred.
Read the package readiness/status files before any activation; never reuse a
consumed cutover controller. Existing Shadow/manual choices must remain intact.

## AutoSwitch scope and savings correction (2026-10-01)

Current development fixes permanent Frontier inheritance and the false security
promotion of configuration notes. Read [VK_AUTOSWITCH_SCOPE_FIX.md](VK_AUTOSWITCH_SCOPE_FIX.md).
Independent small work can choose Luna after protected work; ambiguous continuation,
protected paths, explicit floors and failure handling remain conservative. Native
recommendation tests cover real TF::Build wording and ordinary UI/documentation
work. This is source-only: no backend restart, deployment or live routing-policy
change. The earlier no-restart workaround below remains the actual live state.
Validation passed: 131 executor tests (six opt-in ignored), generated shared types,
web-core TypeScript, executor Clippy with warnings denied, formatting/governance
and diff checks. CU contract bytes are unchanged. Five native classification calls
used 20,883 input tokens (3,840 cached), 915 output, 4.5–9.3s each; five controls
needed no inference. The real preceding TF::Build request was included in one
replay. These are recommendation checks, not measured accepted-task savings.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/scope-fix`.
Next: adopt the backend changes through the normal release path when worthwhile,
then measure total accepted-task usage; no restart or release was done here.

## AutoSwitch no-restart testing workaround live (2026-10-01)

Operator authorized the temporary no-restart path. Frontend source `8d4b9ead2`
is live on the existing backend at `https://vibe.local`; backend PID1504649 and
binary are unchanged. Only the two chat-setting frontend files differ from the
previous frontend source. All old hashed assets remain available, and the prior
frontend/proof have verified rollback copies on mounted SSD.

Nine genuine one-reply checks refreshed all seven models and the two additional
low-effort pairs in the existing availability file. No retries or background
paid refresh were installed. The current backend's 24-hour rule still applies:
proof expires **2026-10-02 16:10:26 UTC**. Native counters total50,254 input tokens
(11,904 cached) and72 output tokens; these are not allowance charges.

TF::Build's empty follow-up draft is now Shadow/assessed; manual model and effort
remain Sol6.1/xhigh. Actual browser selection/reload checks passed at desktop and
mobile sizes without errors. No new development execution was submitted and no
phone operation occurred. Reload the operator's page to receive the updated UI;
previous explicit browser-local manual overrides remain authoritative.

Read `VK_AUTOSWITCH_SHADOW_FIX.md`. Evidence, deployment manifest, test scripts,
screenshots and rollback are at
`/mnt/vk-storage/vk-model-autoswitch-20260930/no-restart`.
The permanent backend auto-refresh fix remains undeployed. Further Shadow work
can use this temporary window; refresh genuine proof on demand if testing extends
past expiry. Never merely advance timestamps or add unattended paid probes.
A complete new live routed task/child acceptance is still pending operator work.

## TF::Build Shadow continuity repair (2026-10-01)

Branch `fix/autoswitch-shadow-continuity` fixes expired availability renewal and
same-session routing hydration. Read [VK_AUTOSWITCH_SHADOW_FIX.md](VK_AUTOSWITCH_SHADOW_FIX.md).
Catalog renewal is bounded, metadata-only and identity-checked; historical exact
execution proof is retained without changing verification timestamps. Manual
choices, fresh-chat opt-in, policy floors and CU wire format remain authoritative.
This is development only; no live proof/profile/service mutation or deployment.
Validation: 127 executor tests passed (six opt-in ignored); the metadata-only native
refresh passed separately in 0.90s against a private copy of the production proof.
All seven models remained discovered; all exact verification timestamps/efforts
were preserved and the production proof hash stayed unchanged. Seven React selector
regressions, web-core TypeScript, executor Clippy, targeted ESLint, formatting
and ops checks passed.
CU canonical contract remains byte-identical. No billed inference or deployment.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/shadow-fix`.
Normal release adoption and a full live Shadow run remain pending. TF::Build's
later manual state must be explicitly changed back to Shadow; do not silently
reinterpret an existing manual execution as routing consent.

## AutoSwitch V2 staging integration (2026-10-01)

The operator now authorizes the full V2 PR/push/rebase merge into staging.
See [VK_AUTOSWITCH_V2_STAGING.md](VK_AUTOSWITCH_V2_STAGING.md) for base, exact
commit mapping and validation limits. Seven V2 commits are rebased onto
staging198d55a20; V1 is already present. Only continuity documents conflicted;
all source patches and newer staging functionality are preserved. No deployment
or full live Shadow test is included. Earlier development-only scope below is history.

## Native child acceptance and capacity correction (2026-10-01)

The bounded native child test now passes. The prior pgrep count included Node
launcher wrappers and diagnostic command text; it was not a count of active agents.
Linux fallback accounting now counts native app-server chains once. Idle servers
still count conservatively. Default limit eight and systemd accounting are unchanged.

The first admitted trial completed Luna5.6/low but exposed loaded-thread resume
ignoring escalation settings. The safety check blocked the second turn. VK now
applies next-turn settings, waits for native confirmation, and rechecks before
inference. The final test completed Luna5.6/low then Sol6.1/medium on the same child
thread, preserved the tracked dirty sentinel, reused duplicate starts, and retained
parent/child identity. Native rollout turn_context matches both CU v1 bindings.
Escalation failure triggers were injected fixtures; root execution identity is a
harness fixture, with no parent inference. Three actual child turns total this pass.

Validation: 122 executor regressions pass, five opt-in tests ignored in the normal
suite; the opt-in native test separately passes; executor Clippy, format/ops and
canonical CU contract comparison pass. Native usage preserves both latest-request
and cumulative-thread fields. Evidence: `v2-delegation/capacity-fix-20261001/verified`
under `/mnt/vk-storage/vk-model-autoswitch-20260930`.

Next is the first complete live V2 Shadow test on a fresh ordinary chat, handled
separately. No staging, deployment, production cutover or external-agent interaction.
Read [VK_AUTOSWITCH_DELEGATION.md](VK_AUTOSWITCH_DELEGATION.md). Version 0.1.42.

## Semantic fallback continuation (2026-10-01)

Auto/Shadow now adds one bounded gpt-5.6-luna/low/standard classification turn only
for materially uncertain deterministic assessments. Known envelopes, manual/pinned
execution and protected floors skip inference. Closed structured output feeds the
existing qualification/floor/exclusion and consented escalation logic. No tools,
implementation loop, staging/deployment changes or agent coordination.

Native sample: ordinary assignee display -> Luna6/medium; private-project access
-> Astra/high; vague/persistence/intermittent-failure requests -> Sol6.1/medium.
Two deterministic controls incur zero calls. Five final classifier calls measured
3,978–3,986 input tokens, 78–133 output and 4.344–8.664 seconds each. One initial
transport check also ran. Classification attempts/usage persist in decisions and
a separate vk.classification.v1 feed; CU vk.routing.v1 is unchanged.
Read VK_AUTOSWITCH_FULL_ROUTER.md for configuration, bounds and actual evidence.
Validation: 29 focused regressions, executor/services Clippy, generated-type and
web-core TypeScript checks, format and ops pass. Source-only; live V2 Shadow QA
and net-savings measurement remain pending.

## Natural-language triage continuation

V2 now recognizes common presentation outcomes on named UI surfaces and corroborates
them with bounded repository evidence at the existing execution boundary. Structured
triage includes uncertainty, validation availability and inspection counts; missing
context retains Workhorse. No planning model call, registry change, CU contract change
or V1 deployment work. Read VK_AUTOSWITCH_FULL_ROUTER.md for scope and limits.

## V2 resumed after V1 staging integration

Continue on `vk/5a81-autoswitch-cu-recovery`; V1 PR127/deployment is separate and
must remain untouched. Follow-up qualification persistence and lexical assessment
repairs are implemented, plus a read-only policy recommendation command. Details:
[VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md). This is not live
activation or live Shadow evidence. No V1 model acceptance campaign was repeated.

# Automatic assessed router (V2)

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Extends accepted V1 with default task assessment, explicit model/effort/envelope
qualification, configurable pair preference, operator-reported validation and
risk-expansion escalation. See [VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md).
Auto can choose older Luna/low, Luna6/medium and Sol6/medium without Routine labels.
Manual and explicit floors/exclusions remain authoritative; no scheduler or reset.
Experimental pairs remain shadow-only. Matching release deployment and a small
live Shadow sanity check remain pending; no production activation in this stream.

## Accepted V1 history

## October 1: Pre-Cutover Preparation Performance

Branch `fix/vk-precutover-preparation`, based on fork/staging620bd7eb9.
Scope: versioned preparation-only tools, verified static evidence/artifact reuse,
rolling online backup checkpoints, bounded concurrent queue inspection, and
whole-preparation timing. The fenced capture callback now has real private
handover/recovery acceptance and is approved for staging integration. See
VK_PREPARATION_PERFORMANCE.md. No production pause/restart/reroute, application
feature change, or replacement of an existing production controller.
Inherited stream notes below describe other work, not this branch's authority.

## AutoSwitch V1 staging-only release

Branch `release/autoswitch-v1` rebases validated V1 onto staging56792a72c.
See [VK_AUTOSWITCH_V1_STAGING.md](VK_AUTOSWITCH_V1_STAGING.md) for exact commit
mapping, preservation of newer staging behavior and operator deployment notes.
V2 remains untouched on `vk/5a81-autoswitch-cu-recovery` at64e9cb5bd and is
excluded. Only continuity documents conflicted; no source conflicts. The operator
owns all post-merge actions. Do not contact or trigger a deployment/staging agent.

# VK Model AutoSwitch V1

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Scope: opt-in model/effort routing at existing Codex execution boundaries.
[VK_MODEL_AUTOSWITCH.md](VK_MODEL_AUTOSWITCH.md) supersedes the planning-only
catalog and describes policy, implementation and enablement gates.
[VK_CODEX_ROUTING_CONTRACT.md](VK_CODEX_ROUTING_CONTRACT.md) defines usage joins.
All seven required models execute on isolated CLI 0.159.2 using the existing
account. Default host CLI 0.153.4 and production VK remain unchanged.
Manual, shadow and automatic modes preserve per-chat control; automatic routing
requires fresh executable-pair evidence and pauses rather than violating floors.
CU-compatible lifecycle telemetry is implemented. Native executor acceptance
passes at the existing capacity limit; private candidate API acceptance and CU
correlation evidence are tracked in VK_AUTOSWITCH_ROLLOUT.md. The active worktree
was externally deleted; recovered source is outside the managed worktree tree at
`/mnt/vk-storage/vk-model-autoswitch-20260930/source`.
No production restart, deployment, global profile change or autonomous retry.

## Inherited integration context

The following notes describe inherited work, not this branch's task scope.

## September 28 — two concurrent selected capacity goals

Added bounded two-agent admission and per-session stop, retaining shared allocation,
independent native/OS deadlines, same-workspace exclusion and interactive priority.
See [VK_CAPACITY_CONCURRENCY.md](VK_CAPACITY_CONCURRENCY.md) for API semantics,
real two-native-goal acceptance and deployment requirements. Companion CU changes
are required; old clients keep one slot. Production deployment remains operator-owned.

# Capacity Cutover Lock

Current scope: implement authenticated ownership release/acquire with fresh
state reload and paused same-PID fallback for compatible backends. Production
cutover is explicitly withheld by the operator, who is using VK. Do not stop,
pause, restart or reroute production. See VK_CAPACITY_OWNERSHIP.md. The running
legacy backend requires a separate one-time upgrade before using this protocol.

Fix read-only readiness to detect a capacity owner that survives process pause.
Branch fix/capacity-cutover-lock adds the existing-inode lock barrier and real
kernel-lock tests; it does not change production services or silently replace
the operator's same-PID standby requirement. Restart-based recovery is separately
rehearsed with copied data and requires explicit approval before production.

## Integrated Codex Model Selector Regression

Restore GPT-6 reasoning choices and hide GPT versions below5.6 in the Codex
selector. Updated onto staging fa7523c17, this frontend-only compatibility correction
does not rewrite existing chat selections, drafts, defaults or native settings.
No backend restart. See `VK_MODEL_SELECTOR_FIX.md` for evidence and deployment.

## Integrated Staging Context: VK::Weird Message

Scope: reconcile native goal completion evidence within the current turn and
report completion status in the standard summary metadata. Replace the generic
checklist warning with `Completion::` after `Human Needed::`, naming missing
evidence when unverified. VK normalizes its status into the existing report;
a response without a standard report receives a compact metadata line.

The reconciliation request is a single turn/steer pinned to the current root
turn. It never starts another turn, reopens the goal or changes its budget.
Final checkpoints remain accepted after the native completion notification.
A rejected/late steer falls back to an honest unverified status. Checklist
verification is supporting evidence, not an independent audit of the objective.

Backend and shared frontend changes are pushed for
[PR #123](https://github.com/artinflight/vibe-kanban/pull/123) into staging.
They are not deployed. See HANDOFF.md for validation and deployment boundaries.

## September 30: scheduled resume history

Scope: scheduled capacity resumes preserve native-goal supporting progress,
turn/stagnation counters, recovery plans and substantive input holds. Explicit
manual resumes retain their current fresh-attempt behavior. No scheduling,
quota, containment or selected-agent admission limits are relaxed. This is the
manager-side fix; the active Chat Orchestration implementation is separate.

October 9 integration: current staging e8c450fb is incorporated as the normal
PR base. Its original continuity documents remain preserved at that immutable
commit; this stream retains newer bounded candidate/recovery tracking. No live
service, route, credential or access change is performed by this merge.
