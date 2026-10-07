# October 7 Lower-Peak Preparation: Not Rollout-Ready

The operator approved preparation and isolated rehearsal only. Production,
scheduling ON, credits OFF and Recommend routing remain unchanged. No full
rehearsal, new production backup, source promotion or cutover was performed.
The approved final candidate remains VK9b3f82538/CU95e7aea47, not deployed.

## Evidence and measurements

Current receipts: `/mnt/vk-storage/vk-low-peak-20261007/`.
`audit-2` supersedes the first inventory by explicitly sizing every prior
recovery-copy root as well as all 44 moved destinations and changed subtrees.
It collapses nested scan roots without removing their contents from coverage.

- All 14 protected recovery roots exist and have current kernel watches.
- All earlier 67 database paths remain included; one additional 274432-byte
  candidate-worktree seed database makes the inventory 68, not 67.
- Database snapshots including a conservative WAL allowance: 2,599,664,360 bytes.
- Changed/recopy non-database files: 8,614,132,774 bytes (8.023 GiB).
- No-compression archive allowance including headers: 13,055,787,765 bytes.
- Fresh capture plus its current verification copy: 18,255,116,485 bytes
  (17.001 GiB), **an estimate, not a completed compressed backup**.
- SSD free at that inventory: 20,441,276,416 bytes (19.037 GiB).
- Required free-space floor: 2,147,483,648 bytes. The estimated capture alone
  leaves only 38,676,283 bytes above that floor; this is not enough to establish
  the combined job's safety while the host keeps working.

The earlier approximately11.2GiB rehearsal estimate excludes fresh backup
retention, current moved-subtree workload and live growth. It cannot establish
readiness. A complete combined peak has **not** been measured or proven to fit.
All local recovery-chain archives and original payloads are retained.

## Directory-move reconciliation

`audit-2/move-reconciliation-evidence.json` binds the original journal and the
successful October5 recovery-placement receipt. Nothing reset or cleared the
original journal. All44 original errors remain visible:

- 34 moves have source-removal events and covering source/parent watches;
  bounded current-tree recopy integration still needs validation.
- Three incoming workspace roots match successful recovery placements from
  outside the watched source tree:036e,1342,ff0a. The existing incremental
  reader cannot accept those as ordinary in-scope source/destination moves.
- Five old recovery administrative directories were replaced. Current Git
  pointers, replacement backlinks and HEAD commits verify for3c96,ad21,be41,
  c5bf,f607. Do not recreate the retired registrations or overwrite newer work.
- Two moves still lack matching source/placement evidence:
  `/mnt/vk-storage/worktrees/d750-cu-credit-aware/codexusage` and
  `/home/mcp/.codex/plugins/cache/openai-curated-remote/sites`.

Explained provenance is not a backup acceptance exception. Incoming placement
and retired-registration cases need a reviewed fail-closed coverage treatment;
the two unexplained moves must be reconciled or a justified full-current
checkpoint transition must retain their historical uncertainty explicitly.
Do not drop protected roots, invent move sources or reuse a clean journal to
conceal these errors. Historical unbacked-edit/recovery limitations remain.

## Implementation and validation

`scripts/testing/staging-low-peak-20261007/` contains the inventory, evidence
classifier, guarded retirement API, floor monitor and focused tests. The API
retires only exact private test SQLite duplicates after verified phase completion;
it rejects archive mismatch, missing Desktop recovery locator, links, changed
allowlists, uncertain consumers and premature/replayed calls.

The guarded API is **not yet integrated into a runnable full-sized driver**.
Do not describe publishing it as enabling the next preparation automatically.
The README lists the exact remaining phase hooks and real verifier dependencies.
`checks-final/checks.json` records focused tests and the pinned PR142 suite,
logs/hashes, minimum observed free space and maximum observed small-test space.
All29 focused tests and146 pinned backup regressions passed. The measured small
test run used at most1,064,960 allocated bytes at sampled instants and observed
no less than20,398,686,208 free bytes, above the2GiB floor. These are small-test
measurements, not a production-sized rehearsal measurement.
Small fixture archive/extraction tests are real; Desktop and consumer callbacks
are synthetic. No new full Desktop recovery or live handover assertion is claimed.
`pnpm run ops:check` passed. `pnpm run format` completed Rust formatting but
stopped at missing frontend Prettier. No dependency installation was attempted.

## Exact intended rollback

Use the final accepted payload at `/mnt/vk-storage/vk-first-run-final-20261006/`:

- VK source `9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4`.
- CU source `95e7aea47e137015daa8efcbb210184ee7ce723c`.
- Candidate server SHA256
  `c33e1cc7b7efb4f63b8c08fb1bbbb59a448f1340fe7728f6bf5118c9d59f17c0`.
- Compile-disabled v2 fallback server SHA256
  `2494f1dc7ca2de8ed26806603b86f9fa3e466c9f19a00e4aab2c8b9712a70c97`.
- Payload archive SHA256
  `6ac06d9b93244894e6200aadf4e68e17f7c020b5cef18b399eea300e7cd1393f`.

`package-and-production-preservation.json` freshly verifies the complete payload
and candidate/fallback/guard archive members. Current3027197 and CU414400 remain
running; existing fallback1369037 remains frozen. Final free-space sample in
that receipt is20,396,761,088 bytes. Historical unversioned service aliases are
not these production units; resolve the actual PID/cgroup rather than restarting
an inactive alias.

This fallback reads the SAME LATEST DATA and preserves new durable holds.
The old production reader is not the overnight capability rollback target.
Previous isolated47-case/browser acceptance remains evidence; it is not the
pending full-workload backup/rehearsal or permission to expose the capability.

## Next safe action

Finish the coverage treatment above, then bound the complete current workload
and integrate the tested phase hooks into a new unconsumed package. If retained
fresh backup plus rehearsal still exceeds the SSD budget, review/adopt Operations'
existing Desktop-streamed verification/restore support into that new package;
do not delete local parents or silently change recovery dependencies. Its code
has not been adopted here. Only a measured full-workload rehearsal with all
assertions and the compatible v2 reader can clear preparation. Source promotion,
fresh final drain and a separate explicit rollout approval remain afterward.
