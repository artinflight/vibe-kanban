# Blue PR114 Preparation

## Scope

The operator requested preparation, not a production interruption. PR114 is
merged into staging at `75276e79fe64d112c8e85492aad32cadb5e83cc4` (version 0.1.42).
Green `vibe-kanban-green-production-20260914.service`, PID2778969, remains the
authoritative writer on4511/4512. Old Blue PID2590517 remains frozen. Neither is
stopped, thawed or replaced during preparation.

The new preparation directory is `/mnt/vk-storage/vk-blue-pr114-20260914`.
Its disposable Blue uses5011/5012. The uninstalled production definition is
`vibe-kanban-blue-pr114-production-20260914.service`, using5031/5032 against the
same authoritative Green-named database, Codex home and attachment roots.
Logical data paths do not change with service color. The old Blue is NOT the
candidate and its occupied4711/4712 ports are not reused.

## Evidence And Readiness

The exact-source release build and focused tests passed:68executor tests,
5capacity-guard tests,8renderer tests and3stale-approval/frontend tests. Two
opt-in native fixtures and one documentation test were ignored by the unit suite;
separate running replica acceptance exercised original-thread resume, ordinary
launch with broken optional capacity configuration, steering, Stop and goals.
Four existing-chat model/draft browser cases passed. All24fresh online SQLite
payloads were restored and integrity/hash verified. Rehearsal measured24.30s
including backup/Desktop verification, then0.12s same-PID/latest-data cutback.
Plan roughly a minute for the live window, subject to fresh active-work and
dirty-file inventory; these are measurements, not a guaranteed live duration.

Private test URL: https://mcp-server.tail744c4.ts.net:18467/. It is a disposable
copy with an offline provider, not a place for real work. Its one extra labeled
rehearsal saved message is not present in production. Green remains at vibe.local.

Read `readiness.json`, `desktop-ready-receipt.json`, `production-plan.json` and
`PROGRESS.md` in the preparation directory. Readiness is not established unless
the final record says `ready: true` and its artifact hashes still match.
Never infer readiness from this document or a healthy process alone.

PR114 changes ordinary-launch handling when optional capacity initialization or
grant persistence fails. Selected scheduled work remains guarded. The two UI
changes are parser-verified formatting only; the incumbent frontend, including
completed-checkpoint styling and retained hashed assets, is reused explicitly.
The backend and capacity guard must be newly built from the exact staging source.

Acceptance records cover the copied original thread, ordinary launch with a
deliberately broken optional capacity configuration, resume, Turn Steer versus
Stop, native goals, attachment round-trip, desktop/mobile saved messages and
existing-chat model/draft reload and submission. `rehearsal-latest.json` records
the actual switch/recovery implementation against isolated state, including a
failed backup before candidate startup and latest-data/settings cutback.

The replica copies current native-home histories and the original maintenance
thread. It does not copy every legacy history into its sandbox; unmapped and
historically missing histories remain explicit exceptions, not deletions or
claims of recovery. Full recovery archives and authoritative originals remain.
Phone-sized browser testing is not physical-phone QA. Prior historical missing
attachments/rollout tails and the duplicate draft-delete warning are not waived.

## Final Window

After readiness, obtain a new explicit cutover instruction tied to the readiness
hash. Work may continue on Green until that window. Recheck active executions,
queued messages, direct/native callers, current frontend and exact source.
Install the prepared reciprocal start interlocks and independent controller;
never run a historical consumed controller. Capture all final changes with the
incumbent paused, verify the Desktop copy, and start new Blue against current
production data. Never copy the earlier test database into production.

Keep Green's original process loaded and frozen for cutback. Cutback fences new
Blue, retains the latest database and refreshes Green's cached settings before
routing back. Do not restore an older database or silently interrupt new work.
Old frozen Blue remains fenced throughout. Continue the original maintenance
conversation for live acceptance; never create a replacement thread.

The separately prepared CodexUsage/capacity activation is not included or
authorized by this task. Its existing Green PID/port and artifact bindings must
be reassessed by its owning agent before any later activation.

Backups belong in `desktop:B:/vk-backups/vk-blue-pr114-20260914/`. Online deltas
still require the retained September11 preservation and recovery-metadata
archives; the final frozen delta is required at cutover. No original files,
worktrees, backups or recovery exceptions may be removed as restart cleanup.
