# Reviewed storage client test snapshot

Fifteen unmodified Python executable/test files from Operations PR215 at
`81887d38d238ce3b0665092bf38a482284441062`, plus the published disabled
config.example.json required by its config regression, are bound by sixteen
commit/path/SHA256 entries in provenance.json. Refresh only from coordinated
published source; do not edit this snapshot independently.

Hosted CI verifies all hashes and runs the 103 published Python tests, reporting
optional skips separately. It then exercises the actual Bridge/Store/bounded HTTP
codec against the native Axum router, migrated SQLite, native queue/default
launch and real approval bridge. Each scenario supplies mixed `os_percent` and
`ssd_physical_free_proposal_v1` incidents. The driver asserts both policy names
in the queued batch and two open incidents after execution success and original
WAL/client-state reopen. Only its HTTPConnection is remapped to the ephemeral
fixture; runtime has no address override. Executor I/O, OS inventory and incident
observations remain synthetic. The b2497288/7a02102 result is predecessor evidence.

Selected physical SSD policy does not read or require allocation input; physical
recovery never releases allocations or proves future commitments fit. Normal
Disk remediation retains allocation/resource/approval protection. OS is unchanged.
The separate reserve-aware path remains explicitly disabled without valid input.
Physical tuning still needs approval. The example leaves activation, SSD tuning
and transport gates false. No binding, credential, access, service or timer is
installed. Direct gateway traffic is not application-authenticated; gateway is
not loopback-only. Existing-boundary review remains required before activation.
