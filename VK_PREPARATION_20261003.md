# October 3 Restart Preparation And SSD Cleanup

The operator requested preparation, then SSD cleanup. No restart, routing change,
production freeze or final handover is authorized or performed in this task.
The current version remains Green PID3059021 on5411. The updated version is an
isolated candidate on5471; production Blue5461 is installed but inactive.

## Source And Validation

PR140 integrates staging67b11e8fa with the already-live attention fixes from
PR138 and the additive review-journal migration. PR141 promotes the resulting
staging86d1c083a into maine53ae4a7e. The built9c2e04d72 candidate and both branch
heads have identical tree6963ed5d5dc174e1f40a84e71e8975cd82c716cc. Canonical main
and staging checkouts are current. Runtime remains VK0.1.42 and Codex0.159.2.

Evidence root: `/mnt/vk-storage/vk-blue-prepare-20261003`.
The release-identity record binds the actual running candidate binary, frontend,
source tree and CI. Local release builds, frontend types/lint,48 routing tests
(one ignored),14 DB tests,77 backup-tool tests and52 operational/review tests pass.
Ten integration CI checks and promotion checks pass. Initial invocation mistakes
(nonexistent web-core lint script and unset test TMPDIR) were corrected; their
failed logs are not success evidence. Integration did not omit the live frontend.

Private functional checks cover original native-thread continuation, Steer versus
Stop, native-goal fixture, attachments, scope correction,12 saved messages, seven
models and all four reasoning levels.1440/390 browser tests also verify opening
clears attention and background/polling preserves new flags. These are isolated,
offline-provider and emulated-mobile tests, not post-cutover live acceptance.
The19 current In Staging issues have no new discrepancy against the retained
September30 audit; unchanged historical source/recovery exceptions remain explicit.

Bounded model qualification was refreshed October3 using the production launcher,
account and Codex home, with nine calls. Prospective production settings verify
CLI0.159.2 and the same private VK/CU telemetry path. Reprobe only if older than
24hours or that identity changes. Existing CU software and its newer Android page
are preserved, not replaced by an older package.

## Backup And Recovery

The fresh rolling backup is SHA256-verified on Desktop B:. Newly registered
carConsole is covered by a separate verified whole-tree supplement. Both restore
descriptors are required. Catch up both online before a later approved cutover;
the supplement fails closed if current content differs. Moved plugin/pytest/video
subtrees use explicit whole-subtree recopy and independent before/after hashing;
unknown errors, overflow and unverified coverage still block.

A semantic review snapshot was verified on Desktop before preparation. The new
controller takes another online snapshot before interruption, uses the verified
frozen backup for boundary comparison, and checks journal-explained changes and
unchanged post-activation flags. It does not restore historical review flags.
The existing iOS activity correction and historical missing-rollout exceptions
remain in current data. No old database is copied over production.

The real old/new binary rehearsal preserves writes, model choices and settings
through same-process rollback. The current-sized rehearsal took49.31seconds,
including49.15seconds for capture/fencing. Allow about a minute, up to two, not a
guaranteed30seconds; capture ceiling90seconds. This proof covers the original
retained process. Cold-start rollback with the older binary after the new migration
is not certified. Do not delete migration records or replace current data to make
an old binary start. Keep the original process for the normal latest-data cutback.

## SSD Cleanup

The SSD began below1GiB free. Cleanup retired eight generated database extraction
directories and a completed, inactive full restore-test copy (78.8GB logical).
Before deletion, local and Desktop full-archive SHA256 matched, processes and
service references were checked, and the extraction had no post-test changes.
The source archive and all chain receipts remain locally and on Desktop. Six
generated directories from this task's completed scale test were also retired.
Exact inventories, hashes and regeneration notes remain in the evidence root.

All production databases, native sessions, source/worktrees, uploads, required
attachment roots and shared build cache remain. A real production attachment
upload/retrieval passed afterward; only that new test attachment was deleted.
Protected directory ownership/modes are unchanged, and production error-priority
logs were empty during preparation. Roughly80GiB was free after cleanup and tests;
use the final disk record for the post-package measurement.

## Approval Boundary

Read the evidence root's `readiness.json`, `software-package-receipt.json` and
`PROGRESS.md` together. Readiness is valid only if the software receipt matches
the exact readiness hash. Production remains usable; no other agent must stop
for ordinary preparation. Later approval must explicitly authorize the short
handover, including the established monitoring-writer pause, and bind fresh
process/queue identities and the latest capture. No cutover-request/approval or
attempt file exists during preparation. Never reuse an older consumed controller.

Maintenance session75bc68d4-aa55-4914-a695-f20c46a13e4c/native thread
01a03e74-2c1a-72f0-9e00-8e4293fe910d must continue after activation. Complete actual
live acceptance before claiming deployment success. Source promotion is not a
live deployment. Use plain language: current version versus updated version.
