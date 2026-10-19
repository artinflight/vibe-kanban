# Dot notification destination scope

Shared issue history and notification destination are different concerns. The old
reader classified every substantive reply without a dispatch receipt as shared
issue activity, then added that count to every sibling workspace. A new reply
could therefore recreate sibling badges after the old dispatch notes were seen.
Read-only inventory confirmed this recurrence; no live state was acknowledged.

Notification counts now use the message's stored workspace only when it matches
an existing owner/project/issue/workspace scope. Both substantive messages and
verified dispatch notes follow this rule. A project thread contributes only to
its project notice. Issue totals remain available; legacy messages without a
validated workspace remain issue metadata and shared history, without assigning
any workspace. Caller or management identity is never inferred from this scope.

The notification inventory and exact-selection validator use that same stored
destination. Genuine conversation remains protected from dispatch acknowledgement.
Shared history, reply quotes, manual read/unread, attention transitions, delivery
and coding-agent flags are unchanged. The workspace renderer no longer falls back
to issue totals when exact workspace counts are absent. No state migration, message
edit/deletion, automatic seen operation, attention resolution or new access exists.

## Validation and release

Synthetic tests recreate a new manager reply after old notes were seen across
five same-issue workspaces. They cover target-only counts/inventory, shared history,
manual unread/repeated reads, independent attention, reload, project-only notices,
unknown legacy attribution, owner/grant isolation and unchanged metadata snapshots.
Frontend tests cover neutral siblings and legacy aggregates; existing history,
read-state, selective acknowledgement and project tests remain required.

This correction is separate from the already approved `b7f3dfeec` frontend package.
Preserve that artifact, its hosted CI and all rollback assets; do not rebuild or
replace it with this later work. The correction is source/test preparation only.

Adoption needs a compatible frontend plus the two changed Python readers:
`Store.notifications` in `sidechat.py` and the destination predicates in
`notification_ack.py`. Integrate only those changes into the complete latest live
Python package, retaining its private/current additions. Browser and connector
processes cache these modules and need a separately coordinated narrow reload.
Publisher does not call these notification methods and needs no reload. Vibe,
backend, static server, gateway, notifier and coding agents need no restart.
Preserve latest SQLite/read/manual-unread state; rollback changes code/assets only.
No additional persistent security capability or adapter/tool/schema change is needed.

After authorized adoption, use the existing read-only workspace notification
inventory for a target and each sibling, and the browser notification metadata
GET. The target must retain its exact unread message/attention; siblings must omit
that message from their notification inventories while shared history still shows
it. Project messages must appear only in project counts. Do not use mark-read,
acknowledgement or real dispatch as a verification step. Exact operational IDs,
resource receipts and real-note evidence remain in the private owner handoff.
