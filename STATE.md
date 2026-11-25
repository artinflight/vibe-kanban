# Deduplication state — November24 file-count repair

The lossless original/catch-up/automatic conversions remain accepted, but the
performance objective is open: source files grew38,791→1,065,426. The user
explicitly requested both lower storage use and faster operation. The prior
space-only acceptance was insufficient. See [packed repair](VK_DEDUP_PACKED_LAYOUT.md).

A packed layout and actual Rust reader pass isolated integrity tests. Five real
sample histories went7,229→8files with identical decoded bytes; optimized and
live performance remain separate. No V2 manifests are published live. Both
serving processes, selected packing sources, pending inputs, settings and backup
epochs remain preserved. The18missing historical dependencies are addressed below. The old mutator refuses unqualified V2 publication.

Daily conversion is held during repair while preserving its enabled05Toronto
calendar. A timer maintenance condition prevents host recovery from restarting
it; exact release instructions and receipts are in the packed repair document.
Existing WakeWatch owns checkpoint/problem reporting; no model polling loop.
Current-data qualification exposed a real history-display bug in old main and
packed readers: raw broadcast replay dropped entries even though stored bytes
matched exactly. Those older main/fallback packed artifacts are not deployable.

The repaired main/fallback builds now pass28focused replay/archive tests each,
full-EOF sample checks and independent source/artifact reconciliation. Main hash:
c4895660de59f1624205c1868301afaf0c1659189103230b274eb2e854330406. Fallback hash:
c6362dd1c9b5285dec1413ba7ec0ed195369ae3f1dfaf915dfcd9ec3c482d290. The protected
reader already has the bounded replay mechanism and its accepted artifact is reused.

All11current-data rehearsal stages are now independently accepted: main loose/
packed/fallback/return histories match; protected six native targets and18retained
replies match with verified original dependencies; all original tables/later writes,
pagination/settings/review/queues/frontend pass; three corrupt packs are rejected.
This qualifies reader behavior in isolation, not live deployment or full acceptance.

All18missing original capture dependencies are now restored byte-for-byte.
Independent acceptance verified18restored inodes and36normal protected/public
replies, with recovery notices and incomplete-original status preserved. Both
current SQL target bindings, settings, sidecars, serving identities and backups
remain intact. Restoration added16,752,640allocated payload bytes and4,096observed
parent-directory bytes; private SSD copies add16,752,640Bto staging. The script's
final memory-pressure refusal was reconciled through fresh read-only acceptance;
no restore was replayed. Why the originals disappeared remains unresolved.

Packing is independently accepted: all 274 groups and 3,639 histories match,
with 580 full pack hashes and unchanged sources/sidecars/current SQL bindings.
The selected layout goes from 1,057,171 files to 4,219 prepared files. Prepared
allocation is 6,768,685,056 bytes including directories. This is still staging;
no live file-count reduction or additional net savings is claimed.

One packed-normal-recovery-v1 script now verifies all prepared files through the
existing normal Desktop-B recovery owner, then both current SQL points, five
current/compatible binaries, the current frontend and a sealed reconstruction
index. Every capture intent and restore receipt is durable; uncertain work is
never replayed. The first checkpoint restored 47 files/49,865,526 bytes. WakeWatch
owns the next completion/problem notification. No Nightly commissioning occurs.

No V2 manifests or serving binaries have been activated. Guarded migration,
compatible live readers/real recovery, ordinary live qualification, safe loose
retirement and final space/file-count/performance acceptance remain unfinished.


Previously measured net reduction73,893,642,640bytes(68.82GiB) includes prior
local/remote-file staging and concurrent growth. New qualification/build staging
must be included in final accounting. Privileged open-original visibility and
remote directory metadata remain unverified; do not claim maximum savings or
strict exclusive filesystem attribution.

Nightly commissioning is explicitly excluded. Its extra composition job remains
stopped with accepted state and partial cursor preserved. No bootstrap, calendar
activation, unrelated backup work or deferred cleanup belongs to this stream.
Earlier full source/SQL/software/frontend recovery proofs remain historical
acceptance of the old layout; they do not qualify future packed retirement.

Previous state: [before packed repair](deployment-history/20261124-before-packed-repair/STATE.md).
Full historical archive: [STATE history](STATE_HISTORY_20261017.md).

Optimized read checkpoint now passed: all five histories/three samples match at
full EOF; summed medians3.877s loose versus3.769s packed(about2.8% faster, warm
cache only). Large live/UI speedups are not demonstrated. Main build completed;
compatible pair builds and current-data rehearsal passed; real packed recovery is running.
