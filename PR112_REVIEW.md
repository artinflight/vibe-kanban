# PR112 Merge And Deployment Review

Reviewed September 14, 2026. PR: https://github.com/artinflight/vibe-kanban/pull/112
Head: `b21ef9bd5790f6a4135f80ea58dabfe49831c7ef`.
Staging: `9a2591916610870ee456b6134bf4f217831010bc`.
Verdict: request changes before merge; prepared deployment is not approved.

## Findings

### P1: Scheduled resume drops explicit model and reasoning overrides

`crates/server/src/routes/capacity.rs:234` loads only
`latest_executor_profile_for_session`, then line275 constructs the resume with
`executor_config: profile.into()`. The database helper projects the last request
to its executor/preset identity. `crates/executors/src/profile.rs:176` converts
that identity back with model, reasoning, agent and permission overrides absent.
Consequently a selected goal using a model/reasoning choice different from its
preset resumes under the preset configuration instead. This is a new scheduled
resume path, distinct from the already reported existing-chat UI fallback.

Preserve the intended effective model/reasoning configuration through admission
and resume; apply capacity permission restrictions separately. Add a test with
per-chat model and reasoning different from the default, asserting the stored
request and native resume configuration. Existing capacity unit tests passing
does not establish this property.

### P1 Deployment Blocker: Candidate frontend omits a live hotfix

The live frontend pointer resolves to
`/mnt/vk-storage/vk-goal-checkpoint-render/release-5d6ed3539`.
Comparing that source to PR112 shows the candidate lacks
`packages/ui/src/lib/goalCheckpoint.ts` and the structured goal-checkpoint
rendering in `packages/ui/src/components/ChatAssistantMessage.tsx`; its component
only passes content to Markdown. The staged release frontend contains no
`splitGoalCheckpoint` or `Goal checkpoint` JavaScript match. Retaining old hashed
assets does not retain behavior for newly loaded candidate pages.

This is a release-composition gap relative to live, not a deletion introduced
by the PR's staging diff. Integrate and validate the live hotfix in the intended
release or explicitly retain the compatible live frontend. Do not deploy the
prepared frontend directory unchanged and claim no regressions.

## Validation

- Fresh fork PR metadata: open, targets staging, mergeable; all ten existing
  hosted checks successful on the reviewed head. No Actions were triggered.
- Local `git merge-tree --write-tree` against fresh staging passed without
  conflicts. No branches were merged or moved.
- `cargo test -p capacity-guard -p executors --lib --offline`: 70 passed,
  two native integration tests ignored. Build/test temporary paths were on SSD.
- `pnpm run format` passed using the existing SSD Prettier installation;
  PR worktree remained clean. `pnpm run ops:check` passed.
- PR diff whitespace check reports an extra blank line at DELTA.md:1274.
- All three staged artifact hashes and all nine evidence hashes in the release
  manifest matched. Historical native/crash/browser acceptance evidence was
  inspected, not independently rerun. Broad workspace tests, physical mobile
  QA and a production handover were not run for this review.
- Read-only service check: Blue PID2590517 active/running, original Green
  PID2669659 active/frozen. No service, routing or production data changes.

## Remaining Deployment Conditions

Fix the model override loss and release-composition gap, rebuild changed
artifacts, then repeat relevant native and desktop/mobile acceptance. CU PR7 is
a paired dependency; this review does not approve that separate codebase.
The package itself states that a production-specific backup/delta, measured
handover and recovery preparation remain necessary. Use latest production data,
preserve original histories and per-chat settings, and obtain a separate final
cutover approval. A private fixture's timings are not a production outage bound.

No merge, push, deployment or restart was performed. Application version0.1.42.
