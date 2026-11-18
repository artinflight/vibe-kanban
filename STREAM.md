# Finish backward deduplication — 18 November 2026

The full user goal is active. Only the four earlier archives are installed;
historical net recovery827,506,688B is not recredited. No new production conversion,
maintenance, dispatch pause or backup payload capture occurred during this turn.
The production-window question is pending: repository restart protocol requires
explicit cutover approval. Do not interpret elapsed time as approval.

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
