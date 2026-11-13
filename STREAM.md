# Provenance integration and activation preparation

VK PR #297 merged into staging as `dbcbfbe4e641cc7e79ec3275397940319689e868`.
The reviewed head remains `70381108f36baf51bd8cc327690ee5dbee150c8e`; source bytes
are identical and reviewed CI was rechecked green before the merge.

This docs-only follow-up branch `docs/provenance-activation-20261113` records the
source integration and future acceptance boundaries. A detailed joint activation
plan for VK and already-merged CU PR #56 is retained privately for the operator.
It does not authorise deployment, service reload, agent work or usage experiments.
No runtime changes were made. The [existing guide](VK_RUN_PROVENANCE.md) retains
the exact nullable-version contract and normal-job verification requirements.

Preserve uncommitted work and use clean pinned source for future preparation.
Activation needs fresh owner coordination, packaged checks, compatible backups/
rehearsal and separate cutover approval under the established runbooks.

Prior stream history: [STREAM history](STREAM_HISTORY_20261017.md) and
[previous record](deployment-history/20261030-before-reconciliation/STREAM.md).
