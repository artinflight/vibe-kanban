# Reviewed storage client test snapshot

Fourteen unmodified executable/test files from Operations PR215 at
`7a02102d6ccf55f2c91223c5128599cefa6492fc` are bound by commit/path/SHA256
in provenance.json. Executable/test bytes equal `f6b800175d41a22528626f8a6ce708271f015f33`;
the later commit only clarifies transport documentation. Refresh from coordinated
published source; do not edit this snapshot independently.

Hosted CI verifies all hashes and runs the 87 published Python regressions, then
the actual Bridge/Store/bounded HTTP codec against the native Axum router,
migrated SQLite, native queue/default launch and approval bridge. The driver
remaps only HTTPConnection to the isolated ephemeral listener; the runtime has
no address override. Original client/native WAL state is closed and reopened.
Executor I/O, OS inventory and incident observations remain synthetic.

The prepared production Bridge requires both explicit gates; neither is enabled
by this snapshot. No binding, service, credential, access or timer is installed.
The fixed client destination does not narrow gateway exposure: direct requests
are not application-authenticated, the gateway is not loopback-only, and owner
binding is not caller identity. Existing-boundary review remains an activation
blocker. The passing native6c658d1/client5c2ee7f result is predecessor evidence.
