# Scheduled First Run: Stop Incident Review

## Decision

The original ten-second CU stop timeout is **not resolved**. It is not evidence
that model work continued for ten seconds: the retained system journal proves
that the relevant worker exited promptly. Two focused reproductions against the
same pinned candidate returned promptly, but neither explains the original
delayed HTTP acknowledgement. Do not describe the earlier42 assertions as full
acceptance or rollout approval.

No application code, live service, routing, database, owner setting or development
worktree was modified by this investigation. No denied start/prompt was retried.
The two reproductions used new synthetic identities, native0.159.2, an offline
provider and the unchanged reviewed CU fixture boundary.

## Original Timeline

All times are October6 UTC. Root:
`/mnt/vk-storage/vk-sfr-http-20261006/vk-continuation-http-lcp7ys3k`.
Input execution: `7ceac568-1139-4568-b3b9-79105b89d201`.
Grant: `d88ba926-a185-4b18-81d8-a20d8ed83e31`.

| Time | Exact retained observation |
| --- | --- |
| 19:33:17.011425 | Execution row created |
| 19:33:17.266426 | Fixture-owned systemd worker starts |
| 19:33:17.923 | Completed HTTP response reports pending/running, not stopping |
| 19:33:18.034 | HTTP response reports held, ineligible, input required, stopping |
| 19:33:18.080 | Last successful HTTP response before the failed stop call; still held/stopping |
| 19:33:18.299685 | Worker exits75/TEMPFAIL, before the stop timeout |
| 19:33:18.472327 | VK execution row records failed/exit75/completion |
| 19:33:19.092023 | Backend warns that persisted native goal pause was not confirmed |
| 19:33:28.433858 | Driver teardown signals fixture backend; shutdown finds zero running processes |
| 19:33:36.885 | Recorded lease expiry,18.585 seconds after worker exit |

The lease is retained as revoked; final ledger is held/ineligible. The exact
revocation-write time is not recorded. The original fetch wrapper captured only
successful responses, so there is no exact failed-request start timestamp.
`driver.log` records the ten-second abort. Provider capture has12 request lines
across all seeds/cases but no per-line timestamps or thread IDs. It cannot prove
the input worker's exact last request time. Do not fill those evidence gaps with
inferred timestamps.

The actual worker unit is
`cu-fixture-a0310812c063410986b4daf7b332002d-vk-capacity-7ceac56811394568b3b979105b89d201.service`.
Retained cleanup confirms all three workers inactive/failed and no shared service
modified. This is a synthetic incident, not a production interruption.

## Focused Reproduction

VK `86f62b2a4a1baff54cde715749b97f283907b8f6`, CU
`95e7aea47e137015daa8efcbb210184ee7ce723c`; same candidate binary/guard.
All2371 source hashes and five artifact hashes verified before each run.
An initial attempt refused the developer's concurrent uncommitted stop tests
before starting a fixture. Subsequent runs used a frozen Git-archive extraction.

| Fixture suffix | HTTP stop response | Empty cgroup observed after request | Provider request count before/after |
| --- | --- | --- | --- |
| `6gi2fzvq` | 398ms | 134ms | 2 / 2 |
| `7z1x2zt_` | 468ms | 219ms | 2 / 2 |

Each count includes one ordinary seed and one input first turn. Sampling continued
through lease expiry plus1.5seconds; no further request occurred. Final grant is
absent, goal remains held, running list empty. Host-side observation queried only
the manager's registered fixture units; no isolation rule was relaxed.

The export includes request-start/headers/body/error timestamps,100ms ledger/
lease/request-count samples,200ms host-unit/cgroup samples, exact journal events,
provenance and cleanup hashes. These are bounded non-reproductions, not proof
that the intermittent acknowledgement issue is fixed.

## Development Owner Scope

In the pinned source, `crates/server/src/routes/capacity.rs` stop handling revokes
the lease before awaiting `AppServerClient::suspend_capacity_execution`, then
verifies unit termination. In `crates/executors/src/executors/codex/client.rs`,
`suspend_capacity` bounds native RPC calls individually but awaits thread/turn
mutexes and log/exit paths without a whole-operation timeout. The independent
guard still runs; control-plane responsiveness and worker containment are separate
contracts. An unbounded graceful await can delay acknowledgement even when the
worker is already gone. This is a source risk, not a proven root cause of this
particular incident.

Developer-owned scope is the stop sequencing/bounds and its focused tests in those
files, plus `scripts/testing/codex_goal_provider.py` and
`scripts/testing/scheduled-first-run-validation.py`. Concurrent uncommitted stalled
revocation/expiry tests were observed in that workspace. Their later local
`stalled-stop-local-acceptance.json` reports provider termination46ms/7ms and
worker exit480ms/567ms after revocation/expiry, with the graceful task still
blocked, one provider request, and the first-run hold retained. Staging inspected
the underlying measurement files and test-only client diff. This supports the
independent worker fence, not timely HTTP acknowledgement. Those tests are not
part of the accepted86f62b2 source. They are now committed/pushed in516148dc2;
fresh CI and final independent review remain developer-owned. Independent review
must resolve the original acknowledgement behavior and verify that blocked native
pause cannot bypass revocation/expiry containment. Do not merely increase CU's
ten-second timeout or retry an ambiguous start/denied prompt.

## Exact Review Inputs

Export root: `/mnt/vk-storage/vk-first-run-gates-20261006/`.

- `original-stop-incident.json`: original HTTP excerpts, DB rows, journal,
  leases, final state, complete relevant logs and source receipt hashes.
- `stop-reproduction-review.json`: both new timelines, process/lease/provider
  comparisons, receipt hashes and explicit unresolved disposition.
- `incident.py`, `export-review.py`, `stop-diagnostic.py`, `combined.mjs`:
  exact diagnostic/export tools. The diagnostic is not a production launcher.
- Each new fixture retains `stop-diagnostic.json`, `host-observer.jsonl`,
  `provenance.json`, `fixture-cleanup.json` and the reviewed boundary proof.

The review packet and the source/binary identity are separate from the pending
frontend package and future deployment authorization. Preserve all original
failure receipts and historical recovery exceptions.
