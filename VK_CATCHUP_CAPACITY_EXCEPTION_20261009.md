# Additional bounded capacity decision, October 9

The approved 05498ad7 retirement is complete. This is a **new request**, outside
that frozen file set. No further file has been removed.

The same actual MCP candidate is restoring the full preserved scope. Comparing
the authenticated baseline and fresh B indexes finds 1,306 changed names,
including 1,148 regular files requiring at least 6,334,836,736 additional native
bytes while their prior versions remain quarantined. Mode and hardlink closure
does not enlarge this index comparison. Rehearsal edits and subsequent writes
remain additional requirements; actual stopped-tree access and final allocation
are not yet accepted.

The initial file allocation lower bound is 95,156,195,328 bytes. Together with
that catch-up and the existing 8,589,934,592-byte reserve, the minimum is
110,080,966,656 bytes **before directories and later changes**. Initial available
space was 105,369,804,800 bytes: at least 4,711,161,856 bytes short. Neither the
reserve nor included scope will be reduced to fit.

One previously excluded incident archive can supply 23,441,530,880 allocated
bytes without purchasing hardware. Its native original remains protected:

`/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst`

Exact identity: device 2065, inode 7340415, size 23,441,521,918 bytes, one link,
UID/GID 1000, mode 0600, mtime/ctime 1791409456129506845 ns. SHA-256:
`e994567edaacc75d8aa9a3497b8384a8dbacec462854a3f7f8c5760e1a9a0ce4`.

A bitwise copy is independently read-back/hash verified at
`B:/vk-backups/vk-safe-release-20261009/excluded-incident-archive-preservation/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst`.
Its retained `tar.log` and `paths.nul` are also preserved in the verified B bundle
`excluded-incident-archive-metadata-preservation.tar.gz`, 4,298,474 bytes,
SHA-256 `c783bbc9d54093be2e03efd6e5623909cd1603e53321bae317b7c74dc74b3987`.
This was a failed historical capture. Preserving its bytes does **not** turn it
into an accepted recovery backup or close any incident exception.

The requested action is retirement of **only that one regular native file**,
after refreshing all identities/hashes, privileged read-only consumer clearance
and exclusion/dependency checks. Keep its directory roots, metadata, all other
files, B copies, incumbent/fallback and recovery evidence. Record its B locator
beside the retained metadata. No general cleanup is requested.

Consumer clearance is not yet obtained. The operator must authenticate the
prepared read-only helper; earlier denied sudo access will not be bypassed.
Final measured capacity and catch-up/fallback headroom still gate promotion.

The helper is
`/mnt/vk-storage/vk-runtime-backup-20261009/excluded-incident-archive-consumer-check-readonly.py`,
SHA-256 `3a93efd9504c632df1bce17ddb060d0bd3907e14193b1372ed9e399c7d2c507d`.
It inspects process executable/cwd/fd/map references to the single pinned inode,
fails on inaccessible live processes or consumers, and performs no mutation.
Operator command, after verifying that helper hash:

```sh
umask 077
sudo python3 -B /mnt/vk-storage/vk-runtime-backup-20261009/excluded-incident-archive-consumer-check-readonly.py > /mnt/vk-storage/vk-runtime-backup-20261009/excluded-incident-archive-operator-consumer-clearance.private.json
```

The private receipt must report `consumer_clearance_passed: true`. This inspection
does not itself authorize retirement. The archive is outside all 77 current
capture roots and does not contribute to either accepted B checkpoint. Its failed
capture's payload directory and every other local entry remain excluded from the
requested retirement.
