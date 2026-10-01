# AutoSwitch V2 delegated work

Development extension of the existing V2 router; V1 staging/deployment is untouched.
This is a source implementation, not live Shadow evidence or measured savings.

## Admission and native integration

Auto and Shadow expose `vk_delegate` on **new Codex chats**. Actions are `start`,
`status`, `follow_up`, and `cancel`. VK handles these dynamic tool requests without
blocking the existing app-server JSON-RPC reader. Each admitted child is a native
Codex thread on that same connection/process. There is no scheduler, retry service,
additional executor process or automatic continuation loop.

These are VK-managed leaf children, not the native collaboration tree. Native
`multi_agent` and `multi_agent_v2` tools are disabled at process and thread startup
for routed executions. Manual mode retains its existing native delegation and
explicit model/effort choices. This boundary is necessary: native spawn happens
before VK receives its notification, and native PreToolUse hooks fail open on
errors/timeouts. A prompt recommendation or hook alone cannot enforce admission.
See [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), and
[app-server](https://learn.chatgpt.com/docs/app-server). Existing native delegation
can inherit parent model/effort and defaults to the full conversation fork; the
controlled path supplies explicit settings and starts without parent history.

The existing runtime cannot retrofit dynamic tools onto an old thread. Start a
fresh routed chat for full Shadow validation. Existing routed threads can still
work in their parent. Scheduled capacity executions and active native goals cannot
use this gateway: independent native threads must not bypass their established
capacity or goal-token accounting. Children cannot recursively delegate or create
goals. A goal activated with children outstanding stops the owning execution.

## Classification and safety

The delegated assignment supplies a stable task key, message, compact requirements /
decisions context, 1–8 repository-relative scope paths, read-only status, independence
and size (`batch` or `substantial`). Tiny/dependent work is refused for delegation.
These fields are supplied by the parent agent, not by the operator.

Only this delta and its scoped references enter existing deterministic/bounded
triage. Uncertain deltas may use the existing bounded semantic fallback. Parent
classification is not rerun. Identical follow-ups retain prior classification;
changed scope is reassessed. Parent protected classification and explicit manual
floor remain hard minimums, but a merely complex Workhorse parent can delegate
mechanical work downward. Prior child floors cannot decrease across follow-ups.

Candidates use the same model/effort/envelope qualifications, configurable ranks,
exclusions, current launcher/home/account proof and supported/verified efforts as
root routing. Auto selects the qualified pair with the lowest configured preference rank. Standard tier
is explicit. No new model ladder or billing assumptions were added. Shadow records
the recommendation and retains the parent's actual model/effort only if that pair
qualifies for this child; otherwise it refuses the child with a visible reason.

Native thread/start or resume must confirm the exact model, effort, OpenAI provider,
standard tier and stable child identity **before** turn/start. Native model rerouting
stops the owner for review. No code or working files are reset during any transition.
Scope paths express ownership and classification evidence; they are not a new
filesystem sandbox. Existing permission controls and repository instructions apply.

## Context, parallel work and cancellation

Each message and context brief is capped at 4,000 bytes. Children receive the brief,
scope references, inherited hard floor, existing custom developer/repository
instructions, and their own follow-up history. Parent conversation history is not
forked. Root-only goal/delegation instructions are removed from the child template.
Native tool catalogs and repository instructions still consume input; no claim is
made that an 8 KB brief equals total input usage.

Identical task+context+scope+access assignments reuse a handle instead of creating
another child, even under a different task key. Concurrent overlapping edit scopes
are refused; independent read-only scopes may overlap. A child slot is reserved
before classification. The existing native session concurrency setting bounds the
leaf count (default four total threads, hence three children); `VK_CODEX_MAX_CHILDREN`
can lower it, including to zero. Active children also count toward VK's existing
Codex execution-capacity guard. This count covers this backend's controlled children,
not external tools or agents outside VK.

`status` waits up to 30 seconds by default (maximum 60) to avoid rapid model-driven
polling. `cancel` issues native turn/interrupt and retains the active slot until
native completion confirms termination. Cancellation during classification prevents
the later turn from starting. A parent that ends with active children interrupts
them and fails visibly rather than leaving unowned inference running. An uncertain
turn-start outcome also stops the owner; it never retries blindly. A follow-up or
restart uses the existing child thread and preserves working state.

## Escalation and accounting

An explicit `follow_up` can raise one floor on native turn failure or two distinct
observed failing validation commands. Initially recognized commands are direct
`cargo test/check`, `pnpm test`, `pnpm run check`, `npm test`, `pytest`, `node --test`
and `tsc --noEmit`; arbitrary output text, shell wrappers and duplicate item IDs do
not count. This intentionally conservative signal is not a claim that every test
failure proves insufficient intelligence. Existing `allow_escalation` consent is
required; Frontier failure pauses further admission for operator diagnosis. A refused escalation retains the previous failure evidence. There
is no automatic retry and no downward bounce. Changed assignments can independently
raise the floor through protected scope or greater complexity.

A private, bounded, atomically replaced journal under the availability file's sibling
`delegation/<root-thread-uuid>.json` retains stable delegation IDs, latest attempt,
assignment, classification, actual settings, native IDs and outcomes. On restart,
unfinished attempts become `interrupted_unconfirmed`, never fabricated successes.
The native thread remains authoritative for conversation and working state.

Existing `vk/routing` raw events and the byte-identical CU `vk.routing.v1` contract
are unchanged. Each exact child thread/turn pair emits another v1 `turn_bound`
under its **real owning VK execution/routing IDs**, with its actual model/effort.
No child database execution UUID or task ID is invented. The owning execution's
existing `execution_end` covers its process lifetime.

An additive `vk.delegation.v1` sidecar is written beside `VK_ROUTING_EVENTS_FILE`
using the `.delegation.jsonl` suffix, and mirrored as `vk/delegation` raw events:

- Stable `delegationId`, `taskKey`, attempt, owning `executionId`/`routingId`;
  parent native thread/turn and exact child native thread/turn.
- Decision, turn binding, usage, attempt end, blocked and cancellation-request events;
  recommended versus actual pair, source, semantic classifier ID, escalation and
  brief size/hash. Idempotent event IDs exclude timestamps.
- Native per-turn token usage is preserved as reported, including cache/output and
  reasoning fields when exposed. Missing usage remains unknown, never estimated.
- Semantic classification records also carry routing ID/task-key correlation even
  when later qualification refuses the child. Failed first attempts remain part of
  the same delegated task's cost across escalation and owner-execution transitions.

Optional log/feed failures warn without changing routing. Required lifecycle-journal
failure prevents admission or stops an uncertain active owner. Child native logs
are wrapped so they cannot replace root session IDs, model display or goal lifecycle.
The UI displays compact child decisions and retains the full event as metadata.
The existing CU consumer can correlate the v1 bindings; a future sidecar consumer
can provide hierarchy-specific analytics. No CU consumer changes were made here.

## Validation and next boundary

Validation passed: 119 executor unit/regression tests (five opt-in runtime tests
ignored), executor/services Clippy with warnings denied, required formatting, ops
governance and byte comparison with the canonical CU v1 contract. No public shared
types changed. Focused policy and offline dynamic-tool lifecycle checks cover downward selection,
protected/explicit floors, exclusions, bounded briefs, duplicate identity, cancellation
through nested RPC without deadlock, explicit model/effort wire overrides, exact
turn-bound cache usage and separation of child/root completion. The transport
fixture uses synthetic native IDs/usage and makes no OpenAI calls.
The ignored `native_delegation_boundaries` test prepares exactly two child turns:
5.6 Luna/low, then Sol6.1/medium on the same thread following injected distinct native
validation-failure fixtures. It checks exact native settings, duplicate-start reuse,
parent lifetime, attribution and preservation of a tracked working-file sentinel.
The injected failures are test fixtures, not claimed real failed model fixes.

The paid harness was attempted once on 2026-10-01 and stopped at the existing
capacity guard **before any app-server or model inference started**. The diagnostic
snapshot found 13 matching native processes against the default limit of eight;
no capacity bypass or retry was performed. Native acceptance of this new gateway
therefore remains unverified. No seven-model campaign, deployment, staging operation
or live production Shadow test was performed.

The operator-requested retry at 2026-10-01 08:33 UTC also stopped before inference:
14 matching active processes against limit eight. Runtime proof remained fresh
(18.58 hours); no model turn started and no limit was changed. Evidence is in
`v2-delegation/retry-20261001-0833/test.log` under the existing SSD task directory.

When genuine capacity is available, run the two-turn harness with the candidate
launcher, account/home and fresh availability proof; then run the planned complete
V2 Shadow test on a fresh ordinary chat. Observe parent, cheap child, protected-child
recommendation, actual versus recommended settings, cancellation and aggregate
accepted-task usage. Goal/scheduled execution delegation remains deliberately disabled.
