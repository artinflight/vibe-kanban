# Visible conversation reads — frontend-only correction

The operator reported the initial manual-only release stopped normal clearing.
That release is superseded by the corrective implementation below; the corrected
frontend is published at 2026-11-02T17:45:07.515775+00:00.
Source integration uses [PR #288](https://github.com/artinflight/vibe-kanban/pull/288)
into staging with the requested rebase method. Its final checks and merge event are
authoritative.

## Current behavior

Deliberately opening or reselecting a conversation, scrolling while reading, or
choosing its jump-to-latest button can mark it read once the latest loaded
assistant reply's end is visible and unobscured in the focused foreground window
for 350 ms. A restored older scroll position stays unread until the latest reply
is reached. Hidden panels cannot acknowledge replies. A reply changing during
the dwell cancels the captured intent. Tab return, passive polling and newly
arriving output alone do not create read intent.

The explicit **Mark all replies read** control remains a fallback in project
chat, Workspaces chat and Workspace Actions. Pending duplicate bulk clicks are
blocked; failure leaves unread intact and requires another deliberate attempt.
No backend/API/schema/generated-type changes are included.

The unchanged bodyless seen API clears the entire workspace across sessions.
Frontend visibility checks cannot supply exact server-side reply revisions or
eliminate the arrival race between the check and server transaction. Those
limitations remain under the operator's frontend-only boundary. Historical
cleared unread flags are not reconstructed. Old loaded tabs need to reload.

## Validation boundary

Fourteen mounted read-on-view regressions, seventeen existing explicit/readiness
regressions and seven adjacent navigation regressions pass. Shared frontend types,
focused ESLint and required formatting pass. The two pre-existing conversation
renderer lint warnings are unchanged. The manual-only live bundle reproduces
zero clearing requests when opening a loaded conversation in a phone browser.
Browser application writes are intercepted; disposable in-memory SQLite supplies
unread state while real history/metadata use read-only live routes.

Real-layout acceptance checks project and Workspaces views at 1440/393 pixels,
including saved scroll/jump-to-latest, initial clearing, deliberate reselection
or reopening, background return/polling preservation, failed requests and the
explicit fallback. All four candidate and all four served cases pass with zero page errors and
zero live application writes.
The full hosted validation-only [Test
baseline](https://github.com/artinflight/vibe-kanban/actions/runs/41493120165) passes on
corrective source b8bad21792f863bce31c42742f7439cc8539503a: frontend
builds/lint/types/regressions, governance, Rust lint, generated types/SQLx, workspace
tests (excluding Tauri), storage/watchers and scheduled persistence. Tauri
fmt/lint/compile checks pass separately.

Private remote backend checks are skipped by the workflow because its deploy key
is unavailable; that coverage is not claimed. The production build exits zero;
its optional Sentry upload reports unavailable authentication and is not certified.

Automatic approval review rejected an optional real-server read-state test because
it would change existing per-turn bits without an exact restoration path. No live
database unread mutation or real persistence acceptance is claimed. No provider
execution or physical S25 action is part of this task.

## Source and release provenance

Corrective feature source: b8bad21792f863bce31c42742f7439cc8539503a.
The preserving build starts from live base
800011bd573e2869d6ea4c0e5bfba4d9046d9cbe plus initial frontend feature
70d7f5b0516a784ca6f27ba9fc6245b441666663, then overlays the corrective package
files. Newer git-preservation notices remain byte-identical. Version is 0.1.42;
asset hashes identify the actual build. Entry assets are index-C2FVxMt6.js /
index-C-pTuj_j.css; both paired roots
retain 822 assets. STATE/LIVE_DEPLOYMENT and the fresh activation receipt identify
the serving build. The pointer switch took 0.013806 seconds; five service identities,
backend executable hash and DB inode/path/99 migrations are unchanged. Public
TLS/index/assets/health pass. The 95,264,657-byte software recovery archive passed
restore checks for 3,460 files and permissions and independent Desktop B readback.

Evidence root: `/mnt/vk-storage/vk-disappearing-unread-20261102-3ad7/`.
Corrective software source/build, paired frontend/fallback, Desktop B recovery
and activation evidence use `fix-release-2`. Original manual-only publication
at 2026-11-02T16:27:39.360218+00:00 is retained under `fix-release-1`; it is not
acceptance evidence for restored read-on-view. No backend restart or DB restore
is needed for this frontend pointer publication.

The operator authorized push, a staging PR and rebase merge. Main promotion is
separate; Git integration does not republish assets or restart services.
