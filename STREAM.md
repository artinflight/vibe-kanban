# Scheduled goal resume status correction

Scope: fix the September 21 overnight rejection of an unfinished native goal
whose app-server status is `usageLimited`. VK previously compared against the
SQLite spelling `usage_limited` and reported a false need for user involvement.

Use the captured goal/get wire response in a regression test. Keep actual
checkpoint input requests, completed work, token-budget limits, blocked states,
identity checks and execution leases enforced. Distinguish rejection reasons.
No manual-takeover redesign, production goal mutation or VK restart in this stream.

Target: artinflight/vibe-kanban staging. Deployment requires an operator-managed
backend build/restart; this source fix does not update the running binary.

Validation complete: 74 executor tests passed, three environment-dependent native
fixtures ignored. Captured usageLimited wire regression passed. Backend rollout
and a bounded live scheduled run remain unperformed.
