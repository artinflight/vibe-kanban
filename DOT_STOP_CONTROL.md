# Exact Dot execution Stop — connector initialized, backend release pending

Seamus explicitly authorized building and initializing Dot's Stop controls on
October 17. This stream adds a guarded backend contract and two additive MCP
tools. It does not authorize stopping real agents as a demonstration.

## Contract

`stop_agent_execution` requires exact `workspace_id`, `session_id`,
`execution_id`, stable UUID `request_id`, and `reason` (`user_request` or
`budget_exhausted`). `get_agent_execution_stop` takes the same four IDs and is
read-only. Neither selects "latest", accepts a process ID, stops a workspace,
clears queued input, alters files, nor exposes a shell/admin route.

The connector first reads `GET /api/execution-processes/{id}/stop-exact` and an
existing matching receipt. It requires version 1, the exact identity and creation
time, a running non-dropped coding-agent execution and serialized admission.
One POST goes only to that guarded endpoint. An absent endpoint returns
`unsupported` with no write: **there is no fallback to the legacy `/stop` or
workspace Stop**. Authentication, Recommend routing and other tools stay intact.

The backend holds the existing shared admission lock across fresh validation,
atomic running-to-killed claim and exact container Stop. The pre-existing
`VK_AUTOMATIC_GITHUB_SYNC=1` setting guarantees that normal launches/completions
use the same lock. Without that guarantee the feature fails closed; this change
does not enable a policy flag. Independent terminal writers cannot win the
conditional claim and still receive a stop. Wrong scope, creation identity,
finished/dropped executions and non-agent scripts cannot reach container Stop.
No execution ID is retargeted to a replacement turn.

`execution_stop_requests` reserves an `unknown` receipt before side effects.
Matching retries read it without dispatch. Conflicting identities/reasons are
rejected. Multiple request IDs for one execution still get at most one claimed
stop. Only `status=stopped, stopped=true` confirms that exact container Stop
returned successfully. Lost responses, errors and cancelled handlers remain
`unknown, stopped=null`; a database `killed` status alone is not confirmation.
Read back the same request; never resend uncertainty under a fresh UUID.

The existing container Stop performs goal-pause best effort and process-group
cancellation/termination, preserving worktrees and histories. Its goal-pause
warning is not proof of a durable scheduling hold. Stopping a current execution
does not by itself prevent a later user/automatic launch or revoke CU leases.

## Tonight's budget and ownership

CU::Track Credit Spending owns accounting and the exhaustion decision. The
authorized aggregate is **this week's remaining allocation + verified banked
rollover + next week's allocation**, with T18 prioritized. No numeric allowance
is invented here; an account wallet or a percentage is not automatically that
sum, and rollover must not be counted twice. CU must provide the verified
components, baseline, spend freshness and exhaustion signal.

CU must coordinate a hold on new admissions, revoke scheduled permissions using
its existing supported control plane, enumerate and stop exact ordinary agent
executions, and read back every result. A bounded enumerated batch alone is not
a complete global hard budget stop. Unknown outcomes remain visible. This
feature does not silently install another spending monitor or change budgets.
Until verified and supervised, the owner allows end-of-turn checkpoints around
8,000 credits; these are cooperative checkpoints, not an exact mid-turn cap.

The existing CU and VK::Staging Check issue descriptions carry coordination
notes. No extra agent or compiler lane was created. The initial seven-lane
inventory included this turn. After a lane freed, an attempted bounded message
to CU was rejected because its existing session had already resumed; no
follow-up was sent. Respect its ownership and the seven-lane ceiling. The release
owner retains the private-reader backend, rollback, compiler and restart window;
its current private build is resource-guarded and not a deployable candidate.

## Validation and deployment gates

```sh
python3 -B -m unittest discover -s scripts/dot-connector -p 'test_*.py' -v
python3 -B scripts/dot-connector/verify_stop_connector.py \
  --source /home/mcp/code/vibe-dot-connector
```

The first run passes 24 connector tests. The installed-source overlay passes
28 existing capacity/Recommend/read regressions, discovery/dispatch and continued
rejection of broad Stop/shell/admin tools. No live calls or state writes occur.
Backend tests cover exact identity, terminal/non-agent rejection, the atomic
completion race, concurrent requests, durable replay/uncertainty, cancellation,
and a disposable `sleep` process. Their hosted execution results are tracked on
[PR264](https://github.com/artinflight/vibe-kanban/pull/264); no user agent is used for testing. Local builds do not take the release owner's compiler window.

Prepare only against the reviewed installed-adapter SHA using
`prepare_stop_connector.py`. Back up and verify the current adapter/shim and
private runtime state before an additive connector-only activation. Preserve
sidechat, approval events, both all-project subscriptions, credentials, Mobile,
Sent Steering and the existing steering overlay's future integration anchors.
Do not deploy a whole backend or frontend from this branch over the release
owner's candidate. The guarded endpoint/migration must enter that coordinated
backend release before a real stop can be available.

Connector activation is not backend acceptance. If initialized while the live
backend lacks the guarded API, tools must report `unsupported` without stopping
anything. Source/tests, GitHub CI, exact installed hashes, post-restart discovery,
backend capability and main Dot's actual tool inventory are separate evidence.
An installed `tools/list` does not establish that the main Dot conversation has
adopted the definitions. Do not ask for pairing, replace credentials or repeatedly
refresh to conceal an inventory propagation problem.

Live read-only preflight confirms the current backend lacks the guarded contract
(it returns the legacy SPA fallback). The connector handles that as unsupported
without a write. CU is actively reconciling the numeric envelope; verified banked
rollover is still unrecovered, so no complete total or hard-budget arming is claimed.

## Verified connector initialization — October 17, 01:57 UTC

Connector **1.4** activated at 01:57:49–01:57:50 UTC from source `70d346699`.
Only `adapter.py` and `stop_control.py` changed, and only
`vibe-dot-connector.service` restarted. Restart/HTTP readiness took **0.774s**;
this is not platform metadata propagation time. The exact installed adapter SHA
is `9f60622a778ec44e5d5e4078561d004905b86057c6f5dc48514e3859bf6b2bf0`;
control SHA is `13c8eff8ccd9a67cc7c56e80c25e55be8daeb675493050dfc9b1cac2092c87f4`.

Source/unit/consistent sidechat backup uploaded to Desktop B, its hash matched,
and download/full offline readback including SQLite integrity passed. These are
private recovery data, excluded from GitHub. Never restore that snapshot over
new conversations. Roll back only the adapter/module after pinning current hashes.

Installed discovery through the real native Vibe MCP upstream advertises both
new controls plus all five sidechat tools. Actual installed readback dispatch to
the live backend returns capability unavailable without a write. Session/access
and subscription hashes, every prior chat message, frontend and sidechat source
pointers and every unaffected service PID remain unchanged. Mobile and Sent
Steering are preserved. No real agent was stopped or launched for testing.

**Real stopping is unavailable until the coordinated backend route/migration
release is accepted.** This is a Vibe backend deployment dependency, not an MCP
cache workaround. The shared admission flag is already enabled; no setting was
changed to bypass the capability gate. A future backend must pass its acceptance
checks before activation; this connector never falls back if it is absent.

**Main Dot availability remains unverified.** The server advertises the controls,
but this coding execution's supplied inventory still lacks them. That inventory
is not an observation of the separate main conversation. Main Dot must expose
both tools and exercise only `get_agent_execution_stop` for a selected target;
no real stop demonstration is authorized. If its catalog is still old, refresh
metadata for this existing connection/version using the supported platform flow
and compare the registered-service discovery requests. Do not replace
credentials, broaden permissions or repeat identical refreshes without evidence.

CU's current turn has pinned a real retained overnight baseline and counts use
already incurred against the interim checkpoint. It reports no verified banked
rollover yet. No complete authorized numeric aggregate or automatic global stop
is claimed here; CU retains that reconciliation and new-admission/lease policy.
Source, test and handoff publication: [PR264](https://github.com/artinflight/vibe-kanban/pull/264).
Current CI conclusions are recorded on that PR without representing preparation
or an installed tool catalog as live/backend/main-conversation acceptance.
