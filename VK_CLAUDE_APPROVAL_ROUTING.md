# MP Claude approvals and Dot notification previews

October 26 follow-up on T68 / draft PR281, in the existing implementation
workspace and branch. This is source preparation, not an activated release.

## Evidence and cause

Read-only live discovery identified MP NODEs Production Orchestration workspace
`67768cca-383d-4325-b81c-3f42b54f325c`, Claude session
`c8e17776-282b-4227-bc29-1f10d01dc93f`. Its latest execution
`0f6b4082-b332-405b-8aef-2a637c95748e` completed October26 at15:50UTC. Exactly two
Claude executions exist, neither running. The saved selection is
CLAUDE_CODE / DEFAULT / sonnet / SUPERVISED; reasoning was not explicitly saved.
No effort was invented and no model, profile, ownership or history was changed.

The turn requested reconciliation of existing editable artwork with its owners.
The bounded tool history includes routine `find`/`ls` file-inventory commands.
The retained notifier ledger contains one pending request for that execution:
`f727c333-7649-4f81-a699-144354fe163c`, created15:34:38UTC and observed no longer
pending15:47:26UTC, a roughly13-minute interval. Its notification says only
`review_in_vk`, with no targets or command. The retained disappearance is NOT
proof of human approval, rejection or confirmed timeout. This trace proves one
wait; it does not quantify every earlier interruption or infer outage coverage.

Read-only inspection found no permission-rule arrays in the usual user settings
file, and no project `.claude/settings.json` or `settings.local.json` in the MP
worktree. This is not a complete managed-policy/effective-settings inventory.
The client also ignores native permission suggestions and approves only the
current input (`updated_permissions: None`); it must not turn a one-call approval
into a persistent grant. No previously granted command allowlist was found in
those inspected files.

The sources explain two independent defects:

1. Before this fix, in SUPERVISED mode `ClaudeCode::get_hooks` forced `ask` for nearly every tool,
   including all Bash commands. `on_hook_callback` forwards that decision to
   Vibe's human approval bridge. Task authorization in conversation is not a
   persisted command permission. An unconditional hook ask prevents ordinary
   native read-only classification/scoped allow rules from resolving the call.
   Native Codex `approvals_reviewer=auto_review` is not a supported Claude flag.
2. `ClaudeAgentClient::handle_approval` originally sent only the tool name to
   `ApprovalInfo`, without action input. The notifier then ignored native
   `tool_name`, parsed only MCP consent, and deliberately retained no commands.
   Its read adapter stripped any additional context again. Dot cannot reconstruct
   a missing command from the resulting IDs or honestly present it for review.

Anthropic documents the native rules/callback distinction in
[Agent SDK permissions](https://code.claude.com/docs/en/agent-sdk/permissions).
Current documentation alone is not acceptance of this repository's pinned
Claude Code2.1.62 runtime or authorization to change its policy.

## Prepared notification and security correction

- Add a backwards-compatible `create_tool_approval_with_context` bridge method.
  Claude supplies bounded display context before publication; existing backends
  retain their original decision behavior. No new shared API field is required:
  the existing optional context field is used for native requests as well as MCP.
- Preview only complete safe command/path/URL values and existing target IDs.
  Never retain prompts, file/edit bodies or permission suggestions in notifier
  storage. Credential indicators, control/bidi characters, oversized individual
  or aggregate input cause withholding rather than a misleading prefix. All
  other tool inputs remain omitted; the preview never claims complete invocation
  context or becomes an authorization instruction. Exact review remains in VK.
- Preserve native tool names. Notifications and readback expose an additive
  `action` object with availability and bounded redacted values. Legacy records
  explicitly report unavailable; no old event/history is rewritten or replayed.
- Deny a supervised callback with no tool-call ID, instead of silently allowing
  an uncorrelated action. Correlated requests still wait for the real request-
  and execution-bound owner response; denial and timeout remain denial. No
  permission rules are persisted from an approval or notification.
- Hash-pinned preparation stages the connector/notifier modules only. It never
  installs, restarts, answers an approval, changes a subscription or copies keys.
  Both existing event-engine files match SHA256
  `540eeadc46f1670301d28e70a79e4d7cbdbf7443929742b18ada250138947e23`;
  existing notification reader SHA256 is
  `b0ef05682f34e20259da38930465999467d99711ecc1aa838860cf3949e3d1f9`.

No live source, service, permission configuration, pending request, subscription,
credential, approval outcome or MP task turn has been modified by this follow-up.
The existing successful Claude continuation release remains installed unchanged.

## Authorized native routing correction

The later user instruction explicitly authorizes correcting approval handling
across Vibe with supported provider mechanisms, preserving genuine approvals and
denials. It supersedes the earlier security-control authorization blocker. The
two earlier proposals did not execute; this source change implements the newly
authorized common routing contract without a new profile flag or global edit.

| Saved/selected policy | Claude Code 2.1.62 | Codex existing native path |
| --- | --- | --- |
| Supervised | `default`, native read-only/scoped allow evaluation | `on-request`, native reviewer, workspace-write or retained read-only |
| Auto / legacy default | `acceptEdits`, native edits plus normal unresolved approvals | Same native reviewer, never blanket acceptance |
| Plan | `plan`, no SDK auto-grant for ordinary tools | Read-only sandbox plus native reviewer |

Only questions and plan exits retain a forced interactive hook. Other tools reach
native deny/ask/allow evaluation. Explicit deny and ask rules survive broad allow
rules. Every unresolved callback requires a real interactive owner and nonempty
call ID; missing/no-op service fails closed. Approval is request/execution bound,
keeps original input and never persists suggested grants. Approved plan exit
changes only session mode to `default`, never bypass. Legacy unknown auto-approve
callbacks abstain. Commit-reminder hooks retain their existing behavior.

Initial and resumed commands start with the effective native mode already in
argv. There is no unsafe startup bypass or unacknowledged late policy setter.
Old `dangerously_skip_permissions` profile fields remain readable but are
constrained by that policy with a warning, like Codex's stale full-access clamp.
Explicit bypass/mode/transport flags in custom command overrides are refused
before spawn instead of silently replacing them; custom model, effort, agent,
scoped permission rules and environment survive. Stored profiles are not edited.

Actual pinned CLI help and isolated mock-API fixtures, rather than latest docs
alone, establish compatibility. This version has no newer Claude `auto` risk
classifier. Prompt authorization does not invent a native allow rule, and
`acceptEdits` does not authorize arbitrary shell/network/MCP actions. Some genuine
unresolved actions can therefore still need human review where Codex can use its
native reviewer. No Codex reviewer flag, blanket Bash grant or bypass is applied
to Claude. Both providers retain explicit requirements and denials.

[Rollout, rollback and live verification](VK_CLAUDE_APPROVAL_ROLLOUT.md) binds the
candidate to its exact source and keeps deployment separate from source tests.
No live policy, MP turn, service, database, subscription or credential changed.
The prior connector restart permission was consumed by the earlier continuation
acceptance; it does not authorize a new backend/notifier restart.

## Validation and remaining acceptance

- 49 connector tests pass, including seven new notification tests: full safe
  command propagation, read-only listing, legacy/unavailable data, credential and
  size/control withholding, malicious event refusal, MCP target preservation,
  request-bound outcomes, schema discovery and retry deduplication.
- The existing installed-source verifier passes 28 policy/capacity/status
  regressions and exact executor/schema/dispatch/allowlist checks, offline.
- Three new Rust preview tests and standalone strict Clippy pass using existing
  shared serde_json artifacts, without rebuilding the workspace locally.
- Final code/CI head `1b4049e6fbbd36d69d2d753926ce7bdd79fbd95a` passes
  [focused connector acceptance CI](https://github.com/artinflight/vibe-kanban/actions/runs/40362154224):
  all three preview tests, all four production Claude/Vibe bridge tests, 49
  connector tests and existing steering fixtures. The bridge exercises real
  approve/deny/timeout, unchanged inputs/no persistent grants, sensitive and
  invalid context, execution-ID binding and uncorrelated callback refusal.
- [Standard CI](https://github.com/artinflight/vibe-kanban/actions/runs/40362154121)
  is green on that exact head: 629 Nextest cases passed, 14 skipped, all seven
  new Rust cases passed, 49 connector tests passed, and 15 scheduling checks
  passed (108 filtered). Backend Clippy, schema checks, Tauri and frontend gates
  pass. The earlier run hit a new nonminimal-boolean Clippy lint; `e8e07ccd8`
  fixed it without relaxing lint or changing the redaction checks. The initial
  run is not reported green. Later receipt edits change documentation only.
  Private deployment checks requiring `VK_PRIVATE_DEPLOY_KEY` remain skipped
  and unverified; green standard CI is not live routing/deployment acceptance.
- Local full bridge command:
  `CARGO_TARGET_DIR=/home/mcp/.local/share/vibe-kanban-green-build/cargo-target CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 cargo test --locked --offline -p services --lib claude_ --no-default-features -j 1`.
  A cold dependency rebuild was interrupted with exit130 when the shared SSD had
  only3.8GiB available. This is NOT a passed test. No cleanup, dependency install,
  threshold change or unrelated process stop was performed. The repository's
  existing provisioned CI verifies the bridge; it does not turn the interrupted
  local build into a pass. No further local Cargo build is admitted here.

The following historical checks precede the native-routing correction. Updated
exact-head evidence is recorded in the rollout guide. Live acceptance is still
required after authorized activation: the same MP
session must retain its native identity/model/effort/history/owner, a bounded
routine authorized action must proceed through the chosen supported routing,
and a synthetic genuine approval must remain pending until its exact owner
response while Dot receives the correct redacted command and IDs. Reading or
webhook acknowledgement alone does not prove human-visible delivery or consent.
No new MP turn, paid call or live security approval was generated for testing.
