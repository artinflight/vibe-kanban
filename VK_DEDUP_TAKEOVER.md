# Deduplication and archival takeover — 2026-11-27

The operator requested that the current work and scope be published and integrated
into staging so the external managing agent can take over. This handoff is source
integration, not deployment, restart authorization or a completion claim.

## Current outcome and remaining work

| Area | Verified status | Work still required |
| --- | --- | --- |
| Original writer cutover and history conversion | Original conversion and catch-up accepted; supported Codex resume avoids historical replay duplication | Preserve native context and verify current growth after final deployment |
| Packed storage/performance repair | Three compatible readers and finite/daily converters tested; Desktop B recovery and private paired switch accepted | Deploy qualified readers, publish packed storage, retire only verified old objects, finish current public/recovery/performance checks |
| Archived workspace separation | Intent/catalog, journaled movement and B adapter source; 53 Python fixture/contract tests | Finish production dependency authority/driver and actual B qualification |
| Automatic revival on message | Ordinary admission/readers and visible recovery state connected in opt-in source; backend compiles | Qualify physical driver, exact dispatch, both readers and ordinary UI on combined candidate |
| Nightly active-workspace backup | Existing Nightly preparation belongs to its existing owner | Integrate archive catalog/shared recovery closure; prove cold payloads aren't recopied; schedule remains off |

**No dedup conversion job was running at the November27 readback.** The prepared
packed-reader activation has no APPROVAL, ARMED, STARTED, ATTEMPT or POST_ACTIVATION
receipt. Its proposed unit is not installed. The dedicated WakeWatch session's
last completed turn is November25; its report is preparation, not deployment.
Old failed test units are historical; do not replay them or clear evidence to
make the dashboard appear successful.

## Scope the operator added before restart

Finish and test archival separation, automatic movement on every future normal
Archive action, automatic revival when messaged and Nightly active-payload
selection before proposing the combined restart. Existing archived workspaces
need one migration through the same lifecycle, not another recurring manual
cleanup project. Source movement begins only after the compatible revival and
history readers are actually serving.

[VK_WORKSPACE_ARCHIVAL.md](VK_WORKSPACE_ARCHIVAL.md) is the full acceptance brief.
The outbox migration records intent only; it is not a verified archive receipt.
An archived flag must never by itself remove data or exclude it from Nightly.
Keep full SQL, catalog and shared dependencies in recovery, with cold payloads
separately recoverable on B. Preserve active/pinned/dirty/shared work, pending
inputs, native identities, settings, attachments and existing backup epochs.

The combined archive/revival implementation is not complete. A restart alone
will not provide it. The sealed dedup-only activation package does not contain
that feature or the new source-only outbox migration.

## Source and ownership

Current feature work is `vk/0815-archive-release`, based on merged staging
78e472543b950a15a260e2d6af249bd5bef671d2, in the separate SSD checkout named in
HANDOFF. PR291 integrated earlier source only. The combined release is still
IN PROGRESS: no exact qualified candidate/fallback pair or deployable combined
manifest exists yet. The restart agent should not select a release from this
intermediate document.

- Integration PR: [#291](https://github.com/artinflight/vibe-kanban/pull/291),
  branch `vk/0815-vk-deduplicate-c`, target operator fork `staging`.
  Before this handoff, remote task head was `6256bed7b`; local scope ended at
  `fa07571c0`. Use the final PR merge/head, not either old pin, for source pickup.
- Reconciled staging base: `dbcbfbe4e641cc7e79ec3275397940319689e868`.
  Retain its run-provenance and specialist-delegation changes.
- This checkout's `fork` is `artinflight/vibe-kanban`; `origin` is upstream
  `BloopAI/vibe-kanban`. Check remote URLs before pushing. Do not target upstream
  or promote staging to main as part of this handoff.
- Actual backend restart belongs to the managing agent outside Vibe. Neither
  this source-sync request nor old cutover messages authorize a new restart.
  Follow the current restart protocol, current owner checks and approval boundary.
- Reuse existing dedup/Nightly/WakeWatch ownership. Reconcile existing journals,
  pending inputs and uncertain dispatches; never start duplicate controllers.

## Accepted evidence and recovery dependencies

Read [VK_DEDUP_PACKED_LAYOUT.md](VK_DEDUP_PACKED_LAYOUT.md), current STATE and
HANDOFF for detailed evidence. The private evidence root on MCP is:

`/mnt/vk-storage/vk-log-dedup-20261103-0815/packed-object-qualification-20261124`

Accepted PACKED_* receipts cover preparation, normal B restore, both reader
protocols, source-pinned controller/daily qualification and paired fallback.
`PACKED_PAIR_PACKAGE_ACCEPTED.private.json` and
`PACKED_FINITE_PACKAGE_ACCEPTED.private.json` are the latest accepted packages.
Preserve the sealed directories `packed-reader-cutover-v1`,
`packed-reader-activation-v1` and finite-publication controls. Their exact pins
remain in [the pre-archival handoff](deployment-history/20261125-before-workspace-archival/HANDOFF.md).
Do not edit accepted pins to make a later combined build appear qualified.

Original software is fallback only BEFORE live VKLOGCAS2 publication; afterward
use a qualified packed-compatible fallback with the latest SQL. Never restore
an older DB over later writes. Accepted historical tests cannot replace current
SQL capture, reader/process/mount identity or public user-flow validation.

Private retained-history inputs, credentials, current SQL, accepted epochs and
software/frontend archives remain external dependencies, not public Git payloads.
Reconcile them from the existing deployment manifest/catalogs. Preserve current
frontend changes and the protected history reader when composing the candidate.

## Acceptance and accounting

Verify normal B restore of the complete archive tree, current SQL, compatible
software/frontend and recovery records. Check ordinary desktop/mobile history,
review, settings, queues, pending input and monitoring. Qualify new closed-log
growth handling and preserve exact selected settings. Report net allocated and
filesystem changes including retained SSD staging and B growth.

The historical 73,893,642,640-byte recovery predates later builds and staging;
it is not current net free space. Packing preparation projects 4,219 files from
1,057,171 selected files, but that reduction has not been applied live.
The November27 SSD readback had approximately 2.8 GiB free; recheck capacity
before builds/transfers and use existing verified recovery/retirement policy.

## This integration's validation

Local source checks: 451 tests passed and 16 explicitly skipped (private host,
Rust lock probe, owned retirement fixture); Ops, legacy-path guard and Rust format
passed. Full format/check/lint lack Prettier/TypeScript/ESLint. Offline Cargo
metadata cannot obtain android_system_properties; whole-workspace compilation
was not run at approximately2.8GiB free SSD. Read hosted checks on the final PR
head; these local results do not substitute for them.

The canonical staging worktree has another owner's uncommitted Antigravity/UI
edits. Do not stash/reset/overwrite them. Read the final remote staging tree or
the reconciled task checkout for this takeover.

Validation of source integration does not certify the unfinished combined
feature or a live restart. DELTA and the PR retain exact check limitations.
