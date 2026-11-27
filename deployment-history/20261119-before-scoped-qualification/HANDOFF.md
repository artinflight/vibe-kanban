# Pickup — scoped closed-log conversion, 18 November 2026

User authorized resolving the per-workspace blocker. Large workspaces remain
active. Preserve all current work and pending inputs; do not retire them. Existing
cutover approval persists, but interruption is explicitly deferred until tonight.
No exact start is scheduled. No production pause/conversion/restart occurred.
Native goal is paused; full backward reclamation remains unfinished.

Read STREAM.md and VK_SCOPED_LOG_CONVERSION.md. Source now has permanent
per-execution writer/converter locks, exact live protocol qualification and a
separate `controller.py --online` route using original and full archive-graph B
verification. Existing global custody is preserved separately. Current production
lacks the protocol and is correctly rejected. A qualified writer activation must
precede any online batch; no global pause is needed for the later bulk operation.

RUNNING: vk-scoped-log-release-v1-0815.service, wrapper exec58681, the sole build
lock/shared-target owner. E/scoped-release-v1/{RESULT,ARTIFACT}.private.json and
build.log hold outcome; do not duplicate. Actual utils integration is complete:
9 tests passed. Focused Python suite154 ran/151 passed/3 optional host skips.
Final format, governance and diff whitespace checks passed. No model/provider QA calls are authorized.

online_owner.py binds actual live reader identities/mounts/settings and refuses
old writers before B actions. nightly_graph.py uses the existing Nightly checkpoint
and independent normal restore, then reads actual immutable B bodies. A real
four-member/1,505B fixture passed twice, second time with staging absent; all B
contexts closed. This is not production selected-graph acceptance. The actual
protected reader has a read-only log mount. The full online host check refused
elevated memory PSI without relaxing thresholds; see E/SCOPED_PROTECTED_READONLY.private.json.

Prepare the release as a minimal overlay on the exact retained runtime source:
R/source-087319cc4 plus P/native-166-build/client.rs. All five edited existing Rust
files matched that runtime source before this change. Preserve private history
bindings and frontend. The new utils module must be included; all actual mutating
server/repair tools require protocol1. An old compatible-reader fallback disables
online conversion. After the deferred activation, bind the existing normal-B
owner, run one small beneficial scoped batch, validate ordinary public history,
review/settings/queues and unrelated writes, and measure actual physical recovery.

Model polling has ended to avoid supervising compilation with paid agent turns.
The resource-owned build continues independently and records success/artifact or
failure in E/scoped-release-v1. Collect that result before activation; a running
job is not a passing build. No cutover is scheduled and no new permission is
needed for the already-authorized work; preserve the deferred evening boundary.
Public page/API both returned200 with verified TLS in21ms/39ms during compilation.
This was availability only, not post-activation UI acceptance. Metadata-only audit
found no individual log above2GiB (largest324,499,915B); no body scan was repeated.

P=/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117.
E=P/efficiency-20261118; R=/mnt/vk-storage/vk-log-reader-release-20261104.
E/SCOPED_LIVE_GATE.private.json is the negative live protocol proof.
E/ACTIVE_WORKSPACE_CLOSED_LOGS.private.json is the82.425GB closed-log inventory.
Old v9 remains UNARMED; do not launch it automatically. All previous sizing,
lookup and efficiency jobs are terminal. No new reclamation is credited.
Changes uncommitted; draft PR291 unchanged. Preserve existing untracked cache files.

Full historical archive: [HANDOFF history](HANDOFF_HISTORY_20261017.md).
