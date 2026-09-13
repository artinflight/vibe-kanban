# STREAM.md

## Current Scope

- Branch: `vk/70a7-vk-goal-based-ag`, based on fork staging `9a2591916`.
- Objective: render trailing goal checkpoint protocol blocks as readable chat cards.
- Scope: shared assistant-message renderer, defensive parser and rendering tests.
- Valid checkpoints show disposition and reason with expandable requirements,
  verification evidence and recovery plan. Empty maps do not imply goal completion.
- Stored messages and goal scheduling remain unchanged. Ordinary text, code
  examples, malformed payloads and incomplete streaming blocks retain Markdown.

## Status and next steps

Implementation is prepared locally. See the latest HANDOFF.md entry for checks.
Browser preview and deployment have not been performed. No services, production
assets, routes or live data were changed. Production rollout is a separate step.
