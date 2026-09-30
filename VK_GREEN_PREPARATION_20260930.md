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
`deploy/vk-green-20260930` at the runtime directory's `cu-source`, uncommitted and
not pushed. The live CU checkout and service were not modified. The operator was
asked whether to include this companion or leave new reporting inactive; no reply
was received during preparation. The proposed package includes the companion,
subject to review, rather than silently dropping reporting or capacity features.

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
  sentinel process. Its7.53second private test excludes Desktop transfer and
  live work draining, and is not a production downtime promise.
- `test_controller.py`: five outer-controller policy/failure tests pass using
  substituted service calls. Read-only production preflight also passes.
- `companion-acceptance.json`:173 CU tests and private HTTP/catalog checks pass;
  four previously recorded native executions reproduce98,093 tokens and one
  transition. Twelve duplicate imports are rejected. No paid model calls ran.

Existing CI was inspected only: the exact staging tip has passing ops governance
and skipped application jobs. Accepted V1 CI/native evidence is retained, and
the executor/RPC/container paths are byte-identical to accepted67c4a5b62. Do not
describe skipped exact-tip jobs as newly passing full CI.

## Preservation

Desktop destination: `desktop:B:/vk-backups/vk-green-refresh-20260930/`.
Online archive: `online-refresh-20260930T172948Z.tar.zst`,5,116,122,626bytes,
SHA-256 `bd672a5d8603b30ee3efe09ad901e6c139657f03ce23a6a0b21087ddb41de515`.
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

The read-only journal `vk-green-prep-journal-20260930.service` tracks work performed
after the online snapshot. Final frozen capture is reserved for the approved
window. Never activate from `runtime`, restore old data over production, or
delete historical recovery evidence. Bulky files remain on the mounted SSD.

## Remaining Boundary

Review the combined CU candidate and user-facing changes before promotion; resolve
the CI/QA requirement without silently launching paid Actions. Candidate, CU and
independent controller unit files remain under `prepared-units`, not installed.
This prevents an unrelated service recovery from activating new settings early.
Validate the effective installed settings after approval, before fencing traffic.

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
