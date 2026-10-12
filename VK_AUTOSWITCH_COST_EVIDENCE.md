# Current-step routing and actual-baseline cost evidence

Recommend remains required. This change does not switch selected models, activate
Auto, spend credits, edit global profiles or require a service restart.

## Current-step classification

The stateless protocol-2 worker now recognizes exact short status/report requests
and simple records of supplied facts in existing documentation when completed
context is available. These are assignments rather than acknowledgements or an
instruction to resume an earlier operation. The existing known-link fast path is
unchanged. No classification cache is introduced.

Every request is reassessed. Current protected repository/prompt risk, failed
validation, missing completed context, unresolved scope, extra requested actions,
manual locks, exclusions and explicit floors remain authoritative. Generic
approvals and continuation keep the surrounding assignment. A routine reporting
step preserves that assignment in existing triage evidence so later work cannot
inherit its lower qualification. No qualification/model/preference changes.

Classifier instructions distinguish unknown answers and unspecified verification
wording from engineering complexity. They explicitly classify bounded recording
and factual reporting as steps, while genuine diagnosis and protected operations
retain their existing minimums. Native semantic evidence is not rewritten to
invent confidence or erase risk.

## Read-only cost report

`scripts/vk-autoswitch-cost-report.py` reads VK decisions and the existing
`vk.routing.v1` feed. It joins actual execution by exact native thread/turn IDs;
the recommendation and requested settings remain separate. It never reads native
session files, changes routing, retries agents or performs inference. Reports
contain private operational IDs: keep them local and do not attach them to PRs.

Example (replace paths and UTC window with the nominated private inputs):

```sh
python3 scripts/vk-autoswitch-cost-report.py \
  --db /approved/private/vk.sqlite \
  --routing-feed /approved/private/routing.jsonl \
  --start 2026-10-11T00:00:00Z --end 2026-10-12T00:00:00Z
```

Use consistent database timestamp formatting for the supplied window. The DB is
opened read-only with `query_only`; no database/configuration migration is needed.
Classifier input, cached input, output and reasoning are reported separately.
Cached input is a subset of input; reasoning is a subset of output and is never
charged twice. Unobserved classifier attempts and native turns remain unknown.
Process completion does not establish review acceptance. Confidence and model
qualification are separate gates, neither is measured code quality.

### Optional exact native usage export

`--usage` accepts private JSONL records with schema `vk.autoswitch.usage.v1`, exact
`nativeThreadId`/`nativeTurnId`, native `model`, `reasoningEffort`, `serviceTier`,
`complete: true`, a source `provenance`, and `tokens` containing `input`,
`cachedInput`, `output`, optional `reasoning`. Export these from already verified
native/CodexUsage attribution; this script cannot certify a fabricated export.
Missing effort/tier/usage and conflicting bindings/settings cannot be replaced
by requested settings or a timestamp-nearest guess. No CU source/schema change.

### Optional reviewed cost weights

No billing weights are shipped. Preference/cost ranks never become money or
subscription-allowance multipliers. `--weights` requires `--weight-evidence`.
Schema `vk.autoswitch.weights.v1` requires a version, and provenance with kind
`verified_telemetry` or `versioned_authoritative`, source, sourceVersion,
sourceSha256, unit, accountScope, validFrom and validUntil. The exact evidence
JSON must match those provenance fields and the supplied rates. Its SHA-256 must
match. The evidence must have been reviewed as authoritative by its owner;
matching hashes prove integrity, not authority or applicability of API prices to
subscription usage. Test fixtures use fictional units only.

Each rate has exact `model`, `reasoningEffort`, `serviceTier`, basis
`per_million_tokens`, nonnegative decimal `uncachedInput`, `cachedInput`, `output`.
Missing model/settings/account-compatible weights remain unknown. Units cannot
be mixed. Weights are estimates with provenance, not observed provider billing.

### Recovery and comparable outcomes

Explicit escalation parent IDs join initial and recovery attempts, including
their classification overhead. Ordinary follow-ups, siblings and time proximity
are not assumed to be retries. Missing parents/attempt usage makes total cost
unknown. Undeclared review corrections/rework remain a coverage gap.

An optional `--outcomes` private JSONL export uses schema
`vk.autoswitch.comparison.v1`, comparisonId, baselineAttemptIds,
candidateAttemptIds, comparable, allAttemptsAccounted, qualityGate `accepted_both`, and provenance.
Only a reviewed, comparable pair with all known attributable attempts and
matching account/unit weights yields a measured-usage weighted net difference.
Completion/recommendation/replay alone never yields accepted-task savings.

The report may show a **same-token-demand scenario** for a qualified candidate,
priced against the actually executed baseline. Its unknown lower-model token
demand, retry/rework and comparable accepted result are explicit; net savings
stays null. This is not an all-Astra counterfactual, a percentage saving or proof
that a cheaper model completed the task. With incomplete real evidence, the
report exposes opportunities and missing observations rather than a saving.

## Validation and rollout boundary

Focused Rust module/context/semantic regressions, isolated same-process reload,
private recorded-case replay and Python accounting tests are the validation
boundary. Hosted tests contain anonymized synthetic fixtures, not private prompts
or operational IDs. No new paid semantic trial is needed for deterministic cases.

Compatible worker/instruction updates can use the installed protocol-2 pinned
validator and immutable prepare/publish path only after matching live identity,
unchanged model policy/settings, validator compatibility and end-to-end reload
acceptance. Otherwise package for Staging's separately authorized adoption.
The cost reporter is an offline source tool, not a backend scheduling service.

October 30 remains the useful-beta deadline. Real Recommend observations and
reviewed native usage/weight/comparable-outcome coverage, rather than a broad
benchmark campaign, are the remaining evidence needed before any Auto decision.
