# Local Instance QA Checklist

## Purpose

Use this checklist before rolling a branch into the local Vibe Kanban instance and before calling a change ready for `staging`.

## Pre-Flight

- Confirm the branch is scoped to one concern.
- Confirm `git status --short --branch` matches the intended stream.
- If the change is risky for runtime, schema, or repo-linking behavior, take a fresh lean backup or confirm the hourly backup is recent enough.
- If the task is supposed to stay local-only, confirm the target runtime should still report `shared_api_base: null`.

## Code Validation Baseline

- Run `pnpm run format`.
- Run the narrowest relevant code checks while developing.
- Before PR readiness, run the documented baseline:
  - `pnpm run ops:check`
  - `pnpm run check`
  - `pnpm run lint`
  - `cargo test --workspace`
- Add repo-specific generation or packaging checks when the changed surface requires them.

## Local VK Validation

- Start the relevant local runtime, usually with `pnpm run dev` or `pnpm run dev:qa`.
- Exercise the changed workflow in the actual app.
- For issue, project, workspace, or PR-linking changes, verify both the UI path and the resulting local behavior.
- For runtime or recovery changes, verify the live API or operator path directly.

## Record What Happened

- Note what was actually exercised.
- Note what was not exercised and why.
- If local validation was skipped for any expected surface, do not describe the branch as fully ready.

## Promotion Gate

Before opening or updating a PR into `staging`, confirm:

- the branch contains the latest `origin/staging`
- required checks passed
- local-instance validation was completed or the gap was explicitly recorded
- `STREAM.md`, `HANDOFF.md`, and `DELTA.md` reflect the current stream state when needed

## Production Promotion Gate

Before promoting `staging` into `main`, confirm:

- `staging` has the expected validated work
- CI is passing
- meaningful user-facing changes received explicit human QA
- the local-only runtime and backup assumptions were not accidentally broken
