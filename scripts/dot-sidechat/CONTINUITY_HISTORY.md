# Historical Dot continuity excerpts

Sanitized source notes only. [Current handoff](../../DOT_INTEGRATION_HANDOFF.md)
supersedes their historical pending/live statements. Placeholder IDs are not
production configuration. The three original continuity files used identical
Dot additions at each tip; one copy of each addition is retained below.


## API branch

# VK Dev browser test activated; owner pairing pending

Read scripts/dot-sidechat/ACTIVATED.md for exact deployed code, artifact hashes,
verified TLS/access checks, rollback and parent-Dot subscription instructions.
Browser pairing is until revoked. No actual chat message/reply is tested yet.

# Private browser sidechat prepared; activation pending

The live React transport and browser API are implemented but inactive. Read
scripts/dot-sidechat/ACTIVATION_REVIEW.md for exact pairing/TLS access approval,
proxy/unit templates and rollback. Vibe is at https://vibe.local; its local
requests do not authenticate individual browsers.

31 Python tests including TLS, both fixture/live DOM suites, UI/web-core typechecks
and targeted component lint pass. The candidate based on production frontend
source5ce84ee21 builds. Optional Sentry upload failed without credentials; no token
was supplied. Source/artifact hashes are in private current-ui-manifest.json.
Real browser acceptance and actual-dot reply remain unverified.

The10:13:58 UTC refresh reached the updated live adapter (discovery, tools/list,
events/list), with no logged request error. Platform additions remain unavailable;
refresh UI outcome is requested. Protected Vibe/approval PIDs are unchanged.
No browser grant, certificate, listener, proxy route or frontend swap was activated.

# Dot connector installed; platform rescan and browser integration pending

Read [live checkpoint and next actions](scripts/dot-sidechat/LIVE_HANDOFF.md). The connector-only release is active; Vibe and approval services kept their process IDs. No actual-dot message/reply has been tested. The platform catalog is stale and the supplied site URL is unresolved.

# Private Dot sidechat isolated prototype — October 16

See [prototype contracts, validation and actual-dot handoff](scripts/dot-sidechat/README.md). This branch adds isolated Python persistence/outbox/tool contracts and feature-flagged React UI below Notes. No production activation or actual-dot roundtrip is claimed. Existing steering/connector files are untouched. Browser screenshots and additive authenticated connector exposure remain required.

## Retained prior context



## UI branch

# Dot mobile usability review — October 16

Mobile Git tab already mounts Notes and Dot at full width; Chat tab remains the
coding agent. Existing visualViewport handling resizes the app for the keyboard.
Prepared narrow-screen CSS improves touch targets, input text size, long-label
wrapping and scrolling in short viewports. Desktop sizing and authentication are
unchanged. This source change is not activated; no browser surface is available
for visual acceptance. See DOT_MOBILE_REVIEW.md for validation and handoff.
