# STREAM.md

## Stream Identifier

- Branch: `vk/739e-vk-single-line-c`
- Repo: `/home/mcp/code/worktrees/739e-vk-single-line-c/_vibe_kanban_repo`
- Base: `staging`
- Working mode: targeted frontend editor fix

## Objective

- Fix the chat/editor inline-code path where single-backtick code spans can leave the cursor stuck in code formatting and make the closing backtick effectively undeletable.

## In Scope

- Shared Lexical WYSIWYG editor behavior used by local chat and issue editors.
- Inline-code backtick escape behavior.
- Markdown synchronization cleanup for editor-only cursor spacer characters.

## Out of Scope

- Fenced multi-line code block editing behavior beyond existing `CodeBlockEscapePlugin` behavior.
- Backend, executor, and deployment changes.
- Broad editor refactors or UI redesign.

## Current Status

- Implemented in `packages/ui/src/components/InlineCodeBoundaryPlugin.tsx`:
  - closing backtick handling now runs in capture phase before markdown shortcuts can consume it
  - empty code-formatted cursor states can leave inline code mode
  - text-node inline code still exits through a plain zero-width cursor target
- Implemented in `packages/ui/src/components/MarkdownSyncPlugin.tsx`:
  - editor-only zero-width cursor spacers are stripped when importing and exporting markdown
  - the controlled markdown value no longer persists invisible spacer characters

## Validation

- `pnpm i`
- `pnpm run format`
- `pnpm --filter @vibe/ui run check`
- `pnpm --filter @vibe/web-core run check`
- `pnpm --filter @vibe/ui run lint`
- `pnpm --filter @vibe/local-web run build`

## Known Notes

- The local-web build passed with existing non-blocking Vite/Sentry/chunk warnings.
- No backend validation was run because this change is confined to shared frontend editor plugins.
