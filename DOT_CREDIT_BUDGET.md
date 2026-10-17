# Dot account-wide credit-budget readback

`get_credit_budget` is a no-argument, read-only connector tool. It reads the
existing CU monitor/history through exactly
`GET http://127.0.0.1:4177/api/credits/budget`. It starts no coding turn, refreshes
no provider, and creates no daemon, credentials, permissions or budget owner.
The fixed HTTP request disables proxies and redirects, uses a five-second
network timeout and accepts at most 64 KiB. Unknown arguments fail before any GET.

The reader implements CU's `account-credit-budget-v1`, `all-account-use` contract.
It preserves decimal strings and nulls without arithmetic or float conversion,
and checks the top-level, weekly and optional overnight observations against
their 60-second validity periods. Stale observations remain explicitly stale;
malformed/unavailable responses return `fresh=false, readback=null` without
private exception details. Account-wide wallet observations are separate from
approved allocations, verified bank and provider settlement.

CU owns reconciliation, historical holds and advance reservation. The current
readback reports its next-week advance reserved in the shared ledger, including
the corresponding future deduction. That is not verified external-controller
enforcement. Bank and combined approved totals remain unknown. Do not reissue
the advance, subtract overnight usage twice, or treat a false stop flag or the
temporary completed-turn checkpoint as extra funding or launch permission.
Readback itself neither reserves funds nor stops agents.

## Cached-tool compatibility for the original CU workspace

Seamus confirmed that main Dot and a fresh read-only worker cannot discover
`get_credit_budget`. Treat standalone discovery as failed. No additional user
check or metadata refresh is required for this compatibility path.

Use the already-discoverable `get_workspace_reconciliation_status` with its
unchanged sole `workspace_id` argument selecting the original CU workspace.
Only that privately bound workspace receives an additive `credit_budget` object:

```text
credit_budget.status                 current | stale | unavailable
credit_budget.fresh                  independent budget observation freshness
credit_budget.readback               complete account-credit-budget-v1 or null
credit_budget.readback.observedAt     CU observation timestamp
credit_budget.readback.expiresAt      CU 60-second expiry
```

All original delivery/hold/receipt fields retain their values and meaning,
including top-level `readback_fresh`. In particular, delivery
`readback_fresh:false` can coexist with `credit_budget.fresh:true`; neither
confirms the other. Other workspaces receive exactly their original response
and do not perform a CU GET. The existing reader runs only after the delivery
store has released its lock. It performs one fixed local GET per matching call,
with no cache, arithmetic, provider poll, new tool/schema, daemon or permission.

The additive preparation helper replaces only the existing status function in
`report_reconciliation.py`, pinned to its installed SHA. Every other AST node,
all tool definitions, adapter, fixed reader, Stop module and release files stay
unchanged. The real CU workspace binding and generated installed module are
private deployment data; the public helper/tests use no real workspace IDs.
Seven compatibility tests plus the existing 25 connector tests pass. They cover
exact preservation, non-CU isolation, stale/unavailable independence, repeated
fresh reads and unchanged argument/UUID validation. Installed old-tool route
acceptance and the exact module hash are recorded in the PR/Vibe handoff.

Atomic file adoption completed at 03:00:25 UTC from runtime source
`c3a301881a88571512ab55a9d72026d6deddaf6b`; installed module SHA256 is
`eb6d1c3c24d50e2457e058d5fda71a17bbe4553bfab2fd39734ed9b944158e0a`.
The retained Python handler had imported the earlier module, so file replacement
alone did not update actual registered calls. The coordinating owner clarified
that connector-only reload was already authorized; the earlier broader restart
restriction was this task's mistaken interpretation.

Only `vibe-dot-connector.service` reloaded at 03:08:04 UTC, with HTTP readiness
in **0.406 seconds**. No other service/agent, new coding worker, Stop, credentials,
network, routing, model, permissions, queued text, browser, compiler or UI work
was involved. All other source hashes/service PIDs and protected ledger/access/
subscription rows were verified unchanged. The retained 32-test candidate and
Desktop B backup were reused; no suite, CI or rebase was repeated.

**Actual registered cached-tool acceptance passed.** Calling the unchanged
`get_workspace_reconciliation_status` through its existing connection returned
nested `credit_budget.status=current, fresh=true`, observed at
03:08:16.960 UTC with a 60-second expiry. The complete exact/null contract was
retained. Every original CU field matched the pre-adoption response, including
`readback_fresh:false`. An unrelated workspace matched the original module's
response against the verified receipt snapshot and had no budget field. Raw
responses and comparisons are retained privately; no real workspace, account or
receipt identifiers are published here.

This existing-tool route has no remaining implementation/activation blocker.
CU can use its cached old tool immediately; no Seamus test, refresh or coding
turn is needed. Standalone `get_credit_budget` discovery remains confirmed failed
in main Dot and a fresh worker, a separate platform limitation. Frozen PR264 and
backend/release source remain untouched by this compatibility change.

## Validation and installation boundary

Eleven new reader/transport/schema tests and the existing fourteen steering
tests pass. Against the installed 1.4 adapter, all 28 existing capacity,
Recommend and status/read regressions pass. Candidate discovery advertises the
new tool exactly once, rejects arguments and broad controls, and preserves both
exact Stop tools, all five sidechat tools and the existing steering overlay's
integration anchors. A fixed live GET returns fresh CU v5 observations; no
private account values or reservation identifiers are published here.

```sh
python3 -B -m unittest discover -s scripts/dot-connector -p 'test_*.py' -v
python3 -B scripts/dot-connector/verify_credit_budget_connector.py \
  --source /home/mcp/code/vibe-dot-connector --live-readback
```

The second command prepares an in-memory overlay against 1.4; after installation,
add `--installed` to check 1.5 without attempting to apply it again. Writes and
agent actions remain mocked. The optional live readback performs only the fixed
CU GET. No real agent is stopped for testing.

Preparation is pinned to installed adapter SHA256
`9f60622a778ec44e5d5e4078561d004905b86057c6f5dc48514e3859bf6b2bf0`.
The candidate adapter is version 1.5, SHA256
`78ad962b59738642168742f670b0740bf6bea96e811d917aa6e8bf1ca978cc60`.
Preserve installed Stop module SHA256
`13c8eff8ccd9a67cc7c56e80c25e55be8daeb675493050dfc9b1cac2092c87f4`.
Back up the current source and mutable state privately, verify Desktop B
upload/download readback, then install only `credit_budget.py` and the additive
adapter at a coordinated connector-only boundary. Never restore an older chat
database over current conversations. Activation and exact installed hashes are
recorded in the PR/Vibe handoff; candidate tests do not establish activation or
the main Dot conversation's adopted inventory.

Staging's prepared steering-over-1.4 candidate is uninstalled. Reconcile it with
the new installed baseline before any later adoption, preserving Budget, Stop,
sidechat, capacity and Recommend. The preparation helpers retain their anchors;
an old pinned adapter must not overwrite a newer installed version.

## Live connector 1.5 — October 17, 02:33 UTC

The requested connector-only activation completed at 02:33:05–02:33:06 UTC
from source `3aea2eabd223d1b316f00907be19d54b1615b18e`.
Only `adapter.py` and `credit_budget.py` changed. Connector restart/HTTP readiness
took **0.409 seconds**; Vibe, CU, frontend, agents and other services were not
restarted. The current adapter hash is the 1.5 hash above; budget module SHA256
is `d8619d2038a7d547c3cf5f60058e9283a262f2be82d71d7b7e91c4446c20bdc4`.
Desktop B backup upload, hash, download, offline file checks and SQLite integrity
passed. All prior chats, protected access/subscriptions, other source modules,
frontend/sidechat pointers and unaffected service PIDs were preserved.

Installed facade discovery using the real native Vibe MCP upstream publishes
exactly one `get_credit_budget`, both Stop controls and all five sidechat tools.
Actual no-argument dispatch returns `status=current, fresh=true` from CU
`credit-weekly-advance-t24-v5` under `account-credit-budget-v1`. Both schema and
annotations are verified: empty object, no additional properties, read-only,
non-destructive, idempotent and closed-world. All backend writes were disabled
in this acceptance. No agent/provider refresh, real Stop, new turn, queued-text,
permission or Recommend change was performed.

**Standalone tool discovery is now confirmed failed in main Dot and a fresh worker.** Installed discovery/readback does not establish platform catalog propagation.
Use the scoped old-tool compatibility path above; no further user test, repeated
refresh or credential replacement is requested.

Staging's steering-over-1.4 hash was reproduced exactly. Applying Budget then
Steering or Steering then Budget yields identical combined 1.5 source SHA256
`2b7dca9f5a41b53f29bce97d1a93fee0fa1503b1cbb79d53dd78ee86446db156`.
That combined steering candidate is **not installed**. Its fourteen current
policy tests plus fourteen steering tests and mocked discovery/dispatch checks
pass. Staging must prepare from current 1.5, preserve the new tool, and retain
its independent release gates.

## Backend Stop dependency and Staging freshness

[PR264](https://github.com/artinflight/vibe-kanban/pull/264) had its completed checkpoint at
`db6bbfcbcf81516b1bbee901fa2cc323bbfdf3e6`. Its final Test workflow passed 599
Cargo tests including all ten Stop tests, plus thirteen scheduling-enabled
persistence tests. Both special acceptance workflows also passed. The PR records
exact CI links and the installed connector 1.4 baseline. At the release owner's later request, a conflict-free normal Staging merge
of `7110930b6d9d1fa3f403a963a1ded49140b3eec1` produced PR264 head
`bf96584b6534fc56f251450636580601227bd8dd`. All four backend Stop files and
Python Stop module are byte-identical to the green checkpoint; newer notes
were preserved. Fresh exact-head CI is tracked on PR264. No local Cargo or
activation was performed for that integration during Nightly's reserved window.
The budget-reader branch remains separate from the Stop backend change.

PR264 is still a release dependency outside the earlier tested PR262/four-private-
bindings baseline. PR262 is now merged into Staging, without live deployment. The release owner retains source review, the combined
rebuild/private binding, all eighteen readers, compatible rollback and backend
acceptance/activation. Installed Stop tools fail closed while the live guarded
backend is unsupported. CU does not claim automatic aggregate Stop enforcement.
Main Dot's actual tool inventory/readback must be observed separately from
installed facade discovery; no repeated refresh, pairing or credential change
is proposed as a substitute.
