# Workspace Attention Preservation

## October 2 Correction

The October 1 readiness answer incorrectly compared issue/task statuses with
the workspace sidebar's Needs Attention state. Those are different data: the
sidebar uses coding-agent turn `seen` flags and live execution/approval state.
Matching issue counts did not prove the operator's unread markers survived.
The agent also stopped with the display discrepancy unresolved, so its goal
completion claim was not supported by complete acceptance evidence.

Same-day backups prove that completed-turn unread flags became read. The UI
called the workspace-wide seen endpoint on provider mount, including when a
mobile workspace's chat was hidden. That is a demonstrated unsafe behavior,
not evidence identifying the requester of every historical flag change.

Separately, the sidebar paginated before grouping, hiding actionable older
workspaces beyond its first 50 items. A read-only browser check that blocks
every POST also blocks the read-only summaries request and cannot establish
that attention/running state hydrated correctly.

## Corrected Behavior

Opening a workspace does not mark its turns reviewed. The existing workspace
actions menu now has an explicit Mark reviewed command. Mark unread remains
available. Running, pending-approval, unread and active/unresolved-subagent
items remain included in the accordion even beyond the initial history page.
Search, flat-list pagination, sort order and archived history stay unchanged.

## Recovery And Acceptance

Recovery matches original completed turn IDs from checksum-verified same-day
backups and changes only missing `seen` flags. Compare-and-set checks preserve
concurrent changes and exclude archived workspaces and interrupted executions.
Back up the before-state and repair receipt to Desktop B: before mutation.
Never restore a historical database over current production.

Verify attention flags independently from issue statuses, goals and execution
history. Allow POST `/api/workspaces/summaries` in read-only browser checks,
while blocking real writes. Exercise the real desktop sidebar and mobile Wksps
tab, including an older unread item beyond the first 50, and prove navigation
does not send a seen request. Exercise explicit review only on isolated data.

Publish the validated frontend to both the active release and the prepared
cutover/cutback release. Preserve old hashed assets and an index rollback copy.
Refresh bound frontend hashes, source-overlay evidence and Desktop software
recovery before declaring the next cutover ready. Old open browser tabs must
reload to use the corrected frontend; they still contain the old auto-clear
code. No backend restart is required for this correction.

Local artifacts: `/mnt/vk-storage/vk-attention-recovery-20261002`.
Desktop recovery: `B:/vk-backups/vk-attention-recovery-20261002`.
