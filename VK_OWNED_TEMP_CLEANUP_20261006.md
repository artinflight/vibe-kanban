# October 6 Staging-Owned Temporary Cleanup

## October 7 Scoped Cleanup Completed

The operator's fresh instruction supersedes the broad visibility hold below for
these exact October5 disposable copies, not for arbitrary cleanup. All1966
allowlisted files were removed: **4,434,825,216 allocated bytes (4.13GiB)**.
Immediately before/after the removal sequence, available SSD bytes were
251,891,712 / 4,685,647,872. Concurrent writes explain the small difference
between free-space gain and allocation removed. Mounted `/dev/sdb1` remains ext4.

The original `plan.json` and `cleanup.py` are unchanged. The plan is explicitly
classified as a cleanup inventory, not a service/backup dependency. Separate
`scoped_cleanup_20261007.py` and `october7/` receipts under the original receipt
root record the narrower assessment, dry runs, six passing exact-file tests,
per-group process/dependency checks and every unlink. The manifest is consumed;
do not replay either cleanup script against it.

Each file's inode/device/mode/mtime/size/hash and single-link status matched the
fixed inventory. All archive-member/duplicate hashes passed before removal, and
all four retained original archives passed full hashes again afterward. Both
private rehearsal services are absent. No accessible application, service or
current package dependency referenced a proposed copy. The inventory's own
reference is retained as evidence, not mistaken for a runtime dependency.
The empty systemd `inaccessible/reg` node is a mount mask, not configuration.

No protected process fields were read and no privilege escalation was attempted.
Kernel/platform daemons, login PAM and the key agent have no identified role in
these unencrypted, completed private-test copies; this is scoped provenance
reasoning, not universal descriptor visibility. Opaque SFTP workers were treated
as potentially relevant: cleanup waited for their exit and required a clear
transfer window before each group. No transfer or service was interrupted.

### Retained Recovery Copies

All original archives remain at their existing local paths, with descriptors and
parent references unchanged. Full Desktop SHA256 checks passed for:

- Software `maintenance-software-20261005T152949Z.tar.zst` at
  `B:/vk-backups/vk-green-cutover-20261005/` (SHA256 `9a4c2fe1...`).
- Rehearsal checkpoint `checkpoint--06974570ead1459398e7a1d9039cc7fa.tar.zst`
  and successful delta `delta--eb05467dae284fc296dafae562fd12b4.tar.zst` at
  `B:/vk-backups/vk-autoswitch-scope-release-20261001/scale-rehearsal/`
  (SHA256 `4b9620fb...` and `3105a1da...`).
- Failed private rehearsal `delta--16a548f9d222439bbd2628660b163e9b.tar.zst`,
  newly copied to
  `B:/vk-backups/vk-staging-owned-cleanup-20261007/preserved-failed-rehearsal/`
  (SHA256 `a20e64da...`). This is preservation of a test artifact, not publication
  of the failed boundary as a valid production backup.

`october7/desktop.json` records full hashes, lengths and exact destinations.
`october7/RECOVERY.md` explains retrieval and isolated reproduction. No Desktop
UI was used. All directories, excluded hardlinked launchers, original archives,
chain descriptors, incident records, source/workspaces and current/fallback
release inputs remain. No27-archive retirement or shared Rust cleanup occurred.

### Validation And Remaining Capacity

Live3027197, paused fallback1369037, CU414400 and dot3109784 retain their process
and freezer states. Protected roots retain identity/ownership/mode; route,
release/readiness/recovery and final9b3f82538 candidate/review-packet hashes match
the fresh baseline. A live59-byte attachment upload/retrieval passed and was
retained; the frozen fallback was not thawed for a smoke test. Scoped logs show
no new FileError, missing-path, upload-failure or HTTP500 matches. No restart,
new deployment, scheduling/credit change or old-data restoration occurred.

`pnpm run format` ran Rust formatting, then failed because frontend `prettier`
is not installed. It left no source changes; no dependency installation was
attempted on the nearly full SSD. Six cleanup guard tests and Python syntax
checks passed. These are cleanup checks, not another feature-acceptance suite.

About4.36GiB is now free, still insufficient for the unchanged full rehearsal.
`october7/capacity-review.json` uses all67 database paths, about2.534GB at this
check. Runtime plus one snapshot already needs5.069GB. Source inspection finds
eight database-copy sets plus archives/downloads, approximately22.09GB before
other files and fresh production backup. This is an estimate, not a measured
new peak. Earlier six-database/seven-copy calculations are explicitly superseded.

The smallest change that leaves recovery logic intact is separate mounted Linux
scratch capacity for rehearsal: budget roughly25GiB, then enforce a fresh
full-scope capacity check including production backup. Desktop B has about303GB
free for archives, but its Windows filesystem is not an already validated Linux
rehearsal volume. Alternatively, a separately reviewed scratch-retention change
could release redundant verified test copies between phases; it must preserve
the full workload and all existing assertions and prove its peak before use.
No such change or volume setup was performed. Larger local chain archives remain
blocked on their real local-path restore dependencies, not merely process access.

## Historical October 6 Assessment

The sections below record the earlier held state, superseded only by the scoped
October7 completion above. Preserve their original evidence and limitations.

## Scope And Outcome

Seamus authorized removal of verified disposable outputs owned by VK::Staging
from the successful October5 restart. This does not authorize another restart,
deployment, cleanup of workspaces or removal of current overnight candidates.
**Deletion is held: 0 bytes reclaimed by this task.** Reproducibility is verified
for 4,434,825,216 allocated bytes (4.13 GiB), but the final process visibility
check still lacks protected-process visibility. The SFTP PIDs have now exited;
this does not resolve the other visibility gaps.

Do not confuse free-space changes caused by the concurrent OP::DiskSpace task
with this task's result. OP owns exactly86 approved duplicate restore-test DB
files under `vk-green-refresh-20260930` and read-only verification of27 archives.
Neither that deletion scope nor those27 archives was modified here. The shared
Rust target, all worktrees and PR147's pending hosted-build/candidate/fallback
artifacts are excluded. October5 remains the live release; today's feature is
not deployed.

## Exact Candidate Manifest And Reproduction

Receipt root: `/mnt/vk-storage/vk-staging-owned-cleanup-20261006`.
`plan.json` records every proposed file, inode, mode, size, timestamp, allocated
bytes and SHA256; `cleanup.py` supports separate plan/apply and rejects changed
files, symlinks, unexpected hardlinks and discovered references. Apply has NOT
been run. Do not weaken its process-visibility gate to make cleanup proceed.

All candidates are under `/mnt/vk-storage/vk-green-cutover-20261005`:

| Candidate | Proposed allocated bytes | Reproducibility proof |
| --- | ---: | --- |
| `software-restore-1791214251531068499` selected1894 files | 1,242,669,056 | 1893 extracted regular files match the retained maintenance-software archive members; downloaded archive matches original SHA256 `9a4c2fe1f7c7d7c13e8baed5089d29a28c90b05318a1af3e1ca1b3da86b32bae`. |
| `scale-resume-rehearsal/handover-67b5fe17a79a4cebb8c14218944c767b/backups/delta-/16a548f9d222439bbd2628660b163e9b/payload` | 2,465,234,944 | All70 regular files match retained archive members; archive SHA256 `a20e64da535aa4fc891b1114472668592441263484881d5b7d13dac983a8b31e`. |
| Same rehearsal's `desktop-archives/checkpoint--06974570ead1459398e7a1d9039cc7fa.tar.zst` | 363,515,904 | Byte-identical to retained original in rehearsal `backups/checkpoint-`; SHA256 `4b9620fb2b37df65ee2c7e24e7472da20b121def70dc12006714183bc4ee7cca`. |
| Same rehearsal's `desktop-archives/delta--eb05467dae284fc296dafae562fd12b4.tar.zst` | 363,405,312 | Byte-identical to retained original in rehearsal `backups/delta-`; SHA256 `3105a1da5a27f127296b006267b56596535705e9bcc4b7f80262afb76998818e`. |

Retain all original archives, result/proof JSON, scripts, journals and directory
roots. The two8790-byte hardlinked extracted Codex launcher files are excluded.
The attachment-name search found only an extracted `find_attachments.py` script,
not an upload store. No attachment file or root is proposed for deletion.

## Fresh Reference Checks And Blocker

The guard examined accessible `/proc` working directories, executables, roots,
descriptors, mapped inodes, command/environment path references and mount tables.
It also checked unit/config references and top-level VK package dependency
plans/manifests. No candidate references were found in those readable sources.
Both exact October5 rehearsal units are inactive with MainPID0.

However, kernel permissions deny descriptor/mapping inspection of same-user
`gpg-agent` PID19071. SSH/SFTP PIDs2324526/2324527, previously active at19:10UTC,
were absent at the later combined-acceptance check. No transfer was interrupted.
Fresh reads of PID19071's cwd/exe/maps remain denied. Privileged system
processes and the login PAM helper also have reported visibility limits.
`sudo -n` and `sudo -n -l` require a password. No new privilege was acquired and
no process was stopped. This is missing evidence, not a claim of an actual path
conflict.

The parent/OP owner was asked for a **privileged read-only open-file/mapping check**
of the exact manifest paths, including aliases/inodes, or equivalent independently
verified evidence excluding those consumers. Existing deletion authorization is
sufficient; what is missing is the reference evidence or authorized read-only
inspection capability. Do not request passwords in chat, kill the SFTP session,
or infer inactivity solely from archive equality. Recheck just before each
approved group and skip if a writer/reference or changed file appears.

## Preservation And Capacity Receipts

`before.json` and `unchanged.json` verify unchanged live and fallback service PIDs,
freezer states, live binary/frontend hashes, route, operational-package/readiness
and recovery receipts. Protected attachment/data/session/recovery/pending-candidate
directory identities, ownership and permissions remain unchanged.

- Initial SSD free bytes from `df`: 66,101,248.
- Protected baseline after concurrent OP cleanup: 5,362,028,544 free bytes.
- Read-only final check at approximately19:16UTC: 5,361,901,568 free bytes.
- This task's removed file count and reclaimed bytes: **0 / 0**.

Mounted SSD and root/inode capacity were checked. Current VK3027197 and CU414400
remain active; fallback1369037 remains frozen; dot3109784 remains active.
No upload smoke was performed because deletion did not occur; no production
mutation or functional acceptance is claimed. After any actual deletion, run the
bounded upload/retrieval check and inspect logs as required by the disk runbook.

## Largest Retained Owned Areas

- `vk-green-reprepare-20261005/backups`: 25,094,610,944 bytes. Original checkpoint
  and delta chain; protected, not approved temporary cleanup.
- Current rehearsal tree: 4,283,969,536 bytes, including the selected2.47GB payload
  and727MB duplicate downloads. Retain its original archives and evidence.
- Software restore tree: 1,243,037,696 bytes, principally the selected files above.
- `current-checkpoint-restoration`: 436,170,752 bytes. Restored five-root incident
  evidence is deliberately excluded, even though it has a source archive.
- Current package `runtime`: 422,264,832 bytes; earlier prepare runtime421,105,664
  bytes. Mixed copied state/attachments/session/test evidence; not blanket-pruned.

Removing protected backup/recovery/state areas would need a separate explicit
retention decision and dependency/restore proof. The user has not granted that
scope, and no amount of headroom is promised from it. No Desktop file was removed.

## Later Acceptance Handoff

OP reports its86 approved duplicate database files removed, reclaiming5.109GiB,
and27 original archives checksum-verified both locally and on Desktop. Those
archives still have local-parent backup-code dependencies; verification alone
does not authorize retirement. They remain outside this cleanup allowlist.
Combined acceptance proceeded independently in small synthetic SSD fixtures.
Its dated `combined-acceptance.json` records later available bytes and unchanged
production identity. All new receipts and pending candidate/fallback artifacts
remain protected. This task still reclaimed **0 bytes**. No privileged approval
tool was offered by this runtime; the exact outstanding request remains a
read-only alias/inode/open/mapped/dependency check against `plan.json` for the
processes the guard cannot inspect. Do not bypass permissions or request secrets.
