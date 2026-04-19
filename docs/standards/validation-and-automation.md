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

## Canonical Branch Sync Check

Before branching from `staging`, after merges that should land on canonical branches, and before promotion work, run:

- `git fetch fork origin --prune`
- `pnpm run ops:branch-sync`

This check should confirm:

- local `staging` exactly matches `fork/staging`
- local `main` exactly matches `origin/main`

If either branch is ahead, behind, or diverged, treat that as a blocker to repair before further branch-base or promotion work.

## Local Validation Requirement

Code validation alone is not enough for this repo. Before a branch is used in the local Vibe Kanban instance or proposed as ready for `staging`, exercise the changed behavior in the running app when practical.

Typical examples:

- UI flow changes: `pnpm run dev` or `pnpm run dev:qa`, then verify the affected workflow in the browser.
- Backend workflow changes: use the local app or API path that exercises the changed behavior.
- Local runtime or recovery changes: verify `/api/info`, backup state, restore assumptions, or the affected operator path directly.

If any expected local exercise did not happen, state that explicitly in the final summary and handoff.

## Preview Validation

When the operator asks for a preview:

- start the relevant preview path rather than only describing how to do it
- verify the resulting URL
- report the working link in `Preview URL::`

For this repo today, the standard remote-review preview path is the Tailscale-backed workflow documented in `docs/operations/preview-delivery.md` and `mobile-testing.md`.

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
- `scripts/check-local-branch-sync.mjs` verifies that the canonical local `staging` and `main` branches match their tracking branches.

## Human Gates

Automation does not replace these human decisions:

- confirming the branch was exercised safely in the local VK instance
- deciding whether a user-facing change needs explicit manual QA before promotion to `main`
- creating and protecting the actual remote `staging` branch on GitHub
- repairing a locally diverged canonical `staging` or `main` checkout when the sync check fails

## Compliance Standard For This Fork

This fork is considered safely compliant when:

- required continuity docs exist and are current
- the local-validation requirement is documented and followed
- branch policy and freshness checks pass
- the promotion path from task branch to `staging` to `main` is clear
- operators state what was verified versus not verified
