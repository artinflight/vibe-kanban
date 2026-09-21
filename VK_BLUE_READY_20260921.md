# September 21 Blue Restart Preparation

Preparation only. Green remains live. No production cutover is authorized.
The machine-readable readiness record below is authoritative: it must say
`ready: true` and have a verified Desktop package before scheduling the switch.
This document alone is not restart approval.

## Release And Roles

- Exact fork/staging: `df49b020706e831ae203d05b1b89723dc2321cc8`, version0.1.42.
  Includes PR121/122 capacity corrections, PR123 completion reconciliation,
  PR120 chat scrolling and merged PR117 model-selector preservation.
- Green incumbent: `vibe-kanban-green-production-20260915.service`, PID1674994,
  ports5091/5092. Current frontend is the September20 chat-scroll release.
- New Blue: `vibe-kanban-blue-production-20260921.service`, ports5121/5122.
  Its production service is inactive; tests use separate state on5131/5132.
- Old frozen Blue2150526, Green2778969 and Blue2590517 remain untouched.
  Never thaw these historical generations or start retired service names.
- Runtime package and readiness:
  `/mnt/vk-storage/vk-blue-refresh-20260921/readiness.json`.
  There is no approval file. The independent controller requires a new approval
  bound to this record, exact source, execution identity and companion restart.

## Preserved Companion And Frontend

CU staging `b8658683bedc224ce64732bf7c99a9631b12e0cb` supplies six capacity
files. The package retains the live weekly chart correction, Android download
page and downloads; the dirty live checkout is not replaced.104 Node tests
pass against this combined package. Initial mismatched test copies were
corrected to match the selected source, not suppressed.

Next-start settings point CU at the packaged release while preserving live
state, private credentials, usage cache, automation state and selected goals.
No live CU restart or goal enrollment occurred. Its restart belongs in the
separately approved switch window. Read-only preflight rejects newly changed
non-overlay CU files so subsequent live work is not silently discarded.

Frontend build61b111b4c matches the merged application tree. Every current
live hashed asset is retained for open tabs. The release server uses the
external frontend package; its unused embedded frontend is a build placeholder.
No DB migration, shared API type or Cargo lockfile changes occur from2fd585ac3.

## Validation Evidence

The task directory contains the exact-source release build log;78 executor
tests and5 guard tests passed,3 environment-dependent executor tests ignored.
All11 deployment configuration tests and3 approval/frontend-binding tests pass.
Renderer tests pass:8 checkpoint cases and11 summary-metadata cases.
Earlier equivalent frontend validation passed typechecks, lint,3 model tests
and production build. Full aggregate Rust checks/tests remain blocked by the
host's missing GTK development libraries; they are not claimed as passing.

Fresh isolated checks cover the copied original native history (105 turns,
same original thread resumed without submitting a turn), same-thread follow-up,
Turn Steer without cancellation, separate Stop, native goal completion,
attachment upload/retrieval and unchanged saved messages. Desktop/mobile
selectors preserve empty and saved drafts through reload and delayed history;
actual submitted configuration and native model evidence agree. Actual model
menus hide pre-5.6 entries and offer GPT-6 Low/Medium/High/Xhigh/Max.

Desktop/mobile settings and WebSockets pass locally and through a temporary
tailnet preview. The initial replica has12 saved messages; rehearsal adds two
explicit fixture messages only to copied data. Original production messages
are not altered. The copied prior thread-resume/error compatibility fixture
also passes two follow-ups against the new release binary.

The capacity audit's native scheduling/real-CU integration evidence remains
in `/mnt/vk-storage/codexusage-capacity/workflow-audit-20260921`; that earlier
agent rehearsal was reviewed, not rerun here. Fresh release tests additionally
cover the new capacity behavior and isolated authentication. Live overnight
account behavior and post-switch CU reconciliation remain acceptance steps.

## Backup And Rehearsal

Desktop destination: `B:/vk-backups/vk-blue-refresh-20260921`.
The fresh online archive is3,944,441,854 bytes; remote SHA256 matches
`9a15b7be408a73b1b9e41eaf0515ae9e4edb9dcd48d1723e8cc53ebe2b5bb377`.
All30 initial SQLite payloads were extracted and integrity-checked. A subsequent
online catch-up contains12 current critical DB snapshots, also restored and
verified. Preserve its parent record and archive; these are a recovery chain.

Both September11 Desktop baseline components remain required:
`preservation-backup.tar.zst` AND `recovery-metadata.tar.zst`, under
`B:/vk-backups/vk-cutover-20260911T1854Z`. Fresh hash verification is recorded
in `base-chain-check.json`; historical full extraction/comparison evidence is
retained, not represented as a new full extraction. The old journal had a
moved-directory error and was not reused. A fresh journal covers current
worktrees, native state, attachments, service settings and CU monitor state.

The actual switch/recovery functions were rehearsed on copied state, including
backup failure before activation, companion lifecycle and post-Blue writes.
The same Green PID resumed with the latest messages, config and profiles.
The first browser assertion expected an internal model ID while the UI showed
its friendly name. Evidence was retained, the test corrected, and the full
rehearsal rerun successfully, including actual submitted-model verification.

Successful rehearsal:30.25seconds switch,0.21seconds return before browser
checks. Separate online live-delta capture/verification:38.23seconds.
These are different measurements, not an end-to-end five-second guarantee.
Budget60-90seconds for the approved interruption; remeasure changed conditions.

## Approval And Recovery Boundary

Green stays usable while waiting. Before approval, refresh changed data and
check current staging/frontend/CU files, journal health, active executions,
queued work and external native writers. Do not interrupt unrelated active
work. Drain identified writers and obtain fresh approval for the bounded window.

Only then pause Green, capture and verify final changes, and activate Blue
against current authoritative paths. Test replica data never replaces live
data. Green remains loaded and paused for cutback; recovery uses the same
latest data and refreshed settings, never an older database restore.

After routing, require original-thread continuity, settings/models, saved
messages, attachment round-trip, desktop/mobile entrypoints, execution/Steer/
Stop/goals and CU connection/reconciliation. Preserve historical missing-thread
and attachment exceptions; this preparation does not resolve or erase them.

The verified software/controller/configuration package and its restoration
receipt must precede `ready: true`. Any later artifact or live frontend change
invalidates the readiness approval. No GitHub Actions were used.
