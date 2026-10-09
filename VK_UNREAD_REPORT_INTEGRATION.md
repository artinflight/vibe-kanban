# Unread report delivery integration

## Review boundary

This candidate implements Root/dot delivery preparation, confirmed-event capture,
durable retry and a one-file connector extension. It reuses deployed
`workspace-review-v1` and the existing connector receipt consumer. Assignment,
visibility and capture reliability are separate streams. Nothing is installed.
No production unread markers or previously recorded receipts were changed.

The patch is packaged in this Vibe draft PR at the owner's explicit direction.
The connector maintenance repository has no remote; no remote was created.
Its isolated source branch is `feature/4113-delivery-context`. The patch changes
**only `report_reconciliation.py`**, with base/candidate/patch SHA256 bindings in
[binding.json](scripts/report_delivery/connector-patch/binding.json).
The existing maintenance owner acknowledged no file overlap through its active
turn on October 9. No capture code or maintenance handoff was edited.

PR236 owns the capture correction: tested backend `3af7fbda8` and connector
`2e4532cf3`, with handoff heads `3cae9537b` and `195e3b782`. Its adapter/status/test
files remain untouched. This patch applies to its connector head without conflict.
The full PR236 baseline must not be merged or deployed independently; its owner
already supplies the bounded delta relative to live backend `c3c48e63`.

## Verified inventory

| Layer | Observed implementation | Remaining connection |
| --- | --- | --- |
| Backend | Live `c3c48e63`; GET review-state confirms `workspace-review-v1`, `atomic_exact_reply`, `manual_intent_guard`. | Existing backend remains authoritative; no second backend or migration. |
| Receipt consumer | Installed `record_workspace_report_delivery` persists evidence and invokes conditional reconciliation immediately. | Pin pre-presentation intent for delayed events. |
| Unread read | Installed `list_workspace_unread_summaries` returns backend flags. | Expose it in the actual dot/client catalog. |
| Server discovery | Real installed discovery returns 20 tools. | Candidate adds one read-only prepare tool and two optional guard fields. |
| This session's catalog | Actual callable tools contain 14 Vibe tools; unread/receipt tools are absent. | Refresh existing custom-server metadata and open a new client conversation. |
| Delivery capture | Existing connector has no confirmed voice/chat delivery callback. | Channel owner must bind the implemented caller to genuine channel confirmation. |
| Frontend | Current release checkout is `5ce84ee21be814b1519cfb2715b50f3432c3e8ba`. | No frontend change; retain this combined release. |

The routed backend service is
`vibe-kanban-current-state-production-20261009.service`, PID1254186, listening on
5561. Its executable is the `c3c48e63` candidate artifact. The connector uses the
existing fixed gateway on4720. Older service units are not deployment targets.
The general frontend pointer resolves to the current `frontend66-over-c3` dist-v6.
These are inspection receipts, not permission to alter any service or release.

[Installed read-only evidence](scripts/report_delivery/evidence/installed-read-only.json)
records real discovery, review-state and a supported unread-summary read, with zero
mark requests. The catalog gap was verified against this execution's available
tools, not guessed from server discovery. The recorded intent epoch may change
through ordinary UI use and must never be reused as a delivery context.

## Implemented behavior

`prepare_workspace_report_delivery` is read-only. It verifies a complete durable
reply identity through existing scoped reads and snapshots both backend intent
and connector hold versions **before presentation**. Preparation is not receipt
evidence. It returns `held` and the existing identity; it does not return raw logs.
The caller declines automatic acknowledgement of held reports.

The existing receipt tool accepts optional paired `expected_intent_version` and
`expected_hold_version`. Automatic callers must pass the prepared versions
unchanged. Recording does not replace them with current versions; reconciliation
uses the existing consumer and exact backend transaction. Guard fields are not
forwarded as unknown backend fields. Old explicit callers remain compatible.
Changing either guard on an existing source event is rejected.

This closes a delayed-event gap in the old caller contract: recording a delivery
after a manual-unread/release cycle used to snapshot the newer intent. A prepared
old event now remains stale. The existing backend independently rejects changed
reply identity/revision, missing closure, newer activity and running/uncertain
turns across workspace sessions. It marks only the exact turn. An older unseen
turn or a newly arriving reply can legitimately keep the workspace badge unread.

[caller.py](scripts/report_delivery/caller.py) implements two explicit boundaries:

1. `Caller.prepare(identity)` retains immutable presentation context in a small
   mode0600 outbox. A reply fetch never submits a receipt.
2. `Caller.confirm(token, event)` persists a genuine channel event before calling
   the existing receipt tool. `chat_delivered`, `voice_playback_completed`, or
   explicit `user_handled` qualify. Partial/cancelled/failed delivery, fetching,
   execution completion and silence never qualify. Worker claims are not events.

The authenticated presentation owner attests actual conveyance; this helper does
not independently prove playback. There is no exposed channel SDK/callback in this
workspace to attach automatically. The source caller is implemented, but a live
transport hookup remains an acceptance gap.

`Caller.retry(token)` replays only an already-confirmed, byte-identical request
after an uncertain result. Backend/connector receipt IDs deduplicate it. Applied
outbox results do not send another mark after restart. One real channel event can
cover individually prepared reports from different workspaces; it never selects
or clears additional workspaces. No polling, startup sweep or bulk seed exists.

`mark_workspace_read` stays available for an explicit request to clear one
workspace. Automatic code cannot call it. Explicit clear requests retain their
existing user semantics; no new confirmation gate or blanket clearing is added.
Explicit leave-unread/release requests continue through `set_workspace_review_hold`
or normal UI manual-intent routes. Release alone never replays old evidence.

## Validation

The patch was applied to a disposable copy of PR236 connector head `195e3b782`,
then all100 existing maintenance tests and26 new caller/integration tests passed.
The11 integration tests use the real Adapter dispatcher, connector ledger and
existing synthetic atomic backend fixture. They do not exercise a production mark
or recompile Rust. Tests cover manual-unread/release before delayed recording,
offline connector hold/release, intent races at atomic POST, newer/running activity,
new unread after commit, genuine-event gating, duplicate/restart/uncertain retry,
unprepared events, broad-clear rejection and multi-report event scoping.

Reproduce without touching the supplied source or runtime:

```bash
python3 scripts/report_delivery/check_connector_patch.py \
  --source /mnt/vk-storage/vk-reply-capture-20261009/connector --test
```

The checker verifies the patch and source hashes, tests a disposable mounted-SSD
copy and leaves source/runtime unchanged. It does not install or deploy anything.
[Validation receipt](scripts/report_delivery/evidence/validation.json) binds the
tested source and results. The dedicated Python CI job tests the15 independent
caller cases and packaged patch boundary. Connector integration needs the owner's
source inputs; CI does not pretend to have them.

`pnpm run ops:check`, `git diff --check`, and Rust formatting passed. Required
`pnpm run format` stopped at missing Prettier after Rust formatting; `pnpm run check`
stopped at missing TypeScript and `pnpm run lint` at missing ESLint. No dependencies
were installed. Full Cargo tests/builds were not run under the no-heavy-build rule
and low SSD capacity. Normal full repository CI remains a review gate.
No generated types, application/frontend/backend sources or schema changed.

## Exact adoption and setup requirements

1. **Connector maintenance owner:** review the one-file patch and its binding.
   Check it against the owner's current source with `check_connector_patch.py`.
   Integrate that patch with PR236's separately owned adapter/status delta; run
   the combined100+26 tests. Reconcile any differing receipt-source hash instead
   of forcing the patch. No separate connector remote is required.
2. **Authorized connector adoption:** only `report_reconciliation.py` changes in
   this patch. Use the maintenance owner's existing file-limited installation,
   hash verification and connector-only restart workflow after authorization.
   Retain existing receipts/holds/outbox on rollback. This task does not authorize
   installation, restart, auth changes or plugin reconnection. No Rust restart,
   new backend migration or frontend release is required by this patch.
3. **Client metadata owner:** after authorized adoption, use Refresh on the existing
   custom MCP server connection and start a fresh conversation. Confirm21 tools,
   the prepare tool's read-only annotation and paired guard properties on record.
   Then actually call unread summaries read-only from that client. A stdio
   discovery receipt alone does not establish client availability. This is the
   [official metadata refresh procedure](https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata);
   [existing plugin sessions do not reload tools](https://developers.openai.com/api/docs/guides/agents-api/tools/plugins#test-a-plugin).
   No refresh or reconnection was performed here.
4. **Root/dot channel owner:** retain exact workspace/session/execution, full
   untrimmed UTF-8 reply SHA256, normalized message index, hash version and exact
   `get_execution.updated_at`. Reject live/truncated/ambiguous replies. Prepare
   before presenting that report. Bind the confirmed chat delivery or completed
   voice playback callback to `Caller.confirm`, with a stable redacted source-event
   reference. An explicit user handled acknowledgement is also supported. Never
   substitute a worker completion/WebSocket event for this callback.
5. **MCP-local Root setup:** the supplied CLI already uses the supported installed
   `Adapter(None)` dispatcher, without credentials or a new network grant.
   Use mounted SSD for its small outbox; imports require the current fixed
   `/home/mcp/code/vibe-dot-connector` installation. For a remote dot client, bind
   the same `Caller` interface to the existing authenticated scoped-tool client;
   do not copy host credentials or expose a generic HTTP endpoint.

Read-only readiness command, usable now:

```bash
python3 scripts/report_delivery/caller.py verify \
  --workspace-id 411319d6-dea1-4a65-88c4-7c487298b686
```

After adoption, the local `prepare --input identity.json`, `confirm --token TOKEN
--input confirmed-event.json`, and `retry --token TOKEN` commands use that same
dispatcher. Store inputs/outbox on mounted SSD. `confirmed-event.json` must come
from actual delivery/handled evidence, never a synthetic fixture or this document.
The CLI cannot manufacture or observe a missing transport callback.

## End-to-end acceptance checklist — real evidence required

- [ ] The adopted connector file hash matches the reviewed candidate; preserve
  PR236's independent source/receipt bindings and current combined frontend/backend.
- [ ] A fresh dot session actually exposes and calls unread summaries and prepare;
  server discovery, metadata refresh and client availability receipts are distinct.
- [ ] Choose one intended completed report with supported closed-log proof. Retain
  exact reply identity and prepared intent versions before presentation. Do not
  backfill historic damaged captures or acknowledge the current running report.
- [ ] Deliver that report through the real user channel, or receive an explicit
  handled statement. Save its real stable channel event and redacted reference;
  aborted/partial playback leaves no receipt. Source evidence names the conveyed
  report, not merely a chat message containing unrelated information.
- [ ] Confirm produces a persisted receipt ID and existing backend exact proof
  with matching execution/index/hash/intent. Save authoritative unread readback;
  expect false only when no other unseen turn exists. Do not broadly clear a
  still-unread workspace to make acceptance look successful.
- [ ] Re-submit the identical event after caller restart. No second marker write
  occurs and later manual unread remains intact.
- [ ] In disposable fixtures, prepare then introduce a newer reply, running turn,
  manual unread/hold, hold release or intent change. Delayed delivery cannot clear
  it; newer activity after a successful commit remains unread.
- [ ] Explicit user single-workspace clear still works through its existing tool;
  explicit leave-unread stays held. No unrelated workspace is selected or cleared.

The first five live acceptance items remain open. There was no actual delivery
callback, metadata refresh, authorized connector adoption or live receipt/clear in
this task. Source implementation and synthetic acceptance do not close those gates.
