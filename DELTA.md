# DELTA.md

## 2026-04-18T00:00:00Z | staging | local-only recovery baseline

- Intent: recover the usable VK board state, remove active cloud coupling, and make the local install restorable.
- Completed:
  - imported the VK cloud export into the local SQLite DB
  - switched the live runtime to local-only behavior (`shared_api_base: null`)
  - restored project settings, local columns, issue creation, workspace linking, and workspace history scroll
  - added lean backup + one-click restore scripts
  - installed hourly backup cron with Desktop archive mirroring
- Verified:
  - local API reports `shared_api_base: null`
  - project boards and issues load locally
  - backups are created locally and mirrored to Desktop
- Not complete / known gaps:
  - some historic metadata can only be reconstructed if present in export or DB snapshots
  - project-scoped PR fallback is still broader than it should be

## 2026-04-18T22:00:00Z | staging | hyrox issue/workspace/PR repair

- Intent: repair missing workspace links and merged PR indicators in the `hyroxready-app` kanban after local recovery.
- Completed:
  - re-linked `ART-57` to `FR::Cardio Timer Font Size`
  - restored merged PR metadata for:
    - `ART-60` -> `#799`
    - `ART-61` -> `#800`
    - `T42` -> `#801`
  - updated issue workspace cards so PR badges are visible on small/narrow layouts
- Files changed:
  - `packages/ui/src/components/IssueWorkspaceCard.tsx`
- Backups:
  - `/home/mcp/backups/vk-hyrox-pr-workspace-fix-20260418T223433Z`
  - `/home/mcp/backups/vk-hyrox-ui-rollout-20260418T224435Z`
  - `/home/mcp/backups/vk-t42-pr-fix-20260418T233203Z`
- Verified:
  - local fallback API shows the repaired issue/workspace/PR links
  - live bundle rolled to `index-tPwgyQmd.js`
  - fix committed to `staging` as `1ad3ed085`

## 2026-04-18T23:00:00Z | staging | vibe-kanban project smoke test

- Intent: prove the `vibe-kanban` project can resume normal issue/workspace work locally.
- Completed:
  - created a temporary issue in the `vibe-kanban` project
  - created a linked workspace against `_vibe_kanban_repo`
  - verified the workspace appeared under the issue immediately
  - stopped and deleted the temporary workspace
  - deleted the temporary issue
- Verified:
  - local issue creation works
  - local workspace creation works
  - workspace linking/refresh works
- Not complete / known gaps:
  - none blocking normal project work in the `vibe-kanban` board

## 2026-04-19T00:00:00Z | vk/df84-vk-ops | full ops-playbook adoption for VK fork

- Intent: finish adapting the Ops Playbook repo into this Vibe Kanban fork so local branch validation, continuity, and promotion rules are explicit and enforced.
- Completed:
  - added repo-specific standards docs for operating model, validation/automation, continuity, and agent rules
  - added a VK-specific ops adoption doc
  - added a repeatable local-instance QA checklist
  - updated root continuity and identity docs to reflect the adopted model and active task branch
  - tightened the ops-governance check to require the new playbook artifacts
- Files changed:
  - `AGENTS.md`
  - `README.md`
  - `REPO_IDENTITY.md`
  - `STATE.md`
  - `STREAM.md`
  - `HANDOFF.md`
  - `DELTA.md`
  - `docs/standards/operating-model.md`
  - `docs/standards/validation-and-automation.md`
  - `docs/standards/documentation-and-continuity.md`
  - `docs/standards/agent-rules.md`
  - `docs/adoption/vibe-kanban-ops-adoption.md`
  - `docs/operations/local-instance-qa-checklist.md`
  - `scripts/check-ops-playbook.mjs`
- Verified:
  - compared this repo directly against `/home/mcp/code/ops-playbook`
  - aligned the repo docs with the current task-branch reality and the fork-specific local-validation model
- Not complete / known gaps:
  - GitHub-side `staging` creation/protection still has to match the documented flow if not already configured
  - no new product/runtime behavior was changed or re-smoke-tested in this doc/governance pass
- Risks / Warnings:
  - docs alone do not enforce remote branch protection
  - future agents could drift again if they update root docs without keeping the standards docs in sync
- Next Safest Step:
  - run formatting and ops-governance validation, then complete the GitHub-side branch-protection setup if needed

## 2026-04-19T00:30:00Z | vk/df84-vk-ops | tighten agent completion and PR rules

- Intent: stop duplicate completion-summary reporting and make continuity-doc updates plus PR handling mandatory parts of finishing a branch.
- Completed:
  - tightened `AGENTS.md` so the final structured summary is emitted once per task
  - made during-task continuity updates explicit instead of optional
  - made push plus PR open/update the default expectation once a branch is review-ready unless blocked
  - synchronized the repo standards and adoption docs with those stronger rules
- Files changed:
  - `AGENTS.md`
  - `STATE.md`
  - `STREAM.md`
  - `HANDOFF.md`
  - `DELTA.md`
  - `docs/standards/documentation-and-continuity.md`
  - `docs/standards/agent-rules.md`
  - `docs/standards/operating-model.md`
  - `docs/adoption/vibe-kanban-ops-adoption.md`
- Verified:
  - reviewed the current repo rules directly and tightened the weak areas the operator identified
- Not complete / known gaps:
  - these are policy changes only; no automation yet checks for duplicate completion summaries or missing PR execution
  - `pnpm run format` may still be blocked locally by missing frontend formatting dependencies
- Risks / Warnings:
  - agents still need to follow the rules; stronger automation may be useful later if drift continues
- Next Safest Step:
  - run ops-governance validation and then commit the policy tightening if the user wants it recorded now

## 2026-04-19T01:00:00Z | vk/df84-vk-ops | harden canonical staging sync rules

- Intent: stop canonical local `staging` from silently diverging from `fork/staging` and make that sync requirement explicit in both docs and tooling.
- Completed:
  - verified that local `staging` is ahead 5 and behind 3 relative to `fork/staging`
  - tightened the branch rules so canonical local `staging` must be an exact mirror of `fork/staging`
  - added a local branch-sync check command and documented when it must be run
  - updated continuity docs to record the currently discovered divergence as a real blocker
- Files changed:
  - `AGENTS.md`
  - `STATE.md`
  - `STREAM.md`
  - `HANDOFF.md`
  - `DELTA.md`
  - `package.json`
  - `docs/standards/operating-model.md`
  - `docs/standards/validation-and-automation.md`
  - `docs/adoption/vibe-kanban-ops-adoption.md`
  - `docs/operations/release-safety.md`
  - `scripts/check-local-branch-sync.mjs`
- Verified:
  - compared local `staging` against `fork/staging`
  - confirmed the current divergence and anchored the rules to the actual `fork` remote used by this repo
- Not complete / known gaps:
  - the canonical local `staging` checkout is still divergent and must be repaired separately
  - `pnpm run format` may still be blocked locally by missing frontend formatting dependencies
- Risks / Warnings:
  - docs and checks can expose drift quickly, but they do not by themselves reconcile a divergent canonical branch
- Next Safest Step:
  - run the new branch-sync check, then repair canonical local `staging` before further branch-base use
