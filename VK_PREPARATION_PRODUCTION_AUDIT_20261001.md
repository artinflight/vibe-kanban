# October 1 Preparation-Time Audit

## Evening Closed-Database Follow-Up

Green preparation exposed additional duplicate I/O after the empty-WAL fix.
Fully fenced checkpointed databases now use one private copy, with integrity
verification; frozen archive contents are streamed and hashed instead of being
extracted and reread. All77 focused regressions pass. Online backup/resume format,
committed WAL handling, final fence checks and Desktop checksum requirements are
unchanged. No source primary-file copy is accepted without a verified fence and
absence of WAL/rollback sidecars. The running production instance is untouched.

The measured package is /mnt/vk-storage/vk-green-ready-20261001. It retains the
earlier consumed attempt separately and runs an isolated candidate from current
staging. Its scale-optimized-rehearsal result, not the8.7-second tiny fixture,
determines the proposed interruption. Read that receipt and the final readiness
manifest before approval. The optimized production-sized rehearsal passed in
28.44 seconds (26.69-second fenced capture, including Desktop verification).
All four recovery/handover cases and the Desktop-downloaded full restore passed.
Nine closed production database copies were forced dirty. This is a private
same-binary rehearsal, not measured production downtime; CU coordination and live
preservation checks can add overhead. The live target is about30 seconds, not a
guaranteed deadline. Earlier unoptimized trials took60-71 seconds and are retained
as evidence rather than described as successful short windows.

## Outcome And Clock

AutoSwitch V2 is deployed on Blue at `https://vibe.local`, production main
`329963d183943f76590a794ae8ee25c89d291e63`, version `0.1.42`, Codex `0.159.2`.
The application tree is accepted PR130 tree `b804fcbb9`; build provenance remains
staging `adfa7c051`. PR132 repaired ancestry without changing that tree. Green's
original process `2506054` is frozen for latest-data cutback. No old database
replaced production and no replacement maintenance thread was created.

The operator was right: these improvements did not make this first production
preparation quick. A 19-second switch does not answer an 87-minute preparation
complaint. These external tooling changes do not need another backend restart.

| Phase | Measured time | Evidence |
| --- | --- | --- |
| Request until V2 staging merge | 22m04s | Request09:19:04.987Z; PR130 merge09:41:09Z |
| Initial preparation after merge | 86m39s | preparation-completion.json, ready11:07:48.079Z |
| Request through initial preparation | 108m43s | Includes discovery and merge wait |
| Full isolated restore, within preparation | 26m44s | online-restore-check.json,1604.235s |
| Operator working/decision interval | 111m23s | 11:07:48.079Z to next request12:59:10.753Z |
| Resumed preparation until switch start | About29m17s | Next request to132828Z; promotion and monitor fixes |
| Final interruption | 19.37s | Controller status.json |
| Frozen backup, within interruption | 14.23s | boundary.json,56,974,217bytes verified on Desktop |

Frontend/backend builds took191.73s/541.87s, within preparation. The first
20.61GB checkpoint covered74.88GB of logical work/state. Its complete capture
duration is not reliably separated from repair/resumed delivery in surviving
receipts. Do not invent an exact allocation of the remaining minutes. Live
acceptance and this audit are extra work while Blue is usable.

Receipts: `/mnt/vk-storage/vk-blue-autoswitch-v2-20261001`. Desktop backups:
`B:/vk-backups/vk-blue-autoswitch-v2-20261001`.

## Why Preparation Stayed Slow

- PR129's roughly17MB fixture proved warm reuse, not production preparation time
  or elimination of a first checkpoint.
- Backup scanning resolved dozens of exclusion paths for every file. Ordinary
  directory deletion falsely invalidated watches; CLI scratch vanished during
  online inventory.
- Initial Desktop delivery used a slow relayed Tailscale route. Verified direct
  LAN, SFTP create/resume handling and SSH exec-channel recovery needed repairs.
- Restore ran inside Codex's1.5GB memory-high limit before moving to a bounded
  4GB-high/6GB-max worker. Heavy page-cache throttling was observed. Production
  and agent resource limits were not changed.
- Restore discovery decompressed the whole archive to find a manifest at its
  end, then decompressed again for recovery. Per-file Python restoration and
  storage throughput still cost time after removing the extra discovery pass.
- Frontend materialization left `.previous` output in Git source, invalidating
  evidence after successful builds. Missing dual VK/CU dependency configuration
  was caught and corrected before activation.
- Staging lacked earlier main-promotion ancestry. PR132 reconciliation happened
  late rather than before expensive preparation.
- Monitor preflight demanded zero children despite ordinary metric sampling.
  Pausing only its parent could block child stdout pipes. Whole-service freezing
  fixed this and passed a real unchanged-DB/same-process thaw test.

Repairs, renewed packages and operator coordination consumed time. Stopping at
initial preparation readiness also divided the flow. Do not hide those costs
inside the final backup/switch duration.

## Corrections And Boundaries

Follow-up source: `fix/vk-production-preparation-costs`, based on staging
`a2733eea5`, at `/mnt/vk-storage/vk-preparation-production-20261001/source`.

- Compile equivalent exclusions once; recheck resolved targets before publication.
- Retain known nested deletion tombstones under watched parents. Root/watch
  loss, directory moves, overflow and replacement watchers still fail closed.
- Validate all archive warnings against journal evidence. Missing files qualify
  only within explicitly scoped online ephemeral roots. Unrelated omissions,
  permission failures and any frozen-boundary warning still fail.
- Persist completed online delivery state and deliver the same verified archive
  without recopying. Later writes stay due for the next delta. This never
  resumes or certifies a frozen production boundary.
- Use strict existing Desktop SSH identity, independent connections, correct
  SFTP create/resume and full remote SHA256. Direct address is explicit and does
  not change shared SSH aliases or authentication.
- Place new manifests first and end discovery once found. Full checksum and
  restoration-stream validation remain. Legacy manifest-last archives work.
- Retain materialization's old/temporary files outside Git source; check main
  ancestry early; provide bounded independent bulk jobs and whole-unit writer
  fencing. Writer-specific operation/child checks and approval remain required.

Keep the independently running journal, verified chain and applicable restore
evidence between preparations/turns. A package refresh or authorization delay
alone does not require a full copy or restore. Scope, journal, archives and
recovery-format evidence must remain valid; lost coverage still requires fresh
validation. Do transport, resource, writer-policy and ancestry checks early.

Keep active/queued work, settings, runtime identity, proof age, ownership and
final data boundaries uncached. Do not omit agent work, histories, messages,
settings, attachments, Git metadata or dirty/untracked files for speed. Never
replace current production with old data.

PR131's schema check failed at tool installation on cache-storage HTTP503 before
code validation. Its other checks passed; accepted same-tree PR130 evidence was
retained. Do not label the promotion run entirely green.

Observed warm phases: static runner7.56s, online catch-ups10.55s/29.98s, frozen
capture14.23s. These are not whole-deployment estimates. Measure the next complete
cold and warm request-to-ready intervals, separate from operator waiting,
interruption and acceptance, before promising quantified total savings.

## Evening Closed-WAL Regression

The202033Z attempt returned to the same Blue process before Green was started.
After agents closed their last connections, goals_1.sqlite and
thread_history_1.sqlite had no WAL files. The read-only backup reader itself
created empty WAL files, causing the correctly strict boundary assertion to
reject the archive. No logical database change or main-file change was recorded.

A new real SQLite/inotify test reproduced the failure before the correction.
Only for a verified fenced source with no WAL or rollback journal, the tool now
copies the database into private SSD staging before opening SQLite. It rechecks
the original generation/sidecars and retains all final journal/fence assertions.
Normal SQLite backup still handles sources with committed WAL frames; a second
test verifies those frames reach the restored database. The private temporary
copies are removed after readers close. Online behavior is unchanged. All73
focused tests pass. A fresh deployment package and new authorization remain
necessary; this source correction does not rerun a consumed handover.

This maintenance task reached initial readiness in18m45s by reusing prior source
build/acceptance and a restored full checkpoint. Another11m25s elapsed before
the final other agent finished. It returned to Blue33m31s after the request,
including final checks and approximately35s interruption. Recovery diagnosis and
acceptance took additional time. These are failed-attempt measurements, not a
successful faster deployment; prior source-agent preparation is not erased.
