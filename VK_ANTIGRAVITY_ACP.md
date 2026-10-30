# Antigravity ACP readiness — checked 2026-10-30

**Execution remains disabled because authenticated supervised runtime acceptance
has not passed.** This is not evidence that the new backend was never deployed.
The live artifact contains the adapter, registrations, schemas and profiles, but
`ACTIVATION_VERIFIED=false` in `crates/executors/src/executors/antigravity.rs`
rejects launch and discovery returns unavailable. Profiles/environment cannot
bypass that gate. The generic compiled message lists earlier prerequisites;
this document records which ones still apply.

| Original reason                              | Current evidence                                                                   | Outcome                                                            |
| -------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Separate ACP runtime absent                  | Official 1.4.1 runtime is installed; fresh initialize succeeds                     | Resolved                                                           |
| Custom-client support uncertain              | Google's ACP release notes explicitly list custom ACP clients and oauth-personal   | Original blanket concern superseded for the official ACP interface |
| Backend/types unbuilt                        | Repaired live binary contains the adapter;11 native adapter and2 stderr tests pass | Resolved at source/build level                                     |
| Service-user account authentication unproven | `session/new` returns standard ACP AUTH_REQUIRED(-32000)                           | Still blocking                                                     |
| Supervised runtime behavior/resume unproven  | No authenticated session or prompt was available                                   | Still blocking                                                     |
| Model/mode interface compatibility           | Runtime documents configOptions; pinned ACP 0.8 adapter consumes legacy models     | Must verify/adapt before activation                                |

Official sources checked October 30:
[ACP release notes](https://antigravity.google/docs/changelog?ide=vscode&tab=extensions),
[personal-account Zed setup](https://antigravity.google/docs/ide/extensions/zed/),
[official ACP registry](https://raw.githubusercontent.com/agentclientprotocol/registry/main/antigravity-acp/agent.json).
The broader [FAQ](https://antigravity.google/docs/faq) restrictions on wrapping the
`agy` CLI do not establish that Google's separately documented ACP custom-client
interface is unsupported. Do not use CLI wrapping or an API-billing fallback.

Installed executable:
`/home/mcp/.local/share/vibe-runtimes/antigravity-acp/1.4.1/agy_acp_server.par`,
SHA256`57e7c4c505fdc8787993d4ff868274f44fd7aa4e4c82cf424fece3bf6c487643`.
The wrapper is `/home/mcp/.local/bin/antigravity-acp`; Linux launch uses`--uid=`.
The registry currently lists 1.4.5. No runtime update was installed; changing
versions must include source/capacity review and repeat acceptance, not blind retry.

Fresh read-only receipt at 00:03:26 UTC: initialize/protocol 1 passed; oauth-personal,
oauth-business, gemini-api-key and agent-platform advertised; loadSession true;
session creation failed with -32000; authenticate calls 0, prompt calls 0; owned
process reaped. Raw provider output and credential files were not inspected or
published. Being logged into a different desktop application is not proof that
this service-user runtime is authenticated.

## Recheck and activation sequence

1. Use `scripts/antigravity/readiness.py` with the exact executable/hash, a fresh
   dedicated scratch directory on mounted SSD, and a new receipt path. It never
   authenticates or prompts; exit2 means unavailable. Its six synthetic tests
   cover secret suppression, bounds, owned-process cleanup and consumed receipts.
2. Operator completes personal-account sign-in through the existing private
   browser handoff after requesting it. Follow the host runbook
   `/home/mcp/code/Operations/docs/mcp-browser-auth-handoff.md`. Never read/log
   OAuth payloads, browser storage, credential fields or VNC password. Close
   access immediately when sign-in completes. Do not silently select API keys.
3. On the same service-user runtime, validate an authenticated session and the
   runtime's advertised configOptions/model IDs and supervised mode. Implement
   and fixture-test any needed ACP compatibility before enabling the adapter.
   Do not guess model IDs or accept auto_edit/yolo defaults implicitly.
4. In a disposable worktree, exercise one bounded real prompt and tool request,
   approval and denial, cancellation/reaping, native session/load continuation,
   EOF/auth failure and changed runtime/worktree rejection. Keep provider call
   count bounded and retain private receipts. Mock tests alone are insufficient.
5. Only then change the compile-time gate, regenerate affected types, build the
   matched release, rehearse latest-data cutback and deploy through the backend
   protocol. Verify actual public execution and update this checklist/manifest.

Keep automatic provider failover disabled and existing Recommend behavior.
Antigravity entitlement is not the direct Claude, Codex or Gemini-API pool; no
new quota mapping, model fallback or paid account setting was invented here.

The exact original preparation guide is retained in
[deployment history](deployment-history/20261030-before-reconciliation/VK_ANTIGRAVITY_ACP_20261021.md).
