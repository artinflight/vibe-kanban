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

# Activated VK Dev browser test - 2026-10-16

Seamus approved activation at10:57 UTC with browser pairing until disconnect or
revocation. Browser entry is https://vibe.local. Backend, gateway, frontend server
and approval watcher were not restarted and retain PIDs[private PID],[private PID],[private PID],[private PID].

Browser service: vibe-dot-browser.service, PID[private PID] at activation.
Installed code: /mnt/vk-storage/vk-dot-sidechat-live/browser-releases/2da6263f7.
TLS listener192.0.2.10:18974 accepts only proxy192.0.2.20.
New certificate/private key are stored privately under connector sidechat state;
only the public certificate was transferred to Homelab. No firewall change.
Nginx chat-only route validates its pinned TLS certificate. Configuration checked
and gracefully reloaded. Initial immediate readiness probe reached an old worker;
original config was restored, then activation succeeded with a bounded readiness
wait. Existing Vibe stayed available. Live checks: unpaired401, foreign Origin403,
Vibe API200. No credentials or TLS checks were disabled.

Frontend source975f62c7cfe006ed4bee41a581a1b97cee978957 includes the newer live
clickable-links baseline2249da3e; not the older candidate. Source build succeeded.
Current release: /mnt/vk-storage/vk-dot-sidechat-live/frontend-releases/975f62c7c.
Live index SHA2562741057eed8ea631283f3466173a6dbc22a419aa621fbc9c08abc334563fe342.
Previous release and786 prior files remain; existing entry JS assets verify.
Activation receipt: /mnt/vk-storage/vk-dot-sidechat-live/frontend-activation.json.
Rollback archive mirrored and SHA256 verified on B:
[private Desktop path]
ce6184f35c7beebbeac3e5e3b5ca3679daf595541927082a5d543ded3fac86b9
Proxy recovery: [private proxy recovery path]

Browser session server expiry is0 (until revoked), with rolling persistent cookie.
The one-use code still lasts10 minutes. A VK Dev-only grant was generated privately;
Seamus enters it himself. Its code is in his restricted local folder:
[private Desktop path]
Initial grant expires[private grant expiry]. No code appears in Git or tool output.
No browser was paired by this agent, and no actual sidechat message was submitted.

Platform discovery NOW exposes all three sidechat tools and the owner-message
event. A real connector read of reserved proof thread succeeded, empty.
The actual Dot should create the project event subscription with:
{"project_id":"11111111-1111-4111-8111-111111111111"}
after Seamus pairs and opens an issue-linked workspace, which registers its
authoritative scope. Current event ownership validation requires an existing scope;
do not fabricate a scope or hijack the approval subscription. Outbox retains
messages until a matching subscription exists. No subscription was created here.

31 Python tests (including ten-year virtual-time session persistence, revocation,
TLS and CSRF) pass. Live transport DOM, formatter/governance and prior frontend
typechecks pass; latest full frontend build includes typecheck. Browser inventory
still empty, so human visual/pairing/mobile testing and an actual-dot reply remain
pending. Do not label the live test an end-to-end success yet.
