# Current frontend deployment — 2026-11-02

The scrolling projects menu is live at `https://vibe.local`, published at
17:28:06 UTC. Public JS is `index-CRD24Nkw.js`; CSS is `index-BDlsFLgm.css`.
Feature commit `d0496eb1d4d6904aa69eb6b087d29c39ece488f0` is applied to the
actual prior live source: explicit-unread fix `70d7f5b0` with preserved chat-notice
source `800011bd`. All other live build inputs are byte-identical. The deployment
snapshot and composition receipt, rather than this branch alone, reproduce the
published frontend. See [release evidence](VK_SCROLLING_PROJECTS_DEPLOYMENT.md)
and [manifest](LIVE_DEPLOYMENT.json).

Five candidate and five public-browser cases passed with 60 synthetic projects;
normal desktop/mobile smoke checks showed all 19 real projects. Scrollbars are
hidden, the page and controls stay fixed, and wheel/touch scrolling works.
All application mutations were intercepted. The 27 current unread/chat-notice
regressions also pass. No physical-device QA is claimed.

The pointer changed atomically in 0.0143 seconds; all 770 old/new hashed assets
are retained with a paired fallback. The 74,848,460-byte software recovery archive
was independently restored locally and read back from Desktop B. All five service
PIDs/invocations, backend binary, database device/inode and 99 migrations stayed
unchanged. No backend restart, data restoration, provider call or device action.
Existing backend/history-proxy frontend roots and preview routes are preserved.
Reload existing browser tabs to receive the new frontend.

# Staging continuity before scrolling publication

# Current public frontend — 2026-11-02

The frontend correction is published at `https://vibe.local`. Deliberate opening,
reselection, reading gestures and jump to latest clear unread after the newest
loaded reply/error is visible in the focused foreground window for 350 ms.
Running and approval turns in the displayed conversation wait until they settle. Background return, passive
polling and new output alone preserve unread. The explicit bulk fallback remains.
Reload all existing VK tabs/devices. Historical unread flags are not reconstructed.

Corrective source `9a45a3abf2d99eb44c14ef7a744d6f7bf0fbb73e` is composed onto live base
`800011bd573e2869d6ea4c0e5bfba4d9046d9cbe`, retaining initial feature `70d7f5b0516a784ca6f27ba9fc6245b441666663`
and view correction `b8bad21792f863bce31c42742f7439cc8539503a`. Newer chat notices
remain byte-identical. Entry JS `index-DqfYW9pf.js`, CSS `index-C-pTuj_j.css`, version
`0.1.42`; both paired roots retain 874 assets. Manual-only release-1 and the
pre-running-guard release-2 are superseded. Rejected candidate-3 was never served.

Fifteen view regressions, seventeen explicit/readiness regressions and seven
adjacent navigation regressions pass, together with types, focused lint, required
format, ops and the preserving production build. Four candidate and four served
layout cases pass at 1440/393 pixels on both chat surfaces. Candidate and served
running-turn checks verify zero read requests while an API-verified turn runs.
Every application write is intercepted. Public TLS/assets/health, backend hash,
five service identities, DB inode/path and 99 migrations pass unchanged. Software
recovery is independently verified on Desktop B; fallback changes only frontend.

The unchanged seen API clears the whole workspace across sessions; its server
arrival race cannot be eliminated by frontend changes. Automatic approval review
rejected an optional real-server state test because per-turn bits cannot be exactly
restored. No live unread mutation/persistence acceptance, backend/API/schema/config
change, restart, provider execution or device work is claimed.

[PR #288](https://github.com/artinflight/vibe-kanban/pull/288) records staging rebase integration;
its final checks and merge event are authoritative. The prior full hosted Test
baseline 41493120165 passes; Rust source is unchanged. Private remote checks skip
without the deploy key. Main promotion is separate. See
[fix evidence](VK_DISAPPEARING_UNREAD_FIX.md) and [manifest](LIVE_DEPLOYMENT.json).
Older production records below are historical provenance.

# Current production and protections — 2026-10-31

The Antigravity-enabled release is live at `https://vibe.local`. It was accepted
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

The unread/review/reselect correction was operator-accepted from original source
`b990b5939642b1ac7e744a9290840a731fa3f550`. All 11 affected package files are
preserved byte-for-byte in the current combined frontend above. [PR #287](https://github.com/artinflight/vibe-kanban/pull/287)
integrates that correction into staging with the requested rebase method. It was
rebased onto PR #286's current staging after its previous head passed all checks.
The rebased package tree matches deployed composition `02a9a993d8d9118ca703a22baa15efcf0c7cc4c9`.
Twenty mounted regressions run in frontend CI. The PR's latest checks and merge
event record final validation and rebased integration IDs. Original deployed
source IDs remain immutable; Git integration does not redeploy or restart services.
See [unread evidence](VK_PROJECT_UNREAD_DEPLOYMENT.md).

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
