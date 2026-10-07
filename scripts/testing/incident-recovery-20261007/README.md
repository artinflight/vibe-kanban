# Retained October 7 Incident Recovery Source

These are exact copies of the scripts used at
`/mnt/vk-storage/vk-combined-release-20261007/incident-2316`, retained for review.
They are not general deployment, cleanup or restore commands. Do not replay
consumed placement, staging-index recovery or source-restoration operations.
They require the original authenticated manifests and no-replace plan. The
original failed and resumed placement receipts both remain in the evidence root.

Read `VK_RECOVERY_INCIDENT_20261007.md`. `recover_private.py` reads complete B
archive streams through the pinned hardened reader, but extracts only the
affected worktrees and Git registration metadata into private scratch. It does
not restore a live database. `place_missing.py` uses exact authenticated paths,
fresh hashes and atomic no-replace placement. Cross-filesystem copies are limited
to small original Git registration metadata. Existing files and symlinks are not
replaced. The read-only `post_audit.py` preserves detached-HEAD recovery exceptions.

Seven synthetic placement tests passed on the SSD. Twenty-seven private snapshot
retirement tests passed separately. Neither proves preservation of arbitrary
edits made after the backup; that limitation remains explicit. Full deployment
handover acceptance has not passed and the pending release is not live.
