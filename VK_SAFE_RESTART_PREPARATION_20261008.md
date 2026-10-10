# Safe restart release preparation — October 8, 2026

Seamus now authorizes safe restart/cutover after the stated safety gates.
This supersedes prior operational holds, but does not accept data loss, erase
exceptions or waive current-state backup, restore rehearsal, fencing or acceptance.

## Bound inputs and preserved baseline

The baseline is current staging 5a887abf8bbedfbfb01ce7f8898fed07102fa1e3.
It includes the separately accepted phone UI deployed at 17:41 UTC, which must
survive this backend release. New inputs are exactly:
- PR150 5ec5722455d9b12ae8a9b00b371351ad12a685ef, including PR147/148 prerequisites.
- PR153 131badc892e62e3951512348dd08c7c3def3abab.
- PR223 cc203a035d24253814ac75c69b5874e2e390afcd.
- PR225 3a74df6d1e7f84c66fdef332b13e0ca722f7499d.

No new unrelated feature branch is included. PR138 is already in the baseline.
The only application merge conflict is startup metadata: keep PR153's strict
parser and runtime identity gate, add an exact single-argument capacity metadata
alias, and retain PR150's variant/ledger contract. Extra/unknown arguments remain
rejected. Real-server namespace tests cover both metadata aliases and their
combined fields. Source-bound hosted artifacts include both backend variants,
guard, current phone/consent frontend, actual protocol-2 module and pinned real
Gitleaks scanner. Its real-scanner tests must execute, not skip. The configured
cleanup-script launch path is also disabled pending human QA; no cleanup authority
or enabling setting is provided in this preparation.

Recommend mode, existing scheduling and usage/credit controls are unchanged.
No automatic credit expansion is authorized. No live report flags are cleared;
later reconciliation requires the current exact delivered-report receipts.

## Actual observations and blockers

The incumbent remains October 5 PID3027197 on5511/5512, with the current phone
frontend. API health and live SQLite quick_check pass. Three executions were
active at initial inspection; no writer was paused, killed or interrupted.
Production database resides on the system filesystem, with about40GiB free.
The mounted SSD has less than1GiB free and hit ENOSPC during isolated integration.
A later metadata-floor check blocked further writes. The proven backup/rehearsal
floor remains8GiB. No data was deleted, no floor reduced, and bulk staging was not
moved to the system disk. Desktop B has about341GB free, but no existing Desktop
Linux/WSL working volume was identified.

Incomplete local preparation is privately preserved on Desktop:
B:/vk-backups/vk-safe-release-20261008/preparation-before-capacity-repair-20261008T190650Z.tar.gz
162977486bytes, SHA2564a135c9f6e91e3baa5c36a44d57129b7bf9cbd3e5700c16a98a379bfd885f80c.
Full readback matched. Source-only integration continues through hosted build
facilities; no private recovery data is uploaded to the hosted builder.

Current live dataset has no vk_runtime_identity table. A reviewed, tested
one-time identity-provisioning step is required after authoritative backup and
held fencing, without bypassing the startup gate or rotating account credentials.
No production identity or receipt has been provisioned. Current canonical VK Git
history is shallow, and no turn-preservation policy is configured in the incumbent.
PR223's controller check rejects shallow/incomplete history and absent/unreviewed
policy; scanner packaging is not proof of live preservation activation.
Enabling publication requires explicit reviewed repository/file policies and
complete original-object prerequisites. These settings have not been changed.

A broad read-only inventory encountered Permission denied at
/mnt/vk-storage/lost+found; it was not retried or bypassed and is not a release input.
The prior Desktop native Git credential failure remains blocked and is not
bypassed by this release preparation. The stopped original conversation was not
resumed; no missing workspace was recreated.

## Historical recovery exceptions — unchanged

See VK_TARGETED_RECOVERY_FINDINGS_20261008.md and its exhaustive hash manifest.
132/145 exact originals are preserved in isolated B stores;129 graphs verify
within declared scope.26 rows meet original-plus-remote-witness criteria;
119 still lack verified witnesses, including13 unfound original commits.
Three Hyrox roots lack tree5411325f7e9aa19ca230043f5bb78677d3388c40.
All448 original-path contents/lifecycles remain unknown;59 candidate copies cover
13 names and cannot prove original identity or additional retirement.
The228 independently supported baseline/08:53 later-retirement dispositions are
retained with their intermediate-version/date limits.14,382 archive-header
metadata records and3 copied source modes are preserved; later metadata/ownership
and journal gaps remain explicit. Eight authenticated transcripts share malformed
line415; its missing suffix remains unknown and the checker still fails overall.
The independent Astra High verdict remains bounded, with recovery-complete and
universal-zero-loss acceptance withheld. New integration is not a new independent
review or evidence that historical loss is accepted.

## Remaining safety gates

Preparation is NOT READY and no release promotion/deployment has occurred.
Provide enough authorized mounted Linux working capacity, then capture fresh
whole state with verified authoritative B delivery and preserved exception ledger.
Use verified PR149 tool49cf82d60 in a NEW controller package, never a consumed one.
Measure actual complete restore/handover/latest-data rollback on isolated state,
bind exact artifacts/frontend/module/guard/scanner/tool/controller hashes, and
verify Git preservation or explicit unresolved accounting without manufacturing
receipts. Provision/verify dataset identity only after backup/fence prerequisites.
Hold all relevant writer fences after safe user/session drain, preserving the
incumbent and latest-data fallback. Never restore rehearsal data over production.
New controller must be reviewed/tested for both guarded backend variants and
current phone fallback assets. Require fresh combined checks and actual isolation
acceptance. PR225 needs real live consent acceptance; fixture/independent review
does not replace it. Only then merge/promote the scoped release and perform the
authorized cutover, actual health/preservation/live workflow acceptance and
report when normal work is available. Cleanup remains technically unavailable
until Seamus's human QA passes.
