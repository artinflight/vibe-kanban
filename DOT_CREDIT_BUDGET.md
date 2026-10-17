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

## Frozen backend Stop dependency

[PR264](https://github.com/artinflight/vibe-kanban/pull/264) is frozen at
`db6bbfcbcf81516b1bbee901fa2cc323bbfdf3e6`. Its final Test workflow passed 599
Cargo tests including all ten Stop tests, plus thirteen scheduling-enabled
persistence tests. Both special acceptance workflows also passed. The PR records
exact CI links and the installed connector 1.4 baseline. This budget-reader
stream does not amend, merge or activate that backend source.

PR264 is still a release dependency outside the prepared PR262/four-private-
bindings baseline. The release owner retains source review, the combined
rebuild/private binding, all eighteen readers, compatible rollback and backend
acceptance/activation. Installed Stop tools fail closed while the live guarded
backend is unsupported. CU does not claim automatic aggregate Stop enforcement.
Main Dot's actual tool inventory/readback must be observed separately from
installed facade discovery; no repeated refresh, pairing or credential change
is proposed as a substitute.
