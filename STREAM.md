# WakeWatch activation and TurnSteer access without restarts

Branch `fix/wakewatch-connector-20261030` starts from merged fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3`. PR #284 is already merged. The backend
binary, database, service identity and original deployment receipts are unchanged.

WakeWatch's explicit printer-connector transport is installed and enabled since
11:38:59 UTC after operator approval. Existing timer, owner, incident ledger,
notification policy and cleanup approvals remain. The process inventory now
recognizes tightly scoped unrelated infrastructure without ignoring unknown work.
One approved acknowledgement test is in Vibe's capacity queue; no resend, extra
turn or forced capacity increase. Exact reply verification remains pending.

TurnSteer already exists in the live backend and connector. Fresh discovery lists
46 tools while this pre-existing client catalog lists 36. The operator refreshed
it; new Dot catalog verification is still pending. The installed `turnsteer` CLI
provides immediate use through existing host access without a new service.

185 watcher tests and 14 steering tests pass. Live steering target/receipt reads
and connector health pass; no new unrelated-agent correction was sent. Scheduled
first-run, targeted stop, automatic Git sync and issue workflows are already enabled.
Native watcher v2 remains separate; unqualified provider failover and recovery
cleanup/PR-monitor protections remain explicit limitations.

Read [WakeWatch recipe](scripts/watcher-events/CONNECTOR_TRANSPORT.md),
[TurnSteer access](TURNSTEER_ACCESS.md) and the deployment checklist.
Prior stream: [full historical archive](STREAM_HISTORY_20261017.md).
