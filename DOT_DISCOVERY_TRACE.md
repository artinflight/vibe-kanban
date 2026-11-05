# Dot discovery discrepancy — 2026-10-16

## Current resolution and remaining limit

Root's owner reports its view caught up at 18:07 UTC without another refresh:
thread read, reply append and delivery read are available, and the complete broad
event schema is visible. Root directly replied to the retained phone test and
verified persistence, then updated the existing enabled automation with original
VK Dev and all-projects-excluding-VK-Dev triggers through the supported flow.
Read-only server inspection at 18:23 UTC independently confirms both active,
non-overlapping subscriptions and exactly one same-thread/workspace phone reply.

The previous inability to reply/register broad scope is superseded. Root still
lacks `list_pending_sidechat_messages`, although the connector and this coding
execution expose it. A fresh automatic roundtrip and user-visible reply receipt
remain unverified. See [the current rollout handoff](DOT_RELIABILITY_ROLLOUT.md).
No further refresh, pairing, activation or automation replacement is requested.

The trace below preserves the evidence collected before that owner confirmation
was available. The reported views changed with time; an exact platform cache,
metadata review state or root-inventory mechanism was never established. The
support packet now applies only to the remaining pending-discovery availability
or a fresh context-free wake failure. It is not a prerequisite to root's verified
reply capability or the already completed broad subscription registration.

## Historical finding and limits

A registered pending-context call through this coding execution succeeded at
18:00:50–18:00:51 UTC on the same adapter child that handled discovery. This coding
execution exposed all four tools while the earlier reported root/worker views
were stale. The configured installed facade also returned the complete schema.
This established a platform metadata/context discrepancy, without identifying an
exact cache component or proving root's stored catalog. No private conversation
or receipt identifiers were published.

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

## Historical resolution packet — remaining recovery tool only

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

Browser access and both notification registrations cover current, archived and
future projects. Root's retained-message reply is persisted, independently checked
in the original thread/workspace. Root's pending-discovery tool remains absent;
fresh automatic event-to-reply routing and Seamus's visible receipt remain open.
The coding execution did not append/relay a reply, resend a webhook, change scopes,
restart services or touch the mobile owner's work during trace/reconciliation.
