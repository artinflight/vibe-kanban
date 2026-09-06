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
- Mutating the live Codex profile before Astra is advertised by the installed
  Codex CLI and account.

## Current Status

- Official OpenAI documentation confirms the model ID `gpt-6-astra` and the
  `xhigh` reasoning effort.
- Source now exposes GPT-6 Astra first in Codex discovery and uses it with
  `xhigh` as the fallback for new Codex configurations.
- Green's installed Codex CLI `0.149.0` does not yet include Astra in
  `codex debug models`; rollout remains blocked on runtime availability.
