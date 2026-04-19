# Vibe Kanban Documentation And Continuity

## Purpose

This document defines how this fork keeps durable operating context visible for agents and the operator.

## Core Rule

Critical repo and local-runtime context must live in the repo, not only in chat.

## Required Root Docs

### `README.md`

- Explains what the repo is and where the ops docs live.
- Update it when setup, release path, or operator entry points materially change.

### `AGENTS.md`

- Holds stable repo rules.
- Keep it concise and stable.
- Update only when repo rules change.

### `STATE.md`

- Holds repo-wide truth.
- Update only when the repo-wide operating state changes.
- Do not place task-branch-only scope here.

### `STREAM.md`

- Holds active branch scope and decisions.
- Update it when the current stream changes direction, scope, or next-safe steps.

### `HANDOFF.md`

- Holds the short next-agent pickup note.
- Replace sections as truth changes; do not append diary-style history.

### `DELTA.md`

- Holds the append-only checkpoint ledger.
- Add compact entries for meaningful changes, reversals, blockers, or handoff state changes.

### `REPO_IDENTITY.md`

- Explains why this fork exists and how it should promote work upstream.
- Update when the fork's role or release path changes.

## Required Supporting Ops Docs

- `docs/audits/vibe-kanban-ops-audit.md`: current audit record against the Ops Playbook baseline
- `docs/standards/*.md`: repo-specific standards that specialize the baseline
- `docs/adoption/*.md`: rollout guidance for keeping this fork aligned with the playbook
- `docs/operations/release-safety.md`: safe branch-to-release path
- `docs/operations/local-instance-qa-checklist.md`: repeatable manual QA and local-instance readiness checklist

## Stable Rules Versus Current State

- `AGENTS.md`: stable rules
- `STATE.md`: repo-wide truth
- `STREAM.md`: branch-local scope
- `HANDOFF.md`: immediate pickup context
- `DELTA.md`: historical continuity

If those roles blur, concurrent agent work becomes unreliable quickly.

## Completion Summary Standard

This repo uses the standardized final completion-summary format from `AGENTS.md`.

Rules:

1. Use the full structure only for the final user-facing completion message of a task or turn.
2. Keep progress updates short and lightweight.
3. Keep `Validation`, `What changed`, `Why it matters`, and `What's next` as short narrative sections in complete sentences.
4. Keep the metadata block compact and consistently formatted.
5. Do not reuse the same headings in continuity docs unless they are the actual final user-facing summary.

## Cold-Start Standard

A new agent should be able to:

- read the required docs in order
- determine what is repo truth versus branch truth
- see the current branch objective
- understand the local-validation requirement
- continue safely without hidden prior chat
