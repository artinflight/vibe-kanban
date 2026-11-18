# Conversation-log reclamation: context for the receiving agent

## Takeover update — 18 November, 00:10 UTC

The receiving agent is pursuing the full goal. Current inert candidate is
P/completion-package-v9, with lost-reply recovery, adaptive SSD admission,
complete physical accounting and the qualified public four-case history/settings/
review/empty-queue browser check.126focused plus8exact-package tests pass.
Fresh exact host owner checks pass. Only the four earlier manifests are installed.
No new maintenance, backup payload capture or conversion has started.

Read STREAM/HANDOFF for the live two-worker sizing handle and current remaining
B-demand/integration work. The older plan-only assignment and known-unfixed-bug
text below are preserved historical context, superseded by this update.

## Objective and why it matters

Finish production conversation-log deduplication and reclaim the recoverable
space, while preserving complete readable histories, references and recoverable
backups. Also address future growth. The operator expected substantial recovery
and has repeatedly received investigation, preparation and handoffs instead.
Success is working production and measured recovery, not another plan or a count
of logical duplicate bytes.

The operator wants the receiving agent to determine the approach independently.
The prepared implementation and previous go/no-go plan are available evidence,
not a required architecture or workflow. A better approach is welcome if it meets
the actual requirements. This turn updates documentation only; no new agent,
maintenance, conversion or backup job has been started. The receiving agent's
execution scope comes from its actual assignment.

## Success criteria

- Recover the space from the remaining beneficial duplicate logs and report
  actual allocated/filesystem recovery, accounting for retained objects and
  staging. Distinguish new recovery from previous cleanup and logical estimates.
- Preserve complete conversation content and order, references, sidecars and
  required metadata. Ordinary history readers work with the resulting storage.
- Keep backups recoverable through Nightly's normal restore path, including all
  dependencies of archived histories, current SQL, compatible software, frontend
  and recovery records. Verify the relevant restores rather than assuming that
  inclusion in a backup root establishes recoverability.
- Recover ordinary public desktop/mobile/history/review/settings/queue service.
  Preserve current database writes, pending inputs and selected model/route/
  permission settings.
- During any maintenance, prevent automatic WakeWatch agent dispatch from
  colliding with it, preserve monitoring, reconcile existing queued deliveries,
  and restore and verify the previous settings afterward.
- Establish the actual effect on future log growth without confusing isolated
  runtime fixtures with the deployed runtime.
- Report completed work, measured space recovery and any genuine unfinished
  outcome candidly. Existing histories and backup epochs remain protected.

## Verified progress and limitations

**Deployed:** archive-aware main/protected readers. Main SHA256
`4766246c477fd8d73367969bee9b705586c5b580ddf786515409d977b48ce104`;
protected `40a91f69f31c1b9751f8f5a699fc8dfaa6f20138ba1b0ab528788aecb7ddd000`.
The main build combines base087319cc4 with a d007c88d2 native-resume overlay;
its identity cannot be inferred from a version label alone.

**Completed reclamation:** four original log paths contain lossless VKLOGCAS1
manifests. Net allocated log recovery is **827,506,688 B**, including all canary
objects and object-directory blocks. This is not full production reclamation.
A separate approved two-build-archive relocation released **303,202,304 allocated
B** from the SSD after independent B copy verification. Separate Nov14 retirement
of 31,572,000,768 B is also historical. These amounts must not be counted again.

**Service recovery:** the interrupted operation was recovered on aware readers;
ordinary route, ingress, capacity and exact WakeWatch dispatcher/five settings
were verified. The historical failure was a strict history expectation mismatch
caused by workspace-path rendering context. Independent raw/archive/live parity
supported its correction. A later full history check passed 22 responses,
including four main/four protected canaries, six T18 checks and exact seven-page/
49-entry pagination. Public history rendered in four desktop/mobile viewport
cases with no page errors or operator writes. Full rendered review/settings/queue
acceptance was not established. Eighteen older histories retain an accepted
restore-before-view arrangement; they are not all locally viewable.

**Growth evidence:** actual native runtime is 0.159.2. Retained initial resume
changed from eight historical turns/10,746,496 response bytes to zero turns/
5,126 bytes (99.9523% fewer initial bytes). This is initial-response evidence,
not a measurement of all future growth. The isolated 0.166 fixture was not the
actual deployed runtime.

**Recovery defect found, not fixed:** the pinned host helper's
`Boundary.freeze_boundary` fails when capacity release commits but its reply is
lost. The subsequent valid status is `owned=false,state=null`; the helper indexes
`state.epoch`, raises TypeError and leaves its in-memory release receipt unset.
That is a concrete risk in the prepared implementation, not a diagnosis of every
possible alternative. A retained offline reproduction uses the exact method AST
and fixtures with zero live operations. It reproduces the bug, not a fix.

## Last observations, not current admission

The last planning snapshot found 3,433 closed candidates / **90,992,755,255 logical
B**. Actual compression/dedup benefit across that population is unverified.
It excluded 82 tiny files, eight pending captures, one invalid capture record,
four existing archives and the active session's 14 files. Those exclusions were
specific observations, not a permanent definition of future scope.

At that time, 1,338 volatile queues and the durable queue were empty, only the
planning execution was active, and 32 uncertain incoming records were preserved.
SSD free space was approximately **3.49 GB**; Desktop B had **85.50 GB** free and
reported the expected identity, Healthy/Online, no B-specific owner pause and no
explicit B hold. Those samples do not prove that the remaining work fits. Logical
source size alone does not determine B write demand because verified chunks may
already exist. No full-run downtime bound is supported: history took 334.782 s,
four viewport/history cases 76.019 s, and the earlier failed interruption lasted
5,814.115 s. These are component/history observations, not an SLA.

The prior prepared pipeline used bounded batches and retained resource/ownership
checks. Its particular batch sizes, execution order and scripts are implementation
choices, not user-mandated solutions. Genuine active ownership, capacity, integrity
and authorization protections remain applicable. Live observations will age;
this handoff does not certify a current quiet window.

## Requirements versus inherited design

**Hard requirements:** preserve all histories, existing backup epochs and recovery
records, current SQL writes, pending inputs and selected settings. Reclamation
must remain lossless and recoverable. Respect other owners and real admission
controls; coordinate maintenance and backup compatibility. Preserve monitoring
and restore WakeWatch's prior settings after any temporary pause.

**Existing-format dependency:** the four installed VKLOGCAS1 manifests depend on
session-local `.log-objects` and compatible readers. Their complete backup unit
includes all objects, even unreferenced ones, manifests, raw logs, sidecars,
adjacent files and directory/link/Linux metadata. An archive-unaware reader cannot
read these manifests. Any replacement/fallback therefore needs compatible data
or verified restoration to exact raw originals; merely starting an old binary
would lose readable history. Semantic omission of repeated turns is not lossless.

**Prior decisions/context:** Vibe and Nightly owner handoffs are accepted.
Nightly retains sole backup producer/schedule ownership. Its separate calendar
commissioning was not made a prerequisite for this work. No additional owner
agent, Staging prompt, backup pipeline, object GC or new retention policy was
requested. The previous prepared operation remains unarmed. Old consumed attempts
and recovery receipts are evidence, not permission to replay them.

## Evidence and inputs

Repository: existing `vk/0815-vk-deduplicate-c` worktree at
`/home/mcp/code/worktrees/0815-vk-deduplicate-c/_vibe_kanban_repo`, physically on
`/mnt/vk-storage/worktrees`. Draft PR
https://github.com/artinflight/vibe-kanban/pull/291 targets staging; `fork` is
artinflight, `origin` BloopAI. Commit/push is not deployment. LIVE_DEPLOYMENT.json
records serving provenance. The current frontend and green authoritative database
must be preserved; DB target is
`/mnt/vk-storage/vk-original-access-recovery-20261025T1748/working90.sqlite`
(99 migrations). Public origin is https://vibe.local.

Private evidence is outside Git. A clone alone lacks the inputs needed to assess
this production case. Path abbreviations below are provenance:

```text
D = /mnt/vk-storage/vk-log-dedup-20261103-0815
P = D/production-20261117
R = /mnt/vk-storage/vk-log-reader-release-20261104
F = R/refresh-20261117-v1
Q = D/nightly-coordination-20261117
```

| Evidence/input | Location and meaning |
| --- | --- |
| Latest planning decision | `P/final-go-no-go-20261117/FINAL_GO_NO_GO.v2.private.json`; references exact live/scope/queue/B/UI receipts. V1 retained. |
| Known recovery defect | Same folder `CAPACITY_RELEASE_EDGE.private.json` and `CAPACITY_RELEASE_EDGE_REPRO.private.py`; pinned baseline host source SHA6496ebb5… . Running the reproduction performs no live action. |
| First completed batch | `P/operation-a0885d2bd43345babf8751bfad024e30/first-journal/state.json`, `FIRST_ORIGINAL_B_PROOF.private.json`; completed batch and original normal-B proof. |
| Prepared, unused design | `P/resume-after-first-20261117/package-v5/PREPARED.private.json`, actual controller and NEXT_INPUTS; unarmed operation40f9db6e87f345bba47606864a4e3a16. No ATTEMPT when reread for this handoff; input SHA53de9edf727c8544cb4a6e18c3fd7f214ab3059b04a6ce9891459335289f363f unchanged. |
| Previous recovery/context findings | `P/isolated-canary-diagnostic-20261117/`; live-canaries, acceptance-context-v1, recover-only-v3. Actual recovery attempts there are consumed. |
| Vibe dependency handoff | `F/HANDOFF_MANIFEST.private.json`, source refs and accepted current-data/reader/frontend contracts. |
| Nightly dependency handoff | `Q/ROOT_HANDOFF.private.json`, `FINITE_FACTORY_PROCEDURE.private.md`, `BATCH_SOURCE_MANIFEST.v3.private.json`, `BASE_PROVIDER_CATALOG.private.json`; existing same-context recovery APIs. Accepted 68 original/sidecar versions total3,073,516,522 B independently normal-B restored. |
| Normal backup format contract | `D/NIGHTLY_BACKUP_CONTRACT.private.json`; format/root/reader dependency contract, with older live-status text treated as historical. |
| Offload and full history proofs | `P/approved-two-build-archives-9816ae8beb404092852093ed2e1c90a0/RESULT.private.json`, POSTCHECK and history-recheck-a094f38beaa14d07a23586a08394ce45; `P/resume-after-first-20261117/POST_OFFLOAD_READINESS.private.json`. |
| Actual resume measurement | `P/MEASURED_PREDEPLOYMENT_CURRENT_RESUME.private.json`, `P/MEASURED_POSTDEPLOYMENT_CURRENT_RESUME.private.json`. |
| Existing implementation/tests | `scripts/log-dedup/`; private package/controller, `P/batch_support.private.py`, `P/closure_support.private.py`, `P/ARCHIVE_CLOSURE_RESTORE.private.md`, actual Rust reader probe under R. |

Useful test context: CI's focused entry is unittest discovery in
`scripts/log-dedup` for `test_*.py`. Private
`P/test_partial_resume_v5.private.py` targets v5; the similarly named
`test_partial_resume_final.private.py` targets v4. Existing passing tests did not
catch the lost-reply defect. An existing test count does not establish correctness
of a new candidate.

The previous `VK_LOG_PRODUCTION_GO_NO_GO.md` preserves a detailed proposed route
and its assumptions. It is historical planning, not a mandate for the receiving
agent. Shared planning entry d43948a5-b1a7-4872-9afc-641ea2e338fd revision4 records
that the implementation remains unarmed and owner contracts remain accepted.
