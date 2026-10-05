# October 5 Authorized Cutover Preparation

## Authority And Current State

The current objective is to finish restart/cutover successfully with a fresh
instance. This supersedes the earlier recovery-only hold. Once the candidate is
ready, send "pause work" using active-turn steering to any active VK agents,
then verify their actual safe completion and an empty queue. Do not create a
competing follow-up writer, kill another agent or infer drain from a failed steer.
Production is still the October4 PID1369037 on5461 at this writing; no new switch
or old-database restore has occurred. The final package is
`/mnt/vk-storage/vk-green-cutover-20261005`.

## Release Evidence

PR145 merged staging8b562265d25a3f8ee6d4fa602144e71caddfbc85 into production
mainfa8122a50ca3e9dab799a29046f4bb359b2065ed. The source tree is
9dd2bd10a353d089f869626cb4634bee4975191e, identical to built/tested a661a8156.
The candidate server hash is
5e7948921f962b9ea74597781ca2e1b0c7bd745edc0d1901a8274dab444097a2.
All10 existing named CI checks passed; no workflow was manually dispatched.
Canonical main is updated. The19 In Staging issues have no new discrepancies;
retained historical exceptions are not silently declared merged.

The private current-data copy passes same-thread continuation, Turn Steer versus
Stop, native-goal fixture, attachment round-trip,12 saved messages and seven-model
controls with four reasoning choices at1440/390 widths. Opening a workspace clears
its unread state; polling/background views preserve it. The packaged module
pointer was republished into the new package, and the actual backend reports
`routing_module:staging-a661a8156-20261005` without a fallback warning. The
readiness/package must include its immutable files and recoverable pointer,
not just a service environment setting.

CLI0.159.2 uses the same launcher/account/home as production. Fresh bounded model
checks required10 calls: seven initial checks, one retry after an explicit Terra
capacity rejection, and two low-effort pairs. All passed. No broader V1 suite was
repeated. VK/CU must retain the same private telemetry feed.

## Backup Protection

Five recovered roots and three repaired Git registrations retain the independent
3366-entry/3052-file recovery proof. Later unbacked edits remain unaccounted;
exact deletion timing and CU causality are not established. The old journal
errors, original backup chain and scoped recovery archive remain intact.

The legacy journal cannot establish historical rename pairing. A separate
read-only journal with the same complete backup scope now watches current data;
all14 bounded protected roots must exist and have covering kernel watches even
when its error list is empty. No old incremental parent may cross journal
identity. The complete new checkpoint is staged under
`/mnt/vk-storage/vk-green-reprepare-20261005/backups` and delivered to
`desktop:B:/vk-backups/vk-green-reprepare-20261005/`.

The full online archive encountered normal deletion of a named Codex launcher
scratch directory during bounded model checks. The published correction permits
only known scratch members under exact protected Codex homes, with journal
deletion evidence and no remaining file or symlink. Missing workspaces, sessions,
unknown files and frozen-boundary warnings still fail closed. The archive is
stream-verified against its manifest and SQLite hashes before delivery is resumed;
database reuse proofs are discarded so the next delta snapshots all DBs again.
This is not a production restore or permission to erase historical journal gaps.

## Operational Integration

Draft PR142, `fix/vk-backup-move-preflight`, contains the durable tools.
Published3f15a4796 is installed and hash-bound in the new package;6483d394b also
corrects the stale readiness interlock reference before sealing and records the
prior receipt. Published528282d00 additionally protects module payload/pointer
recovery and checks the actual candidate module identity. All146 deployment
regressions and80 package operational tests pass.
The consumed October4 package and finalization fault evidence remain unchanged.
Next preparation must explicitly load these published tools until integrated into
staging; an old staging-only tool copy is insufficient. The next preparation pin
is528282d00 or a verified descendant of `fix/vk-backup-move-preflight` until PR142
is integrated. Verify the package receipt and module patch proof, not just branch
presence. October4's boot-directory finalization prevention remains required.

Full checkpoint b8b117feb1db474f9481096447b762c1 and delta60210d02fd8349a388db57cbd7265f82
are Desktop-SHA256-verified. The archive stream and67 SQLite payloads were verified;
targeted extraction verifies all3366 restored entries. This does not claim a new
full extraction of every source file. The exact current-binary handover rehearsal
passed all four cases and Desktop restoration in113.386 seconds. Its generated
copies were retired only after consumer checks and archive verification.
The newly registered minspend repository is added to the whole-tree supplemental
capture, leaving the original checkpoint plan and historical journal unchanged.

The current preparation also verified and removed only18 completed private
rehearsal copies, freeing29,130,399,744 bytes. Six backing archives were freshly
SHA256-checked locally and on Desktop; process/service consumers were checked.
No user worktree, source, production data, attachment or archive was deleted.

## Remaining Before Switch

Require sealed Desktop software recovery, current installed-but-inactive settings,
preflight and a fresh review-state snapshot before consuming the controller.
The preliminary snapshot protects13711 turn flags and is SHA256-verified on
Desktop. Refresh immediately before interruption. Do not replace current flags
or model choices with an older snapshot. Drain agents with the supported steering
path only once preparation is ready. Execute one independent controller attempt,
then resume this original conversation for live acceptance. Rollback uses the
same latest data. Never call preparation or Git promotion a successful cutover.
