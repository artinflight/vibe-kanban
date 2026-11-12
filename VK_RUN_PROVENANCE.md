# Automatic normal-run context provenance

This source change attaches local file observations to normal Vibe coding-agent
starts, follow-ups/resumptions and reviews. It does not depend on AutoSwitch,
routing mode, native goals or an agent remembering a command. Script-only setup,
cleanup and dev-server processes do not create provider-context records.

The starting point is Media Management staging commit
`4b2783612ad1a80ce1394d4f168cf0c36fd6cba2`,
[`tools/handoff/record_run.py`](https://github.com/artinflight/mediamanagement/blob/4b2783612ad1a80ce1394d4f168cf0c36fd6cba2/tools/handoff/record_run.py)
and its
[ordinary-run tracking guidance](https://github.com/artinflight/mediamanagement/blob/4b2783612ad1a80ce1394d4f168cf0c36fd6cba2/docs/CONTEXT_MANAGEMENT.md#ordinary-run-tracking).
Vibe reuses its version/hash/identity field names and conservative claim. This is
an extended lifecycle envelope, **not** an identical MM record or fingerprint.
No change to MM's checkout or another workspace is required.

## Lifecycle and location

`LocalContainerService::start_execution_inner` observes the actual
`workspace.container_ref` and the same effective working directory used by the
executor. It runs after workspace setup, before the final existing launch gates
and sole normal spawn. All existing admission, capacity, ownership, routing,
approval, spending and permission settings remain in force. Recording failure
only logs a fixed warning with the execution ID; it cannot authorize or block a
run. The existing exit monitor owns the observation and closes it before
commit/cleanup, queued follow-ups or finalisation can change the workspace.
Failed spawns drop the observation as interrupted. Stop uses that same existing
exit monitor; no stop/kill behaviour is added.

Each execution has one private, atomically replaced local record:

```text
<actual-workspace-root>/.vk-run-context/<execution-UUID>/record.json
```

The directory is alongside workspace repositories, not in a canonical source
checkout or a global user home. It is deliberately not served over HTTP or
written to the agent transcript. On Unix, new directories are 0700 and files
0600; existing non-private/symlink output directories are refused. An existing
execution directory is never overwritten by a repeated start. No DB migration,
API endpoint, new daemon, recurring job, model call or provider call is added.
Records follow the workspace's existing retention/lifecycle; no separate cleanup
policy is introduced. Preserve the record with CU exports before workspace
retirement when longer audit retention is needed.

## Selected files and version labels

Each source scope is identified by a path relative to the actual workspace:
`.` for the workspace root, each repository root, and each ancestor from the
provider's effective working directory back to the workspace root. This handles
multiple repositories and nested working directories without hashing the full
tree or following unrelated branches. It does not watch every nested directory
an agent might later visit.

Each scope records:

- `AGENTS.md`, `STATE.md`, `STREAM.md`, `HANDOFF.md`;
- `handoff.config.json`, including its own hash;
- MM's three routes: `docs/CONTEXT_MANAGEMENT.md`,
  `docs/WINDOWS_MEDIA_HANDOFF.md`, `docs/CURRENT_STATUS.md`;
- relative files explicitly named by `current` or `run_context_files` in that
  scope's `handoff.config.json`.

The optional config uses MM's existing `instruction_version` key. For example,
a repository can adopt the following metadata through its usual review process:

```json
{
  "instruction_version": "project-instructions-v1",
  "current": ["AGENTS.md", "STATE.md", "STREAM.md", "HANDOFF.md"],
  "run_context_files": ["VK_WORKFLOW.md", "VK_AGENT_DEPLOYMENT_RUNBOOK.md"]
}
```

Bump the label for adopted standing instruction/routing changes; normal state or
handoff updates still change the hashes without requiring a label bump. Absent
or invalid labels are `unversioned`, with an explicit unknown reason. No labels
are guessed from branch names, commits, today's files or old executions.

Reads are bounded to 1 MiB per file, 64 files per scope, 32 scopes and an 8 MiB
snapshot budget (the last bounded read can exceed that budget by up to 1 MiB).
Invalid config entries, exceeded limits, unreadable/special files and symlinks
produce unknown coverage instead of a broader scan. Absolute paths and `..`
are refused. Selected absent files have null hashes and `missing` state;
unreadable/rejected files have null hashes and `unavailable` state. Only hashes,
labels and metadata are saved; file contents and arbitrary config values are
never copied into the record.

## CU::Audit record contract

The envelope has `schema: "vk.run-context.v1"` and
`observationSchema: "mm.handoff-run.v1"`. Do not feed it to a reader that assumes
MM's unextended top-level layout. Important fields are:

| Field | Meaning |
| --- | --- |
| `workspaceId`, `sessionId`, `executionId` | Vibe IDs from the actual execution objects, not inferred environment or branch identities. |
| `workspaceRoot`, `workingDirectory` | Resolved actual workspace and effective provider cwd. |
| `usageSelector.execution_id` | Exact ID for the existing CU `get_usage_report`, with `group_by: execution`. |
| `phase` | `normal-start` or `normal-resume`; a resumed review also uses `normal-resume`. |
| `conversationContext` | Resumptions are `inherited-unknown`. Even a new execution does not prove a fresh instruction context. |
| `observedAt`, `updatedAt`, `endedAt` | UTC observation boundaries, not token-allocation boundaries. |
| `start`, `end` | Maps from relative source scope to an observation. `end` is absent until the monitor closes or the guard is dropped. |
| `instructionVersion` | Per-scope adopted label or `unversioned`. |
| `fileSha256`, `fileState` | Per-scope exact hashes and present/missing/unavailable distinctions. |
| `instructionSetSha256` | SHA-256 of sorted compact JSON `fileSha256`. Config inclusion/file selection can make it differ from MM's seven-file fingerprint. |
| `lifecycle` | `starting` until closure, then `ended` or `interrupted`. It is not evidence that a provider accepted a request or that a task succeeded. |
| `classification` | `unknown`, `mixed` or `observed-stable`, as defined below. |
| `unknownReasons` | Per-scope unversioned/unreadable/config/limit reasons, watcher gaps and interrupted lifecycle evidence. Mixed records retain these reasons. |
| `modelReadStatus` | Always `unknown`. |
| `claim` | Files present at observation, not proof of reading. |

A non-recursive native filesystem watcher watches only the selected files'
parent directories (or nearest existing parent). It ignores read-access and
unrelated writes. A relevant write, deletion, rename or parent replacement marks
`mixed` immediately and persists the first change timestamp, including a
change/revert whose end hash equals its start hash. A watcher error/rescan gap
marks unknown coverage. A newly created watched parent also marks mixed; no
recursive expansion is needed to claim that the original set was stable.
There is no polling service, event history or transcript capture.

The end snapshot independently detects changed hashes, versions and selected
sets. A closed run with no observed changes and no recorded gaps is
`observed-stable`. An open/interrupted run or a run with coverage gaps is
`unknown`; any observed change takes precedence as `mixed`. Notification
delivery and multi-file reads are best effort, not atomic filesystem attestation.
A very brief change/revert around the capture boundary can escape notification
delivery. `observed-stable` means stable **observations**, not proof that no
transient change occurred. Process/host loss leaves an incomplete record; absence
of `end` remains unknown even if a previous event classified it mixed. Missing
records are unknown coverage, never a retroactive stable version.

CU::Audit should join by the exact execution ID and cross-check workspace/session
identity against CU's attribution. Keep the original record with the usage
export and retain its coverage/freshness and missing-component metadata. CU does
not automatically ingest this format. Session/workspace fallbacks spanning
versions remain mixed/unknown; never split their token totals at timestamps or
sum overlapping execution/session/workspace totals. Cached input is already a
subset of input, and reasoning output is a subset of output.

For instruction-version comparisons, use completed ordinary work, its actual
model/settings, task class and reviewed outcome. Exclude mixed, incomplete,
unversioned and inherited-context ambiguity from claims of comparable fresh
instruction cohorts. Presence/hashes cannot prove model reads, obedience,
delivered instruction tokens, injected/conditional context, task quality, causal
savings or billed cost. Do not store full prompts, transcripts, credentials,
native history or environment dumps to improve the join. Records are local,
mutable observations, not signed or tamper-resistant attestation.

## Activation and rollback

This PR does not merge, deploy, swap assets, restart a service or alter running
jobs. It cannot retroactively instrument this implementation execution.

After normal review/CI and a separately authorised managed backend activation
following `VK_AGENT_DEPLOYMENT_RUNBOOK.md`, the changed backend automatically
records **future** normal executions. No AutoSwitch setting, agent command,
frontend update, migration or extra model test is needed. An existing session's
next ordinary follow-up receives a new record with inherited context unknown.
Already running jobs are not attached or restarted. Continue normal work and
inspect those naturally produced records and CU joins; do not launch separate
before/after agent sessions for usage evidence. A missing version label is
expected to remain unknown until that repository adopts reviewed metadata.

Rollback is a source revert through the normal review/activation process. Keep
existing records for audit; disabling future capture does not prove anything
about already observed runs. No cleanup or permission change is necessary.

## Validation and normal-work evidence

The actual Rust module's 13 tests pass in a small isolated harness on mounted
SSD, including native notification delivery while a context remains open,
change/revert handling, end-hash fallback, version/route changes, exact IDs,
resumption, nested/multiple scopes, interruption, missing/unreadable files,
external symlinks, private output and duplicate-execution protection. Its direct
dependencies are pinned to this repository's lockfile versions. The harness is
not the whole Vibe backend and does not certify native provider acceptance.

`pnpm run ops:check`, Rust formatting and warnings-denied focused Clippy pass.
With complete workspace dependencies, run `cargo test --locked -p local-deployment run_context::tests`. The required `pnpm run format`
was run: backend formatting passed, then frontend formatting stopped because
Prettier is absent. `pnpm run check` stopped at absent TypeScript after the legacy
path guard passed. `pnpm run lint` stopped at absent ESLint. Focused and workspace
offline Cargo tests cannot resolve the host's missing `serde` registry entry.
The full backend integration/Clippy/schema baseline remains for normal PR CI;
no large local workspace dependency restore was attempted. No model/provider
acceptance or local-instance activation is claimed.

An existing CU read during this ordinary implementation execution succeeded at
2026-11-12T22:30:11Z, with observation coverage through 22:27:17Z (fresh at query).
Exact execution `971c7d4e-6900-49d6-9627-a0b8b613cd46`, session
`99d70795-b359-4cf8-bb82-ea053f16f2cd`, workspace
`a5079aaa-d42d-4024-9c47-8f04131a6f93` joined to one native thread/model
`gpt-6.1-sol`: 14 attributed observations, 788,664 input tokens including 707,840
cached, and 9,401 output; 798,065 total. This is a partial implementation lower
bound excluding later work, not savings or provider billing. This running backend
does not contain the new hook: there is no automatic start record for this run,
and its instruction provenance cannot be reconstructed from current files.
No separate agent comparisons or test model calls were launched.
