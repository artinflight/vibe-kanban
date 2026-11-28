# System-wide native Approve for me — PR249

PR249 starts at staging962d2673f, after PR248 integrated PR245 history integrity,
PR246 Git checkpoints and PR247's narrow native-reviewer decoder compatibility.
Do not merge the historical PR247/225/239/240 baselines again. This concern is
system-wide native Codex review, not an unused opt-in profile. Implementation and
isolated acceptance are verified; production activation is unfinished.

## Verified runtime diagnosis

The active unit is vibe-kanban-combined-20261014.service, PID3370830, executable
SHA256d4d73b39eace69a31d85871c487496ac08de3a62eade63cf4157e9feb18c72f9,
matching the reported release. Final read-only reconciliation confirms that
incumbent and staging are unchanged. The actual runtime wrapper is
/mnt/vk-storage/vk-model-autoswitch-v1/integration/runtime/codex.mjs; it reports
`codex-cli 0.159.2`. Native config selects reviewer user. DEFAULT supplies
danger-full-access without a reviewer override; NATIVE_APPROVE_FOR_ME is a
separate opt-in workspace-write/on-request/auto_review profile.

T18's inspected start/resume responses explicitly report user/on-request/
dangerFullAccess. Read-only saved-context audits found zero auto_review contexts
among the active Codex executions, including workers with policy never; the
latest audit counted five active executions. Counts are snapshots, not release
admission. T18 and other workers were never interrupted, redirected or approved.

Installed source3d2ee51 resolves MCP reviewer precedence link > app > app default >
session. Session-only selection cannot defeat stale app/link overrides. Live
config has no declared app overrides; the implementation covers arbitrary future
apps/accounts without a Figma/tool-name exception. Read-only overlap inspection
covered PR225/workspace870d, PR239/240/e3e1 and PR115; no owner was retasked.

## Implementation

The sole production AppServerClient construction enables global native review
for every Codex profile/project. Before typed start/resume/fork, it reads
project-effective config and reconciles root/app/default/link reviewers to
auto_review, preserving app/tool enablement and approval modes. Optional null app
properties are omitted because native config/read uses null for absent/inherited
TOML fields. Malformed config or config-read failure blocks dispatch. Private
config responses/errors are suppressed from raw process logs.

Preflight pins guardian_approval and write_stdin_approval. The latter is essential:
native0.159.2 otherwise defaults off review of input to an already escalated
terminal. Ordinary and feedback turns repin native reviewer/on-request. Auto and
stale Never/OnFailure profiles use native review; Vibe's full-access/noop acceptance
shortcuts cannot replace native or mandatory human decisions.

Read-only/Plan stays read-only; other Codex profiles use workspace-write. The
silent host-namespace fallback to danger-full-access is removed: sandbox setup
failure must fail. Managed native requirements remain authoritative. Network
permissions, app/tool approval modes and optional tool exposure are preserved;
request_permissions, network proxy and zsh-fork are not enabled in production just
to make fixtures pass. Sandbox-permitted actions can run without a review event.
A reviewer-only change with danger-full-access would not provide sandbox safety.

Human-only fallbacks require an interactive approval service; Noop cannot approve.
Permission fallbacks grant exactly the explicitly approved permissions for the
current turn, or empty permissions after refusal/timeout. MCP bridge one-shot
consent, native denials and mandatory human/auth/persistent flows are preserved.
Unsupported forms cancel safely; they are never converted into Accept. No generic
external approval responder, protocol upgrade or history transformation is added.
Recommend routing and other executor families' approval mechanisms are unchanged;
other families are not advertised as native-Codex-reviewed.

## Exact compiled evidence

Code/test head9afe687c9a617acc96b018a6a58921fc83acb5e0 passes:

- [Full Test38640253559](https://github.com/artinflight/vibe-kanban/actions/runs/38640253559):572 workspace tests,13 existing skips;12 scheduling-enabled tests,90 unselected; applicable Clippy, schema/SQLx, frontend and Tauri checks. Remote private-dependency checks explicitly skip without their deploy key.
- [Native compatibility38640253455](https://github.com/artinflight/vibe-kanban/actions/runs/38640253455):14 actual typed decoder/history/error regressions, one existing skip;12 native review/policy/human-fallback tests; actual isolated executable startup acceptance. Native artifact11930992822 is acceptance-only.
- [Source-fenced artifacts38640258375](https://github.com/artinflight/vibe-kanban/actions/runs/38640258375): namespace prerequisites and paired candidate/rollback/guard/module/frontend build pass. Artifact11930867486's779 artifacts and2527 tracked-source hashes were independently verified. Its candidate server SHA256 is d81ef8a86968000278334ef0020b2a3663d725f14d0ce4789fd3b0b434ecca9f.

The retained PR247 tests reproduce raw auto_review decode failure and exercise
actual await_response for start/resume/fork. Legacy reviewers, strict unknown/
malformed rejection, unrelated methods/nested payloads, IDs/history/errors/sandbox/
policy and existing history/error regressions remain covered. Current real typed
peer tests additionally verify config reconciliation for all three requests and
that a synthetic private config marker never reaches raw logs.

Public artifacts exclude the live private reader overlay and must not be deployed
directly. Native0.159.2 account-backed tests used the actual runtime wrapper,
read-only credential mounts and isolated filesystem/PID/IPC/UTS namespaces. No
credential copy, account change, external connector write or live approval occurred.

## Actual action and session acceptance

All seven registered native review variants have runtime evidence. Each positive
case checks linked native review events, decisionSource=agent and actual outcome.

| Native review variant | Actual coverage |
| --- | --- |
| command | Source-bound Vibe DEFAULT Auto escalated printf and terminal launch; direct in-sandbox/escalated commands; successful exits/output. |
| execve | Bundled zsh intercepts /usr/bin/printf; native review c66298fa-41c3-4a91-8071-359fb8df0341 plus parent command review; marker/exit0. |
| writeStdin | Corrected9afe DEFAULT Auto backend resumes the existing fixture thread despite CLI guardian/stdin=false; native review0f9273b6-5852-4bb8-ac93-6c154f861a5a approves exact marker/exit input; output/exit0. |
| applyPatch | Native-reviewed marker creation outside workspace but wholly inside isolated fixture storage. |
| networkAccess | Managed-policy fixture reviews one public HEAD request, review4214cfbd-26fe-4ab9-994d-8dc75a0782f8 for http://example.com:80; response/exit0. Ordinary user-proxy misses remain hard-denied. |
| mcpToolCall | Actual DEFAULT Supervised fresh-process legacy-thread resume calls real stdio MCP fixture. Direct native read/write/same-thread second turn/fresh-process resume, unauthorized nested denial and mandatory human form also pass. Existing connected Figma whoami read passes with native review; no design/customer assets or external writes. |
| requestPermissions | Native tool enabled only in its private fixture reviews exact turn-scoped write access to a disposable fixture path. No network or persistent grant. |

Baseline498c8449 actual Vibe HTTP DEFAULT start and legacy resume deliberately use
stale user/never/danger-full-access native config, app/link reviewer=user and a
reviewer=user CLI override. DEFAULT Auto command review`301fa1ac-29c1-467f-8132-24b6753d2760` succeeds. The next DEFAULT Supervised process resumes a genuinely
persisted legacy-user native thread and completes reviewed MCP dispatch. Only
Vibe fixture metadata binds that old thread; native history is never fabricated
or edited. Its original40620-byte prefix remains identical (SHA256 `346b4385ea2bbf35de40ed8a4a2d5ac7e857a2046fd2b0ce4df87f5734ee7b76`).

The corrected9afe backend then resumes that same thread with CLI guardian=false,
stdin-review=false and stale saved config. Command review `fd192ad5-5ab2-46dd-a4b8-2adcb806434e` and the stdin review both succeed. Raw responses retain auto_review;
saved context is auto_review/on-request/workspace-write/network-disabled. Each
original history prefix stays unchanged. Private backends are stopped. Direct
native fixtures cover same-process second turns and fresh-process resume. Fork
uses current typed request tests; the earlier narrow compatibility acceptance
exercised a real native fork turn. A new global-policy fork model turn is not claimed.

The mandatory nonempty form reaches native human elicitation and receives no
automatic answer; only that dedicated fixture turn is interrupted. The native
nested-action denial prevents connector dispatch. Production bridge/unit tests
preserve explicit human approval, refusal, cancellation/timeout and exact turn-only
permission grants. Native user-configured proxy misses intentionally do not have
the managed review callback; no live requirements are changed to bypass that rule.

Seventeen account-backed root turns total were used. Failed null-field and
namespace preflights occurred before model/tool startup. Collectors corrected
symlink target-content hashing and nullable latest-turn binding selection without
replaying a model action. The initial unavailable permission-tool attempt and
unmanaged-network denial retain their failed/denied receipts; they are not relabeled
as successful reviews. Exact private receipts, source hashes and coverage.json
are under /mnt/vk-storage/vk-system-auto-review-20261014.

## Prepared rollout and unfinished requirements

Read-only helpers prepare settings and audit effective saved contexts:

- scripts/testing/prepare-native-review-rollout.py emits before/after fields and native/profile file-hash preconditions. Current proposal: six native edits (reviewer, on-request, workspace-write, guardian, stdin review, app default reviewer) and one DEFAULT profile edit (workspace-write/on-request). It applies nothing.
- scripts/testing/audit-native-review-rollout.py reads only active execution/native-thread bindings and bounded turn_context records, skipping large conversation records. It reports timestamps, reviewer/policy/sandbox and unknown evidence; it never changes approvals/history or prints conversation/credentials.

The Rust delta applies cleanly over actual deployed source5a5abd2e. All existing
modified source bases match staging, and a separate private source receipt binds
all2524 candidate inputs while retaining all three private history-reader files
byte-for-byte. Source/receipts remain private. This preserves PR245/246 and live
reader behavior; source equality is not private runtime acceptance.

SSD capacity initially blocked the private builder, then recovered without this
owner deleting anything. The prepared namespace/version probe passes as ordinary
uid/gid1000 with production home/data/manager paths absent. The prior private MCP
build exception was scoped to an earlier build; the new exact-source exception is
requested and pending. No compiler job started. The launcher retains job1/CPU1,
4GiB/no swap, offline/frozen source/toolchain/dependency isolation,5GiB monitored
aggregate output and >2GiB SSD plus existing host-resource floors. It stops only
its own build on refusal; no automatic expansion, shared cleanup or B/R access.

After build authorization: verify exact private source/artifact hashes, run
existing copied-current/runtime acceptance with current reader/continuation/Git
checkpoint authority intact, and prepare current-data-compatible rollback. Retain
current frontend, capacity guard, routing module/validator/scanner and service
configuration. Require the existing healthy backup/current-data and natural
safe-idle release conditions. Never recapture original history/authority or stop/
retask T18/other owners to satisfy a gate.

The user separately requires exact-action authorization for live policy/profile
writes, merge and immutable package cutover/restart. Those actions remain
unperformed. Do not partially apply global settings to the old binary. After
activation, verify genuine new DEFAULT and naturally resumed existing workers by
native review IDs/outcomes, actual command/connector dispatch and saved contexts;
repeat the read-only audit for stale workers. Existing in-flight approvals remain
with their owners; restart success or a DEFAULT label is not coverage evidence.

Rollback uses the retained incumbent server/current-data-compatible owner package
plus only the proposal's listed before-values (remove originally absent keys),
with fresh checks to preserve later unrelated settings. A new-code binary still
enforces review even if native config is reverted. Preserve latest DB/history,
credentials, private readers, continuation state and Git checkpoint obligations;
never restore a fixture/historical database or rewrite reviewer decisions.

Unverified: retained-source private build, copied-current acceptance/rollback,
backup/safe-idle cutover and live post-activation coverage; production OAuth renewal,
paid/destructive connector operations, every third-party tool and other executor
families are not certified by these fixtures. No system-wide live activation is claimed.
