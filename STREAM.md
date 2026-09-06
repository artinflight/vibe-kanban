# STREAM.md

## Stream Identifier

- Branch: `vk/273f-vk-update-codex`
- Repo: `/home/mcp/code/worktrees/273f-vk-update-codex/_vibe_kanban_repo`
- Working mode: isolated feature branch

## Objective

- Update the Codex default model from GPT-5.6 Sol to GPT-6 Astra.

## In Scope

- Codex model discovery and new-configuration defaults.
- Focused validation and continuity documentation.

## Out of Scope

- Replacing explicit or persisted model choices for existing sessions.
- Restarting or deploying the green instance.

## Current Status

- Official OpenAI documentation confirms the model ID `gpt-6-astra` and the
  `xhigh` reasoning effort.
- Source now exposes GPT-6 Astra first in Codex discovery and uses it with
  `xhigh` as the fallback for new Codex configurations.
- Green's live `DEFAULT` profile now uses `gpt-6-astra` with `xhigh` reasoning.
  The live preset-options endpoint exposes Astra to the existing frontend model
  menu without a backend restart.
- Localhost and `https://vibe.local` API verification passed; green's PID stayed
  `2886161`.
- The live menu now labels Astra as `GPT-6 Astra` and filters Codex choices to
  GPT-6 Astra plus GPT-5.6 Sol, Terra, and Luna. The served main bundle is
  `/assets/index-DKNgBi1_.js`; green's PID remains unchanged.
