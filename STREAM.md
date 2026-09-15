# VK::Agent Autoswitch — design complete

This branch contains a docs-only design pass for automatic agent/model switching.
The implementation contract is [VK_AGENT_AUTOSWITCH.md](VK_AGENT_AUTOSWITCH.md).
Reuse ExecutorConfig and existing execution/continuity paths; CodexUsage remains
the sole usage/allocation authority. The design covers shared pools, reset-aware
pacing, manual precedence, linked-session handoffs and native goal ownership.

No production code, tests, schemas, migrations, runtime configuration or UI were
changed. No deploy, preview, commit or push was performed by this pass.

Next session: begin development from latest staging and reconcile CodexUsage's
in-progress working tree. Implement the CU routing snapshot, VK selector/settings,
then safe session and goal transfer. The docs-only restriction ends with this
pass; it is not a permanent project constraint. Factory telemetry/model access and
native quiescence are activation gates documented in the design, not reasons to
restart general design. Validation results are in HANDOFF.md.
