# Unread report clearing integration

## October 10 resumed owner: fresh client publication verified

Owner resumes implementation head `4696d7177` under Seamus's10:31 source/readiness
scope. Parent Staging has a20-tool catalog and an actual summaries(limit1) read at
10:49:42. This owner independently rechecked its20-tool catalog and actually called
`list_workspace_unread_summaries(limit=1)` at11:30:10 UTC. Both reads succeeded.
[Current-client evidence](scripts/report_delivery/evidence/current-client-20261010.json)
hash-binds the parent receipt and separates those clients from older Dot sessions.
**No Refresh is required for either verified fresh client.** Older Dot conversations
are not independently verified; the earlier14-tool snapshots below are historical,
not a current server/publication gate. Explicit one-workspace mark-read is callable;
no marker was changed merely to test it. Assignment/visibility remains independent.

The current20-tool record schema still lacks paired prepared intent guards and the
prepare tool is absent. Do not send automatic receipts through that unpinned legacy
path. The source-only rr patch adds prepare/paired guards and reuses the existing
backend. Its adoption is a separate maintenance-owner decision; metadata checks for
those new fields are required only after that authorized adoption. Existing
history-module publication and Recommend-only routing are retained, not reopened.

### Exact channel binding boundary

The implemented entry points are `Caller.prepare(identity)` before presentation
and `Caller.confirm(token, confirmation)` after an actual user-channel event, in
`scripts/report_delivery/caller.py`. The channel runtime must retain the same token
with workspace/session/execution/index/full UTF-8 hash/hash-version/revision and
both prepared backend/local intent versions. Pass a report-specific stable event
reference and genuine chat delivery, completed playback or explicit user-handled
acknowledgement. The outbox persists that immutable context before record; retry
never refreshes versions. Reuse this caller, not another connector/backend.

For this owner, commentary/final output belongs to the **hosting conversation
presentation runtime for Root/Dot (ChatGPT/Codex host)**, outside the VK backend
and MCP connector. No exposed tool returns that runtime's post-delivery or
completed-playback event, and no runtime repo/SDK/handler/API identifier is supplied
in this checkout. Therefore an exact named private handler cannot be verified here.
The unresolved API owner is that host's chat/voice transport/presentation owner,
who must identify the actual delivering app/runtime and its supported confirmation
handler/API. This is a runtime integration dependency, not a tool publication or
credential problem; no synthetic delivered event is generated.

The accessible VK function `useSessionSend.send` in
`packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend.ts`
awaits `sessionsApi.followUp` to accept/queue a prompt. That is user-to-worker input,
not confirmation that a worker report reached the user. MCP tools/call success,
execution completion, WebSocket log capture, model final emission, audio synthesis,
partial/cancelled playback and webhook request receipt cannot substitute for the
missing presentation handler. e3e1/PR240 owns capture/consent; its files and package
remain separate. Root/Dot channel ownership does not transfer to that connector.

Next-restart decision: retain explicit user-requested clear readiness; keep automatic
receipt production gated until the channel owner supplies the actual runtime/SDK
and genuine report-confirmation handler, and maintenance adopts the guarded prepare
contract. CLI attestation is not an end-to-end channel binding. No live connector,
restart, security/access/credentials/permissions, routing policy or marker changes
are authorized by this readiness work.

### Inherited CI diagnosis

Full run38043553814 at4696d7177 failed only backend-test job114190057751: the
unchanged routing_triage protected-context test expected Frontier but got Workhorse
at line509. That file is byte-identical to the stream base (SHA256
`90caac528eef4dae2f64b4a4e4406a7224ed3e53b034184dbc00db16f4f3b09c`).
Inspection has a40ms wall-clock budget; exhaustion before discovering the protected
component can leave the default Workhorse floor. Runner scheduling/contention is
therefore a plausible nondeterministic trigger, not a proven cause from this log.
The supplied unchanged mobile rerun-green evidence supports retrying the same source.
No routing/model/policy/test assertion was changed. The exact failed job was rerun
as attempt2 on the same4696d7177 commit:397 passed,7 skipped, including the
previously failing test. This establishes nondeterminism on unchanged source;
the precise load/deadline cause remains unproven. The readiness receipt records it. Full run remote-checks reported success by skipping private-key
checks; that is not independent remote deployment validation.

Shared SSD reached0 free during finalization. Final source/readiness metadata is
retained on `desktop:B:/vk-builds/vk-next-restart-20261010/pr238-readiness/`; the
file-limited docs/metadata commit is published to the existing GitHub branch via
Git API without a new remote. Local checkout/ref sync waits for capacity; all active
work is preserved, with no cleanup or runtime/security change.

## Review boundary

This candidate implements Root/dot delivery preparation, confirmed-event capture,
durable retry and a one-file connector extension. It reuses deployed
`workspace-review-v1` and the existing connector receipt consumer. Assignment,
visibility and capture reliability are separate streams. Nothing is installed.
No production unread markers or previously recorded receipts were changed.
Review: [draft PR238](https://github.com/artinflight/vibe-kanban/pull/238) into staging.

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
| Unread read | Actual current-client `list_workspace_unread_summaries(limit=1)` succeeds. | Preserve a fresh readback per clear; no publication action for verified clients. |
| Server discovery | Real installed discovery returns 20 tools. | Candidate adds one read-only prepare tool and two optional guard fields. |
| Current resumed-owner catalog | 20 actual callable tools; unread summaries query succeeds. | Explicit clear is published. Older Dot clients remain unverified; automatic prepare contract is separate. |
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

## Earlier October 10 receipt: explicit server readiness before fresh-client read

Fresh evidence is in [explicit-read-20261010.json](scripts/report_delivery/evidence/explicit-read-20261010.json).
At the earlier09:57 inspection, installed discovery returned20 tools and that
then-current execution inventoried14 callable Vibe tools, with neither mark-read
nor unread summaries. An authenticated
`list_projects` call through the existing plugin succeeded. The routed backend is
still source `c3c48e6324f778ccd03a5761c2314b440e9ceac3`, PID1254186/port5561;
its running binary SHA256 matches the release manifest. Read-only review-state and
summaries work. Installed `workspace_unread.py` matches PR236's unchanged module.
Existing app permissions are default Allow low-risk actions / Use my default;
no permission setting changed. A missing tool catalog entry is distinct from
per-action approval. This does not establish future mark-read approval behavior.

**Historical correction for the earlier client: metadata refresh.** Current
resumed-owner/Staging clients already query successfully; do not ask them to Refresh.
The individual
`mark_workspace_read({workspace_id})` operation is already deployed, advertised
with a closed one-UUID schema and `readOnlyHint:false`, and dispatched to one fixed
PUT `/api/workspaces/<UUID>/seen`. It needs no new backend, runtime code, connector
restart, Vibe restart, PR236 adoption, prepare tool or delivery callback. The earlier
setup wording incorrectly placed all catalog refresh behind automatic-patch adoption;
that dependency is removed. The optional automatic patch remains source-only.

Only for an older client that independently fails discovery/read, the supported
procedure is: at [ChatGPT Plugins](https://chatgpt.com/plugins), open the **existing Vibe MCP for
dot custom MCP connection**, choose **Refresh**, inspect the discovered metadata,
and start a **new conversation with this connection selected**. Expect20 current
server tools including the two existing unread tools;21 is only the later automatic
candidate. In that new client, verify both names are callable and actually call
`list_workspace_unread_summaries` read-only. Server discovery does not verify client
publication. This UI step requires the connection owner; no refresh tool is exposed
here. Existing credentials, tunnel, network grants and app permissions are retained.
This follows the [official custom-server refresh flow](https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata).
For a published-plugin connection instead, tool changes follow continuous review;
these tools cannot inspect publication type/status, and cannot claim that review
has completed. Do not reinstall, reauthenticate or create another connection to
work around a persistent catalog gap; collect the new catalog/discovery evidence.

Read-only local verification, requiring no outbox or prepared delivery event:

```bash
python3 scripts/report_delivery/verify_explicit_read.py
```

This checks advertised single-workspace schema/annotations and makes only one
summaries read. It deliberately has **no mark command** and reports client refresh
unverified. No real marker needs to change to validate readiness.

For a later **actual user-requested clear**, resolve exactly the named workspace,
call its existing mark tool once, and independently refresh unread summaries.
`marked_read:true` means the backend accepted the clear; it is neither a delivery
receipt nor a fresh `has_unseen_turns:false` observation. Find the requested UUID
in a fresh summaries page (follow pagination if needed); an absent/malformed flag
is unknown. A new reply/manual unread may make the fresh flag true. After an
uncertain write, read state; never automatically repeat the PUT merely because its
response was lost. No startup sweep, bulk request or automatic caller is added.

The deployed `/seen` route uses `manual_intent(read=true)` in the same transaction
as marking existing turns for **one** workspace: it sets backend held=false and
increments its intent version. That is the explicit user's new read intent, not
an inferred release caused by delivery. It does **not** touch connector-local
holds/versions or receipts. A later manual unread/hold advances backend intent
again; stale automatic receipts cannot adopt it. Local review holds continue to
block automatic receipts until explicitly released. Do not silently call
`set_workspace_review_hold(held=false)` as part of clearing, and do not bypass
holds in the delivery caller. Running-turn protection for automatic evidence is
unchanged; an explicit clear retains normal per-workspace UI semantics.

Seven focused tests pass on the **actual installed** adapter/unread/receipt modules
with mocked writes and the PR236 fixture helper. They cover restricted readiness,
no marker calls during verification, local hold preservation, no receipt creation,
post-acknowledgement new unread, lost write response and missing readback. The
combined disposable PR236 candidate passes100 maintenance +44 integration/caller/
readiness cases (144 total). Tested manual SQL constants match deployed source;
this is synthetic/SQL-contract evidence, not a live execution of the PUT route.
No production marker, runtime file, auth/config, service or release changed.
The focused20-test caller/readiness/hash CI passed at `8ed55f8ba`:
[run38043475048](https://github.com/artinflight/vibe-kanban/actions/runs/38043475048).
Full repository checks remain separate; they were in progress at this receipt.

Explicit-path acceptance is independent of the automatic checklist below:

- [x] Recheck running backend provenance, supported read-only capability and installed metadata.
- [x] Mock explicit clear and fresh-readback races against installed modules; preserve local holds and receipt state.
- [x] Current resumed-owner/Staging clients expose the20-tool catalog including mark-read and unread summaries; older clients are separate.
- [x] Actual summaries(limit1) reads succeed in both fresh clients; no clear-for-testing.
- [ ] On a later real explicit clear request, save the single-workspace acknowledgement and separately timed unread readback. No real clear request was executed in this task.

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

### PR238 retry review

Full local `report_reconciliation.py` inspection confirms `consume` never updates
`backend_intent_version`, `hold_version` or the receipt payload. Its UPDATE writes
only status/detail/timestamp/proof. Nonzero pins remain7/2 across pending retries,
new caller/store instances and a lost response after backend commit. Mirrored or
offline hold/release and backend-only UI intent changes stop another POST rather
than adopting new versions. Legacy NULL intent remains NULL; the request's epoch
zero fallback never writes a newer epoch into the ledger.

Focused regressions now cover those stored rows and exact retried HTTP payloads,
including response/readback loss after commit and concurrent duplicate callers.
The original consumer was already preserving pins; no version-adoption repair was
needed. Its comments and regression evidence now make that invariant explicit.

The cached observation defect was confirmed and fixed: an applied outbox cache
returns `readback_fresh:false`, `result_origin:outbox_cache` and a separately named
`historical_readback`. It removes `authoritative_readback` and its timestamp from
the returned cached proof. Connector ledger status is also explicitly historical;
an applied connector duplicate has no fresh proof/readback. Only an independent
successful summaries request sets `readback_fresh:true` and an observation time.
A lost summaries response cannot return a backend's cached flag as current state.

Automatic-path audit: the only receipt send in this proposal is `Caller.retry`,
reached from a persisted `Caller.confirm` event and prepared context. Retry itself
validates both pins before using any injected tool client; `LocalTools.call` also
rejects an unpinned record before dispatch. CLI prepare/confirm/retry uses the same
class. A remote client binding must use that class, not a new direct record call.
There is no installed automatic caller or background worker. The connector's
optional unpinned compatibility path remains for legacy explicit callers; this
proposal does not claim universal server rejection of every external unpinned
caller. The old maintenance direct-Adapter receipt recipe must not be reused as an
automatic runtime callback.

`mark_workspace_read` stays available for an explicit request to clear one
workspace. Automatic code cannot call it. Explicit clear requests retain their
existing user semantics; no new confirmation gate or blanket clearing is added.
Explicit leave-unread/release requests continue through `set_workspace_review_hold`
or normal UI manual-intent routes. Release alone never replays old evidence.

## October 9 delivery/retry validation

The patch was applied to a disposable copy of PR236 connector head `195e3b782`,
then all100 existing maintenance tests and37 new caller/integration tests passed.
The20 integration tests use the real Adapter dispatcher, connector ledger and
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
tested source and results. The dedicated Python CI job tests the17 independent
caller cases and packaged patch boundary. Connector integration needs the owner's
source inputs; CI does not pretend to have them.
The initial15-case caller/hash/scope CI passed at source `dd57fc5ef`:
[run38001200254](https://github.com/artinflight/vibe-kanban/actions/runs/38001200254).
Normal full repository CI was still running when that receipt was recorded.
The revised17-case caller/hash/scope CI passed at source `9f06a0d66`:
[run38002818131](https://github.com/artinflight/vibe-kanban/actions/runs/38002818131).
This receipt validates the source change; full repository CI remains separate.

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
   the combined100+37 tests. Reconcile any differing receipt-source hash instead
   of forcing the patch. No separate connector remote is required.
2. **Authorized connector adoption:** only `report_reconciliation.py` changes in
   this patch. Use the maintenance owner's existing file-limited installation,
   hash verification and connector-only restart workflow after authorization.
   Retain existing receipts/holds/outbox on rollback. This task does not authorize
   installation, restart, auth changes or plugin reconnection. No Rust restart,
   new backend migration or frontend release is required by this patch.
3. **Client metadata owner:** no refresh is needed for the verified current20-tool
   client and successful unread read. Independently assess older Dot conversations. For automatic prepare
   availability, after separately authorized candidate adoption refresh again
   and start a fresh conversation. Confirm21 tools,
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

### Exact remaining channel edge under available tools

[Historical channel/tool evidence](scripts/report_delivery/evidence/channel-binding.json)
records the earlier14 actual callable Vibe tools and the remaining binding contract. Installed
initialize advertises only MCP tools, without a user-delivery/playback event source.
None of `get_agent_replies`, `get_latest_agent_reply`, execution metadata, an MCP
call result or this assistant's commentary/final output returns a confirmed
user-message delivery ID or a completed-playback callback.

The missing owner is **Root/dot's user-channel presentation runtime**. Before
presentation it must associate the prepared token with the exact report and the
channel presentation. Its actual chat-delivery or completed-report-playback handler
must supply that same token, stable channel event ID and redacted report-specific
reference to `Caller.confirm`. An actual explicit handled acknowledgement can
supply the `user_handled` outcome. Cancellation/partial playback has no confirm
call. Model output emission, audio synthesis completion and Vibe worker completion
are not substitute events. The CLI is a local attestation adapter, not this host
callback. No available tool installs or observes the missing channel handler;
end-to-end channel integration remains unimplemented. The current20-tool publication
and actual unread read are verified independently of that missing callback.

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
- [x] In disposable fixtures, prepare then introduce a newer reply, running turn,
  manual unread/hold, hold release or intent change. Delayed delivery cannot clear
  it; newer activity after a successful commit remains unread.
- [ ] Explicit user single-workspace clear still works through its existing tool;
  explicit leave-unread stays held. No unrelated workspace is selected or cleared.

Automatic live acceptance remains open. Current20-tool availability and actual
unread reads are verified; there was no real channel delivery callback, guarded
connector adoption or live receipt/clear in this task. Source implementation and synthetic acceptance do not close those gates.
