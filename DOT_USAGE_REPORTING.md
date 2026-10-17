# Dot read-only CodexUsage reporting

The existing CU owner supplies the recorded-data helper and owns accounting
reconciliation. This stream supplies the connector schema, registration,
compatibility, tests and connector-only adoption. Reporting is independent of
the separate backend exact-Stop release. It cannot stop agents, grant work,
reserve credits, change settings or trigger provider/model calls.

## Supported query

`get_usage_report` accepts these optional arguments, with no additional fields:

| Argument | Supported values |
| --- | --- |
| `window` | `since_reset` (default), `day`, `week`, `custom` |
| `from_time`, `to_time` | RFC3339; `custom` requires `from_time`; optional `to_time` pins any window |
| `group_by` | `workspace` (default), `project`, `session`, `execution`, `model` |
| Entity filters | `project_id`, `workspace_id`, `session_id`, `execution_id`: UUIDs |
| `model` | Exact model name, at most 128 characters |
| `limit`, `offset` | 1–100 rows (default 50); offset 0–100000 (default 0) |

Custom intervals are half-open `[from,to)`, positive and at most 31 days. Day
and week use UTC. Pin the report's returned cutoff for stable pagination;
unpinned live snapshots may change as CU records new observations.

CU's `cu.dot-report.v1` distinguishes unfiltered `accountTotals`, filtered
`selectedTotals`, and paginated grouped `rows`. Input includes cached input;
output includes reasoning. Different groupings describe the same usage and
must not be added together. Missing components/attribution stay unknown with
known subtotals; no coverage is not evidence of zero usage.

Provider allowance/reset windows and locally recorded token windows are
different evidence. Freshness, observation cutoff and requested-window coverage
are reported independently. Recorded-source coverage does not prove complete
provider billing. Costs retain their actual saved source and scope; organization
API billing is separate from Codex subscription/credit billing. Tokens are never
converted into billed credits. The existing credit reader and budget fallback
retain their own freshness and exact decimal/null contract.

`get_usage_summary` accepts exactly `{}` and returns the bounded default
account/reset-window projection. Full reports are limited to 256 KiB; summaries
to 16 KiB. Invalid selectors fail before data access. Unavailable, invalid or
oversized responses fail explicitly without exposing private diagnostics or
inferring usage, cost or allowance.

## Existing cached tool

Only the privately bound original CU workspace's existing
`get_workspace_reconciliation_status({workspace_id})` receives an additive
`usage_report` summary. Its sole input and tool schema remain unchanged. This
avoids depending on new-tool catalog propagation for the default summary.
Other workspaces do not read CU reports and retain their original response.
Existing receipt, hold, delivery and `credit_budget` fields retain their meaning;
top-level delivery `readback_fresh` is independent of
`usage_report.freshness.fresh` and `credit_budget.fresh`.

The status path performs only the default bounded summary, with at most five
rows. It accepts no hidden query parameters or encoded selection in workspace
IDs. Selectable full reports require the named tool to be in the caller's
adopted catalog. Installed discovery/dispatch is recorded separately from an
actual registered call; publication alone does not prove main Dot adoption.

## Validation and adoption

`prepare_usage_reporting.py` requires exact installed adapter and status hashes,
and a private CU binding. Existing routing/read/write functions and existing
tool schemas must compare unchanged. The preparation does not install anything.
CU's pinned helper and its fixed sibling budget reader are installed alongside
the wrapper; tool callers supply neither source paths nor SQL, URLs or commands.
Only fixed existing SQLite/cache data and the fixed local credit GET are read.
No credentials, network/permission expansion, daemon or new reporting owner is
introduced. Prompts, tool logs, raw paths and private receipts are excluded.

Before activation, retain and verify the current connector source and receipt
backup on Desktop B. Adopt only the reporting source files, then reload only
`vibe-dot-connector.service` through the established route; its persistent Python
handler otherwise retains old imports. Vibe, CU, backend, publisher, browser,
frontend and workspace agents remain running. Rollback restores only the prior
connector source and reloads the same unit; never restore old chat/receipt data
over new writes. Existing subscriptions and paired access stay untouched.

Current candidate: 45 light Python tests and 28 installed-policy/read regressions
pass, including unchanged schemas, CU-only isolation, independent stale state,
null/exact-value preservation, input bounds and denied controls. `pnpm run format`
was attempted: Rust formatting passed; frontend formatting stopped because
Prettier is absent. No UI dependencies or compiler work were added. Final helper pin, installed acceptance and catalog status follow below.


## Live baseline and earlier catalog dependency

Connector **1.6** was adopted at **2026-10-17 10:47:43 UTC** from connector
source `6ca6c443dee0cda63fee1a271f91de25d3ae7624` and CU helper source
`64e253b6e863b7c3720aaf052270298fa596df67`. Only the connector service
reloaded; readiness took **0.363 seconds**. Other tracked services, existing
source modules, protected receipt/hold/access/pairing/subscription rows and the
frozen Stop branch were verified unchanged. The private Desktop B source/data
rollback was retrieved and checked byte for byte, with SQLite integrity passing.

| Installed module | SHA256 |
| --- | --- |
| `adapter.py` | `3a590169b3b84ddfabf31be2d0fa29729752be0deabcec1c00ce4f6df593d1fb` |
| `report_reconciliation.py` | `48e63ee6ff5cd67f225557f1b0267b01ad5fb97d58c46743b0331165bb5df4df` |
| `usage_reporting.py` | `a47ee6225a6a4b1237e8f5d861ff5b502df48572b0059eb290cb7d0148f587cd` |
| `dot_usage_report.py` | `92b2b3b7d869064f1d60ad601194273da62ebb10690f7f2a0b2c2880cb9db465` |
| `dot_credit_budget.py` | `2b67e251f87a35ee59420b74e919544143e30ae746b52192ff166fcff07b319c` |

The actual cached registered status tool returned `usage_report` with
`cu.dot-report.v1`, `status:recorded`, token freshness true, requested-window
coverage true, and five bounded rows. The original delivery fields matched the
pre-adoption response exactly, including `readback_fresh:false`. The original
credit field kept its own stale state. The unrelated workspace response was
unchanged and had no reporting field. Root independently confirmed this same
cached path. Observations are dated evidence; callers must read anew for advice.

Real installed discovery and dispatch through the native MCP upstream passed
for both `get_usage_report` and `get_usage_summary`, with recorded, fresh,
covered data. This is separate from actual main Dot adoption of the new names.
Both this execution and root's independent check still lacked those names in
`ALL_TOOLS`. Registered calls reached the new service, but its recent journal
showed calls and **no `tools/list`, `events/list` or external `initialize`** since
activation. This supports a platform catalog discovery/adoption dependency.
Main Dot's selectable named-tool dispatch is therefore **unverified**. No user
refresh/testing, credential replacement, invented forwarding route or new worker
is requested. The existing cached summary works now. Full selectable reporting
still needs supported platform catalog propagation and a named registered call.

## Prepared optional-cutoff compatibility correction

CU's final contract allows `custom` with `from_time` alone: the helper uses its
latest existing scan cutoff. The wrapper correction accepts that shape without
inventing an end time. Explicit cutoffs remain ordered and capped at 31 days;
when omitted, CU validates those bounds against the actual recorded cutoff.
The focused regression passes, for 13 reporting tests / 45 connector tests in
scope. The pinned CU helper's 24 report tests also passed independently here;
CU reports 32 including its eight incumbent credit tests.

The corrected wrapper SHA256 is
`ef7dfaa869377f833e7fa95a915a70f702085b6147794646cc80393db88d8472`.
It is **prepared and not installed**: the live wrapper remains `a47ee622...` and
currently requires an explicit end for `custom`. Staging requested the newly
verified baseline be sealed without another reload while it reconciles the
prepared steering overlay. This narrow correction needs only its next coordinated
connector-only adoption/reload, independently of the backend Stop release.
It does not affect the working cached summary or require CU/backend changes.
Preserve the current 1.6 adapter/status/helper hashes when preparing that overlay;
the old 1.5/steering-only pins are superseded.


## Registered tool adoption verified after the 10:58 refresh

The refresh reached the same updated connector at **2026-10-17 10:58:17 UTC**:
its journal records `server/discover`, `tools/list` and `events/list`, without a
request failure in that discovery window. Runtime 1.6 and all sealed source
hashes remained unchanged; no restart, activation, credential or permission
change was needed.

By the next preservation execution, both report names were present in its
**callable adopted catalog**. Actual registered connector calls succeeded for
`get_usage_summary` and `get_usage_report`. This supersedes the earlier absence
claim for this execution; it is more than a server-side discovery/dispatch test.

The registered full-query acceptance used an explicit custom window pinned to
CU's recorded cutoff, a model filter, workspace grouping and one row per page.
Page two used the returned next offset and the same cutoff. Both calls returned
recorded, fresh, covered data; distinct rows matched the filter; unfiltered
account totals and filtered selected totals remained identical between pages;
the filter reduced selected usage without changing the account denominator.
Actual registered page calls completed at 11:03:05 and 11:03:16 UTC. Raw private
responses and comparisons are retained outside GitHub. No account totals or
private workspace/session/receipt identifiers are published here.

This verifies named reporting through the registered connection in the
preservation conversation. It does **not** prove an already-running separate
main Dot conversation has adopted the new catalog. If that retained conversation
still lacks the names, its per-conversation catalog is platform-managed; this
connector owner cannot invalidate or replace it through the supported tools.
The successful 10:58 discovery plus actual registered named calls support a
catalog-propagation explanation, not a missing or inaccessible server tool.
Do not ask Seamus to repeat the same refresh or replace credentials. The existing
CU status summary remains available, and no backend Stop release is involved.

For coordinated main Dot acceptance, use the named full tool with an explicit
start/end, model or project filter, grouping and `limit:1`; then use the returned
`pagination.nextOffset`, keeping every selector and cutoff unchanged. Compare
rows, account/selected totals, coverage and independent credit freshness. Record
that caller's actual results separately before claiming retained-main-conversation
adoption. The optional omitted-custom-cutoff correction above remains prepared
only and is not required for this explicit-cutoff acceptance.
