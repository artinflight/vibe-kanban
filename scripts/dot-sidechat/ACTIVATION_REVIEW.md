# Private browser integration: implementation and activation review

Implementation is prepared, not activated. No new live credential, browser grant,
TLS listener, proxy route, Vibe restart, or frontend swap has been performed.

## Implemented boundary

browser_api.py serves only pairing/session/logout/history/send. It cannot call a
coding agent, arbitrary URL, event subscription or command. A trusted local CLI
creates an explicit owner/project allowlist grant. Its random 256-bit one-use code
expires in 10 minutes and is written only to a new mode0600 file, not logs or URLs.
Only token hashes are stored. Pairing issues a 24-hour revocable session in a
Secure, HttpOnly, SameSite=Strict, host-only cookie restricted to
/api/dot-sidechat/. This narrow Path avoids sending the new credential over
existing plain-LAN backend/frontend upstream hops. The new upstream must use TLS.

Every read and write authenticates that session. Exact Host, same-origin custom
request header, Origin checks, JSON-only writes and per-session CSRF fencing apply.
Cross-origin preflight is unsupported. Pair attempts are bounded. Non-loopback
serving requires TLS plus one exact trusted proxy peer; wildcard bind is rejected.
HTTP never accepts owner/project/issue/role. The resolver opens the verified Vibe
database in SQLite mode=ro/query_only, derives workspace -> task -> project, and
checks the explicit grant. Relinked or missing scopes fail closed; old history is
retained. Sidechat reads/writes use the installed core's separate private store.

DotSidechatLive is mounted below Notes with the real selected workspace ID under
VITE_DOT_SIDECHAT=1. It includes pairing/disconnect, polling of retained paginated
history, server-derived labels, precise receipts, scope-remount isolation, and
uncertain-send persistence in sessionStorage under session/workspace. Lost-response
retries reuse exact request/body; pending content is locked until resolved.
Transcript bodies and cookies are not stored in localStorage. A full tab close
removes tab storage; server history remains. An expired/revoked session cannot
reuse a new session's grant to silently resubmit an old draft. Separate coding
agent instructions remain in its existing composer; sidechat never auto-forwards.

## Exact access change requiring owner approval

Approve creating a NEW private browser-chat credential and pairing Seamus's
browser for the explicit project allowlist (initial proposed project: VK Dev,
11111111-1111-4111-8111-111111111111). This permits reading retained private Dot
threads and sending owner messages for issue-linked workspaces in those projects
for 24 hours, revocable earlier. It does not permit controlling coding agents,
editing issues, changing subscriptions, or viewing other owners/projects.

Approve a NEW TLS sidecar on MCP 192.0.2.10:18974 accepting only the Homelab
proxy 192.0.2.20, with a newly generated private key kept on MCP and its public
certificate pinned by nginx. Use SAN vk-dot-sidechat.internal. No existing key,
credential, approval rule, service permission, or Vibe authentication is changed.
Add only the /api/dot-sidechat/ proxy location to vibe.local and gracefully reload
nginx after nginx -t; existing Vibe processes and active sockets remain running.
If the existing firewall blocks this path, a separately reviewed exact-source
port rule is required; do not open a broad port or weaken TLS as a workaround.
Install/enable only the new browser sidecar unit (template browser.service.in).
No new route/listener/certificate/grant is installed by these preparation files.

## Frontend candidate and release

Current live frontend source worktree is frontend66-over-c3 at
5ce84ee21be814b1519cfb2715b50f3432c3e8ba, with only dist-v5/dist-v6 untracked.
The sidebar/layout baseline files match the prototype's staging base.
Candidate /mnt/vk-storage/vk-dot-sidechat-ui-candidate uses exactly that source
plus seven UI files. It is not a whole stale staging replacement.
A production static asset switch still requires verified build, current-source
diff review, actual browser acceptance and retained previous hashed assets.
Use an immutable release directory and atomic pointer update; no Vibe backend
restart. Preserve old assets for already-open clients. Do not overwrite dist-v6.

The browser feature can be prepared while plugin discovery is blocked; real Dot
replies require the correct actual-dot subscription. Never simulate them in live UI.
The proof scope has disposable string IDs and deliberately cannot pass the real
Vibe UUID/workspace resolver; perform its original connector proof separately.

## Refresh investigation

At 2026-10-16 10:13:58 UTC, journal records server/discover, tools/list and
events/list from the actual tunnel to adapter PID[private PID], child of tunnel PID[private PID].
Files were installed at10:00:41 and this process started10:00:42. Installed adapter
hash remains 698336af89dc9090ba1627747c9619795a20ae1ecb8dd6fc791e3a85dca86e77.
No request failure appears for refresh. Thus Refresh Tools reached the updated
service; it was not pointed at an old process. Platform tool/event exposure still
omits additions. No unsupported platform API was used. UI refresh outcome/review
details are requested; catalog adoption remains unverified rather than presumed.

## Acceptance and rollback

Before activation: Python/browser DOM tests, current-source frontend build and
typechecks, actual browser pairing/rejection/resize/history/mobile checks.
After approval: verify exact live DB/service paths; install immutable sidecar,
create TLS identity, pin public cert, test TLS peer route, add nginx location;
verify unauthorized401, wrong Origin403 and no credential leakage to other paths.
Generate the approved project grant without printing it; pair in authorized browser.
Verify selected workspace -> actual issue/project, send one authorized proof,
confirm actual-dot append and distinct receipt, refresh and recover full history.
Test browser revocation and inaccessible project without changing Vibe settings.

Rollback: revoke only new browser sessions/grants, stop only new browser unit,
remove only new nginx location and gracefully reload, restore prior static pointer.
Retain all messages/outbox/receipts and previous assets. Do not restore old Vibe DB,
stop agents, change approval subscriptions, or roll back the live connector as a
browser-only rollback.

## Verified preparation results

31 isolated Python tests passed, including disposable-certificate TLS; both DOM
suites pass. UI/web-core typechecks and targeted component lint pass. Read-only
mapping against one actual linked Vibe workspace passed with zero chat writes.
Current-source frontend build exited0 and generated765 artifacts. Private API,
pairing code and chat/flex CSS are present. Hash manifest is at
/mnt/vk-storage/vk-dot-sidechat-prototype-evidence/current-ui-manifest.json.
Optional Sentry upload failed without auth; no token was supplied. Build warnings
include old browsers data, Tailwind content and large chunks; visual acceptance
remains open. Candidate panel differs from prototype only in formatting; manifest
binds its exact built source. Backend[private PID], gateway[private PID], frontend[private PID] and
approval watcher[private PID] remained active. No production browser activation occurred.
