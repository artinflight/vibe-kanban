# Completed Checkpoint Display

The September 14 report used `disposition: "complete"`. The existing display
parser accepted only `continue` and `needs_input`, so it deliberately fell back
to raw Markdown. The earlier six renderer tests missed this state. This was a
coverage gap, not evidence that a deployment had removed the renderer.

The renderer now accepts legacy completion reports and uses the existing card
with a green Completed label. Evidence remains expandable. This is display-only:
it does not complete a native goal, alter its checklist, or rewrite saved logs.
Unknown dispositions, malformed fields, code examples and partial messages
remain ordinary content.

Eight renderer tests cover all supported states, including the exact reported
payload, safe escaping, malformed fields and code fences. Test completion as
well as continuing/input-needed states before future frontend swaps. Preserve
both the display hotfix and its regression tests in staging and release builds.

Live deployment evidence is recorded outside Git in
`/mnt/vk-storage/vk-goal-checkpoint-render/complete-release.json`.
The staging-based Green candidate must receive the corresponding frontend and
a refreshed artifact/backup receipt before cutover. The older readiness record
has been invalidated; this document alone does not approve a backend cutover.
