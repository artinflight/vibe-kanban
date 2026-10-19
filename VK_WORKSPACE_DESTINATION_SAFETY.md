# Exact workspace destinations and Personal visibility

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

Desktop/mobile computed typography and final hosted build/CI acceptance must be
recorded separately before claiming this candidate release-ready. The live font-only
ancestor is preserved. Code blocks plus these UI corrections are not activated;
separate owner approval and coordinated frontend-only release remain required.

Project questions and genuine shared issue questions are independent notification
scopes. A genuine unresolved shared issue question is intentionally discoverable on
its sibling workspaces; a project question belongs only to the project notice.
Read-only diagnosis preserves both questions and manual review/read-state flags.
Exact operational note/workspace IDs and metadata evidence remain private.
