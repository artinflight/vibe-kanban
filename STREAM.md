# Nightly Backup Efficiency Integration

Existing workspace604d and PR263 own the single Nightly worker/package/schedule.
Seamus authorized completing operational commissioning on October26. No backend
restart, Staging controller change, duplicate backup writer, history migration,
source/recovery deletion, security change or new spend is authorized here.
All backup bodies must stream directly to Desktop B; local files are code/control
metadata only. Preserve Desktop-off continuation and genuine owner/STOP guards.

Acceptance requires a current recoverable baseline with independent readback/
restore, durable gap-aware change tracking, demonstrated unchanged-workspace
reuse, interrupted-component reuse, exact installed worker/config/schedule and
next run, and a documented bounded restart-consumption interface. Source tests
alone are insufficient. Reuse accepted162.70GB/137DB and all valid later layers.

Current source work reconciles PR263 against Staging and authenticates reusable
components from failed v8i without relabeling its parent as accepted. Historical
17SQL/one-rollout/five-watch counts must not be treated as current requirements.
The current v11 observer is Staging-owned and is not replaced or reconfigured.
A new observer epoch or namespace census is not proof of complete body coverage.

The active MM STOP latch and Staging-only finite B grant currently block Nightly
payload commissioning. Preserve them; only their owner can issue an applicable
Nightly contract or resolve the stop. Continue bounded source/test integration.

Prior branch intent and evidence remain in
[STREAM history](STREAM_NIGHTLY_HISTORY_20261026.md), authenticated by
[the archive manifest](NIGHTLY_CONTINUITY_ARCHIVE_20261026.json).

The merged upstream stream archive remains in
[Staging stream history](STREAM_HISTORY_20261017.md).
