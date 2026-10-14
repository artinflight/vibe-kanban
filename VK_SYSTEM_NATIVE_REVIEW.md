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

Implementation and exact-head hosted tests/build pass at498c84495553f545c97d33529f70d9156087433b.
Native command, connector, permission, refusal and mandatory-human fixtures pass
as described below. Actual DEFAULT and genuine stale-user resume backend
acceptance also pass. There is no claim of live system-wide activation.
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

## Exact test evidence — October14

[Full Test38636787582](https://github.com/artinflight/vibe-kanban/actions/runs/38636787582)
passes572 workspace tests (13 existing skips),12 scheduling-enabled checkpoint
tests (90 unselected), Clippy, schema/SQLx, frontend and Tauri checks. The remote
private-dependency job takes its explicit missing-deploy-key skip.
[Native compatibility38636787508](https://github.com/artinflight/vibe-kanban/actions/runs/38636787508)
passes14 actual JSON-RPC/history/error regressions (one existing skip),12 native
review/policy/human-fallback tests and actual isolated startup acceptance. All2525 exported tracked-source hashes
(including two symlink target-content hashes) and both binary hashes were
independently verified. The initial collector expected symlink link-text hashes;
that receipt error was reconciled read-only without replaying model turns.
Protocol dependencies and Recommend routing remain unchanged.

Source-bound artifact11929960830 contains acceptance server SHA256
5161fa9df9b364c8a9828345c3575c047d7bf634a741038615a4a1b06ba3757b
and executor tests aa4ce26c8d3a2ad0da9fcfb7fa7df3cad1ea9300651da144e16ac661a71acd5b.
The artifact is for isolated acceptance; it excludes the live private reader
overlay and must never replace the deployed package directly.

Installed native0.159.2, the actual runtime wrapper and a real stdio MCP fixture
verified native review start/completion IDs, agent decision source, connector
dispatch/denial and saved effective context. Safe read, marker write and
fresh-process resume pass. An unauthorized nested action is denied before
dispatch; a mandatory nonempty form reaches human elicitation and receives no
automatic response. An existing connected Figma whoami read also succeeds after
a native agent review; no design/customer assets or external writes were used.
The connector fixture is generic, not a Figma tool/name exception.

Separate native command coverage verifies an in-sandbox printf plus reviewed
escalated printf, reviewed apply_patch outside the workspace but wholly inside
the isolated fixture, and a reviewed write-permission expansion restricted to a
fixture path for one turn. The initial permissions attempt found the tool absent;
its receipt stays failed rather than being relabeled. Enabling the actual
experimental request_permissions_tool in a separate fixture exposes it and the
native review passes. The production feature remains at its existing default;
this patch does not expose extra tools to make them testable.

All account-backed evidence remains private under
/mnt/vk-storage/vk-system-auto-review-20261014. Native test homes and workspaces
are isolated by filesystem/PID/IPC/UTS namespaces; credential files are bound
read-only, not copied. No external approval responder is used. A failed null-field
preflight happened before any model turn or dispatch.

## Human cases and coverage limits

Native denials stay denials. Unsupported/mandatory nonempty forms, URL/login/auth
and persistent consent must never be changed into an Accept response; the existing
bridge supports only its declared one-shot tool-consent form and otherwise cancels
safely or leaves the actual native human request unresolved. The ordinary human
approval service remains the fallback when native Codex escalates a decision to
a person. Noop cannot supply human approval. Permission fallbacks are typed and
grant only an explicitly approved request for the current turn. Managed native
requirements remain authoritative and can reject requested reviewer settings.

Verified action coverage currently includes command, apply_patch/file change,
additional permissions and MCP tool consent. The source inventory also identifies
network access, execve and write_stdin review variants; those additional fixtures
are being completed before claiming category coverage. They do not
certify every third-party connector operation, production OAuth/credential
renewal, paid/destructive external actions, other executor families or running
pre-rollout workers. Native Codex accepts sandbox-permitted actions without a
review event; that is distinct from a review decision. Changing a reviewer while
retaining danger-full-access would not provide command sandbox safety.

## Rollout preparation and rollback

Read-only helpers prepare the exact field proposal and audit saved contexts:

- scripts/testing/prepare-native-review-rollout.py emits before/after native
  reviewer/policy/sandbox/guardian/app/link edits and CODEX profile deltas with
  source-file hash preconditions. It does not apply settings.
- scripts/testing/audit-native-review-rollout.py reads only active Vibe execution
  bindings and native turn_context records, bounded even for large history. It
  reports reviewer/policy/sandbox evidence, never conversation text or credentials.

The live proposal currently has six native edits (root reviewer auto_review,
approval_policy on-request, sandbox_mode workspace-write, guardian/stdin-review enablement and
app default reviewer) and one DEFAULT profile edit (workspace-write/on-request).
Existing native/profile files are not changed. A read-only audit found zero
auto_review saved contexts among seven active Codex workers; live activation and
post-activation coverage remain unverified. Do not stop/retask them to fix that.

The native-review Rust delta applies cleanly to deployed source5a5abd2e, with
each modified existing source base matching staging. A separate private source
receipt binds all2524 candidate inputs and verifies all three retained history
reader files byte-for-byte unchanged. The candidate source preserves the live
PR245/246 integration and private reader behavior; private source/receipts are not
uploaded to public GitHub. Its deployment build is blocked by mounted SSD capacity
below the established private builder's >2GiB minimum. No minimum is waived and
no shared output/history/state is deleted.

After capacity is available, use the established fenced private builder, verify
all source/artifact hashes and run copied-current acceptance with the existing
capacity guard, routing module, frontend, continuation/history contracts and
rollback reader package retained. Obtain the user's exact-action authorization
for the coordinated policy/profile edits, merge and immutable package cutover
under the normal healthy-backup/current-data and natural safe-idle workflow.
Do not apply the global settings to the old binary as a partial rollout.

Verify new DEFAULT workers and genuine existing/resumed sessions at their next
natural process/turn boundary, including native review IDs/outcomes and saved
contexts; repeat the read-only audit for remaining stale workers. A restart alone
is not activation evidence. Rollback restores the prior server plus only the
proposal's listed before-values, with fresh precondition checks so later unrelated
settings survive. Preserve the latest database, native history, credentials,
private readers and current-data-compatible continuation/Git checkpoint state.
Do not restore a fixture or historical database, or rewrite native context history.

## Actual candidate DEFAULT/resume acceptance

The acceptance server at498c8449 completed two real HTTP worker executions in
an isolated Vibe backend, plus one genuine no-tool native legacy seed turn.
DEFAULT deliberately supplied stale danger-full-access/never settings and an
explicit reviewer=user CLI override. Native config also supplied root/app/link
reviewer=user. The first DEFAULT Auto command produced approved native review
301fa1ac-29c1-467f-8132-24b6753d2760, matched the executed printf target and exited0.
Raw responses and saved effective context show auto_review/on-request/workspace-write.

The second DEFAULT Supervised execution starts a fresh native process and
resumes a genuinely persisted user/never/danger-full-access fixture thread.
Only disposable Vibe metadata binds that old thread; its native history is
never fabricated or edited. Native MCP reviews46c23531-3507-4078-94f2-73ee507ef231
and784e2fe2-2b84-44ec-84e4-50006a62e5a3 approve the inspect_fixture call, which
dispatches successfully. The same native thread appends an auto_review/on-request/
workspace-write context and preserves its exact original40620-byte history prefix
(SHA256346b4385ea2bbf35de40ed8a4a2d5ac7e857a2046fd2b0ce4df87f5734ee7b76).
This is a fixture integrity assertion, not a replacement for live PR245 seals.

The private receipt backend-system-fixture/backend-acceptance.json records
source, execution/thread/review IDs, native outcomes, sandbox and saved contexts.
Its backend is stopped. Thirteen account-backed root test turns total were used;
no further billed or uncertain probe was retried. Direct native fixtures cover
same-process second turn and fresh-process MCP resume. Current system-wide
policy uses real typed start/resume/fork request tests; the earlier decoder
compatibility acceptance also exercised native fork. An account-backed fork
with this new global policy is not claimed.

## Terminal-input review correction

The category audit found WriteStdinApproval is default-off in native0.159.2:
without it, input to a previously escalated terminal bypasses the reviewer.
The global preflight now pins features.write_stdin_approval=true as well as
guardian_approval; the real typed start/resume/fork peer regression asserts it.
This is within the requested all-tool scope and enables review for an already
exposed tool. Optional request_permissions, network-proxy and zsh-fork tools
remain at their configured exposure; their approval paths inherit the native
reviewer when enabled. The new correction needs its own exact-head compiled
evidence;498c8449 CI does not certify this later change. Three additional fixture
turns are bounded for network, execve and actual-candidate terminal input
(maximum16 root turns total). No external connector write is added.
