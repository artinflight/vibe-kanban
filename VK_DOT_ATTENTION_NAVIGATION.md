# Jump to Needs Attention in Dot Chat

The visible **Jump to Needs Attention** button selects the oldest unresolved Dot
flag. Previous/next controls move chronologically and wrap; the counter and an
outline identify the selected message. Navigation scrolls only the chat history
and focuses the message. It never calls Resolve or an acknowledgement API.
The existing visibility-read policy, manual unread and independent attention
remain unchanged.

The existing container reads every page through its pinned snapshot before
publishing history. Navigation waits for that initial load, so older flags are
included. Empty history says “No unresolved flagged messages”; failed loading
says it could not check flags rather than claiming none exist.

Selection uses a stable message ID and sequence. If a flag changes, the next
action finds the next surviving flag relative to that sequence. New messages and
polling do not pull the selected message away. Explicit quote links retain their
existing behavior, and Jump to latest leaves attention navigation.

## Validation

The real React container/panel passes DOM and isolated Chromium checks for issue
and project chats at390/1440. Tests load125 messages across three pages, pause
pagination, find older/long flags, navigate both directions and wrap, repeat
clicks, resolve/reopen/add flags externally, reload history, handle zero/one flag
and loading failure, preserve quote navigation, and verify pane-local scrolling,
mobile44px controls and no horizontal overflow. All navigation fixture requests
are GET; manual unread and flags survive unchanged. Physical-phone QA is not
claimed.

Existing notification, Running/approval/subagent/dispatch-attribution/readability
DOM regressions, notification Chromium checks, durable Reply to SQLite/API browser
acceptance and Toronto date/year/DST/update/reload checks pass. The automatic-read
effect remains byte-identical to the published Reply to implementation. No Python,
API or event-contract changes are introduced by this follow-up. The new DOM test
is included in the existing notification CI step.

## Coordinated next release

Reply to `2a29ae93ab2c269e45b038254234ee4c80aba4ff` remains the parent feature;
retain its [matching storage/API/event requirements and latest-data rollback](VK_DOT_MESSAGE_REPLIES.md).
Attention navigation itself is frontend-only. Staging owns the next combined
release; Preserve Dot Integration execution
`88a68ab1-59be-4ec5-8a15-8173286b9c7c` owns exact-message acknowledgements. These
changes do not edit its shared Python/API paths or expand its authorization.

Staging verified timestamps live at07:12:15 EDT on October18 from source
`897164a377a653586327cc45563ad892805e030c`, preserving the collapsible baseline.
The derived private integration record binds that activated owner's receipt,
complete frontend manifest, current root, retained rollback and B delta alongside
the existing Reply to handoff. Prior r1 inputs and receipts remain untouched.
This is baseline reconciliation, not a new Nightly capture or whole-backup claim.

Apply the feature diffs to the current baseline; do not replace it with an older
snapshot. This workspace performs no full frontend build, merge, activation,
service action, real authentication or conversation mutation. Timestamps are
live; Reply to and attention navigation await Staging integration and live
acceptance. Selected model/effort, Recommend, CU/Stop and active jobs are preserved.
