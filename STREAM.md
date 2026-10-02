## Terminal identity recovery and Sol 6.1 High default — October 2

Shadow stopped after the 24-hour discovery expiry: the saved native user agent
contained terminal `dumb`, while the service's identical Codex0.159.2 reported
`unknown`. Recovery compared both metadata responses under the actual service
environment, account/home and unchanged launcher, then atomically refreshed the
catalog/runtime label while preserving every verified-at timestamp and effort.
No execution proof was fabricated; no service restart or runtime upgrade occurred.

The permanent Rust matcher ignores only the terminal component; version,
platform, architecture, client and account checks remain strict. Three focused
matcher tests and the executor Rust check pass. A stale isolated copy renewed
using the existing compiled resolver without inference, then selected Luna5.6/low
for a mechanical request. One CC::Inventory semantic replay succeeded with
Sol6.1/medium: 4,487 input, 217 output tokens, 7.9 seconds; no agent work reran.
This is replay evidence, not a new live development execution or measured savings.

The supported live profiles API now stores CODEX DEFAULT as gpt-6.1-sol/high;
other fields are preserved. Frontend fallback and both creation paths follow
that default while explicit draft choices and existing sessions remain intact.
Permanent Rust changes remain source-only; live recovery uses refreshed data.
Evidence and rollback: `/mnt/vk-storage/vk-autoswitch-identity-repair-20261002`.

The live profile update and frontend `e082c4648` are applied without restart.
Candidate desktop/mobile checks verify new workspaces and new agents default to
Sol6.1/High + Recommended, model/effort edits retain Shadow, and manual selection
remains authoritative. Build/types/lint/format/Ops pass. The served asset receipt
and live-browser checks are in the evidence directory above. Backend PID3059021
is unchanged. Refresh the browser once; no rerun of existing development work is
needed. The source-only permanent matcher requires a later normal release;
current live discovery data already matches the service and renews correctly.

## Preserve Recommended when editing model or reasoning — October 2

The model selector had explicitly forced Manual for every model/effort edit,
overriding the new Shadow default. Both selectors now use the shared override
handler: Shadow stays Shadow with the chosen execution settings, while Auto
changes to Manual for an explicit model/effort choice. Explicit routing choices,
capability floors and exclusions remain authoritative. This is frontend-only.
Evidence: `/mnt/vk-storage/vk-autoswitch-shadow-selection-20261002`.

Published frontend `49ce55538` without restarting backend PID3059021.
Build, types, focused lint, formatting and Ops passed. Desktop/mobile candidate
checks prove model and effort changes retain Shadow, Auto changes lock Manual,
explicit Manual remains authoritative, and both new-agent paths retain the
default. No model calls or development executions were submitted. Existing
assets and service worker are preserved; rollback index is on mounted SSD.
Refresh once; a draft already saved as Manual needs Recommend selected once.

## Recommended default published — October 2

The frontend-only default is live at `https://vibe.local/` from `304535c76`.
Backend PID3059021, service, routing, model policy and telemetry are unchanged;
no restart or main/staging merge occurred. New Codex workspaces and sessions
start in Recommend only (Shadow); explicit choices and existing chats win.
The live attention-indicator fixes from `caef5f3b6` are preserved.

Build, web-core type checking, focused ESLint, formatting, Ops and diff checks
passed. Candidate desktop/mobile browser checks cover both creation paths,
explicit Manual and existing TF::Build Shadow. Live browser evidence and served
hashes are in `/mnt/vk-storage/vk-autoswitch-recommended-default-20261002`.
No development execution or paid model inference was submitted by the checks.
All old assets and the service worker remain intact. Rollback needs only the
saved index on mounted SSD; Desktop SSH rejected its exec channel, so the tiny
rollback index was not copied there. Source is isolated on
`fix/autoswitch-recommended-default`; the new default has not been merged.
Refresh the browser once to load it; this does not enable Auto execution.

## Recommended default for new agents — October 2

Branch `fix/autoswitch-recommended-default` makes new Codex workspaces and new
sessions default to Shadow (Recommend only), assessed floor, no automatic
escalation. Explicit draft/browser choices win; existing sessions keep their
settings. This is a frontend-only change based on the exact live frontend
`caef5f3b6`, preserving the attention-indicator repairs from PR138. The separate
`fix/autoswitch-live-shadow` helper branch is preserved and excluded.

The corrected backend is now live, activated separately by VK::Staging. This
stream owns no restarts or main promotion. Validation and frontend publication
evidence are under `/mnt/vk-storage/vk-autoswitch-recommended-default-20261002`.
No task executions or model calls are needed to validate this default.

# Workspace Attention Preservation

Branch `fix/workspace-attention-preservation` starts at staging `b0f4c10a9`.
Scope: intentional review clearing and actionable sidebar pagination, with
focused tests and evidence-backed flag recovery. No backend, schema, model,
capacity, restart controller or issue-status changes belong in this stream.
See VK_ATTENTION_PRESERVATION.md. Older stream entries below are historical.

## AutoSwitch release compatibility (2026-10-01)

Scope/savings fixes are merged through PR134 (staging) and PR135 (main).
The live backend is still PID1504649/sourceadfa7c051; the release has not switched.
Release preparation found a rollback reader incompatibility: the old binary
rejects added fields inside `SemanticClass`. Scope relationship now persists on
its extensible parent `SemanticTrace`; native classification and safety logic are
unchanged. The generated API types follow that persisted shape.

Release artifacts and current evidence live at
`/mnt/vk-storage/vk-autoswitch-scope-release-20261001`. Desktop has the verified
checkpoint and delta under `B:/vk-backups/vk-autoswitch-scope-release-20261001/`.
The full checkpoint restored successfully into an isolated directory. These are
online backups, not the final fenced cutover capture. Read-only inventory found
an unexpectedly restarted September14 standby (PID2828009); it had no clients or
children and was returned to its frozen state. The routed server and data remain
unchanged. No candidate production startup or route switch has occurred.
Read the package readiness/status files before any activation; never reuse a
consumed cutover controller. Existing Shadow/manual choices must remain intact.

## AutoSwitch scope and savings correction (2026-10-01)

Current development fixes permanent Frontier inheritance and the false security
promotion of configuration notes. Read [VK_AUTOSWITCH_SCOPE_FIX.md](VK_AUTOSWITCH_SCOPE_FIX.md).
Independent small work can choose Luna after protected work; ambiguous continuation,
protected paths, explicit floors and failure handling remain conservative. Native
recommendation tests cover real TF::Build wording and ordinary UI/documentation
work. This is source-only: no backend restart, deployment or live routing-policy
change. The earlier no-restart workaround below remains the actual live state.
Validation passed: 131 executor tests (six opt-in ignored), generated shared types,
web-core TypeScript, executor Clippy with warnings denied, formatting/governance
and diff checks. CU contract bytes are unchanged. Five native classification calls
used 20,883 input tokens (3,840 cached), 915 output, 4.5–9.3s each; five controls
needed no inference. The real preceding TF::Build request was included in one
replay. These are recommendation checks, not measured accepted-task savings.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/scope-fix`.
Next: adopt the backend changes through the normal release path when worthwhile,
then measure total accepted-task usage; no restart or release was done here.

## AutoSwitch no-restart testing workaround live (2026-10-01)

Operator authorized the temporary no-restart path. Frontend source `8d4b9ead2`
is live on the existing backend at `https://vibe.local`; backend PID1504649 and
binary are unchanged. Only the two chat-setting frontend files differ from the
previous frontend source. All old hashed assets remain available, and the prior
frontend/proof have verified rollback copies on mounted SSD.

Nine genuine one-reply checks refreshed all seven models and the two additional
low-effort pairs in the existing availability file. No retries or background
paid refresh were installed. The current backend's 24-hour rule still applies:
proof expires **2026-10-02 16:10:26 UTC**. Native counters total50,254 input tokens
(11,904 cached) and72 output tokens; these are not allowance charges.

TF::Build's empty follow-up draft is now Shadow/assessed; manual model and effort
remain Sol6.1/xhigh. Actual browser selection/reload checks passed at desktop and
mobile sizes without errors. No new development execution was submitted and no
phone operation occurred. Reload the operator's page to receive the updated UI;
previous explicit browser-local manual overrides remain authoritative.

Read `VK_AUTOSWITCH_SHADOW_FIX.md`. Evidence, deployment manifest, test scripts,
screenshots and rollback are at
`/mnt/vk-storage/vk-model-autoswitch-20260930/no-restart`.
The permanent backend auto-refresh fix remains undeployed. Further Shadow work
can use this temporary window; refresh genuine proof on demand if testing extends
past expiry. Never merely advance timestamps or add unattended paid probes.
A complete new live routed task/child acceptance is still pending operator work.

## TF::Build Shadow continuity repair (2026-10-01)

Branch `fix/autoswitch-shadow-continuity` fixes expired availability renewal and
same-session routing hydration. Read [VK_AUTOSWITCH_SHADOW_FIX.md](VK_AUTOSWITCH_SHADOW_FIX.md).
Catalog renewal is bounded, metadata-only and identity-checked; historical exact
execution proof is retained without changing verification timestamps. Manual
choices, fresh-chat opt-in, policy floors and CU wire format remain authoritative.
This is development only; no live proof/profile/service mutation or deployment.
Validation: 127 executor tests passed (six opt-in ignored); the metadata-only native
refresh passed separately in 0.90s against a private copy of the production proof.
All seven models remained discovered; all exact verification timestamps/efforts
were preserved and the production proof hash stayed unchanged. Seven React selector
regressions, web-core TypeScript, executor Clippy, targeted ESLint, formatting
and ops checks passed.
CU canonical contract remains byte-identical. No billed inference or deployment.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/shadow-fix`.
Normal release adoption and a full live Shadow run remain pending. TF::Build's
later manual state must be explicitly changed back to Shadow; do not silently
reinterpret an existing manual execution as routing consent.

## AutoSwitch V2 staging integration (2026-10-01)

The operator now authorizes the full V2 PR/push/rebase merge into staging.
See [VK_AUTOSWITCH_V2_STAGING.md](VK_AUTOSWITCH_V2_STAGING.md) for base, exact
commit mapping and validation limits. Seven V2 commits are rebased onto
staging198d55a20; V1 is already present. Only continuity documents conflicted;
all source patches and newer staging functionality are preserved. No deployment
or full live Shadow test is included. Earlier development-only scope below is history.

## Native child acceptance and capacity correction (2026-10-01)

The bounded native child test now passes. The prior pgrep count included Node
launcher wrappers and diagnostic command text; it was not a count of active agents.
Linux fallback accounting now counts native app-server chains once. Idle servers
still count conservatively. Default limit eight and systemd accounting are unchanged.

The first admitted trial completed Luna5.6/low but exposed loaded-thread resume
ignoring escalation settings. The safety check blocked the second turn. VK now
applies next-turn settings, waits for native confirmation, and rechecks before
inference. The final test completed Luna5.6/low then Sol6.1/medium on the same child
thread, preserved the tracked dirty sentinel, reused duplicate starts, and retained
parent/child identity. Native rollout turn_context matches both CU v1 bindings.
Escalation failure triggers were injected fixtures; root execution identity is a
harness fixture, with no parent inference. Three actual child turns total this pass.

Validation: 122 executor regressions pass, five opt-in tests ignored in the normal
suite; the opt-in native test separately passes; executor Clippy, format/ops and
canonical CU contract comparison pass. Native usage preserves both latest-request
and cumulative-thread fields. Evidence: `v2-delegation/capacity-fix-20261001/verified`
under `/mnt/vk-storage/vk-model-autoswitch-20260930`.

Next is the first complete live V2 Shadow test on a fresh ordinary chat, handled
separately. No staging, deployment, production cutover or external-agent interaction.
Read [VK_AUTOSWITCH_DELEGATION.md](VK_AUTOSWITCH_DELEGATION.md). Version 0.1.42.

## Semantic fallback continuation (2026-10-01)

Auto/Shadow now adds one bounded gpt-5.6-luna/low/standard classification turn only
for materially uncertain deterministic assessments. Known envelopes, manual/pinned
execution and protected floors skip inference. Closed structured output feeds the
existing qualification/floor/exclusion and consented escalation logic. No tools,
implementation loop, staging/deployment changes or agent coordination.

Native sample: ordinary assignee display -> Luna6/medium; private-project access
-> Astra/high; vague/persistence/intermittent-failure requests -> Sol6.1/medium.
Two deterministic controls incur zero calls. Five final classifier calls measured
3,978–3,986 input tokens, 78–133 output and 4.344–8.664 seconds each. One initial
transport check also ran. Classification attempts/usage persist in decisions and
a separate vk.classification.v1 feed; CU vk.routing.v1 is unchanged.
Read VK_AUTOSWITCH_FULL_ROUTER.md for configuration, bounds and actual evidence.
Validation: 29 focused regressions, executor/services Clippy, generated-type and
web-core TypeScript checks, format and ops pass. Source-only; live V2 Shadow QA
and net-savings measurement remain pending.

## Natural-language triage continuation

V2 now recognizes common presentation outcomes on named UI surfaces and corroborates
them with bounded repository evidence at the existing execution boundary. Structured
triage includes uncertainty, validation availability and inspection counts; missing
context retains Workhorse. No planning model call, registry change, CU contract change
or V1 deployment work. Read VK_AUTOSWITCH_FULL_ROUTER.md for scope and limits.

## V2 resumed after V1 staging integration

Continue on `vk/5a81-autoswitch-cu-recovery`; V1 PR127/deployment is separate and
must remain untouched. Follow-up qualification persistence and lexical assessment
repairs are implemented, plus a read-only policy recommendation command. Details:
[VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md). This is not live
activation or live Shadow evidence. No V1 model acceptance campaign was repeated.

# Automatic assessed router (V2)

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Extends accepted V1 with default task assessment, explicit model/effort/envelope
qualification, configurable pair preference, operator-reported validation and
risk-expansion escalation. See [VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md).
Auto can choose older Luna/low, Luna6/medium and Sol6/medium without Routine labels.
Manual and explicit floors/exclusions remain authoritative; no scheduler or reset.
Experimental pairs remain shadow-only. Matching release deployment and a small
live Shadow sanity check remain pending; no production activation in this stream.

## Accepted V1 history

## October 1: Pre-Cutover Preparation Performance

Branch `fix/vk-precutover-preparation`, based on fork/staging620bd7eb9.
Scope: versioned preparation-only tools, verified static evidence/artifact reuse,
rolling online backup checkpoints, bounded concurrent queue inspection, and
whole-preparation timing. The fenced capture callback now has real private
handover/recovery acceptance and is approved for staging integration. See
VK_PREPARATION_PERFORMANCE.md. No production pause/restart/reroute, application
feature change, or replacement of an existing production controller.
Inherited stream notes below describe other work, not this branch's authority.

## AutoSwitch V1 staging-only release

Branch `release/autoswitch-v1` rebases validated V1 onto staging56792a72c.
See [VK_AUTOSWITCH_V1_STAGING.md](VK_AUTOSWITCH_V1_STAGING.md) for exact commit
mapping, preservation of newer staging behavior and operator deployment notes.
V2 remains untouched on `vk/5a81-autoswitch-cu-recovery` at64e9cb5bd and is
excluded. Only continuity documents conflicted; no source conflicts. The operator
owns all post-merge actions. Do not contact or trigger a deployment/staging agent.

# VK Model AutoSwitch V1

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Scope: opt-in model/effort routing at existing Codex execution boundaries.
[VK_MODEL_AUTOSWITCH.md](VK_MODEL_AUTOSWITCH.md) supersedes the planning-only
catalog and describes policy, implementation and enablement gates.
[VK_CODEX_ROUTING_CONTRACT.md](VK_CODEX_ROUTING_CONTRACT.md) defines usage joins.
All seven required models execute on isolated CLI 0.159.2 using the existing
account. Default host CLI 0.153.4 and production VK remain unchanged.
Manual, shadow and automatic modes preserve per-chat control; automatic routing
requires fresh executable-pair evidence and pauses rather than violating floors.
CU-compatible lifecycle telemetry is implemented. Native executor acceptance
passes at the existing capacity limit; private candidate API acceptance and CU
correlation evidence are tracked in VK_AUTOSWITCH_ROLLOUT.md. The active worktree
was externally deleted; recovered source is outside the managed worktree tree at
`/mnt/vk-storage/vk-model-autoswitch-20260930/source`.
No production restart, deployment, global profile change or autonomous retry.

## Inherited integration context

The following notes describe inherited work, not this branch's task scope.

## September 28 — two concurrent selected capacity goals

Added bounded two-agent admission and per-session stop, retaining shared allocation,
independent native/OS deadlines, same-workspace exclusion and interactive priority.
See [VK_CAPACITY_CONCURRENCY.md](VK_CAPACITY_CONCURRENCY.md) for API semantics,
real two-native-goal acceptance and deployment requirements. Companion CU changes
are required; old clients keep one slot. Production deployment remains operator-owned.

# Capacity Cutover Lock

Current scope: implement authenticated ownership release/acquire with fresh
state reload and paused same-PID fallback for compatible backends. Production
cutover is explicitly withheld by the operator, who is using VK. Do not stop,
pause, restart or reroute production. See VK_CAPACITY_OWNERSHIP.md. The running
legacy backend requires a separate one-time upgrade before using this protocol.

Fix read-only readiness to detect a capacity owner that survives process pause.
Branch fix/capacity-cutover-lock adds the existing-inode lock barrier and real
kernel-lock tests; it does not change production services or silently replace
the operator's same-PID standby requirement. Restart-based recovery is separately
rehearsed with copied data and requires explicit approval before production.

## Integrated Codex Model Selector Regression

Restore GPT-6 reasoning choices and hide GPT versions below5.6 in the Codex
selector. Updated onto staging fa7523c17, this frontend-only compatibility correction
does not rewrite existing chat selections, drafts, defaults or native settings.
No backend restart. See `VK_MODEL_SELECTOR_FIX.md` for evidence and deployment.
## Integrated Staging Context: VK::Weird Message

Scope: reconcile native goal completion evidence within the current turn and
report completion status in the standard summary metadata. Replace the generic
checklist warning with `Completion::` after `Human Needed::`, naming missing
evidence when unverified. VK normalizes its status into the existing report;
a response without a standard report receives a compact metadata line.

The reconciliation request is a single turn/steer pinned to the current root
turn. It never starts another turn, reopens the goal or changes its budget.
Final checkpoints remain accepted after the native completion notification.
A rejected/late steer falls back to an honest unverified status. Checklist
verification is supporting evidence, not an independent audit of the objective.

Backend and shared frontend changes are pushed for
[PR #123](https://github.com/artinflight/vibe-kanban/pull/123) into staging.
They are not deployed. See HANDOFF.md for validation and deployment boundaries.

## September 30: scheduled resume history

Scope: scheduled capacity resumes preserve native-goal supporting progress,
turn/stagnation counters, recovery plans and substantive input holds. Explicit
manual resumes retain their current fresh-attempt behavior. No scheduling,
quota, containment or selected-agent admission limits are relaxed. This is the
manager-side fix; the active Chat Orchestration implementation is separate.
