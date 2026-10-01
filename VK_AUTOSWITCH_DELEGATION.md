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
- Native token usage retains the full `tokenUsage` object: `last` is the latest
  request and `total` is cumulative thread usage, not an individual turn total.
  Cache/output/reasoning fields are preserved when exposed. Missing usage remains unknown, never estimated.
- Semantic classification records also carry routing ID/task-key correlation even
  when later qualification refuses the child. Failed first attempts remain part of
  the same delegated task's cost across escalation and owner-execution transitions.

Optional log/feed failures warn without changing routing. Required lifecycle-journal
failure prevents admission or stops an uncertain active owner. Child native logs
are wrapped so they cannot replace root session IDs, model display or goal lifecycle.
The UI displays compact child decisions and retains the full event as metadata.
The existing CU consumer can correlate the v1 bindings; a future sidecar consumer
can provide hierarchy-specific analytics. No CU consumer changes were made here.

## Loaded-thread settings and process inventory

A loaded native thread can ignore model/effort overrides in `thread/resume`.
For an inactive child whose requested pair changed, VK queues
`thread/settings/update`, waits up to ten seconds for the corresponding
`thread/settings/updated` evidence, then verifies a new resume snapshot before
inference. A rejected, missing or mismatched update fails closed. Thread identity,
working state and the normal parent-turn eligibility checks remain authoritative.
This follows the next-turn settings API in the candidate runtime; no active-turn
switch, unload, new child or retry loop is introduced. See the
[official app-server documentation](https://learn.chatgpt.com/docs/app-server).

On Linux without systemd execution accounting, the capacity fallback inventories
actual `/proc` argv/parent relationships. It counts native engines once, collapses
Node launcher chains and excludes shell/diagnostic text mentions. Idle servers
still count conservatively; this is a process inventory, not proof that agents
are doing inference. The default limit remains eight; systemd unit accounting is
unchanged. The native harness owns a process group for cleanup on failure.

## Validation and next boundary

Validation passed: 122 executor unit/regression tests (five opt-in runtime tests
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

The earlier attempts were blocked before inference by a misleading fallback count
(13/14 matching processes, limit eight): launcher wrappers and diagnostic text
were included. This was not evidence of 13/14 active agents. The corrected fallback
count admitted the native test without changing any limit or stopping other servers.

On 2026-10-01 the first admitted trial completed Luna5.6/low, then stopped before
escalated inference because native resume retained the loaded thread's old settings.
After the next-turn settings correction, the two-turn harness passed in 46.16 seconds:

- GPT-5.6 Luna / low, followed by GPT-6.1 Sol / medium, standard tier.
- Same native child thread and delegation ID; distinct exact native turn IDs.
- Native rollout `turn_context` confirms each actual pair and agrees with CU bindings.
- Tracked dirty sentinel preserved byte-for-byte; duplicate start reused its handle;
  child completion did not end or rename the parent; active child count returned to zero.
- Two distinct injected validation failures (one duplicate ignored) triggered escalation.
  They are fixtures, not claims of real unsuccessful model repairs. Parent execution
  identity is a harness fixture and the parent incurred no inference.

Three child inference turns were used in this investigation: the initial diagnostic
turn plus the two passing turns. Final-test native usage: first turn 68,016 input
(54,016 cached), 715 output; follow-up cumulative delta 58,035 input (38,016 cached),
448 output. These are native token observations, not allowance weights or proof of
net savings. The compact brief was 600 bytes; runtime tools/instructions and multiple
model requests still contribute significant input. No additional benchmark ran.

Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/v2-delegation/capacity-fix-20261001/verified`:
`native-test.log`, sanitized `native/result.json`, `correlation.json`, `routing.jsonl`
and `routing.delegation.jsonl`. Raw native protocol logs remain local and are excluded
from the shareable ZIP. Canonical CU contract bytes are unchanged.

The first complete V2 live Shadow test remains pending on a fresh ordinary chat.
Observe parent, cheap child, protected-child recommendation, actual versus recommended
settings, cancellation and aggregate accepted-task usage. Goal/scheduled execution
delegation remains disabled. No staging, deployment, production Shadow test or
external-agent coordination occurred in this pass.
