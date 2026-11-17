# Production log deduplication: final go/no-go plan

17 November 2026. **NO-GO for launch; planning and read-only checks completed.**
The current instruction authorizes preparation only. No maintenance, dispatch
pause, conversion, source deletion, SQL backup, new producer, build or agent was
started. Histories, original backup epochs, completed batches and pending inputs
are preserved. Existing Vibe/Nightly handoffs remain accepted.

## Current evidence

Private receipts: `P/final-go-no-go-20261117`, where
`P=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117`.
These are observations, not reservations or a future writer fence.

| Gate | Verified observation | Decision |
| --- | --- | --- |
| Compatible serving | Aware main `4766246c…` and protected `40a91f69…`; main/protected/proxy/connector/publisher active and thawed with unchanged invocations; current frontend and public TLS/assets match | Pass now; recheck before freezing. Never start an unaware fallback over CAS. |
| Activity/queues | Only this planning execution active; zero durable queue; all 1,338 volatile session queues empty; stable DB/API/DB fingerprint; 32 uncertain incoming records preserved | Wait for this turn's natural completion, then repeat. Never dismiss/replay uncertain records. |
| Capacity | Authenticated backend reports ownership held | Serving recovered; actual release receipt and same genuine lock FD required for maintenance. |
| SSD/RAM | SSD 3,497,500,672 B available: 276,275,200 B above existing 3 GiB floor. RAM 8,194,068,480 B available; full PSI avg10 0.00 | Instantaneous floors pass; peak staging demand remains unproved. Keep 4 GiB RAM/.10 PSI/3 GiB SSD safeguards. |
| Desktop B | Correct NTFS/disk identity; Healthy/Online; 85,496,852,480 B free. Existing MM controls exclude B from E/Q/R; no owner pause or explicit B hold. Local controller/body-writer locks have no kernel holder | Access passes. Fresh native SMART/lease admission and actual remaining-write budget still required. No payload capture started. |
| Backup ownership | Accepted Vibe/Nightly contracts/source pins intact; sole producer and schedule ownership unchanged | Reuse exact retained versions; no new pipeline, owner turn or whole-calendar commissioning gate. |
| History/UI access | Full history passed 22 responses in 334.782 s: four main/four protected canaries, six T18 checks, exact 7-page/49-entry pagination. Fresh public UI passed two workspaces at both 1440/393 px: four successful responses, 160 history entries, zero page errors/operator writes | Browser/authentication access available. Mobile is viewport testing. Full rendered review/settings/queue acceptance remains unproved; navigation probe did not establish a settings dialog. |
| WakeWatch | Exact original dispatcher and five configurations; five fresh normal monitor observations; zero unsettled deliveries; timer active | Unchanged this turn. Preserve held outcomes and existing AF profile mismatch. Future pause needs fresh preimage and five-ledger reconciliation. |
| Attempt | Package-v5 hashes match; prepared operation `40f9db6e87f345bba47606864a4e3a16` has no ATTEMPT; state `prepared_unarmed_partial_resume`; automatic continuation off | Deliberately unarmed. CURRENT/SEALED pointers still identify consumed a088: never replay them. |

Fresh metadata: **3,433 candidates / 90,992,755,255 logical B**, including 82
preserved tiny files; 3,351 non-tiny candidates form **306 planned envelopes**.
Packing must still establish actual positive benefit. Preserve eight pending
captures, one invalid capture record, four completed archives and 14 files in the
active session. Reobserve newly terminal files under custody after natural quiet.
Logical bytes are not recovery potential proven by packing.

## Remaining go gates

1. **Peak allocation:** account for worst-case staging objects/manifests,
   directories, controls and rollback demand on the actual filesystems before
   maintenance. A 512 MiB input envelope does not guarantee fitting in 276 MB.
   Largest candidate is 324,499,915 B; 34 candidates exceed current headroom
   before compression. This proves neither compressed failure nor success.
   Establish a defensible bound or qualify allocation-bounded preparation;
   preserve old staging, primary objects, histories and recovery records.
2. **Remaining B writes:** use the existing retained map/selected factory to
   resolve exact reuse and genuinely missing versions. Count originals, fresh
   SQL, software/frontend/control deltas, all-object closure, indexes/temporary
   allocation and confirmed competing writes. Compare actual physical demand
   with fresh free space. 90.99 GB logical exceeds 85.50 GB free, but existing
   verified chunk reuse can reduce writes substantially: neither insufficiency
   nor sufficiency is proved. Do metadata/demand preparation online; any captures
   use only the existing authorized producer. No invented fixed reserve/quota.
3. **Final sealed operation:** qualify and pin broader read-only rendered
   review/settings/queue acceptance alongside the proven history cases. Refresh
   changed owner pins. Create a new immutable armed sibling of package-v5,
   preserving every previous package/attempt/failure. Use the unused proposed
   operation only if still unconsumed. Bind a fresh operation-owned WakeWatch
   pause, exact preimage/config pins and restoration helper into B recovery
   controls. `REQUIRES_FRESH_PAUSE_BEFORE_ARMING` is a stop condition.
4. **Capacity lost-reply recovery:** offline execution of the exact pinned
   `Boundary.freeze_boundary` reproduced a TypeError when release committed but
   its reply was lost: the next status correctly returns `owned=false,state=null`,
   while the helper indexes `state.epoch`. Its in-memory release receipt stays
   unset. Correct and regression-test that branch in a NEW source-pinned host
   helper before arming. Reconcile the durable release intent and persisted v2
   capacity state under the real lock; verify epoch/revision and goals/issued
   history, preserving a foreign/unknown owner. Never interpret a missing reply
   as no release or reopen ingress before authentic ownership is recovered.
   `CAPACITY_RELEASE_EDGE.private.json` retains the exact offline reproduction;
   no live release was attempted and the deployed helper was not changed.
5. **Window boundary:** a subsequent instruction must release the current
   plan-only restriction. Recheck resources, owners, durable/volatile queues,
   native backup admission and all five watcher ledgers; wait for natural quiet.
   Fresh current-main SQL normal B restore and actual held WriterFence must pass
   before any source replacement. Fixtures and historical recalls cannot replace
   that current checkpoint.

The accepted 68 original/sidecar versions total 3,073,516,522 B with independent
normal-B full EOF/hash/Linux metadata proofs. Current handoffs supply software,
frontend, SQL and control recovery APIs; they do not certify every remaining
version or future final closure. Whole green-XDG backup root inclusion covers
hidden `.log-objects`, but inclusion is not closure acceptance. Preserve complete
session namespaces: all objects (including unreferenced), manifests/raw logs,
sidecars, adjacent files, directory/link metadata and normal namespace references.
B may deduplicate verified physical chunks; repeated turns remain byte-exact.
Restore objects before exposing manifests. Retain the accepted 18 historical
restore-before-view cases; do not claim all 18 are local/live.

## Downtime uncertainty

**No supported total duration or upper bound is available.** The prepared
controller holds ordinary admission while packing, restoring/publishing each
batch, checkpointing and capturing final closure. Its 306 envelopes are not
measured equivalent workloads; missing B captures and closure demand are unknown.

Measured components: full history **334.782 s**; four public viewport/history
cases **76.019 s**. History runs after adoption and again before ordinary release.
If today's duration repeated, those calls alone would take about **11m10s**;
that is an illustration, not a lower/upper bound or total estimate. Earlier B
recalls took 202.429 s for 1.053 GB and 342.911 s for 2.020 GB (the latter includes
packaging failure overhead). Do not replay completed originals or turn selected
recalls into an end-to-end SLA. The prior failed window actually lasted
**5,814.115 s** before recovery; that is not a target estimate.

Measure online preparation, held-admission interruption, per-batch packing/B
recall/checkpoint, closure, ordinary release and postrelease UI separately.
Report a range after demand and representative throughput are known. Preserve
existing 600 s verified-data no-progress watchdog and 300 s recovery grace;
requests, waits and sequence-only ticks earn no progress. Neither is a total
maintenance deadline or recovery guarantee.

## Exact safe launch sequence, after all gates pass

1. Read package-v5 PREPARED/source/NEXT_INPUTS; verify hashes, completed journal,
   normal-B dependency and absence of ATTEMPT/active controller. Reconcile any
   uncertain attempt; never remove an ATTEMPT/foreign lock to retry. Never run
   consumed a088, old raw-first controllers or old pause-installing preparers.
2. Finish admissible demand/preparation while online; verify current software/
   complete frontend recovery. Retain actual old Reader identity and SDK preload
   order. No reader restart or new agent is required.
3. At the authorized window, reconcile/lock all five watcher ledgers and native
   queues. Install only the owned global dispatch hold at the shared dispatcher
   after reconciliation. Monitoring/timer/notifications/config remain active.
   Save exact original bytes/mode and five config hashes. If arming fails,
   restore this owned pause after proving ordinary service; leave no orphan hold.
4. Seal new immutable inputs/manifests with `qualified_single_native_operation`
   only after validation. Pin actual self_source, current host/owner inputs,
   fresh pause/restore helper and complete recovery-source list; keep no automatic
   wake and completed-batch exclusion. Persist exact argv and input SHA256 in a
   final launch receipt. Its filename/hash cannot truthfully be supplied now:
   fresh pause/boundary do not exist. **Today's inputs must not be supervised.**
5. Existing exact command ABI (resolve arguments from that final immutable receipt,
   not ambient variables or old CURRENT pointers):

   ```text
   python3 -B -u <sealed controller-v4.private.py> preflight --inputs <new immutable armed inputs> --sha256 <verified input SHA256>
   python3 -B -u <same sealed controller-v4.private.py> supervise --inputs <same inputs> --sha256 <same SHA256>
   ```

   Run once via the existing single owned native host chain after this execution
   finishes. The supervisor owns controller.lock; worker creates ATTEMPT O_EXCL.
   No provider call, new goal, wake or second continuation loop substitutes.
6. Same normal B context: establish owned maintenance route/ingress holds and
   prove quiet; independently restore the actual current-main SQLite API
   checkpoint with integrity/schema/metadata and recovery controls. Then release
   authentic capacity, freeze verified cgroups and retain the SAME genuine
   lock FD/WriterFence. Adopt current aware readers without restart. Reverify the
   completed four, sidecars, Rust EOF/version seals and immutable B dependencies.
7. Verify private history/review/settings/queues; refreeze under SAME boundary.
   Observed CAS must equal committed union. Select terminal/closed remaining
   files excluding that union. Each admitted batch: pack and actual benefit
   filter; exact independent normal-B original full-EOF restore; serial same-owner
   context switch; actual custody seal; Rust readback; `convert_next_held` ONLY;
   immutable journal/seal/B checkpoint. Only then retire verified NEW duplicate
   staging under exact identities/kernel exclusion. Preserve primary/old objects.
8. Accept ALL-store closure including unreferenced objects/metadata: independent
   local carrier extraction AND normal-B full-carrier restore, tied by full
   SHA256/complete union/restore recipe. Verify final SQL/software/frontend/
   controls. Measure new-run allocated baseline/delta, actual descriptor release
   and filesystem samples; never recredit earlier batches/offload/Nov14 cleanup.
9. Release with independent lossless compatible-service proof and unchanged
   current DB/review/settings/queue fingerprints. Reacquire actual capacity,
   remove ONLY owned ingress/runtime holds, retain permanent aware boot controls,
   restore ordinary public route and close B/RAM contexts. Verify public desktop/
   mobile/history/review/settings/queue rendering; do not submit queued messages
   or alter saved settings for the test.
10. Restore exact WakeWatch bytes/mode and unchanged five configurations; remove
    ONLY owned hold after ordinary route/compatible services/capacity proof.
    Observe five normal timer updates and documented status/check, with no
    synthetic wake. Seal final RESULT, RECLAMATION, PHYSICAL_RELEASE, service/UI
    and WAKEWATCH_RESTORATION_VERIFIED receipts. A worker RESULT alone is not
    proof of later supervisor restoration.

## Recovery by failure stage

- Before host boundary: no replacement. Close owned B context; preserve evidence.
  Restore a newly installed owned dispatch pause after ordinary-service proof.
- Boundary held before adoption: reconcile a lost capacity-release reply against
  authenticated status and locked persisted state; never infer no release from
  an unset in-memory receipt. Use actual host journal/custody to recover the
  SAME aware owners. Preserve latest DB and inputs; never substitute old SQL.
- After adoption/new commit: core rollback covers ONLY failing current batch.
  Keep earlier commits/manifests/journals/B epochs. Prove mixed raw/CAS exact
  original hashes/sidecars, Rust EOF/physical-version seals, committed union,
  aware identities and unchanged review/settings/queue fingerprints. Use
  `recover_compatible` independent lossless proof and normal host release.
  Preserve the strict failure; do not rerun its failed checker as recovery proof.
- If lossless/custody/recovery proof fails: retain owned maintenance and all
  sources/receipts; record RECOVERY_FAILURE. Do not thaw, fake an FD with JSON,
  clear foreign leases, replay ATTEMPT or restore dispatch over held maintenance.
  Reconcile exact live operation and acquire fresh genuine custody before a
  separately sealed recovery invocation. The consumed a088 recover-only helper
  is historical evidence, not a reusable command.
- Unaware fallback requires restoration/verification of EVERY installed manifest
  across ALL batches to exact raw originals/sidecars under qualified custody.
  Restoring only current batch is insufficient. Prefer continued aware service.

First four remain complete: **827,506,688 allocated B net log recovery**. Approved
build offload separately released **303,202,304 allocated B**. Neither is new
recovery this planning turn. Actual deployed native runtime remains **0.159.2**:
retained initial response changed from 8 turns/10,746,496 B to 0 turns/5,126 B
(99.9523% fewer initial bytes). That is not total future-growth measurement;
isolated 0.166 qualification is not deployed-runtime evidence.
