# Deduplication state — November24 file-count repair

The lossless original/catch-up/automatic conversions remain accepted, but the
performance objective is open: source files grew38,791→1,065,426. The user
explicitly requested both lower storage use and faster operation. The prior
space-only acceptance was insufficient. See [packed repair](VK_DEDUP_PACKED_LAYOUT.md).

A packed layout and actual Rust reader pass isolated integrity tests. Five real
sample histories went7,229→8files with identical decoded bytes; optimized and
live performance remain separate. No V2 manifests are published live. Both
serving processes and all history, pending inputs, settings and backup epochs
remain intact. The old mutator refuses unqualified V2 publication.

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

Five main current-data phases now pass exact reference/loose/packed/fallback/
return comparisons and all-table/later-write preservation. Protected qualification
found18original capture files missing from live storage; their recovery records
remain, but the serving reader correctly refuses unverified recovered replies.
All18preserved independent copies match the recorded original hashes (16,713,100B).
Their disappearance is not yet explained; no live restoration has been performed.

One current-data-originals-v1 script tests those exact originals as read-only
private overlays, with fresh SQL copies and the same accepted reader binaries.
All11current-data/corruption/ordinary phases must pass. Seven overlay regressions
pass. Only the previously proven two-diagnostic order exception is allowed;
every other content/order/metadata remains strict. WakeWatch owns the next wake.
After qualification, restore only absent exact dependencies without overwrite,
then verify serving history. Live packing/deployment/recovery and final accounting
remain unfinished; pending inputs, settings and all backup epochs are preserved.


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
compatible pair builds passed; fresh current-data/real recovery qualification remains.
