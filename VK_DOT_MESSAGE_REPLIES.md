# Exact-message owner replies in Dot Chat

This T63 follow-up adds **Reply to** to owner and Dot message bylines. Selecting a
message shows its author, sequence, Toronto timestamp and a bounded text preview
above the composer. Selecting another message retains the draft; Cancel clears
only the target. Sent owner replies show a linked quote that opens the original
message. Context is plain text, with a bounded preview and access to full history.
The existing Eastern timestamp renderer is retained unchanged.

## Durable contract and existing behavior

The optional browser `send.in_reply_to` is an exact message ID. A new additive
`owner_reply_targets(message,target)` table stores only the immutable link; it
never repurposes `messages.reply_to`, which belongs to Dot delivery/continuations.
Message, link and the existing outbox event commit atomically. Reusing a request
with different text, workspace or target rejects; multiple owner replies can
reference the same message. No extra event or notification type is introduced.

Targets must exist in the same owner/thread. Genuine issue conversation remains
shared between sibling workspaces. Verified dispatch notes can be targeted only
from their dispatch workspace; sibling history shows a context-unavailable label
instead of leaking that note's excerpt. Existing dispatch badges/count attribution,
manual unread, independent attention and agent state are not modified by linking.

The existing owner-created event carries `data.in_reply_to`. Dot's ordinary
`read_sidechat_thread` history includes `in_reply_to` and a server-resolved
`reply_reference` (ID, sequence, author, original creation time, bounded excerpt).
Pending recovery verifies that the event target agrees with the durable link and
fails closed on mismatch. These references are context, not coding-agent authority.
The publisher retains the exact target through its existing delivery path.
Dot still appends its answer to the new owner message/event (or that event's
continuation tip), not to the quoted context message.

`capabilities.message_replies` gates the Reply buttons. Ordinary chat continues
with older services. An uncertain targeted send stores its exact target/body/key
using the existing pending-send mechanism, locks target editing, survives reload
and reuses the identical request on retry. A capability downgrade cannot silently
send that draft as ordinary chat. Unsent selection resets on navigation/reload;
sent links and uncertain sends are durable. Canceling an unsent target remains
possible if the service capability changes.

## Validation

- All84 source Python tests pass, including link durability/reopen/pagination,
  atomic failures, replay/conflicting targets, owner/thread/project isolation,
  shared genuine conversation versus target-only dispatch context, publisher
  payload fidelity, corrupt recovery rejection and preservation of existing data.
- A private three-way overlay onto the current sealed Python baseline merges
  cleanly and passes the same84 tests,34 current connector regressions, and an
  explicit test that an owner quote target stays independent of Dot's later
  continuation chain/context. Current continuation/context/dispatch additions
  are preserved; this is compatibility evidence, not an activated package.
- Isolated Chromium at390/1440 passes issue/project reply selection, replacement,
  cancellation, new replies, quote navigation, SQLite reopen/history/reload,
  duplicate clicks, lost-response retry, capability downgrade and ordinary sends.
  Tests use the actual BrowserAPI/SQLite with no credentials or live state.
- Existing Toronto date/year/DST/browser-zone Chromium checks pass at390/1440.
  Existing manual-unread/attention/navigation/reload and Running/approval/subagent/
  target-sibling/readability DOM regressions pass. Types, focused lint, format and
  ops checks pass. Physical-phone QA and actual Dot delivery are not claimed.

Reproduce the browser acceptance with the host's existing Playwright/Chromium:
`VK_TEST_OUTPUT=<mounted-SSD-output> PLAYWRIGHT_MODULE=<existing-module>
CHROMIUM_PATH=<existing-binary> node scripts/dot-sidechat/test-replies-browser.mjs`.
The fixture starts only a loopback test server and disposable SQLite child;
it cannot open a supplied production database or issue a real credential.

## Staging release ownership and gates

Staging execution `5ab782bd-1696-4ed5-9ecd-8811d89441b4` owns the in-progress
Eastern timestamp deployment. This workspace starts no frontend build, activation,
service action or competing job. Its current live pointers are only read for
ownership; exact private receipts are retained with the test evidence. PR268 and
these existing handoff records carry this follow-up to Staging/Preserve.
The feature was rebased onto Staging's newer T63 head `897164a37`; its collapsible
UI, merged current Staging baseline and compact pickup indexes are preserved.

Integrate only the reply feature diff onto Staging's current approved frontend
and Python candidate **after** its current timestamp activation. Preserve the
newer collapsible frontend baseline and Eastern timestamps; do not rebuild/swap
an older T63 snapshot wholesale, retarget the in-flight timestamp execution, or
replace live Python with the branch's older continuation baseline. The tested
three-way overlay preserves the incumbent Python additions and can be resealed
against a fresh ownership/baseline check by the existing release owner.

This feature needs a **Dot Python/API/connector contract plus frontend release**.
It needs no Rust/Vibe backend change. Advertise the reply capability only with
the matching storage/API installed; initialize the additive table before readers
use it. Preserve all current data/auth/subscriptions, CU/Stop, selected model and
effort, Recommend routing and active jobs. Activation and any required Dot-only
service interruption remain with Staging under its applicable owner approval.
No reply-target feature is live or merged as a result of this implementation.

Rollback must preserve the latest SQLite and the new link table. Once linked
owner events exist, keep reply-aware Python during a frontend rollback; an older
strict pending-event validator does not understand the additive `in_reply_to`
field. A Python fallback must also retain this link/event recovery support.
Never restore an old database or strip links/events to make a rollback pass.
After activation, verify actual served issue/project UI on desktop/mobile and an
isolated-owner Dot roundtrip, including event target and readback reference,
without acknowledging real notes or manufacturing a real user dispatch. Refresh
existing connector metadata only if its cached event schema requires it; verify
actual delivery rather than assuming advertisement is sufficient.

## Derived dispatch presentation compatibility

The panel consumes Preserve's `dispatch_note.presentation` from source174668ed7
([contract and final handoff](https://github.com/artinflight/vibe-kanban/blob/174668ed7/DOT_DISPATCH_ATTRIBUTION.md)).
It renders the supplied neutral author/body as plain text only for a Dot dispatch
with explicit derived/unchanged-storage markers. Message IDs, stored role/body/hash,
sequence, flags and send targets remain unchanged. Genuine messages retain their
ordinary author/content; no text matching or management inference is introduced.

Both composer targets and historical reply quotes resolve derived presentation
from the exact referenced message in the complete loaded snapshot. Stored raw
quote excerpts are not shown in place of the available derived view. Unavailable
cross-workspace references keep their existing privacy label and reveal no text.
The server read helper must be included through Preserve's existing shared-source
composition; this UI change adds no Python, API, access or reload requirement.
Staging retains the one combined activation. Focused actual-container DOM checks
cover issue/project at390/1440, selection/cancel/send target, history quotes,
genuine messages, privacy and unchanged raw data, with synthetic fixture traffic.
No browser worker, production build, deployment or runtime change is performed.
