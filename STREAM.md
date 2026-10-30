# WakeWatch activation and TurnSteer access without restarts

Branch `fix/wakewatch-connector-20261030` starts from merged fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3`. PR #284 is already merged. The backend
binary, database, service identity and original deployment receipts are unchanged.

WakeWatch's explicit printer-connector transport is installed and enabled since
11:38:59 UTC after operator approval. Existing timer, owner, incident ledger,
notification policy and cleanup approvals remain. The process inventory now
recognizes tightly scoped unrelated infrastructure without ignoring unknown work.
The single approved acknowledgement test completed at 12:00:07 UTC after waiting
for ordinary capacity. Its exact assistant reply matched; no resend, extra turn or
forced capacity increase occurred.

TurnSteer already exists in the live backend and connector. After the operator's
refresh, this client's discovery now exposes all 46 tools, including both steering
tools, six issue-workflow tools and two handoff tools. A receipt lookup through
the refreshed plugin succeeded. The installed local CLI is an alternative for
authorized shells with loopback access; Dot's read-only, network-disabled host
tool cannot make its API calls.

185 watcher tests and 14 steering tests pass. Live steering target/receipt reads
and connector health pass; no new unrelated-agent correction was sent. Scheduled
first-run, targeted stop, automatic Git sync and issue workflows are already enabled.
Native watcher v2 remains separate; unqualified provider failover and recovery
cleanup/PR-monitor protections remain explicit limitations.

Read [WakeWatch recipe](scripts/watcher-events/CONNECTOR_TRANSPORT.md),
[TurnSteer access](TURNSTEER_ACCESS.md) and the deployment checklist.
Prior stream: [full historical archive](STREAM_HISTORY_20261017.md).
