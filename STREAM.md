# VK::AS::Integration Phase

Docs-only reconciliation of VK autoswitch (`29f99ad75`) and CU multi-provider
allocation. Canonical design: [VK_AGENT_AUTOSWITCH.md](VK_AGENT_AUTOSWITCH.md);
shared contract/handoff: [VK_AGENT_AUTOSWITCH_INTEGRATION.md](VK_AGENT_AUTOSWITCH_INTEGRATION.md).
CU producer docs in `/home/mcp/code/codexusage/docs/agent-autoswitch.md` and
`allocation-contract-v1.md` carry the same revision-2 contract; preserve that
checkout's unrelated dirty implementation. No production code/tests/schemas/UI,
services, goal creation, deployment, commit or push is part of this pass.

CU owns ranked pool availability, atomic multi-permit admission and settlement.
VK owns complete-config mapping, local suitability, parallel launches, expiry
supervision and finite-turn handoff. One pool can back several configurations;
all windows stay within CU. No execution-lifetime pool lock or VK allocation math.
Active native goal transfer and multi-pool charging are explicitly later scope.

Design mismatches are resolved. Activation requires provider identity/live data
and consumption/lag/tail bounds, validated VK independent stop enforcement, and
shared overnight accounting. Future agents can implement independently against
`cu.allocation.v1` draft revision 2 and the integration scenario table.

Validation: repository formatting and ops governance, document link/parity/diff
checks. No runtime/provider/API/deployment validation is claimed. See HANDOFF.md
for exact outcomes. This branch started clean at staging `2fd585ac3`; the autoswitch
design is brought forward from its separate design stream, without its unrelated
continuity files. The docs-only restriction is temporary for this session.
