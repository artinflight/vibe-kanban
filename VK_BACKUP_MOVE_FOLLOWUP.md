# October 4 Backup And Preparation Follow-up

## Scope And Delivery

The October 4 cutover is accepted. This follow-up changes operational tooling
only; it does not restart production, alter routing, restore a database, or
deploy HYROX/accounting. See [VK_UPDATED_LIVE_20261004.md](VK_UPDATED_LIVE_20261004.md)
for the actual service and acceptance evidence, including historical exceptions.

Branch `fix/vk-backup-move-preflight` starts at staging `86d1c083a` in the existing
staging workspace. It imports the already deployed backup/preparation fixes and
77-test baseline from the verified October 4 deployment-tools package, then
strengthens move evidence and package integration. This overlaps the operational
prerequisites in open PR133, `fix/vk-production-preparation-costs` at `af0eb4369`.
That older branch is not descended from current staging; importing its whole
tree would discard newer application work. This follow-up selectively carries
the tooling only. Resolve the PR133 overlap during review; do not replace staging
with that branch. No frontend/backend application source changes are included.

## What Counts As A Protected Move

A missing folder is not automatically a harmless rename. A recoverable move
needs a protected source and destination, observed directory-removal evidence
for that specific source, observed destination evidence, live covering watches,
and a uniquely bounded destination subtree copied and hashed at both capture
boundaries. Cross-parent or differently named moves use an explicit destination
to source mapping. An unrelated removal event cannot prove a move. Ambiguous
sources, aliases, symlink escapes, missing roots/watches, journal overflow and
unknown errors remain fatal. Removal events and source tombstones are retained;
restore must remove the old source and restore the destination with its contents
and permissions. Existing historical recovery exceptions are not broadened.

`journal_compat.py` and `subtree_recopy.py` now live in checked-in deployment
tools, not only an old package. `vk_rolling_backup.py` uses their configured
reader for both capture and resumed delivery. Authenticated parent metadata
permits incremental copying, but complete subtree hashes are still checked.
Coverage is stored in `move-coverage.json`, not by rewriting `backup-plan.json`:
the unchanged plan preserves parent-chain reuse and avoids an unnecessary full
checkpoint. Newly covered subtrees absent from that parent are copied fully.

## Next Preparation Integration

Use a clean, published checkout containing this fix. Before readiness/software
sealing, install the checked-in operational tools into the new, unconsumed
handover package through:

```bash
python3 -B scripts/deployment/vk_prepare.py package-tools \
  --root /mnt/vk-storage/<new-preparation> \
  --coverage /mnt/vk-storage/<discovered-move-coverage>.json
```

Coverage records bounded `recopy_roots`, explicit `move_sources`, and the freshly
discovered `journal_identity` service/PID. Examples are not authority to reuse
October 4's watcher PID or moved paths. Unknown templates, changed identities
and already consumed/sealed packages fail closed. Installer receipts bind the
source commit, controller, adapters, backup plan and coverage to their hashes.
The preparation runner, readiness builder and final controller preflight all
verify this receipt. A patch merely present in a branch is not enough.

Before this PR is merged, next preparation must explicitly use its published
commit for operational tools; current staging alone does not contain this fix.
The post-cutover `next-preparation-tools.json` pointer records that published
pin and an isolated wiring proof. After review/merge, use the resulting staging
commit and verify the same receipt. Neither the receipt nor the wiring test
authorizes cutover or replaces a fresh release-specific rehearsal/drain/backup.

## Service-settings Finalization Prevention

The installer applies `VK_HANDOVER_FINALIZATION_20261004.patch` automatically
to the new known template. Inert installation creates the required boot-override
parent directory; preflight checks it; finalization creates it idempotently.
Do not enable an unowned candidate during preparation. If finalization fails
after a healthy, preserved candidate is already routed and the original
conversation resumed, validate and retain that owner before disrupting routing
or CU. The old owner stays frozen. If that health/identity proof fails, use the
established same-latest-data recovery procedure, never an older database.
The consumed October 4 package remains unchanged as historical evidence.

## Validation And Limits

October5 adds an unconditional check of every declared bounded recovery root:
it must exist, remain within protected scope, avoid symlinks and have a current
kernel watch even when the journal has no errors. Starting a new journal does
not turn a missing folder into an accepted baseline. When historical rename
pairing cannot be established, preserve the original journal/chain and recovery
limits, then make a complete new current-data checkpoint. Never reuse the old
incremental parent with a new journal identity. A real-journal regression proves
this path restores dirty files and original thread data, rejects old-parent reuse
and leaves historical errors and archives intact. Missing/unwatched/linked roots
remain fail-closed. All139 deployment regressions pass with these four additions.
This does not prove recovery of later unbacked edits.

The full October5 checkpoint also encountered a Codex launcher scratch directory
removed normally during bounded model verification. The package now permits only
the named launcher members under the exact protected Codex homes, with journal
deletion evidence and no remaining file or symlink. Workspaces, sessions, unknown
scratch members and frozen-boundary warnings remain fatal. An unpublished full
online archive can be finished without recopying source data only after its exact
plan, journal continuity, full archive stream, manifest and SQLite payload hashes
pass verification. Database reuse proofs are discarded; the next delta snapshots
them again. No production restore occurs.

Readiness now compares measured recopy work to the actual journal requirement.
A clean replacement journal needs a verified full current-data checkpoint rather
than a fabricated nonempty recopy list. New moved roots invalidate that workload
proof. These additions bring the focused suite to144 tests; package installation
binds and uses the updated tools before sealing, not an unintegrated source copy.

The expanded suite covers the original 77 backup regressions, closed SQLite
databases and committed WAL, full/delta archives, delivery resumption and
authenticated recopy. A real filesystem/inotify cross-parent move test captures
and restores the moved worktree, dirty agent work, thread history, source
tombstone and 0640 file mode. Sidecar/CLI integration and explicit rename,
unrelated removal, missing root, ambiguous source and symlink/alias rejection
are tested. Package tests cover missing boot directories, healthy-owner recovery,
tampered/linked tools, changed coverage and unknown/consumed templates.

All 135 deployment tests pass. `pnpm run format`, `pnpm run ops:check` and
`git diff --check` pass. A private copy of the actual October 4 package templates
also passes installation/verification without data copies or service calls.
No full frontend/Rust/Tauri suite, new model inference, physical-phone testing,
or live restart was performed for this tooling-only follow-up. Existing accepted
live checks are not relabelled as newly run tests.

## Completion Reconciliation

The old `preparation-completion.json` is an early preparation snapshot, not the
final deployment result. Preserve it and all sealed receipts. Current truth is
the accepted attempt's `status.json`/`live-acceptance.json`; the separate
`post-package/completion-reconciliation.json` binds the supporting artifacts.
The old report omitted supported evidence for backup_fix, handover_proof and
ready_record. They are now recorded against the final Desktop backup, 77 tests,
private handover/return rehearsal, sealed readiness/software restoration and
accepted original-thread continuation. No unverified rollback is claimed to
have happened live: private rehearsal proved recovery; production did not roll
back or restore a database.

One historical promise remains unproven: a 30-second interruption. Actual final
capture took 43.675 seconds and the public interruption, including finalization
repair, approximately 146 seconds. The revised capture budget was 150 seconds;
acceptance does not turn those measurements into a 30-second success. Future
timing claims must use measured whole preparation and interruption durations.
