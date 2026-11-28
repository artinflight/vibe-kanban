# Combined archive/revival cutover preparation

Finish the full dedup/packed-reader/archive/revival/Nightly release so the
external managing agent can perform spinup/cutover. [Acceptance](VK_WORKSPACE_ARCHIVAL.md)
and [takeover scope](VK_DEDUP_TAKEOVER.md) remain authoritative. None of the five
full requirements is closed; source tests are not a deployable release.

Archived workspaces should move automatically to independently verified Desktop B
recovery. A message should revive the same workspace/session, preserve exact input
and settings, and dispatch once. Nightly should capture current active payloads,
SQL/catalog and shared dependencies while referencing cold generations separately.
Existing and future archives use the same lifecycle. Preserve active, pinned,
dirty, shared, pending and unresolved work and all earlier backup epochs.

Current work is on `vk/0815-archive-release` in the separate SSD checkout documented
in HANDOFF, based on staging78e472543. It retains staging provenance/delegation and
now also the exact shipped frontend patches missing from staging. Physical-driver
and actual Nightly source integration is implemented; production qualification is
unfinished. The root process-inspector package awaits the external manager.

No production restart/cutover, Nightly calendar activation, duplicate controller,
watcher or continuation loop is authorized here. Preserve Nightly ownership,
tracking/cursor and STOP/health controls. The old sealed dedup-only activation
remains unarmed and is not the combined archive release.

[Previous stream](deployment-history/20261128-before-runtime-integration/STREAM.md).

[Full historical archive](STREAM_HISTORY_20261017.md).
