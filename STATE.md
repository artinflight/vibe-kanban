# Current production and protections — 2026-10-30

WakeWatch automatic disk waking is now enabled through the existing printer-style
connector without a restart. Its single approved verification turn completed at
12:00:07 UTC with the exact expected acknowledgement. The refreshed client now
exposes all 46 Vibe tools, including both TurnSteer tools, and a real receipt read
through the refreshed tool succeeded. See [current scope](scripts/watcher-events/CONNECTOR_TRANSPORT.md)
and [TurnSteer access](TURNSTEER_ACCESS.md).

The Antigravity-enabled release is live at `https://vibe.local`. It was accepted
at 03:18:14 UTC: backend source `9a4179e8bdf38e93d1a81faca6c665cadd6fddc7`,
executable SHA256 `137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
The 0.1.42 label also identifies older artifacts; use [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json)
and fresh readback. Public gateway 4720 routes API through history proxy 5640 to
backend 5621. All frontend roots now use the matched bundle; both release pairs
retain old/new hashed assets for open tabs. Blue remains retired.

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
