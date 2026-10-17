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

Pending: exact candidate/runtime preservation and actual registered path
acceptance. Voice client identity and platform parent receipt remain unverified.

Full prior branch notes remain in [STREAM history](STREAM_HISTORY_20261017.md).
