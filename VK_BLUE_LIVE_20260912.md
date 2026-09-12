# September 12 Blue Cutover

## Current Runtime

Blue is production after the separately authorized V3 handover at11:33 UTC.
`vibe-kanban-paused-blue-20260912.service` serves4711/4712, PID2590517 at
acceptance. Original Green PID2669659 remains loaded and frozen, not restarted.
Green is disabled for boot; new Blue is enabled. Both old Blue generations stay
inactive/disabled. Gateway4720 selects Blue; `vibe.local` and HTTPS3443 use it.
Static frontend4313 follows `frontend-dist/current` to the new served assets.

Application baseline is staging586ac628d, version0.1.42, including Turn Steer,
native goals/recovery-first behavior and PR108's recovery acknowledgement fix.
Blue binary SHA256:
`d0a2ca1b0a2c59fccf103f50c96612999b9346eee6b568d7f1f021a9ed49d329`.
Frontend index SHA256:
`9dd02fb1533bc6387e7f3c78a12142dccf71eb5d694e63f5dd5867e40290fc7f`.

## Acceptance

- Original VK session75bc68d4-aa55-4914-a695-f20c46a13e4c resumed native
  thread01a03e74-2c1a-72f0-9e00-8e4293fe910d. No replacement maintenance thread.
- All frozen-boundary IDs remain:40 projects,894 tasks,908 workspaces,63 repos,
  939 sessions,38561 executions,12049 coding turns and775 attachment records.
  SQLite integrity passed;231 existing cached attachment hashes verified;
  3546 indexed rollout files present. These checks do not repair historical gaps.
- Ten saved messages match exactly through gateway and HTTPS3443. Actual-domain
  desktop/mobile settings and WebSocket checks passed, with the UI caveat below.
  New attachment b819d718-6f52-4793-bc8c-73f7acd03d34 uploaded/downloaded exactly.
- Labeled test session4eefa404-cac8-446a-8bf6-2ff35e65a4a7 passed real live steering
  without a second execution, completed a native goal, then separately tested
  Stop resulting in `killed`. Test artifacts remain; existing agent work unmodified.
- Corrected isolated rehearsal invoked the actual rollback function, including
  a pre-Blue backup abort with no settings PUT and Blue-created profile overrides.
  Same-PID/latest-data cutback, attachments, native continuity and desktop/mobile
  reload passed. Private window25.62s; cutback5.84s. Production recorded21.69s
  after freeze to Blue activation, not a universal timing guarantee.

## Remaining Caveats

The desktop project-flyout close control can be covered by workspace content.
Pointer-close failed live; keyboard close worked. This was recorded before
cutover too. Do not call it passed or conceal it as a browser-test workaround.
Mobile settings passed without that warning. Physical mobile/Tailscale-device
QA and broad GTK-dependent workspace validation were not performed in this turn.

Historical missing native tails/killed startup, unlocated attachments and absent
worktree paths remain the previously documented recovery exceptions. No blanket
claim that every historical byte is recovered. PR108 does not erase old prompts;
a successful durable reply acknowledges old recovery context for later turns.

## Backups And Recovery

Permanent directory: `desktop:B:/vk-backups/vk-cutover-20260911T1854Z/`.
Keep original preservation archive AND recovery-metadata archive, online refresh,
and final delta together. Latest online archive112321Z SHA256:
`84e17dd1dc17729b88b88047c643e570bb3ef17f6b4f8cf4438e31287c6be876`.
Final frozen archive `final-boundary-20260912T113349Z.tar.zst`,67974821bytes:
`5888232e98ffb984f3443a30da7cb83cd4428d58609d71e40ee2ff4981c6ce05`.
Both Desktop copies verified. Final capture verified stable committed generations
and extracted SQLite payload hashes. Restore only into an isolated destination;
never put these older snapshots over production after new work.

For a requested cutback, independently fence traffic and drain current work,
stop only Blue, thaw the original Green PID, refresh its caches from latest
persisted settings, then route Green. Never thaw Green while Blue can write.
Do not reuse stale maintenance execution IDs, approval files or attempt markers.
Reboot loses a paused process; same-PID thaw is a current-boot fallback, not a
claim that a paused Green survives reboot.

## Lessons From The Failed Attempt

The01:17 attempt aborted because the model catalogue changed, then recovery
incorrectly PUT override-only profiles into an API requiring complete profiles.
Emergency recovery repeated that mistake, leaving the gateway in maintenance
until independent recovery at02:28. The earlier rehearsal used a different
profile source and missed the actual controller defect.

The corrected controller expands overrides over exact incumbent defaults,
compares effective serde defaults, and avoids unnecessary settings writes.
Seventeen controller/journal/SQLite tests and the actual private recovery path
passed. Old failed controller is persistently masked; old readiness withdrawn.

Refresh copies narrowly exclude downloaded model catalogues and diagnostic
logs, which remain in baseline/live data; no histories, goals, settings, work or
execution history are excluded. A fresh journal/baseline replaced the stale
directory-move watch. Online SQLite snapshots pin a read generation so continuous
telemetry writes cannot indefinitely restart copying.

Overlapping temporary copies exhausted the SSD during repair. Failed scratch
copies were moved to Desktop with per-file hash verification; redundant SQLite
staging/extraction copies were verified against retained archives before retiring.
No production data, worktrees or backup archives were removed. After subsequent
operator approval, only the verified disposable restore-test extraction was
removed, freeing108358057984bytes (about101GiB) and leaving about104GiB free.
Both required Desktop archive hashes were rechecked; no active consumers or
nested mounts referenced the extraction. The removal receipt and adjacent
location note preserve its audit trail. Blue and paused Green were unchanged;
saved messages, SQLite quick check and live attachment round-trip passed afterward.
Future preflight checks must budget peak snapshot/archive/extraction usage;
V3 requires3GiB free reserve.

Evidence: `/mnt/vk-storage/vk-cutover-20260911/PROGRESS.md`,
`paused-v3-attempt.json`, and `paused-handover-20260912T113343Z/`.
