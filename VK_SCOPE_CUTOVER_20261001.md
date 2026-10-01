# October 1 Evening AutoSwitch Cutover

## Final State: Blue Recovered, Green Not Deployed

Attempt20261001T202033Z is consumed. Blue's original PID1504649 is serving5301
and vibe.local using the same latest data. Candidate Green never started.
CodexUsage restarted as2365629; monitoring and external writers resumed.
No older database was restored and no second attempt was made.

The final backup detected newly created zero-length WAL files for goals_1.sqlite
and thread_history_1.sqlite, with unchanged database files and no logical changes.
A real SQLite regression reproduced this: the backup's read-only connection
creates empty sidecars when the last agent has closed a WAL database. The check
correctly refused certification, but preparation lacked this closed-database
case. Do not label the archive a successful frozen backup or the failure a
successful deployment.

The fix is on the separate preparation-tool branch: only for a verified fenced
database with neither WAL nor rollback-journal sidecar, copy its primary file
into private SSD staging before SQLite opens it. Recheck source generations and
sidecars; keep the final journal/fence assertions. Databases with committed WAL
frames still use normal SQLite backup, never a primary-file-only copy. All73
focused tests pass, including the reproduced failure and committed-WAL recovery.
The consumed deployment package was not changed into a retry. A new package
binding and fresh cutover approval are still required.

The correction is committed and pushed as c09181eed on
`fix/vk-production-preparation-costs` in open PR133. It is not merged or installed
into the consumed package. Formatting, Ops governance and diff checks also pass;
application-wide tests were not repeated for this external Python correction.
GitHub currently reports PR133 as conflicting with staging. Resolve that
integration conflict and validate the merged tool source before packaging it;
the pushed fix alone is not cutover readiness.

Recovery acceptance passes: database quick_check, all pre-boundary entity IDs,
protected values,342 attachment hashes and6046 native thread records. The2282
historically missing rollouts remain unchanged. One global draft record has only
a newer updated_at timestamp; its payload and creation time are byte-identical.
This precise exception is recorded rather than excluding scratch preferences.
The original native thread and model settings resumed; CU imported its decision
and turn events; runtime remains0.159.2 with the same private telemetry feed.
Attachment90de611c-1bbc-4718-9302-b989b471a0c6 passed upload/download. Desktop1440px
and mobile390px browser checks show all12 saved messages and working WebSockets
at https://vibe.local with no JavaScript errors. These are browser viewports,
not physical-phone tests. Existing Steer/Stop/goal evidence belongs to the same
unchanged incumbent; no new agent/goal exercise was claimed.

The additional live menu check passes all seven models, low/medium/high/xhigh
reasoning and the V2 routing controls at both viewport sizes. That inspection
blocked all API mutations and left the production model selection unchanged.

A fresh online backup after recovery was verified on Desktop in 35.5 seconds:
`delta--29662dd180ad40faa0cd417a501f1313.tar.zst`, 189904870 bytes, SHA256
31c5fdae31ef48b09b1550b2c7e103116ac70055ac6825734d06f73875805cf7.
It snapshots nine databases and retains 64 reusable database proofs. This is
an online recovery checkpoint, not certification of the failed frozen boundary.

Known warning classes remain: historical missing cache image0fa37354..., unknown
native-item filtering and reconnect subscriber lag. Persisted histories pass;
these warnings are not described as fixed or as a clean application log.

Preparation reached readiness in18m45s. Another11m25s elapsed before the final
other agent finished, followed by fresh checks and approval binding. The attempt
returned to Blue about33m31s after the original request, with roughly35 seconds
of interruption. This is not a successful restart timing. Recovery diagnosis and
acceptance are additional time and the earlier source agent's work was reused.

## Authority And Source

The operator requested preparation and conditional cutover at
2026-10-01T19:47:42Z, once all other agents and queued work have stopped.
This maintenance conversation owns the interruption. The AutoSwitch source
agent's earlier activation hold remains historical; it does not authorize that
agent to restart VK.

Production remains Blue PID1504649 until the independent controller records a
successful switch. Candidate Green is
`vibe-kanban-green-autoswitch-scope-20261001.service` on5411/5412.
The release task is `/mnt/vk-storage/vk-autoswitch-scope-release-20261001`.
Read `PROGRESS.md`, `cutover-attempt.json` when present, and the referenced status
before acting. Never repeat a consumed handover.

Main95deaafe6 and stagingb0f4c10a9 contain the identical complete source tree
1009e42a04d7265a7a03d262381309df267d578a. The hotfix/main and staging-backfill
PRs135/136 and134/137 already landed; another promotion would not change files.
All ten PR136 checks passed. Candidate version is0.1.42, runtime0.159.2.
Both remote refs are checked again before interruption, not just main.

The prepared backend includes independent-task routing-scope correction,
same-session Shadow preference preservation and metadata-only catalog renewal.
The rollback-compatible trace representation passed an incumbent-reader test.
Frontend assets are equivalent to the already served8d4b9ead2 frontend; its index
SHA256 is346ecc8d9d04f10608a6d36b0a2815346e08a278c651311ffbcd2f3489a00e01.

## Preparation Reuse

Reuse the source agent's exact build, private acceptance, real handover rehearsal,
full Desktop checkpoint and isolated restore proof. Do not rebuild, recopy the
entire machine, or repeat paid model trials for an unchanged identity. The
metadata/runtime check still requires the same launcher, account, Codex home,
seven models and shared private VK/CU telemetry feed.

The existing cached exclusion checks and strict direct-LAN resumable transport
are in use. Bulk preparation runs with the tested PR133 independent worker,
pinned tool commitb954bfc7b, outside the maintenance agent's memory group.
PR133 remains a separate source-tool review; this does not claim it was merged.

The source agent's controller initially targeted that agent's conversation.
Corrected it to maintenance session75bc68d4-aa55-4914-a695-f20c46a13e4c and native
thread01a03e74-2c1a-72f0-9e00-8e4293fe910d; added tests. Corrected stale Blue/Green
status labels and required both main and staging refs to match before cutover.

Two directory renames by active work invalidated the older watcher's blanket
coverage assertion. A bounded fallback requires observed move events and current
kernel watch coverage, recopies the entire affected generated-video subtree
on every capture, and independently hashes it for both final-boundary checks.
It does not erase the original errors or certify uninterrupted tracking.
Unknown moves, root loss, missing watches and overflow still block deployment.
Ordinary deletion evidence remains independently validated.

All45 focused controller, backup, writer, journal and subtree tests pass. The
first successful incremental refresh took68.99 seconds, delivered554084322 bytes
to Desktop, snapshotted8 databases and retained63 reusable database proofs.
Its receipt is in the task's `online-backup-result.json` and archive
`delta--b8d214249a664fdb9def78a7780ed34f.tar.zst`. The initial failed attempt
did not modify production or advance the backup chain.

## Acceptance And Timing

Preparation is not live acceptance. Check software-package restoration, fresh
execution and queue drain, current external writer identities, the final fenced
Desktop delta, sole capacity ownership, routed binary/frontend, original-thread
continuity, saved messages/model preferences, attachments and desktop/mobile
entrypoints. Retain existing goal/steer/stop evidence where code is unchanged;
state what is newly exercised. Preserve historical missing-rollout exceptions.

Blue recovery uses its retained process with the same latest data. Never copy an
old backup over production. The controller resumes this original thread once;
finish live acceptance and send exactly one final Ops report afterward.

Measure this task from19:47:42Z, separating ready-to-switch time, agent-drain
waiting, final capture/switch and acceptance. The source agent previously spent
time building and validating this package; reuse is not proof that its earlier
work took no time. The consumed attempt failed; its timing cannot establish a
successful restart speedup. The recovery outcome and off-machine evidence receipt
are recorded separately under the release task's `recovery-outcome.json`.
