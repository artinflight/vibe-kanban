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
| `from_time`, `to_time` | Explicit RFC3339 timestamps, both required for `custom` only |
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

Current candidate: 43 light Python tests and 28 installed-policy/read regressions
pass, including unchanged schemas, CU-only isolation, independent stale state,
null/exact-value preservation, input bounds and denied controls. `pnpm run format`
was attempted: Rust formatting passed; frontend formatting stopped because
Prettier is absent. No UI dependencies or compiler work were added. Final helper
pin, installed acceptance and catalog status are recorded below when verified.
