# Current production and protections — 2026-10-30

The repaired new build is serving `https://vibe.local`: backend source
`ddaaf64a5870124842c385e490a0b40e1174db86`, executable SHA256
`a63eb3a68173d90b894bd933b6676d989ec8325d7ba31135ea52b214bd06c336`.
It was promoted October 29 at 22:00:11 UTC. The version label 0.1.42 also identifies
older artifacts and is not proof of deployment. Use [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json)
and fresh readback. Public gateway 4720 serves the paired new frontend and routes
API through the retained history proxy 5640 to backend 5621. Blue stays retired.

The October 29 recovery preserved current database/history/native homes, repaired
proven stale child metadata without erasing historical failures, fixed ordinary
send admission, and rehearsed new→fallback→new with later writes preserved.
[Backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md) and
[deployment checklist](DEPLOYMENT_CHECKLIST_20261030.md) carry evidence and limits.

Antigravity is compiled but deliberately unavailable. The official ACP runtime
is installed and initializes; current session creation requires authentication.
See [the corrected readiness assessment](VK_ANTIGRAVITY_ACP.md). Automatic
provider failover remains disabled. Recommend, saved model/effort/permission,
queue semantics and existing approval controls must be preserved.

Do not replace production with an ordinary public build: private retained-history
bindings and the protected reader are required. Preserve current data, all
uncertain inputs without replay, existing attachment routes, subscriptions,
native sessions, and original histories. Rollback means paired executable/UI
cutback on the latest compatible database, not restoration of a stale snapshot.
Consumed October 29 controllers, PIDs, leases and manifests are historical only.

Builds use an owned shared target on mounted SSD, incremental compilation off,
bounded memory/CPU and fresh capacity checks. Backups go to Desktop B with
verified reopen; bulky staging stays on the mounted secondary SSD. Do not clean
dirty/active worktrees, native histories or attachments to make space.

Current reconciliation is based on fork/staging, isolated from the dirty canonical
checkout. It records deployed source plus public-safe tooling; it is not another
production deployment. Existing storage-admission/automatic-routing activation
gates are not lifted by source custody.

Prior topic map and protections are preserved exactly in
[the previous index](deployment-history/20261030-before-reconciliation/STATE.md).
The original full [STATE history](STATE_HISTORY_20261017.md) remains immutable
and indexed by [CONTINUITY_ARCHIVE.json](CONTINUITY_ARCHIVE.json).
