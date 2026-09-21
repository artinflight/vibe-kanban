# September 21 Restart Preparation

Status: NOT READY. Preparation is authorized; production cutover is not.
No services, routing, production data or frontend pointers were changed.

Integration update: PR117 merged September21 as df49b0207. Its application
tree matches validated candidate61b111b4c; canonical staging is current.
The model-fix omission and continuity conflicts below are resolved. Fresh
frontend build, typechecks/lint,3 model tests,11 summary tests and actual
desktop/mobile menus pass. Full aggregate Rust checks/tests are blocked by
missing GTK development libraries. Candidate backend packaging, CU scope,
backup/rehearsal and final approval remain outstanding. Use the new staging
head for further preparation, not the superseded fa7523c17 baseline.

Storage update: authorized rehearsal retirement completed later September21;
see VK_REHEARSAL_RETIREMENT_20260921.md. SSD now reports75GiB free. The original
4.3GiB observation below is historical; recalculate peak candidate requirements
against current capacity before starting preparation. Other readiness gates
remain open. Cleanup is not restart approval.

## Verified Release Scope

Fetched fork/staging is fa7523c17ce0339cf4848a507b2b1273eb43db16.
The two September 21 agent streams are merged:

- PR122 (0df82745f): scheduled goal readiness, manual takeover and native resume.
  PR121 (0cd0b6323), the usageLimited wire-status prerequisite, is also merged.
- PR123 (fa7523c17): same-turn goal-completion evidence reconciliation and
  compact completion metadata rendering.

PR120's chat-scroll fix is also in staging and is already frontend-deployed.
No DB migrations, shared/types.ts or Cargo.lock changes occur between the
September 15 backend baseline 2fd585ac3 and this staging head.
This is not a full code-safety certification or candidate acceptance.

## Incumbent And Candidate Roles

Green vibe-kanban-green-production-20260915.service remains live, PID1674994,
FreezerState=running, port5091. Its API reports version0.1.42 and succeeds.
Blue vibe-kanban-blue-pr114-production-20260914.service remains frozen,
PID2150526. Prepare a newly named Blue generation; do not accidentally thaw
the old Blue against live data. Preserve all historical frozen generations.

The current frontend resolves to
/mnt/vk-storage/vk-chat-scroll-20260920/release, source3da008db2.
Its deployment document records the model-selector baseline f175c1b5b plus the
chat-scroll fixes. September 15 frontend paths in older handoffs are historical.
Any new fallback receipt must preserve this current frontend, not an older one.

## Readiness Blockers

1. PR117 remains OPEN and absent from staging. It carries the already-live
   model-selector fix: no pre-5.6 choices and GPT-6 reasoning options. A plain
   staging frontend would lose that fix. A merge-tree check found conflicts in
   HANDOFF.md and STREAM.md only, not application code. Resolve and integrate
   the PR, then pin and validate the resulting staging head before building.
2. The SSD is mounted from /dev/sdb1 but has only4.3GiB available (449GiB used).
   The previous preparation needed more than this for its isolated native-data
   copy alone. No new full copy, build or restore rehearsal was started. Agree
   a verified relocation scope or supply capacity before allocating bulk data.
   Never delete retained recovery copies or use the system disk as fallback.
3. CAPACITY_WORKFLOW_AUDIT.md requires accompanying CU staging for durable
   activity history. Its exact source, dirty checkout boundaries, configuration,
   companion restart scope and package validation still need verification.

## Evidence Reviewed And Checks Run

- Fresh GitHub merge state and local ancestry identify the release scope above.
- Fresh merge-tree attempt for PR117 fails only on the two continuity files.
  This did not alter a branch or working tree.
- Reran the existing compiled summary-metadata test artifact:11 passed.
  This is not a fresh build of the eventual integrated candidate.
- Read PR123's rebased executor test log:78 passed,0 failed,3 ignored.
  This is the other agent's recorded validation, not a new executor run here.
- Read capacity audit evidence and its isolated native/CU rehearsal report.
  No live goals, scheduler selections or automation settings were mutated.
- Read-only production API and service/freezer checks pass.
- Desktop SSH is reachable; drive B reports206,054,875,136 bytes free.
  This is a capacity check, not a newly verified backup or relocation.
- Ops governance and diff whitespace checks pass. Repository formatting was
  rerun with Cargo on PATH after the first attempt failed to locate Cargo.

Full candidate builds, isolated functional acceptance, fresh backup/restore
verification and measured switch/cutback rehearsal remain outstanding.
No GitHub Actions were started. Prior test reports note missing gobject-2.0
for the aggregate workspace checks; that limitation is not a passing result.

## Remaining Preparation And Approval Boundary

After integration and capacity are resolved, package exact staging server,
release-matched guard and frontend; include the verified CU companion scope.
Use the established restart protocol with separate test data and services.
Verify original-thread recovery, Steer versus Stop, goals, saved messages,
existing-chat model choices, actual reasoning menus, attachment round-trip,
chat scroll and completion rendering at desktop/mobile entrypoints.

Verify a fresh recovery package on Desktop B:/vk-backups, including required
historical recovery dependencies. Rehearse the actual controller and latest-data
cutback, then publish readiness bound to source, artifacts and current frontend.
Wait for explicit operator approval before the final interruption. Green stays
usable throughout preparation. At the approved boundary, drain and pause Green,
capture final changes, and activate Blue against current authoritative data.
Never promote test replica data or restore an older database over production.
Preserve documented historical recovery exceptions; this audit did not resolve
missing historical attachments or threads.
