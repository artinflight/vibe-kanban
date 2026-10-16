# Dot chat integration: preservation and handoff

This branch preserves the existing integration for review against `staging` in
`artinflight/vibe-kanban`. It performs no deployment. Status below was reconciled
on 2026-10-16 from the clean original worktrees, their activation notes, and
read-only service/release-pointer checks. It does not certify a real Dot reply.

## What is live

The original activation record reports that the additive connector/event bridge,
private outbox publisher, scoped browser API, TLS proxy route and sidebar were
installed for the approved VK Dev test. The browser, publisher and connector
services were observed running during preservation. The live frontend pointer
still selects source `975f62c7c`, based on the clickable-links baseline
`2249da3e9`. The connector source pointer selects `0f1a9daae`; browser API source
is recorded as `2da6263f7`. Preserving this branch does not change those pointers.

Dot appears below Notes in the right sidebar. On the original mobile layout it
is in the Git/details tab; Chat remains the coding-agent conversation. The
browser must be paired for explicitly allowed projects. Sessions persist until
disconnect or revocation; single-use pairing codes expire after ten minutes.
The selected workspace is resolved to its actual issue/project on the server.
Sidechat does not forward instructions to coding agents.

See [the sanitized activation record](scripts/dot-sidechat/ACTIVATED.md).
Its hashes and source references are historical activation evidence, not fresh
end-to-end verification. Private receipts, keys, pairing material, chat history,
subscriptions and runtime databases remain outside this repository.

## What is unfinished and who owns it

The later `c71c2ee7d` responsive correction is preserved here, but the observed
frontend pointer does not select it. Its larger touch targets, compact spacing,
wrapped labels and keyboard/safe-area handling have only source/DOM evidence.
See [the original mobile acceptance checklist](DOT_MOBILE_REVIEW.md).

The mobile agent owns workspace `2e35466b-127e-41ba-ab56-1dd47bdb8b85` and branch
`vk/2e35-vk-mobile-dot-in`. Its active work is not imported, committed, rebased,
reset or deployed here. Continue mobile and S25+ acceptance with that owner:
portrait/landscape at 360/390/412px, keyboard open, long labels/errors, Notes
expanded/collapsed, pairing, send, history scrolling and lost-response retry.
No phone or rendered-browser acceptance is claimed by this preservation task.

The original activation record also leaves actual browser pairing and the real
Dot event/reply roundtrip unverified. The actual Dot context must own its correct
project/thread subscription, then verify one authorized message, webhook receipt,
exact persisted reply and retained-history readback. A webhook 2xx is not a reply
and is not evidence that a person saw it. Reconcile uncertain delivery before
retrying; preserve event/request IDs and existing approval subscriptions.
Do not run historical bootstrap/deployment instructions as part of this handoff.

## Source inventory and reconciliation

| Area | Preserved source | Decision |
| --- | --- | --- |
| Storage, owner/scope fences, idempotency and receipts | `scripts/dot-sidechat/sidechat.py`, `publisher.py`, `contracts.json` | API history retained. |
| Event subscriptions, signed delivery and connector hook | `events.py`, `connector.py`, `worker.py`, `prepare_live.py`, `verify_live.py`, `bootstrap_proof.py` | Additive implementation retained; separate connector supplies existing authenticated principal and webhook transport. |
| Browser authentication and authoritative Vibe scope | `browser_api.py`, `browser.service.in`, `nginx-browser-location.conf.in` | Revocable pairing retained. Templates require private site configuration; no secrets are supplied. |
| Shared sidebar and resize controls | `packages/ui/src/components/DotSidechatPanel.tsx`, `ResizableSidePane.tsx` | UI candidate is authoritative where prototype copies overlap; only formatting differences there. |
| Real/fixture transports and layout | `packages/web-core/src/pages/workspaces/DotSidechat*.tsx`, `RightSidebar.tsx`, `WorkspacesLayout.tsx`, `dot-sidechat.css` | UI candidate includes persistent pairing and prepared mobile correction. |
| Offline acceptance and isolated demonstration | `test_*.py`, `test-ui.mjs`, `test-live-ui.mjs`, `server.py`, `fixture.tsx`, `fixture.css`, `build.mjs` | All original fixtures/tests retained; fake server must remain isolated. |
| Documentation | `scripts/dot-sidechat/*.md`, `DOT_MOBILE_REVIEW.md` | Original staged notes retained with dated status warnings; this document is the reconciled entry point. |

Both originals were clean at inspection and remain intact in their existing
worktrees: `/mnt/vk-storage/vk-dot-sidechat-prototype` on `prototype/dot-sidechat`
and `/mnt/vk-storage/vk-dot-sidechat-ui-candidate` on `activation/dot-sidechat`.
Both share the canonical Git object store. They are local preservation sources,
not branches to force-push or clean up. Publication uses remote `fork`;
`origin` is BloopAI upstream and is not the publication target.

The eight API commits and three UI commits were replayed onto fetched
`fork/staging` at `2249da3e968b19d23e76b728b2beb7810c9e4924`. Original commits
are not made ancestors of the public branch: historical documents contain private
operational details. Each public copy has an `Original-Commit` trailer. Public
copies redact personal paths, private network/process/application identifiers,
grant metadata and live scope IDs throughout the imported history. Documentation
uses synthetic UUIDs and documentation-only addresses. The reserved proof UUID
is likewise replaced with a synthetic value, and site addresses in configuration
templates are placeholders. Runtime logic is otherwise retained.

The newer staging continuity documents stay intact. Imported continuity additions
are archived in [the sanitized continuity excerpts](scripts/dot-sidechat/CONTINUITY_HISTORY.md)
instead of overwriting newer staging truth. Feature flags remain opt-in:
`VITE_DOT_SIDECHAT=1` selects real transport; `VITE_DOT_SIDECHAT_FIXTURE=1` selects
the explicitly fake fixture. Neither flag provisions a server or authentication.

| Original local commit | Public preserved commit | Existing change |
| --- | --- | --- |
| `4c929ece1` | [0a221b010](https://github.com/artinflight/vibe-kanban/commit/0a221b0102b026014e2d3ad3103839ac24f68d77) | prototype: add private issue-scoped dot sidechat fixtures |
| `1c0c62cbc` | [ebe173df1](https://github.com/artinflight/vibe-kanban/commit/ebe173df1f7b3419798c45f2834c843631b7f2a2) | prototype: bind sidechat events to explicit owner reply intent |
| `0f1a9daae` | [69f36c3f3](https://github.com/artinflight/vibe-kanban/commit/69f36c3f35cceb80014e5a228f01a7d0ef09de66) | feat: prepare authenticated dot sidechat connector bridge |
| `1952864f5` | [c5497db86](https://github.com/artinflight/vibe-kanban/commit/c5497db863599101abcf6d68da700b7b19906dd6) | docs: record live sidechat connector and remaining integration gates |
| `6ed8b593a` | [4e1ca9ab3](https://github.com/artinflight/vibe-kanban/commit/4e1ca9ab36626eb95d044d6b9c31c37bcbe243f5) | docs: verify live Vibe route and browser identity boundary |
| `535e89fb8` | [51fff7f75](https://github.com/artinflight/vibe-kanban/commit/51fff7f7573f25e1b52a448f4cd4a3df250f2e71) | feat: prepare authenticated browser sidechat and live sidebar transport |
| `2da6263f7` | [4e344de75](https://github.com/artinflight/vibe-kanban/commit/4e344de751aea73505bc4f75fe32f46c0a692d43) | feat: retain approved browser pairing until revocation |
| `f898872c5` | [504b10700](https://github.com/artinflight/vibe-kanban/commit/504b107007733408bbb4f277c28f7e1a072a6a36) | docs: record approved live browser sidechat test activation |
| `72768eaa6` | [99bf6626a](https://github.com/artinflight/vibe-kanban/commit/99bf6626af209f52fefa2990911e9880e7d41716) | feat: prepare Dot sidebar on current production frontend source |
| `975f62c7c` | [679fa6c28](https://github.com/artinflight/vibe-kanban/commit/679fa6c28934ab254b9f6fe00c3781e46d3d5706) | feat: retain browser pairing until disconnect or revocation |
| `c71c2ee7d` | [b981a1e6e](https://github.com/artinflight/vibe-kanban/commit/b981a1e6e33d34670e7a652538c2312dc2921b5b) | fix: prepare touch-friendly mobile dot chat layout |

The machine-readable provenance map is [DOT_PRESERVATION_COMMITS.json](DOT_PRESERVATION_COMMITS.json).
The code/commit inventory, public-history secret scan and validation limits are
recorded below; this PR publishes source for review and does not merge staging.

## Vibe tracking and GitHub

- Preservation: [open workspace](https://vibe.local/workspaces/de2d98a3-b73f-4e70-9445-caee5cae188c).
- Dedicated preservation issue: [open issue](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d/issues/b9d9191d-5d68-5046-a54d-16186a87205b).
- Mobile follow-up: [open owner workspace](https://vibe.local/workspaces/2e35466b-127e-41ba-ab56-1dd47bdb8b85).
- Published source: [preservation branch](https://github.com/artinflight/vibe-kanban/tree/vk/de2d-vk-preserve-dot).
- PR: pending publication; will be linked before final handoff.

This preservation workspace initially shared mobile issue T60. Only its own
association was moved to the dedicated issue; the mobile workspace association
and metadata were verified unchanged. Issue/workspace links are intentional task
handoff identifiers, not chat/session/grant identifiers.

## Validation

- Passed: `pnpm run format`, `pnpm run ops:check`, `git diff --check`.
- Passed: all 31 isolated Python tests, including scope/authentication, revocation,
  ten-year virtual-time session persistence, request idempotency, event delivery,
  loopback HTTP and disposable-certificate TLS.
- Passed: `node scripts/dot-sidechat/build.mjs`, both DOM suites
  (`test-ui.mjs`, `test-live-ui.mjs`); the fixture server was stopped afterward.
- Passed: local-web, remote-web, web-core and UI TypeScript checks; local-web and
  UI lint. Formatting the two imported shared components produces equivalent JavaScript syntax
  trees to the original UI candidate (trivia/formatting excluded).
- Attempted: `pnpm run check`, `pnpm run lint`, `cargo test --workspace`, using
  the dedicated shared SSD target, incremental disabled and offline dependencies.
  Their Rust stages exit 101 before compiling product tests because this host
  lacks the `glib-2.0`/`gobject-2.0` pkg-config development files. Later stages
  (including remote Rust and the final i18n check) were not reached. No Rust,
  remote deployment, database schema or generated shared types changed here.
  GitHub CI remains required before merge; no full Rust-suite pass is claimed.
- Passed: inventory of all 31 source/config paths and eleven original commits;
  original API/UI worktrees remain clean. Differences from the chosen original
  source are confined to two formatted TSX components, a synthetic proof UUID,
  template address placeholders and stricter generated/private-file ignores.
- Passed: Gitleaks 8.30.1 scans complete imported blob versions and commit
  messages, plus the final documentation. A reviewed exact-match allowlist covers
  only the literal SQL assignment
  `excluded.previous_secret,rotation_until=excluded.rotation_until` falsely
  detected as a generic API key; other rules remain enabled. Private original
  histories are not ancestors of the published branch, so tip-only redaction
  cannot leave their operational details in published ancestors.
- Not exercised: rendered desktop/mobile/Android QA, actual browser pairing,
  real subscriptions or a real Dot reply. No production chat write, grant,
  service restart, proxy change, frontend switch or mobile-owner edit occurred.
Private validation logs are retained on the mounted SSD under
`/mnt/vk-storage/vk-dot-preservation-20261016/validation/`.
