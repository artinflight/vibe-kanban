# Deployment validation — 2026-10-30

**New repaired build is live. Antigravity is not ready to enable.**
This checklist separates deployed behavior from source-only preparation and
authenticated provider acceptance. See [manifest](LIVE_DEPLOYMENT.json) and
[handoff](BACKEND_DEPLOYMENT_HANDOFF.md) for exact sources/evidence.

| Check                                   | Outcome           | Evidence / limitation                                                                                                                                        |
| --------------------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| New backend actually serving            | PASS              | Live executable a63eb3a68173…; source ddaaf64a5870…; same PID 2100850 since October 29 promotion                                                             |
| Public frontend paired                  | PASS              | Gateway/public JS index-BBpTkgZU.js and CSS index-CUBB2mA2.css; direct backend root still serves legacy bundle                                               |
| Health and feature contracts            | PASS              | Fresh backend and HTTPS public health, issue-workflow and provider-admission routes return200                                                                |
| Ordinary message409 repair              | PASS, scoped      | 14 native regressions; actual candidate isolated send HTTP200 with synthetic executor; original operator message/history preserved                           |
| Original/recent history                 | PASS at promotion | 18 protected,4 selected recent and2 additional print replies verified; original native homes/reader retained                                                 |
| Stale sub-agent indicators              | PASS at promotion | 1,201 summaries had0 stale active/unresolved badges;69 proven original-metadata repairs;74 historical unresolved rows retained                               |
| Review/settings/queues/uncertain inputs | PASS at promotion | Exact semantic checks;17 uncertain inputs preserved without replay                                                                                           |
| Issue workflow/steering/exact-stop      | PASS, scoped      | Live capability/read-only contracts and prior UI checks;24 steering/stop mocks plus30 current connector fixtures; no new paid-model control test             |
| Latest-data cutback                     | PASS, rehearsal   | New→fallback→new preserved59 app tables/migrations and a later-write sentinel; retained paired fallback and artifacts; future fresh preflight still required |
| Stable native backup/Desktop B          | PASS at promotion | Accepted fenced six-native-DB/eight-rollout capture; independently reopened B objects and terminal receipts                                                  |
| Recovery after total cutoff removal     | PASS, scoped      | 110 recovery/deployment tests pass,22 explicit private/optional skips; real stall/failure/progress and CU ownership tests included                           |
| Antigravity runtime installed           | PASS              | Official ACP 1.4.1 hash verified; protocol 1 initialize and loadSession advertisement observed                                                               |
| Antigravity official custom interface   | SUPPORTED         | Google's ACP changelog explicitly lists custom ACP clients and personal authentication                                                                       |
| Antigravity account/session             | BLOCKED           | Fresh session/new returned AUTH_REQUIRED(-32000); 0 authenticate calls,0 prompts                                                                             |
| Antigravity real tools/resume/models    | NOT VERIFIED      | 11 adapter+2 stderr native tests and6 probe tests pass; configOptions/model/mode, real permission/cancel/resume need authenticated acceptance                |
| Antigravity selectable/runnable         | DISABLED          | Compile-time activation gate remains false; no unsafe enablement or billing fallback                                                                         |
| Automatic provider failover             | DISABLED          | Live capabilities report false; external-effect continuation is unqualified                                                                                  |
| Repository custody                      | PREPARED          | 134 source records,27 incident templates,50 connector files; private input omissions explicitly hash-bound;4 custody tests pass                              |
| Whole-branch CI and merge               | PENDING           | Focused native checks passed; full branch check/lint/workspace CI and staging/main promotion are not claimed                                                 |

No production restart, database rewrite, provider prompt or account setting
change occurred during the October 30 reconciliation. Deployment acceptance
records from October 29 are historical evidence, not fresh permission to reuse
consumed controllers. Antigravity's next required step is operator sign-in,
then the supervised acceptance sequence in [its guide](VK_ANTIGRAVITY_ACP.md).

Local `pnpm run format` and `pnpm run ops:check` passed. Standard `pnpm run check` and `pnpm run lint` stopped at missing `tsc `/`eslint` because this clean worktree has no node_modules. No bulk dependency install or full host workspace build was started; hosted CI is the remaining full-branch check.
