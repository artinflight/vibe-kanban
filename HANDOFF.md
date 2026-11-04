# Read Later implementation — 2026-11-04

Implemented VK Dev T91 on `vk/f57c-read-later` after the operator lifted the hold.
The operator requested a local commit of the implementation and continuity notes;
see Git history for its identity. The operator subsequently authorized deployment:
Read Later is live at https://vibe.local as of November 4, 15:11:24 UTC. Reload
existing tabs. No push, backend restart or additional agent launch.

Behavior:
- Sidebar sections: Attention, Read Later, Running, then Completed/idle history.
  Read Later starts folded; it has an item count and a dedicated phone filter.
- Unread workspace rows, project notices, issue cards/list rows and inbox
  notifications expose Read Later and Return to Attention. These actions stop
  click/key propagation and never call mark-read, navigation or agent APIs.
- A browser-local Zustand preference is scoped by host, user, entity kind and ID.
  It survives reloads, retains unread badges and falls back to memory if browser
  storage is denied. There is no cross-device synchronization or backend schema.
- Issue preferences also defer linked workspace rows. Opening an item continues
  to use the existing explicit navigation/read behavior. Read items leave the
  deferred collection; unrelated attention/approval/running semantics are kept.
- Completed is the existing idle collection, not an issue status transition.

Validation completed:
- `pnpm run format`; touched UI and test files additionally formatted with the
  web-core Prettier configuration (root format does not include packages/ui).
- `pnpm run ops:check`, `pnpm run web-core:check`, `pnpm run local-web:check`,
  `pnpm run ui:check`; all passed. Type checks required
  `NODE_OPTIONS=--max-old-space-size=2048`; the inherited 768 MiB heap exhausted
  before producing results. Existing SSD dependency caches were reused.
- ESLint passed for all changed UI components and web-core files, using the
  existing UI and local-web configurations respectively.
- 11 Read Later interaction/persistence tests pass:
  `VK_TEST_OUTPUT=<mounted-SSD-directory> node scripts/testing/run-read-later-tests.mjs`.
- 12 existing tests pass with `node --experimental-strip-types --test` against
  `workspaceSidebarPagination.test.ts`, `dotProjectNotices.test.ts`, and
  `dotWorkspaceActivity.test.ts` in their existing directories.
- Real Chromium at 1440 and 393 px passed defer, persisted reload, restore and
  horizontal-overflow checks with zero read calls, zero application writes and
  zero page errors. A desktop action overlay and phone section-height overlap
  were found and fixed during these tests. All application writes were
  intercepted; unread summaries were disposable browser response fixtures.
  Reproduce using `scripts/testing/read-later-browser.mjs` with VK_TEST_BASE and
  VK_TEST_OUTPUT. Results/screenshots: `/mnt/vk-storage/vk-read-later-20261104-f57c`.
- `git diff --check` passed. No Rust/full workspace/remote deployment checks or
  physical-device tests were needed/run for this frontend-only change. No
  production unread records, conversations or provider turns were modified.

The lightweight branch frontend used the verified existing public gateway on
4720. The preview guide's historical 4511 default is not listening; the current
workflow/runtime record takes precedence. No isolated backend was started and no
public preview route was replaced. The temporary frontend preview was stopped
after browser validation. Preserve every other preview/service.

Deployment: current live source was composed with the Read Later patch and
passed the preservation gate before build and publication. The packaged and
served frontend passed desktop/phone Read Later and five-layout scrolling tests.
All live writes were intercepted. The software recovery archive was fully
restored on SSD and independently read back from Desktop B before activation.
The shared backup lane was initially busy; publication waited for its release,
and no backup exception was used. The pointer switch took 0.012 seconds. All five
service identities, backend hash and database identity/99 migrations remain
unchanged. See VK_READ_LATER_DEPLOYMENT.md and LIVE_DEPLOYMENT.json.

Latest refinement: `b1f609719` makes the shared action icon-only with accessible
label/tooltip, places workspace/project/saved-issue actions in the existing row,
and moves Kanban actions into its existing header. Deployed 2026-11-04T20:16:46.412428+00:00.
The first Read Later build accidentally enabled VITE_DOT_SIDECHAT; the preceding
visibility bundle compiled it disabled. Stored Dot notices resurfaced because
polling was re-enabled, not because acknowledgement records were reset. The
correction explicitly restores VITE_DOT_SIDECHAT=0; three-release disposable
browser proof is in `/mnt/vk-storage/vk-read-later-20261104-f57c/inline-icons/dot-build-setting-browser.json`.
Current source/output manifests, candidate/public desktop+phone icon geometry,
zero polling/read/write assertions, scrolling cases and independent Desktop B
recovery receipts are under `/mnt/vk-storage/vk-read-later-20261104-f57c/inline-icons`. All focused types/lint, 11+15+10 interaction
and five preservation tests pass. No backend/data mutation or service restart.

Next: operator UI acceptance and optional staging integration are separate. No
further deployment is pending. A staging PR still requires the full repository
baseline and branch freshness; any later publication needs a fresh preservation
check against the then-live source. No main promotion was performed.

Prior continuity: [pre-reconciliation record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [full historical archive](HANDOFF_HISTORY_20261017.md).
