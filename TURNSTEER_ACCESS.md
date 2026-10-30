# TurnSteer access for Dot — 2026-10-30

## Current availability

TurnSteer is live in the existing Vibe backend and connector. Its tools are
`steer_session_prompt` and `get_session_steering_receipt`. No backend enable
switch was missing. The operator's plugin refresh succeeded: this client now
exposes all 46 Vibe tools, including both steering tools, six issue-workflow
tools and two Claude-to-Codex handoff tools. A read-only receipt lookup through
the newly exposed plugin tool succeeded. No Vibe, connector or agent restart
was needed.

## Use from Dot

Select the exact running CODEX execution using the existing execution/status
tools. Only for an explicit user correction, call `steer_session_prompt` with
its exact session ID, execution ID, one retained request UUID and the correction.
Use `get_session_steering_receipt` with that same session/request to reconcile.

`status=steered` with `delivered=true` confirms delivery, not completion of the
requested work. Missing or unknown receipts never permit a new request UUID.
A matching repeated request reads its durable receipt first. Completed,
unsupported or unready targets cannot trigger an alternative launch.

Steering preserves existing queued prompts, model/effort/routing and permissions.
Never substitute stop/start or `run_session_prompt` for an active-turn correction.
The latter is an idle-session follow-up command, not steering.

## Alternative from an authorized local shell

The installed `/home/mcp/.local/bin/turnsteer` calls the same connector and native
routes. It needs local filesystem and loopback-network access. Dot's separately
exposed `codex_host_exec` is read-only with network disabled; that tool cannot run
these API operations. Use the refreshed Vibe tools in Dot. Do not expand host
permissions or claim a shell entrypoint alone bypasses the caller's sandbox.

Read target readiness and retained receipts:

```sh
turnsteer target --session-id EXISTING_SESSION_UUID --execution-id RUNNING_EXECUTION_UUID
turnsteer receipt --session-id EXISTING_SESSION_UUID --request-id RETAINED_REQUEST_UUID
```

For an explicit user correction only, retain one request UUID and pass bounded
text on stdin:

```sh
turnsteer send --session-id EXISTING_SESSION_UUID --execution-id RUNNING_EXECUTION_UUID --request-id ONE_REQUEST_UUID < correction.txt
```

The CLI resolves native thread/turn binding, checks scheduled-work restrictions
and submits at most once. It never starts, stops or queues a turn.

## Verification and limits

- Both tools appear in this refreshed client's actual tool catalog, matching all
  46 advertised by the installed connector. Tunnel health/readiness returned 200.
- A real plugin `get_session_steering_receipt` call returned null for a fresh UUID,
  as expected. This validates tool routing without sending an agent correction.
- Earlier live target lookup correctly reported `not_running` for a completed
  execution while preserving the then-pending WakeWatch queue. That WakeWatch
  test subsequently completed; the old target observation is not current state.
- All 14 focused steering contract tests passed. Retained native acceptance in
  `scripts/dot-connector/README.md` verified one correction in one real turn.
- No new correction to unrelated user work or fresh model-level steering
  acceptance is claimed by this follow-up.
- Backend, connector and printer service identities remain unchanged.

For another stale client, OpenAI documents the custom-connection refresh flow:
https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata .
Refresh the existing plugin and verify discovery in a freshly loaded conversation.
Server restarts are unnecessary when the connector already advertises its tools.
