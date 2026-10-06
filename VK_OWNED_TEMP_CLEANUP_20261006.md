# October 6 Staging-Owned Temporary Cleanup

## Scope And Outcome

Seamus authorized removal of verified disposable outputs owned by VK::Staging
from the successful October5 restart. This does not authorize another restart,
deployment, cleanup of workspaces or removal of current overnight candidates.
**Deletion is held: 0 bytes reclaimed by this task.** Reproducibility is verified
for 4,434,825,216 allocated bytes (4.13 GiB), but the final process visibility
check cannot rule out use by a currently active SFTP process.

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
`gpg-agent` PID19071 and current SSH/SFTP PIDs2324526/2324527. The SFTP transfer
started October6 19:10:28UTC; it must not be interrupted. Privileged system
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
