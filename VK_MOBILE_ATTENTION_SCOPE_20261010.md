# Phone-only attention, October 10

The owner clarified that unread/review visibility was requested for phones only.
The October8 follow-up incorrectly tinted desktop cards and added another label
row. This correction restores desktop presentation without changing attention
flags, classification, polling, review controls or conversation read semantics.

## Changes

- Whole-card attention tint, border and stripe (including hover) apply only at
  max-width767px, matching the existing phone layout breakpoint.
- Desktop Kanban removes the added attention class and label prop/row. Existing
  compact unread/approval/status indicators and the explicit review flag remain.
- Phone task labels/highlights and linked workspace highlights remain. Work View
  landing, status defaults, keyboard handling and one-tap Send are preserved.
- The existing read-only mobile UX harness now requires desktop cards to have
  neither the added label nor attention tint, including nested workspace cards.

## Validation and limits

Actual IssueWorkspaceCard/KanbanCardContent source and Tailwind-processed CSS were
rendered in an isolated Chromium fixture. Ten before/after observations cover
390/767/768/1440px, plus corrected390/1440px dark. Desktop attention gradients
and hover are absent, borders match unhighlighted controls and the added label
is absent; phone task/workspace gradients remain. Screenshots and result JSON
are synthetic. No backend, production draft, message or attention flag was used.
Bounded synthetic evidence is retained at
/mnt/vk-storage/vk-mobile-attention-scope-20261010. The full updated
backend-connected UX harness was not rerun in this turn.
Physical phone behavior is not claimed.

UI/web-core/local-web/remote-web type checks, UI/local frontend lint, focused
shared-source lint, repository/UI formatting, browser script syntax, diff
whitespace and ops governance passed. Full local Cargo/build checks are deferred because SSD free space
was372MB; no build, cleanup or shared-target mutation is part of this correction.
CI must provide the wider backend baseline. No backend source/types changed.

## Release boundary

Use the existing PR233/Dev/Staging workflow. The prepared combined frontend
40e56d101ab290820c6eacf0d0354d859eab4179 lacks this correction; it must not be
published as though it restores desktop attention. Staging must integrate this
focused follow-up onto its current combined source and rebuild only the frontend,
retaining newer chat/consent repairs, Work View and Send. Preserve live/fallback
assets, backend and current data. No merge, deployment or restart occurs here.
