# AutoSwitch V1 staging integration

Release boundary: validated V1 only. The operator owns everything after staging
merge. This task does not deploy, start a deployment workflow, or contact another
agent. Version remains 0.1.42.

## Included provenance

Staging base: `56792a72cfa3dece4086a8e957871b40a9b9deed` (PR126).

| Original commit | Rebased commit | Scope |
| --- | --- | --- |
| df3e973a5 | 318a6dd4c | Original feasibility documentation |
| 162770f73 | ea3f7e7c3 | Opt-in V1 boundary routing, manual/shadow/auto controls, model registry and exact runtime qualification |
| 9b334d1a3 | 67c4a5b62 | CU lifecycle JSONL, native turn identity, failure reporting and explicit effort fixes validated in V1 acceptance |

V2 commit `64e9cb5bd474fa59b50a6119dc7fb85640f826fa` is preserved on
`vk/5a81-autoswitch-cu-recovery` in
`/mnt/vk-storage/vk-model-autoswitch-20260930/source` and excluded from this branch.
No automatic task classifier, `assessed` floor, pair-qualification registry or
policyVersion2 behavior is included. V1 remains explicit-floor routing with
manual mode as the default. This document is an integration note, not another
routing implementation change.

## Conflict resolution and preserved staging behavior

Only HANDOFF.md and STREAM.md conflicted while replaying the documentation
commit. Both AutoSwitch notes and staging's newer capacity notes were retained.
No source conflicts occurred. Range comparison shows staging's two-selected-goal
capacity changes and scheduled-resume recovery-history fixes are preserved.
Core V1 router, model registry, telemetry, Codex executor/RPC and container source
files are byte-identical to the accepted V1 commit. The shared client incorporates
both sets of non-conflicting changes. No acceptance-path redesign was necessary.

## Validation scope

Run formatting/governance, executor library regressions (including routing,
telemetry, capacity and goal-resume tests), server build/type checking, web-core
TypeScript and the focused React routing-selection tests. Verify the canonical CU
contract and fixture byte-for-byte and check the accepted runtime manifest/model
pairs. CI applies the repository's normal PR checks. Exact results are recorded
in HANDOFF.md and the final merge report archive.

Evidence: `/mnt/vk-storage/vk-autoswitch-v1-staging/evidence`.
Accepted bounded native/CU evidence remains in
`/mnt/vk-storage/vk-model-autoswitch-v1/integration`.
No broader model campaign or new native inference is necessary: the rebase did
not materially change the AutoSwitch execution path.

## Operator deployment notes

The merge does not upgrade the production launcher or install service settings.
Use the already verified CLI0.159.2 compatibility launcher and the matching
account/home. V1 requires `VK_CODEX_ROUTING_AVAILABILITY`; proof expires after
24 hours, and a different launcher/account/home requires refreshed bounded proof.
Point `VK_ROUTING_EVENTS_FILE` and CU's `CU_ROUTING_EVENTS_FILE` at the same
private file. Existing internal routing logs remain enabled independently.

The interrupted acceptance attempt has a real execution/turn binding but no
native token-count record; its usage remains unknown, not zero. Normal,
escalated and manual completed-turn counters matched CU exactly. This retained
measurement limitation does not imply a new V1 integration blocker.

The operator accepted the V1 architecture/integration boundary. Earlier pending
review/deployment notes in historical documents are not instructions to launch
another agent or reopen the completed acceptance campaign.
