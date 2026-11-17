# Production reclamation pickup — 2026-11-17

Read STREAM.md for current measurements and owner receipts. Zero production
VKLOGCAS1 manifests are installed at this checkpoint; do not report preparation
as actual recovered space. Current full payload allocation is92,632,117,248B.

Private root case `/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117`:
- `native-166-build` is the actual guarded main build/test. Current original main
  PID645213 and original/protected/proxy owners remain unchanged. Deployment must
  use its successful source-pinned artifact, never the older0.159-only guard.
- `prepare_release.private.py` produces fresh compatible main/spec/adapter/host
  inputs after actual build success. Existing qualified protected40a stays.
- `controller.private.py` is the new finite full-scope operation; ARMED through the single
  native chain `vk-log-dedup-full-20261117-3197505a.service` (PID1545066,
  invedad5c8ca48a4dfc88c8c5c652c84095). Read LAUNCH_RECEIPT/CONTRACT and its
  actual launch folder; after build success, SEALED_OPERATION points to the new
  actual full-scope operation. It waits for actual build and natural root completion.
  Never relaunch consumed inputs; original failed attempt remains preserved.
  Must complete first4 live acceptance then ALL positive-benefit current closed
  batches, independent B restore/SQL/controls, complete session object closure,
  Rust EOF, allocation accounting, Vibe public/UI recovery, WakeWatch restoration.
- `batch_support.private.py`, `closure_support.private.py` and controller helper
  tests pass. Own new staging replicas can retire only after publication+B proofs;
  primary CAS, all old epochs, sidecars and original backup bytes remain intact.
- `wakewatch-pause` contains the exact source preimage/receipt/owned hold and
  `restore.private.py`. All five monitors continue naturally, zero new dispatch.
  MUST restore previous bytes/configs and verify five ordinary ticks/readiness.

Current owner handoffs: Vibe
`/mnt/vk-storage/vk-log-reader-release-20261104/refresh-20261117-v1/HANDOFF_MANIFEST.private.json`;
Nightly `../nightly-coordination-20261117/ROOT_HANDOFF.private.json` under the dedup
case. Both existing owner turns are complete; no further approval/turn is awaited.
Nightly remains sole producer/schedule owner; batch-source-v3 and BASE_PROVIDER_CATALOG
are required. Hold actual normal B/reader class and real WriterFence, serially
switch B scopes without nesting producer leases, retain immutable custody epochs.

The Nov4 native ATTEMPT was consumed and failed before any host boundary. Never
replay it. The exact32,579 missing paths were separately archived/retired Nov14
(31,572,000,768 allocatedB); accepted restore-before-old-view remains explicit.
Do not recapture/credit them or restore them merely to certify current readers.

While any manifest remains, use compatible readers. A failed later batch rolls
back only itself or retains fully verified mixed raw/archive serving state; never
fallback to old software or overwrite the current main database. Preserve latest
frontend, current99-migration data/review writes, pending/uncertain prompts and all
selected model/route/settings. Actual deployed resume/growth still needs proof.

Actual8executor tests +74Python regressions +13private helper tests pass.
Public commitd007c88d2 contains exact0.166 guard and guarded subsequent batches.
PR291 remains draft into staging; no merge. Run full formatting and ops pickup
checks after updating this note. Historical checkpoints remain in Git/private
receipts; the apparent old Nov4 armed state is no longer current.

Historical scope: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
