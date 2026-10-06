# Scheduled First Run: Combined Acceptance And Rollout

## Decision And Authority

October 6 staging acceptance only. **Not approved for rollout.** Six isolated
HTTP/CU/native test groups passed their assertions; the earlier stop timeout
still requires review. A real paired frontend/payload is now built and verified;
independent final-delta review plus an explicit rollout checkpoint remain
outstanding. See VK_FIRST_RUN_STOP_REVIEW_20261006.md for the exact incident and
VK_FIRST_RUN_FRONTEND_20261006.md for the package and browser limitations.
No production restart, merge, deployment, routing change, database restore,
settings write, paid inference or real Android test occurred.

The desired workflow is selection now, automatic first native initialization
during the saved overnight window, then ordinary scheduled continuation.
Development owns feature fixes; staging owns combined acceptance and rollout.
No manual start/stop workaround is proposed for the user's workflow.

## Exact Provenance

| Component | Verified source | Release status |
| --- | --- | --- |
| VK draft PR147 | `86f62b2a4a1baff54cde715749b97f283907b8f6` | Base staging `8b562265d25a3f8ee6d4fa602144e71caddfbc85`; all11 listed checks green |
| CU draft PR38 | `95e7aea47e137015daa8efcbb210184ee7ce723c` | Base staging `c8213e81d18123671bce9a262c9dedf1a788a7bf`; not deployed |
| Native test runtime | Codex CLI `0.159.2` | Actual app-server, credential-free offline provider |

Read the developer's `revision-staging-handoff.md` and bundle under
`/mnt/vk-storage/vk-scheduled-first-run-20261006/`. The bundle suffix is the
full VK SHA above. All five artifact hashes and2371 tracked source hashes were
checked before each fixture. Developer source trees remained tracked-clean.

- Candidate HTTP server SHA256:
  `26390884877b6c53e7335067c5b7b81695e6eca323be4f6c8e800319c88cdb12`.
- Compile-disabled v2 rollback HTTP server SHA256:
  `e5aab6ad020c127797f9c0eba5989f9ff4492634dd7d4ad7fcee6b4b582fc0ed`.
- Guard SHA256:
  `04ee7fc587b162c14e642e2c96cea3905af3990ce77956983aef6bc2569f7b53`.
- Existing standard CI run37513209788 and hosted build37513209967 were read,
  not dispatched. The developer's156 candidate tests,157 rollback tests,
  six native offline cases and406 backend CI passes were not redundantly rerun.
- The old27d9562d2 audit and its CI/artifact/headroom blockers are historical,
  superseded by this receipt. Its retained evidence was not deleted.

The original HTTP bundle contains a placeholder frontend and is unchanged.
The separate source-pinned payload documented in VK_FIRST_RUN_FRONTEND_20261006.md
supplies the real external frontend. Its deployment must set
`VK_FRONTEND_DIST_DIR` to that payload, never fall back to the embedded placeholder.
Developer regression-only follow-up516148dc2 is now pushed; its new CI/final
review is separate from the86f62b2 artifact checks. Production code is unchanged.

## Exact Combined Receipts

Receipt root: `/mnt/vk-storage/vk-first-run-staging-acceptance-20261006/`.
Final index: `combined-acceptance.json`, SHA256
`97ade57c3199c82a50686bc41662f9cc80ea8644c5319904a9eebfa1e5e9e7d0`.
It records hashes of per-run HTTP bodies, assertions, latest ledgers, source
provenance, reviewed-boundary proofs and fixture-owned unit cleanup.

Each suffix below is under
`/mnt/vk-storage/vk-sfr-http-20261006/vk-continuation-http-`:

| Suffix | Executed acceptance |
| --- | --- |
| `san47vda` | Authenticated owner/API; inert identity-bound selection; all four stale-card identities; legacy/manual/weekly rejection; authentic nonempty native root checklist; later genuine same-thread resume; input/provider-failure/empty/plan holds; failure exactly one provider request; removal/reselection denial; both rollback gates |
| `nhp5uups` | Four native identity changes and completed-anchor change before dispatch; stale revision/revocation; duplicate scheduler ticks; two actual native workers, third waits; revocation drains workers; persisted CU reload preserves pending selection; rollback ordinary native resume |
| `q6r1xg1x` | Interruption and cutoff before provider; actual fixture backend restart with spent pending receipt; capability withdrawal; no initialization replay; hold-preserving rollback removal |
| `j0ksim2i` | Outside saved window; corrupt/empty/mismatched/input-held/already-checkpointed sidecars cannot gain first-run authority; complete/budget-limited native goals rejected; foreground record blocks dispatch; archived workspace excluded |
| `lf34_bhn` | Actual delayed worker rejects goal ID/thread/objective/creation and anchor changes after issuance, before any provider work; rollback removal after synthetic session deletion preserves native goal and hold |
| `279xj4la` | Actual CU/HTTP same-workspace cross-session exclusion; compatible rollback permits ordinary initialized-thread resume |

There are42 distinct passing assertion names across these six successful groups,
not42 additional unit suites. Earlier unsuccessful fixture attempts remain
retained and are not counted as whole-run passes. Every worker in each final
cleanup receipt is inactive/failed; shared services were not modified.

The actual CU control handler, owner authentication, scheduler and quota ledger
communicated with actual VK HTTP servers. Real native app-server turns authored
positive checklists. Invalid sidecars were deliberate negative fixtures only.
Test account/quota/time are synthetic; no paid quota redemption occurred.
Source-backed isolation and bounded supervisor files were unchanged and hashed.
Host roots/worktrees were read-only, host-manager and other sockets masked,
external networking isolated, canaries unchanged. No copied live database or
real Android goal was used. Only fixture-owned service names were reachable.

The dated driver is retained in
`scripts/testing/staging-first-run-20261006/`. It is not a production launcher.
Its narrow delayed-provider shim supplies an interruption window inside the
same boundary; it does not replace the native engine or fabricate a checklist.

## Finding Requiring Review

Initial root `vk-continuation-http-lcp7ys3k` reached authentic initialization
but CU's ten-second stop request timed out during the input-hold case.
`driver.log`, HTTP receipts, backend log and `fixture-cleanup.json` remain.
No failed prompt/start was retried. Cleanup confirmed all its workers inactive.
The original journal now proves the input worker exited at19:33:18.299685UTC,
18.585seconds before lease expiry. Two focused reproductions returned in398/468ms,
with no later provider work. Developer stalled-stop tests separately support the
independent guard. Exact original HTTP acknowledgement delay remains unresolved;
all timelines/uncertainties are in VK_FIRST_RUN_STOP_REVIEW_20261006.md.
Later full runs passed, but that is not evidence that the original timeout
cannot recur. Review bounded stop/transport reconciliation before release;
do not erase this finding or change developer code without coordinating review.

Other failed attempts were harness setup/expectation corrections: Unix socket
path length, buffered native protocol reading, missing synthetic repo links,
profile canonicalization, native milliseconds versus wire seconds, an
unapproved delayed-launcher configuration, a lease too close to expiry and
synthetic quota-clock/period expectations. Their rejection evidence is retained.
None changed production or relaxed the reviewed isolation/launcher guards.

Accordingly the index truthfully records `executedAssertionsPassed: true`,
`fullHandoffMatrixClosed: false`, and `rolloutAuthorized: false`.
Do not confuse successful bounded tests with final review/release approval.

## Compatible Rollback

Stored ledger format is2; wire `state.version` stays1. Both rollback service
gate configurations (absent and forced1) advertise capability0. Actual latest
pending/held/checkpointed state, native goals, bindings, receipts and issued IDs
survive. Legacy and explicit pending starts fail; removal remains safe, including
a gone synthetic session. Ordinary checkpointed continuation still works.

Current production and its old paused fallback are **unsafe old readers** of
the new ledger, even with initialization OFF. Retain their artifacts, but do
not use them as post-upgrade v2 fallback. Use the reviewed compile-disabled
v2-aware rollback with the same latest state. Never restore an older database
or drop holds/receipts to make an old reader start.

## Minimal Rollout After Review And Explicit Approval

1. Resolve the stop finding and final independent review; bind the final VK/CU
   commits, real external frontend, guard, runtime, module and configuration.
   Recheck only affected acceptance if identities change. Prepare while users work.
2. Deploy compatible CU first against capability0. Preserve scheduling ON,
   credits OFF, original monitor state and owner selections; prove no pending
   first run is launched. This is a future CU-only service change, not authorized now.
3. Use installed PR142 pin `528282d00c985230aad3033dc235d8cd943e5f4d`.
   Its October5 package was reverified;146 retained regressions were not rerun.
   Take a fresh Desktop-backed capture with moved-root/journal checks, review-state
   snapshot, thread/model/settings preservation and latest-data rollback proof.
   October5 success and old backups are not current deployment evidence.
4. At the agreed checkpoint, safely drain VK executions, queued prompts and CU
   grants. Use supported Turn Steer only if a pause is authorized; wait for safe
   completion, never a competing writer or abrupt kill. Perform one coordinated
   backend/frontend handover with feature-gate intent bound to the release.
5. Check actual routed version/frontend, original sessions, saved messages,
   read/unread flags, attachments, model/effort choices, runtime wrappers,
   AutoSwitch module, shared private telemetry and dot connector. User selection
   stays inert until the saved night window. No paid/real Android test is implied.

Work can continue during preparation. The proposed operator checkpoint is:
approve the reviewed final commits and compatible CU-first/VK-second rollout,
then agree a safe drain of active VK turns and the saved scheduler window.
No pause steering, service change or real-goal enrollment is authorized now.
Final service changes affect CU scheduling
and VK agent execution only after a safe drain. No full-scale handover timing
for this candidate has been measured. October5's21.972 seconds is historical,
not a promise for this deployment. Any cutback uses the compatible reader and
same latest data.

## Live State, Storage And Preservation

Read-only check at19:53:54UTC: current VK PID3027197, October5 mainfa8122a50,
version0.1.42; executable SHA remains
`5e7948921f962b9ea74597781ca2e1b0c7bd745edc0d1901a8274dab444097a2`.
CU414400 remains the goal-list deployment, not PR38. Scheduling ON, credits OFF,
connected, zero capacity grants. These are observations, not rollout-drain proof.

SSD available bytes were4,292,698,112 at that check. Staging cleanup reclaimed0:
SFTP2324526/2324527 exited, but PID19071 and privileged process visibility remain
unresolved. See `VK_OWNED_TEMP_CLEANUP_20261006.md` for the4.13GiB allowlist and
exact read-only evidence request. Do not bypass access controls. OP's86 duplicate
deletions and27 original archives are outside this scope; local-parent archive
dependencies still require a retention decision. Shared Rust output is protected.

Retain `/mnt/vk-storage/vk-green-cutover-20261005/historical-recovery-receipt.json`:
later unbacked five-root edits remain unaccounted; precise deletion timing/CU
causality and historical missing rollouts remain exceptions. Protected roots,
workspaces, backups, journals, attachments and all pending release/fallback
artifacts remain. No Desktop payload was deleted or production backup restored.
