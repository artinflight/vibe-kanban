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

Implementation is committed as `a6ec09b12`. Operator-authorized frontend-only
rollout uses live-baseline backport `5d6ed3539` on
`hotfix/goal-checkpoint-frontend`, built in
`/mnt/vk-storage/vk-goal-checkpoint-render/deploy-source`. The full feature branch
was not deployed because it includes newer backend-dependent conversation paging.
Frontend pointer now selects `release-5d6ed3539` under that SSD task directory.
Backend PID2590517 remains unchanged. See HANDOFF.md for checks and rollback.
No PR or push has been performed.
