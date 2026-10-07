# AutoSwitch: risk wording and diagnostic phases

Development correction on `fix/autoswitch-negated-risk`, based on staging
`86d1c083a`. The October 4 accepted runtime remains unchanged. No staging/main
merge, deployment, restart, live policy change or deployment-agent coordination.

## Behavior

- Standalone `non-destructive`, `nondestructive`, `non destructive` and Unicode
  hyphen variants no longer supply destructive intent by substring alone.
  Positive occurrences elsewhere, negated assurances, disabled safeguards,
  identifiers and other protected categories still retain protection. This is
  a narrow correction, not general cancellation of risks mentioned in cautions.
- The existing single semantic call can return `diagnostic_step` when the
  immediately previous successful execution reports the earlier protected
  operation completed and the current request asks for limited observation or
  symptom investigation. The cause may be unknown; authorized scope must be
  localized, short and unambiguous, with no current protected risks and no high
  classification uncertainty. Inspection can still be needed.
- Diagnosis always stays complex/Workhorse or higher. It cannot qualify as
  Routine even with inconsistent semantic output. Current protected paths or
  intent, explicit floors, manual selections, exclusions and failure handling
  remain authoritative. Missing context, uncertain scope, unknown prior
  qualification or reported validation failure cannot release a protected floor.
- The existing `surrounding_assignment:protected` evidence survives the side
  step. A later generic continuation retains that assignment's protection;
  existing escalation consent and native-resume restrictions still apply.
- The concise reason includes `completed_context_diagnostic_step`. Relation and
  evidence use existing extensible trace fields. The strict persisted nested
  classification shape and `vk.routing.v1` contract are unchanged.

The prior reply is an untrusted report that resolves context, not proof of
correctness, authorization to change policy or a verified clean working state.
There is no new planning call, scheduler, tool loop or retry mechanism.

## Focused evidence

Two historical admission replays used Codex 0.159.2 and the exact accepted
launcher/account/home with copied executable proof, existing capacity limits,
neutral context and tools disabled. They classify only; they execute no task.

| Real request | Previous live recommendation | Corrected replay |
| --- | --- | --- |
| USB connection symptom following reported completed initialization | Astra/high, inherited protected floor | Sol6.1/medium, complex diagnostic step |
| Non-destructive media verification, conditionally changing drive-protection limits after a safely stopped job | Astra/high, false deterministic destructive match | Astra/high, fresh semantic data-risk assessment; false substring removed |
| Production hotfix/restart control | Astra/high | Astra/high, deterministic; no classification call |

Classifier overhead for the two paid replays: 9,408 input tokens, zero cached
input, 489 output tokens and 16.702 seconds combined. This is validation
overhead, not evidence of net accepted-task savings. No additional trials or
implementation agents were launched. Real Shadow outcomes after a separately
owned release must establish whether savings exceed classification/recovery cost.

Evidence, sanitized control result and build/test logs are under
`/mnt/vk-storage/vk-autoswitch-risk-phase-20261004`. Private replay input/output
stay there with restricted permissions; no prompts or account identity are
included in this document or commit.

## Validation and release boundary

Focused routing regressions cover positive/negated risk wording, diagnostic
scope, missing context, unknown history, validation failures, inconsistent
classifier output, minimum Workhorse qualification and explicit Frontier floors.
The native replays demonstrate the updated structured relation and candidate
selection, not implementation quality or accepted-task savings.

The final focused routing run passed 53 tests (one opt-in native test ignored).
Formatting, executor Clippy/build, ops governance and byte-identical CU contract
and fixture comparisons are recorded with the change. Full desktop/workspace CI
uses repository runners because this host lacks GTK development dependencies.
Activation and subsequent real Shadow monitoring remain VK::Staging-owned.
