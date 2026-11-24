# Completing deduplication and normal Nightly operation

## Current scope and acceptance

The operator requested completion on November24 after the original selected
finite conversion passed. This expands work to newly closed logs, bounded future
conversion and actual Nightly commissioning. The old finite result is immutable;
its 84.65GiB processed and76.64GiB gross recovery are not final expanded net savings.
The new catch-up and automatic daily conversion are accepted. Nightly readiness
remains pending. Deferred workspace/archive cleanup remains excluded.

## Bounded catch-up and recovery

`scripts/log-dedup/incremental.py` owns the existing production lock and requires
canonical owned pinned code/config. Only eligible closed captures enter a frozen
selection. Each batch has one workspace, at most16 files and128MiB; the initial run
has374 files/110 batches, with512-file/1GiB/four-hour limits. Active/pending/unknown
captures remain untouched. Fingerprint-cached nonbeneficial originals are checked
again if their version changes. An idle pass opens no B recovery context.

`incremental_owner.py` reuses the accepted scoped converter, current writer/reader
identities and normal Desktop-B owner. Source and sidecar versions are rechecked,
then actual writer custody decides publication. Complete original/graph independent
B restore and full production-reader EOF checks precede commit. New temporary
carriers are retired only after their independent recovery proof, exact identity/
hash check and an exclusive kernel inode lease. All primary objects/epochs remain.

ACTIVE is written before batch processing. An exception retains ACTIVE, FAILURE
and LATEST; the next invocation refuses replay. Reconcile selected paths, installed
manifests, old/new hashes, per-batch journals, actual B receipts and live custody
before any recovery action. Preserve uncertain dispatches and original receipts.
A between-batch time limit produces an explicitly incomplete terminal selection.
Never label that full catch-up success. No automatic continuation has been installed.

Current private deployment: production-20261117/incremental-20261124 under the
vk-log-dedup-20261103-0815 SSD task. CONFIG pin:
`ac53ba6ec44d87fd7e5332fef8d8a25a443addc4fc09f29039336060b13e74d3`.
Accepted terminal run `e3787e2e49124284a1f023d061f967f7`:278converted/96preserved,
110batches/374resolved. Source and all receipts remain immutable.
The first launch failed before inventory/selection because Python `-S` hid dbus;
r2 uses the installed system packages and disables user-site packages. It did not
retry an uncertain conversion. Source/config passed independent normal-B restore.

## Monitoring and the remaining forward work

`incremental_watch.py` supplies a read-only sensor to the existing resource-guard
WakeWatch invocation. Same event codec, ledger, owner/chat, settings and capacity
admission; no new scheduler or dispatcher. It verifies exact unit birth, committed
batch/result digests and counters. Success requires complete committed selection;
missing progress, reused/dead process and retained failure stay visible. The
cumulative HUD retains original recovery and avoids duplicate historical exclusions.

The installed automatic-v3 retains finite success and observes later runs. `automatic.py` and
`automatic_watch.py` now provide one bounded daily conversion and successive-run
monitoring through the same WakeWatch hook. Nineteen focused tests pass, including
retained failure holds, missing recovery proofs, dead owners, double-counting
races and the ordinary no-work path. The package is pinned under automatic-v3.
The prepared timer runs at05:00 Toronto; late boot starts outside05:00–17:00 defer,
preserving the22:00–04:00 Nightly window. Routine healthy jobs create no model
continuation. Failures require exact review and cannot replay an uncertain run.

The package passed independent normal-B restoration and is installed. One actual
run converted and independently verified another closed log; final inventory had
no newly eligible paths. The timer is enabled, nextNovember25 10:00UTC. Same
WakeWatch ledger retains pending finite success; actual Rainmeter displays WAITING
and3731resolved with unchanged Lua/process. All current source/event errors are null.

## Nightly commissioning

The prior Nightly owner execution is terminal/idle. The prepared successor under
vk-nightly-efficiency-20261017/commissioning-20261103/completion-20261124 retains
125 roots and adds the actual paired frontend plus both serving binary inodes.
All source pins and roots validate. Its metadata-only checkpoint imports reference
396 original components,3,356 converted logs and1,134 immutable normal-B checkpoints.
The accepted new runs add60components/279logs/60checkpoints. Total prepared
references:456components/3635logs/1194checkpoints. No import or whole-backup
acceptance is claimed yet.

A complete metadata census found at least2,270,077 required inode watches.
The operator raised the live limit to3,145,728; this was independently verified.
No persistent administrator setting was found in the usual sysctl files.
Reboot persistence remains unverified.

The compact observer preserves every path/hardlink alias and exact watch type,
using a string for single-name inodes and sparse byte pages for type lookup.
Twenty-nine inode tests,23tracking tests and one outbox test pass. Full actual memory enrollment passed across all125roots and2,287,396watches,
with peak1,610,854,400bytes under the retained1536MiB soft/2GiB hard limit
and zero swap. Earlier bounded probes stopped safely and closed their own FDs;
they did not establish full admission. The existing observer is now fully ready:
2,289,027watches/zero errors. Existing journal-v40 independently delivered/reopened
B and acknowledged exact source generations. One bounded gap-v22 job is running.
No watch scope or resource floor was reduced.

Retain the predecessor gap/outbox/latch. Reconcile tracking, import existing
checkpoint metadata under the same B owner, qualify all current files and actual
SQLite API/runtime points, and restore the complete composed set independently.
Prove an ordinary incremental cycle plus interruption/Desktop-unavailable behavior
with the exact installed package before enabling the22:00–04:00 America/Toronto
calendar and verifying its next run. The schedule remains OFF today.

## Additional savings and restore location

Exactly24 temporary final-closure tar copies were retired after frozen-plan/hash/
metadata and independent B restore checks, with exclusive kernel leases ensuring
no open consumer. Gross allocated copies removed:440,885,248 bytes. Location notes
retain each immutable `nightly-controls-v1/<SHA>.sqlite` selector, original source
key, body digest and accepted restore receipt. `packed_graph` restores from those
B controls; it never requires the retired local tar. Primary archives, members,
catalogs, original backup epochs and failed remote inputs were preserved.

Keep the derived union index and recovery catalogs until an explicit verified
consumer/rebuild plan permits retirement; names alone are not disposal authority.
Final accounting must include the catch-up, preparation, receipts, surviving local
and remote staging and concurrent growth. Protected-process old-original descriptor
inspection still needs administrator evidence; include this new run's originals.
No zero-open-original or final strict filesystem-attribution claim is made.

## Validation status

Nineteen automatic and fifteen incremental tests pass, including uncertain-publication refusal,
active/pending exclusions, bounded batches, changed exclusions, missing recovery
proof, incomplete terminal selection, reused process identity and cumulative HUD.
Real catch-up batches pass independent normal-B restore and full actual-reader EOF.
Normal timer sensor/event errors are null with no added synthetic delivery. Both
serving binaries/invocations are unchanged. Public index/health and the exact
accepted download wrapper pass TLS verification with the existing homelab CA.
Earlier semantic-history and desktop/mobile viewport proof is retained; this turn
does not claim another full browser or physical-phone acceptance run.

Ops Playbook and `git diff --check` pass. Required `pnpm run format` ran: Rust
formatting passed; frontend formatting stopped because Prettier is not installed.
No frontend or Rust implementation changed in this completion step. The broad
workspace build/lint/test suite was not repeated for these Python/ops changes.

The expanded private administrator audit is prepared with all3,356 original
converted inodes and374 newly selected versions (3,730 records). It pins its
identity-list digest and only reads bounded process metadata. It has not been
published or executed; the prior publication hold remains. Accept its result only
after this catch-up is terminal and reconciled. Only the operator changed the runtime watch limit; no persistent setting is claimed.
