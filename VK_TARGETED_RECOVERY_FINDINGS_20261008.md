# Targeted recovery findings — October 8, 2026

## Verdict

**Partial recovery verified; recovery-complete and universal zero-loss acceptance
remain withheld.** This investigation executed the published bounded plan and
recovered material into new isolated storage. It did not place recovered files
into any live tree, recreate a VK workspace, restart, cut over, merge, delete,
clean up, or change permissions. Original evidence and shared work remain intact.

These are parent-verified findings, not an extension of the completed Astra High
review. That review independently supports the corrected 710 dispositions,
14 accepted patch/result pairs and one rejection, 11 replayed files and 15
recovery files. Its report and source manifest remain unchanged in
[the independent review record](VK_INDEPENDENT_RECOVERY_REVIEW_20261008.md).
The checker continues to fail closed on malformed transcript line 415.

## Actual recovery and remaining accounting

| Target | Verified result | Still unproved |
| --- | --- | --- |
| 145 original commits | 132 exact original commit objects preserved in isolation: 86 VK, 24 opNVLP, 19 Hyrox, 3 Caspian | 11 Programming and 2 Hyrox original objects remain unfound |
| Original commit graphs | 129 roots have all reachable objects hash-verified in the declared scope: 86 VK, 24 opNVLP, 16 Hyrox, 3 Caspian | Three recovered Hyrox roots have missing dependencies; VK scope ends at its authenticated original shallow boundary |
| Original identity plus remote witness | 26 rows meet both criteria, using immutable Actions heads or verified ancestry | 119 rows lack a verified remote witness; isolated object recovery does not prove original remote publication |
| 448 names | 59 same-name candidate copies preserved, covering 13 names: 12 generated JS names and the debug-log name | All 448 original-path contents and authorized retirement remain unknown; 435 names have no byte candidate |
| Missing metadata | All 14,382 original archive-header records recovered: 14,050 directories, 331 symlinks, 1 hard link | Later/intermediate metadata and loss across uncovered intervals remain unknown |
| Three SQLite modes | Snapshot headers and authenticated producer establish copied source mode bits `0664` | Original ownership and subsequent modes remain unproved |
| Initial journal | Desktop packet authenticates the retained journal and its aggregate DELETE masks for all 448 names | Masks do not establish per-event dates, old bytes, authorized retirement or absence of later recreation |
| Malformed transcript | Eight authenticated retained copies have the same bad line, including four September copies | No intact suffix or complete counterpart found; strict verification still fails |

The earlier 228 baseline/08:53-backed later-retirement dispositions remain the
independently supported bounded finding. **No additional retirement is proved.**
No candidate from another path is promoted to recovered original content because
its basename matches. The debug-log candidate is particularly insufficient to
identify the missing log's contents or retention intent. Intermediate versions
and exact per-file retirement dates remain unknown even for the 228 rows.

The fixed original ledger remains unchanged:
[Operations ledger at 53f645a](https://github.com/artinflight/Operations/blob/53f645a95973aaf30f1f4e2cceb6425c3c748621/logs/2026-10-08-github-preservation-missing-commits.csv).
The new accounting distinguishes original object bytes, graph completeness and
remote witness coverage. It does not clear original-history gaps using a rebuilt
working tree or equivalent final content.

## Sources actually searched

The investigation compared 32 retained checkpoint/delta member inventories and
seven offload inventories against the fixed target lists. It streamed and
authenticated the October 7 full/catch-up archives, October 1 full/delta archives,
September 11 preservation archive, September thread-recovery container, three
older/offloaded backup containers, and five smaller recovery/acceptance archives.
[Authenticated source receipts](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/authenticated-sources.json)
record hashes, sizes and scan counts. Hashing original containers and reading
selected members left their contents unchanged.

All 93 October 7 Git pack indexes, 93 October 1 checkpoint indexes, one October 1
delta index and all 78 September preservation indexes were checked, with valid
Git index SHA1 trailers. No target original commit was found in those packs.
The September inventory instead identified 114 exact loose original commits.
The five relevant repository object stores were preserved as 26,395 original
object files, totaling 1,304,912,934 bytes. The backup was captured online with a
recorded tar exit 1, so this is authenticated captured material, not a frozen,
universally complete history boundary.

Exact GitHub `/commits/SHA` reads for all 145 targets returned 47 available
originals and 98 unavailable responses. Exact `/git/commits/SHA` checks on the
remaining 98 supplied none. The 47 available originals were serialized and
accepted only when their Git SHA1 exactly matched the ledger; 18 add to the
September archive's 114 unique originals. No author, message, raw response or
private object contents are published. Remote reference inventory covered 2,489
heads across the five repositories; direct heads, main/staging/related branch
ancestry, Actions heads, 227 Actions ancestry comparisons and recovered parent
graphs were checked for witnesses. The result is 26 rows meeting the original
identity plus witness criterion, not all 132 locally preserved objects.

Eight earlier local-only Git bundles were preserved unchanged. Six imported
successfully into isolated B object databases. Two VK imports failed because
prerequisite objects were not connected to repository history; the bundles and
failure receipts remain intact, and the prerequisite was not bypassed. VK's 86
originals came from the September preservation archive. Two older May Programming
archives were searched and their original Git objects preserved; none contained
the 11 target Programming commits.

The original September VK shallow metadata was recovered and authenticated:
boundary `30abcdac787b6be01312f19bad0b15a8f12898b8`, 41 bytes, SHA256
`5b9600981c8d4e4143670989ea28d72a566b5f666ac4efd2c12ebf79fe73cb46`.
VK graph checks use that retained boundary explicitly. It is not a newly invented
cutoff or proof of all earlier upstream history. Every object reachable in the
declared per-root scope was hashed. Negative global checks for additional
incomplete objects remain recorded; they are not replaced by a claim that every
object in every recovered database passes `fsck`.

GitHub dependency metadata/bytes also supplied exact parent/tree/blob objects for
the Hyrox roots, accepted only after matching each Git object identity. Three
roots remain incomplete:
`0d80abb5750f8e564bcf80c5b5436d2128c7994b`,
`12e552ef56d4d74f219b2ccbb39d0695502d2212`, and
`706cb8310df5125af8abf45405602aeca0911a8e`.
Their remaining missing dependency is tree
`5411325f7e9aa19ca230043f5bb78677d3388c40`. Blob
`cd5ca5de0e5deea79a75c48867500d2289151ed8` was subsequently preserved with
verified exact Git identity through the existing authorized GitHub API; its
response is retained privately on Desktop. The blocked native fetch was not
retried. A targeted read of retained index files and all five isolated object
stores found no copy of the missing tree.
The first tree's retained API entries serialize to a different Git identity;
that assembly was rejected, not treated as recovered original bytes.

The targeted lifecycle search read 2,022 available native transcript files,
23,466,444,460 bytes, with 26,043 matching records referring to 15 distinct target
names. These references supplied no original-path hash plus dated per-name
retirement proof. Dated Firebase caches and older journal matches also supplied
no such proof. Hyrox's 51 listed GitHub Actions artifacts contained no web/dist
build artifact. PR1960 currently remains open/unmerged at head `4175d135c…`;
the earlier owner-local staging merge is a distinct witness, not a GitHub merge.

Older authenticated rollout copies and retained VK normalized/process/token
records were checked for a complete counterpart to line 415. The malformed
prefix is an `event_msg/token_count` record dated August 26; its missing suffix
is unknown. The same malformed bytes were already retained in September, so
these observations do not identify the October 7 incident as their origin.
The normalized stream also has parse errors and no exact complete counterpart;
its current-file observation is not independent archive authentication.

## Preserved artifacts and redaction

Original object databases, older bundles and candidate bytes live only under
`B:/vk-backups/vk-targeted-recovery-investigation-20261008/`, with development
receipts and small candidate copies under the corresponding mounted SSD task
directory. No working-tree checkout or VK workspace registration was recreated.
Exclusive creation or exact-byte reuse protected existing material.

The public evidence directory contains only row IDs/digests, exact commit IDs,
declared scopes, public witness URLs, captured attributes, source authentication
and private-preservation receipts:

- [145-row original accounting](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/original-145-accounting.csv)
- [448-row unknown/candidate accounting](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/unresolved-448-accounting.csv)
- [Candidate provenance](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/candidate-provenance.csv)
- [14,382 metadata records](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/captured-metadata.csv)
- [SQLite mode proof](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/snapshot-mode-proof.json), [journal authentication](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/initial-journal-proof.json), and [transcript counterparts](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/transcript-counterparts.json)
- [Graph verification](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/graph-verification.json), [summary](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/summary.json), and [artifact manifest](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/manifest.json)
- [Private Desktop preservation receipt](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/private-preservation-receipt.json) and [incremental receipt](scripts/testing/startup-recovery-safety/evidence/20261008-targeted-recovery/private-preservation-followup-receipt.json)

Raw transcripts, original file/commit contents, debug-log candidates, private API
responses and link targets stay private. The original independent review files
remain byte-for-byte unchanged. PR223 commit `cc203a035…` and passing CI retain
their verified status; the c31a development workspace's reported disappearance
around 12:40 UTC has unknown cause. It was neither recreated nor treated as proof
of incident loss.

## Exact blocker and next decision

Native Git fetch of Hyrox original `0d80abb5750f8e564bcf80c5b5436d2128c7994b`
into the isolated Desktop B database exited 128: the `wincredman` credential
store could not persist credentials, and Username could not be read with
terminal prompts disabled. No credentials, authentication route or permission
was changed to bypass this blocker. Both failed VK bundle imports likewise remain
explicit failed actions rather than successful imports.

The next concrete input is an operator-provided authenticated original-object
source for the three incomplete Hyrox graphs and the 13 unfound originals, or an
operator-managed Desktop Git authentication handoff for a later specifically
authorized retry. More remote witnesses are required before clearing the other
119 original-history accounting rows under the published criterion.

For the 448 names, an earlier original-path snapshot/hash plus dated lifecycle
record is still required. No retained source searched supplies that pairing.
Seamus/the work owner must either supply additional historical evidence or decide
whether the enumerated generated-output/debug-history uncertainty is acceptable.
That decision records accepted uncertainty; it cannot prove old bytes or zero
loss. The malformed suffix and writes during journal gaps similarly remain
unprovable without a complete retained counterpart or overlapping historical
evidence. Current metadata cannot reconstruct intervening states.

This draft remains available for review. Operational recovery, fresh backup,
protected fallback, writer fencing, controller acceptance and any restart/cutover
are separate next authorizations after sign-off. Cleanup remains unavailable
until Seamus's human QA passes.
