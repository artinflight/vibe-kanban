# Reviewed storage client test snapshot

The six native-driver dependencies, read-only status helper and five published
Python test modules are unmodified source from Operations PR215 at
`5c2ee7f5f561a943d123fcc09d5ee8098cbeab20`. Commit/path and all twelve SHA256
hashes are recorded in provenance.json. Refresh only from a coordinated,
published client commit; do not edit this snapshot independently.

Hosted CI checks exact provenance and runs the 76 published Python tests,
including failed-live-recheck debounce/audit preservation, then invokes the
real Store/NativeAdapter/HTTP driver against the actual Rust router, migrated
SQLite/native queue/default launch and approval bridge. Client state and the
original native WAL database are closed/reopened. Executor I/O, OS inventory
and incident observations are synthetic. Test-only loopback controls are never
product ingress. These files supply no production transport, binding, access
or activation. The previous a345ca8 pair is historical evidence only.
