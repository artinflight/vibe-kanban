# Scheduled First Run: Final Isolated Acceptance

## Current Decision

Final-source isolated acceptance passes. The inert release payload is prepared.
**Production is unchanged and not yet cutover-ready:** explicit rollout approval,
safe SSD headroom, fresh backup/full-workload rehearsal, release/configuration
binding and final safe drain remain. Do not enable pending candidates or resume
the real Android goal. Scheduling ON, credits OFF and Recommend intent stay intact.
No paid inference, archive/temporary-file deletion, merge or restart occurred.

This record supersedes the older86f62b2/516148dc readiness statements, not their
retained incident evidence. Independent review clearance of the minimal stop
bound and9b3f82538 shared-cutoff test correction is supplied by the parent.

## Exact Inputs And Package

- VK PR147: `9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4`.
- CU PR38: `95e7aea47e137015daa8efcbb210184ee7ce723c`.
- Candidate SHA256: `c33e1cc7b7efb4f63b8c08fb1bbbb59a448f1340fe7728f6bf5118c9d59f17c0`.
- Disabled v2 fallback SHA256: `2494f1dc7ca2de8ed26806603b86f9fa3e466c9f19a00e4aab2c8b9712a70c97`.
- Guard SHA256: `04ee7fc587b162c14e642e2c96cea3905af3990ce77956983aef6bc2569f7b53`.
- VK version0.1.42; actual offline native runtime0.159.2.

Receipt root: `/mnt/vk-storage/vk-first-run-final-20261006/`.
`acceptance.json` indexes all exact fixture receipts and their hashes.
`stop-timelines.json` contains lease, observed revoke interval, provider request/
activity/TERM, independently observed empty cgroup, HTTP response and held status.
`frontend-compatibility.json`, `deployment-candidate.json` and
`deployment-payload-receipt.json` bind the payload inputs.

Payload `candidate-release-9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4.tar.gz`:
87,033,879 bytes; SHA256
`6ac06d9b93244894e6200aadf4e68e17f7c020b5cef18b399eea300e7cd1393f`.
All773 members were reread and hash-verified. It contains the final candidate,
matching disabled-v2 fallback, guard, real765-file frontend, exact CU source and
provenance. The86f62b2 frontend is reused because all frontend/build inputs are
unchanged at9b3f82538. No older backend is packaged. Set `VK_FRONTEND_DIST_DIR` to
the packaged frontend; the server's embedded placeholder must never be served.
CU runs its source directly with Node24; no omitted CU bundling step is required.
This is a software payload, not a fresh production backup or sealed handover.

Desktop retention is verified at `B:/vk-backups/vk-first-run-final-20261006/`:
the payload matches the SHA above. Review packet
`review-packet-1791324529988964023.tar.gz` contains321 verified evidence files,
1,884,430 bytes, SHA256
`e67a47ea8cc20be8f0cbf006b93951f69c9d0a2971b6dc038738e42845cb4167`.
`desktop-preservation.json` records both successful remote hash checks, with no
transfer retry. Original backups and all older evidence remain untouched.

## Final Combined Evidence

Each suffix is under `/mnt/vk-storage/vk-sfr-http-20261006/vk-continuation-http-`.

| Suffix | Final-source acceptance |
| --- | --- |
| `717zekit` | Authenticated real CU/HTTP selection without launch; native authentic checklist; later same-thread resume; input/failure/empty/plan holds; no provider retry; legacy/manual/weekly rejection |
| `wg4jtjnq` | Identity/anchor/revision/revocation races; concurrent scheduler ticks; two workers and third waiting; drain; CU state reload |
| `grs6htc3` | Pre-native interruption/cutoff, actual isolated backend restart, capability withdrawal and no spent initialization replay |
| `ok_b7xal` | Saved-window, corrupt/empty/mismatched/held/completed exclusions, foreground and archive constraints |
| `57s38f39` | Actual worker rejects native identity/anchor changes after issuance before provider work |
| `t2ubgywa` | Same-workspace cross-session exclusion |
| `2dmpcvzg` | One/two deliberately stalled workers; unverified exit retained and exact grant safely reconciled; truthful native-active holds |
| `y9yxmbc9` | Initial and final controller-lock contention, bounded error, exact stopping-grant reconciliation |
| `27blad5n` | Real final backend/external frontend at1440/390px; exact JS hash, rendered local workspace shell, no JS errors |

There are47 distinct passing assertion names across eight HTTP/native groups,
plus the browser group. Each HTTP/native group also tests this exact disabled-v2
fallback with gate absent and forced1. Pending/held/checkpointed records, native
identities, bindings, receipts and issued IDs survive. Initialization remains
disabled, removal including a missing synthetic session stays safe, and eligible
already-checkpointed goals can continue normally. No old database is restored.

The actual CU `VkCapacity` fetch budget is10seconds, without override:

| Case | VK HTTP response | End-to-end CU suspend |
| --- | ---: | ---: |
| One stalled worker | 2.720s | 2.747s |
| Two stalled workers | 2.484s | 2.518s |
| Exit confirmation withheld | 2.458s | 2.492s, correctly unconfirmed |
| Initial controller lock | bounded conflict | 0.526s including release |
| Final controller lock | bounded500 error | 2.889s to error;7.625s including fault removal/reconciliation |

For all four stalled worker executions, independent cgroup exit was observed
before lease expiry and immutable hard stop. Each made one outstanding offline
provider request. Native stored status remained **active**, truthfully, because
the pause response was blocked; the durable initialization state was **held**.
Stored active is neither proof of a live worker nor authority to initialize again.
With exit confirmation denied, both VK's stopping grant and CU's pending state
remain. Renewal, fresh start and reselection are rejected. Removing the synthetic
fault reconciles the same grant/execution without changing identity or receipt.

Final-lock failure is a genericHTTP500 at the API, with the backend logging
`Stop remains unconfirmed; controller busy, reconcile`. CU correctly records
unconfirmed rather than success. The harness originally expected detailed409
wording; that failed attempt is retained, and the narrow lock-only correction
asserts the actual500, pending ledger and exact reconciliation. Improving error
wording is a developer-owned diagnostic follow-up, not a containment blocker.

Fault scope is explicit: final HTTP binaries experienced withheld pause/interrupt
responses, held controller-side EOF, denied exit verification and bounded private
FIFO read contention. Internal mutex/log/exit-signal instrumentation belongs to
the developer's13 packaged cases, not a hidden HTTP test hook. Those reviewed
408 CI tests/13 packaged cases are reused, not rerun or miscounted as HTTP tests.
All five reviewed boundary hashes match; host roots are read-only, networking and
manager access isolated, real-workspace mutation attempts zero. Owned workers
are inactive and their deadline timers stopped or already unloaded.

Failed new fixture roots `fvi4by6h`, `qwufcmbc`, `vavimduc`, `iwcuzon1` and
`ipyefy7c` remain. They document variant canonicalization, launcher identity,
argument forwarding/zero-retry rejection, waiting for delayed transport completion
before another launch, and error-message expectation corrections. They are not
counted as whole-run successes. No denied initialization prompt was retried.
Browser scope is assets/local shell, not full UX or a physical phone test; earlier
onboarding overflow and unconfigured remote400s remain documented limitations.

## Original Incident And Recovery Limits

The earlier input worker exited before its lease expired. The parent independently
cleared observed containment; the reviewed whole-graceful bound closes the
previously unbounded graceful waits. The exact original delay cause and revoke/provider timestamps
are still unavailable. New synthetic timestamps must never fill that gap.
Historical missing rollouts and later unbacked five-root edits remain exceptions.
All recovery evidence, original backups, protected roots and rollback chains stay.

## Minimal Rollout And Timing

1. Obtain the separate rollout approval for these exact source identities and
   promote reviewed releases under each repo's procedure. Clear storage safely:
   only about345MB remained after packaging. No archive or blocked4.13GiB
   temporary allowlist is approved for deletion by this task.
2. Use installed PR142 pin `528282d00c985230aad3033dc235d8cd943e5f4d`, not branch
   copies of older tools. Capture fresh Desktop-backed current data, settings,
   read/unread state, sessions, worktrees and attachments with moved-root/journal
   checks. Bind runtime0.159.2, existing AutoSwitch module/shared telemetry,
   routing/owner choices and both final server artifacts; rehearse latest-data
   ownership transfer and the disabled-v2 rollback before sealing readiness.
   The installed `vk_rolling_backup.py` was rehashed against that Git pin:
   `ada02c386d5be898061e05e802baed6f375d6d11e870d268e63fa00f31df845c`.
3. Compatible CU goes first against capability0. Preserve schedulingON/creditsOFF
   and all selections; prove it remains inert for pending goals. Only then expose
   pending first-run capability through the paired VK/backend/frontend cutover.
4. At the approved window, drain active VK executions, queued messages and CU
   grants safely. Use supported Turn Steer only with authorization; no competing
   follow-up writer, abrupt kill or real Android test. One single-writer transfer
   then switches the paired frontend/backend. Verify actual route/version,
   sessions/settings, messages/flags, attachments, models, dot and shared feed.
5. Any cutback uses this disabled-v2 reader on **the same latest data**. Neither
   current production nor the old paused executable is a safe post-v2 reader.
   Never delete holds or copy an older backup over production to permit rollback.

Plan for approximately30-60seconds of VK unavailability after preparation and
safe drain, plus a brief CU service change. This is an estimate, not a measurement
of this candidate's full handover; the last successful handover took21.972seconds.
Space remediation, fresh backup/rehearsal and waiting for agents are preparation,
not included in that downtime estimate. Users can keep working until the approved
drain. No service or routing change is authorized by this acceptance task.
