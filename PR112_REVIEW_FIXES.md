# PR112 Review Findings And Repair Handoff

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
