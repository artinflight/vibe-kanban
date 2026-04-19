# Vibe Kanban Ops Adoption

## Purpose

This document explains how the Ops Playbook baseline is specialized for this Vibe Kanban fork.

## What We Imported From Ops Playbook

- the root continuity document model
- the distinction between stable rules, repo truth, branch truth, handoff state, and append-only history
- the `staging` to `main` promotion model
- branch policy and branch freshness enforcement
- the final-message-only completion-summary format

## What Stayed Repo-Specific

- the local-only Vibe Kanban runtime and backup posture
- validation through a real local VK instance before promotion
- existing Rust, TypeScript, SQLx, and release workflows
- remote-specific checks for `crates/remote`

## Safe Adoption Sequence For This Fork

1. Keep the root continuity docs current.
2. Keep the branch model documented as task branch -> `staging` -> `main`.
3. Require local-instance validation before a branch is considered safe for `staging`.
4. Keep the existing CI and release workflows as the authoritative automation layer.
5. Use repo-specific standards docs to explain where VK is stricter than the baseline.

## Current Adoption Status

Completed:

- continuity docs exist at repo root
- audit and release-safety docs exist
- branch policy, freshness, and ops-governance checks exist
- repo-specific standards and adoption docs now exist
- a repeatable local-instance QA checklist now exists

Still requires human or GitHub setup:

- create and protect the actual `staging` branch on GitHub if it does not already exist upstream for this fork
- align branch protection with the documented `staging` to `main` path
- keep using the local VK instance for branch-level manual validation

## Deferred Or Optional

- stale worktree cleanup automation
- stricter continuity-doc linting beyond the current required-files check
- richer QA checklists for specific product areas as those workflows stabilize
