# Steering frontend release coordination

This is the stable coordination note for the current steering release and a later
combined Dot notification candidate. Update status here without changing another
owner's worktree, branch, running browser or release pointer.

## Current candidate

- Preparation root: `/mnt/vk-storage/vk-sent-steering-release-20261016`.
- Clean source: `/mnt/vk-storage/vk-sent-steering-release-20261016/source`.
- Pinned candidate commit: `1d074941dc4145f6827beb2c43775bab6caec20e` on `prep/sent-steering-live-20261016`.
- Release directory: `/mnt/vk-storage/vk-sent-steering-release-20261016/release`.
- Build/preparation status: complete and verified; release is not activated.
- Live baseline: `9d76d7faf00a0997c9580cf3c8d3bd63f6440ad1`, serving
  `/assets/index-B-YJtP-l.js` from
  `/mnt/vk-storage/vk-mobile-dot-route-20261016/release`.
- Included delta: PR257's two steering runtime files and synthetic regression
  fixture, copied from source fix `ca9911225`. All other live frontend sources
  are retained. Production Dot mode remains enabled and fixture mode disabled.
- Activation scope: static frontend only; no backend/API/sidechat-store change,
  service restart, pairing, grant or conversation mutation.
- Current static rollback: Desktop B archive and full readback/restore verified;
  see `rollback-verification.json` under the preparation root.

Fresh served asset/source-map verification and a synthetic compiled-bundle
reproduction prove that the currently live frontend lacks PR257. Exact-head
PR257 CI is green. PR257 merged into staging as
`9301e6a463a4832cc14976c7a19fa40f58567b05`; canonical staging/main references are
current. The pinned candidate and its runtime sources are published at
`prep/sent-steering-live-20261016` without merging the unrelated Dot PRs.

The existing preparation runner, production build, four frontend type checks,
lint, nine packaged Send/steering cases, five Mobile/Dot viewports, 21 history
tests and 16 link tests pass. Two actual live read-only viewports pass with
writes blocked. The compiled entry is `/assets/index-CGY9AEy0.js`, accompanied by
the unchanged `/assets/index-CEkW_l7u.css`. Old entry assets are retained; the full package has 1,864 files and preserves
inline compatibility scripts. The rollback archive covers all 1,760 incumbent
files. Source maps verify the exact fix and unchanged Mobile/Dot/history/link
sources. Desktop upload/hash/readback/full restore verifies the old static tree.

Read-only final activation preflight passed. Readiness evidence is
`READINESS.json` under the preparation root. The prepared action is
`activate-frontend.py`: default invocation performs read-only checks;
`--activate` is reserved for separately approved release-owner use. No production
pointer has moved. Backend, static server, gateway, Dot and notifier PIDs match
throughout preparation. No restart, forced agent stop or phone re-pairing is
needed. The release owner must approve the exact static switch and verified
static rollback scope, rerun fresh identity checks, then execute post-switch
acceptance. Existing tabs need a normal refresh afterward.

Old drafts created before deployment are intentionally not bulk-deleted because
they cannot safely be distinguished from unsent recovery drafts. An already-sent
legacy draft may need clearing once after refresh; never resend it merely to
clear the composer. Failed and queued drafts remain recoverable.

## Later Dot notification handoff

Seamus's coordination identifies the Dot owner workspace as
`de2d98a3-b73f-4e70-9445-caee5cae188c`, branch `vk/de2d-vk-preserve-dot`, PR254.
The new work adds persistent Dot unread/Needs Attention state, separate violet
badges beside workspace indicators, and additive Python sidechat API/store
changes. That notification delta is **not included** in this pinned candidate.
The existing live Mobile/Dot functionality is included; this does not imply that
the newly implemented notification functionality is ready or enabled.

The Dot owner will hand off tested immutable commit(s), backend deployment and
integration checks separately. A later combined candidate must preserve the
current Mobile/Dot frontend and PR257, install/verify the required sidechat API
and store changes before activating notification UI, and validate persistence,
unread clearing and independent workspace/Dot indicators. Do not follow the
moving PR254 branch head or enable its new UI against the older API implicitly.
Its current not-ready status does not hold or replace this steering candidate.

Current-release readiness does not activate any notification UI or deploy a
sidechat API/store update. The Dot owner retains that separate deployment handoff.
