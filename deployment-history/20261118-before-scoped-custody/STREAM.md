# Finish backward deduplication — 18 November 2026

## Scoped conversion implementation — 18 November 2026

The operator explicitly authorized resolving the per-workspace blocker. A shared
per-execution OS-lock protocol is now implemented in capture, append, migration
and recovered-final writers; the existing converter has a separate --online
admission path. The current production backend lacks protocol1 and was explicitly
rejected by the read-only live gate before source mutation. Production remains
active with the same PID/invocation; no cutover, pause, conversion or deployment
has occurred. One activation of qualified writer binaries is required at the
already deferred evening boundary; thereafter bulk conversion needs no global
pause. Do not ask again for the existing cutover approval or interrupt daytime work.

Read VK_SCOPED_LOG_CONVERSION.md for the contract and remaining integration gates.
143 focused Python tests pass with3 optional host tests skipped; the real Rust
lock implementation passes4 standalone tests, including cross-process Rust/Python
qualification in the Python suite. Actual async-writer Rust integration tests are
building through the existing bounded offline shared target and owned build lock.
The first sandbox attempt stopped before compilation because this checkout lacks
the old dev_assets mountpoint; v2 removes that obsolete mount and is running.
Results belong under P/efficiency-20261118/scoped-rust-tests-v2. Do not launch a
second build or recycle a consumed package. Earlier efficiency experiments remain
unactivated. Native goal is paused; this is the separately authorized blocker fix.

## Active workspace correction — 18 November 2026, 10:11 UTC

The operator confirms that the large workspaces are active. Do not propose retiring
those workspaces or treat absence of a running execution as abandonment. The
current question is how their owning agents can reduce history individually.

Read-only ACTIVE_WORKSPACE_CLOSED_LOGS.private.json in P/efficiency-20261118 records
2,223 closed, terminal-execution raw logs using 82,424,827,904 allocated bytes in
unarchived In Progress workspaces. Pending/unknown logs use 311,156,736B across
10 files; one OP::Disk Space capture sidecar is invalid JSON and is classified
unknown, preserved, and not repaired. These are source bytes, not predicted savings
or production eligibility. T18 has21.838GB closed, Staging Check13.024GB, and PODs
Weekly10.895GB. The prior 83GB total also includes existing objects and metadata.

Recommended scope is lossless per-execution dedup inside active workspaces,
preserving complete readable history and native continuation state. Owners can
identify pending work, maintain a compact continuity note and nominate closed
execution IDs at a natural boundary. A shared, resource-bounded script should do
packing, normal-B recovery verification and journaled installation, sequentially
across workspaces; asking every model to run independent bulk loops is unnecessary.
The currently qualified Batch explicitly requires the global deployment WriterFence
and maintenance route. A workspace/file-scoped exclusion and recovery path needs
implementation and qualification before any zero-global-pause installation claim.
Existing online object staging alone does not authorize manifest replacement.
No agent was messaged and no conversion, retirement, pause or deployment occurred.
A summary or shorter future tool output cannot reclaim already persisted history.

## Cold history retirement proposal — 18 November 2026, 09:54 UTC

The operator proposes keeping completed/archived conversations on Desktop B,
retaining a local catalog, restoring individual histories through a tasked agent,
and deduplicating those archives offline. This is under evaluation; no retirement,
nightly automation, new cutover, or production mutation has been launched. Daytime
service must remain available. Do not automatically launch the old v9 whole-system
conversion route while this alternative is being resolved.

Fresh read-only database/filesystem inventory is retained in
P/efficiency-20261118/COLD_ARCHIVE_INVENTORY.private.json. Allocated session-history
bytes (including directories/objects, unique inodes; no symlinks or scan errors):

- Archived, unpinned, no running execution: 286,523,392B across 309 workspaces.
- Additional unarchived Done, unpinned, no running execution: 10,911,744B across
  23 workspaces. Together approximately 0.297GB; metadata selection only, not an
  approved or fully qualified retirement set.
- Unarchived histories overall: approximately 91.4GB; approximately 83.0GB belongs
  to In Progress tasks, including pinned/running exclusions. Old timestamps or
  terminal individual executions do not prove an entire workspace is retired.
- These history files are on the root ext4 volume, device 64512, not the secondary
  SSD (device 2065). Confirmed by stat and findmnt. Reclamation here does not
  directly release the SSD staging volume. Earlier shorthand implying otherwise
  must not guide capacity decisions.

Recommended lifecycle, requiring implementation/qualification: select an exact
inactive workspace set under a workspace-level retirement guard; preserve pending
inputs, pinned/current work, source changes and shared attachment references;
retain a consistent SQL/recovery record, native transcript dependencies, exact
log/object/sidecar graph and restore metadata on B; verify complete recovery before
retiring only that verified local set. Keep a searchable local catalog with an
explicit restore-required state. Restoring must rehydrate and verify paths before
history/resume is enabled. Existing archived flag/worktree cleanup is not such a
cold-history state or writer guard. Integrate retirement after successful Nightly
backup and independently preserve cold bundles from rolling-backup expiration.
Deduplication can then use immutable B archives independently of live service.
This is a better future lifecycle, but archived/Done flags alone do not cover the
present 91GB backlog. Do not silently redefine the original completion claim.

Efficiency evidence from the same turn: existing B reader fetched and verified
one 200,819,810B body in 47.126s baseline; the isolated 1MiB decoder block candidate
with unchanged <=64KiB wire frames took 12.469s (3.8x). Compression took 49.424s;
near-data independent restore took 72.014s, so neither was selected. All experiments
terminated and released their contexts. The 1MiB candidate is not production
qualified or integrated. Local packer change removes repeated compression passes;
130 tests ran in 7.790s, OK with 3 skipped. SSD pack benchmark refused before
archive output because free space was below the unchanged 3GiB reserve. No measured
end-to-end duration or production recovery is inferred. Bulk work belongs in the
existing finite local controller, not a continuously active model/polling loop.

## Operator correction — 18 November 2026

The operator confirms that explicit `cut over now` approval was given the previous
night. The earlier claims that approval was missing were wrong. That authorization
persists; do not ask for it again. The operator now needs Vibe for daytime work and
has explicitly deferred cutover until tonight. No exact start time or time zone
has been agreed: do not infer permission to interrupt daytime work or invent a
scheduled start. Preserve ordinary service and all active work. No arming,
maintenance pause, conversion or launch occurred during this exchange; only
read-only inspection was performed. When the agreed evening window arrives,
refresh volatile safety checks for the selected route; do not assume the old
whole-system operation is the accepted design after the cold-retirement proposal.

The full user objective remains unfinished. Only the four earlier archives are installed;
historical net recovery827,506,688B is not recredited. No new production conversion,
maintenance, dispatch pause or backup payload capture occurred during this turn.
Prior cutover approval exists, but daytime interruption is deferred. The current
request is to evaluate an efficient cold-retirement alternative.

Current immutable candidate: P/completion-package-v9/PREPARED.private.json.
NEXT_INPUTS SHA2564f0c9db5d6f80b5200dbfc017f466b55cf17a465d4530efdacd0911dc3547757;
controller5020115c833f6dcca9cf717b7cdfb227b0574ee04c21fd75881f5c1f727d3ce7.
It remains UNARMED. P/arm_completion_v9.private.py defaults to inert inspection;
--apply requires fresh <=300s readiness and exact current root execution. It
creates a fresh operation-owned dispatch hold and immutable armed inputs, never
launches. The finite controller must wait for natural quiet; do not stop agents,
replay consumed packages or create another continuation loop. Preserve all epochs.

Implemented tested lost-capacity-reply/journal recovery (previous local commit),
adaptive worst-case SSD admission, full inode/directory/staging accounting, finite
B input caps and a final benefit recheck after shared objects are created. Fixed
the inherited backup closure's omission of raw/adjacent files: all affected
namespaces now include nested regular bodies and unreferenced objects. Large files
use bounded fragments with independently restored whole-file SHA256 verification.
Existing real writer custody, normal B restore, Rust EOF and safe recovery remain.

Sizing COMPLETE:3,366 stable plans/91,104,810,328rawB. Normal B metadata matches
6,732versions:5,586exact map +573retained carrier;573missing/9,117,894,501B.
No original/full closure restore acceptance is inferred from these matches.
Final input caps:9,185,003,365B originals,46,453,728,929B controls/closure.
Conservative planned B demand61,373,458,925B. At00:31UTC fresh B was Healthy/Online,
71,155,728,384B free:9,782,269,459B slack. SSD conservative simulation318batches,
minimum3,296,433,152B above unchanged3,221,225,472B reserve, charging directories,
object records and2MiB retained controls/batch without cross-file dedup credit.
Actual guards still run before each pack and throughout backup/conversion.

126focused tests and8exact-package tests pass. Four public cases(two workspaces,
1440/393px) pass history/settings/review-dialog/empty-queue rendering, no page
errors or operator writes. Fresh exact five-owner/reader/frontend check passes;
one active root,zero durable queued messages,32uncertain inputs preserved.
Full Cargo/frontend check/lint and PR update are not claimed.

Growth requirement is supported: deployed native0.159.2 startup0historical turns/
1,826B versus retained predeployment8/10,746,496B. Ordinary27.048minute interval:
1,961,984allocated log/object bytes, no new/missing files or conversions, no new
executions. No extra provider request, matched-workload claim or daily forecast.
Operating/restore details are in VK_LOG_DEDUPLICATION.md.

P=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117.
D=P/completion-20261117-demand. Sizing and backup lookup jobs are TERMINAL;
RESULT, BACKUP_DEMAND_RESULT, B_INPUT_BOUND_COMPONENTS_v2 and FINAL_READINESS
retain evidence. Earlier serial sizing was explicitly stopped after2,948plans;
its interrupt and all completed plans remain. No measurement job needs resuming.

Remaining: authorized natural-quiet production window; fresh owned dispatch
pause/SQL/fence; all beneficial conversion passes; complete normal-B closure;
ordinary service, original FD/filesystem recovery and exact WakeWatch restoration.
Full completion is not claimed. Prior continuity is retained in
[November17 history](deployment-history/20261117-before-completion-takeover/STREAM.md).

Full historical archive: [STREAM history](STREAM_HISTORY_20261017.md).
