# Vibe Kanban Agent Rules

## Purpose

This document defines the expected agent behavior for this fork on top of the repo's stable rules.

## Before Editing

Agents should:

1. Read the required continuity docs in order.
2. Confirm the current branch and stream scope.
3. Verify the requested task against actual repo state.
4. Identify whether the change affects the local VK runtime, upstream promotion path, or both.

## Scope Discipline

Agents must:

- stay within the assigned stream
- avoid mixing unrelated cleanup into feature or recovery work
- update `STREAM.md` if branch scope changes
- keep repo-wide truth out of branch-local docs and vice versa

## Local Runtime Safety

Agents must not:

- re-enable shared cloud API settings for the local install unless the task explicitly requires it
- claim local rollout safety without stating what was exercised
- replace the local DB or risky runtime state without a fresh backup path

## Reporting Rules

Agents must leave durable state by:

- updating continuity docs when truth changes
- recording local validation, code validation, and remaining gaps separately
- stating when human QA or GitHub branch-protection work is still required
- keeping handoffs usable for a fresh cold-start agent
- emitting one final completion summary per task instead of repeating completion reports after each follow-up step

## PR Execution Rules

Agents should:

- treat PR work as part of finishing the branch, not as optional aftercare
- push the branch and open or update the corresponding PR when the branch is review-ready unless the user says not to or a concrete blocker prevents it
- state the exact blocker if PR work could not be completed
- keep PR scope aligned with `STREAM.md` and the actual branch contents

## Concurrent Development Rules

When multiple streams are active:

- one branch should represent one stream
- one PR should represent one concern
- branch-local intent belongs in `STREAM.md`
- superseded or abandoned streams should be closed or explicitly marked

## Confusion Handling

If docs, code, or live behavior disagree:

1. Verify code and branch reality first.
2. Verify the local runtime or API when the task touches user-visible behavior.
3. Update stale docs if truth is clear.
4. Escalate only the unresolved risk.
