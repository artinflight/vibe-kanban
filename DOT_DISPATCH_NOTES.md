# Dot-origin dispatch notes

## Supported protocol

The existing Dot connector observes successful `start_workspace` and
`run_session_prompt` results **after** the dispatch and before returning the MCP
response. PR271's issue precondition and exact error result are unchanged. Native
Vibe/UI user prompts bypass these hooks and never become Dot-origin notes.
Caller text cannot select an owner, author role or receipt identity.

A confirmed execution receipt is stored in the private connector journal before
attempting the chat write. Native read-only execution/session/workspace/task/
project joins verify its exact binding, coding-agent run reason and retained
issue association. Existing owner project grants/all-project policy authorize
the destination. No workspace is created, linked or relinked by the note writer.

The explicit internal `record_dispatch_note` path accepts a verified dispatch
principal. It can create the first authorized thread for a linked workspace,
without any previous owner message. It inserts one ordinary visible Dot message
with `reply_to:null`, normal Dot unread state and a separate execution binding.
It creates no owner message, owner event, fake reply target, subscription or wake.
Existing reply tools still require their original scoped owner event.

Notes use only these fixed safe summaries and the execution UUID:

- New workspace: “Dot prompted this workspace's agent to begin the requested work.”
- Existing session: “Dot prompted this workspace's agent to continue the requested work.”

No prompt body, account detail, title, person name or model-generated summary is
copied into either the note or journal. Acceptance records admission, not
successful completion: an accepted execution can subsequently fail or be stopped.
Failed/unknown dispatches do not produce an acceptance note.

## Durability, retries and readback

The journal is keyed by authenticated owner and accepted execution ID; the chat
note has the same unique owner/execution key and a deterministic request UUID.
Message, unread state and note binding commit in one SQLite transaction. Concurrent
receipt retries or a lost note acknowledgment cannot produce another note. A
completed receipt cannot be downgraded by an older competing failure.

The existing sidechat publisher retries up to 20 pending accepted receipts every
five seconds, with fair ordering and a 0.5-second soft batch budget. Native/chat
lock waits are bounded to 100ms so recovery yields to existing message delivery.
It never sends/resends an agent prompt, launches an actor, scans unrelated
executions or calls a model/provider. A process restart
or lost MCP response after receipt capture retains the note/recovery state. The
SQLite journal and chat data remain private and owner-readable only.

The first MCP result content block is preserved. A second JSON block supplies
`dispatch_note` state (`noted`, `pending` or `awaiting_execution_receipt`) and known
receipt IDs. A pending note **does not mean the agent dispatch failed** and never
permits resending that prompt. Read the existing cached
`get_workspace_reconciliation_status({workspace_id}).dispatch_notes` for bounded,
owner-scoped receipt/readback state. Reading does not retry or mark anything read.
All previous delivery, hold, CU/budget and freshness fields retain their meaning.

## Exact unsupported receipt boundaries

The current backend start/follow-up request types do not carry a stable external
origin/request key correlated with a returned execution. See
`crates/db/src/models/requests.rs` and
`crates/server/src/routes/sessions/mod.rs`.

- If the **backend POST response** is lost before its execution receipt reaches
  the connector, acceptance remains unknown. The connector does not infer Dot
  provenance from identical prompts, timing, a latest execution or an agent report.
  No acceptance note is emitted and no prompt is automatically retried. Backend
  request-to-execution correlation is required to close this gap. This is separate
  from losing the outward MCP response after the receipt was captured, which is
  recoverable by the durable journal.
- Capacity-queued follow-ups return no execution ID. They receive
  `awaiting_execution_receipt`; no note falsely says an agent accepted them.
- Sequential-setup starts can return a setup execution, rather than a confirmed
  coding-agent execution. Those receipts stay pending with
  `agent_execution_not_confirmed`. The worker does not guess the later agent ID.
  A backend queue/setup-chain-to-agent receipt is needed for complete coverage.
- An unlinked existing workspace or an unauthorized/relinked issue cannot receive
  a fabricated note/thread. Its receipt remains pending until a supported, exact
  association is available. PR271 prevents new issue-less connector starts.
- If receipt storage itself fails after dispatch, the result retains the accepted
  execution information and reports note persistence unavailable; it never reports
  a note as saved. Automatic recovery requires a durably captured receipt.

These are backend receipt dependencies, not voice/call-routing changes. The
scoped implementation adds no Rust migration, backend restart or new credentials.
It does not replace backend dispatch idempotency or relax the existing no-blind-
retry rule. No live negative-start probe or validation workspace is required.

## Source, tests and adoption

This stream depends on preserved PR271 source and the live PR270 follow-up
runtime. Runtime preparation copies the complete current sidechat bundle and
changes only its worker; it must retain sidebar/mobile/attention/steering/artifact
behavior and the original sidechat contracts. `prepare_dispatch_notes.py` gates
exact adapter/status/worker hashes and checks unchanged AST nodes outside the
three scoped hooks. No new tool name, argument or catalog refresh is needed.

34 public connector tests and 66 incumbent Python sidechat regressions pass.
Fixtures cover Dot/user origin; accepted/failed/unknown dispatch; first-message
notes; session/workspace binding; scope changes/isolation; concurrent retries;
restart/MCP-response loss; note-commit acknowledgment loss; unread state; no
owner event; safe purpose text; fair and monotonic recovery. Full private-adapter
mocked dispatch checks both start/follow-up hooks. The existing PR271 full-adapter
harness still passes 28 exact rejection vectors, unchanged valid mocked creation
and 27 incumbent controls. Every start in these tests is mocked; no real agent,
workspace or live negative-start request is used.

Before adoption, verify Desktop B source/data backup and isolated restore, fresh
module/service pins, and connector idle evidence. Adopt only the connector and
existing publisher worker. Browser/frontend/Vibe/agents and voice/call routing
stay running unchanged. Rollback retains latest databases and standalone note
messages; prior code renders the standard Dot messages without needing the new
receipt tables. Record actual cached read-only acceptance separately from fixture
validation and any future naturally authorized live dispatch.

## Deployed receipt — 2026-10-18 00:18 UTC

[PR272](https://github.com/artinflight/vibe-kanban/pull/272), into staging, is
stacked on [PR271](https://github.com/artinflight/vibe-kanban/pull/271).
Functional source `8c5b505df7462df694cd762ff8f2a6d4a8bdf033` was adopted at
00:18:09 UTC. Only the connector and existing publisher were reloaded; HTTP
readiness took 0.459 seconds. Vibe, agents, browser, frontend/static/gateway and
notifier retained their process/pointer identities. The original PR271 guard,
all CU/report/budget/Stop modules and complete incumbent sidechat bundle except
its worker remain byte-identical.

| Installed component | SHA-256 |
| --- | --- |
| Adapter (two post-dispatch hooks) | `fd9a3d6a0b864a9b5433cf90f6c9bd4687075fafb8430bc049c0979b29ff51a5` |
| `dispatch_notes.py` | `9b8aedbda9e233c80a2df5c1e1da9b4b915ccfc463902c1434605186210d821d` |
| Status wrapper | `8a03ca7e954519c90a968681a80c545eb0c771bdbb32699ecd1095a59af1a093` |
| Existing publisher worker | `75a4cf65db29441f1bc0f4e080ac28c50a20a83bcd58080d1b7920346026bbef` |
| Preserved PR271 guard | `50056e974b9577a0d3d220331923f332d6cba0ef61beb4af03491ce8465b3c07` |

The **actual cached registered** `get_workspace_reconciliation_status` returned
`dispatch_notes:{status:"recorded",receipts:[]}`. Its original fields were exactly
equal before/after, including the original sidechat association, hold/delivery
fields and `readback_fresh:false`. That flag is not upgraded by note availability.
The receipt journal is mode 0600 with SQLite integrity `ok`; it contains no
historical backfill. The repaired workspace/issue/branch API record was unchanged.
Protected sessions/grants/subscriptions and all pre-existing messages were
verified at the boundary. No synthetic live message, workspace or execution was
created. Accepted live note rendering awaits a naturally authorized real dispatch;
fixture/full-adapter acceptance is not claimed as a live agent run.

Private manifests, cached receipts, source/data snapshots and rollback procedure
are retained under the named mounted-SSD `vk-dot-dispatch-notes-20261018-v2`
release directory and Desktop B's matching `vk-backups` directory. Both before and after
archives passed upload/download hash equality, isolated source restore and SQLite
integrity checks. Rollback restores code/pointer only, preserving the latest
chat and receipt databases. No private chat contents or runtime IDs are published.

Local ops and diff checks pass. `pnpm run format` was attempted: Rust formatting
passed, then missing Prettier blocked frontend formatting. Broad frontend/Rust
checks were not run locally; no compiler window or UI work was used. Public CI
and protected-branch integration are tracked in the PR, separately from scoped
runtime acceptance and the backend receipt limits above.
