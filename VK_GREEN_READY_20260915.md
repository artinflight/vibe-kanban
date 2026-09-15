# September 15 Green Preparation

Preparation only. Blue remains usable; no cutover is authorized yet. Final
readiness is the verified `readiness.json` and Desktop receipt under
`/mnt/vk-storage/vk-green-refresh-20260915`, not this document alone.

## Release And Roles

- Staging/source: `2fd585ac30bfa75975f6319585e4a66bb684fdcf`, version0.1.42.
- PR115 fixes newer Codex error-category decoding; PR116 makes capacity
  deployment configuration a required versioned release input.
- Incumbent: `vibe-kanban-blue-pr114-production-20260914.service`, PID2150526,
  ports5031/5032. Gateway4720 and vibe.local remain on Blue.
- Candidate: `vibe-kanban-green-production-20260915.service`, ports5091/5092,
  installed but not started or enabled.
- Preview: isolated copied data on5071/5072, private Tailscale18468. It uses an
  offline provider and includes labelled rehearsal records; never use it for
  real work or copy its state into production.
- Old Green2778969 and historical Blue2590517 remain frozen. Neither is the
  candidate. Immediate cutback is to current Blue2150526 using latest data.
- Authoritative data stays in the existing green-named XDG/Codex homes and
  attachment roots. Color does not identify storage ownership.

## Validation Evidence

The exact-source release build passed for server and capacity guard. Executor
tests:73 passed/3 ignored; guard tests:5 passed; one doc test ignored. The
explicit captured-resume test passed with all154 turns. An isolated HTTP test
resumed the same formerly failing fixture thread twice without replacement.
Eleven capacity deployment tests and three stale-readiness binding tests passed.
Eight completed-checkpoint renderer tests, repository formatting, Ops Playbook
and diff checks passed. The clean canonical staging reference was fast-forwarded
to the same pinned release commit.
Full workspace/Tauri checks were not run for this preparation.

Frontend inputs are identical to live PR114, apart from two root ops scripts.
All1390 retained frontend files match. Isolated checks passed for12 saved
messages, attachment upload/retrieval, same-native continuation, Turn Steer,
separate Stop and goal completion. The copied original maintenance thread
resumed97 turns without submitting another turn. Four desktop/mobile model
tests retained draft/empty-chat choices through reload and actual submission.
Private HTTPS desktop/mobile settings checks passed with websocket traffic.
Known post-send `Scratch not found` remains a pre-existing warning, not repaired.

Actual switch/recovery functions passed against private services and copied
state, including backup failure before activation. Successful switch27.36s;
cutback0.14s retained newly written messages, settings and profiles. An existing
chat submitted the right model after cutback. The CU lifecycle peer was private;
these timings do not prove real CU reconnection time or a five-second window.

## Backups And Cutover

Desktop directory: `desktop:B:/vk-backups/vk-green-refresh-20260915/`.
Online archive `online-refresh-20260915T003436Z.tar.zst`, SHA256
`a3ffb61bcda0285f553c5f6b6a2dcb3831a2119ebbfea6d26fa2e28f0322f048`, is verified
on Desktop. All26 SQLite payloads were extracted and integrity/hash checked.
This is not the frozen boundary. Retain the September11 full preservation and
recovery-metadata archives plus subsequent deltas; historical recovery exceptions
are unchanged. No old database may be restored over production.

New CU and unit-config journal coverage supplements the existing journal.
Any overflow, missing coverage or changed staging invalidates readiness.
After fresh approval, refresh online changes before fencing, drain accepted
writes, pause Blue and external native writers, stop CU, capture/verify the
final delta on Desktop, then start Green and CU against current authoritative
state. Do not promote the replica. Rollback stops Green before thawing the same
Blue process and refreshes cached settings from latest data. Original thread
continuation and full live acceptance remain mandatory after routing.

CU PID3155695 remains unchanged during preparation; installed settings are not
loaded yet. `live-check` after routing must prove the new connection is reconciled.
No automation, reset or selected-goal setting was enabled/changed. Old Blue
fallback may restore ordinary VK work without the new capacity integration.

The independent controller requires a fresh approval bound to readiness hash,
source commit, current maintenance execution and native process identities,
including the CU restart. No approval file was created by preparation. Allow
roughly a minute for the window; capture size and CU startup determine actual
time. If final checks fail, retain current data and return to Blue, not an old
backup. Check free SSD space again before catch-up/capture; it was17GB during
preparation before final packaging. No user data or old backups were deleted.
