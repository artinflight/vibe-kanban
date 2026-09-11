# September 11 Blue Readiness Evidence

This records online preparation, not a production cutover. Green remains the
authoritative backend on ports 4511/4512 with the guarded rollback artifact. The new
isolated Blue test is https://mcp-server.tail744c4.ts.net:18464/ on the tailnet.
Its copied data is disposable; continue real work on Green until a separately
approved switch. Never promote the test database over current production data.

## Candidate And Recovery

Version 0.1.42 application code is `c184c75e5`, including the T25 correction,
recovery-first autonomous goals and PR104's attachment preservation guard.
Staging `3b3a65855` adds the established restart protocol without application
changes. Later documentation-only commits do not require another binary build.
Release hashes and source tree are recorded in
`/mnt/vk-storage/vk-cutover-20260911/release/manifest.json`.

Production Blue uses the same logical live DB, Codex home, worktree and attachment
paths after Green releases them. Rollback uses guarded old software against that
same latest state, never an older database copy. Active newly accepted work blocks
automatic rollback; preserve it and repair forward or coordinate a drain.

## Verified Functional Handover

`window-rehearsals/20260911T213203Z/result.json` under the cutover directory records
a complete disposable old/new/old handover using real backend binaries, the real
native agent engine, isolated writable state and an offline model fixture:

- Original test conversation continues on Blue and again after rollback.
- A message and untracked file created after preparation survive activation.
- Native `turn/steer` targets the active turn; Stop remains a separate killed
  execution. The eight-step goal reaches complete in the native goal database.
- New saved messages and an uploaded attachment survive rollback with matching
  attachment bytes. No older state is copied back.
- Existing desktop (1440x1000) and mobile (390x844) tabs reconnect through separate
  frontend/API/WebSocket routing. Reloaded pages work after both directions;
  there are no page errors. Ten original saved messages remain, plus test writes.
- The tailnet Blue test's actual saved-message picker shows all ten messages on
  desktop and mobile. Selecting one inserts its content into the draft without
  sending it. Evidence: `saved-picker-result.json` and screenshots.
- The online baseline and final delta are Desktop SHA256-verified. The actual
  delta's SQLite payload is extracted and checked, and the late untracked file
  is retrieved from the archive. Whole private service groups stop before capture.

The measured unavailable interval is 35.07 seconds, including the final capture,
Desktop verification, restore check, startup and frontend switch. Rollback with
conversation continuation takes 5.86 seconds. These are measured rehearsals, not
a five-second production guarantee. Allow approximately one minute for the
approved switch; perform slow preparation while Green remains available.

`window-rehearsals/original-20260911T210016Z/result.json` separately verifies this
actual maintenance session `75bc68d4-aa55-4914-a695-f20c46a13e4c` resumes native
thread `01a03e74-2c1a-72f0-9e00-8e4293fe910d` through Blue, preserving the copied
20.4 MB original rollout prefix. Only its repository is substituted in the private
test DB. This is not an authenticated production execution. Recent Green turns
and this private resumed turn have a nullable new-turn agent_session_id; the
older successful anchor and actual native resume response establish continuity.

## Backup And Final-Change Capture

Permanent backup components are on Desktop
`B:/vk-backups/vk-cutover-20260911T1854Z`. Keep the preservation archive and its
separate recovery-metadata companion together. All 23 companion SQLite snapshots
were extracted and passed integrity checks. The final production boundary does
not exist until the separately approved switch.

The new online refresh `online-refresh-20260911T210652Z.tar.zst` is 985,940,093 bytes,
SHA256 `30e5bf209b1a6cf0cfe1039e7f35d0876820f7e1577e5901aedcf11126f21266`, verified
on Desktop. Its consistent snapshots and changed files supplement the earlier
preservation archive; it is not a replacement for either original component.
Its five-minute preparation ran while Green stayed live.

A read-only change journal starts before online capture and tracks 108,873
directories. Final capture takes all changes since that earlier cursor, including
work accepted during preparation. Overflow, lost coverage or directory moves
invalidate fast-delta readiness rather than silently omitting files. Keep the
journal alive through approval; repeat volatile preflight before switching.

Debug `logs_2.sqlite` telemetry is copied during online preparation and its live
originals remain untouched. It is not recopied wholesale during the short window.
This exclusion does not cover rollouts, thread_history databases, goals, saved
messages, settings, attachment payloads, execution output or worktree files.
Held read-only SQLite connections check data_version and inode identity so real
commits or replacement are detected without mistaking WAL housekeeping for loss.

The complete preservation archive was extracted inside a filesystem/network jail
and every archived entry content-compared. The first extraction's restrictive
umask caused mode-only differences; permissions were corrected from the archive
and verified for 819,993 files/directories, with symlink targets checked separately.
No content, size, owner, link or missing-file differences were reported by the
full comparison. `full-restore-verified.json` records the combined evidence;
the original tar comparison's nonzero exit and mode-only log are retained.
No writable production paths were exposed to the restore. The roughly 103 GB
disposable restored copy is retained unless the operator approves its removal;
originals and verified backup archives are never part of that cleanup scope.

## Controller And Approval

The retired `vk-cutover-controller-20260911.service` is genuinely masked:
systemd reports `LoadState=masked`. Its ineffective runtime mask had been hidden
by the installed unit file. The original file is preserved as
`/mnt/vk-storage/vk-cutover-20260911/retired-controller-original.service`.
Neither this controller nor retired `vibe-kanban.service` may be revived.

The replacement operational artifacts are `handover_v2.py`, `emergency_v2.py`,
`incremental_capture.py`, `change_journal.py` and `vk-cutover-v2.service` in the
cutover directory. Default controller invocation is read-only preflight. The
service draft is not installed or running, and no fresh approval file exists.
Eight controller decision tests, four real change-journal tests and two SQLite
generation-versus-checkpoint tests passed;
systemd unit verification passed. Preserve the final tools archive and receipt.

The final approval records the current maintenance execution, a fresh timestamp,
the agreed measured window and acceptance of temporarily pausing the two idle
preview-owned native clients that share the history store. Check their full
identities before stopping Green, including replaced executable images. Do not
stop unrelated preview/application services or assume inherited CODEX_HOME means
a process is currently doing native work. Unknown writers block activation.

The independent controller must retain its own emergency recovery after its
maintenance turn is interrupted. Recovery is bound to the same systemd invocation;
stale continuation or approval files are not authority. Continue the original
session at most once, without Git reset or new-thread fallback.

## Historical Exceptions And Acceptance

This preparation does not repair the September 7 missing native tails/killed
startup, 429 previously unlocated attachment records, 115 exact worktree attachment
copies not yet restored to cache, or 118 absent nonarchived worktree paths. The
earlier 29 empty-history results were a test-home omission of thread_history;
all 2,621 indexed nonarchived histories passed corrected native reads. Keep the
actual historical recovery exceptions open.

The existing Green flyout close-button overlap predates this preparation;
isolated new Blue passes pointer-close checks. Broad GTK-dependent workspace
validation remains limited by the previously documented system dependency.
Live acceptance after the separately approved switch must still verify real
entrypoints, saved messages, original continuation, steering/Stop/goals,
attachments, execution and logs. Process health alone is not completion.
