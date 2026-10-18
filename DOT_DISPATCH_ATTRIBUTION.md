# Dispatch attribution correction — source only

Audit: [PR272 source 71252feae](https://github.com/artinflight/vibe-kanban/pull/272).
The old hooks called `observe` without caller evidence, `origin='dot'` defaulted
all connector dispatches to Dot, and the note writer emitted fixed Dot wording.
Only the accepted target execution/session/workspace was verified. That proves
where work was accepted, not who initiated it.

This branch preserves selective acknowledgement source
`fe69d36dc0846762a418c2a8b8a0a5dfd26e1de0` as an ancestor. Its acknowledgement,
connector tools/schemas, bounds and protection rules are unchanged. That narrow
permission is now owner-approved; activation remains coordinated by root/Staging.
This turn does not deploy, reload, clear notifications, change runtime pointers,
authentication, grants, routing, model or effort, or create an execution/workspace.

## Trusted caller evidence: currently unavailable

The inspected deployed adapter receives JSON-RPC over the tunnel's stdio command.
The service routes that command through one `main` transport channel. The adapter
accepts raw `_meta` but has no verifier for an initiating actor and passes no
trusted caller context to dispatch. `VK_APPROVAL_PRINCIPAL` identifies the access
owner; it does not distinguish root Dot, a manager or a native user. Target-native
execution records likewise do not identify the initiating connector caller.
No credentials or secret values were inspected to reach this conclusion.

Consequently **no initiating identity is currently verified**. `current_caller()`
records that trusted host observation as:

```json
{"kind":"unknown","verification":"unavailable","reason":"runtime_caller_not_attested"}
```

There is intentionally no known-root/manager/user attribution path until the
platform supplies verifiable, per-request actor provenance. Caller names in
prompts, tool arguments, `_meta`, owner display names, target workspace identity,
timing and generic connector use never upgrade this record. No caller argument
is added to a public tool, and no permission/credential setting is introduced.
A verified transport-to-request actor assertion (including its trust verifier)
is the precise dependency for future named attribution; another generic channel
or owner label is insufficient. Native UI prompts still bypass connector hooks.

## New receipts and notes

Both source preparation paths explicitly pass `current_caller()` at the trusted
runtime hook. The old `origin='dot'` default is removed. New receipt metadata
commits in `dispatch_receipt_callers(owner,execution,caller)` in the same transaction
as the accepted receipt. `VerifiedDispatch` carries this metadata separately from
its verified target identity. Chat-side metadata in `dispatch_note_callers` commits
with a new note and its existing dispatch binding. These are additive side tables;
no original receipt/message/read-state columns or values are rewritten.

New accepted notes say:

> The workspace agent was prompted to begin [or continue] the requested work.
>
> Caller: unknown (no verified initiating-caller identity).
> Accepted execution: the exact accepted execution UUID

No private prompt body, inferred manager name or personal detail enters the note.
Target execution verification, grant/scope checks, deterministic request identity,
owner/execution uniqueness, monotonic completion, bounded publisher recovery and
no-blind-resend behavior remain. Lost outward responses and note acknowledgements
recover without duplicate notes. Failed/unknown acceptance, no-execution capacity
queues and setup-script receipts do not produce a false coding-agent acceptance
note. Backend lost-response/queue/setup-chain correlation limits from PR272 remain.

## Historical data and T63 presentation contract

Missing historical caller evidence is always
`kind:unknown,verification:unavailable,reason:historical_caller_not_recorded`.
Retries never backfill caller identity or rewrite old messages/receipts. Original
message IDs, raw `body`, `hash`, request keys, sequence, execution bindings and all
seen/manual-unread/attention values remain unchanged.

The only shared `sidechat.py` change is a two-line read hook. For an exact existing
owner/message/thread/workspace dispatch binding it adds:

```text
dispatch_note.caller                 unavailable/unknown metadata
dispatch_note.ownership_signal       false
dispatch_note.presentation.author_label  "Dispatch"
dispatch_note.presentation.body      neutral accepted-execution wording
dispatch_note.presentation.derived   true
```

The stored raw body/hash remain available unchanged for audit; the derived body
is explicitly separate and must not be treated as the original hashed content.
T63 can render the neutral label/body for dispatch notes, including historical
ones. This branch does not bundle UI rendering. Genuine conversation gets no
new dispatch classification. Existing target-workspace filtering occurs before
the presentation hook, and wrong-owner bindings yield no derived presentation.
No read creates metadata tables or changes message/notification state.

**Dispatch and management are independent.** `ownership_signal:false` means this
record supplies no ownership evidence; it is not a command to unset an explicit
association. T63's persistent dot-managed indicator must use its separate,
owner-authenticated association. Neither a generic dispatch, inspection, unknown
caller nor T18 subordinate activity may create that association. This stream
writes no management association and does not infer positive or negative ownership.
T63 Reply source `2a29ae93a` and Jump source `a04f35176` remain separately owned;
no UI or `browser_api.py` file is modified or replaced here.

## Validation and adoption requirements

44 connector tests and 100 sidechat/T63/owner-reply/acknowledgement tests pass.
Six caller-specific cases also pass against an exact-live Store overlay, including
legacy schema/receipt replay without backfill, unchanged raw historical data,
unknown-caller durability, pending recovery, wrong owner/genuine conversation
protection and byte-preserving upgrade patches. Full private-adapter mocked
start/follow-up dispatch passes, including spoofed `_meta` actor claims, unchanged
PR271 error results, unknown-dispatch suppression and duplicate receipt handling.
All work is fixture-only: zero live prompts, notes, agent turns or state writes.
Ops/diff checks pass. Required formatting passed Rust formatting, then stopped
at missing Prettier. No compiler/browser work or full Rust/frontend CI is claimed.

`prepare_dispatch_attribution.py` gates exact adapter and Store hashes, patches
only the two accepted-result hooks and the two-line presentation addition, and
verifies preservation of every other AST/source byte. It never writes live files
or runs services. It copies the corrected receipt module and shared attribution
helper into a candidate. The initial PR272 preparation script is corrected too.

A candidate was tested against deployed adapter
`fd9a3d6a0b864a9b5433cf90f6c9bd4687075fafb8430bc049c0979b29ff51a5`
and deployed T63 Store
`dd184669bdb07bc2156ecc5efe5c1bea1f56494876a510126615f01f09440aaf`.
Its adapter hash is
`ed2de6dba65cce7d8e43c7260126b3f119f451bc52662ec4ddbb9beb82b5ca84`;
its Store hash is
`f8e517989267f808bb4500f90edb1b6d04c826f5a232e87336e0c6ca9be93417`.
The corrected receipt module hash is
`2bb47d7d483afe18c4f75e4a340381dcc239eb0c19fea278650359e3e5f3a1d2`;
the shared attribution helper is
`a63f5ee7efdb7e4af1254c66d8931ece8b723d825eb2acf6f82664cf6572d596`.
The preserved acknowledgement module is
`9f568c587d3a97d615bf8940af46dd26172e33301a0a215e52aa05b0bf769e12`.
Those are prepared/source artifacts, **not installed versions**. Future preparation must
refresh shared source pins and reconcile T63 ownership work rather than install
an entire old branch/bundle. Copy no older `browser_api.py` or frontend over newer
source. Package the shared helper with the complete current sidechat release so
connector and browser readers can resolve it, preserving all other modules.

Root/Staging now owns the authorized combined publication and narrow connector
reload; do not ask the owner to repeat that approval. This source owner performs
no activation. Use the established backup/rollback boundary and preserve the
latest chat/journal data through any rollback.
The source-only selective acknowledgement remains unactivated here. Derived
historical presentation requires T63's renderer to consume the supplied metadata;
no live UI/caller identity/catalog adoption is claimed by these fixture results.

## Final package/catalog handoff to Staging

Selective acknowledgement's exact source remains fe69d36dc; its module, connector
hook, tools/schema and tests have no functional diff in this correction. The
owner explicitly approved the narrow action plus safe connector reload. T63's
current Reply2a29ae93a, Jumpa04f35176 and verified-management work remain separate
shared inputs; preserve Eastern timestamps, collapsible UI, CU/Stop and the
current private adapter. No new worker or separate publication owner is needed.

Compose against **fresh complete shared source**, with no overwrite of newer
`sidechat.py` or `browser_api.py`:

1. `prepare_notification_ack.py` gates current connector/contracts/Store hashes.
   Its output is only `notification_ack.py`, a three-line connector hook and
   appended schemas. Preserve all incumbent event/tool definitions and permissions.
2. `prepare_dispatch_attribution.py` gates the current private adapter and Store.
   Its output supplies the two caller-context hook changes, corrected
   `dispatch_notes.py`, shared `dispatch_attribution.py`, and only the two-line
   read hook over the freshly pinned Store. It rejects changed anchors rather
   than replacing newer ownership code. No browser API replacement is required.
3. Place `dispatch_attribution.py` in the complete shared sidechat runtime import
   path used by connector, browser and publisher. The corrected receipt module
   belongs alongside the existing private adapter. Preserve every other adapter
   AST node and all CU/Stop/Recommend/model settings. This preparation never changes
   a live file, pointer, credential, grant, service or database.
4. T63's renderer should use `dispatch_note.presentation` for dispatch label/body,
   keeping raw body/hash as immutable audit data. Management comes from its explicit
   owner-authenticated association, never the dispatch table or caller metadata.

Proposed named catalog additions (no upstream adapter `ALLOWED` expansion):

- `list_workspace_dot_notifications`: read-only, one existing authenticated-owner
  workspace, bounded exact IDs/state tokens, no message bodies or implicit seen.
- `acknowledge_dot_dispatch_notes`: ONE workspace, 1..50 exact distinct
  `{thread_id,message_id,state_token}` selections; current owner/thread/target
  verification and CAS/no-clobber decisions in one transaction. Protect genuine
  conversation, owner manual unread, unresolved attention, sibling/new/unselected
  messages and every coding-agent flag. A response is an observed selected-item
  readback, never a blanket workspace-clear claim. Duplicate retries cannot undo
  a later owner unread action. The approved cleanup must still use fresh exact
  inventory; this source turn performs no live inventory or acknowledgement.

Candidate routing is tested through the actual adapter with fixture-backed
connector calls; this does **not** prove new tool adoption in main Dot's catalog.
Staging should verify the actual registered discovery/dispatch path and fresh
read-only inventory after its owned release, then use only the already approved
exact-ID cleanup scope. No credential/grant workaround or alternate route.

Reload dependency: the existing publisher imports `recover_pending` from
`dispatch_notes` inside its five-second loop; Python caches that module. Updating
files and restarting only the connector leaves the publisher's old writer loaded.
Its future pending-receipt recovery could still emit the old fixed Dot text.
The combined runtime plan must account for refreshing that cached publisher
module as well. The persistent browser likewise needs its updated Store read hook
loaded for derived historical presentation; T63's new API/UI runtime already has
a coordinated adoption boundary. Do not claim either path updated from a connector
health check alone. No Vibe backend or agent restart is required. This handoff
flags those module-lifetime dependencies to the release owner, not a separate
activation or permission bypass by this workspace.

For exact code review, compare the four PR272 files listed below against audit
head71252feae, and review the new attribution/helper/test/preparation files on this
branch. The shared Store diff against fe69d36dc is exactly two additive lines;
there is zero `browser_api.py`, UI or acknowledgement implementation diff:

```sh
git diff 71252feaeca0b9deba53d0faed59731e07f76d95 HEAD -- \
  scripts/dot-connector/dispatch_notes.py \
  scripts/dot-connector/prepare_dispatch_notes.py \
  scripts/dot-connector/test_dispatch_notes.py \
  scripts/dot-connector/verify_dispatch_notes.py
git diff fe69d36dc0846762a418c2a8b8a0a5dfd26e1de0 HEAD -- \
  scripts/dot-sidechat/sidechat.py scripts/dot-sidechat/browser_api.py \
  scripts/dot-sidechat/notification_ack.py
```
