# Dot manual unread — T63 follow-up

## Behavior

Each Dot reply has **Mark unread** beside its existing attention action. It
sets the standard unread flag without creating, resolving or reopening Needs
Attention. The action becomes **Mark read** until the owner clears the manual
choice. Ordinary new replies still become read when their end is visible in a
focused chat. Manual unread survives open-chat visibility events, polling,
navigation, sibling issue workspaces, browser reload and service/store reopen.

Owner-only `POST /api/dot-sidechat/read-state` accepts the existing exact
workspace/project target, message ID and explicit `read`/`unread` action. The
existing session, origin, CSRF, owner/project and Dot-reply checks apply. A
transactional additive `manual_unread` column in `dot_reply_state` preserves
all prior state; concurrent service startup migrates it once. No Vibe schema,
agent flags, task state, MCP tool/event schema or delivery/outbox changes.

Automatic `seen` acknowledges only replies that are actually read and skips
manual overrides at the server, including older clients and late requests.
The frontend honors returned IDs, excludes overrides from automatic reads,
blocks repeated in-flight clicks and rejects snapshots predating a manual
change. Failed actions remain retryable. The new controls require the
`manual_unread` capability, so the frontend works with the incumbent API.

## Validation

- 71 isolated Python tests pass: ordinary read/attention, repeated explicit
  actions, persistence, owner/project isolation, migration/concurrent startup,
  HTTP session/origin/CSRF and unchanged issue/project delivery/planning.
- DOM tests pass for issue/workspace and project targets at 390/1440 px:
  ordinary visible read, independent unread/attention and Resolve/Reopen,
  repeated clicks, failed-operation retry, navigation/reload, late read
  acknowledgement, stale refresh and older-service capability fallback.
- Isolated Chromium at 390/1440 px passes actual geometry, independent badges,
  manual-unread persistence while focused, reload, explicit read/resolve,
  touch sizing, no overflow and unchanged coding-agent state.
- Existing uncertain-send/reload/receipt/logout tests pass.
- All four frontend TypeScript checks, local-web/UI lint and focused shared
  container lint pass. Repository format, ops and diff checks pass.
- Full `pnpm run check` and `pnpm run lint` reach Rust and fail on this host's
  missing `glib-2.0.pc`; `cargo test --workspace --offline` hits the same
  prerequisite. Full Rust workspace validation requires hosted CI;
  frontend checks are reported independently. No system packages were installed.

Tests use disposable state and isolated unpaired browsers. No production
conversation, pairing, grant, subscription or service was mutated. No actual
owner-device or automatic root-Dot reply acceptance is claimed here.

## Publication and release boundary

Continue existing VK Dev **T63**, workspace
`7db73dbd-3b5d-4c21-87f1-4924be648284`, branch
`vk/7db7-vk-project-dot-c`. Reuse its existing unmerged review
[PR268](https://github.com/artinflight/vibe-kanban/pull/268), updating its scope
from the prior rollout documentation to this requested Dot follow-up. The
October 17 rollout record remains historical and independently reviewable.
Current Staging was reconciled without dropping local deployment notes; exact
local additions/edits are retained in T63_DEPLOYMENT_PICKUP_20261017.md. Checkout
`.agents`/`.codex` directories were empty; no checkout-local skill was present.
No model, effort, Recommend routing, AutoSwitch or approval configuration changed.

**Not merged and not deployed.** The previous feature's deployment authorization
does not apply to this follow-up. Staging retains release ownership, coordinated
with Preserve Dot Integration. Release needs a combined Python sidechat/browser
service update plus frontend; no Rust backend rebuild/restart is required.
Adopt the compatible service before enabling the controls. During a frontend
rollback keep the patched service and latest SQLite: an older service's automatic
reads do not understand the override. Service cutback requires an override-aware
compatible package, not a stale database restore.

Live source observed October 18 is the newer
`/mnt/vk-storage/vk-dot-dispatch-notes-20261018-v2/sidechat-release`, with the
October 17 sidebar frontend. Preserve all CU/Stop, continuation/context and
private dispatch-note changes (PR270–272). Do not install this checkout's older
complete runtime over that package. An isolated three-way integration of only
`sidechat.py`/`browser_api.py` read-state changes into that live source passes
all 71 sidechat tests; other Python modules remain byte-identical. This is
compatibility evidence, not an activated or fully accepted release candidate.
Private integration evidence/screenshots remain under
`/mnt/vk-storage/vk-dot-manual-unread-20261018/`.
