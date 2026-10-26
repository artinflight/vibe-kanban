# Direct launcher Claude support — T68

Branch `vk/695f-vk-direct-launch` starts from fork staging `5b43524ea`.
The new focused issue `0eb31691-b6e1-406a-a2b9-a4b9bf5ca1f2` (T68) was
created and linked before code work. Scope: direct connector executor/schema and
Claude dispatch, plus an explicit idempotent idle-checkpoint Codex handoff.
See [contract, limits and validation](VK_DIRECT_LAUNCHER_CLAUDE.md).
Draft PR281 remains open into staging. The approved adapter/launcher files are
installed; a live disposable Claude initial turn passed. Runtime adoption is
pending a connector-only worker restart (separately blocked by automatic review)
and refresh of Dot's cached workspace schema. One approved continuation remains;
do not duplicate the initial turn. No Vibe restart, Staging Check/control,
production-session experiment, billing/global-setting, merge or recovery-data
change is part of this connector-only action.

The following inherited stream notes describe earlier work, not this branch's
implementation or release authority.

# Collapsible Issues release stream

Current branch prepares the accepted collapsible issue UI for rebase-merge
into staging and a frontend-only live release. See
[feature, validation and release evidence](VK_COLLAPSIBLE_ISSUES.md).
Preserve the compact indexes and all existing release protections below.

# Usage-efficiency follow-up: compact job outcomes

Base: staging `d0b0bb298` (PR266 merged). Branch:
`fix/compact-job-outcomes-20261017`, existing Automatic Restart Preflight owner.
This follow-up adds bounded durable outcomes to the existing runner and measures
actual JSON payload reduction. Approval-review share is not evidence of waste;
models, AutoSwitch, all approval checks and QA remain unchanged. Staging retains
release ownership; no new execution owner or nightly job.

Seamus authorized reducing repeated pickup input and redundant work while
keeping models, effort, AutoSwitch, full history and acceptance unchanged.
Scope: lossless continuity archives and concise current indexes, adoption of
the existing fingerprinted `scripts/deployment/vk_prepare.py` result reuse,
and narrow shared-job correctness fixes coordinated with their existing owners.

Staging owns combined release/native queue recorder-drain acceptance. Nightly
workspace604d/PR263 owns producer completion, capture reconciliation, B package,
whole-plan recovery and schedule activation. Do not edit their workspaces,
duplicate jobs/stores, compile another candidate or claim their pending checks.
All runtime, admission, data, security and human-QA constraints in [STATE](STATE.md)
remain active. No production change is part of this stream.

Validation must show exact archival preservation and bounded pickup input,
then exercise the existing Preparation runner with identical commands and
acceptance before/after reuse. Count actual command launches and repeated
input bytes; do not infer tokens, money or model-call savings from byte counts.
Any model-workflow claim needs actual same-model provider evidence.

Read [the efficiency evidence/contract](USAGE_EFFICIENCY.md) for current results
and unresolved acceptance. The full prior branch histories, constraints,
identities and receipts remain in [STREAM history](STREAM_HISTORY_20261017.md),
indexed and hash-bound by [the archive manifest](CONTINUITY_ARCHIVE.json).

Current release coordination, newer Sidebar adoption and remaining private gates:
[October 17 release status](VK_RELEASE_COORDINATION_20261017.md).
