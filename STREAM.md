# WakeWatch connector transport without a backend restart

Branch `fix/wakewatch-connector-20261030`, based on merged fork/staging
`7b64a69bc34d418b31c1f902c7714122a20783a3`. Deployment reconciliation PR #284 is
merged; the deployed backend and original release receipts remain unchanged.

The operator requires automatic Disk Space wakes without any further restart.
Native storage admission lacks its owner-file startup path. The printer watcher
already invokes the ordinary Vibe connector successfully, so this branch adds an
explicit disk transport using that same installed entrypoint. Existing timer,
incident ledger, owner, saved configuration and cleanup approvals are preserved.

All 183 repository watcher tests pass, including installed-connector compatibility.
Required formatting and Ops Playbook checks pass.
Production activation and one idle-only acknowledgement test were blocked by
automatic approval review pending explicit approval. No activation is claimed.
See [the recipe and limitations](scripts/watcher-events/CONNECTOR_TRANSPORT.md).
No Rust/UI/backend build, service restart, printer change or synthetic pressure.

Prior stream: [full historical archive](STREAM_HISTORY_20261017.md) and
[deployment reconciliation](deployment-history/20261030-before-reconciliation/STREAM.md).
