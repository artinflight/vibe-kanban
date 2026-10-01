# Automatic task assessment and qualified-pair routing

This extends accepted V1 on `vk/5a81-autoswitch-cu-recovery`; it does not replace
its execution lifecycle, native verification, manual controls or CU producer.
It is source implementation, not a production activation. Version remains 0.1.42.

## Assessment and minimum capability

New Auto/Shadow choices default to **Automatic — assess this task**, serialized
as `floor: assessed`. Missing floor also means assessed. Existing saved explicit
routine/workhorse/frontier values retain their meaning; old V1 Workhorse defaults
are preserved because they cannot be distinguished safely from deliberate locks.
Choose Automatic once for those saved configurations to permit downward routing.

`routing_assessment.rs` performs deterministic checks on the submitted prompt:

| Envelope | Positive evidence / risk | Minimum | Initial preferred verified pair |
| --- | --- | --- | --- |
| Mechanical | Text-only typo, spelling, punctuation, link or Markdown edit with documentation/label scope | Routine | 5.6 Luna/low; medium without low proof |
| Bounded | Local/existing-pattern UI, tests or boilerplate, with named deterministic validation | Routine | 6 Luna/medium |
| Validated fix | Localized fix/refactor with a reproducing/regression/unit test | Workhorse | 6 Sol/medium |
| Normal | General implementation or insufficient evidence for cheap routing | Workhorse | 6.1 Sol/medium |
| Complex | Architecture, novel/cross-cutting work, unfamiliar debugging or long autonomy | Workhorse | 6.1 Sol/medium |
| Protected | Security, permissions, migrations, destructive work, concurrency, deployment/control plane | Frontier | Astra/high |

Risk checks precede cheap classifications. Explicit absence of validation prevents
bounded/fix qualification; a long requirements surface prevents routine routing.
Effective minimum is the maximum of assessment, explicit user floor and persisted
prior execution floor. Follow-up wording never silently lowers an established
session floor. New independent tasks can assess downward without manual labels.

Deterministic evidence remains the zero-inference path. Materially uncertain normal
requests can now use one bounded semantic classification turn, described below.
Neither layer proves tests exist or pass. Unknown context retains Workhorse;
security hidden from the available context still requires review and validation.

## Qualification and selection

`routing_models.json` retains all seven models. Each model now has explicit
`qualifications` rows: `{effort, envelope, status, floor, preference_rank}`.
Status is `qualified`, `experimental`, `denied`, or `minimum_required`.
Experimental rows are eligible only in Shadow; missing/denied rows never qualify.
Minimum-required rows establish an allowlist for their protected envelope.
Duplicate effort/envelope rows and invalid effort/envelope/floor values fail closed.
Older custom policies without qualification rows pause Auto instead of guessing.

Selection intersects released policy, envelope qualification, effective minimum,
exclusions, runtime effort support and fresh exact account/launcher/home execution
proof. It sorts surviving pairs by configurable preference_rank, then stable model
ID/effort tie-breakers. No safe candidate means pause. There is no assumption that
model names form a total intelligence order. Model-level cost_rank is retained for
old configuration readability; **pair preference_rank controls V2 selection**.
Ranks express policy preference, not API dollars or subscription billing weights.
The service tier remains standard under the V1 automatic execution contract;
explicit priority/fast settings remain available through manual selection.

Older 5.6 Luna is seeded for mechanical work, Terra for mechanical/bounded work,
and Sol for mechanical/bounded/validated/normal fallback. New Luna handles bounded
work; Sol6 handles validated fixes; Sol6.1 remains the normal/complex workhorse.
Astra qualifies as a safe fallback and is the protected-envelope minimum.
These are reviewable initial qualifications, not measured quality equivalence.

Luna/low is qualified only for mechanical work and still requires exact low-effort
execution proof. Sol6/low for bounded work and Sol6/medium for complex work are
experimental. Shadow may recommend experimental pairs without applying them.
Change qualification/ranks through `VK_CODEX_ROUTING_MODELS`; do not weaken the
separate executable-pair proof requirement. Promote from observed real work and
review outcomes, not token volume alone.

## Escalation and human control

V1 process failure escalation remains. Ordinary follow-ups also recognize explicit
operator reports such as repeated test failure, rejected review, violated invariant,
unsuccessful fix and no verified progress. They are labeled
`operator_reported_validation_failure`, never presented as automatically observed
test results. Newly assessed higher-risk scope records `risk_expansion_*`.
Both require existing escalation consent in Auto. No confidence score is used.
No background retry, active-turn switch, dirty reset or new scheduler is added.
A failed frontier attempt pauses for diagnosis. Pinned native goal continuations
retain their existing model and lifecycle behavior.

Manual model/effort changes lock Manual and retain stored floor/exclusion/consent
constraints for later Auto use. Existing explicit Workhorse/Frontier floors and
Astra exclusions remain hard constraints. Natural-language model directives are
not a replacement for those explicit controls. Shadow never changes execution.

## Observation, feedback and rollout

RoutingDecision version2 stores the assessed classification/evidence in reason,
effective floor, selected pair and predecessor. Existing raw logs show actual model,
effort, recommendation, reason, floor and escalation status. CU wire schema remains
`vk.routing.v1`; version2 decisions advertise `policyVersion: vk-autoswitch-v2`.
Manual/older decisions retain v1 identity. Canonical CU contract/fixture bytes are
unchanged; only the policy version value changes, allowed by the wire schema.

Existing execution IDs, native bindings, end outcomes and transition links support
per-pair/envelope review, failure/recovery cost and cache/output accounting. CU does
not write qualification policy or gate this implementation on allowance pricing.
Promotion remains an administrator decision using reviewed results; raw test output,
review corrections and allowance pressure are not automatically learned in V2.

Production launcher adoption retains the prepared CLI0.159.2 workflow. Candidate
proof is `/mnt/vk-storage/vk-model-autoswitch-v1/full-router-availability.json`.
It combines accepted V1 pairs with two bounded new low-effort probes, preserving
the oldest verification timestamp instead of refreshing untested pairs. Refresh
only when expired or final launcher/account/home changes. No live service changed.

Before everyday activation, package matching frontend/backend and run a small
number of **real live Shadow recommendations** through the normal rollout gate.
These live recommendations have not yet been collected on the deployed instance.
Then use Auto with Automatic minimum for qualified low-risk envelopes; experimental
pairs stay Shadow until explicitly promoted. No 24–40 task benchmark is required.
Release QA and the existing explicit production-cutover approval remain gates;
accepted V1 dirty-state/native/CU acceptance is not repeated by this change.

## Validation for initial V2

Fourteen focused Rust routing/assessment/telemetry tests passed on the final
source, including downward pair choice, unsupported/stale proof, shadow-only
qualification, exclusions, floor retention and reported-failure consent. Four
React selection tests passed, including hydrated floor/exclusion preservation.
Executor/server Clippy with warnings denied also passed.
Web-core TypeScript checking, focused selector/hook ESLint, Rust-generated shared
types, formatting, ops governance, Python syntax and diff checks passed. The initial
frontend check lacked recovered dependencies; restoring dependencies and rerunning
passed. Two new low-effort native probes passed; accepted V1 seven-model/execution
trials were not repeated. Full workspace tests, rebuilt browser/deployment QA and
live Shadow task recommendations were not performed in this implementation turn.

## V2 continuation after V1 staging merge

V1 is integrated separately through PR127. This work stays on the preserved V2
branch; it does not rebase onto staging, change its release package or activate a
runtime. The CU wire contract remains byte-for-byte unchanged.

Qualification context is now persisted as optional `assessed_envelope` in VK's
RoutingDecision. Follow-ups retain the stricter envelope, not just its coarse
Routine/Workhorse/Frontier floor. This prevents a complex task's minor follow-up
from silently admitting a pair qualified only for normal/mechanical work. Exact
continuations such as “continue” retain a bounded task's envelope rather than
unnecessarily upgrading it. Older decisions fall back to assessing their stored
prompt. An unknown persisted envelope fails conservatively to protected work.
Escalations persist the envelope actually used for candidate qualification.

Low-risk evidence now uses lexical boundaries: “latest” does not count as a test,
and “splinter” does not count as lint. Bug/refactor/parser/algorithm work cannot
enter the bounded UI envelope merely by also mentioning a button or unit test.
These rules are conservative admission heuristics, not proof of code correctness.

For inexpensive policy inspection, `cargo run -p executors --example
routing_recommend` reads JSONL from stdin. Example input:

```json
{"prompt":"Fix button spacing in one component and run snapshot tests"}
{"prompt":"Continue.","previous_envelope":"bounded"}
{"prompt":"Change authentication","denied_models":["gpt-6-astra"]}
```

Use the candidate's actual `CODEX_HOME`, launcher environment and
`VK_CODEX_ROUTING_AVAILABILITY`. The command uses the same policy and availability
checks, and reports Auto and Shadow candidates separately. Missing/stale proof is
reported as a blocker, never replaced with fictional execution evidence. Output
omits prompts, does not emit CU execution records and is explicitly offline. It
cannot replace live Shadow acceptance. Failure reports require VK's persisted
execution history and produce a blocker in this command.

The remaining rollout gate is still a matching V2 candidate and a few real Shadow
recommendations, followed by ordinary release QA/approval. V1 deployment is owned
separately. No production usage-savings claim is made from offline recommendations.

Current continuation validation: all 17 focused routing/assessment/telemetry tests,
web-core TypeScript, generated shared types and focused executor/example Clippy
passed. Tests cover persisted multi-follow-up context, protected subsystem names,
false lexical validation evidence, unchanged Shadow execution settings and nullable
CU task identity. No native executor lifecycle code or CU producer was changed;
accepted V1 native acceptance was not repeated.

The built recommendation command passed seven bounded smoke cases against the
existing exact-launcher proof: mechanical Luna5.6/low, bounded Luna6/medium,
validated fixes Sol6/medium, retained cheap continuation, retained complex context,
Astra exclusion pause and failure-context refusal. Experimental Sol6/low appeared
only as the bounded Shadow candidate. No new inference or live execution occurred.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/v2-continuation/`.

## Natural-language outcome triage (focused V2 continuation)

Admission now includes a compact `TaskTriage` record, persisted on RoutingDecision
and therefore available through the existing raw routing log. This is a
**deterministic, compositional outcome recognizer plus bounded repository scout**,
not a general language-model classifier. It recognizes a requested presentation
change on a named UI surface without requiring engineering vocabulary. Unrecognized
requests continue at the safer existing workhorse tier. There is no paid planning
pass, new agent, scheduler, runtime dependency or change to the CU wire contract.

For example, “Add a tooltip to the settings page and make sure it works” identifies
UI help on one likely surface. A matching Settings page/component, an existing
Tooltip pattern, and a recognized package check (such as tsc, Vitest or ESLint)
permit the existing bounded envelope and its qualified model/effort selection.
“Make sure it works” is not itself evidence that validation exists or passed.
Without repository corroboration the deterministic layer retains Workhorse, with
high uncertainty and `needs_repo_inspection: true`; the semantic extension below
can now assess this uncertainty before final selection. The operator need not supply file
names or technical scope labels; the existing execution boundary supplies the
session worktree. An unrelated SettingsButton is not a Settings-page match.

Plain-language access, deletion and shared-state consequences override cheap UI
intent, as do protected imports/paths in a matched component. Compound, cross-page,
novel or ambiguous requests do not receive the small-UI qualification. Existing
explicit risk guards and deterministic text-edit/explicit-scope rules remain as
additional signals. This is deliberately limited coverage, not a claim of complete
semantic understanding, dependency analysis or proven test coverage.

The structured record contains version, intent, likely scope, existing-pattern
evidence, ambiguity, expected horizon, validation availability, risk categories,
uncertainty, inspection-needed flag, evidence codes and inspected entry/file counts.
Uncertainty is categorical evidence strength, not a self-reported success
probability. Available checks are explicitly labeled `package_check_available_not_run`;
legacy explicit validation requests are `requested_not_verified`. Retained session
qualification is recorded separately from the current request's inferred intent.

Inspection runs only for recognized outcomes where it could improve qualification.
It uses conventional UI source roots, at most 768 directory entries, eight bounded
file reads (16 KiB each), depth eight and a cooperative 40 ms budget. It does not
follow source symlinks, run repository scripts, execute tools from repository text,
read credential stores or send source to a model. Slow individual filesystem calls are
not forcibly interrupted; work runs off the async admission thread. Missing,
oversized, unreadable, unsupported or incomplete evidence cannot authorize a new
routine classification. No cache can go stale because the small inspection uses
the current working tree. Unusual repo layouts safely retain Workhorse.

Manual mode bypasses triage. Native pinned resumes, prior floors, escalation
consent, exclusions, qualification ranks, exact model proof and Shadow behavior
remain authoritative. A newly discovered protected component can raise the
existing follow-up risk-expansion gate. No active-turn switching or retry was added.

The offline `routing_recommend` example accepts optional `repo_root` in each JSONL
row and returns the same compact triage record. By default it performs no inference.
The new explicit `--semantic` option exercises the live fallback and records its
usage; neither mode emits fake CU execution events or replaces live Shadow QA. The V1
release/deployment path remains separate and untouched.

Validation for natural-language triage: 22 focused routing/assessment/telemetry
regressions passed, including the unchanged V2 manual, floor, Shadow and escalation
checks plus five new triage tests. Services check, focused executor/services Clippy,
shared-type generation, web-core TypeScript, format and ops governance passed.
The recommendation executable passed five cases against existing runtime proof:
ordinary tooltip request with repo evidence -> Luna6/medium; no repo evidence ->
Sol6.1/medium; protected component -> Astra/high; compound task -> Sol6.1/medium;
protected task with Astra excluded -> pause. These used synthetic repository
fixtures, not live workload acceptance, and made zero native/model calls.
The initial compound-request regression failed and was corrected before the final
passing run. Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/v2-triage/`.
Live V2 Shadow/release QA remains pending; V1 acceptance was not rerun.


## Bounded semantic fallback (2026-10-01)

Live Auto/Shadow admission now invokes `routing_semantic.rs` only when the existing
assessment is normal, high-uncertainty and has no hard risk or failure evidence.
Manual choices and pinned native resumes return before classification. Explicit
Frontier floors, previously protected sessions and terse continuations with a
known prior qualification also skip an unhelpful extra call. Known
mechanical/bounded/complex/protected classifications remain the zero-cost path.
The offline recommendation example stays zero-inference unless `--semantic` is
explicitly supplied. No task implementation is performed by that command.

The initial classifier is **gpt-5.6-luna / low / standard**, configurable with
`VK_CODEX_CLASSIFIER_MODEL` and `VK_CODEX_CLASSIFIER_EFFORT`. It requires the same
fresh exact launcher/home/account and model/effort execution proof as routing,
respects model exclusions and VK's execution-disable/capacity controls, and uses
one nonqueued local slot. Missing proof, disabled execution, unavailable capacity,
wrong native settings, malformed output, tool attempts, timeout or uncertain
classification retain conservative admission. There is no retry or second scheduler.

A fresh ephemeral Codex app-server thread receives only the request (maximum
6,000 UTF-8 bytes), up to 1,500 characters of the preceding request, compact
existing deterministic triage/repository evidence and the explicit floor. Longer
current requests skip inference rather than silently truncating safety context.
No source files, task worktree, repository instructions or broad repository map
are loaded into the classifier. The inherited bounded scout remains unchanged.
A neutral directory, replacement classification-only instructions, disabled skill
instructions, disabled shell/MCP/apps/plugins/hooks and other development tools,
read-only sandbox and no approvals isolate it from implementation. Unexpected
native tool/request events abort the classifier. No active task is switched.

The native `turn/start.outputSchema` is a closed schema. Its compact result is:
`{envelope, scope, novelty, ambiguity, horizon, validation, risks, uncertainty,
inspection_needed, reason}`. Enums and sizes are checked again locally; arbitrary
fields and invalid values are rejected. The reason is at most 160 characters.
Validation describes a likely checking method, never a claim of passing tests.
`inspection_needed` means missing facts could change classification, not ordinary
code navigation before implementation. No autonomous scout/tool loop is introduced.

Semantic output can replace only the soft unknown-work default. Downward admission
requires localized, established-pattern, short work, a known validation method,
non-high ambiguity/uncertainty and no inspection need. Cross-cutting/novel/extended
work raises the complex envelope; any reported protected risk raises Frontier.
Hard deterministic risks, explicit validation restrictions and large requirement
surfaces cannot be lowered. Previous session envelope and floor,
explicit floor, exclusions, qualification status and executable proof are then
applied by the unchanged router. No safe candidate still means pause; escalation
still uses consented existing execution/follow-up boundaries.

Transport has a 35-second response deadline (45-second transient-unit backstop),
one native turn, bounded 2 MiB protocol input, 64 KiB line and 4 KiB final-result
limits. These are input/wall-clock/accepted-output limits, **not a hard billed-token
cap**; native app-server does not expose a per-turn output-token budget here.
Normal classification output is small and actual native usage is recorded.
The implementation uses the official [app-server structured-output and token-usage
interfaces](https://developers.openai.com/codex/app-server) and [per-run config
controls](https://developers.openai.com/codex/config-reference), verified against
candidate CLI 0.159.2's generated schema. No API-key billing path was added.

### Classification observability

`RoutingDecision.semantic` contains the attempt UUID, status, native thread/turn
IDs, model/effort/tier, elapsed milliseconds, native input/cached-input/output/
reasoning tokens, structured result and concise detail. Absence means no classifier
attempt. Original deterministic `triage` is preserved independently. Unknown usage
is null, not invented zero. Native IDs, not timestamps, bind usage events.

Every classifier attempt also appends a `vk.classification.v1` JSONL record beside
`VK_CODEX_ROUTING_AVAILABILITY`, replacing its extension with
`.classification.jsonl`. Each record is `{schema, timestamp, classifier}`. This
small audit feed preserves overhead even when later admission has no safe candidate
and no execution is created. Successful admission joins by `decision.semantic.id`
and the existing execution's authoritative routing ID. Pre-admission failed
attempts legitimately have no execution ID. Optional feed failure warns and does
not alter routing. Classifier status/errors also survive in the persisted decision.

The existing CU `vk.routing.v1` contract and its three events remain unchanged;
classifier inference is not mislabeled as a development execution. No CU code was
changed. A future consumer can join the separate classifier record to the existing
routing decision and include its native usage in initial-plus-recovery cost.
Shadow's existing system message now shows deterministic versus semantic path,
class, semantic uncertainty/risk/reason, recommended model **and effort**, actual
execution settings, floor and escalation. Full measured usage is in its metadata.
The manually selected Shadow execution settings remain unchanged.


### Focused validation and current limits

Five final native classification calls used the exact candidate CLI 0.159.2
launcher/account/home and fresh existing pair proof. Each returned validated JSON,
matching native settings/IDs and measured token usage. Recommendations:

| Ordinary request | Inferred envelope | Qualified recommendation | Classifier |
| --- | --- | --- | --- |
| Show who is working on this card beside its progress label. | Bounded | GPT-6 Luna / medium | Semantic, low uncertainty |
| Make this remember the last option I chose. | Normal | GPT-6.1 Sol / medium | Semantic; unspecified persistence scope needs inspection |
| Let anyone with the link see everyone’s private projects. | Protected | GPT-6 Astra / high | Semantic auth/security risk |
| Make it better. | Normal | GPT-6.1 Sol / medium | Semantic, high uncertainty |
| This button sometimes doesn’t work after switching projects. | Normal | GPT-6.1 Sol / medium | Semantic; cause/scope uncertain |
| Fix the typo in README.md. | Mechanical | GPT-5.6 Luna / low | Deterministic; no inference |
| Design a new architecture for the application. | Complex | GPT-6.1 Sol / medium | Deterministic; no inference |

The five final calls took **4.344–8.664 seconds each** (32.396 s total), consuming
19,916 input tokens, zero cached input, 491 output tokens including 81 reasoning
tokens. Per-call input was 3,978–3,986; output 78–133. One initial transport check
also completed (5.006 s, 6,851 input, 78 output), keeping an unspecified help-icon
request conservative. Removing inherited skill/context instructions reduced
subsequent input overhead; total investigation used six native calls, not a model
benchmark. No development feature was executed by these classifier tests. Token
counts are observed usage, not subscription allowance weights or proven net savings.

Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/v2-semantic/`, including
`results.jsonl`, `classification-feed.jsonl`, `usage-summary.json` and validation
logs. Each successful classifier UUID occurs exactly once in the audit feed and
joins its native thread/turn. Existing CU contract mirror remains byte-identical.

There is no known architectural blocker to live V2 Shadow validation. This branch
is **not deployed**, and real operator-task Shadow/review/savings evidence remains
pending. The operator-controlled runtime must have matching fresh availability
proof and capacity. Review a small number of ordinary live recommendations and
include classifier overhead before judging net savings. Unknown persistence,
intermittent bugs and requests needing inspection deliberately remain conservative;
this patch does not add a scout agent or claim hidden repository risks are solved.
V1 deployment, staging integration, qualification registry and CU consumer are
untouched.


Local validation for this extension: 29 focused routing/triage/semantic/telemetry
regressions pass, including protocol usage binding and tool/reroute rejection,
manual bypass, retained qualifications and continuation cost avoidance. Executor
and services Clippy/build checks, recommendation-example type check, generated
shared types plus generation check, web-core TypeScript with a 2 GiB Node heap
(the initial default-heap run exhausted memory), repository formatting
and ops governance pass. No full-workspace test campaign, browser UI run or
production execution was needed for this focused backend extension.
