# Green Cutover Readiness, October 1

## October 2 Correction

The prior completion claim missed workspace attention acceptance. Issue statuses
and unread turn flags are different. The frontend repair069cb835d (PR138) is now
installed in Blue and Green: explicit review replaces automatic clearing, and
older actionable items remain visible past50. Only28 proven missing flags across
11 workspaces were restored; live1440/390px checks show16 attention workspaces.
Read VK_ATTENTION_PRESERVATION.md and the refreshed current readiness/software
receipts. The original backend release and28.44-second private handover evidence
are reused, not claims of a new production cutover or guaranteed downtime.
CU's already-live Android0.4.0 page/APK is preserved without runtime changes.
Activation still requires current agent/queue drain and operator approval; do not
interpret the prematurely completed native goal or historical readiness as a pass
of that volatile gate. Old tabs must reload to receive the repaired frontend.

## Current State

Blue1504649 remains production at vibe.local, main329963d18, VK0.1.42 and
Codex0.159.2. No production freeze, route switch, old-database restore or new
maintenance conversation occurred during this preparation.

Green is running as an isolated test instance, unit
vk-green-ready-preview-20261001.service, loopback5421, serverPID2790710.
It has a fresh production app-data copy and separate writable native home, cache
and fixture worktrees. Filesystem isolation denies access to production paths
and credentials. Tests use an offline native provider; the real production
launcher/account/home and model proof are checked separately without inference.
This test copy is not the data source for production activation.

Green's prepared production unit remains inactive on5411. At a separately
approved switch it opens the SAME latest authoritative production data after
Blue releases ownership and is frozen. Blue stays loaded for latest-data cutback.

Application source is main95deaafe6/stagingb0f4c10a9, identical tree
1009e42a04d7265a7a03d262381309df267d578a. Actual running test binary SHA256 is
e2120644ec026eee46f987327b2e98a7ea0e2be79f89e6e518cb8493b2612e12.
It includes scope demotion, Shadow continuity and metadata-only model renewal,
with the compatibility correction for Blue's older trace reader. The preserved
frontend is index-BAHizUjd.js. Exact-tree CI/build evidence was checked and reused;
there was no unnecessary application rebuild or repeated broad native suite.

## Corrected Tools

PR133 document conflicts were reconciled in856066872; af0eb4369 adds single-copy
fenced snapshots and streamed archive verification. Both are committed/pushed.
The external tools are included in the new package independently of the backend
binary. PR133 remains open, not merged; that is not an absent runtime fix.

The empty-WAL failure is fixed without ignoring unexpected writes. For verified
fenced databases with no WAL or rollback journal, copy the primary once into a
private snapshot, fully integrity-check it there, and validate unchanged source
generations, journals and writer identities. Immutable reads apply ONLY to that
private snapshot. Databases with sidecars retain normal SQLite backup, including
committed WAL frames. Streamed archive validation hashes the exact decompressed
snapshot members and manifest; missing, duplicate or mismatched members fail.
Online capture/resume extraction format is unchanged.

All77 focused tool regressions and45 package/controller/writer regressions pass.
Formatting, Ops and diff checks pass. No application-wide suite was rerun for
these external Python changes. Application acceptance is described below.

## Acceptance And Timing

The candidate passes same-native-thread continuation, Turn Steer within the
existing execution, Stop cancellation, explicit goal completion, attachment
upload/download, scope correction and preservation of12 saved messages.
Desktop1440px and mobile390px browser checks pass seven models and low/medium/
high/xhigh reasoning, saved-message rendering and WebSockets with no JS errors.
These are viewport tests, not a physical-phone test. A fixture-log interleaving
error was fixed by binding evidence to execution/thread IDs, then rerun successfully.

CLI0.159.2, the exact unchanged launcher/account/home and common private
VK_ROUTING_EVENTS_FILE/CU_ROUTING_EVENTS_FILE are verified. The seven-model proof
expires October2 at16:10:26 UTC; only a bounded availability check is needed if it
expires or identity changes. No paid model inference was repeated.

The production-sized optimized rehearsal forced nine closed database copies,
861847552 bytes total, dirty. Measured handover:28.44 seconds, of which26.69 was
final capture with Desktop verification. Four real-binary cases passed: backup
failure recovery, successful latest-data handover, same-process cutback retaining
new writes/settings/models, and repeated recovery. A Desktop-downloaded full
restore also passed. Production was never involved in those switches.

About30 seconds is the live target, not a hard guarantee. CU coordination and
live preservation checks add overhead not modeled by the private fixture.
Unoptimized trials measured60-71 seconds; those are retained, not omitted from
the record. Large tests must use the independent4G-high/6G-max bulk worker and
direct Desktop transport both ways, not the agent's1.5G-high cgroup. Generated
test extractions were retired only after their archive/restore checks passed;
archives, receipts and all live user data remain.

## Handoff And Approval

New package: /mnt/vk-storage/vk-green-ready-20261001.
Read readiness.json, software-package-receipt.json and PROGRESS.md. The software
receipt must prove Desktop checksum and downloaded restoration of this exact
readiness hash. Current final inventory at readiness: only this maintenance
execution active; zero queued messages. Recheck immediately before switching.

Verified software archive: maintenance-software-20261001T212155Z.tar.zst,
315050389 bytes, Desktop SHA256
f74f954addbe83a0a7534c56e8aef88a1350cb0271dfb0309cca7afaba6200f1.
Downloaded restoration verified1969 files and readiness SHA256
a91db24a785890cfc0cac7546d44d3c78667f585cfe003c17342532ac25c9b0a.

The reusable online data chain and new software package are stored on Desktop
B:/vk-backups/vk-autoswitch-scope-release-20261001. The latest online receipt is
online-backup-result.json; that is not a substitute for final fenced capture.
It includes updates made while preparation runs. The preapproved backup scope,
original native history paths and2282 historical missing-rollout exceptions are
preserved. Never hide or claim to have repaired those old exceptions.

Fresh operator cutover approval is still required. Record it in
maintenance-request.json, then perform an online incremental refresh while Blue
remains usable and bind approval with bind_maintenance_approval.py after fresh
drain/source/writer checks. The independent unit is
vk-green-ready-controller-20261001.service; its OnFailure recovery is
vk-green-ready-recovery-20261001.service. Do not start either during preparation.
The frozen capture timeout is45 seconds; failure returns to the current data.
No cutover-attempt.json or cutover-approval.json should exist until authorization.

Continue original session75bc68d4-aa55-4914-a695-f20c46a13e4c/native thread
01a03e74-2c1a-72f0-9e00-8e4293fe910d after switching for live acceptance.
Never replay the consumed202033Z package or use its old approval. Never overwrite
production with the preview copy or an older backup. Report exactly once after
the actual handover's acceptance and durable documentation.
