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
The main packed-reader artifact is accepted after exact success reconciliation.
Its hash is4a14b76bc3f0ce85c702f099e901b89fe6cc962df3221ab476845a80d3d87957.
Both compatible builds are now independently accepted: protected reader and
V2-aware fallback retain their separate source overlays and pass10reader tests
each. Current-data qualification found a real display-replay defect: the existing
main reader and packed candidate both drop raw broadcast messages when
normalization falls behind. One tested history rendered109versus103entries with
different replies despite identical decoded stored bytes. Those main/fallback
packed artifacts are not approved for deployment.

The already-preserved protected reader's bounded finite-replay mechanism is now
applied to main/fallback sources. One replay-repair-build-v1 script runs focused
replay/archive tests and serial builds under the existing shared target, resource
limits and WakeWatch. Fresh current-data/real recovery qualification remains open.
No live service, source history, pending input or selected setting was changed.


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
