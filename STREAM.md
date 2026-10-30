# Deployment reconciliation and Antigravity readiness

Branch: `fix/deployment-reconciliation-20261030`, based on fork/staging
`2bf2676d2d3841c252fa7f2a9b4e7993128bb093`. User requested investigation,
conditional Antigravity activation, repository custody, commit/sync, checklist
and a reproducible backend-deployment handoff.

Reconciled the deployed backend/frontend/generated source and exact ordinary-send
409 fix without pushing the private candidate's Git ancestry. Public recovery
bindings are intentionally empty; private host acceptance remains mandatory.
Recovered deployment modules and tests, inert exact incident templates, paired
connector source, source catalogs and bounded ACP readiness diagnostics now live
in this branch. No production file/service changed during this reconciliation.

Current native checks:11 Antigravity,2 ACP stderr and14 send-admission tests pass.
Recovery checks:110 pass/22 explicit skips. New source-custody4 and ACP-probe6
tests pass. Connector steering/stop24 and captured-current-contract30 pass.
The old connector start fixture lacked now-required issue scope; the new runner
fixes the fixture without changing captured deployed code.

Authentication is the current Antigravity blocker. Official documentation now
explicitly supports custom ACP clients; the old missing-runtime/custom-client
uncertainty is superseded. No prompt was sent. configOptions/model/mode,
permission denial, cancel/reap and native resume still need authenticated
end-to-end acceptance. The compile-time gate remains false.

See [handoff](BACKEND_DEPLOYMENT_HANDOFF.md), [checklist](DEPLOYMENT_CHECKLIST_20261030.md)
and [live manifest](LIVE_DEPLOYMENT.json). Source sync is separate from a staging/
main merge or another deployment. Keep PR draft until its full required checks
and private release acceptance are complete.

Prior stream retained in [the exact previous record](deployment-history/20261030-before-reconciliation/STREAM.md)
and [STREAM_HISTORY_20261017.md](STREAM_HISTORY_20261017.md).

Local `pnpm run format` and `pnpm run ops:check` passed. Standard `pnpm run check` and `pnpm run lint` stopped at missing `tsc `/`eslint` because this clean worktree has no node_modules. No bulk dependency install or full host workspace build was started; hosted CI is the remaining full-branch check.
