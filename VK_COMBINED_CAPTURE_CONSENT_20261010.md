# Bounded capture/consent release candidate — October 10

WHAT: pair PR236 capture fixes (reviewed 6e27580a4f38975f40326ba773e7f82a27384be6)
and PR239 complete, bounded consent context (reviewed b5e49f393a419a03631cf71ddca74d52e08b9cdc).
WHY: preserve assistant finals and accurately show routine dispatch review;
prevent healthy capture draining from appearing permanently unavailable.
CONTEXT: build over the actual deployed backend c3c48e63 and live frontend
5ce84ee2, preserving the mobile/attention overlay and all other live code.
SUCCESS: hosted compiled regressions, affected Clippy/type checks, runnable
paired artifact with exact hashes, verified incumbent rollback identities.
Preparation is not authorization to deploy, restart, or change security settings.

## Source boundary

The feature branch starts at 5ce84ee21be814b1519cfb2715b50f3432c3e8ba.
Its backend is byte-identical to c3c48e6324f778ccd03a5761c2314b440e9ceac3.
The incumbent executable SHA256 is
2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f.
Live frontend canonical path/hash manifest SHA256 is
876c23dadf93e3f207c0ccae740324b50a8da08a62a77d11d5c0f41e850e220d
(JSON sorted relative paths, each {sha256,bytes}, compact separators).
All 577 mapped application JS/TS sources match the tracked frontend baseline.
External evidence: /mnt/vk-storage/vk-combined-capture-consent-20261010/evidence/.
The source fence verifies exact reviewed files and every live-only code file.
No DB migration, generated shared protocol, lockfile, connector allowlist,
permissions, routing configuration or runtime support worker is changed.

## Hosted validation and compatibility

The opt-in combined-capture-consent-acceptance job runs both reviewed suites,
real writer/HTTP recovery and atomic review tests, mounted history and consent
UI tests, all affected Clippy targets, three frontend type checks and formatting.
Its additional regression passes a full 60,000-scalar/240,000-byte prompt through
validation, pending approval normalization, UTF-8 chunks, raw durable capture,
closure, restart replay and the exact incumbent c3 strict reader. Approval stays
pending; no test represents synthetic content as actual delivered user review.
Capture errors and draining remain distinct, optional HTTP fields preserve older
clients, shared types and receipt schemas stay unchanged. Server and frontend
must be published together to obtain the complete UI behavior.

The artifact builder uses the incumbent acceptance profile/toolchain on Ubuntu
24.04, builds the external-frontend placeholder server before Vite assets,
checks read-only --capacity-build-info and uploads exact source/file hashes.
No application server is started. Hosted fixture writes are disposable checkout
storage only. Native generic Cancel wording remains an upstream limitation;
validation diagnostics are truthful in VK, with full explicit consent preserved.
Historical incomplete capture is not fabricated or backfilled.

## Narrow publication proposal (not executed)

Download the successful immutable Actions artifact to Desktop B. Independently
verify artifact digest, manifest, server and every frontend file. Store the
incumbent actual server plus dist-v6 assets as a separately verified rollback
pair on Desktop B. Do not use the historical initialization-disabled rollback
binary: rollback means the exact currently running c3 binary and 5ce frontend.

Release coordinator must perform the normal fresh identity/controller check,
latest mutable-state backup/restore gate, writer drain and capacity checks under
VK_BACKEND_RESTART_PROTOCOL.md and VK_AGENT_DEPLOYMENT_RUNBOOK.md, then obtain
explicit activation authority. Publish only this server/frontend pair, rebind
normal runtime source/artifact identity through the release flow, preserving all
existing runtime settings, capacity guard, Recommend routing, wrapper, module,
scanner and application data. No connector or approval policy change is part of
this release. Roll back the executable/assets pair with current data; never
restore a stale database merely to roll back code. The compiled incumbent reader
regression establishes JSONL compatibility, not a live state restore rehearsal.

Do not merge the wider PR236/239 historical branches, or merge this production-
based draft into unrelated staging/main without a separately reviewed baseline
integration. Normal branch-freshness gates are not waived by focused acceptance.
Physical Android QA, full unrelated workspace/remote/platform CI and final live
release health remain the release coordinator's gates, not claimed here.
