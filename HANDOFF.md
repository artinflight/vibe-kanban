# Read Later pickup — implementation ready, publication blocked

As of 2026-11-04T21:20:55.397887+00:00, source commits `8aa46ba36` (save already-read workspaces) and
`449819b1e` (phone section sizing and overlap regression) are complete. The
operator's current request is implemented and validated but **not deployed**.
Live still uses the previous inline-icon release; LIVE_DEPLOYMENT.json and
STATE.md remain its authoritative runtime record.

Current feature behavior in the candidate:
- Already-read and unread ordinary workspaces offer the existing inline bookmark.
  Read/unread flags remain unchanged. A saved workspace stays in Read Later after
  reading/polling/reload and beyond pagination, until explicitly removed.
- Removal uses "Remove from Read Later" in all seven locales and returns a read
  workspace to Completed/idle history. Issue/inbox unread eligibility is unchanged.
- Attention → Read Later → Running → Completed order, browser-local host/user
  preferences and VITE_DOT_SIDECHAT=0 remain preserved.
- Section natural height explicitly overrides h-full, preventing long phone lists
  from overlapping the Read Later header. The earlier rejected candidate under
  `save-read` was never published; retain its diagnostic evidence.

Validation passed:
- UI/web-core/local-web types, focused lint, required format/ops/diff checks.
- 15 Read Later, 15 conversation-read, 10 notice, 12 pagination/Dot and five
  preservation regressions. The corrected production tsc/Vite build passed with
  one CPU, 5 GiB cap, 2.3 GiB observed peak and no swap.
- Packaged candidate: four desktop/phone × read/unread cases passed inline icon,
  section bounds, save/reload/remove, no overflow/errors, zero read/application
  writes and no Dot polls. Five scrolling layouts passed. New live-browser tests
  have not run because publication has not occurred. Full Rust/hosted baseline,
  real provider sends and physical-device tests were not run.
- Exact live composition: 1,324 pinned source inputs, 11 reviewed production edits,
  417 hashed outputs, 1,137 paired assets; all other live sources preserved.
- Software recovery: 116,678,639 bytes, full isolated restore and 5,071 file hashes
  verified. Desktop B copy has **not started**: another owner holds the native
  shared backup lane. Do not interrupt or bypass that owner.

Release gate: VK_AGENT_DEPLOYMENT_RUNBOOK.md step 6 requires a verified current
Desktop B recovery copy. An asynchronous choice was offered: keep waiting, or
explicitly waive that copy for this frontend-only release. No waiver was received.
Only this task's idle waiter was stopped while awaiting that decision. No owned
backup/controller/browser/build process remains active; no automatic deployment.
No backend/service/data/read-state/device change or push/PR was performed.

Evidence and prepared fresh controller:
`/mnt/vk-storage/vk-read-later-20261104-f57c/save-read-fixed`. The controller is unused and requires Desktop B verification; do not
reuse stale ownership evidence blindly. Before resuming, re-read the current
pointer/source/artifact and protected service/database identities. If the pointer
changed, compose against the new live source and repeat the preservation gate.
Preserve VITE_DOT_SIDECHAT=0. Complete Desktop B copy and independent readback,
then fresh atomic publication, four public browser cases and five scrolling
layouts, trusted public/runtime verification, final continuity and commit.
`record-final-deployment.py` in the evidence root consumes actual activation and
live receipts; it must not run before those checks exist. A waiver requires an
explicit bounded operator instruction and truthful recovery/controller records.

Prior continuity: [pre-reconciliation record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [full historical archive](HANDOFF_HISTORY_20261017.md).
