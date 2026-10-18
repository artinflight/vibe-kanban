# Reviewed storage client test snapshot

These six files are unmodified test-only source from Operations PR215 at
`42bc9ceb10c978094992cee1d6284f5ea43b9bd9`. The commit/path and exact SHA256
bytes are recorded in provenance.json. Refresh only from a coordinated,
published client commit; do not edit the snapshot independently.

The hosted native test invokes the real Python Store/NativeAdapter/HTTP driver
against the actual Rust router, migrated SQLite/native queue/default launch
and approval bridge. It closes/reopens both client state and the native WAL
database. Only executor I/O, OS inventory and incident observations are synthetic.
The driver controls disposable test state through a cfg(test)-only loopback
fixture; product ingress has no setup routes. These files provide no production
transport, binding, access or activation. Native rejection, uncertainty, fences,
capacity and restart cases also have independent Rust coverage.
