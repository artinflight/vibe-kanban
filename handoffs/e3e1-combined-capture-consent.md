# e3e1 combined capture/consent preparation

Intent: build only reviewed PR236/239 source fixes on actual deployed source,
with hosted validation and artifact/rollback identity. No deployment authorized.
Branch: fix/e3e1-combined-capture-consent.
codeSha: pending initial feature commit; read exact codeSha with
`git log -n 1 --pretty=format:%H -- . ':(exclude)handoffs' ':(exclude)runs'`.

Changed: 21 reviewed source/test files, one combined writer/legacy-reader test,
compiled incumbent reader fixture, source fence, paired artifact builder,
opt-in hosted workflow, and current handoff/release documentation.
Commands/results so far: fresh git fetch; read-only executable/environment/
frontend-source binding; both scoped git apply --check passed; all 577 mapped
live frontend application sources matched; source fence passed; scoped rustfmt.
No local Cargo compilation, production server launch, security or data writes.

Decisions: actual production base overrides routine latest-staging baseline;
keep the live-only frontend overlay, no wider historical merges. Build only
server/assets; retain incumbent support artifacts/settings. Native Codex Cancel
wording remains upstream; no consent bypass. Keep all review/hold safeguards.

Resume: run Test workflow_dispatch on this exact feature head; inspect the
combined acceptance job, correct scoped failures only, download artifact to
Desktop B and verify hashes. Append exact tested source/run/artifact evidence.
Next: normal explicitly authorized release flow after fresh backup/drain gates.
Known issues: no live release acceptance/physical Android QA yet; no actual
report delivery or badge clearing performed; incomplete past captures remain
unverifiable. See VK_COMBINED_CAPTURE_CONSENT_20261010.md.
