# Dot Chat text matches workspace text

Dot message paragraphs and composer text use the same `1rem` base as the native
workspace WYSIWYG message/editor. The existing mobile composer rule stays16px,
matching the workspace input and retaining its phone zoom protection. Font family,
line spacing, metadata, timestamps, controls and the compact project unread badge
are unchanged. No routing, reply, draft, notification or read-state code changes.

Actual live compiled-app measurements before this correction, using synthetic
messages in the real workspace renderer and blocking real writes:

| Text | Desktop before | Mobile before | Matched target |
| --- | --- | --- | --- |
| Workspace message |16px|16px|16px|
| Dot message |13px|13px|16px|
| Workspace composer |16px|16px|16px|
| Dot composer |13px|16px|16px|

Both project/workspace layouts use IBM Plex Sans with the existing emoji/sans
fallbacks. Relative message sizing follows workspace text when the root text
scale changes; mobile inputs retain the same16px override as workspace inputs.

`scripts/dot-sidechat/typography-browser-check.mjs` compares computed Dot body and
composer sizes/families with the actual native workspace nodes. It requires a
native reference, checks every rendered message and horizontal overflow, and can
reuse a measured reference after navigating to project-only chat. Acceptance uses
the compiled candidate and actual trusted served assets at390/1440, with isolated
API fixtures. Reply/draft reload, exact destinations, read/unread independence and
attention navigation remain affected-interaction checks. No real chat writes.

Use the existing hosted frontend-only build, immutable asset retention, verified
B archive and old/new-asset rollback flow. Keep all incumbent roots and latest
data/Python untouched. Private Nightly/Disk admission evidence must account for
remaining demand and resident bytes once; browser phases are bounded, sequential
and separate from agents. No local heavy build, service restart, backup capture,
model/effort or Recommend change. The private publication receipt distinguishes
before/candidate/live measurements and exact-head CI; a build alone is not live
acceptance or whole-Nightly recovery evidence.
