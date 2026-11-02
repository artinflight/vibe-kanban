# Scrolling projects menu pickup — 2026-11-02

The projects menu change is in `vk/9cb7-vk-scrolling-pro`, based on `aceb355e9`.
Desktop grid tracks now allow the AppBar to shrink within the viewport. The rail,
expanded names list and mobile projects list have hidden scrollbars and contained
overscroll. Footer/actions stay outside the scrolling list. MobileDrawer exposes
an optional content class override used only by project navigation.

Validation passed: required repository format, UI format/lint/type check,
shared layout ESLint, shared frontend type check (bounded 3 GiB heap), local
app types, and ops governance. The shared type check first exhausted the default
heap; the bounded rerun passed. Browser receipts are in
`.vk-preview/scroll-check/`. The isolated fixtures use
actual AppBar/MobileDrawer components and extracted SharedAppLayout grid/mobile
markup with 60 synthetic projects. They do not contact a backend. Before-change
reproduction: desktop document grows to 3015 px; mobile list expands to 3132 px
and pushes creation controls beyond the sheet. After-change checks pass at
1440×900, 1024×600, 393×852, 393×600 and 740×393:
internal wheel/touch scrolling, hidden standard/WebKit scrollbars, viewport-sized
document, stationary controls, final-project selection, expanded-name scrolling,
and keyboard project reordering. No page errors. This is browser emulation, not
physical-phone QA. Dependencies link to an existing SSD install; no new download.

Committed locally at the operator’s request; no push, PR or runtime deployment.
Use `git log -1` for the commit identity. Preserve the current
public release and all preview routes. Production details remain in [STATE](STATE.md)
and [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json). Normal deployment/PR gates still
apply if requested later.

Prior pickup: [previous record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [HANDOFF history](HANDOFF_HISTORY_20261017.md).
