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

## Release

Promotion and frontend release validation are in progress. Incumbent source
`6655bba77` includes newer live Dot activity and readable workspace-row changes
not yet present in staging. The release must preserve these frontend sources,
existing hashed assets and artifact viewer. No backend, Python, gateway or agent
restart is part of this frontend-only activation. Current data stays in place.

Public branch preview:
https://mcp-server.tail744c4.ts.net:8443/projects/1cf19067-4055-4432-bbc1-581919f9185d
