# Replacement Green From Staging

## PR113 Readiness Refresh

PR113 is merged into staging32676919b. The tested frontend sourcef224ec7ae has
an identical full tree to that merge; both the pinned source and canonical
staging checkout now point at32676919b. The only changes from503dbad74 are the
checkpoint renderer/parser, its tests and a document. Backend inputs are unchanged;
the previously tested server/guard binaries are reused, not rebuilt.

Current frontend is index-Ca4e1mj1.js in Green and release584226ead in live Blue.
Eight renderer tests and desktop/mobile Tailscale saved-message/WebSocket checks
passed again after integration. Three controller tests reject changed frontend
paths, changed frontend content and stale readiness approvals before service
actions. The unchanged switch/recovery, thread, attachment, goal and model tests
retain their earlier evidence; they were not all repeated for this UI-only patch.

The refreshed production plan pins the current Blue frontend for rollback. The
controller additionally requires `cutover-approval.json.readiness_sha256` to match
the exact published readiness record. Its default preflight remains read-only.
New archives use unique refresh timestamps, preserve prior records, and must be
restored/hash/mode checked and Desktop-verified before ready=true is published.
Only the latest `readiness.json` plus `release-tools-backup-receipt.json` authorize
a claim of preparation readiness; neither authorizes actual cutover.

## Scope And Authority

The operator accepted Blue as stable, authorized retiring the original frozen
Green, and explicitly required PR112 to merge into staging before preparing the
replacement. PR112 in `artinflight/vibe-kanban` merged September14 at12:07:40UTC
as `503dbad742128959dfba4b2dbf9835a6de5379f6`. Main was not promoted. No GitHub
Actions were invoked. An unqualified `gh pr view` defaults to the upstream repo
on this checkout; use `--repo artinflight/vibe-kanban` for authoritative PR state.

Blue remains production on4711/4712 behind gateway4720, PID2590517. Its live
frontend is `vk-goal-checkpoint-render/release-584226ead`. Current data roots
remain the existing green-named XDG directory, Codex home and attachment cache.
Nothing in the disposable replica is an activation or restoration source.

The old frozen Green PID2669659 was terminated without thaw. `systemctl kill`
returned an auxiliary-process EINVAL after the main process exited; independent
PID/cgroup/service reconciliation confirmed retirement, so it was not retried.
Its unit is runtime-masked and boot-disabled. Original data and artifacts remain.

## Candidate And Evidence

Task root: `/mnt/vk-storage/vk-green-refresh-20260914`.
Pinned source: `source/`, detached staging32676919b. Canonical staging is
`/mnt/vk-storage/worktrees/vk-reference-staging`, on the same commit. Backend
inputs equal reviewed PR head4a2f8fcf5; checksum-verified backend artifacts were
reused. The completed-checkpoint frontend was rebuilt and validated separately.
Application version remains0.1.42.

- Server SHA256: `3e4e594f9f531477b3d7df3300be9de7599d1b8b7bf7ab54a41c6bdd8d114380`.
- Capacity guard SHA256: `a66c85f10c8039906da37d3e3408f40b978690ddbc0b0c6edb028e8097a36680`.
- Frontend entry: `index-Ca4e1mj1.js`. Incumbent hashed assets remain available.
- Test service: `vibe-kanban-green-staging-20260914.service`, loopback4911/4912.
  Private test URL: `https://mcp-server.tail744c4.ts.net:18466/` (Tailscale only).
  This endpoint remains tied to the replica, never production4511.
  Bubblewrap exposes only copied writable state, no live homes or systemd bus.
  Real native Codex uses an offline provider, not subscription traffic. This
  test environment does not authorize real project work or production writes.
- Snapshot inventory:40projects,902tasks,916workspaces,951sessions,
  38,719execution rows,779attachment rows and12saved messages. Three running rows
  were marked killed only in the copy because their real processes were absent.
- `functional-result.json`: same-native follow-up, Steer on the same execution,
  separate Stop cancellation, native goal with8checkpoints and completion,
  attachment upload/retrieval, saved messages unchanged and SQLite quick check.
- `runtime/original-native-result.json`: copied ORIGINAL thread
  `01a03e74-2c1a-72f0-9e00-8e4293fe910d` read86turns and resumed the same ID.
  No message or replacement thread was submitted to the original live session.
- `ui-result.json`: desktop1440x1000/mobile390x844,12saved-message titles,
  project flyout, current asset and WebSocket traffic; no page errors in those
  screens. This is browser emulation, not physical-phone QA.
- `model-ui-result.json`: existing chat with empty/saved drafts, reload and
  delayed history loading on both sizes. Selector, submitted model/reasoning
  and native resume configuration matched; original native ID retained.
- Repaired PR112's native scheduled-resume/model evidence and14DB/6renderer
  regression tests remain in `codexusage-capacity/pr112-repair` and
  `PR112_REVIEW.md`. Same reviewed artifacts are used here. Not all prior test
  suites were rerun; full non-Tauri workspace testing was previously incomplete.

## Known Limits

The model test records an unchanged post-send `Scratch not found` page error:
the backend clears a draft after spawning; the frontend then deletes it again.
This is not evidence of model loss or a newly introduced PR112 change. The
  model/draft assertions remain separate from this warning. The same warning
  was reproduced with the incumbent binary after isolated cutback. Do not claim an
error-free application or that every historical selection issue is repaired.

The offline provider can print Python shutdown warnings when VK stops its test
process group. The server itself has shut down cleanly after drained work with
exit0 and no Tokio timer panic. This bounds the prior review caveat for the
drained deployment path, not every possible active-task teardown.

The paired CU PR7/controller rollout is separate. Unused-capacity operation
stays unconfigured/off in this VK deployment until that private integration is
reviewed and enabled. Its native goal/model checks used isolated evidence; real
quota harvesting and earned-reset redemption were not deployment tests.

Historical native-tail/startup and attachment coverage exceptions are unchanged.
The extra copied legacy indexes include old absent/superseded entries; do not
mistake those for new restart losses. Retain the September7 recovery evidence.

## Backups And Next Window

Permanent destination: `desktop:B:/vk-backups/vk-green-refresh-20260914/`.
`retired-green-software.tar.zst` is software/config only, SHA256
`37e988a75b4a09d11defc8518120a3eee7237a88eb870b8327e1d5fe09a4e6ee`.

Fresh online delta: `online-refresh-20260914T122416Z.tar.zst`,2,623,055,184bytes,
SHA256 `43b101b58c889e92ed4546b3839d6edb95d2fe36d3a824aa464708c963a0b79b`.
Desktop hash verified; all25SQLite payloads were extracted, hashed and integrity
checked. The delta requires BOTH `preservation-backup.tar.zst` and
`recovery-metadata.tar.zst` in Desktop's `vk-cutover-20260911T1854Z` directory.
The main archive's full isolated restoration was verified September11; the
companion remains required for SQLite and recovery metadata. No archive may be
copied over newer production data. This online snapshot is not a final boundary.

`switch_recovery.py` is the role-based handover/recovery implementation used by
the prepared controller and isolated rehearsal. It preserves the incumbent PID,
tests backup failure before candidate start, and refreshes latest persisted
settings after candidate writes before routing back. `rehearsal-latest.json`
is the current result; earlier failed test records are retained. The successful
final corrected run measured24.91s including Desktop-verified database capture,
0.39s candidate activation and0.13s cutback. It includes the buffered-write drain
and an existing-chat model submission after cutback. Additional live dirty-file capture,
inventory/draining and later acceptance are not included in that timing.

The production unit, reciprocal Blue start guard and independent controller/
recovery units are prepared files, not active changes. Green will open the SAME
latest production paths after Blue is paused, never its old replica. All live
work may continue during preparation. A fresh `cut over now` authorization must
identify the actual maintenance execution, accepted external native processes
and measured capture limit. Current discovered external native consumers include
Oharafit preview, CodexUsage preview and a tmux scope; they must be accounted for.
Preflight blocks other active/queued work, changed identities and uncovered repos.

At the authorized window, stop only the disposable Green replica to close testing,
install the prepared units and reciprocal guard, recheck inventories/artifacts,
and use the independent controller. It pauses Blue, captures/verifies the final
delta, starts production Green and changes the coherent route/frontend. Keep
Blue's original process paused for latest-data cutback. The original maintenance
conversation resumes for live acceptance. Do not start the old controllers,
reuse stale approvals, mark interrupted work completed or restore old state.

Readiness and packaged controller hashes belong in `readiness.json`; the package
receipt belongs in `release-tools-backup-receipt.json`. Expect roughly a minute
for the final window, not a five-second promise; refresh the estimate if the
journal delta or writer inventory grows. The independently supervised controller
was syntax/unit-definition checked; its actual switch/recovery functions were
exercised against isolated services, including pre-start failure and post-write
cutback. Production execution and physical-device QA have not occurred.
No activation approval is implied by this document.
