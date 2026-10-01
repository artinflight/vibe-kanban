# AutoSwitch V2 Deployment Preparation

## Current State

PR130 merged into staging at 09:41:09Z on October1, commit
`adfa7c0512c0ceeb72cea0fbc6329f71504a93bf`. The tested PR head760310cd7 and merged
source tree are identical. Version remains0.1.42. Production still runs Green
PID2506054, ports5261/5262, from main dcd51cc12. CU2506120 is unchanged. Historical
Blue764264 remains frozen; replacement Blue uses a distinct new unit on5301/5302.
No new handover has occurred. Source promotion is not production activation.

The task package is `/mnt/vk-storage/vk-blue-autoswitch-v2-20261001`. Its source
worktree is detached at exact staging. Never build production from this older
maintenance branch or overwrite authoritative data from a test replica.

## Evidence

- Reused content-hashed PR130 evidence for the identical tree:374 backend tests,
  zero failures, six ignored, frontend typechecks/lint, selector tests and Clippy.
  The original PR's ten checks passed; no broader V1 inference suite was repeated.
- Fresh matching frontend/backend/guard builds pass. Frontend191.73seconds,
  backend541.87seconds. The runner's generated `.previous` directory caused a
  clean-tree rejection after compilation; it was moved outside source, then
  cached verification completed in7.56seconds without recompiling application code.
- Private original-thread resume, Turn Steer versus Stop, goal completion,
  attachment round-trip,12 saved messages and DB integrity pass.
- Desktop1440/mobile390 browser checks pass: saved messages, seven-model menu,
  reasoning controls and V2 Automatic minimum/Shadow/Manual controls.
- Three bounded real Shadow executions pass with the exact production launcher,
  account and Codex home. Mechanical work recommends Luna5.6/low; bounded work
  recommends experimental Sol6/low in Shadow only; protected work recommends
  Astra/high. Actual native rollouts retain the chosen Sol6/medium. One bounded
  semantic-classification call also occurred. This is not a measured savings claim.
- Actual current Green/new Blue binaries pass failed-backup recovery, verified
  rolling-boundary handover, latest-message/model/settings cutback to the original
  process and repeated recovery. Adapted rehearsal16.97seconds, including private
  Desktop backup delivery; this is not a production downtime guarantee.
- Read-only board audit:19 In Staging issues, no newly unreconciled heads beyond
  the previously documented semantic exceptions. Live inventory:40 projects,
  972tasks,994workspaces,1035sessions,12saved messages. The queue check took1.12s.
- Native-path inventory records6042 VK native threads and2282 historical missing
  paths. Those are retained exceptions, not newly repaired histories. Attachment
  hashes verified for335 present files; absent historical attachments remain explicit.

Read the task's JSON/logs for precise scope and hashes. The copied native-history
inventory across both homes has a different scope from the VK-only count above.

## Backup Corrections

The first full production-format checkpoint inventories74.88GB before compression.
This one-time checkpoint replaces neither production nor the prior recovery chain.
Subsequent captures use verified incremental parents. Desktop B is the destination;
all staging and isolated restores stay on mounted SSD storage.

The compressed checkpoint is20,606,299,148bytes, archive
`checkpoint--d5073c889c0b4930826e142ca9ee5be3.tar.zst`, delivered to
`desktop:B:/vk-backups/vk-blue-autoswitch-v2-20261001/`. Desktop verified its
full SHA256 as `c35f5d355147a84387243f14f80d97c277c56c8e4fd95598f341910084113119`.
Its recovery descriptor was separately delivered and checksum-verified. The full
isolated restore uses the byte-identical local archive plus the descriptor
downloaded from Desktop; it does not download a second20GB copy. Do not call this
a full archive download. The smaller private rehearsal did download its archives.
Full isolated restoration passed in1604.24seconds, including database integrity,
without materializing absolute links back into production. Its test copy remains
at `backups/isolated-production-restore` under the task root; it is generated
verification data, not authoritative production or the only backup.

Desktop's Tailscale route used a slow relay. The verified direct LAN connection
uses the same existing SSH host key, preserves strict checking, resumes only
large transfers and verifies the complete destination checksum. Neither transfer
resume nor the faster route substitutes for full-byte verification.

Production-scale discovery exposed three gaps not caught by small fixtures:

1. Resolving every exclusion for every file was needlessly expensive. The adapter
   binds equivalent normalized prefix checks and rejects changed exclusion links.
2. Codex removes temporary directories normally. A known DELETE_SELF followed by
   IGNORED is a deletion record when its parent remains watched, not unexplained
   coverage loss. Root deletion, unexplained watch loss and moves still fail closed.
3. An online archive can encounter CLI scratch files that disappear after inventory.
   Only missing paths below the exact native `tmp/arg0` root with matching journal
   deletion events may be reconciled. Other read errors remain failures. This does
   not weaken the final frozen-boundary archive, which still requires success and
   unchanged protected state through Desktop delivery.

Task-local adapters and regression tests are in the package. They are not changes
to the built application tree and require a separate source backfill before future
agents assume PR129 alone includes them. Preserve failed-attempt evidence and the
successful archive; do not repeat a full copy merely to hide an explainable warning.

Two further preparation findings are recorded, not hidden as cutover time:

- The transfer adapter initially used SFTP resume for a nonexistent incremental
  destination. It now creates new files and resumes existing partial files, rejects
  oversized destinations and still checks the entire destination hash. Delivery
  was resumed from the existing348MB archive, without recapturing live data.
- Bulk restoration inside the Codex execution's1.5GB memory-high limit repeatedly
  throttled file buffering despite ample host memory. The existing restore and
  delivery workers moved to `vk-v2-backup-verification-20261001.scope`, bounded at
  4GB high/6GB maximum, with reduced CPU/I/O weight. No native execution or live
  service moved. Future bulk preparation should start in a separately bounded
  job; raising or removing VK's normal agent limits is not the fix.

Formatting passed on the maintenance checkout using the candidate's existing
Prettier binary after the checkout-local formatter was absent. No dependencies
were installed and no unrelated source was changed. Ops and diff checks pass.

## Additional Writer Coordination

A15second read-only journal observation found continuous writes to
`/home/mcp/code/monitor-local/data/monitor-local.sqlite-wal`. Open-file inspection
attributes them to `monitor-local-preview.service`, PID1179. This is separate from
VK and CU; no process has been paused. The operator has been asked whether this
monitor may briefly pause for the final backup. The prepared controller requires
explicit coordination and exact process identity, rejects new child work, and
uses its established same-process pause/thaw and failure recovery path. Twenty
one focused controller/backup-adapter/coordination tests pass. Readiness remains false
without that decision; do not silently exclude the database or ignore its writes.

## Remaining Gates

The full checkpoint restore and first incremental delivery passed. Inactive
candidate/recovery/CU settings are installed, with Green2506054 and CU2506120
unchanged. Capacity configuration and runtime0.159.2/seven-model/shared-feed checks
pass. The first configuration check caught missing dual VK/CU dependencies and
automatically restored previous settings; the corrected established dependency
pattern then passed. The production candidate has never started.

The final package and measured incremental refresh are certified by the task's
`software-package-receipt.json`, `online-backup-result.json` and
`preparation-completion.json`; require their successful results, not this note
alone. Production promotion is awaiting clarification of the
older no-GitHub-Actions constraint: opening a normal PR automatically runs checks.
The monitoring pause also needs coordination. Do not claim promotion, readiness
or deployment until their receipts exist.

Before interruption, recheck active/queued work and native/background writers,
including default-home Codex and fitrdy-manager Git polling. Release ownership,
pause the original Green, verify the final Desktop-backed delta, then start new
Blue against the same latest data. Cutback thaws original Green and uses that same
latest data. Never restore an older database or create a replacement maintenance
conversation. Post-switch functional acceptance remains mandatory.

Timing starts at the actual request execution09:19:04.986Z. Merge wait22m04s is
separate from preparation, downtime and live acceptance. Include backup-tool
correction time and any operator-decision wait; do not reset the clock or quote
only the switch as total deployment time.
