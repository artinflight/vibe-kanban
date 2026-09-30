# September 30 Green Preparation

## Current State

The operator requested staging-to-main preparation and clarified that the final
action is a cutover, not an ordinary restart. No cutover permission was given.
Production Blue remains PID764264, ports5121/5122, unit
`vibe-kanban-blue-production-20260921.service`. CU remains PID2139576.
No production service was stopped, paused, restarted or rerouted.

Candidate source is exact fork staging620bd7eb9bced30711cd560108e5f1c5a798dd5a,
version0.1.42. Main remains32c556f3e6dd455f5ad4651ba82e74f6e2148967.
The promotion merge-tree has no conflicts. No promotion PR, main merge or
GitHub Actions launch was performed. The prepared production port is5261/5262.

## Included Work

The new delta includes PR125's two selected capacity goals, PR126's scheduled
resume recovery history and AutoSwitch V1. V2 is excluded. Manual routing stays
the default; existing chat models/reasoning must not be reset. No new migration
or Cargo.lock change exists relative to the currently deployed1b31e1874.

All19 issues in the project's In Staging column were audited against branches.
Sixteen match by ancestry or patch equivalence. Three exceptions were resolved
semantically: the older follow-up send action evolved into staging Turn Steer;
unknown-item sanitation is present in84a55972d; generated Vite metadata was
intentionally removed by a86dfe6a5. None is an omitted feature based on this audit.

CU reporting cannot safely deploy from the dirty canonical checkout: that branch
predates capacity code already running. An isolated reconciliation preserves the
actual live CU release and adds only V1 telemetry. Its source is on
`deploy/vk-green-20260930` at the runtime directory's `cu-source`, committed as
406f19b and not pushed. The operator explicitly approved including this package.
The live CU checkout and service were not modified. The clean isolated source
and a verified Git bundle preserve the reconciliation; it is not claimed merged
into CU main or staging.

## Evidence

Root: `/mnt/vk-storage/vk-green-refresh-20260930`.

- `validation.json`: release/guard build, formatting, ops governance, frontend
  production build and diff checks pass. Frontend typechecks/lint pass; aggregate
  check/lint stop at the known missing `gobject-2.0` Tauri dependency.
- `evidence/non-tauri-tests.log`: full non-Tauri workspace tests pass. Executor
  subset includes96 passing tests/four ignored and five guard tests.
- Focused frontend tests pass:11 summary metadata, eight styled goal-checkpoint,
  three routing-selection regressions. No metadata/checkpoint styling was dropped.
- `functional-result.json`: isolated original fixture-thread resume, Turn Steer,
  distinct Stop, goals, attachment byte round-trip and saved messages pass.
- `original-history-check.json`: the actual maintenance history was read through
  the candidate CLI using a copied index/rollout. No replacement thread or real
  inference was created. This is a read check, not a live resume claim.
- `live-ui-result.json`, `model-menu-result.json`:1440px and390px layouts pass;
  saved messages, WebSockets and model/effort menus work with no page errors.
  No model older than5.6 is offered. Xhigh is displayed as Extra High. These are
  browser layouts, not physical-phone or Tailscale-entrypoint acceptance.
- `ownership-result.json`, `handover-rehearsal.json`: actual old/new binaries
  reject competing/stale ownership, recover from backup abort and return to the
  same original PID with the latest message/model/settings/controller state.
  The shipped handover primitives are exercised; CU's dependency gate uses a
  sentinel process. Its3.32second private test excludes Desktop transfer and
  live work draining, and is not a production downtime promise.
- `test_controller.py`: seven outer-controller policy/failure tests pass using
  substituted service calls. Failed main/emergency recovery does not resume
  writers without a healthy routed owner. Repeated cutback handles an already
  released/frozen candidate. `install_prepared.py` passes its default dry run;
  it requires separately bound approval before installing any production files.
- Refreshed read-only production preflight passes with active work still running.
  Blue764264/CU2139576 remain unchanged. The HTTPS API returned200 using the
  existing local-certificate bypass; host curl does not trust this CA, so this
  is availability evidence, not new TLS trust validation.
- `companion-acceptance.json`:173 CU tests and private HTTP/catalog checks pass;
  four previously recorded native executions reproduce98,093 tokens and one
  transition. Twelve duplicate imports are rejected. No paid model calls ran.

Existing CI was inspected only: the exact staging tip has passing ops governance
and skipped application jobs. Successful accepted CI at52381535641bc23c8adfedcf0251b772fcb7b608
covers the identical entire staging tree c399d1faa1317a6ace906b71e0a3a0569b886a8e.
`ci-tree-equivalence.json` records the comparison. This is stronger than the
previous subset comparison, but is not a newly launched exact-tip CI run.

## Preservation

Desktop destination: `desktop:B:/vk-backups/vk-green-refresh-20260930/`.
Online archive: `online-refresh-20260930T181003Z.tar.zst`,5,116,791,972bytes,
SHA-256 `4add9d0ffc58e644998a7422866dcca865cf3b387d194e11ebd9ac2fbf983997`.
Desktop matched the hash; all30 SQLite payloads were extracted and passed
integrity checks. Required September11 baseline archives were freshly hashed on
Desktop; existing full baseline restore evidence is retained, not rerun as a
new full extraction. This is a recovery chain, not a standalone full archive.

The fresh inventory has40 projects,969 tasks,991 workspaces,1032 sessions,
39,864 executions and12 production saved messages. The private replica adds
sentinels; its larger message count is not production data.333 existing attachment
files match their recorded hashes. Historical unavailable attachments and2282
missing VK rollout paths remain exceptions;2824 missing paths across both native
homes is the wider backup-audit scope, not a new-loss count.

An active test run moved a watched directory, invalidating the original change
journal. That error was not ignored: a new watcher and fresh online baseline
were created while production remained usable. Old archive/receipt are retained.
The read-only journal `vk-green-prep-journal-refresh-20260930.service` now tracks
work after this baseline. A newer journal socket invalidates an older baseline;
preflight and final capture enforce that relationship. The old watcher is stopped.
Final frozen capture is reserved for the approved
window. Never activate from `runtime`, restore old data over production, or
delete historical recovery evidence. Bulky files remain on the mounted SSD.

## Remaining Boundary

The operator approved the combined CU package. Opening the staging-to-main PR
automatically launches GitHub Actions; the previous explicit prohibition still
applies. A specific permission question was sent and remains unanswered. Main
promotion is held for that decision, not for a known failing release test.
Candidate, CU and
independent controller unit files remain under `prepared-units`, not installed.
This prevents an unrelated service recovery from activating new settings early.
Validate the effective installed settings after approval, before fencing traffic.
Do not advertise the cutover as ready while the requested main promotion is held.

Fresh cutover permission must bind the final readiness digest and exact source.
Recheck staging, live frontend, active/queued work, journal health, backup coverage
and launcher qualification. CLI0.159.2 proof expires after24 hours and is bound
to the recorded launcher/account/home. Both VK and CU use the same new private
telemetry feed; fixture events are never production input.

The approved handover will stop CU, release Blue's scheduling lock while its API
is responsive, pause Blue, capture/verify final changes, activate Green in standby,
acquire ownership, route traffic and reconcile CU. Blue remains loaded for
latest-data cutback. Post-switch live acceptance must cover original-thread/model
continuity, saved messages/drafts, goals/Steer/Stop, attachments, desktop/mobile
entrypoints and CU connection/reconciliation. The controller changes next-start
ownership back to normal after acceptance; a host reboot was not tested here.
