# Vibe Kanban Validation And Automation

## Purpose

This document defines the minimum safe validation baseline for this Vibe Kanban fork and how automation supports it.

## Required Baseline Checks

Before a normal PR into `staging`, the default baseline is:

- `pnpm run format`
- `pnpm run ops:check`
- `pnpm run check`
- `pnpm run lint`
- `cargo test --workspace`

If work touches generated or remote deployment surfaces, also run the affected checks:

- `pnpm run generate-types:check`
- `pnpm run prepare-db:check`
- `pnpm run remote:generate-types:check`
- `pnpm run remote:prepare-db:check`

If a change affects packaging or local install behavior, include the narrowest relevant packaging validation such as:

- `pnpm run build:npx`
- `pnpm run check:npx-cli`

## Local Validation Requirement

Code validation alone is not enough for this repo. Before a branch is used in the local Vibe Kanban instance or proposed as ready for `staging`, exercise the changed behavior in the running app when practical.

Typical examples:

- UI flow changes: `pnpm run dev` or `pnpm run dev:qa`, then verify the affected workflow in the browser.
- Backend workflow changes: use the local app or API path that exercises the changed behavior.
- Local runtime or recovery changes: verify `/api/info`, backup state, restore assumptions, or the affected operator path directly.

If any expected local exercise did not happen, state that explicitly in the final summary and handoff.

## Automation Baseline

This repo should keep these controls active:

- PR validation workflow
- branch policy enforcement
- branch freshness enforcement
- release workflows for existing publish paths
- ops governance checks for required continuity and operating docs

## Current Automation In This Repo

- `.github/workflows/test.yml` enforces PR validation, branch policy, and branch freshness for PRs into `staging` and `main`.
- `scripts/check-branch-policy.mjs` enforces allowed PR base/head combinations.
- `scripts/check-branch-freshness.mjs` ensures the PR branch contains the latest base branch tip.
- `scripts/check-ops-playbook.mjs` verifies the required ops docs and references exist.

## Human Gates

Automation does not replace these human decisions:

- confirming the branch was exercised safely in the local VK instance
- deciding whether a user-facing change needs explicit manual QA before promotion to `main`
- creating and protecting the actual remote `staging` branch on GitHub

## Compliance Standard For This Fork

This fork is considered safely compliant when:

- required continuity docs exist and are current
- the local-validation requirement is documented and followed
- branch policy and freshness checks pass
- the promotion path from task branch to `staging` to `main` is clear
- operators state what was verified versus not verified
