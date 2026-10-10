# Independent recovery review received — October 8, 2026

## Actual verdict and scope

**The corrected bounded content accounting is independently substantiated.
Recovery-complete and universal zero-loss sign-off are withheld.** The separate
review has completed; routing is no longer an outstanding review prerequisite.
No duplicate reviewer or routing change is requested or performed.

The operator identifies reviewer workspace `802f378d-7b9c-4f62-ab89-d8f8205e8391`,
session `27d79e0c-3d31-4293-9f71-2985466a93c7`, and execution
`dd57bdb6-6043-4951-b16a-2fb286938ca9`, completed at **13:59:52 UTC**. The report
confirms Astra High from its own turn metadata. Completion time/execution ID
are operator-supplied attribution, not a new live execution query.

The review covers implementation pin `984f5ee79d575df0066c6a3afc2ee49fe02e4d0e`
and documentation/receipt tip `d000ce732049b296f71f47d8ee88edc01b84a904`.
This tracking update changes no checker, tests, application or recovery files;
it does not extend the review's code pin to unreviewed implementation changes.

It independently downloaded/authenticated all three Desktop packets and their
manifests, reproduced every one of the 710 supplied candidate dispositions,
bound 14 accepted patches and one rejected patch, replayed 11 files, and checked
all 15 recovery files. It corroborates later retirement for 228 baseline-backed
Hyrox names, with exact per-file deletion times/intermediate versions unproved.
The remaining 448 names, malformed line 415, 145 original-history gaps and
journal/mode/link limitations remain unresolved. This is no operational approval.

## Safe artifact references

These three redacted tracking artifacts are copied byte-for-byte from
`/mnt/vk-storage/independent-recovery-review-20261008-802f378d/safe-review`:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| [REVIEW.txt](scripts/testing/startup-recovery-safety/evidence/20261008-independent-review/REVIEW.txt) | 9,388 | `60ea25f282d40636fd909ee6b7886a77c84230c9a63c10292c0c5453e9b27604` |
| [unresolved-448.csv](scripts/testing/startup-recovery-safety/evidence/20261008-independent-review/unresolved-448.csv) | 104,828 | `271b667ee95466d5a7f98d4b81ab1d8e50a626b54edd5c982d92a37aeb52f92d` |
| [source manifest.json](scripts/testing/startup-recovery-safety/evidence/20261008-independent-review/manifest.json) | 2640 | `2cfa3bdbb0ccf0fd8e9a4aa63a2371e00cf6ca06015b44035531f163315bf51a` |

The report and CSV match the source manifest's hashes/lengths; the CSV has 448
unique row IDs and path digests. The manifest inventories additional reviewer
receipts retained in the original reviewer directory; they are not all copied
into this documentation update. The supplied manifest is retained unchanged,
not presented as a new three-file manifest. No private transcript, raw recovered
file contents or secret is published. Prior parent verdict/routing receipts are
historical observations and are superseded for review status by this record.

## Published investigation plan — subsequently executed

The latest operator instruction subsequently authorized investigation and recovery
into isolated storage. The plan below is retained as the historical scope; actual
searches, recovered material, proof limits and blockers are recorded in
[the targeted findings](VK_TARGETED_RECOVERY_FINDINGS_20261008.md). These new
parent findings do not extend the completed independent reviewer verdict.

Use the unresolved CSV and pinned 145-row Operations ledger as fixed target
lists. Do not repeat the 710-row audit, successful patch replay, file hashes or
three packet authentications. Only a newly found witness warrants targeted
validation of its affected rows.

1. **448 names: check alternate retained versions and lifecycle witnesses.**
   First compare original member inventories/tombstones of Desktop's full
   `B:/vk-backups/vk-runtime-backup-20261007/checkpoint--02136af9b9c24c08bccba0868864e597.tar.zst`
   and catch-up `delta--430d3a842f5d4216862a1703e33232b8.tar.zst`, rather than only
   the already-merged baseline receipt. Check any earlier checkpoint already
   listed in retained backup inventories; its existence/coverage must be
   established before treating it as evidence. Read selected archived members
   only for indexed hits, without filesystem placement. For the 447 dist names,
   compare retained `.firebase/hosting.ZGlzdA.cache` and dated build/deployment
   inventories/logs against PR1960, branch tip `4175d135c`, and staging merge
   `9aa765897aa6dfd8caf3a691173fd65257522d27`. A per-name earlier hash and dated
   supersession/removal witness can distinguish historical build output from
   potentially missing work. Treat `firebase-debug.log` separately: its old bytes
   and retention intent are unknown. A whole-worktree removal, basename or
   unauthenticated DELETE mask cannot settle either content or earlier lifecycle.
2. **145 original commits: inspect different retained object stores/witnesses.**
   Search checkpoint/older-backup Git object packs and reflogs, plus any existing
   Desktop clones identified by preservation inventories. Do not repeat the
   same canonical-store absence probes. Cross-reference already retained remote
   branch/tag/PR-head and Actions-run commit receipts with GitHub reads for the
   exact ledger SHAs. Clear a row only with verified original commit-object
   identity and an immutable remote witness/ancestry relationship. A sanitized
   checkpoint, same final tree or PR223's different commit does not clear it.
   No fetch into shared repositories or workspace recreation is needed.
3. **Transcript/metadata/journal gaps: inspect targeted alternate records.**
   Compare line 415 and adjacent event identities with older authenticated
   copies of the original rollout and retained VK normalized/process records.
   Require provenance tying a complete counterpart to this stream; preserve the
   malformed original and the checker's failure. For the 14,382 metadata gaps
   and three SQLite modes, consult original archive headers/source manifests or
   earlier authenticated snapshots, distinguishing captured attributes from
   staging/snapshot-generated modes. For overflow/outside-root intervals, look
   only for already retained overlapping journals or dated edit/move witnesses
   covering the actual gaps and original bytes. A new clean journal, current
   permission or successful test cannot prove missing historical state.

## Historical unknowns at independent-review receipt

The 448 names' prior contents, per-name supersession/deletion times, intermediate
versions and authorized disposability remain unknown. For the 145 history rows,
original commit identity/remote coverage remain unknown. Line 415's complete
record, original link/type/mode metadata, and writes/bytes during journal gaps
cannot be manufactured from current files or incomplete receipts. Such claims
are unprovable from the currently authenticated evidence alone; the candidate
alternate sources above have not been searched in this tracking-only turn.

If that bounded search finds no witness, Seamus/the affected work owner must
decide whether to accept a specifically enumerated, bounded preservation result
with those residual unknowns, or require additional historical evidence and keep
recovery-complete acceptance blocked. They must explicitly determine whether
obsolete generated output/debug history and exact original commit history are
required preservation targets. A decision to accept uncertainty does not verify
missing contents/history and must not change the ledger to proven zero loss.
No such decision is required to finish this tracking update or proposed plan.

Operational recovery, release preparation, live-file repair, workspace recreation,
cleanup and restart/cutover remain separate authorizations. Cleanup stays unavailable
until Seamus's human QA passes. The review-receipt turn updated isolated tracking
only; the subsequent authorized
investigation recovered material only to isolated storage. No operational action
is authorized by either record.
