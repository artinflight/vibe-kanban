# October 29 incident implementation

These inert `.txt` files preserve the implementation used for the successful
recovery, stale-child correction, message-regression cutback, current-data
roundtrip, corrected build, fenced native backup and final promotion.
They are historical evidence, **not runnable fresh deployment commands**.
Every original operation is consumed. Old process IDs, snapshots, leases and
manifests are never new authority.

`sources.json` records exact original and published-template hashes. Private
workspace/session identifiers are represented by `INCIDENT_UUID_*` tokens.
The local private binding map can reconstruct the exact originals for review;
no prompt, transcript, database, credentials or backup payload is published.
The original private sources and recovery receipts remain retained on SSD/B.

Use the reusable sibling deployment modules and `BACKEND_DEPLOYMENT_HANDOFF.md`
for a new operation. Prepare a fresh authenticated manifest, prove current
writer/capacity ownership and current-data cutback, and use independent
no-progress supervision. Never copy an old PID or run one of these historical
controllers against production.
