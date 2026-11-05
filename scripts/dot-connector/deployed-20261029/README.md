# Deployed connector source custody

This snapshot records the adapter and its Python/Node companions serving the
October 29 release, plus the paired sidechat implementation. `sources.json`
binds each public file to its deployed bytes. One private usage-workspace binding
is a placeholder; its value remains in the host's private reconciliation receipt.
Do not install a placeholder-bearing file or copy this directory over production.

The adapter also requires the retained MCP executable, Node 24, the existing
authenticated tunnel/approval-event bridge, and existing service configuration.
Keys, subscriptions, receipt databases, account files and provider histories are
deliberately excluded. The `sidechat_connector.py` shim points at the installed
paired sidechat release. The public snapshot is source custody, not a second
connector or a new notification publisher.

The historical adapter discovery test predates the additive tools. The current snapshot runner updates the obsolete Recommend start fixture with
required issue context and checks additive discovery, capacity and reply reads;
steering/stop tests cover the separate control contract;
do not confuse this old test inventory with fresh full-connector acceptance.
See [the backend handoff](../../../../BACKEND_DEPLOYMENT_HANDOFF.md) for current
validation and the fresh-baseline installation procedure.
