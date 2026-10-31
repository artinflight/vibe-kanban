# Project conversation unread/review corrections — live frontend update

## Same-workspace reselection correction — published 12:04:09 UTC

Source `b990b5939642b1ac7e744a9290840a731fa3f550`; public JS
`index-Cy2e9ltd.js`, unchanged CSS `index-CUBB2mA2.css`, version 0.1.42. Live frontend:
`/mnt/vk-storage/vk-unread-reselect-20261031-c097/reselect-release/paired/candidate`.
The public HTTPS root/new bytes and prior entry assets verify with pinned TLS.
All five live service identities and the database identity/99 migrations remain
unchanged. Atomic pointer replacement took 0.0056 seconds. No backend restart,
schema change, provider execution or device action.

The repeat nested workspace click now performs an explicit read without requiring
a route change. Thirteen mounted regressions, shared TypeScript, focused ESLint,
required format/ops and production build pass. Exact browser regression fails on
the previous live bundle and passes against both candidate and published live UI.
At 1440 px, initial opening clears, a reseeded unread survives polling, the actual
nested workspace repeat click emits a new 200 and clears persistently without
changing URL. At 393 px, closing/reopening clears persistently. Both reload checks
pass with no page errors. Only this task's own workspace unread/seen state is used.

Every existing activation gate was retained. Candidate desktop/mobile SQLite
review-flag persistence tests and real backend manual-clear/reload, unrelated flag
and native unread preservation all pass. Original flags and task body restored;
all unrelated browser mutations blocked. Both paired roots retain 559 assets.
The 43,244,856-byte frontend/source software recovery package was independently
read back and hash-verified on Desktop B. Previous full-state recovery retained.

Evidence root: `/mnt/vk-storage/vk-unread-reselect-20261031-c097/reselect-release`.
Key files: `browser-candidate-reselect.json`, `browser-live-reselect.json`,
`own-candidate-verified.json`, `browser-candidate.json`, `activation.json`,
`after-live-pinned.json`, `Desktop-B-recovery-verified.json`, `frontend-source.json`.
Temporary frontends/browsers closed. Exact operator URL/workspace flow is still
unconfirmed; both earlier publications were reported unresolved. Full PR/Rust/
hosted CI and physical-phone interaction not claimed. Push/PR/merge remain held.
Backend/history direct frontend roots retain October 30 UI. Existing browser tabs
need reload to use this publication. This scoped automated evidence does not claim
operator acceptance of the full original symptom.

## Reproduction before the third publication

The operator reported "no change" after the second publication. A fresh test
clicked the actual nested workspace card, including a repeat click while its
conversation remained open. Initial opening clears native unread, but the repeat
click sends zero seen requests and leaves unread true. Prior "reselect" coverage
clicked the parent issue card, changing routes and concealing this failure.
`same-workspace-reproduction.json` under the investigation root records the live
200 initial read, unread reseed, zero extra requests and unread still true.

A shared explicit project navigation/read action addresses same-route selection.
It reads only a deliberate click on the current project/issue/workspace in a visible
document; ordinary destination loading still gates initial reads. Polling must
preserve subsequent completions. The exact new browser regression fails on the previous release at the repeat
nested-workspace click. The corrected release and subsequent proof are above.
Push, PR and merge remain held for operator confirmation.

## Previous corrective release — published 11:15:55 UTC, operator still reports unresolved

The first publication below was reported unresolved by the operator. It proved
request emission only. Follow-up real project-board tests now prove native read
persistence. The mobile UI also reproduced manual review flags falsely shown as
unread "Needs review" with no clear action. A production desktop test caught parent
card mouse-up navigating before nested control clicks. The correction separates
manual flags from native activity, adds mobile clearing, and prevents parent
activation from interactive children.

Application source at that publication: `3366b015155bfa1857b898e263a6d966aabbe452`.
Public JS: `index-9ssuLQsW.js`; CSS/version remain `index-CUBB2mA2.css` / 0.1.42.
Its frontend pointer resolved to
`/mnt/vk-storage/vk-unread-reselect-20261031-c097/final/paired/candidate`.
The switch took 0.0154 seconds; all five live service identities remained unchanged.
No backend restart, schema change, provider execution or device action occurred.
Both paired roots retain 507 assets. Public HTTPS health, identity, exact new entry
bytes and prior entry assets pass with pinned certificate/hostname verification.

Eight seen and seven mounted UI regressions pass. The nested workspace regression
fails on the old desktop handler. The exact production build and focused types/
lint/format/ops checks pass. Persistent SQLite browser fixtures pass at 393/1440 px
on candidate and live frontend: one clear write, reload persistence, unrelated
metadata preservation and no navigation side effect. The real live mobile test
uses ONLY this task's own issue/workspace. It seeds a manual flag and native unread,
clears the manual flag through the UI, verifies reload and that another flag/native
unread survive, then opens the conversation and verifies native unread clears.
Original flags/task body were restored; backend-managed metadata lines were handled
separately. No unrelated workspace markers were modified. No page errors occurred.
Physical-phone interaction and full PR/Rust/hosted CI are not claimed.

Recovery: `paired/fallback` under the current evidence root retains the previous
live index plus all 507 assets. Frontend rollback uses an owned atomic pointer
replacement; no database restore or service restart is needed. The 37,762,844-byte
paired frontend/source recovery package was independently restored and hash-verified
on Desktop B through the existing native object store. Previous backend/full-state
recovery remains preserved. This is software recovery, not a new mutable-state
snapshot. Existing backend/history direct frontend roots retain their prior bundle.

Evidence for that publication: `/mnt/vk-storage/vk-unread-reselect-20261031-c097/final`.
Key files: `frontend-source.json`, `pair-receipt.json`, `activation.json`,
`own-candidate-verified.json`, `own-live-verified.json`,
`browser-candidate-review-verified/results.json`, `browser-live-review/results.json`,
`after-live-pinned.json`, `Desktop-B-recovery-verified.json`.
Temporary frontend/browser processes were closed. Nothing was pushed; PR and merge
remain on hold. Reload existing browser tabs to load the correction.

## Initial publication — superseded and reported unresolved

The operator requested the live update on 2026-10-31. It was published at
10:38:31.936 UTC from `f95bab83836d467f972e904710220eee09406d5b`, version 0.1.42.
Project workspace chats now share Workspaces' visible-chat read effect. Loaded
workspace identity, hidden-document handling and no polling-based clearing remain.

## Release and preservation

Public origin: `https://vibe.local`. Public entry JS: `index-hKvj8yI6.js`.
CSS remains byte-identical `index-CUBB2mA2.css`. Source differs from the October 30
frontend only in the two callers and shared seen hook. The dependency lock matches
the reused SSD package installation. Production `tsc && vite build` passed with a
bounded 4 GiB heap, with existing Browserslist/Tailwind/Sentry warnings. Every one
of 417 build files is size/SHA256-bound and the artifact viewer matches its source.

`/home/mcp/.local/share/vibe-kanban/frontend-dist/current` now resolves to
`/mnt/vk-storage/vk-project-unread-deploy-20261031-c097/paired/candidate`.
The verified atomic pointer replacement took 0.00645 seconds. All 455 hashed assets
are retained in both new paired roots, including every prior live asset.

Backend PID 645213 and invocation `440a8acde3f4428abc3a27a8f601808d` stayed unchanged;
its executable hash remains `137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2`.
History reader, history proxy, gateway and static server identities also match.
No backend restart, routing change, database restore, schema mutation, provider
inference, device action or notification-repair write was performed. Backend and
history-proxy direct frontend roots retain the October 30 bundle; public frontend
requests use the new pointer. Reload existing browser tabs to load the fix.

## Validation and limits

Eight mounted React regressions pass; removing the project call reproduces five
failures. Shared/local frontend type checks, focused ESLint, full required format,
ops checks, frontend import guards and diff checks passed during implementation.
The deployment reran regressions, format and ops checks, plus the production build.

The exact packaged candidate and live public-gateway frontend passed Chromium at
1440 px and 393 px. Opening/reopening the actual project workspace sent exactly
two seen requests per viewport; issue-only navigation, closing and summary polling
sent no extra seen requests. Workspace summary reads were allowed. Seen and other
mutating requests were intercepted, preserving live unread flags, configuration
and history. There were no page errors. Actual persisted unread transitions and
physical-phone behavior are not claimed. Temporary frontend/browser processes
were closed; the initial dev-preview timeout was superseded by successful checks
of the packaged production frontend.

Public HTTPS health/capability routes, current database identity/migration count,
new entry bytes and both old entry assets passed. HTTPS used the installed pinned
vibe.local certificate with OpenSSL partial-chain trust; hostname and certificate
verification stayed enabled. No global trust configuration was changed.

Full Rust/full PR baseline and hosted CI were not run. Automatic approval review
rejected pushing source/launching GitHub workflows as an unapproved external export.
No push or workflow launch occurred. The release used the exact committed source
and a locally built artifact. Git integration remains separate from deployment.

## Recovery and durable evidence

The previous public frontend remains untouched at
`/mnt/vk-storage/vk-deployment-reconcile-20261030/activation-release-1/paired-frontend/candidate`.
The new frontend-only fallback is
`/mnt/vk-storage/vk-project-unread-deploy-20261031-c097/paired/fallback`.
Its index is byte-identical to the previous live index and it retains both asset
sets. Frontend rollback would atomically repoint `current` to that fallback after
checking current ownership; it requires no database restore or service restart.
This documents recovery and does not authorize an unrelated future cutback.

The paired frontend archive and incremental fix source bundle total 33,406,911
bytes. Existing native Desktop B object-store transport independently restored
and hash-verified both, including recovery descriptors. This is software recovery,
not a new mutable-state backup. The prior full deployment backup is preserved.

Evidence root: `/mnt/vk-storage/vk-project-unread-deploy-20261031-c097`.
Key receipts: `frontend-source.json`, `pair-receipt.json`, `activation.json`,
`before-live-pinned.json`, `after-live-pinned.json`, `browser-candidate.json`,
`browser-live.json`, `Desktop-B-recovery-verified.json`, `manifest-after-verified.json`.
`LIVE_DEPLOYMENT.json` is updated without rewriting original backend provenance.
