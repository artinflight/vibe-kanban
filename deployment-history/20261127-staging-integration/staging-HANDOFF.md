# VK::Run Provenance — review corrections, 2026-11-13

Source-only change on `vk/a507-vk-run-provenanc`, current fork/staging base
`bc3b89dee`. Existing production runtime and running work remain untouched.
Draft [PR #297](https://github.com/artinflight/vibe-kanban/pull/297) targets
staging. [Previous CI](https://github.com/artinflight/vibe-kanban/actions/runs/43321606696)
failed backend test compilation (E0061); the review correction fixes the omitted
context argument in `github_sync_tests.rs`. Check the corrected head's CI before
integration.

- `crates/local-deployment/src/run_context.rs` implements workspace-local private
  records, bounded hashes/config labels, native file events and terminal capture.
  The normal spawn path creates the guard; the existing exit monitor owns it.
- [VK_RUN_PROVENANCE.md](VK_RUN_PROVENANCE.md) defines the extended Media
  Management schema, CU::Audit exact-ID joins, unknown/mixed/inherited context,
  storage/privacy limits, activation and rollback. A file hash never proves a
  model read. Records appear only for future executions after separately
  authorised managed backend activation, with no AutoSwitch requirement.
- Eighteen focused tests pass against the actual module in a small mounted-SSD
  harness, with direct dependency versions pinned to Cargo.lock. Governance and
  Rust formatting pass. Whole-repo offline Cargo cannot resolve serde; required
  frontend format/check/lint stop on missing Prettier/TypeScript/ESLint. Full CI
  and actual post-activation ordinary-run evidence remain distinct validation.
- CU exact-execution query succeeded during this normal implementation work;
  the guide records its partial lower bound and lack of automatic start coverage.
  No provider tests, workers, deployment, merge, restart or device action.
- A confirmed-empty scope (every selected `fileState` is `missing`) now has
  `instructionVersion: null` and no unversioned reason, while retaining hashes,
  states and watches. Real unversioned instructions and unavailable files remain
  unknown. Five regressions cover this distinction, start/resume and later
  instruction appearance. No new scope fields; see the guide's pinned v1 contract.
  The separate CU PR #56 owner is aligning consumption; this branch changes no CU
  code, attribution or usage evidence, and starts no comparison agents.

Review the focused staging PR and its CI before integration. Do not activate
from this task. Use the existing deployment runbook when separately authorised;
observe future ordinary starts/resumptions for usage evidence.

Previous handoff/source evidence: [specialist delegation](VK_GOAL_SPECIALIST_DELEGATION.md),
[scrolling deployment](VK_SCROLLING_PROJECTS_DEPLOYMENT.md),
[HANDOFF history](HANDOFF_HISTORY_20261017.md), and
[previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md).
