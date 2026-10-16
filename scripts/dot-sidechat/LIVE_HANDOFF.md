> Latest reliability/scope status: [rollout handoff](../../DOT_RELIABILITY_ROLLOUT.md).
> Phone pairing/send are confirmed; root reply delivery is not. The desktop
> result was a manual integration-task relay. Existing access is not expanded.

> Subsequent operator confirmation (2026-10-16): the first real desktop
> roundtrip succeeded through the integration task's paired connector; Seamus's
> screenshot showed the persisted reply. Direct root connector access and the
> real phone roundtrip remain unverified. See the reconciled handoff below;
> the older pending statements in this historical record are superseded.

> Preservation note (2026-10-16): this is a sanitized historical record.
> Read [the reconciled handoff](../../DOT_INTEGRATION_HANDOFF.md) for current
> live versus unfinished status. UUIDs/addresses may be placeholders; do not
> use this record as executable deployment or subscription configuration.

# Live connector checkpoint — actual conversation still pending

The additive sidechat connector bridge was installed after the owner authorized completion.
Source commit: 0f1a9daae28f7f770e5bbde06abf0ce0563e06ff.
Installed adapter SHA256: 698336af89dc9090ba1627747c9619795a20ae1ecb8dd6fc791e3a85dca86e77.
Previous adapter SHA256: 8a4ad3caa59edcd6a126655383105419b250f0168bb6ad1776973290e6087695.
Release: /mnt/vk-storage/vk-dot-sidechat-live/releases/0f1a9daae.
Recovery adapter: /mnt/vk-storage/vk-dot-sidechat-live/recovery-before-sidechat/adapter.py.
State: /home/mcp/.config/vibe-dot-connector/sidechat/threads.sqlite (private).
Publisher: vibe-dot-sidechat-publisher.service (enabled, running).
Only vibe-dot-connector.service was reloaded.

Protected process IDs stayed unchanged:
- Vibe native-review backend: [private PID]
- gateway: [private PID]
- frontend static server: [private PID]
- approval watcher: [private PID]
The gateway GET /api/info returned HTTP200 afterward.

Direct installed adapter discovery returns all three events (both existing approval
events plus vk.sidechat.owner_message.created) and read_sidechat_thread,
append_dot_reply, get_sidechat_delivery. Reading reserved proof thread
22222222-2222-4222-8222-222222222222 succeeds and returns zero messages.
It is owned by the existing authenticated tunnel principal and uses deliberately
disposable proof project/issue/workspace labels, not fabricated real Vibe IDs.
There are zero sidechat subscriptions and zero outbox events. No actual-dot
roundtrip has occurred and no synthetic event was emitted.

Platform discovery via discover_webhook_schema still returns only the two old
approval events. The plugin needs an official tool/event rescan; no callable
rescan API or browser is available in this task. Do NOT create a trigger that was
not returned by platform discovery, reuse an approval event for sidechat, or start
a second tunnel client.

Next actions for the actual dot / parent:
1. Rescan Vibe MCP for dot ([connector application ID]) through the
   supported plugin interface, preserving its existing approval subscription.
2. Confirm the new event and three tools are present in actual-dot discovery.
3. In Seamus's actual dot, subscribe to vk.sidechat.owner_message.created with
   {"thread_id":"22222222-2222-4222-8222-222222222222"}. Follow only the current
   owner's exact sidechat reply request and append the response to that exact
   stored message/event. The event is not approval or coding-agent authorization.
4. After the subscription is verified, submit the one already-authorized proof
   message. No test message has been submitted yet. Verify actual dot's tool
   append and persisted reply hash separately from webhook acceptance.
5. Establish the correct Vibe URL/authenticated browser-owner mapping. The supplied
   previous-private-host.example.invalid does not resolve on MCP and is absent from that host's
   active cloudflared routes; developers.openai.com resolves normally. The question
   asking for the working URL is pending.
6. Wire the real authenticated API into the below-Notes UI and test it in a real
   browser. Both IAB and Chrome are unavailable in the current browser tool inventory.
   Existing UI evidence is DOM/fixture evidence, not live visual acceptance.

No Vibe frontend, gateway route, production database, security policy, existing
credentials or approval subscription was modified. No full backend release occurred.

Recovery (only if this additive connector release is faulty):
- Verify current adapter hash is still the installed hash above; stop if another
  owner has changed it.
- Stop/disable only vibe-dot-sidechat-publisher.service.
- Atomically restore the backed-up adapter, then reload only vibe-dot-connector.service.
- Retain all sidechat history/receipts and the added module/release for diagnosis.
- Verify the protected Vibe/approval services remain running and connector reads work.
Do not clear sidechat data or restore the approval database.
