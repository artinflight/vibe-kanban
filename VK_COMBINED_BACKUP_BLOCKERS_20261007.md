# Combined Backup: Measured Capture, Not Readiness

## Current Result

Production was not paused or restarted. The full online capture completed archive
creation but failed closed before Desktop publication. It is not a usable new
backup head. All original B chains and retained recovery exceptions remain intact.
No archive was deleted in this task. The earlier specifically approved27-file
retirement is complete and must not be repeated.

Preparation root: `/mnt/vk-storage/vk-combined-preparation-20261007`.
`backup-plan.json` covers66 roots and requires the current69 databases, including
the connector receipt ledger; the payload manifest contains69 fresh snapshots.
All14 protected root identities are guarded. The new full-baseline journal does
not erase the old45-error journal,31 outside-root moves, or unknown later edits.

`capture-space.json` records878.144seconds, initial79,308,926,976 free bytes,
minimum52,712,136,704, observed host consumption26,596,790,272 and a4GiB floor.
This is whole-host observed consumption, not an exclusive job allocation figure.
No space-floor stop occurred. Archive bytes23,441,521,918; no full restore or
handover was run. Latest audit free52,679,131,136 bytes (about49.06GiB).

## Exact Unresolved Warnings

Capture used immutable312ac0b20 tools. It first rejected the present Codex updater
Unix socket. Published PR149 successor6db1a43e1 recognizes only that exact owned,
non-symlink socket under the scoped Codex homes. Unknown or substituted paths
still fail.194 operational regressions pass, including7 focused recovery tests.

The new tool package was then verified and used to re-evaluate the retained
warnings read-only. It still rejects the missing shell snapshot:

`/home/mcp/.local/share/vibe-kanban-green-codex-home/shell_snapshots/01a1181d-8887-7962-bb8c-597d70cbfaf4.1791408487176536081.sh`

The corresponding `thread-writer-locks/01a1181d-8887-7962-bb8c-597d70cbfaf4.lock`
also disappeared. Both have journal deletion evidence, but deletion observation
alone is not proof that recovery may omit them. Do not broaden exemptions or
silently drop protected shell snapshots. The launcher tmp/arg0 warnings have the
existing narrow ephemeral classifier; unrelated missing files remain fail-closed.
`blocked-preparation.json`, `journal-after-capture.json`, the complete tar log and
unpublished archive retain exact evidence. No warning was edited or suppressed.

Next backup action is to establish the two paths' lifecycle and recovery needs,
then use strict verified unpublished-capture recovery only if its guards pass;
otherwise obtain a fresh complete capture under an appropriate quiet boundary.
Do not promote this archive by manually constructing a successful descriptor.

## Durable Tools And Adoption

Operational branch `fix/vk-desktop-backed-recovery` is pushed at
`6db1a43e1bc10e991c5a9bfd27f3400166ec6594` in PR149. New package:
`/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-6db1a43e1`.
All70 bound files,27 retained descriptors and six head references verify.
Original sealed312 package remains untouched. This is a verified successor,
not an in-place reseal or a claim that a deployment controller has adopted it.

Desktop retained package:
`B:/vk-backups/vk-desktop-provider-20261007/desktop-provider-recovery-6db1a43e1.tar.gz`,
4,976,307bytes, full SHA256
`90fc02c2706b01c56a3e2325f480e81538032c326574a80573ed9451d53187ac`.
Local `recovery-package-6db1a43e1-desktop.json` binds the transfer verification.
Future preparation must bind this successor (or a reviewed newer revision) into a
NEW controller package; the failed capture's recorded312 provenance stays true.
B remains sole retained archive provider; no SSD-parent duplication is required.

## Release Gates

Draft PR150 preserves combined source2bc909d63 with PR1479b3f82538,
PR148cb0b441a2 and compatible CU95e7aea47. Hosted bundle hashes match all tracked
inputs and five artifacts. Candidate SHA8926cd97ed757ba7607f1b4f41d862a0638198db927ed720bc2a9032defd774b;
latest-v2 fallback SHAee297e7f1b93c8557410f238d9ee5c9239f8a04ade9e3aa6d29128a3432f824b.
Both are blocked by the historical replay defect documented separately. CI also
fails two Clippy errors and three HTTP fixture setup checks (missing explicit
isolation root); the locally guarded HTTP tests pass. Do not remove isolation.
The bundle embeds placeholder frontend assets: it is NOT a deployable standalone
UI. Frontend input identity matches the accepted real PR147 frontend, but final
packaging and combined serving acceptance have not been completed.

Still required: developer compatibility/lint repair; final combined CU/HTTP/native
acceptance; accepted full B-backed backup; measured appropriate restore and
latest-data fallback rehearsal; final frontend/module/runtime bindings; promotion;
actual user/agent/queue/CU-grant safe-use checks and one authorized cutover.
No idle claim is made from chat silence. No agent was interrupted. Recommend,
scheduling ON, credits OFF and root's ownership of real receipt reconciliation
remain unchanged. No additional user approval is requested for the existing
conditional cutover authority.

## Validation Limits

Independent31 Rust tests and server compile pass;94 connector tests pass.
Both original and formatted private historical harnesses reproduce4/4 rejected
logs without production DB access. Operational194 regressions and ops governance
pass. Owner `pnpm run format` passes Rust formatting then stops at missing
frontend Prettier; the sparse operational checkout's format command stops at its
absent capacity-guard crate. These are reported limits, not full format passes.
