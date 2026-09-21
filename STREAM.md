# Consolidated overnight capacity workflow repair

User request: fix all identified workflow failures and validate the integrated
backend before another production restart. Production restart is not authorised
for this stream. Target fork staging; do not collide with other active agents.

Scope: native-goal readiness and identity validation before permission; same-goal
manual takeover preserving selection; foreground admission before executor slot
allocation; active-turn send route takeover; durable launch-failure reasons.
PR121 wire-status fix is included in the base. CU companion branch provides
persistent activity history and specific unavailable-goal reasons.

Validation uses an existing one-session, credential-free isolated HTTP fixture,
installed native Codex with local deterministic provider, real systemd guards,
and the CU scheduler with synthetic quota. See CAPACITY_WORKFLOW_AUDIT.md.
