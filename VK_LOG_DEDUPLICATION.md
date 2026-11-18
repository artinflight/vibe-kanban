# OP::Disk Space — lossless conversation log deduplication

Status (17 November 2026): compatible readers and native-resume prevention are
DEPLOYED; the first four lossless manifests are installed. Net first-batch
recovery is827,506,688 allocated bytes including object-directory cost. Full
reclamation remains unfinished. [Current continuation procedure](VK_LOG_RECLAMATION_READINESS.md)
excludes that completed batch and preserves all old recovery epochs. The next
production operation is prepared and unarmed; never replay the old consumed run.

## Cause, scope and preservation

The [disk investigation and prevention fix](VK_DUPLICATE_HISTORY_FIX.md) identify
replayed native `thread/resume` history as the main measured growth mechanism.
The exact-qualified `vibe-codex-executor/0.159.2` narrow-resume correction is
deployed in the qualified composite main build. Its exact allowlist also covers
qualified0.166.0, but the ACTUAL continued runtime remains0.159.2. It prevents historical
turns being returned on qualified resumes, retaining new output and native model
context. Other identities/versions still use their existing protocol; requalify
new native versions rather than widening that guard without tests.

Existing JSONL is archived losslessly, including every repeated message, malformed
historical byte, record boundary, Unicode character and final newline. No semantic
turn deletion, transcript repair or history completeness certification occurs.
An archive manifest remains at the original `<execution>.jsonl` relative path.
`processes/.log-objects/<sha256>.gz` holds content-defined, individually compressed
chunks, shared only within that session's processes directory. The ordered
manifest records original byte count/hash and each chunk's byte count/hash.
The current format is `VKLOGCAS1\n` followed by bounded JSON. Cuts occur between
16 KiB and 256 KiB (the final chunk may be shorter); content anchors resynchronise
after insertions. Compression savings and duplicate-chunk savings are distinct.

The backend reconstructs the original byte stream for raw/history readers,
streaming presentation, strict review reads, native-capture validation and
historical-recovery hashes. Existing review hashes, execution/session references,
capture state and recovered-final sidecars remain valid. Missing/corrupt objects
and incorrect manifest lengths/hashes fail reads. Existing size/framing limits
apply to reconstructed bytes. Archived files reject appends. New executions keep
ordinary JSONL capture; repeated historical resumes are prevented by the existing
executor fix. There is no new background job or automatic conversion of live logs.

Keep manifests and their entire `.log-objects` directory together. A chunk can be
referenced by many executions in the same session. Never delete objects when one
execution is removed. No object garbage collector or automatic retention change is
provided; whole-session removal already owns the complete session tree. No chunks
reference another session, native home, attachment, database or external file.
Storage owners must keep the tree private and immutable after verification.

## Measurement and offline preparation

Use `python3 scripts/log-dedup/log_dedup.py --help`. All operations leave source
files unchanged. `plan` is read-only. `pack` and `restore` require a new, disjoint
destination, refuse existing output trees and never install, overwrite, truncate
or delete an original. Interrupted/failed output without a successful receipt
is unsealed and must not be installed.

1. Follow the host disk-cleanup safety runbook. Check mounts and capacity first.
   Reconcile actual DB process/session identities, completion status, active writer
   and reader FDs, protected-history bindings and every external consumer.
   Freeze a JSON array of exact session-relative paths of the form
   `xx/<session-uuid>/processes/<execution-uuid>.jsonl`. Do not use a broad cleanup
   glob or assume a legacy file with no sidecar is complete. An unchanged scan is
   a source-version check, not a live-writer fence or proof of successful capture.
2. Put the list, plan and output under a named directory on mounted SSD. Avoid
   source/destination overlap. The following variables stand for reviewed paths;
   they are not an approved production file list:

   ```bash
   python3 scripts/log-dedup/log_dedup.py plan --root "$SOURCE_SESSIONS" --files "$EXACT_FILES" > "$EVIDENCE/plan.json"
   python3 scripts/log-dedup/log_dedup.py pack --plan "$EVIDENCE/plan.json" --destination "$EVIDENCE/archive"
   python3 scripts/log-dedup/log_dedup.py verify --root "$EVIDENCE/archive"
   cargo run --offline --locked -p utils --example verify_log_archive -- "$EVIDENCE/archive"
   python3 scripts/log-dedup/log_dedup.py restore --root "$EVIDENCE/archive" --destination "$EVIDENCE/restored"
   ```

   Use the existing owned SSD Cargo target, offline dependency cache, one build
   job and disabled incremental compilation; these examples do not set build
   ownership. The Rust example checks every reconstructed byte against the receipt
   using the backend reader, independently of the Python packer.

3. Packing refuses symlink/special-file sources, changed identities/content,
   pending capture sidecars and stale plans. It copies `capture.json` and
   `recovered-final.json` sidecars exactly. The plan binds all source versions and
   sidecar hashes; packing checks the entire set before and after construction,
   validates each archive, fsyncs files/directories and seals `receipt.json`.
   Review any other adjacent files; retain them unchanged during installation.
   File access/ownership/ACL policy must be reconciled: new objects and restored
   files are private (0600), not copies of arbitrary historical ACLs or owners.
4. Independently hash-compare restored originals and sidecars, check actual
   allocated blocks including directories and receipts, and record capacity.
   The plan's 4 KiB rounded allocation is an estimate excluding directory metadata;
   `raw_bytes - archive_payload_bytes` is not actual filesystem recovery.
   Separate duplicate-chunk reduction from compression. Do not extrapolate a
   selected sample to the whole 104.85 GiB investigation population.

## Production requirements and rollback

Follow [the deployment runbook](VK_AGENT_DEPLOYMENT_RUNBOOK.md),
[backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md) and
[restart protocol](VK_BACKEND_RESTART_PROTOCOL.md). This document adds no restart,
agent interruption, source-retirement or live migration authorization.

- Integrate through staging and pass required source checks. Build the backend
  with both prevention and archive readers, exact private retained-history inputs,
  current service/capacity/approval settings and all current live fixes. Preserve
  current frontend/assets. There is no schema or shared-type change.
- Reopen and verify a current restore-grade Desktop B backup containing original
  JSONL, DB and sidecars. Backups of an archived tree must include all objects.
  Rehearse candidate → compatible fallback → candidate against current copied data
  and a later-write sentinel. Include protected/recent/recovered history, review
  hashes, pagination, ordinary send/resume, approvals, queues/settings and attachment
  retrieval. Real provider QA needs its own bounded authorization.
- At an authorized drained boundary, hold ingress/writer fences, recheck exact
  allowlisted identities and all consumers, then prepare/revalidate the final
  frozen plan. Install objects durably **before** manifests. Preserve all unlisted
  files and references. Switching a completed original requires atomic replacement
  plus directory sync under deployment custody; this tool deliberately does not
  perform that production replacement. Retire original payloads only within the
  separately reviewed exact-file recovery procedure. Open old descriptors can
  delay block recovery; verify allocation rather than assuming it.
- Old binaries and generic `cat`/direct-JSONL tools cannot interpret manifests.
  Audit external scripts/readers before installing any manifests. Give those
  consumers reconstructed copies or archive-aware readers. For backend fallback,
  either retain these readers or restore raw JSONL at each original path first,
  byte/hash/sidecar verified from the archive or current backup. Never point an
  archive-unaware backend at converted logs, and never restore an old DB over newer
  writes. Reserve actual capacity for reconstruction before converting.
- After deployment, prove serving hash and preserved DB/native/protected-reader
  identities. Measure an actual Vibe resume's persisted size and returned turns;
  validate history/review/read/send behavior through the public route. Observe
  matched workload windows before claiming ongoing growth reduction. Future
  offline batches may archive newly completed logs after the same owner, consumer,
  version and recovery checks. No timer is enabled by this change.

## Validation and measured recovery

A frozen six-file sample covers the two identified T18 and PODs Weekly captures,
a second capture in each session, and two OP::Disk Space logs. This is a selected
sample, not a census or a representative statistical estimate.

| Measurement                                                             | Verified bytes |
| ----------------------------------------------------------------------- | -------------: |
| Original logical JSONL                                                  |  1,089,013,599 |
| Original allocated file blocks                                          |  1,089,056,768 |
| Identical chunks stored once                                            |    293,726,709 |
| Unique chunks before compression                                        |    795,286,890 |
| Compressed unique objects                                               |    160,672,803 |
| Manifests                                                               |      4,222,283 |
| Actual archived tree allocation, including receipt/sidecars/directories |    237,555,712 |
| Measured recovery potential for this exact set                          |    851,501,056 |
| Production space actually reclaimed                                     |              0 |

That is **812.1 MiB (0.793 GiB), or 78.2%**, of measured allocated-block recovery
potential for the selected files. The packed tree has 32,174 regular files; budget
inode/directory overhead as well as bytes. Root and SSD inode headroom were checked.
The plan's estimate was 855,134,208 bytes; the actual measurement above includes
extra metadata and supersedes it. No whole-population recovery figure is verified.

The separate packed tree and complete restoration passed independent Python
hash comparisons of every restored original and sidecar. Source device/inode,
size, mtime, ctime and content hashes remained unchanged. Durable recovery and
production retirement still require the Desktop B workflow, not this rehearsal.

Ten Python migration regressions pass, covering restoration, repetition, malformed
historical bytes, corruption/missing references, traversal/symlinks, stale/pending
sources, change during packing, truncated gzip CLI failures and session isolation. Thirty-six Rust utility
tests pass, including six new archive/history/review-bound tests; one pre-existing
private retained-capture probe is ignored. Utility clippy (all targets, warnings
denied), full `pnpm run format`, ops governance and diff checks pass. The first
formatter attempt found broken canonical Node links; the successful run used the
existing standalone formatter without installing dependencies or retaining links.
Seven unchanged prevention regressions pass again in the previously qualified
executor binary; that is a cached-binary rerun, not a new executor build.

The actual Rust backend reader independently reconstructed and hash-verified all
six packed files (1,089,013,599 bytes), matching the Python receipt. After the full
restore comparison, only the eleven generated restoration log/sidecar copies were
retired by exact path and verified hash; originals and the packed tree remain.
That temporary-output cleanup is not production reclamation.
`cargo check --offline --locked -p server --lib` also passes, including the changed
historical-recovery reader. This is compilation, not a runnable release candidate;
the build used a dummy local frontend asset directory, not the served frontend. Full workspace tests, hosted CI, public
browser/history QA, live Vibe send/resume, deployed growth reduction and actual
reclaimed production space are not certified by these checks. No provider turn,
service restart, production data replacement, production log deletion or frontend
publication occurred. The live service readback still reports the investigation's
PID 645213 and original invocation identity.

Private evidence, exact paths, plans, source-version/hash checks, packed/restored
comparisons and validation logs: `/mnt/vk-storage/vk-log-dedup-20261103-0815/`.
Do not publish transcript objects, restored logs or private history bindings.


## Current production continuation — 17 November 2026

The final plan-only review and exact safe launch/recovery procedure are in
[VK_LOG_PRODUCTION_GO_NO_GO.md](VK_LOG_PRODUCTION_GO_NO_GO.md). Current decision
is NO-GO until peak allocation/remaining B demand, broader UI and fresh arming/
boundary gates pass. No maintenance or conversion was started for that review.

Use the fresh Vibe and Nightly owner handoffs and an unconsumed operation UUID,
never a consumed attempt. Fresh metadata measures 91,655,319,552 allocated bytes
including shared objects. Prior separate 31,572,000,768-byte Nov14 retirement
cannot be counted again. The completed four-log batch recovered 827,506,688
allocated bytes net including all canary object/directory costs. Further recovery
remains unverified; preserve and exclude that batch from every continuation.

During authorized downtime pause WakeWatch dispatch through the shared installed
Store.dispatch boundary after reconciliation, preserving monitoring and every
saved setting. Check unsettled deliveries and native durable/volatile queues;
preserve uncertain incoming prompts. Restore the exact prior dispatcher bytes,
remove only the owned hold, verify all five normal monitor ticks and transport
readiness, and report both pause and restoration. No synthetic paid wake is needed.

After a first batch's actual main/protected history acceptance, retain compatible
readers across every subsequent batch. A later failure restores only its current
batch; never boot an archive-unaware reader over earlier manifests. Keep immutable
per-batch custody/config epochs before resealing shared controller filenames.

The complete backup closure includes ALL affected session-local .log-objects,
including unreferenced files, plus manifests, sidecars, original directory/link
metadata and final software/control epochs. Bounded physical carriers may preserve
these bytes through the SAME Nightly owner-controls transport: independently
extract/hash/metadata-check each carrier and independently normally restore its
entire B bytes/hash/metadata. Bind both proofs by the exact full carrier SHA256 and
retain a complete union index and explicit restore procedure. No semantic turn
omission or prefix-only graph may substitute. Compatible binaries may be split
into exact contiguous parts with full-artifact hash/metadata reconstruction.

Own newly created SSD staging object replicas may retire only after the actual
production manifest/primary objects, independent B originals, immutable journal
and normal B control checkpoint pass; use a frozen exact inode/hash allowlist and
kernel consumer exclusion. Keep all primary objects, originals' backup epochs,
old preparation epochs and rollback recipes. Rehydrate exact staging replicas
from verified primary CAS before a separately admitted future raw rollback.

Exact0.166.0 native resume support was isolated and qualified without inference.
The real retained predeployment wire baseline reports0.159.2,8turns and
10,746,496 response bytes. Capture fragments must be joined through their actual
newline boundary before parsing the JSON response; inspecting only the first
101 capture records misses the multi-megabyte initial response. Retain byte/hash/
turn-count metadata without publishing conversation bodies. The retained actual
postdeployment native 0.159.2 response was zero historical turns / 5,126 bytes,
versus eight / 10,746,496 bytes before deployment (99.9523% fewer initial bytes).
This is initial-response evidence, not total future-growth measurement. An
isolated0.166 fixture is not deployed0.166 evidence. The successor build passed8
actual executor tests.
No automatic converter timer is enabled.


## Completion takeover qualification — 18 November 2026

The new inert completion-package-v9 integrates the corrected capacity-release
and journal-recovery helper, adaptive batch admission, complete physical accounting
and actual public history/settings/review/empty-queue acceptance. The original
package-v5 and every consumed attempt remain unchanged. This is prepared code;
no additional production conversion or reclamation is claimed yet.

Admission recalculates actual SSD availability before each batch. It includes
worst-case gzip expansion, object/directory blocks, copied sidecars, both staging
and publication copies, and raw rollback, retaining the unchanged3GiB reserve
and16MiB control allowance. Sources are ordered by size so smaller beneficial
conversions can release room for the larger ones. It never silently skips a
large source that fails capacity admission. Existing real writer/B/reader gates
remain mandatory. Physical accounting counts unique allocated inodes, directory
blocks, links without following them, and all named new preparation/staging roots;
logical compression estimates are not recovery credit.

All126 focused tests pass, including actual patched-host lost-reply recovery,
admission changes and physical accounting. Eight additional exact-package tests
pass, including real converted fixtures and corruption refusal. Four public
browser cases(two workspaces at1440/393px) render history, settings and the review
dialog and confirm actual empty queues; no page errors or operator writes were
sent. This is desktop/mobile viewport coverage, not physical-phone testing.

Fresh actual native0.159.2 startup again returned zero historical turns and1,826
response bytes, compared with the retained predeployment8turns/10,746,496bytes.
No extra provider/native request was generated for measurement. An ordinary
1,622.893second observation measured1,961,984 additional allocated log/object
bytes(1,955,286 logical bytes), with no new/missing log files, no archive
conversions and no executions created in that interval. The same active task
continued. This is one live workload observation, not a matched pre/post workload
experiment, daily forecast or claim that new output stops growing. The deployed
fix prevents initial historical replay for its qualified native identities; new
execution output still needs capacity monitoring and eventual retention policy.

Private growth evidence: completion-20261117-demand/GROWTH_MEASURED_v2.private.json
and its before/after inventories. V2 corrects only the workload-count query to
SQLite julianday timestamps; the original count-query failure is retained.
CURRENT_ACTIVE_RESUME.private.json retains only wire counts/hashes and identity.
Existing restore instructions above still apply: preserve complete session stores,
all objects including unreferenced ones, sidecars, SQL, exact compatible binaries,
frontend and normal-B recovery controls. Never start an unaware reader while any
manifest remains; restore exact original bytes under genuine custody first.


The inherited closure iterator omitted raw logs and other adjacent regular files
inside affected process directories. archive_closure.py now includes every regular
body recursively, records directory/link and hardlink metadata without following
links, and preserves unreferenced objects. Large bodies use bounded ordered
fragments. Independent extraction hashes their concatenation against the original
whole-file SHA256 across carriers; missing, reordered, duplicated, changed or
incomplete fragments refuse acceptance. Restore fragments into one separate inode,
verify complete length/hash, then apply metadata before publication. Five new
behavior tests cover full namespace inclusion, cross-carrier large bodies,
corruption/gap refusal and changed source versions. The v7 private restore recipe
and index record this protocol. No production closure acceptance is claimed yet.


The final unarmed candidate also caps actual original/control input bytes before
normal B writes. Uncertain control captures retain their charge; existing bodies
consume no new original-capture allowance. It rechecks remaining raw candidates
after successful passes until shared objects produce no further eligible benefit.
All3,366stable measured logs total91.105GB. Exact normal-B metadata matching leaves
9.118GB of missing bodies; this is not full restore acceptance. The conservatively
bounded sequence and fresh owner/B/SSD evidence are recorded in STREAM/HANDOFF.
Production interruption is awaiting the explicit window decision; the three
production outcome requirements remain open.
