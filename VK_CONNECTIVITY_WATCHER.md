# Intermittent startup connectivity watcher — October 16, 2026

[Matching local VK issue](https://vibe.local/projects/e2645d00-9bc6-4136-8d6e-0c2fcf032d77/issues/5668964d-eea4-4b09-a3bc-070dd69a9e2c)
is linked to workspace `281e1381-05fa-479c-944b-8d67d489a762`.
The fork has GitHub Issues disabled; no upstream GitHub issue was opened.

## Findings in plain English

Several agent processes had trouble reaching shared services at roughly the
same times. This makes a shared network, DNS, or provider-routing problem more
likely than a problem confined to one task. It does not establish the root cause.

On October 16 UTC:

| Window | Verified evidence |
| --- | --- |
| 14:23–14:24 | Model refresh request timeouts at 14:23:26 and 14:23:54 in separate native processes; VK routing-discovery startup failure at 14:24:04.981; a third native process reported address-lookup failures at 14:24:25, :30, :36 and :43. A fourth process logged a model-refresh child-process exit timeout at 14:24:42. |
| 14:46–14:47 | VK routing-discovery startup failure at 14:46:25.667; native model refresh request timeouts at 14:46:15, 14:47:19 and 14:47:23 in three processes; a fourth logged a child-process exit timeout at 14:47:18. |

The child-process timeout is recorded separately: it is not proof of a network
timeout. The operator also reported a GitHub DNS failure; its exact original
timestamp and endpoint have not been independently verified here. Native lookup
failures in the first window are independently verified, without a captured hostname.

The system resolver is the local `127.0.0.53` stub. Tailscale advertises catch-all
DNS routing (`~.`) via `100.100.100.100`; Ethernet lists `10.0.0.97` and `1.1.1.1`.
That makes resolver routing worth investigating, but is not evidence that
Tailscale caused the failures. DNS and public HTTPS connectivity were healthy
at the 15:03 baseline and in corrected live watcher cycles beginning 15:10 UTC.

## Installed watcher

- User service: `vk-connectivity-watch.service`, enabled independently of this task.
- Fixed expiry: **2026-10-19 15:07:44 UTC**. Restarting the service does not extend it.
- Persistent install/evidence: `/mnt/vk-storage/vk-connectivity-watch-20261016/`.
- Installed source: `bin/connectivity_watch.py`; install hash/expiry in `installation.json`.
- Logs: `logs/events.jsonl`, rotated at 5 MB with eight retained generations
  (at most about 45 MB). Directory permissions are 0700; log/cursor files 0600.
- Current heartbeat: `logs/latest.json`; restart cursors: `logs/cursor.json`.
- Source in this branch: `scripts/diagnostics/connectivity_watch.py` and
  `scripts/diagnostics/vk-connectivity-watch.service.in`.

Every 30 seconds the watcher compares A-record DNS answers/timing for
`chatgpt.com`, `api.openai.com`, `github.com` and `api.github.com` through the
stub, Tailscale, LAN and public resolver. It also queries AAAA via the stub.
It makes public HTTPS HEAD requests using the default address selection and
IPv4, recording DNS, TCP connect, TLS, first-byte and total cumulative times,
remote IP, HTTP status and curl exit code. It sends no credentials and saves
no response bodies. HTTP 403/421 or other error statuses still demonstrate
working transport; they do not establish authenticated service health.

On a failed HTTPS probe, a recently resolved stub IPv4 address can be tested
with curl `--resolve` while preserving TLS certificate verification/SNI. The
address is cached for no more than 15 minutes. This is additional evidence,
not a change to the system resolver. These probes bypass environment proxies;
they measure the host's direct route, which may differ from an agent's proxy
or authenticated workspace-discovery path. Timings include process scheduling
and the watcher's CPU limit and should be compared across samples.

The watcher reads native WARN/ERROR diagnostics from `logs_2.sqlite`, with a
restricted target allowlist, and records fixed error categories with process/
thread IDs. It never copies diagnostic bodies, debug prompts, tool payloads or
transcripts. It reads VK failed-execution metadata, including workspace/session
IDs, and matching backend journal errors. It discovers running VK service names
over systemd each cycle and queries exact journal units, following releases
without expanding historical journal unit globs. Native and journal events retain
their original timestamps separately from collection time. A two-minute
multi-process failure window gets an explicit correlation record. All SQLite
connections are read-only and bounded; cursors survive service restarts.

Resolver configuration/statistics, default routes, available memory and host
load are recorded every five minutes and on probe failure. The watcher does not
change DNS, inspect credentials, retry authenticated operations or restart VK.
The live backend remains `vibe-kanban-native-review-20261015.service`, PID
`3927146`, on `127.0.0.1:5621`; historical port 4511 is not the current backend.

## Read and stop it

```bash
systemctl --user status vk-connectivity-watch.service --no-pager
cat /mnt/vk-storage/vk-connectivity-watch-20261016/logs/latest.json
tail -n 40 /mnt/vk-storage/vk-connectivity-watch-20261016/logs/events.jsonl
journalctl --user -u vk-connectivity-watch.service -n 10 --no-pager
```

Stop and disable the watcher without touching VK or deleting evidence:

```bash
systemctl --user disable --now vk-connectivity-watch.service
```

`failures` counts DNS/HTTPS transport failures. `probe_errors` counts DNS probe
process crashes/missing binaries; `source_errors` counts unavailable log sources.
A zero heartbeat does not prove the authenticated startup path is healthy.
On recurrence, compare original event times, process/workspace IDs and probes:

- Stub/Tailscale queries fail while LAN/public queries work: investigate resolver routing.
- Normal HTTPS fails but pinned-IP HTTPS works: investigate name lookup, accounting for CDN address changes.
- DNS works but TCP/TLS fails for several providers: investigate shared egress/network conditions.
- Public probes work while only native discovery/model refresh fails: investigate the authenticated provider route or native client, preserving timing uncertainty.

If a future release changes the Codex home, native log schema, VK DB or DNS
servers, review the service arguments and source-health records. Do not restart
the application as part of adjusting this diagnostic service.

## Validation and limits

Ten offline tests pass: error distinction, DNS statuses, aborted probes,
unauthenticated HTTP error responses, command timeouts, prompt/body exclusion,
restart cursors, smaller replacement databases, journal byte-array messages,
deduplication/recovery, service replacement without historical unit globs,
rotation and fixed-expiry behavior (some cases share tests).
Run `python3 -B scripts/diagnostics/test_connectivity_watch.py`.
`systemd-analyze --user verify`, `pnpm run ops:check` and `git diff --check` pass.
Live collection captured the actual native incident history, failed executions
and both journal startup failures; corrected cycles have all 28 DNS/HTTPS
results and no source/probe errors. Installed source hashes are verified.

Initial commissioning records before 15:10 UTC include collector failures:
too little task headroom aborted some dig processes, the journal timeout was
too short, and journal byte-array MESSAGE fields needed decoding. These are
watcher setup defects, not new evidence of host network failures. They remain
in the log for transparency; use the corrected watcher generation from 15:10.
The corrected unit allows 96 tasks and disables core dumps.

Pre-PR live inspection at 15:46 found repeated journal source timeouts despite
healthy DNS/HTTPS and native/DB collection. The journal wildcard expanded against
historical service names and exceeded the 15-second bound. Exact-unit queries
completed in under one second outside the service. The updated collector now
discovers running units via systemd, then uses exact journal filters. Only the
watcher was restarted, retaining the expiry and cursors so unread journal events
can be recovered. Earlier clean samples remain valid, but heartbeat source errors
identify the subsequent journal collection gap. Installed-source and fresh-cycle
validation are recorded in the private `publication-validation.json` receipt.

`pnpm run format` was attempted: Rust formatting completed, then frontend
formatting stopped because this checkout has no installed `prettier` binary.
Pre-PR `pnpm run check` and `pnpm run lint` were attempted and stopped on missing
`tsc`/`eslint`. `cargo test --workspace`, using the shared SSD target with
incremental builds disabled, stopped on missing `glib-2.0.pc`. No frontend/Rust
application code changed; hosted CI must supply the full application baseline.
No DNS outage, authenticated startup or provider failure was deliberately induced.
The next natural failure is needed to determine its cause. No fix is claimed.
