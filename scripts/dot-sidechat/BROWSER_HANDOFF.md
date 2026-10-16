# Browser route and authentication verification - 2026-10-16

Verified: https://vibe.local resolves on Windows to 192.0.2.20.
Homelab TLS-validated GET / returns Vibe Kanban (index-Djfpggqs.js), and /api/info
succeeds. Active nginx /etc/nginx/conf.d/vibe.local.conf sends /api/ and /v1/
to MCP 192.0.2.10:4720, and / to 192.0.2.10:4313. This is the current Vibe.
Windows DNS also returns NXDOMAIN for previous-private-host.example.invalid; this is not
evidence of what a browser with different DNS/cache sees.
Windows curl HTTPS failed CRYPT_E_NO_REVOCATION_CHECK; homelab curl passed
normal TLS validation. No TLS configuration was changed.

AUTHENTICATION: the proxy adds no personal authentication. A request without
cookies/Authorization receives /api/info login_status=loggedin. Source config.rs
gets this from deployment.get_login_status(), not the request. The middleware
relay_request_signature.rs passes non-relay requests through, and Origin checks
do not establish identity. The local browser cannot yet be mapped to the owner
merely because the server is logged in. MCP tunnel authentication is separate.
Use a verified signed browser/relay session mapped to the owner, or a separately
approved scoped browser pairing mechanism. Deny unpaired reads/writes, inject
owner server-side, enforce Origin/CSRF, and resolve authoritative workspace scope.
No credentials, pairing, permissions, services or auth settings changed here.

BROWSER: cua.getState returned apps=[] and browsers=[].
The computer-use skill was read; required node_repl runtime is not available.
No live screenshot, authenticated browser inspection or visual acceptance is claimed.
The sidebar remains a source/DOM-tested prototype, not deployed to vibe.local.
Production frontend is unchanged. Do not overwrite its newer customized dist-v6
with the staging-based full build; integrate against authoritative current source.
The fixture at loopback port18973 remains fake and must not be exposed publicly.

PLUGIN REFRESH: official instructions:
https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata
Open https://chatgpt.com/plugins in the owning account/workspace, open existing
Vibe MCP for dot, select Refresh, and confirm changed metadata. Expected tools:
read_sidechat_thread, append_dot_reply, get_sidechat_delivery; event:
vk.sidechat.owner_message.created. Keep existing approval subscriptions.
Docs recommend a new conversation for affected tool tests; actual-dot event
subscription must still originate in the intended dot context.
No rescan API or connected browser is available in this execution environment.

REMAINING: connect an authorized browser or perform the documented refresh;
establish browser-owner authentication; wire live transport and actual scope into
the current frontend source; visually verify; complete exact actual-dot proof.
Connector installation details and reserved proof thread are in LIVE_HANDOFF.md.
No real sidechat message or actual-dot roundtrip was performed in this follow-up.
