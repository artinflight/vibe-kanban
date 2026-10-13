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

### Follow-up reporting scope

Natural progress questions about existing outputs are classified before semantic
inference when the completed reply identifies the output. Recommendation
questions require a named Recommend mode or recorded/observed/generated
model or routing recommendations. A prior suggestion alone is insufficient. The closed reporting
grammar excludes extra actions, safety judgments, new advice, unresolved pronouns
and unknown topics. Existing failure and protected-context checks still apply.

This uses the existing `completed_context_bounded_record` evidence. No cache or
new cost assumption is added: a missing classifier trace is still unknown unless
an exact reviewed zero-inference receipt establishes that path. The synthetic
candidate check expects Sol6/low in Recommend under the existing registry; it is
not proof of account availability, cheaper execution quality or savings.

A hosted pure-policy job exercises the real context/assessment/semantic/worker
validator/candidate functions without a subprocess sandbox or inference. It is
not executor or same-process reload acceptance, and produces no publishable
worker. The existing full-sandbox job and independent review remain required.

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
`complete: true`, native observation `timestamp`, `accountScope`, `regime`, `weightVersion`, a
source `provenance`, and `tokens` containing `input`,
`cachedInput`, `output`, optional `reasoning`. Export these from already verified
native/CodexUsage attribution; this script cannot certify a fabricated export.
For a turn with usage spanning regimes or rate windows, supply `events`: additive
native usage deltas with distinct `eventId`, timestamp, exact settings, regime,
weightVersion, accountScope, complete/provenance and tokens. Their sums must equal
the turn totals. Identical immutable duplicates are deduplicated; conflicting
ones remain unknown. A supplied aggregate timestamp must equal the last event.
Aggregate regime/version, if supplied, must agree with every event. Do not label
a multi-regime cumulative total as a single event in the final regime.

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
`per_million_tokens`, nonnegative decimal `uncachedInput`, `cachedInput`, `output`,
and explicit `regime` and `weightVersion` (or reviewed evidence defaults). A rate
may have its own validFrom/validUntil within the overall evidence interval.
The package version and sourceVersion describe provenance; they cannot substitute
for an event's missing weightVersion/regime. Only a single exact matching rate
may be applied. Applicability is **start-inclusive, end-exclusive per event**.
Expired-now weights still price historical in-window events; currently valid
weights cannot price older out-of-window events. No report-time/admission-time
fallback. Conflicting timestamps, regimes, versions or accounts remain unknown.
If exporters supply `timestampSources`, `regimeSources`, `weightVersionSources`
or `accountSources`, all observations must agree with the event's fields.
Missing model/settings/account-compatible weights remain unknown. Native
observation dates must fall within the reviewed weight validity window; an
admission timestamp is not a substitute. To price classifier overhead, include
its exact native thread/turn observation in the usage export as well, with tokens
matching the persisted trace. Classifier timing and applicability are independent
of the parent execution. Units cannot
be mixed. Weights are estimates with provenance, not observed provider billing.

### Verified zero-inference paths

Absence of a semantic trace never proves zero overhead. Optional
`--classifier-proof` reads private immutable JSONL, schema
`vk.autoswitch.classifier-path.v1`: executionId, decisionId, verified true,
integer calls zero, path, moduleManifestSha256 and reviewed provenance
(reviewRef/sourceSha256). Allowed paths are the existing
completed_context_reference_lookup and completed_context_bounded_record.
The exact decision ID, execution ID and pinned module hash must match persisted
triage evidence, with no bounded_semantic_fallback marker. An actual semantic
trace remains authoritative over a contradictory zero-call receipt.
Without this explicit reviewed receipt, classifier cost remains unknown.
This is an offline accounting receipt, not a classifier cache or routing change.

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

## Review correction and current acceptance boundary

Earlier hosted executor/reload runs changed AppArmor settings without
operator authorization and **are not accepted validation**. Their receipts are
retained, superseded. The first corrective commit removes the AutoSwitch
workflow's install/sysctl step. The normal PR workflow's AppArmor profile-loader
was also removed before pushing: both routes require
a supported sandbox under unchanged security settings and stop if unavailable.
The user subsequently approved only the official Ubuntu Bubblewrap package on
disposable GitHub Ubuntu runners. The package install is runner-guarded, with
read-only before/after hashes of restriction values and AppArmor state/profiles;
any difference stops validation. No persistent host install, custom profile,
security configuration change or capability grant. The unchanged sandbox probe
and non-privileged binary checks remain mandatory after installation.
A restricted runner is a validation blocker, never permission for a bypass.
No merge, new publication, rollback, backend restart or policy/model change is
part of this correction. The known prior live publication is preserved.

Offline accounting regressions cover per-event half-open date boundaries,
historical expiration, changed regimes/versions, classifier-specific timing,
per-event recovery cost, conflict/absence handling and reviewed no-inference
receipts. Fictional fixture units never become allowance or billing weights.
Static workflow assertions forbid the removed security-changing commands.
Final exact-source executor/reload acceptance and independent review remain
required before further module publication. Local accounting tests do not
replace that requirement.

The earlier private 32-case replay changed only two documentation/status cases
and skipped their classifier; it is diagnostic evidence, not clean final-source
acceptance or cheaper-model quality. The 117-turn admission report had 107
Astra/high, seven Sol6.1/medium and three Sol6/low recommendations versus 101
actual Sol6.1/high, 13 Astra/xhigh and three missing bindings. Known classifier
subtotal was 223,300 input (31,744 cached), 10,024 output (6,343 reasoning), with
two incomplete trace usages. The corrected read-only rerun identifies 74 absent classifier traces without
reviewed zero-inference receipts, in addition to the two incomplete traces.
These 76 uncertain usages are coverage gaps, not zero cost. Complete native usage, applicable subscription
weights and comparable accepted outcomes remain uncertified: no monetary or
allowance saving is claimed. Private IDs/inputs remain outside this repository.
