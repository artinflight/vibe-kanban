# Dot attention controls: connector verified, main-session discovery pending

Checked October 16, 2026, 23:29 UTC. Seamus confirms the deployed badges work.
The main Dot conversation still has the older tool inventory, without an
attention argument or attention tool. **Main-conversation attention control is
not yet accepted.** UI acceptance and an internal worker do not establish it.

## Intended Dot workflow

| Operation | Supported connector call |
| --- | --- |
| Ask a question requiring the owner's answer | `append_dot_reply` with optional `attention: "question"` |
| Request a decision or action | `append_dot_reply` with optional `attention: "action"` |
| Flag an existing Dot reply | `set_sidechat_attention` with `action: "question"` or `"action"` |
| Resolve a particular answered/completed item | `set_sidechat_attention` with `action: "resolve"` |
| Reopen a particular item | `set_sidechat_attention` with `action: "reopen"` |

Append retains its exact `thread`, `workspace`, `request`, `body`, `reply_to`
and `event_id` fields. Reuse the same request UUID and original annotation on
retries. Attention updates require the exact `thread`, original `workspace`,
Dot-reply `message` and explicit `action`. Read the thread to obtain the actual
reply identity and current attention state. Never guess a message or workspace.

When the owner answers or completes an action, Dot must explicitly resolve the
corresponding item after establishing that it is satisfied. A new message alone
does not resolve every question. Reading visible replies clears only Dot unread;
attention remains independent. Neither operation clears coding-agent flags.
Old append calls without attention remain valid but cannot create an attention
item. There is no control command embedded in ordinary reply text.

## What the installed connector actually publishes

The configured service uses the installed adapter and its existing sidechat
shim, which imports the current release `7222b127c`. `connector.py`,
`contracts.json` and `sidechat.py` match the public source byte for byte.
The installed facade's local `tools/list` includes all five sidechat tools:

- `list_pending_sidechat_messages`
- `read_sidechat_thread`
- `append_dot_reply`, including optional `attention: question | action`
- `get_sidechat_delivery`
- `set_sidechat_attention`, with `question | action | resolve | reopen`

The adapter dispatches these through its sidechat allowlist before generic
coding-agent write handling. The old local `tool-schemas.json` is an October 4
diagnostic snapshot; the running adapter does not read it. Editing that snapshot
would not update the registered connection.

A repeatable probe exercises the **installed facade**, using an upstream
metadata stub and a disposable store with a synthetic authenticated principal:

```sh
python3 -B scripts/dot-sidechat/verify_attention_connector.py \
  --adapter-directory /home/mcp/code/vibe-dot-connector
python3 -B -m unittest discover -s scripts/dot-sidechat -v
```

Installed discovery, actual facade dispatch, question/action/resolve/reopen,
legacy append, durable read/attention independence, duplicate-reply prevention,
retry state preservation and workspace/identity rejection pass. All 58 sidechat
tests pass. No live store, account credentials, webhook or Vibe mutation is used
by the probe. This proves the installed implementation; it does **not** prove
ChatGPT has adopted its schema in the main conversation.

## Discovery evidence and supported resolution

The registered service remains active from the approved **22:37:17 UTC**
activation. Its method-only journal since activation contains **232 tools/call
requests, zero request failures, zero initialize, zero tools/list and zero
events/list** at this investigation's readback. Its service command selects the
same installed adapter and current source verified above. Calls reach the
updated service, but no post-deployment platform catalog request is observed.
No tool arguments, conversations or receipt identifiers were logged/published.

This is evidence of a discovery gap, not evidence that the server omits the
controls. **No connector compatibility patch is indicated by these checks.**
Adding another tool, bumping a version or restarting the connector cannot make
an unchanged client inventory accept a new argument. Do not work around it by
changing permissions, credentials, subscriptions or interpreting reply text as
an unadvertised write command.

For this directly connected custom MCP service, the supported step is to open
the **existing Vibe MCP for Dot connection** in ChatGPT's plugin/app settings,
select **Refresh**, and verify both the new attention tool and append argument
in the resulting catalog. The earlier 17:54 UTC refresh preceded this release.
This is one refresh of the newly deployed definitions, not repeated refreshing
of an unchanged service. [Official OpenAI guidance describes refresh and
verification of changed metadata](https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata);
[app settings manage tools and refresh their definitions](https://developers.openai.com/api/docs/guides/custom-mcp-server#how-to-use).

Then check the **main Dot conversation**, not just a fresh internal worker.
Using a fresh owner test in the existing paired conversation, Dot must append
one annotated reply, read back its unresolved state, resolve that exact reply
when answered and read back the resolved state. Repeated requests must not
produce another reply. No retained real message should be replayed for testing.

Refresh is the documented metadata remedy, but its sufficiency for this existing
main session remains unverified. Official guidance also tests refreshed tools
in a new conversation; that is a diagnostic comparison, not a substitute for
the requested main-conversation acceptance. If the app catalog updates while
main Dot still lacks the controls, that remaining session-inventory propagation
is outside this connector's control. If refresh produces no tools/list request
on this registered service, escalate the connection/discovery issue with the
deployment/refresh times, these aggregate counts and expected schemas. If a
request does arrive, compare its returned catalog before considering a connector
compatibility change. Do not ask for another identical refresh without evidence.

## Preservation and deployment status

This investigation makes no live source, frontend, service, permission, pairing,
message, attention-state or subscription changes. No restart is needed for the
already-published attention controls. Frontend remains `index-CrPmgoRY.js`, app
version `0.1.42`; Mobile and Sent Steering are preserved.

Read-only live checks confirm two paired sessions, each covering all 43 projects,
and two active, unexpired subscriptions, with exactly one destination for every
current project. Automatic future-project policy remains enabled. At this
readback 25 projects are archived; the earlier rollout recorded 26. This task
did not change project archive status. Private runtime data stays outside GitHub.

Pending: main Dot's supported catalog adoption and its real annotate/resolve
roundtrip. No new pairing, phone UI debugging or activation is required.
