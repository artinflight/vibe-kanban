# STREAM.md

## Stream Identifier

- Branch: `vk/a6c2-vk-multi-line-in`
- Repo:
  `/home/mcp/code/worktrees/a6c2-vk-multi-line-in/_vibe_kanban_repo`
- Base: `fork/staging` at `89fb5724f`
- Working mode: workspace create prompt multiline paste fix

## Objective

- Preserve multiline clipboard text when pasting into the workspace creation
  chat editor.

## In Scope

- Shared editor paste behavior used by workspace creation and session chat.
- Focused type-check, lint, formatting, and source-level paste validation.
- Branch-local continuity notes.

## Out of Scope

- Live VK service restart or deployment.
- Backend workspace creation behavior.
- Broader editor redesign.

## Current Status

- Rebased onto `fork/staging`, which already includes the high-priority
  multiline paste guard from `fix/multiline-paste-priority`.
- Kept the additional markdown conversion behavior so non-raw paste conversion
  preserves clipboard newline boundaries when it reaches the markdown path.
- No live deploy, frontend symlink swap, service restart, or live DB mutation
  has been performed in this branch session.

## Relevant Files / Modules

- `packages/ui/src/components/PasteMarkdownPlugin.tsx`
- `scripts/vk_live_regression_smoke.py`
- `packages/web-core/src/shared/components/WYSIWYGEditor.tsx`
- `packages/web-core/src/shared/components/CreateChatBoxContainer.tsx`

## Validation So Far

- `pnpm install --offline --frozen-lockfile`
- `pnpm --filter @vibe/ui run check`
- `pnpm --filter @vibe/ui run lint`
- `pnpm run format`
- `git diff --check`
- Local Lexical reproduction confirmed multiline text serializes as:
  `first line\nsecond line\n\nthird line`

## Validation Gaps

- Browser UI smoke has not been run yet.
- Full repository checks have not been run in this worktree after rebase.

## Next Safe Steps

1. Finish the rebase and merge into local `staging`.
2. Run focused validation after the merge.
3. Push `staging` only if the operator asks for remote publication.
