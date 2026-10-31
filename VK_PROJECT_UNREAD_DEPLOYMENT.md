# Project conversation unread fix — live frontend update

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
