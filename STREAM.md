## October 10: bounded capture/consent pair — preparation only

Current production backend is c3c48e6324f778ccd03a5761c2314b440e9ceac3;
actual served frontend source is 5ce84ee21be814b1519cfb2715b50f3432c3e8ba.
This isolated candidate starts at the latter (backend identical to c3), and
applies only the reviewed source/test hunks of PR236 and PR239. No historical
branch merge, production action, security/configuration change or live review
receipt is authorized/performed by this preparation. See
VK_COMBINED_CAPTURE_CONSENT_20261010.md and
handoffs/e3e1-combined-capture-consent.md for the current release boundary.

## October 8 authorized safe restart — preparing, not ready

Read VK_SAFE_RESTART_PREPARATION_20261008.md. Latest operator authority permits
safe restart/cutover after fresh gates; historical recovery acceptance is not
implied. Combined source includes the four exact PR pins atop the already-live
phone baseline. SSD capacity/restore rehearsal, identity/controller binding,
writer drain, Git policy/prerequisites and live consent acceptance remain gates.
No production restart, route switch, writer interruption, cleanup or security
setting change has occurred. Recommend and usage controls stay unchanged.
Recovery exceptions and completed independent-review verdict remain explicit.

# October 8: Phone frontend deployed

The operator-approved phone redesign/style pass is live at `https://vibe.local`
following rebase merges of PR224 into staging and PR226 into main. Production
frontend source is main `22f09e245`; its entire tree matches clean build source
`bdf6346d3`. Read VK_MOBILE_RELEASE_20261008.md for hashes, backup, activation,
regression coverage and remaining limits. Earlier preparation/no-deploy entries
below are historical.

At 17:41 UTC, an atomic directory/symlink exchange activated
`/mnt/vk-storage/vk-mobile-release-20261008/release/frontend` at the actual runtime
frontend path. The general `frontend-dist/current` pointer also resolves there.
The prior directory and hashed assets remain available. Backend service
`vibe-kanban-green-production-20261005.service`, PID 3027197, binary, database,
route 5511/5512 and execution/routing configuration were preserved. No restart
or inference request was made; Recommend-only and configured model/effort remain
unchanged. Future backend packages must retain this new frontend source/assets.

Candidate and live Chromium acceptance passed at 360/390/412/1440px and 390px dark,
including project/task/workspace navigation, state/Back, conversation reading,
composing, local attachment simulation and keyboard viewport geometry. HTTPS
asset hashes, 12 saved messages, 16 active/27 archived project order, configuration
and backend identity matched. Full implementation/promotion CI, production build,
format/governance checks passed. Physical Android keyboard/browser chrome,
Safari/Firefox and production write/drag/queue/review mutations remain unverified.

Rollback archive SHA256 is verified locally and on Desktop at
`desktop:B:/vk-backups/vk-phone-frontend-20261008/frontend-before.tar.gz`. This
artifact-only rollback preserves current application data; no full mutable-state
backup/restore or backend continuity rehearsal was performed. Evidence and
rollback commands are under `/mnt/vk-storage/vk-mobile-release-20261008`.

# October 8: Phone screen redesign

Branch `vk/eb7d-vk-native-feelin` replaces the initial size-focused mobile pass
with dedicated task-feed, workspace-list and compact conversation layouts.
Status/activity chips, clear titles, a thumb-level New task action and progressive
disclosure replace stacked panels, nested cards and persistent composer toolbars.
Retain history-aware sheets, feed/draft/search state, safe areas and visible
viewport behavior. Desktop and configured execution model/effort stay intact;
model routing stays Recommend-only. No merge or deployment is authorized.
Read VK_MOBILE_UX.md for the current design and validation.
Review: [draft PR #224](https://github.com/artinflight/vibe-kanban/pull/224) into
`staging`. Historical entries below do not define this stream.

The follow-up style pass reduces search/chip visual bulk while preserving 48px
input/control targets. Search icons, lighter surfaces, aligned 24px headings,
softer card borders and tighter row spacing refine the new phone layouts.
Style evidence is in `/mnt/vk-storage/vk-mobile-style-20261008`.

## October7 historical-log and CI compatibility repair — isolated

The isolated review candidate now explicitly validates deployed goal-cleared and
sleep lifecycle notifications missing from its pinned SDK, with sanitized real
historical-format and damaged-variant coverage. CI fixtures require debug assets
in their compiled checkout, optional exact-root binding, and SSD storage on MCP;
the host-installed connector test runs separately and explicitly. Narrow error
return types resolve the two new Clippy failures without lint suppression.
Strict file/hash/writer-closure, receipt/hold/lifecycle guarantees remain intact.
See VK_CONNECTOR_COMPATIBILITY_20261007.md for exact acceptance and limits.
Staging/production, live receipts and badges are untouched; root owns integration.

## October7 connector candidate repair

Isolated branch fix/e3e1-review-log-integrity starts from combined eacafb3a1.
Staging combined source is untouched. The repaired candidate needs release-owner
integration/acceptance; no production restart or automatic delivery claim.
See VK_CONNECTOR_REPAIR_20261007.md.

# October 7 Combined Release Preparation

Connector candidate13a3458eb is now received and applied for review, not accepted
for deployment. Read VK_CONNECTOR_INTEGRATION_REVIEW_20261007.md. The combined
Rust compile found and corrected the inspect deadline call mismatch. New
deletion/closure regressions block readiness; no staging/main/live change.

Integrate only reviewed PR1479b3f82538 and PR148cb0b441a2, with compatible
CU95e7aea47. Await the reviewed connector backend handoff before final build,
combined acceptance or promotion. Conditional cutover authority requires proven
space, fresh backups, full appropriate restore/latest-v2 rollback and an actual
safe-use/drain check. No active agent may be interrupted to accelerate delivery.
Retiring the27 local archive duplicates requires separate specific approval.
Development histories below describe their branches, not a production release.

# PR147 bounded stop-response reliability

The complete graceful attempt has a 2-second deadline, including mutex, RPC,
log and exit-signal awaits. Independent OS stop and cgroup verification follow
regardless of graceful outcome. HTTP worker stops run concurrently: 2+3+2 seconds
per worker, with bounded controller lock waits, within CU's 10-second request
budget for two workers. Unverified exit retains stopping grants and first-run
holds/identities/receipts; native active status is never fabricated as paused or
used as replay permission. Lease and hard-stop enforcement remain unchanged.

Focused isolated regressions cover thread/log/exit-signal stalls, actual one/two
native workers, unverifiable exit and independent lease expiry. Original authentic
promotion/later resume remain mandatory. Final-source CI/artifacts/evidence and
staging's exact remaining CU/HTTP/rollback acceptance are recorded in
`/mnt/vk-storage/vk-scheduled-first-run-20261006/stop-response-handoff.md`.
Previous evidence remains preserved in stalled-stop-handoff.md. Independent
review at 22034d9b6 cleared observed worker containment; original revoke-write and
last provider-request timestamps remain unavailable. No runaway claim is made.
No production deployment/restart, Android/provider use, settings change or cleanup.
Keep Recommend and deploy compatible CU before exposing pending candidates.

# October 6: Scheduled native first run

Branch `vk/fa60-vk-scheduled-goa` starts at fork staging `8b562265d`.
Read VK_SCHEDULED_FIRST_RUN.md for the pinned CU contract, provenance, isolation,
wire interface, combined acceptance and rollback requirements. No production
deploy/restart/settings writes, real Android initialization or paid inference.
Pending exposure is default-off and belongs to the later staging rollout after
CU compatibility. Recommend is preserved. Local development checks listed below pass; combined CU/private-HTTP acceptance
and rollout remain with the parent/staging owner.

Validated on the final offline binary SHA-256
`a854d6158f061d8fa60c14f5badfbf6cbe0b99b5f5036eccd16b1c0775f6c787`:
155 executor unit tests; six real-native offline scenarios (authentic first
turn/promotion/later resume; required input hold; one-request provider failure;
identity changed after lease preparation rejected before model work; plan review
hold; completed first turn without a checklist held without promotion). All used
the reviewed CU kernel/supervisor boundary and zero host-workspace mutation
attempts. Receipts: `/mnt/vk-storage/vk-scheduled-first-run-20261006/acceptance.json`.
Focused executor/server all-target Clippy, frontend type checks/lint, formatting
and ops checks pass. Broad check/lint are blocked by missing host GTK/GLib/GIO;
full workspace tests and shared-generation checks remain CI requirements. No
remote source paths changed. No unrestricted fixture backend was run; the
CU/private-capacity-HTTP combined rehearsal and legacy-CU/durable rollback
acceptance remain explicit release requirements in VK_SCHEDULED_FIRST_RUN.md.
No backend release package or production restart was attempted.

# October 7: correct the incomplete no-restart boundary

Current branch `fix/autoswitch-current-step-risk` retains the earlier source and
PR148. The prior delivery failed the requested no-restart classification scope:
fixed backend prompt/history rules vetoed updated worker policy. Internal protocol
2 now separates immutable repository/native/lifecycle facts from replaceable
prompt classification and inferred history. All normal classification, semantic
eligibility and manual-history inference use one pinned module. See
[VK_AUTOSWITCH_RELOAD.md](VK_AUTOSWITCH_RELOAD.md).

Development only: Recommend, actual model/effort, credit settings, active module,
service and staging/main remain unchanged. No owner coordination or deployment.
One VK::Staging adoption of matching backend/validator/worker protocol2 is required
to remove the old veto; subsequent policy fixes use prepare/publish without
backend restart. The old `current-step-665d836db-20261007` artifact is superseded,
not deleted. October30 (20x→10x) remains the usefulness/readiness deadline.
Current checks/package receipts: `/mnt/vk-storage/vk-autoswitch-module-boundary-20261007`.
Implementation `09dcd2cb2d873139904d32821bbc0924cdeabfac` is pushed; the
final delivery also adds the omitted-input safety check and this evidence.
Final executor unit suite: 156 passed, seven opt-in tests not invoked. All-target
executor Clippy, formatting/governance and byte-identical CU contract/fixture pass.
The sandboxed reload proof (`reload-final-proof.log`) kept PID3305974 unchanged:
negative deployment wording and history policy updated through real worker
publication, actual model selection changed, all 15 captured real assessments
passed (three corrected to Sol6/low, twelve unchanged), manual/Recommend behavior,
child floors/escalation, rollback and dirty state survived. Six rejected-update
cases include old protocol and an unsafe all-cheap worker. Native inference: zero.
The subsequently added full-input budget guard passed its dedicated regression
in the final 156-test suite; the same-process test is not a live production trial.
Observed helper stages were 18/7ms, not a production latency guarantee.
An initial expanded-suite run hit its obsolete whole-suite ten-second assertion;
the test now verifies prompt termination of the deliberately stalled helper
instead. Final behavior/timeout assertions pass. No failed receipt was removed.

Fresh package preparation, private publication/check/render pass for protocol2
`policy-boundary-v2-20261007` under the task root's `package`; worker SHA256
`039a9ebb5e625a9bff871f2560a27a39efa36a62d4378ca0c38e512ad5901629`, manifest
`3edec4e9c4e5b202c4718dcc85977063fd0603bb67a79cd5b94afac69390f7f1`.
It is a stripped development-profile helper, not an installed production server.
Normal candidate packaging may rebuild optimized artifacts from the same source.
The old validator was tested only as a copied private artifact and rejects the
new preparation clearly; no live validator/pointer was replaced. Rendered config
was not installed. `DELIVERY.json` binds final source and paths after commit.

Full check/lint/workspace-test commands were attempted; local frontend checks pass
with the larger Node heap, but desktop/workspace Rust is blocked by missing GLib/
GObject development metadata. All ten CI checks passed for implementation09dcd2cb2, including full backend tests,
schema and desktop checks. The final input-budget guard/documentation commit
requires its own fresh CI; read final head status from GitHub rather than using
this earlier result as exact-head acceptance.
Live Green remains PID3027197, started October5 15:33:08UTC, old protocol1 module
`reference-lookup-bb5fe5f40-20261005`, Codex0.159.2; exact read-only identity is in
`LIVE_IDENTITY_UNCHANGED.json`. Recommend/model/credit/runtime settings are intact.
No staging/main integration, deployment, restart or other-agent interaction.

Remaining readiness: release CI and owner adoption of the matched boundary once,
then real Recommend evidence, protected cases, classifier overhead and total
accepted-task quality/usage before October30. Ordinary policy corrections after
that adoption use module prepare/publish, not another backend restart. Auto needs
separate authorization. [PR148](https://github.com/artinflight/vibe-kanban/pull/148)
includes unchanged PR146 prerequisites; do not adopt both as separate releases.
Safe source remains `/mnt/vk-storage/vk-model-autoswitch-20260930/source`; the
recreated managed checkout was not used or overwritten. Older entries below are
historical.

# October 7: AutoSwitch current-step risk correction

Branch `fix/autoswitch-current-step-risk` preserves `fix/autoswitch-reference-steps`
at `bb5fe5f40852d48dfa0049c1fd797ee829ff1265`. See
[VK_AUTOSWITCH_CURRENT_STEP_RISK.md](VK_AUTOSWITCH_CURRENT_STEP_RISK.md).
Scope: release inferred session protection for positively classified, resolved
bounded follow-ups; retain the surrounding assignment for generic resumes;
recognize explicit deployment/restart prohibitions without erasing positive
protected operations. The stable module validator now requires native bounded
scope evidence, and agrees with built-in independent-request handling.

Recommend remains required; no Auto, credit/model configuration, deployment,
restart, live module publication or staging-owner interaction is authorized here.
This changes backend safety guards, so it requires backend-matched adoption by
VK::Staging; publishing only the worker to the old backend would fail closed.
The October 30 readiness deadline (20x to 10x allowance) remains authoritative.
Validation: 153 executor unit tests passed (seven opt-in tests not invoked),
15 completed real assessments replayed without inference, sandboxed module reload
and all-target executor Clippy passed, formatting/governance and exact CU wire
compatibility passed. Three prior Astra recommendations become Sol6/low; their
Auto-qualified option is Luna6/medium. The other twelve are unchanged. No actual
model changes or accepted-task savings are claimed. Frontend type checks passed
with the larger Node heap; full desktop/workspace checks require CI because the
host lacks GLib development metadata. Receipts:
`/mnt/vk-storage/vk-autoswitch-current-step-risk-20261007`.
Delivery: implementation `665d836dba44dcd1af9244992e2656745d15641e` is committed
and pushed. [PR148](https://github.com/artinflight/vibe-kanban/pull/148)
targets staging and includes unchanged PR146 prerequisites; integration CI is
pending. The matching prepared module `current-step-665d836db-20261007` and
validator are in the task's `package` directory; `DELIVERY.json` records hashes.
They are not published live. Staging/main are unchanged. Adopt the backend,
validator, worker/instructions and existing native adapter together. A worker-only
hot update cannot implement this stable safety-guard correction.
Older entries below are historical.

# October 5: AutoSwitch reference-step and classifier startup correction

Current branch `fix/autoswitch-reference-steps` begins at staging `8b562265d`.
The no-restart module is live on October5 Green PID3027197/port5511, source
`a661a8156`. See VK_AUTOSWITCH_REFERENCE_STEPS.md. Scope is a hot module fix
for known-link presentation plus a classifier-only config metadata adapter for
the existing native launcher. Native config exceeded the current reader limit;
ordinary agent frames and authoritative restrictions/settings/usage remain intact.
Live publication and old-core sandbox verification passed without restart;
backend PID3027197 is unchanged. Release `reference-steps-aac5bd457-20261005`.
The known-link replay admits Luna6/medium (Recommend: experimental Sol6/low).
One formerly failed native classifier replay now completes on Luna5.6/low;
4,711 input/259 output tokens and9,823ms, no retry. Ambiguous work stays Astra.
56 routing regressions and three adapter tests passed; no net savings claim yet. Publication/turn receipts
are retained outside Git under `/mnt/vk-storage/vk-autoswitch-reference-steps-20261005`.
No restart, cutover, Auto enablement or staging-owner coordination. Recommend stays
required; complete useful routing deadline remains October30 (allowance20x →10x).
Older entries below are historical.

## October 8 targeted recovery investigation — partial recovery verified

Read VK_TARGETED_RECOVERY_FINDINGS_20261008.md and its exhaustive evidence.
132/145 exact original commit objects are preserved only in new isolated Desktop B
object databases; 129 graphs are hash-verified within their declared scope.
VK uses its authenticated original shallow-history boundary. Only 26 rows meet
original identity plus remote-witness criteria; 119 remain unresolved for coverage.
All 448 names remain unknown; 59 same-name candidate copies cover 13 names and
are not proof of original bytes or retirement. 14,382 captured metadata headers
and three source mode bits were recovered; later states/ownership remain unknown.
The initial journal is now Desktop-authenticated; its lifecycle limitations remain.
Eight archived transcripts retain the same malformed line; no intact suffix found.
Native Desktop Git fetch is blocked by wincredman/disabled credential prompts;
no route/credential bypass. Two VK bundle imports failed prerequisites and remain
explicit. Shared/live trees, workspaces, runtime and original backups are untouched.
New findings are parent-verified, not a duplicate or extension of the Astra review.
Recovery-complete/zero-loss acceptance remains withheld. Request additional
original-object/lifecycle evidence or a decision on enumerated residual unknowns.
No restart/cutover/merge/cleanup/permission change; cleanup still needs human QA.

## October 8 recovery evidence correction — sign-off withheld

Read VK_POST_BACKUP_RECONCILIATION_20261008.md. The earlier blanket claim that
all 710 candidates were accounted for is withdrawn. Parent checks authenticate
the two retained Desktop packets, individually bind 14 accepted patches and the
rejected patch, match 11 replayed files and compare all 15 recovery files.
The checker now fails overall on the preserved transcript parse error.
Only 228 of 676 absent Hyrox names have baseline/08:53 evidence; the other 448
have no baseline content and cannot be certified as later-retired. The subsequent
investigation recovered 132 exact originals in isolation;
13 remain unfound and 119 rows still lack verified remote witnesses. See
VK_TARGETED_RECOVERY_FINDINGS_20261008.md for the current exhaustive accounting.
The separately authorized Astra High
review completed at 13:59:52 UTC and independently substantiates the corrected
bounded findings; recovery-complete/universal-zero-loss sign-off is withheld.
See VK_INDEPENDENT_RECOVERY_REVIEW_20261008.md for the copied redacted report,
448-row list, source manifest and historical investigation plan, now executed.
Earlier blocked delegation receipts are historical; no duplicate review or
routing change is needed.
PR223's remote commit and 11 checks are verified; the c31a workspace's absence
around 12:40 is operator-reported and its cause unknown. No workspace recreation
or incident-loss inference is authorized. Production/shared work remain untouched.
The operator subsequently authorized isolated recovery from retained sources.
No live placement, restart, cutover or cleanup. Cleanup requires Seamus human QA.

## Current repair acceptance

PR153 sourcea81d46e92 passes all10 checks and405 Cargo tests (7 skipped),
including16 real-server cases under private namespaces. The repair is unmerged;
independent review supports the bounded findings, with recovery-complete
acceptance withheld. Production and the maintenance worktree are
unchanged. See VK_STARTUP_RECOVERY_SAFETY.md. No deployment authority is implied.

## October 8 startup/recovery safety repair

Branch fix/startup-recovery-safety-20261008 starts from fork/staging8b562265d.
Scope: strict invocation rejection, pre-start runtime identity pins, preservation
of ambiguous worktrees, read-only recovery verification and isolated regressions.
See VK_STARTUP_RECOVERY_SAFETY.md for contracts, evidence and validation gaps.
No changes to maintenance, PR149/150/152, production, routes or services are in scope.
This branch remains a draft until independent review and real isolated acceptance.

# October 8: PR223 P1 preservation review corrections

Review baseline `3cb3632897a5081224fd45d39b3cf7d772937709` was unsafe: replacement
refs and binary diff attributes hid secrets from scanning, and retries overwrote
original-head obligations. Nine targeted regressions reproduced these and related
failed-admission/legacy-receipt gaps before the fixes, with the approved real
Gitleaks executable exercised on replacement refs, attributes and same-turn retry.

The correction scans raw original blobs and commit messages using Gitleaks stdin
under the publication Git environment, bypasses local attributes/drivers and
legacy grafts, and preserves an append-only original-commit ledger across retries
and failed admissions. Generated commits have write-ahead obligations. Fresh
checks rescan original bytes and reject schema-1 or incomplete receipts. Missing
or unverifiable originals remain blockers and cannot become acceptable exclusions.

Validation on the corrected source: the complete 72-case fixture suite plus one
additional positive real-scanner publication/check test passed (73 distinct tests,
15 configured with approved Gitleaks 8.30.1; none skipped). Four focused Rust tests,
all-target focused Clippy, repository formatting, ops governance and branch policy
passed. Fresh fork/staging ancestry was checked without operating its workspace.
Frontend type checks and local-web/UI lint passed; full check/lint/workspace tests
were attempted and stop at missing host GLib/GObject/GIO development libraries.
Trailing remote-manifest/I18n checks and copied-data full executor/UI acceptance
remain unverified. Logs are in the review evidence directory named below.
Approved scanner SHA256:
`88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509`.

Tracking and delivery remain VK Dev T48 and [draft PR223](https://github.com/artinflight/vibe-kanban/pull/223)
on `feat/turn-git-preservation`. Review evidence is in
`/mnt/vk-storage/turn-git-preservation-review-20261008/`; the final external
`publication-receipt.json` records the exact development remote SHA after push.

No live activation, Staging workspace/runtime operation, restart, recovery,
cleanup, merge, force push, permission or network change was performed.
Recommend-only remains required. Seamus owns controller/package integration and
separately authorized Staging adoption. The controller consumer must require
schema 2 and a fresh check under its complete inventory and held writer fence.
Old receipts need explicit original-history reconciliation; do not auto-migrate
or delete them to clear the gate. Copied-data executor/UI/stop timing acceptance
and full CI remain rollout requirements.

# October 8: Automatic turn Git preservation — development only

Branch `feat/turn-git-preservation` starts at fork/staging
`8b562265d25a3f8ee6d4fa602144e71caddfbc85`. Read
[VK_TURN_GIT_PRESERVATION.md](VK_TURN_GIT_PRESERVATION.md) for the complete
publication/privacy policy, exact-history receipt and fail-closed controller
contract. VK Dev T48 / `783c983a-416e-43f5-9754-8c2f619e9918` is linked to workspace
`c31ac191-d4cf-4ab9-b3e8-9c1a7d7c3b73`. The fork disables GitHub issues.

This is opt-in source development. No config is installed and production
enforcement is not active. Seamus owns Staging integration, installation,
controller wiring, restart/cutover and copied-data/live acceptance. The separately
stopped Staging conversation/workspace/runtime was not operated. Recommend-only
routing remains required. No merges, auto-merge, cleanup, incident recovery,
visibility/permission changes or force pushes were performed.

Development delivery: [draft PR223](https://github.com/artinflight/vibe-kanban/pull/223)
into staging. Initial implementation commit `021b12a9160c8c988dde862758ad43c7da337bdf`.
Final remote coverage is independently checked after the documentation/link commit;
see the private `publication-receipt.json` in the evidence directory. This is
source delivery, not activation or production acceptance. The workspace's stored
branch label remains `vk/c31a-vk-git-sync-enfo`; the actual isolated development
Git branch and PR head are `feat/turn-git-preservation`. Do not promote the stored
legacy label or the separately stopped Staging workspace.

Local validation: all 40 isolated Git fixture tests passed, including real
Gitleaks acceptance and push/PR uncertainty, exclusion, original-history,
concurrent-writer and stale/newer-turn coverage. Four focused Rust tests passed,
including the embedded helper and owned process-group fixtures. Focused
all-target Clippy, formatting and ops governance passed. Local Git ancestry
confirms the branch contains freshly fetched fork/staging; branch policy passes.

Frontend type checks passed with Node's heap raised to 8 GiB after the initial
default-heap failure. Local-web/UI lint passed. Full `pnpm run check`,
`pnpm run lint` and `cargo test --workspace` were attempted; host GTK/GLib/GObject/GIO
libraries are missing, so broad desktop/backend validation and trailing
remote-manifest/I18n stages remain incomplete. Generic CI must provide that
coverage. No native provider inference, copied-data full executor/UI acceptance
or production acceptance was performed. Shared Cargo target/incremental policy
was retained; fixtures, dependencies and logs used mounted SSD storage.

Evidence: `/mnt/vk-storage/turn-git-preservation-20261008/` (fixture-tests.log,
cargo-tests.log, focused-clippy.log, format.log, ops-check.log, check.log,
lint.log and workspace-tests.log). Seamus's rollout outcomes are in the contract
handoff: matching protected backend/policy/scanner/state packaging; complete
controller inventory and real held writer fence; copied-data visible pending,
blocked, successful and stop/cleanup timing acceptance; separately authorized
Staging integration/live adoption. No Staging message was sent or conversation
resumed. Desktop prompt guidance was read through established SSH access.

# October 8: MCP approval bridge

Scope: route supported empty-form Codex MCP tool elicitations into Vibe approval,
return typed results, preserve explicit consent and truthful origin diagnostics.
Linked issue/workspace: VK::MCP Approval Bridge. Development tests and draft PR
only; no deployment, restart, recovery, permission changes, production resumes
or Staging-agent operations. See VK_MCP_APPROVAL_BRIDGE.md and current HANDOFF.md.
Current correction is limited to PR225 comment6063071315: reject nested
redaction-only invocation context after sanitization and add compiled Rust
regressions. Independent re-review closed the original P1 findings at `da07a5c3b`.
Same draft, no broader redesign, merge or live activation.
Older entries below are historical and belong to other streams.

# October 5: AutoSwitch reloadable module

Development branch `feat/autoswitch-reload-module` starts at staging `6af55a461`.
See VK_AUTOSWITCH_RELOAD.md. The next restart candidate must include this backend
hook, a published module and its verified service setting; backend-only adoption
will not activate reloads. VK::Staging owns installation/cutover/live acceptance.
Recommend remains required; no Auto activation is authorized. Full useful router
readiness is due before October 30, 2026 (allowance reduces 20x to 10x).
Remaining dependencies: CI/integration, owner adoption, one genuine complete V2
Recommend acceptance with native/CU/child attribution, practical cheaper-step
corrections and net usage/quality evidence. CU expiring-credit budgeting remains
separate in issue `0aeb028e-2856-40c3-943b-aacf32ec4808`.
Older entries below are historical and do not describe this delivery's scope.

Local development validation passed: 55 routing regressions (one existing opt-in
native test not repeated), the opt-in real-worker reload/admission test, executor
all-target Clippy, formatting/governance and unchanged CU contract/fixture.
The reload test stayed in one PID; code/prompt/model-policy/classifier-settings
updates affected subsequent admissions, manual/Shadow choices and child floors
remained authoritative, failure fallback/rollback preserved the dirty sentinel.
The observed initial before/after helper stages took 33/18 ms in the latest run;
this is local timing, not a production guarantee or savings measurement. No paid
inference was performed. Generic CI/staging integration and owner live acceptance
remain release dependencies until their receipts are recorded.
Prepared initial package: `/mnt/vk-storage/vk-autoswitch-reload-design-20261005/package`;
rendered next-candidate setting: adjacent `candidate-autoswitch.conf`. No service
file was installed. The read-only current-production readiness check correctly
rejected the absent module setting; live backend PID1369037 remains unchanged.

# October 4: AutoSwitch risk and diagnostic-phase correction

Branch `fix/autoswitch-negated-risk` starts from `fork/staging` at `86d1c083a`.
Scope: correct the non-destructive false positive and allow a clearly limited
post-operation diagnostic phase to release an inferred Frontier floor to
Workhorse. Existing manual constraints, protected risks, failure escalation,
qualification registry and CU wire contract remain authoritative.

Development only. No main/staging merge, live configuration change, deployment,
restart, or contact with staging/deployment agents. VK::Staging owns activation.
See VK_AUTOSWITCH_RISK_PHASE.md for bounded replay evidence and limitations.
Older preparation/runtime entries below are historical.

# October 3 Restart Candidate

Prepare current staging AutoSwitch changes together with the live PR138 attention
fix, preserving the current review journal. Keep production usable and measure
the whole preparation. Do not activate the candidate without separate approval.
The source-stream notes below are retained as history.

## October 3: AutoSwitch staging integration

Clean branch `fix/autoswitch-followup-staging` starts at staging `b0f4c10a9`.
It carries the exact AutoSwitch source from `dd41b5de1`, including the October 2
Recommended default/selector behavior, Sol6.1 High default, terminal-independent
runtime identity, and completed-context follow-up repair. Original development
branch `fix/autoswitch-recommended-default` remains preserved. No source conflicts
or routing changes were introduced when extracting this release scope.

The unrelated attention/sidebar changes from open PR138 are deliberately excluded.
They are already in the live frontend; VK::Staging must account for PR138 before
replacing that frontend to avoid losing the live attention fixes. This integration
does not merge or modify that separate PR. It also does not restart services,
change main, or contact/trigger staging or deployment agents.

Existing focused/native evidence is in VK_AUTOSWITCH_FOLLOWUP_CONTEXT.md and
`/mnt/vk-storage/vk-autoswitch-context-20261002`; no inference acceptance is repeated
because the source is byte-identical. Fresh integration checks and PR metadata
are recorded under `/mnt/vk-storage/vk-autoswitch-staging-20261003` and in the PR.
The host lacks Tauri GTK development packages and has under 1 GiB free SSD space;
full workspace/desktop checks therefore rely on the repository CI runners rather
than risking the live host. Local checks cover the changed executor, services and
frontend sources, formatting/governance, and byte-identical CU wire compatibility.

# Workspace Attention Preservation

Branch `fix/workspace-attention-preservation` starts at staging `b0f4c10a9`.
Scope: intentional review clearing and actionable sidebar pagination, with
focused tests and evidence-backed flag recovery. No backend, schema, model,
capacity, restart controller or issue-status changes belong in this stream.
See VK_ATTENTION_PRESERVATION.md. Older stream entries below are historical.

## AutoSwitch release compatibility (2026-10-01)

Scope/savings fixes are merged through PR134 (staging) and PR135 (main).
The live backend is still PID1504649/sourceadfa7c051; the release has not switched.
Release preparation found a rollback reader incompatibility: the old binary
rejects added fields inside `SemanticClass`. Scope relationship now persists on
its extensible parent `SemanticTrace`; native classification and safety logic are
unchanged. The generated API types follow that persisted shape.

Release artifacts and current evidence live at
`/mnt/vk-storage/vk-autoswitch-scope-release-20261001`. Desktop has the verified
checkpoint and delta under `B:/vk-backups/vk-autoswitch-scope-release-20261001/`.
The full checkpoint restored successfully into an isolated directory. These are
online backups, not the final fenced cutover capture. Read-only inventory found
an unexpectedly restarted September14 standby (PID2828009); it had no clients or
children and was returned to its frozen state. The routed server and data remain
unchanged. No candidate production startup or route switch has occurred.
Read the package readiness/status files before any activation; never reuse a
consumed cutover controller. Existing Shadow/manual choices must remain intact.

## AutoSwitch scope and savings correction (2026-10-01)

Current development fixes permanent Frontier inheritance and the false security
promotion of configuration notes. Read [VK_AUTOSWITCH_SCOPE_FIX.md](VK_AUTOSWITCH_SCOPE_FIX.md).
Independent small work can choose Luna after protected work; ambiguous continuation,
protected paths, explicit floors and failure handling remain conservative. Native
recommendation tests cover real TF::Build wording and ordinary UI/documentation
work. This is source-only: no backend restart, deployment or live routing-policy
change. The earlier no-restart workaround below remains the actual live state.
Validation passed: 131 executor tests (six opt-in ignored), generated shared types,
web-core TypeScript, executor Clippy with warnings denied, formatting/governance
and diff checks. CU contract bytes are unchanged. Five native classification calls
used 20,883 input tokens (3,840 cached), 915 output, 4.5–9.3s each; five controls
needed no inference. The real preceding TF::Build request was included in one
replay. These are recommendation checks, not measured accepted-task savings.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/scope-fix`.
Next: adopt the backend changes through the normal release path when worthwhile,
then measure total accepted-task usage; no restart or release was done here.

## AutoSwitch no-restart testing workaround live (2026-10-01)

Operator authorized the temporary no-restart path. Frontend source `8d4b9ead2`
is live on the existing backend at `https://vibe.local`; backend PID1504649 and
binary are unchanged. Only the two chat-setting frontend files differ from the
previous frontend source. All old hashed assets remain available, and the prior
frontend/proof have verified rollback copies on mounted SSD.

Nine genuine one-reply checks refreshed all seven models and the two additional
low-effort pairs in the existing availability file. No retries or background
paid refresh were installed. The current backend's 24-hour rule still applies:
proof expires **2026-10-02 16:10:26 UTC**. Native counters total50,254 input tokens
(11,904 cached) and72 output tokens; these are not allowance charges.

TF::Build's empty follow-up draft is now Shadow/assessed; manual model and effort
remain Sol6.1/xhigh. Actual browser selection/reload checks passed at desktop and
mobile sizes without errors. No new development execution was submitted and no
phone operation occurred. Reload the operator's page to receive the updated UI;
previous explicit browser-local manual overrides remain authoritative.

Read `VK_AUTOSWITCH_SHADOW_FIX.md`. Evidence, deployment manifest, test scripts,
screenshots and rollback are at
`/mnt/vk-storage/vk-model-autoswitch-20260930/no-restart`.
The permanent backend auto-refresh fix remains undeployed. Further Shadow work
can use this temporary window; refresh genuine proof on demand if testing extends
past expiry. Never merely advance timestamps or add unattended paid probes.
A complete new live routed task/child acceptance is still pending operator work.

## TF::Build Shadow continuity repair (2026-10-01)

Branch `fix/autoswitch-shadow-continuity` fixes expired availability renewal and
same-session routing hydration. Read [VK_AUTOSWITCH_SHADOW_FIX.md](VK_AUTOSWITCH_SHADOW_FIX.md).
Catalog renewal is bounded, metadata-only and identity-checked; historical exact
execution proof is retained without changing verification timestamps. Manual
choices, fresh-chat opt-in, policy floors and CU wire format remain authoritative.
This is development only; no live proof/profile/service mutation or deployment.
Validation: 127 executor tests passed (six opt-in ignored); the metadata-only native
refresh passed separately in 0.90s against a private copy of the production proof.
All seven models remained discovered; all exact verification timestamps/efforts
were preserved and the production proof hash stayed unchanged. Seven React selector
regressions, web-core TypeScript, executor Clippy, targeted ESLint, formatting
and ops checks passed.
CU canonical contract remains byte-identical. No billed inference or deployment.
Evidence: `/mnt/vk-storage/vk-model-autoswitch-20260930/shadow-fix`.
Normal release adoption and a full live Shadow run remain pending. TF::Build's
later manual state must be explicitly changed back to Shadow; do not silently
reinterpret an existing manual execution as routing consent.

## AutoSwitch V2 staging integration (2026-10-01)

The operator now authorizes the full V2 PR/push/rebase merge into staging.
See [VK_AUTOSWITCH_V2_STAGING.md](VK_AUTOSWITCH_V2_STAGING.md) for base, exact
commit mapping and validation limits. Seven V2 commits are rebased onto
staging198d55a20; V1 is already present. Only continuity documents conflicted;
all source patches and newer staging functionality are preserved. No deployment
or full live Shadow test is included. Earlier development-only scope below is history.

## Native child acceptance and capacity correction (2026-10-01)

The bounded native child test now passes. The prior pgrep count included Node
launcher wrappers and diagnostic command text; it was not a count of active agents.
Linux fallback accounting now counts native app-server chains once. Idle servers
still count conservatively. Default limit eight and systemd accounting are unchanged.

The first admitted trial completed Luna5.6/low but exposed loaded-thread resume
ignoring escalation settings. The safety check blocked the second turn. VK now
applies next-turn settings, waits for native confirmation, and rechecks before
inference. The final test completed Luna5.6/low then Sol6.1/medium on the same child
thread, preserved the tracked dirty sentinel, reused duplicate starts, and retained
parent/child identity. Native rollout turn_context matches both CU v1 bindings.
Escalation failure triggers were injected fixtures; root execution identity is a
harness fixture, with no parent inference. Three actual child turns total this pass.

Validation: 122 executor regressions pass, five opt-in tests ignored in the normal
suite; the opt-in native test separately passes; executor Clippy, format/ops and
canonical CU contract comparison pass. Native usage preserves both latest-request
and cumulative-thread fields. Evidence: `v2-delegation/capacity-fix-20261001/verified`
under `/mnt/vk-storage/vk-model-autoswitch-20260930`.

Next is the first complete live V2 Shadow test on a fresh ordinary chat, handled
separately. No staging, deployment, production cutover or external-agent interaction.
Read [VK_AUTOSWITCH_DELEGATION.md](VK_AUTOSWITCH_DELEGATION.md). Version 0.1.42.

## Semantic fallback continuation (2026-10-01)

Auto/Shadow now adds one bounded gpt-5.6-luna/low/standard classification turn only
for materially uncertain deterministic assessments. Known envelopes, manual/pinned
execution and protected floors skip inference. Closed structured output feeds the
existing qualification/floor/exclusion and consented escalation logic. No tools,
implementation loop, staging/deployment changes or agent coordination.

Native sample: ordinary assignee display -> Luna6/medium; private-project access
-> Astra/high; vague/persistence/intermittent-failure requests -> Sol6.1/medium.
Two deterministic controls incur zero calls. Five final classifier calls measured
3,978–3,986 input tokens, 78–133 output and 4.344–8.664 seconds each. One initial
transport check also ran. Classification attempts/usage persist in decisions and
a separate vk.classification.v1 feed; CU vk.routing.v1 is unchanged.
Read VK_AUTOSWITCH_FULL_ROUTER.md for configuration, bounds and actual evidence.
Validation: 29 focused regressions, executor/services Clippy, generated-type and
web-core TypeScript checks, format and ops pass. Source-only; live V2 Shadow QA
and net-savings measurement remain pending.

## Natural-language triage continuation

V2 now recognizes common presentation outcomes on named UI surfaces and corroborates
them with bounded repository evidence at the existing execution boundary. Structured
triage includes uncertainty, validation availability and inspection counts; missing
context retains Workhorse. No planning model call, registry change, CU contract change
or V1 deployment work. Read VK_AUTOSWITCH_FULL_ROUTER.md for scope and limits.

## V2 resumed after V1 staging integration

Continue on `vk/5a81-autoswitch-cu-recovery`; V1 PR127/deployment is separate and
must remain untouched. Follow-up qualification persistence and lexical assessment
repairs are implemented, plus a read-only policy recommendation command. Details:
[VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md). This is not live
activation or live Shadow evidence. No V1 model acceptance campaign was repeated.

# Automatic assessed router (V2)

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Extends accepted V1 with default task assessment, explicit model/effort/envelope
qualification, configurable pair preference, operator-reported validation and
risk-expansion escalation. See [VK_AUTOSWITCH_FULL_ROUTER.md](VK_AUTOSWITCH_FULL_ROUTER.md).
Auto can choose older Luna/low, Luna6/medium and Sol6/medium without Routine labels.
Manual and explicit floors/exclusions remain authoritative; no scheduler or reset.
Experimental pairs remain shadow-only. Matching release deployment and a small
live Shadow sanity check remain pending; no production activation in this stream.

## Accepted V1 history

## October 1: Pre-Cutover Preparation Performance

Branch `fix/vk-precutover-preparation`, based on fork/staging620bd7eb9.
Scope: versioned preparation-only tools, verified static evidence/artifact reuse,
rolling online backup checkpoints, bounded concurrent queue inspection, and
whole-preparation timing. The fenced capture callback now has real private
handover/recovery acceptance and is approved for staging integration. See
VK_PREPARATION_PERFORMANCE.md. No production pause/restart/reroute, application
feature change, or replacement of an existing production controller.
Inherited stream notes below describe other work, not this branch's authority.

## AutoSwitch V1 staging-only release

Branch `release/autoswitch-v1` rebases validated V1 onto staging56792a72c.
See [VK_AUTOSWITCH_V1_STAGING.md](VK_AUTOSWITCH_V1_STAGING.md) for exact commit
mapping, preservation of newer staging behavior and operator deployment notes.
V2 remains untouched on `vk/5a81-autoswitch-cu-recovery` at64e9cb5bd and is
excluded. Only continuity documents conflicted; no source conflicts. The operator
owns all post-merge actions. Do not contact or trigger a deployment/staging agent.

# VK Model AutoSwitch V1

Current branch: `vk/5a81-autoswitch-cu-recovery`.
Scope: opt-in model/effort routing at existing Codex execution boundaries.
[VK_MODEL_AUTOSWITCH.md](VK_MODEL_AUTOSWITCH.md) supersedes the planning-only
catalog and describes policy, implementation and enablement gates.
[VK_CODEX_ROUTING_CONTRACT.md](VK_CODEX_ROUTING_CONTRACT.md) defines usage joins.
All seven required models execute on isolated CLI 0.159.2 using the existing
account. Default host CLI 0.153.4 and production VK remain unchanged.
Manual, shadow and automatic modes preserve per-chat control; automatic routing
requires fresh executable-pair evidence and pauses rather than violating floors.
CU-compatible lifecycle telemetry is implemented. Native executor acceptance
passes at the existing capacity limit; private candidate API acceptance and CU
correlation evidence are tracked in VK_AUTOSWITCH_ROLLOUT.md. The active worktree
was externally deleted; recovered source is outside the managed worktree tree at
`/mnt/vk-storage/vk-model-autoswitch-20260930/source`.
No production restart, deployment, global profile change or autonomous retry.

## Inherited integration context

The following notes describe inherited work, not this branch's task scope.

## September 28 — two concurrent selected capacity goals

Added bounded two-agent admission and per-session stop, retaining shared allocation,
independent native/OS deadlines, same-workspace exclusion and interactive priority.
See [VK_CAPACITY_CONCURRENCY.md](VK_CAPACITY_CONCURRENCY.md) for API semantics,
real two-native-goal acceptance and deployment requirements. Companion CU changes
are required; old clients keep one slot. Production deployment remains operator-owned.

# Capacity Cutover Lock

Current scope: implement authenticated ownership release/acquire with fresh
state reload and paused same-PID fallback for compatible backends. Production
cutover is explicitly withheld by the operator, who is using VK. Do not stop,
pause, restart or reroute production. See VK_CAPACITY_OWNERSHIP.md. The running
legacy backend requires a separate one-time upgrade before using this protocol.

Fix read-only readiness to detect a capacity owner that survives process pause.
Branch fix/capacity-cutover-lock adds the existing-inode lock barrier and real
kernel-lock tests; it does not change production services or silently replace
the operator's same-PID standby requirement. Restart-based recovery is separately
rehearsed with copied data and requires explicit approval before production.

## Integrated Codex Model Selector Regression

Restore GPT-6 reasoning choices and hide GPT versions below5.6 in the Codex
selector. Updated onto staging fa7523c17, this frontend-only compatibility correction
does not rewrite existing chat selections, drafts, defaults or native settings.
No backend restart. See `VK_MODEL_SELECTOR_FIX.md` for evidence and deployment.

## Integrated Staging Context: VK::Weird Message

Scope: reconcile native goal completion evidence within the current turn and
report completion status in the standard summary metadata. Replace the generic
checklist warning with `Completion::` after `Human Needed::`, naming missing
evidence when unverified. VK normalizes its status into the existing report;
a response without a standard report receives a compact metadata line.

The reconciliation request is a single turn/steer pinned to the current root
turn. It never starts another turn, reopens the goal or changes its budget.
Final checkpoints remain accepted after the native completion notification.
A rejected/late steer falls back to an honest unverified status. Checklist
verification is supporting evidence, not an independent audit of the objective.

Backend and shared frontend changes are pushed for
[PR #123](https://github.com/artinflight/vibe-kanban/pull/123) into staging.
They are not deployed. See HANDOFF.md for validation and deployment boundaries.

## September 30: scheduled resume history

Scope: scheduled capacity resumes preserve native-goal supporting progress,
turn/stagnation counters, recovery plans and substantive input holds. Explicit
manual resumes retain their current fresh-attempt behavior. No scheduling,
quota, containment or selected-agent admission limits are relaxed. This is the
manager-side fix; the active Chat Orchestration implementation is separate.

## October 9 combined frontend preparation

Seamus explicitly authorized the final workspace-first frontend. Product source
7810706ea5255a0894457c96aa158adbb947b9a1 combines final66e00728's twelve frontend
changes with c3c48e63's six newer consent/chat repairs. The c3c48e63 backend, guard
and routing artifacts remain pinned; no backend/schema/dependency rebuild is
required by this inclusion. Current staging e8c450fb is incorporated for normal
PR freshness. Its older continuity notes remain accessible at that immutable
commit; these files retain the newer combined safety/recovery tracking.

The same actual MCP candidate is still restoring. Final catch-up capacity, whole
restore verification, actual application/consent acceptance and scoped promotion
remain held. No production restart, cutover, merge or general cleanup occurred.
