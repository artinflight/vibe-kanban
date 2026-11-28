# Compact durable preparation outcomes

PR266 is merged into staging `d0b0bb298`. This extends its existing runner and
fixture benchmark; it creates no new scheduler, cache, privilege route or agent.
Tracking remains [Vibe T51](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d/issues/c89125a3-5aeb-5335-a1a2-5bf20c9d69c3).

## Behavior

The existing runner always writes `run-<id>/outcome.json`, with a bounded
preparation-only state and, after completion/failure, a SHA256/byte/path binding
to that run's full `result.json`. Full outputs, fingerprints, logs and volatile
acceptance remain unchanged. The optional `run --compact` flag prints this
small receipt; default full JSON and Python callers retain their existing API.
The documented preparation command adopts the opt-in flag for future jobs.

- A new job records running/false before it can return success. Abrupt parent
  death cannot leave that job showing an earlier job's completed outcome.
- Cache ownership refusal returns blocked/false for the caller's exact new job;
  it neither overwrites the owner's latest alias nor clears its lease.
- Failures remain nonzero, identifying the stage or exact prerequisite plan slot
  without copying command arguments or raw exceptions into the small receipt.
  Inspect that job's retained report/log and plan; do not blindly relaunch it.
- A completed outcome is published only after the full result exists and the
  existing inherited-output drain, artifact hash and input checks have passed.
  Outcome-publication failure returns false/nonzero; retained completed evidence
  can be reconciled without rerunning the work.
- These are presentation receipts, not a security boundary or trusted approval
  system. Receivers must bind the expected job/source/full-result hash and keep
  existing acceptance. Mutable `latest-*` paths alone are not replay authority.
- Task completion remains not inferred, delivery remains not attested, QA remains
  separate, and cutover remains unauthorized by this receipt. No review/hold/read
  state is cleared and no model, effort, permission or AutoSwitch setting changes.

## Reporting investigation and supported boundary

The private fixed-window usage report was reconciled without provider refresh,
new models or any change to approval processing. Cached input is part of input;
review share is a workload attribution, not proof of unnecessary review. Token
observations are not billed spend and do not establish avoidable cost.

The installed reply reader duplicates a successful final in both latest-durable
and latest-successful fields when they refer to the same message. A read-only
synthetic probe returned two copies of a 49,000-byte final in a 102,107-byte JSON
response. Identity/reference-based compaction is an integration opportunity for
that connector's owner; this patch does not overwrite or reload its live source.
Different failed/successful replies must remain distinct.

A delivered external task can still have no assistant message in the backend's
available durable history. The current connector reported that precise gap;
execution completion and empty history alone cannot reconstruct delivery or a
missing final. This change improves jobs whose writer we control. It does **not**
repair external design tools, retroactively manufacture assistant history,
mark delivery, relaunch an agent or substitute stdout for a native final.
That capture/reader gap remains a separate owner/platform dependency.

## Bounded acceptance

Run the existing `benchmark_vk_usage.py` against mounted fixture storage. It uses
the same commands, output hashes, cold/repeat/changed-input cases and all fresh
checks as PR266. The new fields count actual full/compact JSON serialization
bytes for the same six completed jobs, with zero provider calls. Full reports
exist and are hash-bound while measured; only disposable fixture data is removed
by the fixture's existing lifecycle. Production evidence is never removed here.

The measured receipt is [USAGE_JOB_OUTCOME_MEASUREMENTS.json](USAGE_JOB_OUTCOME_MEASUREMENTS.json).
JSON byte reduction is not a measured token/credit or model-call reduction.
No additional validation reruns are removed beyond PR266's already measured
fingerprinted reuse; the improvement is result presentation and durable status.

The sealed six-job measurement returned **20,413 bytes** in full-report JSON
versus **4,959 bytes** in compact-outcome JSON: **15,454 fewer bytes (75.7067%)**.
The commands and evidence are identical; only result presentation differs.
All six jobs retain their corresponding full report while measured, all fresh
checks remain, and the fixture makes zero provider calls. Prior interim timing
serializations can differ by a few bytes; this exact table binds the checked-in
measurement receipt, not an estimated token or billing conversion.

Source/fixture acceptance covers full-report binding, opt-in CLI compatibility,
nonzero failures, prerequisite diagnosis without argument leakage, stale success
under cache contention, abrupt parent death, missing terminal evidence and
outcome-publication failure. Existing capture-drain and validation tests remain.
No production job, connector, schedule, service or backend was changed. Adoption
by an operational driver still requires that owner's exact-source integration;
external task delivery remains independently evidenced.

Package `vk_prepare.py`, `vk_prep_common.py` and `vk_job_outcome.py` together from
the exact reviewed source. The package fixture invokes its actual isolated
`run --help` and checks the flag; do not copy the runner alone. Validation uses
small source/loopback fixtures only. Formatting runs Rust formatting but the
repository command remains blocked by unavailable Prettier; no local compiler
or dependency installation is part of this task.
