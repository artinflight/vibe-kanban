# Dot discovery discrepancy — 2026-10-16

## Finding and limits

The existing connection reaches the updated connector. A read-only pending-context
call through the registered Vibe MCP plugin succeeded at 18:00:50–18:00:51 UTC,
and the running service logged its `tools/call` at 18:00:51.264011 UTC. It returned
one unanswered message with complete exact routing context. No conversation text
or private event/thread/message/receipt identifiers are included here.

The coding execution's new turn now exposes all four sidechat tools, including
`list_pending_sidechat_messages`. This differs from the reported root inventory
(no sidechat tools) and earlier fresh internal worker (three original tools).
It proves that recovery is callable through the registered connection in this
execution. It does not prove that an existing root has received those tools.

The configured installed facade advertises the complete event schema. The
reported root/worker view still has the old two-filter definition. The evidence
points to platform metadata propagation or conversation-inventory selection, but
does **not** identify an exact cache component. The platform's stored catalog,
metadata review/import state and per-conversation binding are not exposed here.
Do not label an unobserved internal cache as a proven root cause.

## Evidence

| Check | Observed result |
| --- | --- |
| Approved module source | `d2c79543ea373680da79944bd98756639d23cc0c`; all seven installed file hashes match the activation receipt |
| Connector process start | 17:48:51 UTC, before the reported 17:54 Refresh Tools action |
| Running tunnel | Same identity as the configured unit; exactly one local client for that identity; running executable matches installed binary |
| Tunnel version | `0.0.15+a390c168ff1b2d14e73a95991c186c6aba3ff5a0` |
| Readiness | Documented loopback health/readiness endpoints return 200; dispatcher/response delivery report zero failures/timeouts/retries |
| Discovery received | `server/discover` at 17:53:53.087050, `tools/list` at 17:53:53.302756, `events/list` at 17:53:53.465780 UTC |
| Request process | All three discovery requests and the later registered pending-tool call were logged by the same adapter child in the same service cgroup |
| Advertised capabilities | `tools` and `events`, using the existing configured owner/state settings |
| Configured facade `events/list` | Successful result, one sidechat event, no RPC error |
| Sidechat tools | `read_sidechat_thread`, `append_dot_reply`, `get_sidechat_delivery`, `list_pending_sidechat_messages` |
| Sidechat event filter properties | `thread_id`, `project_id`, `project_ids`, `all_projects`, `exclude_project_ids` |
| Required event alternatives | One thread, one project, an explicit project list, or `all_projects: true` together with explicit exclusions |

The journal intentionally logs only method names and error classes, never request
arguments or response bodies. Thus the three 17:53:53 requests are observed in the
reported refresh window, but the local journal cannot tie them to a particular
ChatGPT click/request ID or prove what catalog the platform stored afterward.
It also cannot independently identify the affected root's registration record.
The registered coding-plugin call reaches this updated service; a duplicate local
tunnel or wrong local release was not found. Platform support must correlate the
root's actual app/connection record with these timestamps.

The facade probe imports the exact installed adapter/modules, supplies only the
running adapter's named owner/state settings (including systemd drop-ins), and
calls the real event-list handler. Its upstream tool provider is inert: only the
additive sidechat metadata is asserted, not the complete upstream tool list.
It does not start another tunnel, invoke coding agents, replace credentials,
change permissions or create subscriptions. This probe is distinct from a capture
of an already-completed platform response.

Canonical SHA256 values for reproducing the comparison (UTF-8 JSON, sorted keys,
compact separators):

- Sidechat tool descriptors in advertised order: `d40849738641f23537e8d5e065c4fcb458554754c3735137d44423cc85b680e8`.
- Sidechat event definition array: `c35245832051f8b7fbe354ff5f121303b4bfd432110b5dfb46694287dba34d99`.

The documented tunnel `/health/mcp` observer reports `not_observed`, no external
initialize epoch and no retained tool list, even though the method journal records
the newer `server/discover`/list requests. Its help explicitly distinguishes
readiness from observed discovery and says health reads do not probe. This empty
observer is **not** evidence of an old served catalog or of no discovery traffic.
No undocumented diagnostic or subscription endpoint was called.

All six advertised input/payload schemas also pass JSON Schema Draft 2020-12
validation. All four compatible/new filter forms validate, while missing
exclusions, false all-project mode, mixed scopes and duplicate exclusions reject.
This rules out those standard-schema defects; it does not establish acceptance
by the platform's metadata ingestion or event subscription UI.

The sanitized reproducible private probe and trace are retained at
`/mnt/vk-storage/vk-dot-discovery-20261016`. They include no runtime credentials or
conversation bodies. Final readback still found one accepted phone delivery
attempt without a reply and zero broad platform subscriptions.

## Supported resolution and escalation packet

Seamus already performed the documented refresh, and the server received discovery
in that window. Another identical refresh is not the proposed resolution.

Use this report with the existing app/connection and affected-root identifiers
**privately** through the OpenAI support/partner path. Ask the platform owner to:

1. Correlate the existing connection's 17:53:53 discovery with its stored tool and
   event metadata. Compare the expected fields/descriptors/hashes above with the
   active catalog and inspect any failed, held or stale metadata ingestion.
2. Compare the root, the three-tool internal worker and this successful four-tool
   coding execution's connection/catalog bindings. Explain why the same named
   connection produces different inventories, and expose the current metadata
   through the existing connection while preserving subscriptions and credentials.
3. Confirm the broad event filter is active in the actual platform subscription
   flow. Do not work around a stale schema by copying callback credentials, direct
   SQLite subscription writes, permission changes or a replacement connection.
4. Once the active catalog is confirmed, verify the actual root can use all four
   tools. A fresh **root conversation** with the existing plugin selected is the
   documented context-selection test; an internal worker alone is insufficient.
   Do not abandon the original root/history or claim this test fixes event schema
   ingestion. If the actual root still differs, continue the same platform case.

[Official connection guidance](https://developers.openai.com/plugins/deploy/connect-chatgpt)
requires confirming changed metadata and testing a fresh conversation after refresh.
[Official troubleshooting](https://developers.openai.com/plugins/deploy/troubleshooting)
recommends isolating server/client layers and escalating reproducible logs to the
OpenAI partner contact when the validated issue persists. These are supported
resolution paths, not a claim that this execution can invalidate a platform cache.
For published plugins only, [metadata review documentation](https://developers.openai.com/plugins/deploy/app-review)
explains that tool definitions may update independently; this report does not
establish that a review hold applies to this private connection or its events.

No escalation was sent to anyone from this task. The packet is prepared for its
owner. Raw transport logs, credentials and private connection/request identifiers
remain outside GitHub. The supported broad request and exact reply procedure are
in [the rollout handoff](DOT_RELIABILITY_ROLLOUT.md).

## Acceptance still open

Browser access to current, archived and future projects remains active. Root's
actual inventory, complete notification subscription and natural root-to-phone
reply remain unverified. The coding execution did not append or relay a reply,
resend a webhook, change any scope, restart any service, or touch the mobile
owner's files/browser while tracing discovery. A successful recovery read does
not mean the phone received a reply.
