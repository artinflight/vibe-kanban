# Standalone restart progress monitor

A Python standard-library server and browser UI for monitoring a restart controller
independently of the application it restarts. This is a source-preservation
snapshot, not an installation or deployment. Site-specific units, addresses,
private adapters, controller receipts and operational evidence are not included.

## Controller reporting

Import `Reporter` from `progress.py` into the independent controller package:

```python
from progress import Reporter

report = Reporter("/path/to/private/run.json", "unique-attempt-id")
report.start("Application restart", [
    {"id": "backup", "label": "Back up current state"},
    {"id": "verify", "label": "Verify application health"},
])
report.update("backup", "running", "Copying current state",
              metric={"done": 200, "total": 1000, "unit": "bytes"})
report.update("backup", "completed", "Backup checksum verified")
report.update("verify", "running", "Checking application health")
report.update("verify", "completed", "Acceptance checks passed")
```

Use a new file and ID for every attempt. Writes use a lock, atomic rename and
fsync. Failed/completed attempts are immutable. Public-safe messages and labels
are required: the progress file is the producer's publication boundary.

Create a private monitor configuration outside the repository:

```json
{
  "source": "file",
  "run_id": "unique-attempt-id",
  "progress_file": "/path/to/private/run.json"
}
```

Run from this directory using a private observation cache:

```sh
python3 -B server.py --config /path/to/private/config.json --cache /path/to/private/cache.json
```

The default listener is loopback, port 8189. A separately configured private
reverse proxy can expose the site to its intended audience. No application
service or database is started, restarted or changed by the monitor.
`legacy.py` supports explicitly selected receipt directories as an alternative
producer; it must never infer authority from an unrelated historical directory.

## Progress and forecasts

Counters and controller completion receipts determine progress. A timer never
fills a progress bar. Uncertain waits use clearly labeled conditional ranges,
assumptions, qualitative confidence, evidence timestamps and fixed recalibration
checkpoints. Overdue checkpoints remain overdue until new evidence arrives.
Planning allowances are assumptions, not statistical intervals or measured facts.
Blocked or stale observations lower confidence; disconnected views retain their
last forecast. Only controller completion establishes success.

A producer can attach a `planning_estimate` to a step with `lower_seconds`,
`upper_seconds`, `assumption`, and optional `recalibrate_on`. Use
`measured_duration_seconds` only for a matching measured rehearsal. The legacy
adapter's planning allowances are examples and need review for each controller.

## Restart Monitor control

The header control clears a finished attempt from this browser's view and waits
at zero for a new attempt ID. Its local-storage marker survives polling and page
reloads. A new attempt resumes real progress. Active and blocked attempts cannot
be dismissed. Resetting the view does not change the controller, its receipts,
the server cache or the application. Successful resets need no warning banner;
real source, stale-data and connection warnings remain visible.

## Validation

```sh
python3 -B -m unittest discover -s . -p 'test_*.py' -v
node --check web/app.js
```

Browser regressions use an existing Playwright installation and browser:

```sh
RESTART_TEST_BROWSER=/path/to/installed/browser node test_web.cjs /path/to/playwright http://127.0.0.1:8189
```

Use an isolated browser context and synthetic observations. The harness also
checks the current completed read-only snapshot when available. It covers desktop
and mobile layouts, uncertainty/stale/error/reconnect behavior, reset persistence,
new-attempt progress, and preservation of the controller's actual result. It does
not install a browser or start a new application backend. Temporary browser data
and optional `RESTART_TEST_ARTIFACTS` should use approved private scratch storage.
