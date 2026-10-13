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

Actual native acceptance remains required: isolated private backend/home/root,
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
