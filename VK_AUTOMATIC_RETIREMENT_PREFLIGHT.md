# Two-profile protected-consumer preflight — source only

[Draft PR234](https://github.com/artinflight/vibe-kanban/pull/234) is stacked on
PR231 checkpoint `c57dceaac5b214fe94dfdce512827ab7b0520b75`. The earlier installation proposals are superseded by the
[two-profile installation plan](scripts/deployment/security/inspection-two-profile-install-plan.json). **Installation approval was
withdrawn. Nothing in this PR installs privileges or changes current Staging.**

The result is a stable, read-only privileged inspection ABI and an unprivileged
held-operation adapter. Within the bounded namespace proposed below, future
release IDs, targets, source hashes, owner PIDs and nonces do not require root
policy/code/sudo amendments. A restart with no retirement skips privileged
inspection entirely. Backup, exact target authorization, interruption approval,
rollback and fallback retention until human QA remain separate gates.

## Why ordering changed

The 15:35:17 root receipt
`443032f47a9abaed509d12beba4daa736e2f75aebf5e99d0a5fc60022709d894`
preceded expensive native/B hashes and preparatory SSH/SFTP creation. Protected
SSH/SFTP PIDs 1632206/1632291/1632292 started at 15:42:48, leaving a real inspection
coverage gap. Staging aborted before unlink; it did not delete or cut over.
Fresh timestamps alone would not correct that sequence.

The adapter now does, in order:

1. Finish SSH/SFTP creation, B verification, backup/QA/rollback/authorization gate
   callbacks and ordinary-permission artifact hashes. Freeze exact release,
   inode/metadata/hash results and the live owner binding.
2. Seal the managed operation's remote-command channels through its owning
   orchestration gate. Start the local status thread and the fixed checker child.
   These are the last new processes/threads belonging to this operation.
3. For an exact continuation, seal fork/clone/exec across the terminal actor's
   threads using unprivileged Linux x86_64 seccomp TSYNC. Only then submit the
   manifest and fresh nonce to the already-created checker, inside the held lease.
4. Root authenticates the owner, scans protected process consumers, verifies
   owner/lease/target metadata again and returns one bounded direct stdout reply.
5. Check local lease, target metadata, bounded in-memory live status, authenticated
   bindings, timestamps and late PID/TID births. Recheck both wall-clock and
   monotonic receipt age after the complete witness traversal, immediately
   before returning to the exact in-process
   continuation. **No gate callback, SSH/SFTP, B hash, orchestration callback or
   subprocess is run after clearance.** No saved-receipt input or refresh loop.

`verify_gates` is called once before inspection. `status.live_status` and
`lease.verify` are required to perform only bounded local/in-memory checks. The
continuation is an already-approved unprivileged operation, not a root callback.
The adapter contains no unlink, service operation or arbitrary root execution.
Its process seal is irreversible and suitable only for a dedicated terminal
operation actor, never for adoption into the current long-lived owner in place.
The owning controller must close remote command channels before sealing;
seccomp does not prevent writing commands to an existing SSH connection.

## Trust boundaries and approved scope

Root owns the stable launcher, checker ABI/code and fixed policy. The reusable profile is unchanged. Its proposed data scope is the new **empty**,
dedicated namespace:

```
/mnt/vk-storage/vk-process-inspection-managed-v1
  objects/<32 lowercase hex release ID>/<bounded artifact leaf>
  control/<same release ID>/owner.lease
  control/<same release ID>/owner.sock
```

The scope anchor is root-owned 0755 and enrolled by inode and SSD filesystem UUID
`26e4cac1-f2cf-485b-b1bc-d1be197a747e`. `objects`, `control` and release directories
are mcp-owned 0700. Targets must be ordinary UID1000 single-link files with
0400/0500/0600/0700 permissions; leases are empty, UID1000, 0600, single-link files;
sockets are UID1000, 0600. Every relative component stays on the anchor device.

The SSD mount parent is mcp-writable. Root therefore verifies the independently
root-owned anchor inode and UUID on every operation and reopens it after scanning.
Renaming or replacing its pathname fails closed; mcp cannot manufacture a
replacement root-owned inode. No chmod/chown of the existing SSD mount or roots
is proposed. Bind/mount/device changes require root authority and fail the
recorded identity checks. Root-controlled UUID device metadata accommodates
normal device-number changes across reboot.

Root scope authorization belongs to the operator/root administrator. It is
separate from the owning release controller's authorization of exact artifacts
inside that scope. The controller supplies strictly bounded JSON, not a pathname
to a manifest. Live Unix SO_PEERCRED PID/UID/start, the exact kernel FLOCK owner,
and an ephemeral nonce authenticate that manifest and its source/root/backup
bindings. Its SHA-256 is a content binding, **not a digital signature** or proof
of human QA. This proposal trusts the existing UID1000 managed-controller role;
processes sharing that UID are not cryptographically separate principals. Root
never attests release-code trust or authorizes a deletion from that assertion.
An independent signing authority would be a different, separately reviewed design.

A release manifest contains only ABI1, bounded scope/release IDs, source/root/
backup hashes, exact lease and target identities (device, inode, size, mtime,
ctime, links, UID, GID, mode), target hashes and exact held-guard declarations.
No absolute path, caller-selected policy, command, interpreter, arbitrary suffix,
manifest-file read or external key path is accepted. At most 32 targets and 64KiB
input/output are allowed. Static root policy permits at most four explicitly
root-enrolled scopes; this proposal enrolls exactly one.

The historical incident archive remains outside this namespace. The separately
proposed `historical-archive-v1` profile covers exactly that one existing path,
device 2065, inode 7340415, size 23441521918 and the full metadata/SHA bindings in
[its policy](scripts/deployment/security/historical-archive-policy.proposal.json).
Both the fixed root handler and root-owned policy must match those constants;
the request cannot select a different path. Root uses only O_PATH metadata on
this file. The prior approved SHA is a binding, not a claim that root rehashed it.
The unprivileged adapter hashes it before requesting root clearance.
No file is moved into the managed scope. This historical profile never grants
deletion, future unrelated targets or configurable path expansion. Installation
of this additional scope requires explicit approval of the new bundle.

## Privileged capability and consumer coverage

The launcher accepts zero arguments, clears its environment and executes only:

```
/usr/bin/python3 -I -S -B /usr/local/libexec/vk-process-inspection-v1.py
```

The checker has no repository imports or subprocess/exec/deletion operations.
Its installed code, policy, interpreter and their ancestors are required to be
root-owned and non-user-writable; administrator-owned OS standard-library code
is part of the installation baseline. Ordinary OS Python updates do not require
new release-specific sudo grants. Checker/ABI/launcher changes remain exceptional
security changes. There is no grant to a Python interpreter, shell or sudoedit.

Root takes **O_PATH metadata handles**, never artifact/lease byte reads, content
hashes or data-directory enumeration. Ordinary-permission release code verifies
content hashes before requesting inspection. Root reads only its static code/
policy and fixed `/proc` process metadata, FD metadata, maps, namespaces, mounts
and locks. It emits no command lines, environments, protected FD path strings,
map lines, memory bytes or secrets. Receipts expose counts and bounded
PID/TID/start witnesses, plus operation bindings and code/policy hashes.

Every process and thread is checked for inode matches via exe/cwd/root, FDs and
mapped-file device/inode. Denied/malformed inspection, incomplete visibility,
process/task reuse or churn, substitution, scan timeout and oversized output
fail closed. PF_KTHREAD and zombie state allow genuinely absent user exe/cwd/root;
no name/UID heuristic excuses an opaque SSH/SFTP process. The implementation is
conservative: inventory churn, including kernel-task churn, can still block a
pass. Installed host visibility/performance are not yet tested.

An exact owner target FD may be an intentional archive guard. Its manifest
`guard_held` declaration is accepted only with the exact owner PID's kernel
exclusive whole-file FLOCK, reverified before and after scanning. Only that
owner's FD reference is exempted. Other PIDs, the owner's maps/executable and
unverified locks still block. The root inspector closes its own O_PATH handles
before scanning. This guard is ownership bookkeeping, not a global reader lock.

## Supported boundary and residual race

This provides full attempted protected-process inspection at the held boundary,
rejects concurrent inventory churn and late uninspected births, and prevents the
managed terminal actor from creating new local processes afterward. A five-second
maximum receipt age is an additional bound, not the correctness argument.

**An already-existing unrelated process can open a file after its FD/maps have
been inspected, even with an unchanged PID inventory.** Advisory FLOCK, this
scanner and the process seal do not provide atomic global file-open exclusion.
The approved consumer-clearance and managed-owner gates are retained; no new
unattainable global-consumer fence is required or claimed. A same-PID unrelated
exec/open or existing remote channel remains a residual TOCTOU risk. Final local
checks and immediate continuation minimize the interval but cannot eliminate it.
If the operational policy demands stronger atomic exclusion, this capability
cannot meet that demand and must not be described as doing so.

## Exact one-time two-profile installation proposal — NOT authorized

The [version-pinned installation plan](scripts/deployment/security/inspection-two-profile-install-plan.json)
is the authoritative bundle. It records source and binary hashes, exact object
permissions, both policy scopes, the sole allowed enrollment change, installation
order, read-only installed acceptance and rollback. It is a plan, not an installer
executed here. The original namespace checker, policy template and launcher remain
byte-for-byte unchanged. The historical handler loads that audited scanner from
one fixed root-owned installed path; no caller-controlled code import exists.

The one administrator-owned grant file `/etc/sudoers.d/vk-process-inspection-v1`
would contain exactly these two digest-pinned, zero-argument commands:

```
mcp ALL=(root) NOPASSWD: NOSETENV: sha256:33b47e5f890040bb8821a6a458dd1c4062e34c97d3e644cccd233e728051e12a /usr/local/sbin/vk-process-inspect-v1 ""
mcp ALL=(root) NOPASSWD: NOSETENV: sha256:8ee7e17dfe7bbbbdbe186f48e89eab33e3f123a16a930847889c7bf062f4a6aa /usr/local/sbin/vk-historical-archive-inspect-v1 ""
```

The final `""` prohibits arguments. No interpreter, shell, sudoedit, deletion,
service, credential, wildcard or group-membership grant exists. NOEXEC is absent
because each environment-clearing launcher must exec its one fixed interpreter
and root-owned code with `-I -S -B`. Neither binary is setuid or capability-bearing.
Root-owned non-user-writable interpreter/stdlib inputs are an installation baseline.

Bootstrap creates `/usr/local/libexec` only if absent (root:root 0755), validates
existing root-owned ancestor directories, installs the two fixed code files
0644, two launchers 0755, two policies 0600 and the one grant 0440. It creates
only the fresh empty managed anchor (root:root 0755), with empty mcp:mcp 0700
`objects`/`control` children. No existing Staging directory is adopted or changed.
The administrator enrolls that freshly created anchor's actual inode in both
policy templates, with the pinned SSD UUID. Null inode templates fail closed.
These are the only policy transformations allowed by this plan; authenticated
installation evidence records both final policy hashes. Code and policy receipts
configure each unprivileged adapter once. Routine managed releases need no grant
amendment. A different historical target or security boundary requires approval.

The historical adapter reuses the terminal boundary sequence and the existing
controller's backup/fence/promote/fallback contracts. Its live authenticated
owner is the dedicated boundary actor that actually holds its private control
lease; it does not impersonate or alter the incumbent Staging owner. Existing
CandidateController status methods that verify/hash packages must run during
preparation. Post-clearance status is bounded local memory/identity only.
Operational adoption and installed read-only acceptance are separate, unperformed
steps; existing deletion and cutover paths were not modified.

## Practical administration boundary

Read-only discovery found no established agent-usable administrator installation
channel or retained root terminal. Existing root daemons and unreadable sudoers
files are not authorization. Parent's Desktop readiness task owns the one-time
secure administrator authentication; this task asks for no terminal commands.
No sudo denial was retried or alternative escalation used.

The account also has existing `lxd` group membership and access to LXD's admin
socket. That is a separate host-privilege boundary, not authority to bypass sudo
or bootstrap this installation. The socket was not contacted. These fixed
capabilities do not govern all activity of the mcp account or revoke its existing
privileges. Same-account secondary-agent review is advisory; it cannot enforce
root authorization against another same-UID worker. The current Vibe approval UI
is likewise not a signed root command authority. A future protected signer or
broader executor is not required or introduced here. See the
[LXD security documentation](https://canonical.com/lxd/docs/default/explanation/security/).

## Bounded rollback — administrator only, not performed

Both adapters default to `adoption_enabled=False`; an approved owning controller
must explicitly opt in with `adoption_enabled=True`. Disabled adoption rejects
before preparation, privilege invocation or continuation. Installation alone
therefore does not adopt this adapter or change the current owner.

For rollback, disable admission to this adapter in the owning controller by
setting that explicit local adoption switch false. Disarm/drain any pending
terminal continuation through the managed owner's existing control before
withdrawing the grant: changing the switch for future calls or removing sudoers
cannot retract an already-issued receipt or cancel an action already underway.
The switch is an admission check, not an in-flight cancellation API. A terminal
actor's seccomp seal is also irreversible; do not try to reuse it for orchestration.

Then an administrator removes **only** this exact privileged grant file, withdrawing
both inspection commands:

```
unlink -- /etc/sudoers.d/vk-process-inspection-v1
```

This is an administrator rollback instruction, not a new agent sudo grant,
executable rollback helper, or authorization to run it now. Validate the exact
root-owned regular grant entry and retain its source/hash in the installation
record before removal; validate the remaining sudo policy afterward. Do not
remove the directory, any unrelated include, launcher, checker, policy, managed
namespace, artifacts, receipts, backup evidence or fallback. No recursive cleanup
or data retirement is part of rollback. Fallback still survives until human QA.

A revoked-grant error blocks automatic continuation without retries or an
alternate privilege route. Source tests model withdrawal of only the exact grant
in a synthetic SSD fixture, retain its bytes and an unrelated grant, and prove
that refusal leaves artifacts/evidence/fallback intact. Disabled-adoption tests
prove no preparation/checker/action occurs. Actual privileged removal, effective
sudo matching and operational draining remain untested; none are performed here.

## Existing route and urgent operator bridge

Read-only investigation found the fixed-purpose root-owned memory-guard snapshot
helper unsuitable for inode consumer inspection. No safe retained privileged
consumer-reader route was established. An unreadable sudoers include is not
proof of an applicable grant. No sudo attempt/denial retry, service API, identity
change or alternate escalation was used.

The owner's proposed one-off operator-terminal stdout bridge is a separate
current-path investigation: a resident completes hashes/SSH and obtains the
receiving Unix FD before the operator runs the unchanged approved helper. It
makes no new installation/grant and is not adopted by this PR. Compatibility
conditions for Staging's review:

- Enable SO_PASSCRED before receiving, use recvmsg for every frame/fragment,
  bound bytes and framing, reject absent/mixed/truncated credentials and extra
  data. UID0 authenticates a root sender, not automatically the expected scanner;
  account for sudo PTY/proxy sender PID and connect evidence to the approved code.
- One initial `/proc` list does not cover protected births during the scan.
  Prove coverage at scan completion and reject uninspected late processes. Root
  credentials on a JSON message cannot repair missing inspection coverage.
- The unchanged historical helper has no approved archive-holder exemption.
  A resident's target FD/FLOCK can be reported as a consumer. Do not waive a
  failed clearance or silently substitute new root reader code.
- Keep the same resident/lease/target binding through immediate continuation;
  no later SSH, subprocess or B/native hash. Recheck local identity and time,
  reject extra messages/replay. There remains the unrelated existing-process
  open-after-inspection race described above.

Staging session `7d6734c1-c8d0-4d55-ac27-b1f763d15a6e` retains operational ownership.
User relays name executions `e7db8d73-a331-4fb0-b5c2-7230d44011ff` and
`d9f07b0f-b92d-4b17-a60a-f1cfdf0782bb`; read-only lookup records the latter as
completed, so no new prompt/execution was started. Findings return through the
existing reply. The current owner, Staging roots, model/effort and approvals
remain under that session's control.

The subsequently relayed prepare-first resident closes the archive FD and finishes
both SSH children before waiting for an authenticated digest and actual operator
message. Read-only source review found that its unchanged helper and later local
scan enumerate process leaders, not each task's private FD/maps state; its denied-
PID comparison does not establish coverage of thread births or protected PIDs
born during the local traversal. The last receipt-age check also precedes a
proof-file write/fsync that could block before unlink. These findings were sent
through the current reply; no Staging source/owner was changed. This is distinct
from the residual existing-process open race, not a request for global exclusion.

## Validation and what remains manual

Focused fixtures run as mcp, without sudo or executing the root entrypoint.
They cover real Unix peer/PID/kernel lease authentication, reusable source/release
bindings, strict parsing, scope and inode substitution, symlinks/hardlinks,
metadata-only target handles, protected consumer/denial/churn models, replay and
freshness, late SSH PIDs, backup/QA gates and native terminal process sealing.
A disposable native actor creates actual preparation/verification children,
creates its inspection child before sealing, then proves a post-response SSH
subprocess is denied; the privileged scan is explicitly substituted in that test.
Source regressions do not prove installed privileged visibility or live adoption.

After the proposed exact historical grant is approved, its read-only clearance
also needs no operator snapshot command. Its exceptional retirement approval
still comes from the existing controller; the root receipt grants no action.
Within the approved managed scope, ordinary future checks need no operator
command after one-time installation and tested controller adoption. No-retirement
restarts require no inspector. Humans still approve new scope/security changes,
exceptional target retirement/interruption decisions, backup or rollback
exceptions, and human QA. Failures block instead of requesting successive manual
snapshots. Direct-B incremental backup and reserved capacity could avoid routine
cleanup entirely; that separate project is neither implemented nor a dependency
added here.

[Source bundle/validation receipt](scripts/deployment/receipts/two-profile-inspection-source-validation-20261009.json)
records exact artifacts and remaining validation limits. Earlier receipts are
historical evidence for their respective source checkpoints, not this revision.
Protocol references: [sudo primary manual](https://www.sudo.ws/docs/man/1.9.14/sudoers.man.pdf),
[Linux kernel seccomp documentation](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html).
