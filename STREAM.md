# Dot existing-conversation follow-up repair

Branch: `fix/dot-sidechat-followup-context`, based on current fork/staging.

Investigate the reported uncertain voice-to-main delivery without repeating
Staging, Nightly or Disk Space actions. Repair the owned gap between an already
answered sidechat request and a later promised update. See
[the protocol/evidence boundary](DOT_FOLLOWUP_DELIVERY.md).

Scope: Python sidechat, additive existing-status lookup, focused tests and
sanitized handoff. Preserve Project Sidebar, Mobile, Steering, Dot attention,
artifact delivery, CU1.6, Stop and all access/subscription/session state. Frozen
PR264 and other owners' worktrees are untouched. No frontend/Cargo build, new
actor, agent execution, model/routing/permission change or Vibe restart.

Live: functional source 831cd88d9, connector-only adoption at 23:04 UTC. Actual
cached lookup, exact-thread update, same-key retry and readback passed; one new
unread reply and no owner event. Desktop B before/after preservation verified.
Voice client identity/platform parent receipt and unattended monitoring wake
remain unverified. See PR270 and the protocol handoff for exact boundaries.

Full prior branch notes remain in [STREAM history](STREAM_HISTORY_20261017.md).
