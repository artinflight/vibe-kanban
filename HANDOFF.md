# Backend owner pickup — 2026-10-30

Start with [STATE](STATE.md), [the live manifest](LIVE_DEPLOYMENT.json),
[BACKEND_DEPLOYMENT_HANDOFF](BACKEND_DEPLOYMENT_HANDOFF.md) and
[the evidence checklist](DEPLOYMENT_CHECKLIST_20261030.md).

The new repaired binary is live; this reconciliation branch is not the running
source revision. Do not redeploy it merely to make Git and production hashes
look alike. A public build omits private retained-history bindings and is not
a drop-in replacement. The canonical checkout is dirty; preserve it.

Antigravity requires operator sign-in before actual execution testing. The
readiness probe initializes successfully then receives ACP AUTH_REQUIRED(-32000).
It sent zero prompts. Keep the gate disabled until supervised tool/denial/cancel,
advertised models/modes and bound native resume are proven. Use the private
browser handoff only after the operator requests it; never inspect credentials.

Rollback artifacts and latest-data compatibility evidence are retained. Fresh
idle/writer/capacity ownership and a new backup are required before another
cutover; old controllers are consumed. A 600-second no-progress supervisor and
separate 300-second recovery remain despite removal of the total50-minute cutoff.
Preserve the protected reader, original native homes, uncertain inputs and every
new write. Do not restore the pre-cutover database as a normal rollback.

Detailed prior pickup is retained in [the previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
