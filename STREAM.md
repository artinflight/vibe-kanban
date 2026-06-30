# STREAM.md

## Stream Identifier

- Branch: `fix/multiline-paste-priority`
- Repo: `/tmp/vk-paste-pr`
- Base: `fork/staging` at `eb90083db`
- Working mode: focused staging PR

## Objective

- Preserve multiline chat paste in VK by making the custom paste handler handle
  multiline plain text before Lexical's default rich paste path can consume
  clipboards that also include HTML.

## In Scope

- `PasteMarkdownPlugin` multiline/rich clipboard behavior.
- Read-only smoke guard for the paste source invariant.
- Continuity notes for this branch.

## Out of Scope

- Restarting `vibe-kanban.service`.
- Switching the live frontend symlink.
- Deploying binaries or assets.
- Mutating live DB/project records from this source task.
- Reworking broader workspace creation, project settings UI, lab runtime, or
  deployment workflows.

## Stream-Specific Decisions

- Feature workspaces may prepare code, checks, preview, docs, and PRs.
- Feature workspaces must not restart or deploy the live VK service.
- This branch must merge to `staging`; the next VK release/restart package can
  then include it through the normal VK repo project workflow.

## Relevant Files / Modules

- `packages/ui/src/components/PasteMarkdownPlugin.tsx`
- `scripts/vk_live_regression_smoke.py`
- `STATE.md`
- `STREAM.md`
- `HANDOFF.md`
- `DELTA.md`

## Current Status

- `PasteMarkdownPlugin` detects multiline `text/plain` before the HTML opt-out,
  inserts it with `selection.insertRawText`, and registers the command at
  `COMMAND_PRIORITY_HIGH`.
- `scripts/vk_live_regression_smoke.py` checks that the source paste handler
  still has the multiline guard and does not use `COMMAND_PRIORITY_LOW`.
- No live deploy, frontend symlink swap, service restart, or live DB mutation
  has been performed in this branch session.

## Risks / Regression Traps

- The canonical checkout `/home/mcp/_vibe_kanban_repo` may be intentionally
  dirty; do not build or deploy from it just because it is canonical.
- Branch names in historical handoffs can be stale; trust the checked-out branch
  and code first.
- A workspace name that looks like VK work is not proof that the workspace
  contains the VK repo.
- `VK_AGENT_DEPLOYMENT_RUNBOOK.md` contains deploy instructions, but this branch
  does not grant permission to restart or deploy production VK.
- The smoke script is intentionally narrow and read-only. It does not replace
  UI/browser validation for a release candidate.

## Next Safe Steps

1. Run formatting and focused script validation.
2. Optionally run the live smoke script if `https://vibe.local` is reachable.
3. Create or inspect a throwaway `VK Dev` workspace to verify the guard runs in
   the generated workspace context.
4. Open a PR into `staging` after validation.
