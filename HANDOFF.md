# Active completion handoff — 17 November 2026, late UTC

Full objective: finish lossless backward production deduplication, measured net
recovery, normal-B recoverability, ordinary UI/service/WakeWatch restoration and
deployed future-growth evidence. Read VK_LOG_AGENT_HANDOFF.md for the full scope;
its old plan-only authorization describes the previous turn. The goal is active.

Production remains on the aware readers with ONLY the four earlier archives.
This turn fixed the documented capacity-release lost-response bug in public
scripts/log-dedup/capacity_release.py plus prepare_capacity_host.py. New inert
private host/helper under P/completion-20261117-capacity-host; PREPARED pins them.
Still integrate capacity_release_source into NEW host config and host_source into
NEW operation inputs, including source/recovery closures. Do not edit/replay v5
or any consumed package. The new helper also reconciles saved intent during
recover_boundary before the old no-release branch.

111 focused tests pass (11 release tests +3 actual patched-host integration tests
included), format passes using pinned Prettier3.6.1, ops/diff pass. tests.log and
format-with-pinned-prettier.log retained. No broad build or PR update this turn.
Fresh LIVE_STATE confirms reader/public/five normal watcher ticks; actual current
native0.159.2 initial resume is0turns/1,826B, no provider request added.

P=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117.
D=P/completion-20261117-demand. B metadata lookup COMPLETE:6,732requested names,
5,676found entries through existing leased Nightly native context; no payload
capture. BACKUP-MAP-*.private.json carries decoded map rows. Match exact current
hash/size against PLAN-*.private.json; lookup presence is not restore proof.

LIVE read-only sizing job: exec session70465, PID2294952, exact script
D/measure-v3.private.py. Poll this same handle and inspect actual process before
any retry. START-v3 records identity. Older measure/measure-v2 are terminal with
retained FAILURE receipts (transient full PSI .18/.19). V3 waits at unchanged
resource floors for at most600s, persists per-file plans/sizes, and reuses stable
completed plans; it is not a maintenance/controller/goal loop. At last observation
1,560 of3,366non-tiny logs /4,761,656,829rawB measured. No live log writes.
RESULT.private.json means complete sizing only. Preserve partials if it stops.

Next actionable gaps: complete exact B demand and SSD peak/rollback bounds;
qualify rendered review/settings/queue checks; integrate the fixed helper and
size-admitted batch order into a fresh sealed operation; then execute all remaining
beneficial batches, complete normal-B all-store closure and actual allocation/FD
release, recover ordinary public UI and exact watcher state. Resource floors stay
4GiBRAM/.10fullPSI/3GiBSSD. Original backups, all objects, inputs and selected
settings remain protected. No new recovery is claimed yet.

Historical scope: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
