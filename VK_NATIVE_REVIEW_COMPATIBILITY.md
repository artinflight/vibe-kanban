# Native Approve for me compatibility

## Problem and bounded repair

The retained isolated test at
`/mnt/vk-storage/vk-native-auto-review-test-20261013/test-state.json` failed before
any probe command: `thread/start` rejected `auto_review`, expecting `user` or
`guardian_subagent`. The live launcher is Codex 0.159.2 at
`/mnt/vk-storage/vk-model-autoswitch-v1/integration/runtime/codex.mjs`.
Protocol dependencies remain pinned to `rust-v0.116.0` / `38771c9082535aa1`.
This branch starts from fork/staging `7f06d040a4b3c6f92eb7dde9c1fbc9265d778aa4`.
Its JSON-RPC source was byte-identical to deployed source
`d45035b0f9999f75e6bd4582a8cedd2f2785b857` (SHA256
`18f5e289834ce9d21d45c9a7a10d5fb32b3030672df16d20274e35309bdb7821`).

`sanitize_response_value` maps exactly the top-level `approvalsReviewer` string
`auto_review` to `guardian_subagent` only for `thread/start`, `thread/resume` and
`thread/fork`. `await_response` adapts a response copy after the reader has
passed the original raw line and response to its callback. There is no recursive
mapping, native configuration write, outbound conversion, reviewer default,
unknown reviewer fallback or approval-decision conversion. No protocol upgrade.

The current official [Auto-review documentation](https://learn.chatgpt.com/docs/sandboxing/auto-review)
explains native reviewer routing. Local upstream source at
`3d2ee51ca2d5db578f328aa75e20aa22c0197c9a` declares the same `AutoReview` variant
with `serde(rename = "auto_review", alias = "guardian_subagent")` in both
`protocol/src/config_types.rs` and `app-server-protocol/src/protocol/v2/shared.rs`.
The pinned v0.116 response enum calls that reviewer `GuardianSubagent`.
This supports the inbound spelling alias; native runtime/schema verification
and actual account-backed acceptance must supplement source evidence.

## Boundaries and integration

Read-only overlap inspection covered PR225/workspace870d, PR239/240/e3e1, and
PR115. Their MCP consent, human review and error compatibility paths are
preserved. PR245 large-history/continuation integrity and PR246 planned coordinated
release must remain independently reviewable. The release owner can apply this
small source/test delta to the final coordinated candidate; do not promote an
older baseline or independently restart Vibe. Recommend-only routing is unchanged.

Auto sets approval policy to `never`; explicitly configured `on-request` survives
Supervised. Acceptance must use Supervised, `workspace-write`, `on-request`,
`auto_review`. Live DEFAULT is `danger-full-access` with reviewer `user`; it is
not modified. Changing only the reviewer does not supply sandbox safety. The
existing host-dependent sandbox fallback must be checked against the actual
saved effective context; a downgraded sandbox cannot count as acceptance.

## Validation and acceptance gates

New tests in JSON-RPC use each actual `ThreadStartResponse`, `ThreadResumeResponse`
and `ThreadForkResponse` through the production `await_response` path. Each first
reproduces the raw decoder error. They check `user`, `guardian_subagent`, missing,
unknown and malformed reviewers; malformed policy/sandbox/thread data; unrelated
methods/nested content; raw response/JSON-RPC IDs; failed turn identity/history,
error message and RPC failures. Existing history/item/service-tier/error tests
stay intact. A configuration regression checks Auto/Supervised policy precedence.

No local Cargo compilation is permitted for this task. The focused hosted
`native-review-compatibility.yml` runs the regressions, builds an immutable
candidate server/test binary and verifies actual isolated startup using the
existing namespace fixture. Export binds source/tree/file hashes and artifact
hashes. It starts no account-backed worker, activates no routing module and
performs no deployment. Normal Test CI supplies the broad baseline.

Final integrated release consumption must repeat acceptance in an isolated private backend/home/root,
read-only existing account authentication, explicitly authorized harmless printf
with `require_escalated` to cause eligible native review, first turn and second
turn on the same thread, fresh-process resume and fork when supported. Require
native review started/completed evidence, outcome linked to the command, and
saved `on-request`/`workspace-write`/`auto_review` context. A successful command
inside the sandbox is not proof of review. Human elicitation must stay human;
no blanket external approval responder. Use bounded turns and retain sanitized
receipts on mounted SSD. Do not change credentials or production profiles.

## Rollout and rollback handoff

Do not deploy this branch. Require exact-head CI, isolated native acceptance,
independent review and the release owner's inclusion in the coordinated candidate.
Recheck its source delta against deployed/latest integrated source; preserve
PR245/246 and the live wrapper/history contract. Rollout follows the normal
explicitly authorized safe-idle coordinated restart, current-data backup and
artifact receipt workflow. No new default or permission changes are implied.
Rollback this alias by reverting its source hunk in a new candidate, or use the
release owner's verified paired rollback while preserving latest data. Native
`auto_review` threads will again fail typed decoding under the old protocol;
retain their native data and do not rewrite history or config as a workaround.

## Native runtime evidence at the executable source head

Executable/test head: `da209fdee76e1872c3de8d1b66d41e026423b84d`.
The configured launcher reports `codex-cli 0.159.2`. Generated schemas for
ThreadStartResponse, ThreadResumeResponse and ThreadForkResponse all declare
`user`, `auto_review` and `guardian_subagent` and explicitly describe the last as
the legacy alias. An ephemeral native start configured with the legacy spelling
returns the canonical `auto_review` spelling, confirming equivalence on the
actual installed runtime without changing native defaults.

Four bounded native turns passed in a private fixture: FIRST and SECOND on the
same process/thread, RESUMED after a new app-server process, and FORKED on a new
fork thread. Each emitted matching `item/autoApprovalReview/started` and
`item/autoApprovalReview/completed` events with `decisionSource: agent`, low risk,
status approved, the exact authorized printf action and matching target item ID.
Each reviewed command exited0 and each turn completed. Root saved rollout has
three effective turn contexts with `on-request`, `auto_review` and
`workspace-write`; fork contexts retain the same settings. No external approval
responder was installed. This proves native review, not an unreviewed command.
The candidate HTTP integration is recorded separately when its artifact is ready.

Private scripts, schema outputs, event records and sanitized receipts are retained
under `/mnt/vk-storage/vk-native-review-compatibility-20261013`.
`evidence-index.json` binds the scripts and native receipt by SHA256. Account
credential contents are not copied into that packet or committed: the existing
file is mounted read-only into the fixture. PID/IPC/UTS/filesystem namespaces mask
host managers, homes, worktrees and mutable production state; outbound model
access uses the shared network. The HTTP driver addresses only its randomly
allocated loopback candidate port and contains no generic approval responder.

The first fixture masked the `/run` resolver target as well as host managers and
failed before model output/usage/command. A no-account namespace probe reproduced
the missing resolver and DNS error. Only this task's fixture was cancelled. The
corrected fixture binds the resolver read-only; neither host DNS nor account
credentials were changed. For the Vibe HTTP test, nested bubblewrap must pass
before the fixture uses existing `VK_ASSUME_USERNS_BLOCKED=0`; this hint is scoped
to that private backend to preserve the requested workspace-write policy.
No production hint, host policy or sandbox fallback is changed or certified.

## Compiled validation

[Hosted Test38421738894](https://github.com/artinflight/vibe-kanban/actions/runs/38421738894)
passed at executable/test head `da209fdee`:554 Rust tests passed,13 existing skips,
including the five new JSON-RPC tests and Auto/Supervised configuration test.
Existing history/error/deadline regressions passed. Workspace Clippy, schema/SQLx,
frontend and Tauri checks passed. The unchanged remote-backend job explicitly
skipped private-dependency checks without a deploy key; remote paths are untouched.
Local `pnpm run format`, `ops:check`, legacy-path guard, all four frontend type
checks (4 GiB Node heap), local-web/UI lint and diff checks passed. No local Cargo
compilation occurred; aggregate local Cargo stages were not run.

[Scheduled artifact38421738644](https://github.com/artinflight/vibe-kanban/actions/runs/38421738644)
failed before compilation at its known routing-module namespace prerequisite:
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. This separate
release artifact gate is not waived or repaired by this compatibility patch.
The narrow native acceptance builder uses the normal hosted test namespace setup
and exports an acceptance-only backend, without a routing-module release package.

## Candidate HTTP acceptance and final handoff

[Native compatibility38421739086](https://github.com/artinflight/vibe-kanban/actions/runs/38421739086)
passed14 focused JSON-RPC tests (one existing private-fixture skip), the
policy-precedence regression and18 real-server startup/identity cases. It built
and exported artifact11827492874 from `da209fdee`:
server SHA256 `c7b24f6a2d6e4b69ef9a8d8863ea81c94f777e1f107e0c381fdb5ae598fdd492`;
executor-tests SHA256 `089086b5cd676f6c845d2e72451e126ea472b34288c95f5837597b64849bbef0`.
The downloaded receipt and both binaries passed independent local hash checks;
all tracked executable/test/build inputs match that source. Later changes are
continuity documentation only. This is an acceptance artifact, not a coordinated
release package or deployment nomination.

The private actual Vibe HTTP backend completed exactly two authorized worker
turns, VIBE_FIRST and VIBE_RESUMED, on the same native thread. Both have matching
native review start/completion IDs, the exact printf action and target command,
`decisionSource: agent`, approved outcome, successful command exit0 and completed
execution/turn. Original persisted JSON-RPC response logs still contain
`approvalsReviewer: auto_review`, `approvalPolicy: on-request` and
`sandbox.type: workspaceWrite`. The saved native rollout has exactly two effective
turn contexts with `auto_review`, `on-request`, `workspace-write`. No external or
human approval requests were answered or present in those probe traces.

The collector initially missed the two-character session-directory prefix, then
incorrectly parsed arbitrary Stdout chunks as whole JSON-RPC lines. Both worker
commands had already completed. Read-only reconciliation concatenates Stdout
chunks before line parsing and checks both retained process logs and saved native
context. Neither command was repeated; final reconciliation makes zero model
calls. The private backend was stopped by fixture teardown after each phase;
no live Vibe service was started, stopped or restarted. Corrected receipt:
`backend-fixture/backend-acceptance-reconciled.json` under the retained SSD evidence
root. The initial collector errors and native DNS setup failure remain retained
with the final passing receipts; they are harness errors, not decoder failures.

[Draft PR247](https://github.com/artinflight/vibe-kanban/pull/247) is independently
reviewable into staging. Required next actions are independent review and the
release owner's integration of this exact source/test delta into the coordinated
PR245/PR246 candidate, followed by that final candidate's CI/artifact/native checks
and separately authorized safe-idle cutover. The scheduled routing-module artifact
namespace gate still fails and is not waived. Do not merge historical approval
bridge baselines through this patch, activate AutoSwitch modes, change native or
Vibe DEFAULT permissions, or use this fixture as a production rollback dataset.
Rollout/rollback must preserve latest native/Vibe data and the existing combined
source/paired artifact contract. No deployment or live acceptance is claimed.
