# Current production — 17 November 2026

The compatible log readers are deployed. Main executable SHA256 is
`4766246c477fd8d73367969bee9b705586c5b580ddf786515409d977b48ce104`;
protected reader is `40a91f69f31c1b9751f8f5a699fc8dfaa6f20138ba1b0ab528788aecb7ddd000`.
The build is base087319cc4 plus the exact d007c88d2 native-resume overlay;
it is not a plain build of either commit. [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json)
records current hashes/provenance and retains historical releases separately.

Four original paths now contain verified lossless VKLOGCAS1 manifests. Net
allocated recovery is827,506,688 bytes including all canary objects and their
object-directory blocks. This first batch is NOT full reclamation. Preserve every
old epoch, sidecar, complete object store, pending prompt and selected setting.
NEVER select any historical archive-unaware fallback over remaining manifests.
The current99-migration authoritative DB and latest existing frontend are preserved;
public TLS/assets and all five serving/ingress services were verified after recovery.
Blue remains retired. No provider settings or concurrency guard was changed.

The actual continued native runtime is0.159.2: its initial resume now returns
zero historical turns/5,126 response bytes versus8turns/10,746,496 bytes before
deployment. The isolated0.166 fixture is qualification evidence, not deployed
runtime evidence. No extra provider request was made for measurement.

The operator-approved follow-up moved ONLY two inactive build archives to
independently verified Desktop B copies, preserving restore metadata and removing
only their unchanged SSD originals.303,202,304 allocatedB released; SSD postcheck
3,492,601,856B exceeds3GiBfloor. The full current history recheck passes22responses,
including exact7page/49entry reconstruction, plus public TLS/assets. Its334.782s
run used existing600s completed-data supervision; older failure receipts remain.
No production conversion was armed or started. See STREAM/HANDOFF for receipts.

Full production deduplication remains unfinished. Today's exact history mismatch
was workspace-path rendering context, independently reproduced on raw and archive
inputs. The prepared continuation adopts compatible readers without reactivation,
excludes the completed batch and separates strict history acceptance from lossless
service recovery. WakeWatch's previous dispatcher and all five configurations
were restored exactly; ordinary monitoring continues. No new maintenance was
started for this preparation. See [STREAM](STREAM.md), [HANDOFF](HANDOFF.md) and
[OP::Disk Space procedure](VK_LOG_RECLAMATION_READINESS.md) for actual readiness,
resource gates and outstanding full-scope/UI/normal-B closure acceptance.

[PR291](https://github.com/artinflight/vibe-kanban/pull/291) remains the source
integration record; commit/push does not deploy the prepared operation. Required
branch checks and private deployment qualification are distinct. Earlier source,
frontend/scrolling integration and provider qualification remain in
[the preserved November3 state](deployment-history/20261117-before-log-reader-continuation/STATE.md).
Their historical deployment IDs and acceptance budgets are not rewritten.

Full historical archive: [STATE history](STATE_HISTORY_20261017.md).
