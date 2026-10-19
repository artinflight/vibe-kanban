# Exact workspace destinations and Personal visibility

Workspace names retain their current font size and single-line ellipsis. The
narrow header now supplies the same native `title` as the desktop header, with
the complete current name. This uses browser hover behavior; no custom tap
tooltip or new gesture is added. Touch still has the full text in the DOM for
accessibility and native text selection. Hosted desktop/narrow checks exercise
the same long name, ellipsis, hover metadata, touch without navigation or sending,
and title updates when the selected workspace changes.

The project Dot sidebar also resolves its human workspace heading from the
ID-validated workspace record, keeping the project name as context. A pending
record shows a neutral workspace label; a delayed sibling response cannot rename
the displayed destination. Linked workspace breadcrumbs expose their complete
labels through native titles too. Existing header sizes and layout are retained.
The mobile chat header uses the same exact-workspace branch fallback as desktop
when a human name is unavailable. These corrections need only a frontend release;
they add no read-state writes, pairing capability or backend reload requirement.

The Project conversation panel previously replaced a requested workspace absent
from its sidebar snapshot with the first linked sibling. A loading, filtered or
stale snapshot could therefore change the destination. Issue workspace cards also
inferred a local link from a human name, which is not a unique identity.

The requested workspace ID is now authoritative. Only an explicit stored local
workspace link permits card navigation. Missing or failed record/session responses
leave a placeholder, and mismatched API workspace/session identities fail closed
before prompt delivery. No server or access change is required.

Session selection is scoped to host and workspace during render, before stream or
composer subscriptions. Initial latest-session selection remains stable through
list reorder. Delayed creation callbacks cannot select a session in a subsequently
opened workspace, including navigating away and back; sends already started remain
pinned to their original destination. Existing keyed composer/draft lifetimes remain.

Personal defaults and the older saved built-in self-only choice now include the
authenticated self OR unassigned. Search, priority, tags, blocked/subissue rules,
sorting and explicit custom assignee choices retain their meaning. No assignments
are written. Workspace headers prefer the human workspace name over the branch
and use larger, high-contrast text in full and embedded views.

## Validation and release boundary

`node scripts/testing/test-workspace-destination.mjs` runs actual project panels,
query/session/send hooks and Personal filters with controlled synthetic transport.
It covers stale/loading lists, explicit/unlinked cards and reorder, delayed record
responses, rapid/return navigation, in-flight creation, mismatched API identities,
and self/unassigned/other assignees with the other issue filters. No real prompts
or assignment/read-state writes are used. Hosted CI runs this regression.

Focused source checks passed against the actual production panel, session/create/send
hooks and Personal filters. Existing desktop/mobile sidebar tests also verify that
reordered rows still select their displayed IDs. Repository formatting and governance
passed; hosted frontend type/lint/format and local/remote builds passed at the first
implementation checkpoint. An initial pickup-size and mobile test-timing failure
were corrected without changing application behavior.

A bounded actual compiled-app mobile workspace case measured20px human headings
and16px Dot/native message/composer text, with exact copied code, reply/draft reload,
manual unread/attention independence and exact destination intact. Further MCP
browser probes stopped at genuine pressure/capacity guards; all own children are
terminal and the unused local window is released. Remaining desktop/mobile component
acceptance uses hosted Chromium with the built candidate stylesheet and synthetic
transport, rather than consuming Nightly/Disk resources. Exact final-head CI/build
and browser results are recorded in the existing PR and private owner handoff. The live font-only
ancestor is preserved. Code blocks plus these UI corrections are not activated;
separate owner approval and coordinated frontend-only release remain required.

The approved `5c411b59b` package was selected on October19 and its served mobile
checks passed. Served desktop testing then reproduced a long-name overflow:
the navbar's automatic minimum width expanded the shell's `auto 1fr` grid.
The original component fixture used a column layout and did not expose it.
Frontend-only rollback restored the16px font baseline while retaining every
incumbent and candidate asset; services, agents and conversations were untouched.
The correction sets the navbar's minimum width to zero. The regression fixture
now uses the shell grid and checks actual header bounds as well as body overflow,
so a parent clipping overflow cannot conceal a failure. This correction requires
its own exact-source validation and release selection; it is not deployed by
the earlier exact-package approval.

Project questions and genuine shared issue questions are independent notification
scopes. A genuine unresolved shared issue question is intentionally discoverable on
its sibling workspaces; a project question belongs only to the project notice.
Read-only diagnosis preserves both questions and manual review/read-state flags.
Exact operational note/workspace IDs and metadata evidence remain private.
