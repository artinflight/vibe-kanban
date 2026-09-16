# VK::Agent Autoswitch — review revisions complete

This docs-only revision preserves the existing product design and applies the
September 16 review in [VK_AGENT_AUTOSWITCH.md](VK_AGENT_AUTOSWITCH.md).

- Multiple jobs may run concurrently on one quota pool; coordinate only admission.
- CU owns quota reasoning, preferences and admission; VK maps eligible configs.
- Initial delivery includes new work and safe finite-turn continuation. Active
  cross-engine goal transfer is separately releasable advanced work.
- Droid model `auto` is explicit and can share Factory quota with explicit Opus.

The shared CU contract is not yet jointly agreed. Section 13 lists version/binding,
concurrent-admission and active-work safety semantics for the integration pass.
No VK-specific score, raw quota schema or lifetime pool lock may fill that gap.

Next session should begin initial development with contract fixtures, settings,
selection/admission and safe handoffs. The docs-only boundary belongs only to this
pass. No code, tests, schemas, migrations, UI or runtime behavior changed; no goal
was created. Validation and exact pickup status are in HANDOFF.md.
