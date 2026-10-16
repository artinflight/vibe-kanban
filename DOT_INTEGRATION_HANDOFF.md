# Dot chat integration: preservation and handoff

> Latest: [discovery trace and supported resolution](DOT_DISCOVERY_TRACE.md),
> plus [reply reliability and all-project rollout](DOT_RELIABILITY_ROLLOUT.md).
> Root directly replied to the retained phone test; both notification triggers
> are registered. Fresh automatic routing and user-visible receipt remain open.
> The earlier desktop success used a manual integration-task relay.

This branch preserves the existing integration for review against `staging` in
`artinflight/vibe-kanban`. Its later authorized connector-only activation and
complete browser-project scope are recorded in the latest rollout handoff. Status below was reconciled
on 2026-10-16 from the clean original worktrees, their activation notes, and
read-only service/release-pointer checks, and Seamus's subsequent confirmation
of the first successful desktop roundtrip. The evidence boundaries are below.

## What is live

The original activation record reports that the additive connector/event bridge,
private outbox publisher, scoped browser API, TLS proxy route and sidebar were
installed for the approved VK Dev test. The browser, publisher and connector
services were observed running during preservation. The live frontend pointer
still selects source `975f62c7c`, based on the clickable-links baseline
`2249da3e9`. The initial connector source was `0f1a9daae`; it is now `d2c79543e` after
the approved connector-only rollout. Browser API source remains `2da6263f7`.
Both existing paired sessions now cover all current/archived and future projects;
both original and broad notification subscriptions are now registered. Root
replied directly to the retained phone test; fresh automatic end-to-end and human
viewing evidence remain open. See the latest handoff for exact evidence.

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

## Confirmed desktop roundtrip and its boundary

Seamus confirmed the first real desktop Dot chat roundtrip on 2026-10-16:
an owner message reached Dot through the webhook, the exact Dot reply was
persisted through the integration task's available paired connector, and his
12:07 UTC screenshot showed the reply in the desktop UI. This operator-confirmed
result supersedes the activation record's earlier statement that no real reply
had been verified. It is not a fixture or a webhook-acceptance-only result.

That desktop proof used the integration task's connector while root lacked the
new tools. It does not establish unattended root replies. Root subsequently gained
thread read, reply append and delivery read at 18:07 UTC, directly replied to the
retained phone test and verified persistence. Independent server readback confirms
one reply in that message's original thread and workspace. Neither successful
message should be resent to recreate evidence. The new phone result supersedes
the earlier inability to use root's own reply connector; fresh automatic routing
and Seamus's visible receipt remain unverified.

This documentation records the operator's confirmation without publishing the
conversation, screenshot, pairing material or private delivery/receipt identifiers.
The preservation task did not independently rerun this live test. It was a manual
integration-task relay, not an unattended reply through root's own connector.

## What is unfinished and who owns it

The later `c71c2ee7d` responsive correction is preserved here, but the observed
frontend pointer does not select it. Its larger touch targets, compact spacing,
wrapped labels and keyboard/safe-area handling have only source/DOM evidence.
See [the original mobile acceptance checklist](DOT_MOBILE_REVIEW.md).

The mobile agent owns workspace `2e35466b-127e-41ba-ab56-1dd47bdb8b85` and branch
`vk/2e35-vk-mobile-dot-in`. Its active work is not imported, committed, rebased,
reset or deployed here. That owner retains its active UI inspection. Seamus has
confirmed phone pairing and sending, so this task does not resume geometry,
keyboard, pairing or browser debugging. The earlier mobile checklist is historical
preparation evidence. The retained phone test now has a direct root reply;
remaining acceptance is a fresh automatic message-to-reply roundtrip without
manually naming a workspace, plus Seamus's confirmation of its visible receipt.

Root still lacks pending-message discovery. Its three reply tools and broad event
schema are available, and both original and broad notification subscriptions are
registered. The source recovery tool works through this coding execution but its
availability in root remains a distinct platform limitation. Preserve the existing
enabled automation, both triggers and approval subscriptions. A webhook 2xx and
reply persistence are separate from human viewing; reconcile uncertain writes
before retrying. No further refresh, pairing, activation or historical bootstrap
procedure is required for this handoff.

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
| `535e89fb8` | [b92a025da](https://github.com/artinflight/vibe-kanban/commit/b92a025da876966d0139d14dac0ae41893919e67) | feat: prepare authenticated browser sidechat and live sidebar transport |
| `2da6263f7` | [4b95d24ca](https://github.com/artinflight/vibe-kanban/commit/4b95d24ca19ff943b264b120f72acf1baa5b2107) | feat: retain approved browser pairing until revocation |
| `f898872c5` | [269c12af3](https://github.com/artinflight/vibe-kanban/commit/269c12af3641396a36595bf32d4443645877a5aa) | docs: record approved live browser sidechat test activation |
| `72768eaa6` | [b869b190e](https://github.com/artinflight/vibe-kanban/commit/b869b190eb94e2481e00f468cb88fdf842cd8d9f) | feat: prepare Dot sidebar on current production frontend source |
| `975f62c7c` | [ef5c307a6](https://github.com/artinflight/vibe-kanban/commit/ef5c307a6ea943c3fd7723b6cb49e4257beeb1e8) | feat: retain browser pairing until disconnect or revocation |
| `c71c2ee7d` | [c85279429](https://github.com/artinflight/vibe-kanban/commit/c852794299653bcf739d921d945b50f6c0bfa312) | fix: prepare touch-friendly mobile dot chat layout |

The machine-readable provenance map is [DOT_PRESERVATION_COMMITS.json](DOT_PRESERVATION_COMMITS.json).
The code/commit inventory, public-history secret scan and validation limits are
recorded below; this PR publishes source for review and does not merge staging.

## Vibe tracking and GitHub

- Preservation: [open workspace](https://vibe.local/workspaces/de2d98a3-b73f-4e70-9445-caee5cae188c).
- Dedicated preservation issue: [open issue](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d/issues/b9d9191d-5d68-5046-a54d-16186a87205b).
- Mobile follow-up: [open owner workspace](https://vibe.local/workspaces/2e35466b-127e-41ba-ab56-1dd47bdb8b85).
- Published source: [preservation branch](https://github.com/artinflight/vibe-kanban/tree/vk/de2d-vk-preserve-dot).
- PR: [#254 — preservation into staging](https://github.com/artinflight/vibe-kanban/pull/254) (draft; no merge or deployment).

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
  The local Rust limitation remains. Hosted Test run
  [38911578393](https://github.com/artinflight/vibe-kanban/actions/runs/38911578393)
  passed for source baseline `14fca343b`, including frontend, backend tests,
  Clippy, generated types/SQLx and Tauri. Remote-dependency checks did not execute
  without the private deploy key; workflow-dispatch-only combined acceptance was
  skipped. The current correction changes documentation only; its final head
  and CI receipt are recorded on PR #254.
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
- Operator-confirmed live evidence: the first desktop webhook/reply-persistence
  roundtrip succeeded through the integration task's connector; Seamus's screenshot
  confirms the displayed reply. Root's later direct phone-test reply is also
  persisted, independently verified in its original thread/workspace. Both
  non-overlapping notification subscriptions are registered. Fresh automatic
  end-to-end and phone-visible receipt evidence remain open. This reconciliation
  did not rerun pairing, append/relay a reply or perform browser/Android QA.
- The initial preservation phase made no runtime changes. Subsequent approved
  connector/publisher activation and complete-project access are documented in
  the rollout handoff. This latest reconciliation is read-only; no activation,
  subscription mutation, reply relay or mobile-owner edit occurred.

Private validation logs are retained on the mounted SSD under
`/mnt/vk-storage/vk-dot-preservation-20261016/validation/`.
