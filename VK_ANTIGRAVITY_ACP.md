# Antigravity ACP — verified October 30, 2026

The original authenticated-execution blocker is resolved. The existing personal
account passed the real Vibe ACP adapter's supervised write, denial, native resume
and cancellation checks. The activation release enables installation discovery
and supplies the verified runtime/model through service-scoped defaults. Consult
[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json) for the actual running release;
[the checklist](DEPLOYMENT_CHECKLIST_20261030.md) distinguishes live verification
from the isolated provider exercise.

| Original reason | Evidence and disposition |
| --- | --- |
| Separate runtime absent | Official ACP 1.4.1 installed and hash verified; resolved. |
| Custom-client support uncertain | Google's ACP documentation explicitly supports custom clients and personal authentication; resolved for this interface. |
| Service-user authentication unproven | Cached personal-account authenticate acknowledged and session created at 01:12:16 UTC with browser opening disabled; resolved. |
| Model/mode compatibility | Six advertised legacy model IDs; tested `gemini-3.8-flash-low`; acknowledged `default` supervised mode explicitly selected on new/load. |
| Approval, denial, resume and Stop unproven | Actual Vibe adapter acceptance passed; resolved for the tested runtime/model and supervised mode. |
| Build/activation omitted | Matched backend/frontend built, generated schema checked, latest-data cutback rehearsed; exact live outcome in the manifest. |

Official sources checked October 30:
[ACP release notes](https://antigravity.google/docs/changelog?ide=vscode&tab=extensions),
[personal-account setup](https://antigravity.google/docs/ide/extensions/zed/),
[official ACP registry](https://raw.githubusercontent.com/agentclientprotocol/registry/main/antigravity-acp/agent.json).
Do not wrap the unrelated `agy` CLI or silently substitute API-key billing.

## Installed and tested pair

Runtime: `/home/mcp/.local/share/vibe-runtimes/antigravity-acp/1.4.1/agy_acp_server.par`,
SHA256 `57e7c4c505fdc8787993d4ff868274f44fd7aa4e4c82cf424fece3bf6c487643`.
Co-shipped `localharness_external`, SHA256
`5ba6f2f24faffa6bceaf9344871ccc8624ebeccb27a7d0d45a9ffdda851d72c7`,
is a required runtime dependency. The wrapper is
`/home/mcp/.local/bin/antigravity-acp`; Linux launch uses `--uid=`.
The registry advertised 1.4.5; this task deliberately retained tested 1.4.1.
A runtime update needs fresh bounded acceptance.

The selected service environment is:

```ini
Environment="VK_ANTIGRAVITY_ACP_EXECUTABLE=/home/mcp/.local/share/vibe-runtimes/antigravity-acp/1.4.1/agy_acp_server.par"
Environment="VK_ANTIGRAVITY_ACP_MODEL=gemini-3.8-flash-low"
```

Explicit saved-profile executable/model values take precedence. Existing profiles
were not rewritten. Availability reports `INSTALLATION_FOUND`, never a fabricated
login timestamp or entitlement. Discovery performs no credential read or process
launch. Launch still requires the interactive approval bridge and supervised
permission policy. `auto_edit`/`yolo`, reset/fork and custom agent/reasoning/mode
options remain unsupported. Automatic provider failover remains disabled.

## Actual native acceptance

Private receipt: `vk-deployment-reconcile-20261030/native-account-5/RESULT.private.jsonl`
on mounted SSD. Test source `a9e403eae34bfca0c1da4cc55a24f61b95e44fc0`; executable SHA256
`b8c23f7d6ee49674cf22d3760bbf83131782cd8dbf334ec60f271cb96fd316cf`.

- First final-fixture turn completed successfully, performed the one explicitly
  approved file creation, denied two requests, left the denied file absent and
  returned the exact fresh test marker in new assistant output.
- Second turn loaded the same native session and returned the exact marker in
  new assistant output after the user event. Replayed history/tool output could
  not satisfy the assertion. Cancellation while approval was pending stopped
  the turn, left the requested file absent and reaped the process in 0.0403 s.
- Four model turns were used in total, the disclosed ceiling. Earlier fixture
  turns proved denial/read behavior but were not counted as a complete pass.
  Pre-session allocator/harness failures used no prompts. No more inference is
  authorized by this test budget; post-deployment readbacks use no prompts.
- The real provider exercise used Vibe's actual `AcpAgentHarness` in an isolated
  worktree. It was not a new production workspace conversation. Production API
  availability/model checks are a separate, non-inference acceptance layer.

`run_native_acceptance.py` pins test/runtime/harness hashes, binds the existing
credential read-only, admits only its new SSD output as writable, holds the
shared build lock and bounds/reaps its process group. The official runtime needs
read-only `/sys/devices/system/cpu/possible` and `present` for its allocator.
Never copy or inspect credential contents. Use `--help` for required bindings.
Ordinary CI skips the opt-in provider test and cannot spend the account quota.

## Headless authentication and diagnostics

The operator completed existing-account sign-in. Both temporary viewer sessions
are closed/stopped; profile retained. No further login is required for this
release. MCP is headless: SSH does not display a browser. Future explicitly
requested sign-in uses `/home/mcp/.local/bin/mcp-browser-auth` and the Operations
browser-handoff runbook, dedicated display/profile, loopback listeners and
bounded tailnet-only access. The one operator-authorized passwordless exception
was temporary; the shared helper/password file was not changed.

`scripts/antigravity/operator_auth.py` authenticates only `oauth-personal`, requires
acknowledgement before session creation, sends no inference, rejects unexpected
tools, discards raw output and reaps its owned runtime. Thirteen offline tests
cover auth/readiness privacy, optional successful ACP `_meta`, bounds and cleanup.
The observed callback expired after roughly 303 s; an expired loopback callback
caused the unreachable-local-page report. A verifier also incorrectly rejected
valid `_meta` success responses; that was fixed. Authentication and browser sign-in
are distinct. Never use credential files, cookies, storage, screenshots or login
payloads to guess readiness. Close viewer access immediately after confirmation.

`scripts/antigravity/readiness.py` initializes without authenticating or prompting.
An AUTH_REQUIRED response before the personal handshake is not proof that cached
credentials are missing. A successful empty session does not itself prove tools,
resume or cancellation; use the bounded native acceptance when those need a
fresh qualification. Keep receipts containing session identifiers private.

## Deployment and cutback

Use the matched binary/schema/frontend plus the exact private 16-entry retained-
history input. The production compile-time activation gate must match its recorded
binary, not merely the current checkout. The activation controller verifies
`INSTALLATION_FOUND`, `gemini-3.8-flash-low` and `SUPERVISED` before acceptance.
Keep the existing account, native home, approval bridge, Recommend behavior and
all current database/history paths.

The immediate fallback is the working October 29 `ddaaf64a` release, which already
recognizes the Antigravity executor but has activation disabled. Fresh-copy
new→fallback→new testing preserved 60 tables including the later-write probe,
18 protected and four recent histories. Both paired frontends retain both sets
of hashed assets for open tabs. Cut back software against the latest compatible
state; never restore an old DB over new work. After new executions or schema
changes, recheck compatibility and drain work before cutback. The older `d154fe9d`
artifact remains retained but is not the newly qualified immediate fallback.

Original guide: [archived preparation record](deployment-history/20261030-before-reconciliation/VK_ANTIGRAVITY_ACP_20261021.md).
