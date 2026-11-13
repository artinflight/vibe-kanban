# Provenance merged; activation preparation only — 2026-11-13

VK [PR #297](https://github.com/artinflight/vibe-kanban/pull/297) merged into
staging as `dbcbfbe4e641cc7e79ec3275397940319689e868`. The tree equals reviewed
head `70381108f36baf51bd8cc327690ee5dbee150c8e`; Test run 43416444956 was rechecked
successful before merging. Private remote and release-only checks were skipped.
CU PR #56 merged into main as `4a190f19a399392d9ca80d04832a8f31fe208e81`.

The [guide](VK_RUN_PROVENANCE.md) retains the producer/CU contract and integration
record. A detailed activation plan is retained privately for the operator, covering
current bindings, live-change preservation, backup/rehearsal gates, process
reloads, normal-job evidence, skipped checks and rollback. No deployment,
restart, agent turn or separate usage experiment was performed.

The current branch only updates documentation. Activation remains future
separately authorised work under the established deployment/restart runbooks.
Use the next normal job after activation for exact-ID producer-to-CU acceptance;
unknown/mixed/inherited context and missing attribution remain explicit.
Preserve others' uncommitted work. No live acceptance is inferred from the merge.

Previous handoff/source evidence: [specialist delegation](VK_GOAL_SPECIALIST_DELEGATION.md),
[scrolling deployment](VK_SCROLLING_PROJECTS_DEPLOYMENT.md),
[HANDOFF history](HANDOFF_HISTORY_20261017.md), and
[previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md).
