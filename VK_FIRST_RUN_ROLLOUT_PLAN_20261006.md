# Scheduled First Run: Combined Acceptance And Rollout

## Authority And Current Decision

October 6 staging-owner preparation only. **Not ready for rollout.** No production
restart, route change, merge, deployment, setting change, paid inference or agent
interruption is authorized by this task. Parent independent review and an explicit
rollout checkpoint are required. Earlier restart approvals do not apply.

Desired behavior: select an uninitialized goal now without starting it; its first
native turn initializes the checklist during the saved overnight window. No manual
start/stop workaround. Development owns source fixes; staging owns combined
acceptance, release provenance, preservation and the proposed rollout.

## Exact Candidates

| Component | Candidate | Base | Status observed |
| --- | --- | --- | --- |
| VK PR147 | `27d9562d2003836ae607f3b1bfdd54322588fb36` | staging `8b562265d25a3f8ee6d4fa602144e71caddfbc85` | Draft, mergeable, backend-test failed |
| CU PR38 | `95e7aea47e137015daa8efcbb210184ee7ce723c` | staging `c8213e81d18123671bce9a262c9dedf1a788a7bf` | Draft, mergeable, no listed CI checks |

Read contracts in VK `VK_SCHEDULED_FIRST_RUN.md` and CU
`docs/scheduled-first-run-vk-contract.md` at these exact revisions. Both candidate
tracked trees were clean. CU's existing untracked Python caches were left alone.
There were no published GitHub reviews at inspection; that does not mean the
parent's independent review is finished. Changed heads require revised provenance
and affected acceptance, not silent substitution.

VK backend-test job `112424355475`, run `37508783715`, failed in
`routing_triage::tests::simple_language_and_discovered_protected_context_raise_the_floor`,
`crates/executors/src/routing_triage.rs:509`: actual `Workhorse`, expected
`Frontier`. Cause and resolution belong with development/review; this audit does
not classify it as harmless or unrelated. Backend-schema was still running when
the receipt was captured. Existing CI was read, not dispatched or rerun.

## Evidence Checked, Not Repeated

Audit root: `/mnt/vk-storage/vk-first-run-staging-acceptance-20261006/`.
`audit.py` independently checks retained receipts and current read-only identity;
`audit.json` records exact SHA256s, service identities, PR status and blockers.
Its result is `audit_passed: true`, **`combined_acceptance_passed: false`**.
Audit receipt SHA256:
`06774385159722b5dab44be4a76589edc7c751f86a76dcb41cdb4f08ede010ad`.
Auditor SHA256:
`d7fafe69d9b75dbbf0ca68fc94d961681afa8a4f97e6a2df860a07e02a91207a`.
The read-only audit passed; `pnpm run format`, `pnpm run ops:check` and
`git diff --check` passed for this documentation-only preparation. No new native,
HTTP/scheduler, full workspace or paid test execution is claimed.

- VK retained index: `/mnt/vk-storage/vk-scheduled-first-run-20261006/acceptance.json`.
  Seven result/proof pairs under `/mnt/vk-storage/vk-sfr-20261006/` verify: 155
  executor tests plus six offline native cases (success/later resume, input,
  provider failure, identity race, plan review and empty checklist). These were
  not rerun. Each proof's boundary source hashes and result hash were checked.
- Their exact executable is `executors-ea5da41c91a59f7a`, SHA256
  `a854d6158f061d8fa60c14f5badfbf6cbe0b99b5f5036eccd16b1c0775f6c787`.
  It is an executor test binary, **not** an HTTP server release.
- CU package: `/mnt/vk-storage/cu-credit-aware/first-run-identity-release-20261006-8xs89s8c/`.
  `acceptance.json` SHA256
  `e3521f5e33b59edd109b252ced1078e3d5223e5664444b585a2bffc841c3589a`.
  Retained receipts cover 229 tests, scanner and desktop/mobile-sized UI. All
  referenced receipt hashes and 164 packaged file hashes verify. The 14 protected
  live files still match. These tests used mocked VK, not combined HTTP acceptance.
- Installed PR142 operational package verification passed; pin
  `528282d00c985230aad3033dc235d8cd943e5f4d` in
  `/mnt/vk-storage/vk-green-cutover-20261005`. Retain its 146 regression evidence;
  do not substitute older workspace scripts or repeat unrelated suites.

Production remains VK PID3027197, October 5 release/main `fa8122a50`, version
0.1.42, CLI0.159.2. CU PID414400 serves the goal-list package with deployed source
reference `02769eab8424d6cfc85d33900b5aa319045834bc`. Read-only CU control confirms
scheduling ON, credits OFF, connected, zero active grants. Saved window is
21:00-04:00 America/New_York. These observations are not permission to change
settings and not a substitute for a fresh agent/grant/queue drain at rollout.

## Combined Acceptance Still Required

All rows below are **pending actual combined execution**, even where unit/offline
receipts cover part of the behavior. Use the reviewed CU fixture isolation and
bounded fixture-manager boundary, exact candidate HTTP server/guard and CU
scheduler, synthetic workspaces/native threads, offline provider and private
state only. No real Android goal, production credentials, real provider traffic,
denied-prompt retry, live manager access or permissive substitute harness.

| Case | Required observable receipt |
| --- | --- |
| Select without launch | HTTP selection round-trip binds goal/thread/objective/native-seconds createdAt, session/workspace/path and turn anchor; pending persists; no execution, provider call, checklist or unpause occurs before the window. |
| Scheduled first native turn | CU saved-window tick with included quota dispatches exactly once through actual VK HTTP; successful authentic native root checkpoint has nonempty requirements; same-turn completion promotes eligibility. A file-only or empty checklist cannot promote. |
| Holds and restart | Provider failure, input, plan review, malformed/empty checkpoint, budget/window cutoff and ambiguous restart become durable holds. Reloading both services, another scheduler tick or reselecting cannot silently retry or launder the hold. Denied request is not retried. |
| Capability withdrawal | Capability 1 to 0 rejects new pending admission and prevents continuation of an initialization grant; safe removal remains possible. Existing hold evidence survives. |
| Legacy dispatch | Old CU request lacking exact firstRun identity is rejected for pending goals with zero launches; already checkpointed normal resume remains compatible. |
| Races and concurrency | Change each bound identity/turn anchor after selection and before worker; duplicate/concurrent requests, foreground work, lease ownership and the existing two-goal limit reject or serialize safely. Record execution/provider counts and no cross-workspace launch. |
| Revocation | Revoke before dispatch and during initialization; no stale grant launches/resumes afterward, holds/receipts remain accurate and removal is possible without retry. |
| Later normal resume | After successful initialization, an ordinary eligible window resumes the same native thread without firstRun or a second initialization. |
| Rollback reader | Upgrade private v1 state to v2, create each hold, switch to the proposed compatible fallback and reload; all identities/holds remain, unauthorized retries remain zero and allowed removal works. |

Receipts must bind both source and executable hashes, boundary hashes, HTTP
requests/responses without secrets, synthetic identities, private before/after
ledger/checkpoint state, scheduler time/window, execution/provider counts and
case outcomes. Preserve canary/masking proofs: host worktrees read-only, no real
service-manager route, no live sockets/config and no external provider egress.
The existing executor driver and checkpointed-goal integration test alone cannot
satisfy this matrix. Do not run those drivers against live endpoints.

## Rollback Compatibility Is A Release Blocker

PR147's controller accepts stored version1 or2 but commits version2 even with
`VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION` disabled, including ownership
acquisition. Disabling the feature is **not** a downgrade of the stored format.
Current production and its paused fallback are old readers and cannot be used as
the post-upgrade rollback reader. Do not erase fields/holds or restore an older
ledger/database to make an old reader start.

Development must provide a reviewed version2-aware fallback artifact, or evidence
that a proposed exact candidate with admission disabled is an adequate fallback.
The latter disables new first runs but does not roll back candidate code defects.
Staging must exercise its latest-data hold preservation/removal behavior in the
same isolated boundary before calling rollback ready. Preserve original thread,
model selections, read/unread flags, saved messages, attachments, wrappers,
AutoSwitch module, shared private routing feed and other services.

## Minimal Proposed Rollout After Approval

1. Finish parent review, resolve CI, obtain source-bound HTTP/guard and compatible
   fallback artifacts, complete the combined matrix and release-source checks.
   Prepare while existing agents keep working; no production interruption needed.
2. Publish the reviewed CU-compatible version first against current VK capability0.
   Preserve scheduling ON/credits OFF and monitor state. Verify capability0 is
   inert, normal checkpointed resume remains compatible, and no pending native
   first turn is dispatched. This is a future CU-only service change, not permission
   to make it now; verify its capacity worker state before interruption.
3. At the explicit rollout checkpoint, use the pinned PR142 tools for fresh
   Desktop-backed capture, moved-root/journal verification, review-state snapshot,
   exact runtime/module/shared-feed checks and latest-data rollback rehearsal.
   Keep preparation separate from the short final pause; do not reuse a consumed
   handover or call October5 backup evidence a current backup.
4. Safely drain VK executions, queued prompts and CU grants immediately before
   the one coordinated backend handover. Active agents must finish/checkpoint;
   any requested pause uses Turn Steer, never a competing writer or forced kill.
   Bind feature-gate configuration to the approved release so another restart is
   not casually required. Switch frontend/API together; retain compatible recovery.
5. Verify actual routing/release, original sessions, owner settings and protected
   data. Enable no paid test or real Android test. User selection is inert and
   normal scheduled work waits for the saved window. Report updated/current version
   plainly, not merely a color. Any cutback keeps the same latest state and holds.

Expected user impact: work continues throughout preparation; a short agreed final
drain/handover affects VK agents. No measured duration for this candidate exists
yet. Prior 21.972-second switch is historical, not a promise for this release.

## Remaining Blockers And Ownership

- SSD has only 28,258,304 bytes free at audit. Parent/storage owner must arrange
  safe headroom or an approved adequately sized isolated location. No shared-tree
  cleanup, bulk copy, system-disk build or backup fallback was performed.
- Development must supply exact PR147 server/guard provenance; existing inspected
  old servers and the executor test executable are insufficient.
- Development/review must resolve the failed backend test and complete required CI.
- Reviewed combined HTTP/scheduler harness execution and compatible rollback-reader
  evidence are missing. These are not waived by the retained unit-test counts.
- Parent independent review and explicit rollout checkpoint remain required.

Retain `/mnt/vk-storage/vk-green-cutover-20261005/historical-recovery-receipt.json`:
five-root later-unbacked edits remain unaccounted; deletion timing/CU causality is
not proven; historical missing rollouts remain exceptions. Do not drop protected
roots, reset journals or reclassify historical loss as repaired. No new production
backup or Desktop payload was created for this bounded preparation audit.
