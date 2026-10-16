> Preservation note (2026-10-16): this is a sanitized historical record.
> Read [the reconciled handoff](../../DOT_INTEGRATION_HANDOFF.md) for current
> live versus unfinished status. UUIDs/addresses may be placeholders; do not
> use this record as executable deployment or subscription configuration.

# Private Dot sidechat — isolated prototype

This is source/fixture evidence, not a deployed feature or a verified actual-dot roundtrip.
Branch: `prototype/dot-sidechat`; base: `872f69996ae8225faba4bc12e89880e7b7623efb`.
Worktree: `/mnt/vk-storage/vk-dot-sidechat-prototype`.

## What works

- SQLite owner/project/issue threads; multiple registered workspaces share the same issue thread.
- Immutable workspace mapping, owner-scoped reads, stable snapshot pagination and retained complete messages.
- Atomic owner-message/outbox commit; exact event/message/workspace reply correlation.
- Idempotent owner sends and dot replies, including concurrent duplicate admission. A second final reply to the same owner message is rejected.
- Durable leased outbox, stable event IDs after lost responses/restarts, bounded retries, expired/revoked subscription exclusion.
- Separate webhook acceptance and reply-persistence receipts. Human viewing is unknown, never inferred.
- Only owner messages create wake-up events. Dot replies cannot create an event loop.
- Explicit tool allowlist and contract schemas; no coding-agent action or generic HTTP tool.
- Shared React chat panel below Notes behind `VITE_DOT_SIDECHAT_FIXTURE=1`; default build retains the original sidebar.
- Resizable pane (440px initial, generally 360–640px; viewport-clamped), keyboard divider, pinned composer, retained history, message hash links, separate delivery states.
- Loopback-only standalone fixture with fixed fake identities and labeled simulated replies.

The Python core receives a trusted Principal from an adapter. Constructing that object is NOT authentication. The fixture server deliberately uses fake identities and must never be published, reverse-proxied publicly, or pointed at production data. It rejects foreign Host/Origin and caller identity injection, but is intended only for disposable test messages. The browser fixture is not connected to Vibe's actual issue/workspace selection.

## Files

- `sidechat.py`: storage, scope fencing, tools and delivery contracts.
- `publisher.py`: one leased delivery through an injected trusted transport; no network implementation.
- `contracts.json`: proposed event and three MCP tools.
- `server.py`: isolated HTTP fixture; no credentials, background subscriptions or external calls.
- `test_*.py`: storage, HTTP, publisher and security regression tests.
- `test-ui.mjs`: DOM acceptance using the actual bundled React code. It is not a visual browser test.
- `build.mjs`: reproducible standalone bundle.
- `packages/ui/src/components/DotSidechatPanel.tsx`, `ResizableSidePane.tsx`: shared components.
- `packages/web-core/src/pages/workspaces/DotSidechatFixture.tsx`: explicitly fake transport container.

## Run privately

Use the existing installed Node toolchain; no new credentials required.

```sh
export PATH=/home/mcp/.cargo/bin:/home/mcp/.nvm/versions/node/v24.13.1/bin:$PATH
pnpm install --offline --frozen-lockfile --ignore-scripts
node scripts/dot-sidechat/build.mjs
python3 -B -m unittest discover -s scripts/dot-sidechat -v
python3 -B scripts/dot-sidechat/server.py \
  --data /mnt/vk-storage/vk-dot-sidechat-prototype-evidence/fixture.sqlite --port 18973
# A second shell:
node scripts/dot-sidechat/test-ui.mjs
```

The server listens ONLY on 127.0.0.1. A temporary SSH local forward can expose it on the operator's own 127.0.0.1:18973. No Funnel, tailnet listener, production proxy or service unit is installed. Stop the exact owned fixture process and SSH forward when finished; retain the database if its history is wanted.

The standalone shell uses the same chat and resize components. The production-layout patch is off by default. Enabling its fixture flag without routing /\_\_dot_fixture to the isolated fixture intentionally reports unavailable; it never falls back to a live agent or changes a live Vibe issue.

## Verified and unverified

18 isolated Python tests pass. UI and web-core TypeScript checks pass.
New UI components pass targeted lint. Including RightSidebar in the strict lint invocation reports its pre-existing useMemo dependency warning (changesExpanded/devServerExpanded/processesExpanded); that dependency array is unchanged by this branch.
DOM acceptance passes Notes placement, fixture labeling, keyboard resize, owner send, webhook-accepted versus reply-persisted states, and reload-retained history.
Normal repository formatting completes using the existing Cargo/Node PATH.
Browser tools reported no available browser (IAB and Chrome unavailable); screenshots, pixel layout, mobile interaction and real browser accessibility remain unverified.
No actual dot, paid model, live event, subscription, connector reload, Vibe restart, production database, permissions or credentials were changed.
The existing approval webhook was neither read from its secret state nor modified.
No Rust source/schema changes; full Rust/release CI is not represented by these targeted prototype checks.

## Actual-dot proof prerequisites — parent/operator handoff

Current source connector: `[connector application ID]` (Vibe MCP for dot).
Proposed event: `vk.sidechat.owner_message.created`.
Reserved disposable proof thread: `22222222-2222-4222-8222-222222222222` (NOT created live).
Exact subscription arguments after provisioning: `{"thread_id":"22222222-2222-4222-8222-222222222222"}`.

Do not reuse an unrelated existing Vibe issue merely to obtain IDs. Use a private disposable prototype scope explicitly labeled as test context, then map real project/issue/workspace IDs for a separately reviewed Vibe integration. The current live VK Dev project is `11111111-1111-4111-8111-111111111111`, but no specific sidebar issue/workspace has been provisioned or selected. Fixture IDs are not real Vibe IDs.

Before creating the subscription:

1. Connector owner reviews additive modules/catalog/dispatch against the exact current adapter hash, retaining ca3fe817 queue handling and PR250 steering overlay compatibility. Do not replace or modify approval event definitions/subscriptions.
2. Bind the existing authenticated single-owner tunnel principal to the isolated proof store. No caller-supplied owner or role. Provision only the reserved proof scope/thread; core resolve currently generates IDs, so a reviewed bootstrap must explicitly reserve the nominated ID rather than silently choosing a different filter.
3. Add only the event in contracts.json and read_sidechat_thread, append_dot_reply, get_sidechat_delivery. Event discovery and subscribe must enforce exact owner/thread access. After existing callback verification, bind its returned subscription ID/expiry to this thread. The signed transport retains callback secrets; sidechat storage stores only the opaque subscription ID.
4. Add isolated outbox draining using the existing verified/signing transport. Do not repurpose the approval state machine. Preserve existing approval delivery, renewal and revocation behavior.
5. This requires a coordinated live connector reload and tool/event rescan. It has NOT been authorized as a described release or performed. Existing tools cannot do the roundtrip without this additive exposure. Do not launch a second tunnel client.
6. Parent creates the one exact-thread subscription from Seamus's actual dot and instructs it to read the owner message, then append one reply to that exact event/message with a stable request UUID. No coding-agent actions.
7. Only after discovery/subscription verification, submit one authorized test owner message: “Private sidechat proof. Reply with SIDECHAT-DOT-OK and take no coding-agent action.” Publish its actual stored event once. A timeout keeps the same event ID; do not invent a new owner message.
8. Verify webhook receipt independently, then a matching persisted reply/hash and complete thread readback. A 2xx alone is not success. No automatic fixture reply is permitted in this proof.
9. Stop only that proof subscription after evidence is captured; retain the complete proof thread and receipts. Leave the existing approval subscription unchanged.

None of these prerequisites has been silently satisfied. The proof remains blocked at connector tool/event exposure and trusted principal bootstrap.

## Minimal eventual Vibe integration

- Replace the fixture browser identity/transport with Vibe's authenticated owner context and authoritative issue/workspace mapping.
- Add authenticated same-origin API routes or a reviewed proxy/auth adapter; never expose the fixture server publicly.
- Wire retained-history pagination/reconnect recovery and request persistence across browser reloads; the current fixture only retains its in-flight request key in memory.
- Add real browser visual/mobile/accessibility tests and screenshots.
- Backend routes/migrations require reviewed Vibe build/restart. A UI-only fixture needs no Vibe restart; connector-only proof needs only the separately coordinated connector reload/rescan.
- Keep Send to workspace agent a separate future action. Reuse PR250 steering receipt semantics after deployment, retain Recommend-only routing and the capacity queue fix, and never auto-forward sidechat.

## Per-event intent and platform review

Each owner-message event carries server-generated author_type=authenticated_owner,
intent=sidechat_reply_requested, reply_scope=same_thread_only and the exact message
SHA256, in addition to owner-authorized thread/project/issue/workspace/message IDs.
Transcript reads attach the same immutable message identity and explicit
coding_agent_action_authorized=false and platform_review_bypass=false.

These are provenance facts about a normal reply request, not instructions to
override system policy or evidence that platform review has approved an action.
Free-form message text cannot overwrite them. The receiver must scope the event
to its exact owner message and subscription, rather than importing older approval
automation instructions as authority for this separate conversation.

The owner has reported Slack replies being rejected under older approval
automation instructions. This prototype does not diagnose or fix that platform
routing behavior. If an actual reply is rejected, retain the message and outbox
receipt, report the rejection, and leave reply_persisted=false. Do not reroute
through Slack, invent an approval, use another assistant, or retry under a new
identity to evade review. Webhook acceptance still does not prove reply delivery.

## Authorized live-connection preparation

The owner subsequently requested completion of the actual connection. The additive
bridge now implements authenticated exact-thread or project-scoped subscriptions,
verified signed transport via the existing helper, future issue-thread routing,
subscription expiry/rotation, and an independent outbox worker. New code is tested
with 22 isolated tests plus 28 existing connector regressions. The unchanged PR250
overlay applies to the candidate and passes its 14 existing regressions.

A connector-only reload is authorized by that follow-up. No Vibe/backend/gateway
restart or frontend replacement is part of this connector step. The active browser
URL/authentication boundary remains unresolved: previous-private-host.example.invalid does not
resolve from MCP and is absent from its cloudflared routes. Do not expose the fixture
identity as browser authentication or publish private conversation data to compensate.

The proof bootstrap creates an empty thread only. A real dot subscription, an owner
message/event, and a real appended reply remain separate evidence gates.
