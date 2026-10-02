# Attention Incident And Recovery, October 2

## Operator Correction: Opening Clears Attention

The manual-only review behavior described below was rejected. It was an agent
overreach, not the desired design. Source caef5f3b6 in PR138 restores automatic
clearing when a visible chat opens, removes Mark reviewed, and keeps Mark unread.
Hidden mobile panels/background documents and summary polling do not clear
flags. Older actionable items remain visible beyond50. Real isolated-database
tests and live read-only browser checks pass at1440/390px, with17 live attention
workspaces visible at test time. Tests did not change production review flags.
Both Blue and prepared Green frontends carry the correction; publication and
old-index recovery are checksum-verified on Desktop. Current evidence is
open-chat-* under /mnt/vk-storage/vk-attention-recovery-20261002. Old tabs reload
for the corrected code. The operator explicitly authorizes the separate backend
cutover; read the independent attempt status for its outcome.

## Earlier Incident

The agent failed to verify the full reported state and stopped too early.
Matching issue/task statuses did not establish that workspace unread/review flags
survived. The earlier completed goal and readiness answer were therefore not
supported by complete acceptance evidence.

Same-day checksum-verified backups identify original completed turns whose seen
flags changed. The prior frontend cleared entire workspaces on provider mount,
even with mobile chat hidden; pagination also hid actionable items beyond50.
The individual historical requesters are not recorded, so do not invent blame.

Code069cb835d in PR138 replaces automatic clearing with explicit Mark reviewed
and keeps actionable items in the accordion beyond50. The validated frontend is
installed in live Blue and prepared Green, retaining old immutable assets and
Desktop-backed index rollback. No backend was restarted or production route
changed. Old open tabs must reload to use the fix.

The recovery restored28 original flags across11 nonarchived workspaces using
compare-and-set, excluding interrupted executions. A current before-state,
original flag plan, repair result and frontend bundle are SHA256-verified on
Desktop B:/vk-backups/vk-attention-recovery-20261002. Production was not replaced
with an older database. Original prompts, summaries, execution IDs, issue
statuses and12 saved messages remain intact.

Desktop1440/mobile390 browser tests show16 attention workspaces, including old
entries. Navigation sends no seen request; explicit review succeeds against
Green's isolated copy only. Read-only browser tests must permit POST
/api/workspaces/summaries, or status hydration has not actually been tested.
Physical-phone testing and the full Rust workspace suite were not rerun for this
frontend-only correction.

The new unused Green package binds this source overlay and preserves CU's
already-live Android0.4.0 page/download. CU runtime/configuration is unchanged.
Current artifact receipts and agent/queue drain govern activation, not the old
completed goal. Never reuse the failed handover or restore old data over prod.
Prepared Green still uses the latest authoritative production data at activation;
its isolated preview is never the source of production data.

Application/source worktree: /mnt/vk-storage/vk-attention-recovery-20261002/source.
Runtime/recovery evidence: /mnt/vk-storage/vk-attention-recovery-20261002.
Readiness package: /mnt/vk-storage/vk-green-ready-20261001.
