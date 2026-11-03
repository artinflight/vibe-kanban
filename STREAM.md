# Prevent Codex resume history duplication — 2026-11-03

Branch `vk/95c6-vk-duplicate-con`, based on verified fork/staging
`d90e347461688c06f55713e8a1057c52e51cfd00`. Backend executor change only.

The OS-drive investigation found that native initialize returns
`vibe-codex-executor/0.159.2`, while the existing narrow-resume guard recognizes
only `codex_cli_rs/0.159.2`. Every resumed execution consequently captures the
entire prior thread again. Accept both exact qualified client/version identities;
retain original behavior for every other version/name and the existing empty-turn
verification. No history rewriting, schema, frontend or generated-type changes.

Regression fixtures now return prior turns whenever excludeTurns is absent.
Exercise the actual client for ordinary, delegated and deadline-bound resumes,
retained metadata/new deltas, ignored-flag rejection and legacy compatibility.
Validation and rollout requirements are recorded in `VK_DUPLICATE_HISTORY_FIX.md`.

[PR #290](https://github.com/artinflight/vibe-kanban/pull/290) targets staging with
rebase; final checks and the merge event govern integration and rebased IDs. Local
full Rust check/lint require missing host GLib development metadata; the workspace
test attempt was stopped on that known prerequisite. Hosted PR checks provide
the broad validation gate. Frontend types/lint, format and ops pass locally.

Source repair is not deployed. Existing accumulated logs remain intact. A backend
build/restart needs fresh backup, private history bindings, coordinated drain,
current-data fallback rehearsal and post-install persisted-size/history/send QA
under the existing deployment runbook. Preserve current public frontend features.
No provider inference, agent interruption or cleanup is part of this source fix.

Full historical archive: [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).
