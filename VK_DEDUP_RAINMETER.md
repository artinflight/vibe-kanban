# Live dedup HUD — Desktop, November 21, 2026

The installed `DedupProgress` Rainmeter card sits directly beneath Archive Queue
(`NReconcile`), at desktop coordinates238,-408, size420×218, with an8px gap.
It matches the existing translucent dark panel, cyan/magenta accent and
Segoe/Cascadia typography. Activation is saved for the existing Seamus Rainmeter
profile; no new recurring Desktop task is required. Double-click opens the
existing [live progress page](https://mcp-server.tail744c4.ts.net/vk-dedup-status).

## What it reports

- Resolved logs out of the finite3,362-log selection, percentage, verified logs,
  committed batches and committed original-history volume.
- Allocated live-log recovery including shared objects. This is **not final net
  filesystem savings**: retained staging, other growth and final accounting remain.
- Current stage, last source observation and last verified progress. Rainmeter
  fetches every15seconds; the existing publisher normally updates about once per
  minute. Counting does not imply conversion acceptance until committed.
- Explicit offline/stale/stalled/paused/backup-wait states. Source observations
  older than3minutes show STALE. A running job without verified progress for
 10minutes shows STALLED. Intentional pauses and backup waits stay distinct.
  Converter success displays CHECKS PENDING, never full deduplication completion.

The interface deliberately makes no ETA promise: batch sizes and backup/restore
cost vary, so a files-per-second estimate would be misleading.

## Data and ownership

`rainmeter_feed.py` adds a bounded, sanitized `VK_DEDUP_HUD_V1` comment to the
existing status HTML. The fixed counters come from the ordinary watcher snapshot
and the matching COMMITTED receipt; races omit the savings figure. No source log
is scanned. Private history, paths and errors are excluded. The helper's two-line
publisher integration is retained in `scripts/log-dedup/rainmeter/watcher-feed.patch`.

The existing resource-guard timer, route, incident ledger, dispatch settings,
separate WakeWatch chat and finite converter are unchanged. No backend or
Rainmeter process restart, synthetic wake, new agent or controller was created.
The HUD reads status only; it does not pause, resume or recover the job.

Desktop installation:
`C:\Users\Seamus\AppData\Roaming\JaxCore\InstalledComponents\DedupProgress`.
The skin INI uses UTF-16LE; Lua is under `@Resources`. A small local
`display-state.txt` receipt records the source timestamp and displayed state,
allowing verification that the real Rainmeter consumer received live observations.

## Validation and recovery

Ops checks and Rust formatting pass. Full `pnpm run format` stops at the web
formatter because Prettier is absent from this worktree; no web source was changed.
Five Python feed tests pass. Twelve parser/presentation scenarios pass inside
Rainmeter's actual Lua runtime, covering malformed/inconsistent data, offline,
stale, clock skew, stalls, intentional holds and success-with-checks-pending.
HUD-only captures verify the matching appearance, legibility and placement.
Native window inspection verified the same Rainmeter PID128024 and all existing
HUD positions/visibility. The only saved settings change is the new DedupProgress
section. Archive Queue source hashes are unchanged. The live consumer advanced
from126 to130 logs while the existing converter retained PID1316160 and its
invocation3594484094cb4790885a9b4b7570da3f. These are acceptance-time identities,
not authority for future process operations.

Small verified originals are on DesktopB under
`B:\vk-backups\dedup-hud\20261121-122919`. Installation/test receipts and
HUD-only images are staged at `B:\vk-staging\dedup-hud-20261121` and on mounted
SSD at `/mnt/vk-storage/vk-log-dedup-20261103-0815/rainmeter-hud-20261121`.
Use the scoped inspector/installer/verifier sources under
`scripts/log-dedup/rainmeter`; the installer refuses an existing installation.

To hide the card, deactivate only DedupProgress through Rainmeter. Do not restore
the whole historical Rainmeter.ini over later operator changes. Publisher rollback
removes only its import/embed call and helper, after checking current source and
holding the existing incident lock. Preserve all later watcher changes. The card
then shows stale/offline data; conversion and normal monitoring remain unaffected.

This completes the requested HUD. Historical conversion and the original final
recovery/service/accounting acceptance remain separate, unfinished work. The native
goal stays paused; no second continuation loop was started.

## November22 offline incident

The converter stopped when its Desktop SSH connections timed out. A separate
producer bug generated an alert resource longer than the shared codec allowed,
which erased the published process snapshot and made the card show OFFLINE.
The corrected producer retains fresh process observations if alert routing fails;
private alert errors remain in the ledger/status and a public warning identifies
the delivery problem. Bounded alert IDs pass the real failure/stall/success codec.
The unchanged Rainmeter process128024 received a fresh RUNNING observation at
1795345033 after the converter resumed. No skin, layout or Rainmeter restart was
needed. See [recovery evidence](VK_DEDUP_OFFLINE_RECOVERY.md).
