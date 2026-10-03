# AutoSwitch: classify the current step using completed context

## What changed

The router previously saw the current and prior user prompts, but none of the
agent's completed findings. It also raised bounded continuations back to the
previous complex category. This made ordinary fact lookups inherit Sol/Astra even
when they needed little reasoning.

At execution admission, VK reads at most 3,000 characters of the immediately
previous successful execution's final reply in the same session. Failed, killed,
running, nonzero-exit and missing-summary executions provide no reply; the query
does not search older replies for a convenient substitute. No full transcript,
repository crawl or extra summarization call is added. The previous execution ID
already persisted on RoutingDecision identifies the source of that context.

The reply is untrusted reported context. It resolves references, but does not
prove tests passed, override instructions or grant permission. The classifier
retains its existing one-call Luna5.6/low settings, no tools and usage recording.
Its input adds `previous_completed_reply`; all existing length limits remain,
with this one additional 3,000-character maximum.

Two additional scope relations distinguish a `bounded_step` within a larger
assignment from a read-only `reference_lookup`. Low uncertainty, resolved context,
localized established work, short horizon and a known validation method are all
required. Protected assignments retain their floor for changes; a pure lookup
may shed inferred historical protection, while current protected evidence and
explicit floors remain authoritative. Unknown persisted categories fail closed.

A narrow deterministic fast path recognizes simple link/dimension questions only
with a matching kind of fact in completed context, no additional operation or
risk or suitability judgment, and a single distinct link or measurement. Multiple references require
semantic disambiguation. This is a classification shortcut, not a factual answer
or an instruction to skip verification by the development agent.

A cheap step records `surrounding_assignment:<envelope>` in extensible triage
evidence. A later ambiguous continuation recovers that qualification instead of
inheriting the cheap lookup's level. Returning above the latest execution's floor
still follows the existing escalation-consent policy. Native control/resume after
such a step requires an ordinary follow-up or explicit manual selection; it cannot
silently resume the broader assignment on the cheap model.

## Validation

- 48 routing, triage, semantic, delegation, availability and telemetry executor
  tests pass; one opt-in native execution test remains intentionally ignored.
  Added checks cover same-assignment release, retained protected changes, manual
  floors/locks, exclusions, failed-boundary preservation, Shadow settings,
  persistence and subsequent continuation, and zero-inference reference handling.
- Formatting, Ops governance, diff checks and executor Clippy with warnings denied
  pass. The CU contract remains byte-identical to its canonical copy.
- `cargo check -p services --lib` checks the production admission integration.
  The exact admission SQL also passed an isolated SQLite check for same-session
  isolation, 3,000-character bounds, completion/exit status and missing replies.
- Native classifier replays used the live service's launcher/account/home and
  inherited capacity settings, with an isolated copy of availability and usage
  output. No agent implementation work reran and no capacity check was bypassed.
- Final replay of “Okay this sounds good, what's the actual touchpad surface
  dimensions?” correctly recognizes the already-established 25 × 17 mm fact.
  Auto selects **gpt-6-luna / medium**, replacing the recorded complex/Sol6.1
  recommendation. Shadow selects the existing experimental **gpt-6-sol / low**.
  The model registry, preference ranks and experimental qualifications are unchanged.
- The actual link-plus-shopping-quantities request remains conservative because
  its immediately previous reply does not contain the requested quantities.
  The recurring-error report also remains conservative. Do not claim all
  CarConsole work qualifies for a cheaper model.

Four native calls used **18,763 input tokens, zero cached input, 649 output** and
**31,496 ms** combined. One call found a contradictory continuation instruction;
after correcting it, a single additional call verified the dimensions result.
The final call used 4,734 input / 158 output tokens and took 12.8 seconds. A simple
unambiguous reference incurs no classifier call. These counters are classification
overhead, not subscription billing weights or proven net savings.

Evidence is under `/mnt/vk-storage/vk-autoswitch-context-20261002`. The initial
`replay-output.jsonl` records intermediate failures as well as results; the corrected
native result is `dimensions-corrected.jsonl`. Its earlier multi-link deterministic
control was subsequently tightened and is not final evidence; the final regression
suite rejects ambiguous multiple links/measurements. `sql-validation.json` and
`usage-summary.json` record the bounded query checks and total inference cost.

## Release boundary

This is backend source work, version 0.1.42, not a hot-loaded policy change.
No production mutation, restart, staging/main merge or deployment-agent interaction
was performed. No schema migration or generated shared-type change is needed;
the existing CU wire contract and raw routing log are preserved. New scope labels
live in the existing extensible trace/evidence strings, not strict nested fields.

Normal staging integration and VK::Staging adoption remain before live observation
can validate net savings. Full-workspace tests, fresh model benchmarks, child
execution trials and production cutover were not repeated for this focused patch.
