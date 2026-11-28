# Maintained Nightly source in the combined archive release

This is the existing Nightly owner implementation from operator repository commit
`d419d85f4f5652a36f9372feaa889d59e4ee8079`, source scope
`scripts/deployment/*.py`. `UPSTREAM_SOURCE.json` records its original per-file
hashes. It is contained here so release qualification does not load a changing
external worktree. Source inclusion does not install a service or enable a schedule.

Archive integration changes only `vk_nightly_service.py`,
`vk_nightly_finalize_current.py`, `vk_nightly_composed_consumer.py`,
`vk_nightly_composed_restore.py` and the new `vk_nightly_workspace_archive.py`.
The service optionally opens the pinned archive driver selection before its
existing lifetime lease. The normal current map must omit cold payloads and
retain current SQL/shared dependencies. Its normal independent SQL readback
checks the exact cold catalog against the source-qualified selection.

All existing source tracking, provider/native leases, immutable epochs, journal
cursors, cycle receipts and schedule controls remain owned by Nightly. No new
backlog converter or scan is introduced. A changed/pending revival invalidates
acceptance and preserves earlier backups. Deployment source manifests must pin
the complete current closure, including these integration changes and the
separately pinned archive driver configuration. Actual B/runtime acceptance is
still required; source tests alone do not qualify the combined release.
