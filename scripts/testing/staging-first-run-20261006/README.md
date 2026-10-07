# October 6 Combined First-Run Acceptance

October7 pin: the driver now uses combined5ec572245/CU95e7aea47 and that exact
hosted bundle. Candidate, extended, stalled and real-frontend groups passed on
this source; the earlier remaining groups are retained baseline evidence, not
claimed as rerun. See VK_RECOVERY_INCIDENT_20261007.md: subsequent host-side
verification caused an incident, and deployment/full handover remain blocked.
Never inspect these executables outside the reviewed isolation boundary.

This is the retained staging test driver, not a production deployment command.
Its original October6 pin was PR147 `9b3f8253879abdc5ebc88b3c3411946ce6f6a3b4`, CU PR38
`95e7aea47e137015daa8efcbb210184ee7ce723c`, the delivered five-file binary
manifest and the existing reviewed CU controller/worker isolation boundary.
It rejects source or binary drift and runs only in a new synthetic SSD root.
It does not copy a production database, import account credentials, contact a
paid provider, change live settings, or start an unrelated agent.

Final receipts and reconciliation live under
`/mnt/vk-storage/vk-first-run-final-20261006/acceptance.json`.
Read `VK_FIRST_RUN_FINAL_ACCEPTANCE_20261006.md` before interpreting results.
Historical unsuccessful fixture attempts are retained; do not count their whole
runs as passed. A successful fixture is not production rollout authorization.

The environment variable `VK_STAGING_ACCEPTANCE_PHASE` selects `candidate`,
`extended`, `fencing`, `policy`, `launcher`, `sameworkspace`, `stalled`,
`lock-only`, or `frontend`. The Python
driver provisions the reviewed boundary and starts the Node CU/HTTP driver.
Only fixture-owned bounded worker services are reachable. `delay-provider.py`
provides a deterministic pre-native interruption window; it does not replace
the real native engine or produce a checklist. Negative policy cases deliberately
create invalid synthetic progress files; those files are never success evidence.

The bundle's embedded frontend is a placeholder. The `frontend` phase pairs the
final backend with the previously built real external frontend; `package-final.py`
verifies source compatibility and every asset before packaging. It never activates
a service. `record-final.py` indexes the exact successful final-source fixtures.

`stall-provider.py` preserves all native command arguments and zero-retry settings,
but drops graceful pause/interrupt responses. `fault-manager.py` still forwards
every action through the unchanged private broker; it holds controller-side EOF
and can deny, never fabricate, exit confirmation. `hold-progress.py` makes only a
new private FIFO to hold a discovery read/controller lock for at most five seconds.
These faults are not production hooks or internal-mutex instrumentation. The
developer's packaged internal mutex/log/exit-signal tests complement the HTTP tests.
The outer observer records only fixture-owned cgroups and synthetic lease files.
All test roots and unsuccessful setup attempts remain; no cleanup is authorized.

Do not run the Node driver against a
live endpoint or relax the host-manager, filesystem or launcher checks to make
a fixture pass. This dated driver is evidence, not an unreviewed general-purpose
replacement for the deployment controller or backup tools.
