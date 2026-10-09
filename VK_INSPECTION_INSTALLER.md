# Pinned administrator bootstrap — prepared, never run as root

This package implements exactly the two-profile installation scope reviewed at
`29af1c33e029bc1fe9ef9467fd51a03eb586105d`. The JSON plan, inspector code/policies,
launcher digests and two grants remain unchanged. Owner approval is pending.
This document is an invocation record, not authorization to run it now.

Package: `/mnt/vk-storage/vk-retirement-preflight-tests/install-two-profile-29af1c33-r1.py` (124669 bytes).
SHA-256: `6d7db4427a7fed2e056ca28ca71057b99a7cc6cb719c74b99a25b7b778c6a6e3`.

The unprivileged builder embeds verified local Git source from the reviewed head
and both prebuilt digest-matching launchers. Root performs no download,
compilation or repository import. The bootstrap below reads one bounded regular
file without following a leaf symlink and executes only the SHA-verified bytes
held in memory; replacing the package after hashing cannot replace executed code.
The exact generated script also needs review as the bootstrap implementation.

## One administrator invocation after explicit approval

Run from an authenticated administrator context on MCP, **only after approval**:

```sh
/usr/bin/python3 -I -S -B -c 'import os,stat,hashlib; fd=os.open("/mnt/vk-storage/vk-retirement-preflight-tests/install-two-profile-29af1c33-r1.py",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); info=os.fstat(fd); assert stat.S_ISREG(info.st_mode) and info.st_size==124669; data=os.read(fd,2097153); os.close(fd); assert len(data)==124669 and hashlib.sha256(data).hexdigest()=="6d7db4427a7fed2e056ca28ca71057b99a7cc6cb719c74b99a25b7b778c6a6e3"; exec(compile(data,"reviewed-inspection-installer","exec"),{"__name__":"__main__"})' --install --approved-plan 29af1c33e029bc1fe9ef9467fd51a03eb586105d
```

Administrator authentication is still unresolved. Both supported Desktop runner
attempts failed; there is no verified Desktop UI/terminal or runner route. This
package supplies the invocation, not authentication. No credential is embedded
or collected, and no sudo attempt, LXD bootstrap or privilege bypass occurred.

`--install` performs the full dry-run preflight before writing; a separate manual
preflight command is optional. To perform only preflight, use the same hash-checked
bootstrap with `--dry-run` instead of the installation arguments. It performs no
writes; complete OS/root visibility and sudo policy checks require administrator
access and were not executed here. No configurable destination/test root exists
in the command-line interface.

The installer refuses existing targets, symlinks, mutable privileged ancestors,
source/binary/plan mismatches, wrong historical metadata and incorrect SSD UUID.
It does not change the writable SSD parent. It creates only the approved fresh
root-owned anchor, enrolls that inode in both policy templates and emits exact
final policy hashes. Fixed installed code is root-owned and non-user-writable.

Before publishing the grant, it checks the include, current full sudo policy and
full prospective policy using a root-owned ignored dotfile wrapper including
`/etc/sudoers` plus the staged include. Dotfiles are validation evidence, not
active grants. Publication uses atomic no-replace linking in the protected sudo
include directory, then removes the inactive stage name. A final full policy and
installed metadata/hash check runs before successful completion.

Root-owned progress, validated, success/failure records remain in the new anchor;
safe success evidence is also printed as JSON. The wrapper/dotfile evidence and
all installed files, policies, artifacts and directories survive failures.
Catchable failures (including TERM/HUP) withdraw only the newly created grant,
verified by its inode and digest. A concurrent administrator's changed/replaced
grant is preserved and reported as blocked cleanup. Power loss/SIGKILL cannot run
cleanup; durable provenance written before publication supports exact rollback.
Retry against partial state refuses collisions rather than overwriting it.

The installer never edits a controller/adoption configuration: both source
adapters remain default-disabled. Its `adoption_enabled: false` record means no
adoption action was taken, not that this broker controls every account activity.
No deletion, cutover, live owner change, archive-content read as root, service
interruption, backup creation or scope expansion occurs.

## Read-only installed acceptance — commands prepared, NOT executed

Installation already verifies file ownership, modes, content pins and full sudo
syntax. For an optional administrator recheck use the same hash-checked bootstrap
with `--verify-installed`. This recheck is metadata/config verification, not proof
of protected consumer clearance.

Save the authenticated successful installer stdout JSON through the parent into
an ordinary-user SSD task file, for example
`/mnt/vk-storage/vk-retirement-preflight-tests/installed.safe.json`. Failed or
partial output is not acceptance evidence. It contains hashes and scope identity,
not credentials. Then the ordinary mcp worker can run these checks automatically;
no repeated administrator invocation is needed:

```sh
python3 -B scripts/deployment/vk_inspection_acceptance.py --profile managed --installation-json /mnt/vk-storage/vk-retirement-preflight-tests/installed.safe.json
python3 -B scripts/deployment/vk_inspection_acceptance.py --profile historical --installation-json /mnt/vk-storage/vk-retirement-preflight-tests/installed.safe.json
```

Use the published source revision for this harness and its recorded source hashes.
It creates only synthetic objects and its private acceptance lease/socket in the
approved namespace; evidence/lease/artifact files are retained. The historical
check does not move/change the archive and hashes its bytes only as UID1000 before
root scanning. Both calls use `consume=None` and synthetic inspection-only gate
values, never a retirement authorization or change to operational admission.
The ephemeral owned socket is closed by the existing status implementation.
Root is invoked only through the two fixed installed inspection commands.

Real protected PID/TID visibility, churn behavior, syscall seal support and
host performance remain untested. Any consumer, denied inspection, stale result,
wrong binding or substitution blocks. Do not weaken the gate or refresh snapshots
in a loop. An unrelated existing process may still open after its scan; no global
atomic fence is claimed. Operational owner integration and backup/QA/rollback
approvals remain with Staging; fallback survives until human QA.

## Exact administrator rollback — exceptional, not performed

First disable/disarm/drain both adapters through the existing owning controller.
Then use the same hash-checked bootstrap with:

```text
--rollback --approved-plan 29af1c33e029bc1fe9ef9467fd51a03eb586105d --drained
```

`--drained` records administrator attestation, not an automatic owner cancellation
mechanism. The script reads only its root-owned fixed provenance, removes only
`/etc/sudoers.d/vk-process-inspection-v1` if inode/digest still match, and validates
the remaining sudo policy. It preserves helpers, policies, managed/control roots,
all evidence, backups, unrelated includes and fallback. No recursive cleanup.
Complete, failed or prepublication-validated provenance supports withdrawal; if
none exists or the grant differs, it refuses and requires administrator review.
Existing receipts/begun actions cannot be retracted by removing a grant.

Same-UID review remains advisory; LXD admin membership remains a separate existing
privilege boundary that was not used and is not governed by this capability.

## Reproduction and validation

Build as mcp on mounted SSD using
`scripts/deployment/security/build_inspection_installer.py`, the recorded reviewed
Git head, fixed template and the two pinned proposal ELFs. The builder refuses
root execution, non-SSD output, overwrites and digest mismatch. The source receipt
records all source/artifact hashes; generated bytes reproduce exactly.

20 unprivileged fixture/harness tests pass. Actual O_EXCL/no-follow file operations,
fresh-inode enrollment, grant ordering/collision, full prospective fixture syntax,
failure cleanup and provenance rollback are tested. Root UID ownership, OS UUID/
namespace/stdlib checks and installed consumer scan are explicitly modeled.
An actual unprivileged invocation of package `--install` rejects before mutation
with `administrator authentication required`. Neither root bootstrap nor installed
acceptance has run. All 54 existing checker tests also pass.
