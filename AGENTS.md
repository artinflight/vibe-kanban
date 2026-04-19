# Repository Guidelines

## Purpose

- This repo uses the Ops Playbook continuity model adapted for Vibe Kanban.
- The goal is to keep feature work isolated, tested locally in this fork before use in a local Vibe Kanban instance, and only then promoted into an upstream PR.
- Keep this file stable. Current branch intent belongs in `STREAM.md`, not here.

## Required Read Order

1. `AGENTS.md`
2. `STATE.md`
3. `STREAM.md`
4. `HANDOFF.md`
5. Relevant package or crate guide for the area being changed
6. Code and validation paths for the task
7. `DELTA.md` only for compact continuity history

### Crate-specific guides

- [`crates/remote/AGENTS.md`](crates/remote/AGENTS.md) — Remote server architecture, ElectricSQL integration, mutation patterns, environment variables.
- [`docs/AGENTS.md`](docs/AGENTS.md) — Mintlify documentation writing guidelines and component reference.
- [`packages/local-web/AGENTS.md`](packages/local-web/AGENTS.md) — Web app design system styling guidelines.

## Authority Order

1. Code, workflows, and validated behavior
2. `STATE.md`
3. `STREAM.md`
4. `HANDOFF.md`
5. `DELTA.md`

## Repo-Specific Rules

1. Treat this repo as the operator fork used to validate work safely before it is proposed upstream.
2. Keep the local-only VK runtime recoverable while changing repo policy or feature code.
3. Preserve working repo-specific release workflows; layer Ops Playbook controls on top instead of replacing proven automation.
4. Separate repo-wide truth from branch-local intent. If a rule or status applies only to the active task branch, keep it out of `STATE.md`.
5. When adopting or tightening ops rules, document both:
   - what is now required for this fork
   - what still depends on GitHub branch protection or human process outside the repo

## Update Rules

1. Update `STATE.md` only when repo-wide truth changes.
2. Update `STREAM.md` when branch scope, decisions, or next steps materially change.
3. Replace targeted sections in `HANDOFF.md`; do not stack diary entries.
4. Append one compact `DELTA.md` entry for meaningful checkpoints.
5. Update repo-specific ops docs when the working model changes.
6. Update continuity docs during the task whenever validated truth, scope, blockers, or next-safe steps materially change.
7. Do not defer required doc updates to "later" once the relevant truth is already clear.
6. Keep `AGENTS.md` stable; do not turn it into a session log.

## Project Structure & Module Organization

- `crates/`: Rust workspace crates — `server` (API + bins), `db` (SQLx models/migrations), `executors`, `services`, `utils`, `git` (Git operations), `api-types` (shared API types for local + remote), `review` (PR review tool), `deployment`, `local-deployment`, `remote`.
- `packages/local-web/`: Local React + TypeScript app entrypoint (Vite, Tailwind). Shell source in `packages/local-web/src`.
- `packages/remote-web/`: Remote deployment frontend entrypoint.
- `packages/web-core/`: Shared React + TypeScript frontend library used by local + remote web (`packages/web-core/src`).
- `shared/`: Generated TypeScript types (`shared/types.ts`, `shared/remote-types.ts`) and agent tool schemas (`shared/schemas/`). Do not edit generated files directly.
- `assets/`, `dev_assets_seed/`, `dev_assets/`: Packaged and local dev assets.
- `npx-cli/`: Files published to the npm CLI package.
- `scripts/`: Dev helpers, validation helpers, and DB preparation.
- `docs/`: Documentation files, including ops audit and release-safety guidance.

## Branch / PR Rules

- Treat `main` as the protected production and upstream PR target branch.
- Treat `staging` as the protected integration branch for normal work.
- Start normal work from the latest `origin/staging`.
- Use one branch per stream and one PR per concern.
- Open normal feature, fix, docs, and chore PRs into `staging`.
- Only open PRs into `main` from `staging`, except for explicit `hotfix/*` branches.
- Validate a feature in this fork's local Vibe Kanban instance before promoting it to `staging`, and treat the `staging` to `main` PR as the production promotion step.
- When a task branch is ready for review, agents should push it and open or update the corresponding PR unless the user explicitly says not to or a concrete blocker prevents it.
- If a PR was not opened or updated, agents must say exactly why in the final completion message.
- Do not mix unrelated cleanup, refactors, and feature work in the same branch.
- Keep a canonical local checkout of `main` current with `origin/main`; do not leave the operator's reference checkout stale after merges.
- Keep a canonical local checkout of `staging` current with `origin/staging` once the branch is created.
- If a direct production hotfix is ever needed, branch from the latest `origin/main`, keep scope minimal, and backfill the fix to `staging` afterward.

## Documentation Roles

- `README.md`: repo overview, setup, and links to operational docs.
- `REPO_IDENTITY.md`: stable explanation of this fork's role and release path.
- `AGENTS.md`: stable operating rules.
- `STATE.md`: repo-wide truth.
- `STREAM.md`: current branch scope and boundaries.
- `HANDOFF.md`: short pickup note for the next agent.
- `DELTA.md`: append-only continuity ledger.
- `docs/audits/vibe-kanban-ops-audit.md`: audit record of how this fork maps to the Ops Playbook.
- `docs/standards/*.md`: repo-specific standards for branching, validation, continuity, and agent behavior.
- `docs/adoption/*.md`: repo-specific adoption and rollout guidance for this fork.
- `docs/operations/*.md`: operational runbooks and release/QA procedures.

## Managing Shared Types Between Rust and TypeScript

`ts-rs` allows you to derive TypeScript types from Rust structs and enums. When making changes to the types, regenerate them with `pnpm run generate-types`. Do not edit `shared/types.ts` directly; edit `crates/server/src/bin/generate_types.rs` instead.

For remote and cloud types, regenerate with `pnpm run remote:generate-types`. Do not edit `shared/remote-types.ts` directly; edit `crates/remote/src/bin/remote-generate-types.rs` instead.

## Build, Test, and Development Commands

- Install: `pnpm i`
- Run dev (web app + backend with ports auto-assigned): `pnpm run dev`
- Run QA dev mode: `pnpm run dev:qa`
- Backend (watch): `pnpm run backend:dev:watch`
- Web app (dev): `pnpm run local-web:dev`
- Type checks: `pnpm run check`
- Lint: `pnpm run lint`
- Rust tests: `cargo test --workspace`
- Generate TS types from Rust: `pnpm run generate-types`
- Prepare SQLx (offline): `pnpm run prepare-db`
- Prepare SQLx (remote package, postgres): `pnpm run remote:prepare-db`
- Local NPX build: `pnpm run build:npx` then `pnpm pack` in `npx-cli/`
- Ops governance check: `pnpm run ops:check`
- Format code: `pnpm run format`

## Validation Rules

- Before finishing any task, run `pnpm run format`.
- Before using a branch in a local Vibe Kanban instance, run the narrowest relevant checks and document what was not exercised.
- Before opening or updating a PR into `staging`, the default validation baseline is `pnpm run ops:check`, `pnpm run check`, `pnpm run lint`, and `cargo test --workspace`, plus any repo-specific generation checks affected by the change.
- Before promoting `staging` into `main`, require a fresh `staging` branch, passing CI, and explicit human QA for meaningful user-facing changes.
- If work touches remote deployment paths, include `pnpm run remote:generate-types:check` and `pnpm run remote:prepare-db:check`.
- Do not claim completion without stating what was actually validated.
- Do not treat doc updates, commits, pushes, or PR creation as separate "completion" events that each deserve a fresh final-summary block.

## Coding Style & Naming Conventions

- Rust: `rustfmt` enforced (`rustfmt.toml`); group imports by crate; snake_case modules, PascalCase types.
- TypeScript and React: ESLint + Prettier (2 spaces, single quotes, 80 cols). PascalCase components, camelCase vars/functions, kebab-case file names where practical.
- Keep functions small, add `Debug` / `Serialize` / `Deserialize` where useful, and add tests for new behavior or edge cases.

## Agent Summary Standard

- Use this structure only for the final user-facing completion message of a task:
  - `Validation`
  - `What changed`
  - `Why it matters`
  - `What's next`
  - `PR`
  - `Docs`
  - `Churn`
  - `Human Needed`
  - `Commit/Push`
  - `Preview URL`
  - `Branch`
  - `Worktree`
- Emit this full structured summary once per user task, at the actual end of the task.
- After that summary has been sent, do not send another full completion-summary block for follow-up actions on the same task unless the user has clearly started a new task.
- If the user asks for a narrow follow-up inside the same task, answer that request directly and briefly instead of re-summarizing the whole task.
- Keep the first four sections as short complete-sentence narrative.
- Keep metadata lines compact with `::` separators.
- Keep intermediate progress updates brief instead of reusing the full summary block.

## Security & Config Tips

- Use `.env` for local overrides; never commit secrets.
- Key envs: `FRONTEND_PORT`, `BACKEND_PORT`, `HOST`, `VK_ALLOWED_ORIGINS`.
- Dev ports and assets are managed by `scripts/setup-dev-environment.js`.

## Forbidden Behaviors

- Do not treat branch-local notes as repo-wide truth.
- Do not release unvalidated changes into the local instance just because CI would probably pass.
- Do not leave continuity state only in chat.
- Do not edit generated shared type files manually.
- Do not emit multiple final-summary reports for the same task.
- Do not leave required continuity-doc or PR work undone when the branch is otherwise ready, unless you state the blocker clearly.
