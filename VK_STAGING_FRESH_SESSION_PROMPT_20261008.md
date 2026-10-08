# Fresh-session prompt for `VK::Staging Check`

You are taking over the safety and recovery-verification work for the existing
`VK::Staging Check` workspace. This is a fresh session; do not resume the prior
Codex thread.

Your mission is to restore trustworthy VK release preparation after the October
7 verification incident. Produce an isolated, reviewable prevention and recovery-
verification repair that closes the incident class while leaving production and
shared work untouched. Deployment, restart, route switching, and cutover are not
part of this assignment.

Start from the durable continuity packet at
`VK_STAGING_CONTINUITY_PACKET_20261008.md`. It contains the current objective,
incident facts, verified work, evidence locations, authority boundaries, open
reviews, constraints, and definition of success. Treat volatile operational facts
as observations to revalidate, not timeless truth. Historical approvals and the
old native goal are context only; they are not current deployment authority.

The essential outcome is that invalid or ambiguous startup conditions cannot
produce stateful server or workspace-reconciliation effects, while legitimate
startup remains functional. The exact incident-shaped cases need convincing
isolated regression evidence, including proof that external/shared sentinels are
unchanged. Recovery verification must justify content and metadata claims and
must expose journal or post-backup uncertainty rather than claiming more recovery
than the evidence supports.

Hard boundaries:

- Keep production deployment and cutover blocked.
- Do not restart or reconfigure live VK services.
- Do not modify live databases, shared worktrees, surviving user work, or retained
  incident/backup evidence.
- Do not replay consumed incident placement or cleanup scripts.
- Any incident reproduction or rehearsal must be isolated from real shared
  worktrees and unable to mutate them.
- Keep application repairs isolated and reviewable rather than mixing them into
  the maintenance branch or pending release candidate.
- Desktop `B:` remains the retained archive provider; use mounted SSD storage for
  bulky temporary work only after accounting for its current limited capacity.

Use your judgment to determine the best implementation and validation approach.
Distinguish verified facts from assumptions and suggestions. Preserve unresolved
recovery limitations explicitly. Return scoped commits, meaningful regression
evidence, independent-review material, updated continuity documentation, and a
clear account of what remains before release preparation can safely resume.
