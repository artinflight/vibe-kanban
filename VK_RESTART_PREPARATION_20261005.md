# October 5 Restart Preparation

## Current State

The latest owner handoff holds restart, cutover and CU resumption. It authorizes
recovery verification and Git-registration reconciliation only, superseding the
earlier conditional cutover instruction. No October 5 restart, ownership release, freeze, routing
change, production database restore, or production settings installation has
occurred. The current production process is1369037 on5461, with the previous
3059021 process still frozen. Do not interpret the isolated preview as production.

Preparation began at12:30:20UTC. Evidence and the fresh unconsumed package are in
`/mnt/vk-storage/vk-green-prepare-20261005`. Read `preparation-status.json` and
`backup-blocker.json` there before proceeding. **Cutover is not ready.**

## Recovery Verified; Backup Readiness Still Blocked

Recovery finished at13:23:38UTC. Staging independently verifies all3366 entries
and3052 regular files against the October4 19:48:19UTC manifest, before and after
repairing Git registrations. File hashes, modes and symlink targets match.
Evidence is in `/mnt/vk-storage/five-root-recovery-20261005`:
`staging-file-verification-before.json`, `staging-file-verification-after.json`,
`git-admin-archive-evidence.json`, `git-registration-repair.json` and
`backup-coverage-recheck.json`. The recovery agent's six-archive evidence remains
intact; Staging additionally checks the full SHA256 of the three archives used
for administrative recovery.

Three missing administrative directories are restored with atomic no-replace
placement. Recovered `.git` pointers already name the correct destination and
are not changed. No checkout, reset, branch recreation or branch movement occurs.
All indexed objects exist and Git status/worktree registration succeeds:

| Recovered worktree | Registered branch | Preserved HEAD |
| --- | --- | --- |
| `0752-fr-v5-generation/hyroxready-app` | `vk/0752-v5-generation-ef` | `47a999dbf` |
| `5f8f-cf-horns/carfind` | `vk/5f8f-cf-horns` | `e217675cb` |
| `carfind-four-module-donors` | `staging` | `978a8ef49` |

All shared refs remain unchanged, including newer independently held HYROX work.
Each recovered index reports a clean working tree; that establishes agreement
with recovered state, not proof that later unbacked work never existed.

The scoped repair archive `five-root-repaired-20261005.tar.zst` and its receipt
are verified on Desktop `B:/vk-backups/five-root-recovery-20261005`. It contains
the recovered roots, restored registrations and evidence; all3411 protected
archive entries pass streaming content/mode/link verification. Its SHA256 is
`746f5a3c2f2bf9c2568a37287bec0f64e4824709937dd36a2151e51280981823`.
**This is not a full production backup or cutover-boundary backup.**

All12 recopy roots now exist. The authenticated backup adapter still rejects
`Move needs an explicit source or unique matching source evidence`. Diagnostic
evaluation identifies seven older unmapped rename cases: two organic-video
renames, two pytest-cache renames, the personal daemon staging rename and two
personal plugin temporary-directory renames. The three administrative repair
moves additionally need explicit bounded coverage. Possible source names in
aggregated masks are not proof of their pairing or timing. No guessed mapping,
dropped root, journal reset or rewritten parent chain is used to pass the check.
The preserved raw journal has13763 error records at sequence1309030;11083 are
unique (10970 removed watches,98 failed watches and15 moved directories).
These are retained findings, not a claim that each error remains unreconcilable.
Verification stops at the first unresolved guard, before a new production backup
is published. All30 operational package bindings still verify.

All135 operational tests pass from the checked-in pinned source in13.383seconds,
including closed-database, committed-WAL, cross-parent moves, preserved tombstones
and fail-closed cases. Two initial test invocations were invalid: a nonexistent
temporary directory, then package-installer tests outside a Git source checkout.
The successful run uses the mounted SSD temporary directory and operational source.
No tool guard is weakened. Production health reports OK with the same PID1369037;
dot remains2937772 and the previous process3059021 remains frozen. CU settings and
resumption state are not changed by this task.
The earlier package recorder now refuses to run while `restart_hold` is set;
its refusal is tested before any status write, preventing it from replacing the
reconciliation with obsolete conditional-authorization or missing-root claims.

Later unbacked edits remain unaccounted. The journal has deletion records but no
per-deletion timestamps; exact deletion time and CU causality are not established.
Preserve these limits and all historical recovery exceptions in future readiness.

## Original Missing-Root Finding (Before Recovery)

Five explicitly protected recopy roots were present in the verified October4
19:48 backup inventory but are now absent. Their journal events since that
backup include directory deletion, self-deletion and watch removal (`0x40008600`).
No relocation destination or authorization for these deletions was established.
This preparation did not delete or move them.

| Root below `/mnt/vk-storage/worktrees/` | Prior inventory entries |
| --- | ---: |
| `0752-fr-v5-generation` | 1527 |
| `5f8f-cf-horns/carfind` | 844 |
| `carfind-four-module-donors` | 842 |
| `hyroxready-app/codex-content-first-pilot/docs/organic-content/videos` | 23 |
| `organic-content-assets/opNVLP/assets/organic-content/videos` | 130 |

The backup adapter correctly refuses an absent covering watch/root. Do not drop
these roots, clear journal errors, reset the journal/backup chain to hide the
gap, or invent a historical exception. Establish what happened and reconcile
the missing work before certifying readiness. An async question about an
authorized cleanup/relocation remains unanswered; subsequent conditional
cutover permission does not establish that deletion was intentional.

The prior chain remains intact. Latest archive `c37409afa0154405a5d3a04bf4c7b68b`
was freshly checked against SHA256
`bfe4edd6efcfa0e6cd2f833b87d55912dd30f966fb6931eb9abc978c7fc45d6e` locally;
its prior Desktop verification receipt is retained. This is not a claim that
every missing file is in that single incremental archive or that subsequent
uncommitted work has been recovered. Preserve the entire parent chain.

## Prepared And Tested

The replacement is built from `a661a81568f382dfaa130f1dd2397e62b59e1f6a`, including
PR143 and PR144. Promotion PR145 targets main from staging. Its initial
branch-freshness failure was resolved using the PR branch-update operation:
staging is now `8b562265d25a3f8ee6d4fa602144e71caddfbc85`, with an identical tree
to the tested build. Canonical staging was fast-forwarded. Main is unchanged;
PR145 is not merged.

- Release build, repository formatting and ops governance pass.
- 55 focused routing regressions pass; the opt-in real-worker acceptance passes
  code/prompt/settings reload, pinned in-flight settings, last-good fallbacks,
  protected risk, rollback and unchanged dirty state without native inference.
- 135 operational regressions pass, including closed SQLite, committed WAL and
  cross-parent move evidence. An initial invocation lacked required `TMPDIR`;
  the successful run used the mounted SSD temporary directory.
- Published operational source `c6ebf6131` from draft PR142 is actually installed
  in this package. All30 bound files verify, including the service-finalization
  prevention patch. This is tool integration, not backup-readiness evidence.
- All14 package controller tests pass. The prepared companion override now
  explicitly names both current/replacement services and uses a last-sorting
  override path; stale older drop-ins must not override those dependencies.
  No production drop-in has been installed.
- An isolated candidate runs as `vk-green-preview-20261005.service` on5521 using
  copied application state, a private offline provider and no production data
  or credential mounts. Continuation, Steer versus Stop, native-goal fixture,
  attachment round-trip and12 saved messages pass.
- Browser checks at1440px and390px pass seven models and four reasoning levels
  without page errors. These are isolated desktop/mobile-sized checks, not
  physical-phone or production cutover acceptance.
- The initial module and matched validator are published only under this new
  package's `autoswitch-module`. Its manifest hash is
  `e2479a4e6b75eb35e311c5d468c0a95f64f676eb3bce2d8f56c6fb39684c0317`.
- A fresh review snapshot preserves13702 turn flags and verifies on Desktop.
  No review flags, saved messages, models or live UI preferences were changed.
- A read-only scan found1054 queues empty and only the maintenance execution
  active. This is not reusable final-drain evidence.

## Remaining Work

First resolve move-source evidence in a fresh authenticated coverage revision,
including the proven repair sources, without weakening unresolved-history guards.
If historical source pairing cannot be proved, establish a separately authenticated
complete current-data checkpoint while retaining the old journal/chain and explicitly
recording the recovery limits; do not manufacture proof by resetting history.
Then finish current complete backup coverage, exact-candidate latest-data rollback rehearsal, promotion,
inert service installation, package sealing and Desktop software restore proof.
Refresh model availability only if the24-hour proof expires or the exact
launcher/account/home changes. Runtime remains0.159.2 with the shared private
VK/CU feed. Fresh review/drain/writer/runtime checks are required immediately
before any subsequently approved switch. The restart hold remains in force.
PR145 is still unmerged; its current CI checks pass. Preserve the original maintenance
conversation and all historical recovery exceptions. Never restore an older
database over production. No new interruption estimate is certified yet.
