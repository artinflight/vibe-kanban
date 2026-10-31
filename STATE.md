# Current production and protections — 2026-10-31

The same-workspace reselection correction is live at `https://vibe.local`,
published 2026-10-31 at 12:04:09 UTC from
`b990b5939642b1ac7e744a9290840a731fa3f550`. Public JS is `index-Cy2e9ltd.js`;
CSS/version remain `index-CUBB2mA2.css` / 0.1.42. The operator reported "no change"
after the previous 11:15 frontend. Fresh live reproduction then found actual
nested-workspace reselection sent zero seen requests and left unread set. The old
"reselect" test clicked the parent issue card, changed routes and missed that bug.

Deliberate selection of the already displayed project workspace now sends a read
action; different destinations still wait for loaded chat. Polling and background
tabs preserve new unread. The new regression fails on the previous frontend and
passes on candidate/live at 1440/393 px with real read persistence and reload.
Thirteen mounted regressions, focused types/lint, format/ops and production build
pass. Existing candidate flag/preservation gates also pass, original test flags/
body restored. All service and database identities remain unchanged; the pointer
switch took 5.6 ms. Both paired roots retain 559 assets with verified Desktop B
software recovery. The operator accepted the fix ("Good") and authorized PR, sync and rebase merge.
The full PR baseline is running before integration. See [release evidence](VK_PROJECT_UNREAD_DEPLOYMENT.md).

The Antigravity-enabled backend remains live. It was accepted October 30
at 03:18:14 UTC: backend source `9a4179e8bdf38e93d1a81faca6c665cadd6fddc7`,
executable SHA256 `137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
The 0.1.42 label also identifies older artifacts; use [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json)
and fresh readback. Public gateway 4720 routes API through history proxy 5640 to
backend 5621. Public frontend publication at 13:07:50 UTC adds workspace project
filters while preserving the October 31 unread/review/reselect fixes exactly.
Combined frontend source is `02a9a993d8d9118ca703a22baa15efcf0c7cc4c9`;
public JS is `index-Bgdr6hzC.js`. Backend/history-proxy direct frontend roots
retain October 30 assets. The new public release retains all previous hashed
assets, with an immediate paired frontend fallback. All five services, the backend
executable and the database identity were unchanged. Blue remains retired.
See [filter deployment evidence](VK_WORKSPACE_FILTER_DEPLOYMENT.md) and the
manifest for build provenance, backup and verified public readback. Source
integration uses [PR #286](https://github.com/artinflight/vibe-kanban/pull/286)
into staging with rebase; its merge event records integration and rebased IDs.
Main promotion remains separate.

Antigravity is available with the existing personal account, tested
`gemini-3.8-flash-low` and supervised permissions. Actual native approval, denial,
resume and cancellation passed with four model turns total. Public availability
and defaults passed without further inference. No new production workspace prompt
is claimed. Browser access is closed; no further login is needed. See
[Antigravity evidence](VK_ANTIGRAVITY_ACP.md) and [the checklist](DEPLOYMENT_CHECKLIST_20261030.md).

Current database/native homes, 99 migrations, protected histories, settings,
review state and 17 uncertain inputs were retained without replay. The first
activation refused an empty reader-created WAL identity mismatch; recovery
restored the original process/consumers without restoring data. A detached repro,
strict fix and fresh roundtrip preceded the successful release. See
[activation/recovery record](ACTIVATION_RECOVERY_20261030.md).

The immediate fallback is the working October 29 `ddaaf64a`/`a63eb3a68173…`
release with its paired UI, now tested against a fresh current DB and later-write
sentinel. The older `d154fe9d` bundle is retained separately. Cutback uses the
latest compatible data, never an old snapshot over new writes. Drain/recheck
before future cutback; fallback disables Antigravity execution.

Public source intentionally omits sixteen private retained-history bindings.
Preserve the exact private input, protected reader, native homes, attachments,
queues, saved settings, Recommend behavior and existing capacity/approval controls.
Automatic provider failover remains disabled. Top-level service memory limits
remain unlimited; executor limits/capacity guards remain separate safeguards.

The recovery/deployment tooling and docs are reconciled in the isolated
`fix/deployment-reconciliation-20261030` branch and
[PR #284](https://github.com/artinflight/vibe-kanban/pull/284), targeting staging
with the operator-requested rebase method. All eight hosted workflows passed on
`a4213813210ea15affb1d91a306883cb27f452e3`; fresh read-only live verification passed
at 09:20:33 UTC. The PR merge event records integration status and rebased IDs;
main promotion is separate. Preserve original build receipts and unrelated
canonical-checkout edits. Read
[backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md) before another deployment.

Builds use the owned SSD target with bounded resources and no duplicate large
install. Backups belong on Desktop B; bulky staging uses mounted SSD and verified
RAM where explicitly bounded. Old controllers/PIDs/leases are consumed evidence.
A 600-second verified-no-progress watchdog and separate 300-second recovery remain;
there is no total 50-minute cutoff.

Prior topic map: [previous index](deployment-history/20261030-before-reconciliation/STATE.md).
[STATE history](STATE_HISTORY_20261017.md) remains indexed by [CONTINUITY_ARCHIVE.json](CONTINUITY_ARCHIVE.json).
