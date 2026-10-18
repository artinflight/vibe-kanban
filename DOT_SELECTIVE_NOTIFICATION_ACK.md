# Selective Dot dispatch-note acknowledgement — source only

Seamus asked Dot to clear Dot Chat notifications alongside the explicitly
selected Dot-used workspaces. This implementation provides the missing normal
connector capability without using a browser session, minting credentials or
mutating live state. It is **not deployed and performs no live cleanup**.

## Reconciled shared baseline

The branch is stacked on PR268's newer T63/owner-reply source
`2a29ae93ab2c269e45b038254234ee4c80aba4ff`. Its manual unread, workspace dispatch
attribution, quoted owner replies, attention, frontend and browser API are not
edited here. The deployed package was independently inspected:

| Live component inspected | SHA-256 |
| --- | --- |
| T63 `sidechat.py` | `dd184669bdb07bc2156ecc5efe5c1bea1f56494876a510126615f01f09440aaf` |
| Sidechat connector | `35ec4b57727e55ab50bb745dd7fddc88c44d67d0912701f0ec536228fd10230d` |
| Sidechat contracts | `8e0a77640a1858a0846920c420265d589fe238d448fa18b96f7773cb9fd5a525` |
| Browser API | `3196e1d45abdcd73f0f6a685e9d10b9923d7455ef1c1774086ee2c60c0e4bad6` |
| Private adapter | `fd9a3d6a0b864a9b5433cf90f6c9bd4687075fafb8430bc049c0979b29ff51a5` |
| Dispatch receipt integration | `9b8aedbda9e233c80a2df5c1e1da9b4b915ccfc463902c1434605186210d821d` |

Live T63 keeps genuine conversations issue-shared, attributes verified dispatch
notes only to their workspace, and preserves `manual_unread` independently of
attention. Its browser seen operation accepts only an authenticated owner and
skips manual unread. The new implementation does not relax that browser path or
turn a Dot principal into an owner principal.

## Proposed supported tools

`list_workspace_dot_notifications({workspace_id, after?, limit?, through?})`
opens the existing private store with SQLite `mode=ro` and `query_only=ON`.
It performs no store creation, schema upgrade, backfill, grant or read-state
mutation. Existing authenticated-owner scope resolves the thread. It returns
bounded pages (1..50) of existing Dot message metadata: exact thread/message/
workspace IDs, sequence, verified dispatch execution when present, current seen/
manual-unread/attention state, protected reason and a compare token. No message
bodies, prompt text, owner identity argument or browser secret are returned.
Sibling dispatch notes are excluded; genuine shared conversation is labelled
protected. Pagination pins an upper message sequence; reading never marks seen.

`acknowledge_dot_dispatch_notes({workspace_id, items:[{thread_id,message_id,
state_token}, ...]})` requires one canonical workspace UUID and 1..50 distinct,
explicit selections. No thread-wide, issue-wide or workspace-wide clear exists.
Unknown arguments, owner/role inputs, wildcards and duplicate IDs reject.
The server verifies the entire batch's existing owner/thread/workspace binding
before any update. A wrong-owner, missing, sibling-dispatch or non-Dot ID rejects
with no partial writes and no outside-scope existence disclosure.

Only an existing verified `dispatch_notes` binding can qualify. Genuine Dot
replies/conversation, manual unread, unresolved question/action attention and
changed state tokens are left intact. Protected items have individual outcomes.
An already-seen retry performs no update; if the owner subsequently marks that
note unread, retries preserve the override. A malformed dispatch binding cannot
turn a conversation reply into an eligible dispatch note.

Validation, conditional decisions, exact-ID seen updates and selected-item
readback occur inside one `BEGIN IMMEDIATE` transaction. Responses identify each
selection's outcome and current state, with an observation time and current
upper sequence. They do not claim that an entire workspace is clear: unselected
or newly arriving messages are untouched, and later owner changes can supersede
the response. Compare tokens are state fingerprints, not credentials or grants.
No action resolves attention, edits messages, generates an event, changes a
subscription or calls a coding-agent/native workspace read-state endpoint.

## Source and validation

- `scripts/dot-sidechat/notification_ack.py`: narrow inventory/ack operations.
- `scripts/dot-sidechat/connector.py`: three-line additive early dispatch hook.
- `scripts/dot-sidechat/contracts.json`: two additive tool definitions; old
  tool/event definitions are retained.
- `test_notification_ack.py`: 14 focused fixture tests, including target/sibling
  isolation, wrong owner/IDs, protected attention/manual/conversation state,
  unchanged message/outbox/agent flags, duplicate/response-loss retry, new
  arrivals, changed compare token, bounded pages/IDs and incompatible schemas.
- `prepare_notification_ack.py` and its two tests: exact-pin preparation with
  unchanged original AST/definitions and rejection of stale shared source.
- `verify_notification_ack.py`: fixture-only acceptance against exact deployed
  Store/adapter bytes; it opens **no live state** and makes no live tool call.

The full 98-test sidechat/T63/owner-reply suite passed, followed by the two new
preparation tests (100 distinct tests total). All 14 focused cases also passed
against the deployed Store. The actual installed adapter's two new dispatch
routes passed with fixture-backed connector calls and network disabled. This
proves candidate routing, not main Dot catalog adoption or live acknowledgement.
Ops and diff checks pass. Required `pnpm run format` was attempted: Rust formatting
passed, then missing Prettier stopped frontend formatting. No Rust compilation,
UI/browser work, agent/workspace launch or runtime security change was performed.

## Adoption and authorization boundary

**No deployment is authorized by this turn.** The additive definitions register
through existing `sidechat_connector.TOOLS/NAMES`; the inspected adapter needs no
upstream `ALLOWED` expansion. However, this is a new persistent read-state write
capability for the authenticated Dot owner. Today only browser-owner seen calls
have that authority. The proposed permission is limited to the owner's explicitly
selected, unchanged, non-manual, non-actionable verified dispatch notes; the risk
is that such selected activity badges can be hidden. It grants no general
conversation, coding-agent, attention-resolution or cross-owner clearing power.
The owner has now explicitly approved this exact narrow capability. Deployment
remains coordinated by root/Staging and is not authorized in this attribution
turn. Preserve any applicable server security review; do not require the owner
to repeat the unchanged permission approval. If the platform has
an additional registered-connection allowlist, its exact change must be reviewed;
this implementation does not edit one or change authentication.

At the separately coordinated deployment boundary, refresh the live pins and use `prepare_notification_ack.py` to
prepare **only** the new module, the additive connector hook and appended tool
definitions against the complete latest live package. Preparation verifies the
old AST and all old tool/event/schema metadata, and leaves `sidechat.py` alone.
Do not install the entire stacked branch or substitute its older/private-missing
bundle: current live and unactivated shared owner-reply source differ. Preserve
all newer modules, PR271, CU/Stop, sidebar, browser/frontend, subscriptions and
current data. Use the established backup/rollback procedure, then a connector-only
reload at a safe boundary. No Vibe, browser, publisher, agent or backend restart
is required by these hooks. Prove actual registered discovery/dispatch before
claiming availability; main Dot catalog propagation may be separate.
Live acknowledgement remains a later, explicitly bounded cleanup action after
fresh inventory and exact selection. No credentials/grants, browser workaround,
database workaround, synthetic live note or validation agent is part of that step.
