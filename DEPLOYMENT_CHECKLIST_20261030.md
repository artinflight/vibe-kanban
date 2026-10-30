# Deployment validation — 2026-10-30

**Antigravity is deployed and available.** New release accepted 03:18:14 UTC;
independent public readback passed 03:20:10 UTC and again at 09:20:33 UTC before
PR integration. Exact runtime identity and limits
are in [the manifest](LIVE_DEPLOYMENT.json); procedure/evidence in
[the handoff](BACKEND_DEPLOYMENT_HANDOFF.md) and [activation record](ACTIVATION_RECOVERY_20261030.md).

| Check | Outcome | Evidence / limitation |
| --- | --- | --- |
| New backend actually serving | PASS | Source 9a4179e8b; binary 137d6cd7b647…; observed PID 645213. Version label alone is not proof. |
| Matched frontend and public routes | PASS | Public JS index-DNMY17oB.js/CSS index-CUBB2mA2.css; backend root corrected; HTTPS bytes match. |
| Existing open tabs | PASS | Both paired roots retain 403 old/new hashed assets; old JS/CSS fetched and hash checked publicly. |
| Desktop/mobile UI | PASS | Actual browser acceptance at 1440/390 widths; UI writes blocked during smoke. |
| Health and feature contracts | PASS | Backend and trusted HTTPS health, issue-workflow and provider-admission routes verified. |
| Antigravity account | PASS | Existing personal account authenticate/session creation acknowledged; viewer closed and browser stopped. |
| Antigravity approved/denied tools | PASS, real native | Approved file created; two denied requests blocked and denied file absent; new assistant marker exact. |
| Antigravity native resume | PASS, real native | Same native session; exact marker in new assistant output, not replay/tool output. |
| Antigravity cancellation | PASS, real native | Pending approval cancelled; file absent and process reaped in 0.0403 s. |
| Antigravity available in live build | PASS | Backend and public API report INSTALLATION_FOUND, gemini-3.8-flash-low and SUPERVISED. |
| Provider QA scope | BOUNDED | Four real model turns total. Actual Vibe adapter exercised in isolated worktree; no new production workspace conversation or additional post-deploy inference. |
| Ordinary message 409 repair | PASS, scoped | 14 native regressions and prior isolated send HTTP 200; operator confirmed original message started. Repair retained in deployed source. |
| Current DB, histories and settings | PASS | Same DB/native homes, 99 migrations, 18 protected/four recent histories; exact settings/review/queue checks. |
| Uncertain inputs | PRESERVED | All 17 retained without replay; no invented completion. |
| Stale sub-agent indicators | PASS at prior repair | 1,201 summaries had no stale active/unresolved badges; 69 proven metadata repairs; 74 historical unresolved rows retained. No new blanket deletion. |
| Latest-data cutback | PASS, fresh rehearsal | New→working incumbent→new preserved 60 tables including later-write probe; both frontend pairs retained. Future work/schema changes require recheck/drain. |
| Native and application backup | PASS | Application SQLite plus six native DBs/nine changed rollouts on Desktop B; native total 3,607,837,269 bytes. Unchanged-image proof reuse explicitly does not claim a new capture. |
| Failure recovery | PASS, actual event | First checkpoint refusal recovered original PID/public service/owned consumers with data_restored=false; exact empty-WAL cause reproduced and fixed. |
| Stall recovery after cutoff removal | PASS, scoped | 600 s verified-no-progress watchdog and separate 300 s recovery; 130 offline checks pass, 22 private/optional skips. No total 50-minute cutoff. |
| Consumers and protected reader | PASS | Owned consumers resumed; original CU process and protected history reader preserved. |
| Source/tooling custody | RECONCILED | 134 historical source records, 27 inert incident templates, 50 connector files, new activation/recovery/backup/rehearsal tooling and tests. Private bindings stay outside Git. |
| Branch validation | PASS at a421381321 | All eight hosted workflows passed, including final recovery/mirror tooling; [exact runs and coverage limits](BACKEND_DEPLOYMENT_HANDOFF.md#hosted-validation-and-source-integration). Later documentation commits require their own PR checks. |
| Release and recovery evidence on Desktop B | PASS | 45 sealed release items / 201,792,843 bytes plus 62 terminal/reconstruction items / 7,944,662 bytes independently verified; 53 fallback-only assets retained. |
| Automatic provider failover | DISABLED | External-effect continuation remains unqualified; existing Recommend behavior preserved. |

The first activation was aborted before binary replacement and recovered normally.
The corrected fresh package succeeded. The immediate fallback is the previously
working October 29 build (`ddaaf64a`/`a63eb3a68173…`) using latest compatible data;
Antigravity execution is disabled on that fallback. Never restore an old snapshot
over later writes or stop new executions automatically to roll back.

No further operator login is needed. Refresh Vibe once to pick up the new frontend.
[PR #284](https://github.com/artinflight/vibe-kanban/pull/284) contains source and
operational reconciliation, targeting staging by the operator-requested rebase
method. Its merge event records final integration status and rebased IDs. Main
promotion is separate; original build identities and the fallback remain retained.
Private remote CI without deploy credentials and combined capture consent acceptance
were skipped, not certified.
Top-level service memory limits remain unchanged/unlimited; executor limits and
capacity guards remain separate. AG reset/fork and non-supervised modes are unsupported.

## Feature activation follow-up — 2026-10-30

| Feature / check | Outcome | Current evidence and remaining limit |
| --- | --- | --- |
| WakeWatch automatic disk dispatch | ENABLED | Explicit connector transport selected at 11:38:59Z; existing timer readback and live owner/config readiness passed. Native v2 remains separately disabled. |
| WakeWatch actual model reply | PASS, live | The single test completed at 12:00:07Z; execution 02f6a6f4-46d5-4939-9fdb-b86107522752 returned exactly WAKEWATCH_READY_4f2df84a. No resend or cleanup. |
| WakeWatch source tests | PASS | All 185 watcher tests, including queue/lost-ack no-resend and protected-infrastructure inventory. |
| TurnSteer backend/connector | AVAILABLE | Both tools in live discovery, real target/receipt GETs pass, all 14 steering tests pass. Existing native acceptance retained; no fresh unrelated-agent correction. |
| TurnSteer caller discovery | PASS | Operator refresh took effect: this client now exposes all 46 tools including both steering tools. A real receipt lookup through the refreshed tool succeeded. No new live correction was sent. |
| Issue workflow creation/linking | AVAILABLE | Live capabilities v1, atomic reservation, conditional relink and durable launch receipts; all six tools now exposed in this refreshed client as well as server discovery. No new issue created for this check. |
| Claude-to-Codex handoff | AVAILABLE, guarded | Both handoff tools now exposed in this refreshed client; verified checkpoint dispatch required. No blind automatic provider failover. |
| Scheduled native goal first run | ENABLED | Authenticated live capacity API reports scheduledGoalInitialization=1 and targetedStop=true. |
| Automatic Git synchronization | ENABLED | Running backend has VK_AUTOMATIC_GITHUB_SYNC=1; existing ownership/preservation gates still apply. No publication generated for this check. |
| Eight-execution capacity limit | ACTIVE | Authenticated capacity API reported eight running executions during the probe's wait. This is admission control, not a disabled feature. |
| Automatic provider failover | NOT READY | Live contract explicitly reports false and external_effect_resume_qualified=false; no safe activation switch is claimed. |
| Recovery cleanup / PR monitor | HELD | Existing recovery flags remain; no worktree deletion or unrelated monitoring activation performed. |
| Restarts / original runtime | PASS | Backend, connector and printer PIDs and invocation IDs unchanged; no daemon reload or restart. |
| Client rollback | VERIFIED BACKUP | Seven original modules/private config retained on SSD and in an independently hash-verified 51,142-byte Desktop B archive. Reconcile outstanding deliveries before reverting; preserve current ledger/data. |

Read [WakeWatch recipe](scripts/watcher-events/CONNECTOR_TRANSPORT.md) and
[TurnSteer access](TURNSTEER_ACCESS.md). New capability availability is distinct
from an agent's cached tool catalog and from permission to perform a destructive action.
