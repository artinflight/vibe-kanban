# AutoSwitch: release old task requirements when the work changes

## Problem

TF::Build's API-key location message was classified as security implementation.
All following messages then inherited Frontier/Astra. Three rules reinforced it:
`retain_previous` always took the more expensive task category, boundary routing
always took the previous maximum floor, and a previous protected category disabled
semantic reassessment. The mechanism was operating, but its recommendations did
not demonstrate savings.

## Change

- Qualification now follows the current assignment. A clearly independent request
  can release the prior inferred category and floor; current explicit floors remain
  authoritative. A named documentation target, an inspected UI surface, or structured semantic
  scope evidence is required. A generic “one component” description alone cannot
  release prior protection. Unknown scope, references such as “it/the same thing,” failed work
  and unresolved continuations do not clear existing requirements.
- “Okay, carry on” and “ready” are recognized continuations, avoiding repeated
  classifier calls. They retain the actual task category, including protected risk.
- Semantic output adds `scope_relation`: independent, continuation, context_only,
  or unknown. Old traces default to unknown. Scope, uncertainty and risk evidence
  are reflected in persisted triage rather than leaving stale unknown fields.
- Classifier instructions distinguish supplied configuration facts and routine use
  of an existing key from requests to expose keys or change security. Context-only
  output claiming a new protected risk is rejected as inconsistent. Context notes
  do not become automatic evidence for cheap implementation.
- Prior protection no longer blocks classification of a new request. Deterministic
  protected paths/outcomes, manual choices, exclusions, failure escalation and
  explicit floors remain authoritative. Protected qualifications are unchanged.
  A cheap unrelated edit does not authorize subsequent unrecognized security work.
- Child hard safety inheritance remains unchanged; repeated attempts within the
  same delegated assignment retain their established floor.

## Validation and limits

131 executor tests pass (six opt-in native tests remain ignored), including the action persistence boundary, retained
security continuations, explicit floors, independent task release, old trace
compatibility and protected-path checks. The replay helper now accepts the previous
request as classifier context. Native replay results are recorded under
`/mnt/vk-storage/vk-model-autoswitch-20260930/scope-fix`.

Initial native replay results (recommendations, not implementation runs):

| Request | Auto candidate | Evidence |
| --- | --- | --- |
| API-key location note | Sol6.1 / medium | Context only; no new security change |
| Add a character counter under the notes editor, after permissions work | Luna6 / medium | Independent, localized UI work |
| README typo after protected work | Luna5.6 / low | Deterministic; zero classifier calls |
| Carry on / ready after normal work | Sol6.1 / medium | Continuation; zero classifier calls |
| Make it better, referring to access permissions | Astra / high | Ambiguous continuation of protected work |
| Put the API key in browser code | Astra / high | Actual key-disclosure risk |
| README typo with explicit Frontier floor | Astra / high | Human constraint wins |

Shadow can additionally recommend Sol6/low for the UI case under the existing
experimental qualification; Auto uses the qualified Luna6/medium pair instead.
No preference ranks, minimum-required model list, CU v1 wire contract, scheduler,
active-turn switching or production settings were changed.

This patch is development-only. The earlier frontend/fresh-proof workaround stays
live; the running backend still has the old scope-retention logic. No restart was
performed or authorized by this pass. Historical decisions are not rewritten.
An existing ambiguous “carry on” does not erase old protection: a concrete new
assignment can be reassessed once the patched backend is adopted. This is evidence
of better recommendations, not measured savings on accepted development tasks.
Validation also passed generated shared types, web-core TypeScript and executor
Clippy with warnings denied. The CU wire contract remains byte-identical to the
canonical CU contract. Repository formatting, governance and diff checks passed.

Five native classifier calls used 20,883 input tokens (3,840 cached) and 915 output
tokens, taking 4.5–9.3 seconds each. These are observed token counters, not measured
subscription charges. Five deterministic/continuation controls used no classifier
inference. One call replayed the actual preceding TF::Build request from the DB,
confirming the key-location note remains Sol6.1/medium with its real context.
There were no implementation runs, retries, new child-agent trials or live policy
changes. Native evidence is in `validation-summary.json` and the replay JSONL files
under the artifact directory above. Full-workspace tests and live adoption were
not repeated for this executor-only change.
