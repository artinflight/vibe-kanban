# Direct Dot launcher: explicit Claude and safe Codex handoff

VK Dev **T68**, issue `0eb31691-b6e1-406a-a2b9-a4b9bf5ca1f2`, tracks this
source-only change. The dedicated workspace was linked to that new issue before
implementation. Base: fork staging `5b43524ea35b2eb5dd80d0881dc8445489f4442f`.
No live adapter, Vibe instance, global setting, staging branch, existing agent,
production Claude session, or recovery data is changed by this preparation.

## Correct layer and exact executor behavior

The direct connector intercepts `start_workspace` and `run_session_prompt` before
the native Rust MCP tools. Its old discovery schema allowed only `CODEX`, and its
follow-up resolver rejected a valid `CLAUDE_CODE` session with `Cannot resolve
CODEX session`. The native Rust MCP launcher already supports Claude; changing
only that Rust MCP tool would not repair direct Dot dispatch.

`prepare_launcher_connector.py` prepares an overlay against an explicitly pinned
adapter SHA256. It preserves issue preflight, authenticated caller observation,
existing tools, approval notifications, sidechat, fixed endpoints and the CODEX
policy/capacity handlers. It refuses changed integration anchors and never
installs files, changes settings or restarts a service. The prepared module is
`launcher.py`; the live connector source is outside this repository.

- `start_workspace.executor` accepts exactly `CODEX` or `CLAUDE_CODE`.
  Name, explicit prompt, repositories, project and matching issue remain required.
  The advertised schema is independent of an older native MCP tool definition.
- Claude requires an explicit model from the executor's checked-in selector:
  `opus`, `opus[1m]`, `sonnet`, or `haiku`. Unsupported names are rejected rather
  than mapped to another model. Provider/account availability is not established
  by this local catalog. Adding exact provider model IDs requires catalog review.
- The first Claude connector version accepts the default variant only. Custom
  variants fail explicitly to avoid the backend's default-profile fallback.
- Claude effort supports `low`, `medium`, `high`, `max` on Opus/Sonnet. Haiku
  rejects an effort selection. Invalid effort never reaches the executor's
  permissive string parser. Omitting effort retains the selected preset default.
- Existing Claude sessions preserve saved model, effort, variant, permission and
  policy exclusions. The saved UI draft wins over prior execution settings.
  Conflicting explicit settings, cross-executor drafts, unknown formats and
  unavailable reads fail before any POST.
- A fresh Claude session can supply `model_id`, `reasoning_id`, `variant` and
  `permission_policy` to `run_session_prompt`. Conflicting settings in a session
  with saved selection must first be resolved in the owner draft. A fresh session
  with no explicit/saved model is rejected; no model is guessed.
- Existing CODEX arguments retain their original handlers. CODEX uses Recommend
  (`shadow`) routing without replacing the selected model or effort. Claude has
  no Codex recommendation engine: this limitation is stated, and stored routing
  exclusions/floor are retained. No Auto routing is introduced.
- The existing idle snapshot and capacity-queue response remain in effect.
  A capacity-queued response has no new execution ID and instructs callers not
  to resend. Provider quota is unknown; this code never buys or enables extras,
  refreshes a provider account, changes billing settings or retries a model call.

## Explicit Claude-to-Codex handoff

New fixed tools are `handoff_claude_to_codex` and the read-only
`get_claude_codex_handoff`. A write requires an explicit owner request, source
session UUID, exact latest execution UUID, stable request UUID, continuation
prompt and explicit Codex model/effort. There is no automatic capacity-triggered
handoff. The backend uses only the supplied model/effort, validates the configured
Codex model policy, retains model exclusions and forces Recommend.

The backend contract is `GET/POST /api/sessions/{session}/handoff` and
`GET /api/sessions/{session}/handoff/{request}`. Capability discovery requires the
existing serialized admission setting. An absent, incompatible or unconfigured
backend fails closed; there is no `/follow-up`, queue or stop fallback. This
change does not enable the setting.

Admission requires an active workspace and an exact successful Claude checkpoint.
It rejects running processes in any session of the workspace, failed/dropped
source history, queued or incoming input, saved source drafts, unresolved
subagents, unverified continuity obligations, bounded owners and scheduled grants.
The conditional SQLite reservation rechecks DB work at the reservation boundary;
shared admission serializes process launches. Ordinary follow-up/queue input
cannot restart a claimed source or unresolved target.

Context contains every stored source execution/action and its complete raw log,
plus the explicit continuation. Every log must have an actual closed capture and
matching finalized byte count/SHA256. Missing, corrupt, incomplete or oversized
history is rejected without truncation or launch. The full packet must fit both
60,000 characters and 240,000 bytes. Original sessions, logs, files and pending
inputs are retained. This conservative bound intentionally excludes long or
historical sessions whose completeness cannot be proven. Source approvals must
be explicitly persisted; a current preset is not substituted for unknown past
approval settings. The source working directory is retained in the target.

A durable reservation precedes target session creation and the single launch.
Unique source/session and checkpoint identities prevent duplicate handoffs even
under another request ID. The new Codex session uses the same workspace. Success
records its exact target session/execution; cancellation, a failed spawn or an
uncertain response leaves `unknown`, never automatic replay. An unknown target
is also fenced from manual relaunch. Receipt reads are the reconciliation path;
manual resolution of an uncertain launch is a separate operator/release concern.
No automatic recovery/release endpoint is added here.

## Validation and adoption

```sh
python3 -B -m unittest discover -s scripts/dot-connector -p 'test_*.py' -v
python3 -B scripts/dot-connector/verify_launcher_connector.py \
  --source /home/mcp/code/vibe-dot-connector
CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 \
  cargo test -p server handoff --no-default-features -j 1
```

The verifier uses a read-only adapter snapshot and mocked I/O. It runs 28 existing
Recommend/capacity/status regressions, checks the prepared schema with JSON Schema,
and exercises exact Claude/CODEX dispatch, issue preflight, observer preservation,
new tool dispatch and forbidden-tool rejection. The historical Recommend fixture
predates mandatory issue context; its issue prerequisite is supplied in isolation,
then the actual issue gate is tested separately. No real agent is launched.

Backend fixtures cover exact checkpoint rejection, source/target fences,
concurrent duplicate requests, changed identities, cancelled/uncertain dispatch,
complete capture preservation and refusal, pending-work admission, approval
preservation and unsupported selections. They use disposable SQLite/log data.
Local validation passes 12 backend handoff tests, 42 connector tests and 28
legacy connector regressions plus schema/discovery/dispatch assertions. Remaining
checks and limits are recorded in HANDOFF.md. The broader server run has
98 passing tests, 3 failed ownership/bootstrap fixtures and 2 ignored cases; the
large-history failure passes in a separate process, but two launch/timeout
fixtures still fail with collision/capacity rejection. Those failures remain
unresolved, not classified as pre-existing. Full offline workspace validation is
blocked by an uncached Tauri dependency; frontend format/check/lint are blocked
by missing package tools. These gates remain open for review.

Adoption requires coordinated review of the exact current connector hash and a
backend release containing the migration and guarded route. Preserve the current
approval/security integrations and private readers; a public source build is not
a release package. No deployment/restart, paid-model acceptance, production
session handoff or main Dot inventory refresh is authorized or claimed here.
The draft PR targets staging; merging and release acceptance remain separate.
