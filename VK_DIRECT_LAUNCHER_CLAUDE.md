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
approval settings. Custom source presets and agent modes are also refused: their
semantics cannot be translated to a different executor by selecting defaults.
The source working directory is retained in the target.

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
The connector suite passes 42 tests and the installed-source verifier passes 28
legacy regressions plus schema/discovery/dispatch assertions with zero live calls.
The additional backend regressions exercise unrelated CODEX admission alongside
an unresolved handoff, and refusal to discard a custom source preset/mode.
All 14 focused handoff tests pass. The final complete server-library matrix on
code head `888518dcb0c3c06873cef1e95cb12e9239648291`, with each case in its own
120-second-bounded process, reports **103 passed, 0 failed, 2 ignored**. No case
timed out. Ignored cases remain ignored, not passed. Final test binary SHA256:
`9d8eb7f8a8e8cd65ee03a5814d633b74f7466364f86b941a7d014c15e7acbe64`.
The following documentation-only receipt update does not change tested Rust or
connector source.

Strict focused lint also passes:
`cargo clippy --locked --offline -p server --lib --tests --no-default-features -j 1 -- -D warnings`.
The pure validators use a small internal error type mapped to the existing HTTP
400/409 variants; unsupported selections and custom-preset refusals assert those
variants. This resolves the new helpers' strict-lint errors without changing the
shared API error enum or suppressing lints.

### Ownership-fixture diagnosis (October 26 follow-up)

Comparison base is exact PR staging base
`5b43524ea35b2eb5dd80d0881dc8445489f4442f`; incoming PR head was
`ed9c9015cb3281d44ead17336f45101af70b27e4`. A `git archive` snapshot under this
workspace's ignored `.out/t68-validation/base` had all 2,644 regular tracked
files verified against base Git blobs. It was compiled with the same locked,
offline, no-default-features server-library command, shared SSD Cargo target,
`CARGO_INCREMENTAL=0`, debug info disabled and one compiler. The standard build
script generated dummy frontend assets for this test-only snapshot; no backend
was started. Base test binary SHA256:
`a48a406754e1ec5f31c7c258465880d6474c04596288d9ad85c3894a63d1db36`.

The ownership worker, its fixtures, Codex admission and process inventory sources
are byte-identical to base. Run an individual bounded fixture using the compiled
server test binary, `original_worker::tests::<name> --exact --nocapture`, in a
fresh process, with a 120-second timeout and temporary files on the mounted SSD.
The bounded base/updated-branch results were:

| Fixture suffix | Isolated base (seven engines) | Branch (seven engines) | Final code head (six engines) | Classification |
| --- | --- | --- | --- | --- |
| `production_follow_up_resolution_launch_and_workspace_races` | Fails at `tests.rs:1053`, both admissions return `Worker collision or capacity guard blocked` | Identical capacity assertion | Passes, 2.42 seconds | Existing fixture's positive path is environmentally capacity-blocked. |
| `production_timeout_receipt_recovery_and_revoke_endpoint` | Same failure at the same assertion | Identical capacity assertion | Passes, 2.70 seconds | Same host-capacity boundary. |
| `production_large_history_startup_and_native_input_admission` | Passes, 51.21 seconds | Passes | Passes, 46.14 seconds | Previous shared-process failure is baseline harness interference. |
| `production_startup_holds_pr_monitor_archive_launch_until_adopted` | Passes, 2.50 seconds | Passes | Passes, 2.27 seconds | Isolation control passes. |

Read-only inventory using the exact native process-matching/deduplication rules
found seven app-server engines; `VK_USE_SYSTEMD_RUN` and execution-limit overrides
were unset. `original_worker_capacity_available()` requires fewer than seven,
independently of the fixture's synthetic swap sampler. Both failing admissions
return before dispatch, so they never reach this PR's new follow-up fence.
The earlier branch matrix was 101 passed, 2 capacity-blocked failures, 2 ignored.
During the final committed-head run, read-only inventory showed **six** engines
(11:45 UTC), with the systemd override still unset. The host availability changed
naturally: both positive launch/timeout paths then passed, with all four ownership
fixtures passing in isolation. No process was stopped, safety threshold changed,
capacity override enabled or collision guard bypassed. The earlier failed runs
remain failed evidence; the final green run independently closes these two paths.

The base's four production fixtures run together with `--test-threads=2` all
failed with shared-native-goal / SQLite thread-identity errors. They mutate
process-global `CODEX_HOME` and register a process-global worker authority;
`tests.rs:645` explicitly requires process isolation. The repository CI uses
`cargo nextest run --workspace --exclude vibe-kanban-tauri` for that reason.
Local bounded comparisons use a separate process per case, without installing
nextest or changing the host's bubblewrap/AppArmor policy. Shared libtest failure
counts are not a valid regression comparison for these fixtures.

### Broader dependency/resource boundaries

The repository-declared pnpm setup now succeeds using the existing mounted-SSD
store: `pnpm install --frozen-lockfile --store-dir /mnt/vk-storage/pnpm-store`.
`pnpm run format`, `pnpm run ops:check`, both frontend lint scripts, the legacy
path guard and unused-i18n check pass. `pnpm run local-web:check` reaches TypeScript
but exits 134 with V8 heap exhaustion near 750 MiB. Node has no `NODE_OPTIONS`
override; the task's existing memory.high is 1,572,864,000 bytes and memory.max is
3,145,728,000 bytes. No resource limit or heap override is changed. Full
`pnpm run check` therefore still needs a sufficiently provisioned test runner;
frontend type checking is not claimed green. The existing CI/preparation setting
is an 8,192 MiB Node heap, which exceeds this execution's 3,000 MiB hard limit;
it was not applied to this host.

The previous uncached `arboard v3.6.1` blocker was resolved through normal locked
Cargo dependency resolution. `cargo test --locked --workspace --no-run -j 1`
now exits 101 at `glib-sys v0.18.1`: the exact failing prerequisite is
`pkg-config --libs --cflags glib-2.0 'glib-2.0 >= 2.70'`, with `glib-2.0.pc`
unavailable. `gtk+-3.0` and `webkit2gtk-4.1` pkg-config packages needed by the
Tauri member are also absent. A runner with these declared native development
libraries is required. No system packages, security profiles or global
configuration are installed/changed. Full-workspace Cargo test/check/clippy and
the aggregate `pnpm run lint` are not claimed green; the Rust portion needs those
native prerequisites. Focused server testing excludes the unrelated Tauri member.

Adoption requires coordinated review of the exact current connector hash and a
backend release containing the migration and guarded route. Preserve the current
approval/security integrations and private readers; a public source build is not
a release package. No deployment/restart, paid-model acceptance, production
session handoff or main Dot inventory refresh is authorized or claimed here.
The draft PR targets staging; merging and release acceptance remain separate.

Remaining end-to-end acceptance requires a separately authorized coordinated
backend/migration and exact hash-matched adapter adoption, followed by disposable
Claude workspace/session dispatch with explicit model/effort and approvals, an
idle complete-history handoff to the explicitly selected Codex model/effort,
receipt reconciliation/replay proving one target launch, source/unknown-target
fences, and readback of history, Recommend policy and approval settings. It also
requires the broader native/frontend gates on a provisioned runner. None of these
requires or authorizes experiments on an existing production session.
