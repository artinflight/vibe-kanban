# September 15 Green Live Acceptance

Green is live after the operator's explicit "proceed". The independent controller
completed the switch in28.11seconds. No older database was restored, no replica
was promoted, and the original maintenance conversation resumed on its original
native thread with GPT-6/xhigh. The handover must not be repeated.

## Final Runtime

- Live: `vibe-kanban-green-production-20260915.service`, PID1674994,
  enabled/running5091/5092. Gateway4720 and https://vibe.local route Green.
- Source: staging `2fd585ac30bfa75975f6319585e4a66bb684fdcf`, version0.1.42,
  including PR115 resume-error compatibility and PR116 capacity deployment.
- Latest-data fallback: `vibe-kanban-blue-pr114-production-20260914.service`,
  original PID2150526 retained frozen/disabled. Stop Green and drain writes
  before thawing Blue; refresh cached settings from current persisted data.
- CU: `codexusage-preview.service`, restarted as PID1674995. Versioned
  `live-check` passed: correct running configuration, route, connection and
  reconciliation. Unused-capacity automation remains off, with no background
  jobs. No goals were enrolled, no resets redeemed, no scheduling enabled.
- Idle external native PIDs613308/2136204 resumed with unchanged identities.
  CU-owned idle native609589 ended with its service restart, as inventoried.
- Old Green2778969 and historical Blue2590517 remain frozen separately; do not
  thaw them as the immediate rollback target. No worktree or user data deleted.
- Isolated test preview5071 and its private18468 route are stopped.

## Live Evidence

Evidence root: `/mnt/vk-storage/vk-green-refresh-20260915`.
Consumed attempt: `cutover-20260915T083542Z`.

Frozen-record preservation passed for40 projects,907 tasks,921 workspaces,
63 repositories,956 sessions,38,836 executions,12,321 turns and784 attachment
records. Database integrity is OK;5,909 native index paths match the boundary.
All240 available attachment hashes checked, and a new retained test attachment
uploaded/downloaded correctly through the production entrypoint. Historical
missing-file exceptions are preserved, not counted as recovered attachments.

All12 saved messages match exactly and appear in settings and the actual saved
message menu at desktop1440 and mobile390 widths. Websockets and deployed assets
passed; these browser checks do not substitute for a physical phone test.
All211 non-test frozen draft/executor payloads match. The labelled acceptance
session consumed only its empty test draft; no user draft was edited.

Real Turn Steer redirected the same execution; its native goal completed.
Separate Stop correctly left its test execution killed. A browser reopened the
existing test chat and submitted GPT-6/xhigh to its same native thread; the turn
completed. The original maintenance thread/model was verified independently.
Only the maintenance execution and labelled Stop test were intentionally
interrupted. No interrupted user task was presented as complete.

## Backups And Remaining Exceptions

Desktop directory: `desktop:B:/vk-backups/vk-green-refresh-20260915/`.
Final frozen archive `final-boundary-20260915T083549Z.tar.zst`, SHA256
`4f136afd9572fe869d9c638e568c8774fefa917db2a7c7ae9c321ac7281099ad`, was verified
on Desktop before activation. Retain its online parent delta, the earlier online
backup, ready package, and September11 full preservation/recovery-metadata
chain. Final acceptance, committed notes and receipts are archived separately
by `finalize_live.py`. Never overwrite current production with these older DBs.

Logs retain the known missing July13 attachment0fa37354 and unknown Codex item
warnings. They are not new cutover failures or waived recovery obligations.
Host CLI does not trust the existing local TLS issuer; vibe.local checks used
the explicit verification bypass already used in prior acceptance. Certificates
and routing infrastructure were not changed. Full workspace/Tauri tests were
not run; targeted build/tests and live acceptance are documented separately.

The SSD had11GB free before final evidence packaging. No cleanup was performed;
recheck capacity before the next backup or deployment. Old Blue does not have
the new loaded capacity settings: rollback preserves ordinary VK operation and
latest data, not proof of capacity feature activation on that older process.
