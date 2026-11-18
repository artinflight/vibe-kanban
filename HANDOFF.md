# GPT-6.2 frontend model update — 2026-11-18

Branch `vk/273f-vk-update-codex-frontend-only` is a clean frontend-only candidate
based on `fork/staging` `dbcbfbe4e`. It adds GPT-6.2 Sol and GPT-6.2 Astra to the
Codex picker, uses GPT-6.2 Sol for new default-variant configurations, preserves
custom variants and explicit selections, and keeps all streamed GPT models at
5.6 or newer.

[PR #298](https://github.com/artinflight/vibe-kanban/pull/298) targets `staging`.
The implementation commit is `fb8e03406`.

The fallback exposes low, medium, high, xhigh, and max, matching the current
Vibe Codex executor contract. Discovered extra tiers are retained. CLI-only
`ultra` is not added because this backend would ignore it, and Fast/Ultrafast
service-speed selection has no frontend contract. Supporting either requires a
separate backend/contract change.

The browser cannot discover future models itself. It consumes
`/api/agents/discovered-options/ws`, whose Codex source is currently static.
Separate backend work should publish installed Codex model metadata and make the
latest compatible Sol available to executor-default resolution.

No runtime, profile, database, backend, deployment, or service was changed by
this source candidate.

Validation passed with exact `fork/staging` lockfile dependencies: repository
formatting, three focused Node/tsx regressions, local/remote/web-core/UI
TypeScript checks, local/UI lint, unused-i18n check, ops governance, production
frontend build, diff whitespace, compiled-bundle marker checks, and local preview
HTTP/API proxy checks against the active backend on `127.0.0.1:5621`. The build
produced `index-C2pzTuWF.js` and `index-BDlsFLgm.css` with the expected existing
chunk-size/Sentry warnings.

`cargo test --workspace` was attempted with the required shared non-incremental
target and stopped at the host's missing `glib-2.0.pc`; no Rust file changed.
The clean preview passed locally on `127.0.0.1:5511` and was stopped after the
review. Its advertised tailnet route timed out, public Funnel publication was
denied because authenticated backend exposure lacked destination-specific
approval, and shared-browser controls were unavailable, so browser-visible
operator QA is not claimed.

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
