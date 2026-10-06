# October 6 Combined First-Run Acceptance

This is the retained staging test driver, not a production deployment command.
It is pinned to PR147 `86f62b2a4a1baff54cde715749b97f283907b8f6`, CU PR38
`95e7aea47e137015daa8efcbb210184ee7ce723c`, the delivered five-file binary
manifest and the existing reviewed CU controller/worker isolation boundary.
It rejects source or binary drift and runs only in a new synthetic SSD root.
It does not copy a production database, import account credentials, contact a
paid provider, change live settings, or start an unrelated agent.

Retained receipts and reconciliation live under
`/mnt/vk-storage/vk-first-run-staging-acceptance-20261006/combined-acceptance.json`.
Read `VK_FIRST_RUN_ROLLOUT_PLAN_20261006.md` before interpreting results.
Historical unsuccessful fixture attempts are retained; do not count their whole
runs as passed. A successful fixture is not production rollout authorization.

The environment variable `VK_STAGING_ACCEPTANCE_PHASE` selects `candidate`,
`extended`, `fencing`, `policy`, `launcher`, or `sameworkspace`. The Python
driver provisions the reviewed boundary and starts the Node CU/HTTP driver.
Only fixture-owned bounded worker services are reachable. `delay-provider.py`
provides a deterministic pre-native interruption window; it does not replace
the real native engine or produce a checklist. Negative policy cases deliberately
create invalid synthetic progress files; those files are never success evidence.

The bundle frontend is a placeholder. This driver is HTTP/native acceptance,
not browser or final frontend acceptance. Do not run the Node driver against a
live endpoint or relax the host-manager, filesystem or launcher checks to make
a fixture pass. This dated driver is evidence, not an unreviewed general-purpose
replacement for the deployment controller or backup tools.
