# Deduplication and workspace archive separation

November27 source integration: start with [the restart-agent takeover scope](VK_DEDUP_TAKEOVER.md).
Current staging's specialist-delegation and run-provenance changes are retained;
their original notes are preserved in [staging history](deployment-history/20261127-staging-integration/staging-HANDOFF.md).
Git integration does not deploy this unfinished combined scope.

Finish lossless packed deduplication and the newly authorized workspace archive
lifecycle before proposing the combined managed restart. Archive actions should
automatically move eligible workspace payloads to verified Desktop B storage;
sending a message should revive the same workspace and preserve the input and
selected settings. Nightly should retain active payloads plus SQL/catalog/shared
recovery dependencies, with cold payloads separately restorable.

[Archive scope and acceptance](VK_WORKSPACE_ARCHIVAL.md).
[Packed dedup evidence](VK_DEDUP_PACKED_LAYOUT.md).

Existing archive flags need one migration through the same lifecycle. Preserve
active/pinned/dirty/shared data, queued inputs, backup epochs and existing owners.
The intent outbox is source-only; it grants no retirement or backup exclusion.
Do not claim the mover, revival or Nightly integration is implemented.

Nightly calendar activation remains excluded. Preserve its tracking and partial
cursor; no uncertain replay or duplicate jobs/watchers/agents/model polling.
Daily dedup remains held under its existing maintenance condition.
Backend restarts are performed by the managing agent outside Vibe. The sealed
dedup-only candidate remains unarmed and is not the combined archive release.

[Previous scope](deployment-history/20261125-before-workspace-archival/STREAM.md).
Full historical archive: [STREAM history](STREAM_HISTORY_20261017.md).
