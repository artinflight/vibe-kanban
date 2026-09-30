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

These are conservative prompt-derived signals, not proof that tests exist or pass.
V2 does not inspect arbitrary repository contents or pay for a second planning
model. Unknown context uses Workhorse. Subsystem/path mentions supply risk cues;
there is no claim of semantic dependency analysis or flawless English matching.
Security hidden from the prompt still requires ordinary review and validation.

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

## Validation for this change

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
