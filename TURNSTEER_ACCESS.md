# TurnSteer access for Dot — 2026-10-30

## Current availability

TurnSteer is installed and live in the existing Vibe backend and connector. It is
named `steer_session_prompt`, with `get_session_steering_receipt` for reconciliation.
There is no disabled backend feature switch to activate. Fresh local connector
`tools/list` advertises both tools among 46 total. The current ChatGPT conversation
initially exposed only 36, omitting steering, six issue-workflow tools and two
Claude-to-Codex handoff tools. That is a cached client discovery gap, not evidence
that the server implementation is disabled.

The operator refreshed the plugin. A fresh Dot catalog must still be independently
checked; this already-running Codex conversation retains the old schema. Do not
restart Vibe, the connector or any agent to refresh a client catalog.

## Use immediately through existing Dot host access

The installed `/home/mcp/.local/bin/turnsteer` command calls the same installed
connector and native routes. Dot can invoke it through its existing authenticated
MCP-host execution capability; no new agent, listener, credential or service is
introduced. If that particular Dot conversation lacks host execution too, it must
select its already-installed host-access plugin or use a freshly loaded Vibe
connector catalog. Do not claim the caller has tools that are absent from it.

Read target readiness and retained receipts:

```sh
turnsteer target --session-id EXISTING_SESSION_UUID --execution-id RUNNING_EXECUTION_UUID
turnsteer receipt --session-id EXISTING_SESSION_UUID --request-id RETAINED_REQUEST_UUID
```

For an explicit user correction only, generate one request UUID, retain it and
pass the bounded correction text on stdin:

```sh
turnsteer send --session-id EXISTING_SESSION_UUID --execution-id RUNNING_EXECUTION_UUID --request-id ONE_REQUEST_UUID < correction.txt
```

Use the exact currently running CODEX execution. The command resolves its native
thread and turn, checks scheduled-work restrictions and submits at most once.
It does not start, stop or queue a turn, change model/effort/permissions, or consume
an existing queued follow-up. The existing `run_session_prompt` remains a separate
idle-session follow-up command and never implicitly steers.

`status=steered` with `delivered=true` confirms delivery, not completion of the
requested work. A missing/unknown receipt never permits retry with a new UUID.
Reusing an exact request reads its durable receipt first. Identity conflicts and
completed/unsupported/not-ready targets fail without an alternative launch.

## Verification and limits

- Both tools are advertised by the actual installed connector; tunnel health and
  readiness return HTTP 200.
- Live receipt lookup succeeds and returns null for a fresh request UUID.
- Live target lookup correctly reports `not_running` for the completed Disk Space
  execution and preserves `queue_pending=true` for the WakeWatch test.
- All 14 focused steering contract tests pass. Earlier retained native acceptance
  in `scripts/dot-connector/README.md` verified one correction in one real turn.
- This follow-up has not sent a new correction to an unrelated active agent and
  does not claim new model-level steering acceptance or Dot catalog verification.
- Backend, connector and printer service identities remain unchanged.

OpenAI's documented custom-connection refresh flow is at
https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata .
Refresh the existing plugin's metadata, then verify its tools in a fresh
conversation. No server restart is needed here because these tools are already
advertised by the running connector implementation.
