# Release preparation / efficiency integration

Base: staging `7110930b6d9d1fa3f403a963a1ded49140b3eec1` (PR262 merged).
PR266: `perf/usage-efficiency-20261017`. Source implementation stays with existing
Automatic Restart Preflight; Staging owns this integration and release acceptance.
No new execution owner or nightly job.

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
