# Collapsible issues

The operator accepted the branch preview and authorized rebase-merge and live
frontend activation on October 18. Desktop cards and phone rows support a
per-issue chevron. Collapsing reveals the issue title, hides workspace/detail
content, adds 24px bottom padding and a subtle blue tint/3px left accent.
Expanding restores the workspace presentation. Titles remain visible when no
workspace is available. Existing orange phone attention styling takes precedence.

Expansion preferences use the existing `UI_PREFERENCES.expanded` map with
`kanban-issue:<UUID>` keys. No API, database or generated type changes are needed.
Preview proxy Host preservation also keeps subscriptions/preference requests
compatible with backend same-origin validation.

## Validation and review

Three focused DOM tests cover independent collapse/restore, title fallback,
detail visibility and navigation. Public browser checks at 1440px and 393px in
light and dark themes verified tint removal on expansion, exact 24px collapsed
padding, mouse/Enter, navigation and subscriptions. Test writes were intercepted.
The operator accepted the behavior, spacing and coloring in the preview.
English, French, Spanish, Japanese, Korean and both Chinese locales have labels.
Fresh rebase validation passes all four frontend type checks, local-web/UI lint,
ops/continuity checks, formatting, locale consistency/unused-key scans and the
three collapse regressions. The unused-key scan requires process-sandbox exit
here because its file-discovery subprocess was blocked. Local aggregate Rust
check/lint/tests are not represented: host GLib development prerequisites are
unavailable. No Rust files changed; applicable CI must pass before merge.

Rebased onto staging `fc7e00a42`; source changes applied without conflicts.
Continuity conflicts retain the new compact indexes and immutable archives.
Detailed feature history originally lived in the old branch pickup prefixes;
this topic document replaces duplication in all three indexes. Original branch
receipts are retained in [the feature history](VK_COLLAPSIBLE_ISSUES_HISTORY_20261018.md).

## Live release — October 18

[PR274](https://github.com/artinflight/vibe-kanban/pull/274) was rebase-merged
into staging at `5b43524ea35b2eb5dd80d0881dc8445489f4442f` after all 12
applicable checks passed in run 39119211683. The unrelated combined-capture
acceptance job was skipped. Canonical staging and main references are current.

The frontend is live at https://vibe.local/ with entry
`/assets/index-CHIz5WC2.js` and stylesheet `/assets/index-BThoGfNC.css`.
App/API version remains 0.1.42. Existing tabs need a refresh.

The clean release combines the merged feature with the exact eight incumbent
frontend files from `6655bba77`, retaining live Dot unread/attention/activity
and workspace-row readability fixes that remain in their separate PR268.
Build source `5338d42f4` and release source `872547964` have the same tree,
`814a571ad5a098df5335ae9b7f1d37d0a6e7c5af`. The release source includes the
merged staging ancestry. Relevant frontend inputs of the public feature head
and merged staging compare identically; no second build was needed for
commit-identity-only promotion. The release branch is published as
`deploy/frontend-collapsible-issues-20261018`.

The memory-capped Preparation runner passed combined type checking and the
production build. Packaging retains all 2283 incumbent non-index assets
byte-for-byte and adds 106 members. Existing tabs can still load their old
hashed chunks. The artifact viewer and notification service worker are retained.
Release manifest SHA256:
`bbc6b8b939787315c4935d2d95773d5ef75cf35ffc62690142a056c879e6cdd7`.

The incumbent frontend and candidate delta were uploaded to Desktop B,
downloaded, extracted and verified: 2284 incumbent files and 106 delta members.
The verified incumbent remains the immediate immutable pointer rollback.
Backup root: `desktop:B:/vk-backups/vk-collapsible-issues-20261018/`.
No SQLite or conversation snapshot was restored or needed for this UI switch.

Actual served browser acceptance passed at 1440px and 393px in light/dark
modes: exact packaged entry, title/tint transitions, 24px padding, mouse/Enter,
unchanged navigation, accepted subscriptions and preference-save requests.
All 54 visible actionable workspace rows per case retained full opacity.
No runtime exceptions or WebSocket errors occurred. Root, JS, CSS, artifact
viewer and service-worker bytes matched the release. All seven monitored
production service PIDs and definitions, the API route and sidechat pointer
remain unchanged; no Vibe, Dot or agent restart/reload occurred.

All automated application writes were intercepted. Physical-phone acceptance,
live preference reload durability, drag persistence, workspace mutations,
attachment uploads, saved-message edits and intentional notification clearing
were not write-tested. Their existing code paths remain unchanged. The operator
accepted the feature, spacing and coloring through the branch preview.

Private preparation, backup, source binding, activation and browser receipts
are retained under `/mnt/vk-storage/vk-collapsible-release-20261018/` and are
not published as application data.

Branch preview remains available at:
https://mcp-server.tail744c4.ts.net:8443/projects/1cf19067-4055-4432-bbc1-581919f9185d
