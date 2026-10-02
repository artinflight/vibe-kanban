# Attention Incident And Recovery, October 2

## October 2: Stale Restoration Corrected, Exact Loss Boundary Unproven

The earlier claim that all 28 flags were proven missing was incorrect. The repair
at 01:53:08 UTC unioned unread turns from several snapshots, including
`db.v2.sqlite.backup-build-local-2026-10-01T140820752Z.sqlite`. Copying that old
database into a newer backup did not make its review state current. Sixteen flags
were sourced only from that historical build copy; actual production snapshots
show their later read transitions. The recovery incorrectly revived them.

At 10:20:39 UTC, a targeted transaction undid 13 of those stale flag writes. Three
others had already been reviewed again today and were left untouched. Each write
required the exact earlier repair timestamp and unseen flag, with a completed
execution and nonarchived workspace. Every other flag, original turn content/ID,
and every other database table was checked unchanged inside the transaction.
The production database was not replaced, and no service was restarted.

The first operator loss report was October 1 at 23:37:11 UTC. Verified production
backups show read transitions at different times, not one proven bulk database
wipe. Five recent workspace flags cleared between 20:53:01 and 20:55:31 UTC;
the last backup before that group is 20:37:32 UTC, SHA256
d4eb37afe90f70ccdb9a76ac374ac60bd9fa1696a470dadcd962a19bc2ba07db.
Two later completions cleared at 21:08 and 21:17. Requester identity and visible-chat
state were not recorded, so these timestamps cannot distinguish actual review
from hidden-panel auto-clearing or prove the exact intended loss boundary.

The 20:37 production snapshot is proposed as the recent recovery boundary; the
operator has been asked to choose it or retain only the confirmed stale repair.
That further point-in-time reconciliation is not performed or certified here.
Do not silently choose a boundary, restore old databases, overwrite later reviews,
or mark all old workspaces read merely because their completions are old. Some old
unread items already existed in every relevant production snapshot.

Current audit, guarded repair, full current-state backup and Desktop SHA256
receipts are under /mnt/vk-storage/vk-attention-point-recovery-20261002 and
Desktop B:/vk-backups/vk-attention-point-recovery-20261002. Selection tests cover
later reads/unread changes, archived/running work, post-boundary completions and
unrelated rows. Earlier recovery notes below describe historical actions, not
proof of the operator's intended read/unread state.

## Recovery Evidence Requirements

Use one time-qualified authoritative production snapshot for the chosen boundary,
not a union of anything ever unread. Record the original source database path,
snapshot generation time and SHA256; the surrounding archive timestamp alone is
not sufficient. Build backups, isolated candidates and fixture databases are not
production authority. Preserve subsequent deliberate review/unread actions and
new completions. Use per-turn compare-and-set, verify unaffected data, and back up
the current state to Desktop before a repair. If missing audit data prevents an
exact reconstruction, state that limit and obtain the genuine boundary decision.

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

The now-invalidated recovery restored 28 original flags across 11 nonarchived
workspaces using compare-and-set, excluding interrupted executions. A current before-state,
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
