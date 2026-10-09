# Automatic protected-consumer preflight (source only)

## Outcome and authority

This adds a fixed-policy root checker and an unprivileged adapter for PR231's
held preparation owner. It removes the recurring operator consumer-check command
**after separately approved installation and owner adoption**. Nothing is
installed, granted, retired, restarted, backed up or switched by this change.
The current urgent restart still needs its independent fresh root receipt.

The dependency is PR231 checkpoint
`c57dceaac5b214fe94dfdce512827ab7b0520b75`, not its mutable branch name. This is an
isolated dependent branch; current staging and the current owner remain intact.
PR229's eight reviewed source files, PR231's sealed packages and the approved
application/frontend artifacts are untouched. No protected data is included.

Seamus requested removing routine manual operator checking. That authorizes
source development and this exact proposal; it does not authorize live privileged
installation. Target retirement approval, human interruption approval, verified B
backup/exclusion checks, rollback and human QA stay separate. In particular the
fallback survives until successful human QA, regardless of consumer clearance.

## Existing privilege route investigation

Read-only discovery found `/usr/local/sbin/memory-guard-snapshot`, root-owned mode
0755. Its fixed purpose is memory logging; it cannot perform the required
inode-bound scan. It is unsuitable for reuse or modification here. The protected
sudoers include was unreadable to mcp; no effective privilege rule is inferred
from that absence of visibility. No retained root Python consumer checker was
visible in the process inventory. Historical operator sudo produced a receipt
at 13:35:05 UTC; a file receipt is neither a retained privileged process nor a
fresh authorization route. No sudo command, sudo denial retry, privileged service
API, SSH identity change or alternate escalation was attempted.

No safe already-authorized route was established. A parent/operator who has an
existing authenticated privileged terminal may run the already-approved pinned
read-only command when its held boundary is ready; this branch does not commandeer
that terminal, reuse its credentials or claim the old receipt remains fresh.

## Fixed root authority

The only proposed allowed invocation is:

```
/usr/bin/python3.12 -I -B /usr/local/libexec/vk-retirement-check.py
```

`mcp` invokes it through fixed `/usr/bin/sudo -n --` argv. Sudo matches the
interpreter digest, exact flags and exact script path, with NOSETENV and NOEXEC.
There are no argument wildcards, environment-based policy selectors, shell,
repository imports, subprocesses, arbitrary path reads, service operations,
unlink, directory traversal for deletion, chmod or root receipt-file writes.
Python isolated mode excludes user Python paths; bytecode writes are disabled.
The interpreter, checker, policy and their ancestors must be root-owned and
non-user-writable; the root checker enforces this at entry. OS standard-library
code is an administrator-owned dependency, not an imported worktree input.
Sudo's normal auditing remains in effect; no credential or process-content
logging is added. Exact matching/digests follow [sudo's primary manual](https://www.sudo.ws/docs/man/1.9.14/sudoers.man.pdf).

The checker hardcodes only `incident-archive-db5bb16b`, the full native path,
SHA-256 `e994567edaacc75d8aa9a3497b8384a8dbacec462854a3f7f8c5760e1a9a0ce4`,
and every device/inode/size/mtime/ctime/link/UID/GID/mode field from the approved
one-file exception. It also hardcodes the current retained lease/status paths.
The root policy must match those constants. A changed target requires an
exceptional reviewed code/policy change; mcp cannot enroll another target.
This grant has no cleanup or general restart authority.

`retirement-policy.proposal.json` is the exact proposed baseline policy. It pins
the candidate manifest, source and root binding, lease identity, host proc device
and PID/mount namespaces. These were read from the October9 retained owner
097e1bfa and lease without writing them. They are configuration pins, **not a new
liveness receipt**. Revalidate these pins at installation/adoption; if any differs,
stop and present a changed bundle. Do not refresh a root policy from user input.

The only stdin fields are target ID, fresh 256-bit nonce, integer owner PID,
start time and candidate manifest hash. Extra keys, paths, commands, duplicate
JSON keys and oversized requests reject. Root authenticates a live Unix peer
PID/UID/start, source/root/manifest and the owner's exact kernel FLOCK holder.
A busy lease held by another PID is insufficient. The status server must assert
the matching ephemeral retirement-boundary nonce; plain preparation status
cannot obtain clearance. PID reuse, lease substitution, released ownership,
missing status and mismatched source/root/manifest reject.

Every target/lease path component is opened with anchored O_NOFOLLOW descriptors.
Endpoint connection is anchored through its already-open private parent and
then authenticated with SO_PEERCRED. Symlinks, parent substitution, changed
inodes/metadata, additional hardlinks and changed content reject. Target hashing
uses the opened pinned regular file; path identity is rechecked. Root reads only
that approved file, its fixed policy/code, fixed lease, bounded status, mount
inventory and prescribed proc metadata. It never reads environ, cmdline, process
memory, descriptor contents, credentials or backup payloads other than the
single already-approved archive being hash-checked.

## Boundary integration

`vk_retirement_preflight.at_held_boundary` is a source adapter; the existing
097e1bfa production preparation driver has **not** been modified to use it.
Adoption belongs to the parent preparation owner, after reviewed source/package
binding and approval. It does not require a VK backend build or service restart.
A source driver integration looks like:

```python
status = BoundaryStatus(live_status)
server = PreparationStatus(existing_fixed_endpoint, lease, status)
# At the owner's actual already-authorized retirement boundary:
at_held_boundary(
    lease=lease, server=server, status=status,
    expected_target=approved_target, expected_lease=approved_lease_identity,
    installation=approved_installed_hashes,
    prepare=finish_all_preparation,
    verify_gates=refresh_approval_backup_exclusion_fallback_rollback,
    consume=existing_unprivileged_boundary_continuation,
)
```

Only the owning process uses this adapter; do not run a second concurrent status
accept loop while it temporarily serves root probes. It finishes expensive
preparation first, checks all five gates, verifies its still-held lease, installs
a fresh in-memory nonce and serves the existing status endpoint while the fixed
checker runs. The helper hashes before scanning, closes its own target FD, scans,
then rechecks visibility, live owner/lease and target identity. Thus the receipt
is minted **after** hashing/preparation, at the held boundary. Parent preparation
approval never becomes an interruption or retirement permission.

The adapter accepts only the direct successful child output. It verifies installed
code/policy hashes, nonce/PID/start/source/manifest/root/lease/target, complete
visibility, and both wall-clock and monotonic freshness. The receipt is limited
to five seconds after issuance and scan-to-issuance to35 seconds. Fresh gates,
status and lease are checked before the final freshness check and immediate
unprivileged continuation. The nonce is removed even on failure. There is no
stored-receipt input, retry, timestamp refresh or old manual-receipt fallback.
A timeout (600 seconds including hashing), denial, changed gate or any scan error
blocks continuation. Missing installation is a hard stop, not manual polling.

A receipt asserts inspected absence at the scan, not perpetual absence of future
consumers or permission to delete. The parent must retain the existing exclusion/
reader-writer fence and recheck the pinned path at its actual operation. Linux
proc inspection cannot atomically prevent an unrelated future open. This branch
adds no deletion or blanket reader-freezing power to close that race.

## Visibility and safe receipts

The checker requires the pinned host proc mount/device and host PID/mount
namespaces matching PID1, and rejects hidden/subset proc mounts. It enumerates
all processes and each process's tasks, inspecting exe/cwd/root, every FD's
identity and maps' device/inode fields. Thread coverage follows [Linux's primary
proc task documentation](https://www.man7.org/linux/man-pages/man5/proc_pid_task.5.html).
It checks stable PID/start/thread inventories before/after, rejects births,
vanishing tasks, PID reuse, unreadable live metadata and scan deadlines. Kernel
threads are identified by PF_KTHREAD; only kernel/zombie missing exe/cwd/root
is acceptable. FD closure is tolerated only with stable task/inventory checks.
Any other permission/I/O/parsing problem fails closed. A churn-heavy host may
need a later exceptional decision; automatic retry is deliberately absent.

Successful stdout contains pins, nonce, owner/lease/manifest, code/policy hashes,
fresh timestamps and counts. It contains no process names, arguments, map text,
FD destinations or secrets. Failure stdout is only a generic blocked result;
exception details never expose a protected read. The checker creates no output
file. A retained copy of successful output may be historical evidence but cannot
be supplied to this adapter to authorize another boundary.

## Exact one-time approval bundle (not executed)

Approve all four changes together, after reviewing this PR's exact source:

1. Create `/usr/local/libexec` if absent, and `/etc/vibe-kanban`, root:root0755;
   verify all ancestors are real root-owned directories without group/other write
   or user-write ACLs. Preserve unrelated entries. Install only the checker at
   `/usr/local/libexec/vk-retirement-check.py`, root:root0644. This is data for the
   fixed interpreter, not an executable wrapper.
2. Install `retirement-policy.proposal.json` as
   `/etc/vibe-kanban/retirement-policy.json`, root:root0644. No user-writable request
   folder, runtime daemon, shared root socket or generalized allowlist is added.
3. Validate the exact proposed sudoers file with `/usr/sbin/visudo -cf` in a
   root-owned staging location. Install only that rule at
   `/etc/sudoers.d/vk-retirement-preflight`, root:root0440; validate the complete
   sudoers tree. No blanket NOPASSWD, interpreter argument wildcard, sudoedit,
   service management, shell, install command or policy edit is granted to mcp.
4. Adopt the reviewed unprivileged adapter in the owning preparation package,
   binding its source/hash and fixed policy to the owner. Keep preparation
   non-activating and its existing retained evidence/lease intact. The current
   driver lacks the required nonce status and will correctly reject. Parent must
   arrange owner adoption without relaxing source, package or lease recovery
   checks. A changed owner source/path/policy needs a reviewed amended bundle.

Artifact SHA-256 pins:

| Artifact | SHA-256 |
| --- | --- |
| Checker | `c022cc6017d0d88101a4ad4431ab2056db10124060691fcad8246ad0345e95ed` |
| Baseline policy | `bfd27d6ecb4507805490e333c3ea55b4a3c4061268f240f48ff83d4d28dba268` |
| `/usr/bin/python3.12` | `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f` |

Copy into root-owned locations, then verify the destination hashes **before**
enabling the grant or running any copied code. Checking only user-writable source
before copying is insufficient. Verify the actual interpreter/root library
ownership and exact sudo rule during the approved installation. An interpreter
update that changes its digest fails closed until an exceptional grant update.
No local payload, new SSD backup, group membership, capabilities, proc mount,
Yama/LSM setting, polkit policy, service config or system-wide sudo default changes
are part of this bundle.

## Minimal staged rollout and validation

Stage1 is this source-only PR: fixture tests plus PR231 owner/generation/package
regressions. Stage2, only after the bundled action approval, is root installation
and **read-only** installed-command acceptance at a held non-activating boundary.
Check effective command matching rejects alternate flags/path/target/arguments,
and that actual protected host processes can be inspected. Demonstrate wrong
nonce, absent boundary and stale receipt rejection without retiring anything.
Stage3 lets the already-authorized owning retirement continuation consume one
fresh receipt. Its separate approval, verified B copy, exclusion checks and
rollback/fallback policy remain authoritative. Cutover and human QA are unchanged.
A repeated normal boundary requires no operator command; new targets, failed
visibility, changed pins, or exceptional operational approvals still involve a
human. Grant rollback is removal of the one exact rule by the administrator,
with existing fallback and data retained; this branch does not execute rollback.

Local validation:23 focused regressions passed, including genuine same-process
Unix peer/PID and held kernel lease; pinned hashing/scan ordering and FD closure;
open FD/hardlink/map/thread consumers; protected/malformed/missing metadata;
proc visibility/namespace mismatch; churn and deadline; symlink/path/identity/
hash substitution; duplicate/oversized/extra-field requests; wrong socket peer,
PID/start/manifest/source/root/lease; nonce replay/absent boundary; timestamp and
code/policy substitution; gate/fallback preservation and preparation-before-scan.
No root checker or sudo command was executed, so actual root host visibility,
installed sudoers matching, privileged stdout provenance and owner adoption
remain Stage2 evidence. No fixture result is live clearance.

Ops governance passed. `pnpm run format` ran Rust formatting successfully, then
blocked on missing Prettier. `pnpm run check` passed the legacy-path guard then
blocked on missing TypeScript; `pnpm run lint` blocked on missing ESLint. This
checkout has no node_modules. Full Cargo workspace tests were not run because
this source-only task prohibits unrelated rebuilds. The dependency regressions
initially had139 pass/3 packaging failures due to the expected clean-source
requirement; repeat from committed clean source before publishing this draft.
