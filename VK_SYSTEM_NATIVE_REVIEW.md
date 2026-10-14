# System-wide native review preparation

This follow-up starts at fork/staging962d2673f after PR248 integrated the narrow
PR247 decoder compatibility plus PR245 history and PR246 Git checkpoint work.
PR247 is still open but its source is integrated; do not duplicate or merge its
historical baseline. This policy follow-up uses its own concern/PR.

## Verified diagnosis — October14

The active unit is vibe-kanban-combined-20261014.service. Its executable SHA256
is d4d73b39eace69a31d85871c487496ac08de3a62eade63cf4157e9feb18c72f9,
matching the reported release. Native Codex config selects reviewer user; the
DEFAULT profile supplies danger-full-access with no reviewer override. The
separate NATIVE_APPROVE_FOR_ME profile supplies workspace-write/on-request/auto_review,
so it does not enable DEFAULT or existing sessions. T18's two inspected execution
responses explicitly report user/on-request/dangerFullAccess; its current worker
was read only, never interrupted, redirected, approved or changed.

Installed native0.159.2 supports MCP review before human elicitation. Native
source3d2ee51 resolves link reviewer before app, then app default, then session;
changing only the session reviewer is insufficient when overrides exist. Existing
native config has no declared app reviewer overrides, but the implementation must
cover arbitrary apps/accounts rather than only Figma. Private runtime identities,
traces and proposals are under /mnt/vk-storage/vk-system-auto-review-20261014.

## Candidate behavior

Every production Codex executor enables native review for all profiles/projects.
Thread start/resume/fork resolve project-effective native config, set root/app/link
reviewers to auto_review and retain every app/tool enablement and approval mode.
Private configuration responses are suppressed from raw logs because they can
contain credentials. Config-read failure blocks dispatch; there is no unchecked
fallback. Existing raw conversation/history and reviewer decisions are untouched.

Ordinary and feedback turns explicitly pin native reviewer and on-request again.
DEFAULT, Auto and stale Never/OnFailure profiles use on-request rather than Vibe's
unconditional approval path. Read-only remains read-only; other profiles use
workspace-write, with no host-policy fallback to danger-full-access. Native
sandbox establishment failures must fail rather than escalate silently. Mandatory
native human input, URL/authentication, persistent consent and reviewer denials
remain governed by native Codex and the existing Vibe human bridge. No generic
accept responder or command/tool/app allowlist is added. Recommend routing is
unchanged. Sandbox-permitted actions do not acquire a new approval requirement.

Native Codex review is available only to the Codex executor family. Other executor
families do not expose this native reviewer; their own human approval mechanisms
must remain intact and must not be advertised as Codex-reviewed.

## Validation and rollout work

Implementation, exact-head hosted tests/build, native command and connector
acceptance (including stale reviewers, DEFAULT and resume), native refusal and
mandatory-human cases are in progress. No current claim of system-wide activation.
Use mounted SSD artifacts and the approved hosted builder; no heavy Cargo on MCP.

Live security-sensitive policy/profile writes, merging and any service restart
require the user's applicable exact-action authorization. Prepare reviewable
policy edits, source-bound artifacts, backups/current-data rollback and the
normal safe-idle release plan first. Do not interrupt or retask T18 or other work.
Running processes are not silently reconfigured: natural new turns/processes and
resumes must be verified at their actual activation boundary; original-history
seals and fixed-worker authority are never rewritten or bypassed. No new arbitrary
approval gate is introduced by these existing constraints.

## Additional human-boundary coverage

Additional candidate safeguards: native human-only tool fallbacks require an interactive service; Noop cannot approve them. Native permission-expansion requests receive typed, turn-scoped responses through the human approval service rather than JSON null. Guardian enablement is pinned while managed native constraints still fail closed. Actual native/MCP acceptance remains pending the source-bound builder.

## Installed protocol correction

The account-backed MCP preflight found that native config/read emits null optional
app fields. Those are absent/inherited TOML values; passing them through write
overrides produces invalid empty strings. The candidate removes null object
properties only within the app configuration before round-trip, while preserving
non-null enablement/tool approval values and repairing reviewers. The first
preflight failed before any model turn or tool dispatch; it was not blindly
replayed after a billed/uncertain command. An explicit null regression covers it.
