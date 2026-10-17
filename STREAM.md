# Issue context for connector-created Dot Chat workspaces

Branch `fix/dot-workspace-issue-context`, based on current fork/staging.

Repair the reported standalone workspace through supported issue creation/link
routes, keeping its identity, branch, worktree and complete history. Prevent new
connector starts without verified issue/project context. See
[the repair and creation contract](DOT_WORKSPACE_ISSUE_CONTEXT.md).

The live issue association, browser HTTPS route and actual cached connector
lookup/history are verified. A real owner message arrived afterward. Do not
answer or start another task merely to demonstrate the repair. Preserve private
account details, sessions, grants, subscriptions, CU/Stop/follow-up pins and other
owners' work. No Vibe/backend/agent/frontend restart or new worker is authorized
by this source stream. The connector-only guard is live at source 4a5674de3;
only its process restarted. The live negative start probe was rejected by review
and was not retried; see the exact validation limits in the protocol handoff.

Full prior notes remain in [STREAM history](STREAM_HISTORY_20261017.md).
