# PR112 Review Findings And Repair Handoff

**Repair status:** both P1 findings are addressed in application commit
`a6106d2e0`; local repaired-binary acceptance passed. Original review findings
below are retained as history. PR112 remains draft/unmerged and undeployed.

September 14, 2026. Reviewed application head:
`b21ef9bd5790f6a4135f80ea58dabfe49831c7ef`, against staging
`9a2591916610870ee456b6134bf4f217831010bc`.
PR: https://github.com/artinflight/vibe-kanban/pull/112

## Objective

Make PR112 safe to merge and prepare a release that preserves existing chat
choices and live frontend behavior. The review requests changes. Earlier
completion/acceptance notes do not close the findings below. This document
transfers repair context; it does not implement or certify a fix.

## P1: Scheduled Resume Drops Explicit Model And Reasoning

In `crates/server/src/routes/capacity.rs:234`, start loads
`latest_executor_profile_for_session`; line275 uses `profile.into()` for the
new executor configuration. The database helper projects the last execution's
configuration to executor/preset identity. The conversion at
`crates/executors/src/profile.rs:176` sets model, reasoning, agent and permission
overrides to None. A scheduled goal with a model/reasoning choice different
from its preset therefore resumes with preset settings instead of its choice.

Why it matters: the operator already experienced unexpected GPT-6 to GPT-5.6
changes after the previous cutover. A correct global default is not proof that
an existing chat's model is preserved. This new scheduled path is separate from
the previously reported frontend fallback bug; do not assume both causes are
the same or bulk-reset user selections.

Success means explicit model and reasoning choices survive scheduled resume,
while capacity-specific permission restrictions remain enforced. Cover choices
different from preset defaults, default changes between runs, and subsequent
ordinary continuation. Verify stored request and native resume configuration,
not just a UI label or profile API. Preserve the same goal, thread and progress.
Resolve how any newer saved per-chat selection is treated explicitly rather
than silently overriding it with a historical or global value.

## P1 Deployment Blocker: Missing Live Goal-Checkpoint Rendering

At review time the production frontend pointer resolved to
`/mnt/vk-storage/vk-goal-checkpoint-render/release-5d6ed3539`.
The corresponding source is available in
`/mnt/vk-storage/vk-goal-checkpoint-render/deploy-source`.
Compared with that source, PR112 lacks `packages/ui/src/lib/goalCheckpoint.ts`
and the structured checkpoint renderer in
`packages/ui/src/components/ChatAssistantMessage.tsx`. Candidate rendering
passes the content directly to Markdown. The staged release JavaScript had no
`splitGoalCheckpoint` or `Goal checkpoint` match.

This is a release-composition omission relative to live, not a deletion in
PR112's staging diff. Keeping old hashed assets only supports already-open tabs;
it does not preserve this behavior when the candidate index loads fresh assets.

Success means the chosen release retains the live checkpoint behavior on fresh
desktop/mobile loads without regressing ordinary messages or history. Integrate
the hotfix into the intended release or demonstrate a compatible retained live
frontend. Reconcile the release against current live assets, not only the older
backend baseline. Update affected artifact hashes and acceptance evidence after
changes; do not present the current package as validated for the repaired code.

## Review Evidence And Limits

- Local merge simulation passed; all ten existing hosted checks passed on the
  reviewed head. No new GitHub Actions were triggered by this review.
- Independent focused run: 70 capacity-guard/executor tests passed; two native
  integration tests ignored. These do not cover the override-loss scenario.
- Formatting and Ops checks passed; PR whitespace check found an extra blank
  line at `DELTA.md:1274` (minor cleanup, not the safety blocker).
- All three artifact hashes and nine evidence hashes in
  `/mnt/vk-storage/codexusage-capacity/release/manifest.json` matched. Historical
  native/crash/browser evidence was inspected, not independently rerun.
- The paired CU PR7 remains a dependency, not approved by this VK-only review.
- Production-specific backup/delta and measured handover/recovery preparation
  remain outstanding. Private fixture timing is not a production outage bound.

## Boundaries

This repair handoff does not authorize production deployment, restart, routing
changes, real-goal enrollment or quota/reset consumption. Keep production work,
saved messages, histories, settings, attachments and rollback data intact. Do
not restore old databases or replace original threads. Observe the established
restart protocol and obtain separate final cutover approval for deployment.
Do not use GitHub Actions; use local validation and skip-CI pushes.

Use mounted `/mnt/vk-storage` for bulky validation artifacts; permanent backups
belong on Desktop `B:/vk-backups/`. Keep fixes scoped to these findings and their
necessary integration. The receiving agent should choose the implementation.

The fixing agent's handoff should identify the repaired commits, tests proving
each outcome, exact release artifacts, remaining gaps and merge/deploy status.
No production readiness claim is justified solely by resolving Git conflicts.

## Repair implementation and validated result

The scheduled route now loads the complete latest non-dropped coding-agent
request, including explicit model/reasoning and other user overrides. Existing
profile-only consumers retain their previous API. A server-persisted follow-up
draft updated at or after that execution takes precedence as a complete newer
selection; its text is neither submitted nor cleared by scheduling. Browser-only
changes that failed to save are not observable by the scheduler. Unset fields
continue to mean preset defaults; explicit fields survive preset changes.
Capacity admission still applies its temporary native permission restrictions
after normal configuration resolution. Ordinary continuation retains its normal
request/configuration path.

The live checkpoint parser and renderer were integrated from the independently
verified current pointer `vk-goal-checkpoint-render/release-5d6ed3539` and its
`deploy-source`. Rendering leaves stored history unchanged and preserves malformed,
partial, fenced and ordinary messages. Old hashed assets alone are not used as
proof of this behavior.

New local regression drivers are `scripts/testing/capacity-model-review.py`,
`capacity-checkpoint-browser.mjs`, and the imported checkpoint rendering tests.
Artifacts and logs are under `/mnt/vk-storage/codexusage-capacity/pr112-repair`.
The model driver accepts only the fixed disposable one-session HTTP fixture,
uses the real installed native app-server with an offline provider, and captures
stored execution requests, native resume parameters and actual model requests.
No production state, live routing or real quota is part of this validation.

### Repaired-code evidence

- All 14 database tests passed, including complete-config preservation and
  ignoring a newer dropped execution. Six checkpoint parser/rendering tests pass.
- `cargo clippy -p server -p db --all-targets -- -D warnings`, `cargo check -p server`,
  UI type-check/lint, local frontend production build (including TypeScript),
  `pnpm run format`, and `pnpm run ops:check` passed. No Actions were invoked.
- `capacity-model-review.py` passed four actual installed-Codex/offline-provider
  runs: explicit GPT-6/high over a GPT-5.5/low preset; preservation after the preset
  changed to GPT-5.6-sol/low; newer saved GPT-5.5/medium selection; and subsequent
  ordinary continuation. Each checks the stored execution request, native resume
  parameters, actual model-request model/reasoning, same goal/thread identity,
  and retained progress. Scheduled network restrictions remain in place even
  with explicit AUTO permissions; ordinary resume restores its normal sandbox.
  Scheduled work leaves the user's unsubmitted draft intact.
- Fresh 1360px desktop and 390px mobile loads used `index-DPTdm8R5.js`, displayed
  structured checkpoints and ordinary surrounding text, and had no script errors.
  Screenshots and JSON evidence are in `pr112-repair` below.

### Exact repaired release and remaining boundaries

`/mnt/vk-storage/codexusage-capacity/pr112-repair/manifest.json` inventories the
new optimized server, guard, frontend files and validation evidence with SHA-256.
The server hash is
`3e4e594f9f531477b3d7df3300be9de7599d1b8b7bf7ab54a41c6bdd8d114380`.
The guard is unchanged; the fresh frontend contains the live checkpoint behavior
and retains the current live hashed assets for existing tabs. The original
`release/manifest.json` now explicitly points to this superseding VK package.

The isolated backend's teardown logged a Tokio timer shutdown panic after the
runs. All four functional runs passed; cleanup confirmed zero running fixture
executions, zero outstanding grants and no listener on 49173. This is recorded
in the manifest as an unresolved teardown limitation, not certified production
handover behavior. The full workspace/Tauri and earlier crash/reset suites were
not rerun for this scoped repair; earlier evidence stays attributed to its old
build. CU PR7 review and production backup/delta, measured handover/recovery and
final cutover approval remain separate. No real quota/reset was used and no
production service, frontend pointer, history, settings or attachment changed.
