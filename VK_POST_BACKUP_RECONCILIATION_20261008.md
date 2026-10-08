# October 8 recovery evidence correction — sign-off withheld

The earlier statement that all 710 candidates were accounted for is withdrawn.
The recovery evidence does **not** support restart, cutover, another restore or
cleanup. This correction is developed only in the isolated PR153 source checkout.
Production, shared working files and the stopped original conversation are untouched.

Seamus's supplied independent source review at
`a23a2d2cd2c8ce9d0a064f3b662ce706e3f69c8a` verified argument checks,
database/root identity protection, removal of automatic cleanup and passing CI.
That review could not authenticate the private local/Desktop row evidence.
The checks below are new **parent-agent checks**, not a separate independent
review. AutoSwitch blocked the requested reviewer before creating a child thread:
`Shadow recommendation exceeds inherited child qualification`. Its recommended
qualification was `gpt-6-astra/high`; the operator-controlled policy disables
escalation. A qualified separate reviewer or separate review session is required.

## Authenticated retained packets

Read-only downloads from Desktop B match both published hashes. Streaming checks
also matched all contained manifest entries and local inputs. Recorded commands
and consumed restoration programs were never executed.

| Retained packet | Bytes | SHA256 | Manifest entries checked |
| --- | ---: | --- | ---: |
| `B:/vk-backups/vk-incident-20261007T2316/incident-20261007T2316-evidence.tar.zst` | 35,382,789 | `bf757ac1e257c7b9ca5edacba7491177b300c1db9677f0e94018dae9e8d88aa7` | 41 |
| `B:/vk-backups/vk-startup-recovery-safety-20261008/post-backup-reconciliation-deaa2e1dc.tar.gz` | 4,200,310 | `67d831c8c6289b6c1a80fb47fb2a4d2767cc34c99b0d50d1f870dfbcf64599f5` | 21 |

The reconciliation packet also authenticates its separate 08:53 audit member,
SHA256 `3b87711216971a96a2b9ecb71d28493481b564a667526d7a2723db0d07e99908`.
Packet authentication proves the retained bytes, not the truth of every earlier
conclusion. The original packets are preserved unchanged; this report supersedes
incorrect conclusions in their `resolution.json` and earlier branch notes.
See [archive authentication](scripts/testing/startup-recovery-safety/evidence/20261008-review/archive-authentication.json).

## Corrected 710-row accounting

Every retained candidate's name and event mask was checked against the
packet-authenticated incident journal. Public rows use SHA256 of the full path,
so a reviewer with the private archive can match every row without publishing
private transcript content. No candidate is omitted because its name predates
the catch-up backup.

| Candidates | Supported disposition |
| --- | --- |
| 19 present | Current content matches the authenticated baseline receipt. |
| 15 present | Current newer owner content matches the maintenance Git commit. |
| 228 absent Hyrox names | Authenticated regular-file baseline rows passed the retained 08:53 audit. Their retained private baseline copies still match. The separate owner's retained merge log and release checkpoint match the packet's source hashes and corroborate later task retirement. Separate reviewer sign-off remains pending. |
| 448 absent Hyrox names | **No baseline content or 08:53 audit row exists.** The retained initial journal records deletion for all 447 generated `dist` names and `firebase-debug.log`. This local journal's SHA is recorded, but it is not authenticated by these two Desktop packets. These names cannot be classified as later-retired baseline files; their content and precise lifecycle remain unverified. |

See [all 710 redacted dispositions](scripts/testing/startup-recovery-safety/evidence/20261008-review/mutation-dispositions-redacted.json)
and [retirement claim limits](scripts/testing/startup-recovery-safety/evidence/20261008-review/retirement-evidence.json).
A whole worktree's later removal does not prove the lifecycle of names already
absent from its accepted baseline. The earlier blanket classification of all
676 absent names as later-retired was unsupported.

## Fail-closed historical patch attribution

The old checker matched patch literals anywhere in JavaScript and applied one
aggregate success observation to all of them. It also allowed an overall pass
while retaining parse errors. This is a proof weakness; it does not establish
that any historical patch was misclassified.

The corrected checker recognizes only a complete sequential program of printed,
awaited tool calls. Exactly one patch must be first. It requires a unique call
identity, a subsequent matching result, exact result-slot cardinality and an
ordered patch receipt followed by structured command results. Comments, branches,
unexecuted literals, multiple patches, expressions, duplicate identities and
ambiguous errors fail closed. A later command's returned nonzero exit status can
coexist with a proved patch success. Any transcript parse failure prevents an
overall pass, including a failure outside the requested timestamp window.

Against the authenticated 135,028,264-byte transcript (SHA256
`9b052c937413d638623d785dad70dca575d408eb4afbb90b626811d48475fe56`),
14 accepted patch/result pairs bind individually; the single failed verification
at line 37343 binds as rejected. In-memory replay from commit
`422fe5ba0a406f03dd3a658d25e2f632f66d49ab` matches all 11 resulting files.
**Overall verification returns exit 1 and `recorded_edits_verified: false`**:
line 415 cannot be parsed, SHA256
`17c828479a4803c0126d478ef14638189bc3f4a7f53fe86cf98d80153bd50ffd`.
The malformed bytes remain retained; no exception silently removes them.
See [14 accepted bindings, rejected binding and 11 file hashes](scripts/testing/startup-recovery-safety/evidence/20261008-review/strict-owner-replay.json).

All 15 original recovery files match the current clean maintenance commit
`f36e6f10df9b5e66951c4e47c6dedbdf4f54944a`. Fourteen also match the original
reconstruction hashes. HANDOFF's original version matches ancestor commit
`422fe5ba0`; subsequent continuity commits explain the current difference.
See [15 recovery-file comparisons](scripts/testing/startup-recovery-safety/evidence/20261008-review/recovery-files.json).
These are named content facts, not certification of unobserved edits or history.

## Separate original-history accounting and workspace absence

The [pinned 145-row ledger](https://github.com/artinflight/Operations/blob/53f645a95973aaf30f1f4e2cceb6425c3c748621/logs/2026-10-08-github-preservation-missing-commits.csv)
authenticates as Git blob `92a689f064986f5b8bdf06a0a31d4167759e22b7` and
SHA256 `54dce876aabf4c725fb3a57997a35beacff4d6a87f081980b344274af84d23ae`.
Its counts remain 86 vibe-kanban, 24 opNVLP, 21 hyroxready-app, 11 programming
and 3 caspian-app. Read-only object probes and cross-reference against the pinned
original-commit and association manifests found no original object or original
remote witness for these rows. **All 145 remain unresolved.** Eligible source
checkpoints or reconstructed content do not clear original-history gaps.
See [every history row and probe outcome](scripts/testing/startup-recovery-safety/evidence/20261008-review/original-history-cross-reference.json).

The operator reports that Git Sync Enforcement's development workspace
`/home/mcp/code/worktrees/c31a-vk-git-sync-enfo/_vibe_kanban_repo` became unavailable
around 12:40 UTC after its fixes were pushed. This review observes its absence;
its cause is unknown. No incident-loss inference or workspace recreation follows.
[PR223](https://github.com/artinflight/vibe-kanban/pull/223) remains open at remote
commit `cc203a035d24253814ac75c69b5874e2e390afcd`; all 11 reported checks pass.
See [read-only PR223 receipt](scripts/testing/startup-recovery-safety/evidence/20261008-review/pr223.json).

## Remaining blockers and next authority boundary

Independent row-level sign-off is unavailable until reviewer routing is resolved.
The malformed transcript line and 448 content/lifecycle gaps remain explicit.
The incident journal's overflows and `ready: false`, the earlier 45-error journal,
and outside-root move history leave unobserved writes uncertified. The inventory
still has 14,382 names without authenticated type/link/directory/mode metadata,
and three SQLite rows lack mode evidence. Original history has the separate 145
unresolved rows. Previously skipped private-dependency checks remain unexercised.
No universal zero-loss or recovery-complete claim is made.

Only after independent sign-off should fresh-backup, protected fallback, writer
fencing and controller acceptance be prepared as a separate next step. Cleanup
must remain unavailable until Seamus's human QA passes. This review authorizes
no cleanup, restore, deployment, restart, cutover or stopped-session resumption.
See the [explicit withheld verdict](scripts/testing/startup-recovery-safety/evidence/20261008-review/verdict.json)
and [safe evidence manifest](scripts/testing/startup-recovery-safety/evidence/20261008-review/manifest.json).

Private authentication/reproduction inputs and the parent audit program are under
`/mnt/vk-storage/vk-startup-recovery-safety-20261008/independent-review`.
No raw private transcript or secret is included in committed evidence. The Python
regression suite passes 35 tests, including adversarial patch/result attribution
and a CLI failure despite matching files when transcript parsing fails.
