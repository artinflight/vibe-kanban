# Vibe Kanban Operating Model

## Purpose

This document defines the branch, PR, validation, and cleanup model for this Vibe Kanban fork.

## Branching Model

### Standard branches

- `main`: protected production branch and the upstream PR target branch.
- `staging`: protected integration branch for normal work in this fork.
- task branches: short-lived branches for one feature, fix, docs change, or chore.

### Default rules

- Start normal work from the latest `origin/staging`.
- Use one stream per branch and one concern per PR.
- Do not push normal task work directly to `staging` or `main`.
- Keep a clean separation between local fork validation and upstream promotion.

### Hotfix exception

If a direct production fix is required:

- branch from latest `origin/main`
- use a `hotfix/*` branch
- keep scope minimal
- backfill the fix to `staging` after merge

## Promotion Path

The standard path for this fork is:

1. Create a task branch from `origin/staging`.
2. Implement the scoped change.
3. Run narrow local checks while developing.
4. Validate the branch in the local Vibe Kanban instance before treating it as safe for operator use.
5. Open a PR into `staging`.
6. After `staging` has passing CI and human confidence, open a promotion PR from `staging` into `main`.
7. Propose the final upstream PR from this fork's `main` only after the fork has been validated and promoted cleanly.

## Local Instance Safety Rules

- Before risky schema, runtime, or repo-linking changes, take a fresh lean backup or confirm the hourly backup is fresh enough.
- Keep `shared_api_base` disabled for the local install unless explicitly working on remote/cloud behavior.
- Do not treat local VK validation as optional for changes that affect user-visible flows, task/workspace linking, or local runtime behavior.

## PR Discipline

- One PR per concern.
- Keep PR scope reviewable and avoid mixing refactors with unrelated fixes.
- State what was locally validated, what still needs human QA, and whether the branch was exercised in the local VK instance.
- If a stream supersedes another one, say so explicitly in the PR body, `STREAM.md`, and `HANDOFF.md`.

## Freshness And Merge Expectations

### Into `staging`

Before merging to `staging`, require:

- passing required checks
- branch freshness against `staging`
- current continuity docs
- successful local validation for the changed surface

### Into `main`

Before merging to `main`, require:

- a promotion PR from `staging` or a tightly scoped `hotfix/*` branch
- passing required checks
- explicit human QA for meaningful user-facing changes
- confidence that the local-only runtime and backup posture remain intact

## Cleanup And Hygiene

- Delete merged task branches when they are no longer needed.
- Remove merged or abandoned worktrees after the stream is closed.
- Do not keep editing a merged branch.
- Close superseded PRs with a brief explanation instead of leaving stream ownership ambiguous.
