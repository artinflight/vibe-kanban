# Usage-efficiency acceptance

Tracked in [Vibe T51 — Automatic Restart Preflight](https://vibe.local/projects/1cf19067-4055-4432-bbc1-581919f9185d/issues/c89125a3-5aeb-5335-a1a2-5bf20c9d69c3).

This stream preserves models, effort, AutoSwitch, full history and release
acceptance. It changes pickup input and extends the existing Preparation runner,
not production service state. Source base is staging `7110930b6d9d1fa3f403a963a1ded49140b3eec1`.

## Lossless pickup

The former mandatory STATE/STREAM/HANDOFF total **1,032,169 UTF-8 bytes**.
All three survive byte-for-byte in the root-level `*_HISTORY_20261017.md` files;
keeping them at the root preserves their relative file links. The manifest
records original sizes, SHA256 values and every heading/line locator. No date
trimming, paraphrased replacement archive or historical deletion occurs.
Current indexes expose active protections and route readers to topic evidence.
Exact identities/receipts remain in their original sections, not copied into
every pickup. `pickup.py find QUERY` returns locators without loading history
into the agent's input. Read surrounding sections whenever needed for authority.

`pnpm run ops:check` verifies archive bytes and a combined 16 KiB pickup budget.
The existing fingerprinted Preparation default plan now includes that continuity
validation as a reusable check, alongside unchanged preparation tests and ops
validation. No second cache or job scheduler is introduced. Reuse still binds
source, tool binary/version, environment, config, dependencies, logs and outputs;
volatile owner/data/health/queue checks remain fresh. Changed or damaged results
rerun only affected work. Accepted build/rollback bundles retain full hash checks.

## Shared-job ownership

Missing prerequisites and duplicate-cache ownership already fail before any
Preparation build. Empty plans/commands and missing declared outputs fail closed.
Nightly PR263 owns exact producer lifetime, stream drain, error propagation and
sealed capture completion; it must not publish an early successful parent exit.
Staging owns the native queue fixture's recorder-drain correction and actual
compiled-artifact queue readback. Do not add a parallel job runner to fix either.
Neither a completed launch nor an empty log is a successful result attestation.

This branch fixes one reproduced runner hole: nested empty output directories
were accepted as artifacts. They now fail without a successful cache receipt.
It also streams child output in 64 KiB blocks through EOF before log/artifact
sealing, under the same finite timeout. A delayed inherited writer regression
verifies the final log and artifact are present before caching. Timeout kills
only the new invocation's owned process group and cannot publish success.
EOF is only stream-drain proof: Nightly must still join its exact producers and
verify their exit/readback results. Detached producers that close stdout are
outside the generic runner's completion proof; do not launch them as synchronous
Preparation steps or treat a parent exit as their result.

## Measurement contract

Use the same committed fixture commands and acceptance in both modes. Count
actual launches, hash-checked outputs and volatile checks across identical
repeated requests, then invalidate one input and test its rerun. Measure pickup
bytes separately from validation calls and provider calls. This scripted
benchmark makes **zero model calls** in either mode and changes no selected
model. It cannot prove billed-token, money or native same-model call savings.
The latter requires a real same-model workflow receipt from coordinated owners;
do not substitute bytes divided by four or a mocked provider success.

## Measured result

[Machine-readable synthetic receipt](USAGE_EFFICIENCY_MEASUREMENTS.json) records
the actual identical-command run with matching output hashes:

| Measurement | Before | After |
| --- | ---: | ---: |
| Mandatory pickup UTF-8 bytes | 1,032,169 | 8,029 |
| Identical repeat: validation/build/fresh command launches | 3 | 1 |
| Cold + repeat + changed-input command launches | 9 | 7 |
| Fresh acceptance executions across those requests | 3 | 3 |
| Provider calls in this fixture | 0 | 0 |
| Original historical bytes retained | 1,032,169 | 1,032,169 |

Mandatory input fell **99.2221%** (1,024,140 fewer bytes per full pickup).
Relevant source/topic reads remain additional; the receipt also counts the
same four recipe/source/test reads on both sides. The identical repeat avoids
two actual command launches; a changed input reruns validation and build.
No model-call, billed-token or credit reduction is proved by this fixture.

Validation: 61 Preparation/queue regressions passed in 15.956 seconds, five
continuity tests and one measured workflow test passed, and `ops:check` passed.
The nested-empty-artifact regression was observed failing before correction.
The first sandbox suite could not open its six loopback fixtures; the same
suite then passed using the supported isolated-test route. `pnpm run format`
completed Rust formatting but stopped at missing Prettier. No dependency
installation, local Cargo build, backend/frontend aggregate check or live
provider acceptance was attempted during the shared resource hold.

## Remaining coordinated acceptance

Staging must reconcile its newer uncommitted pickup updates into topic guides
or an additional hash-bound archive before adopting these indexes. Never
overwrite those updates with this older source snapshot. Keep the concise
indexes and archive pins when merging future owner notes.

The real same-model workflow measurement and compiled native queue acceptance
remain pending a permitted owner window; this fixture is not their substitute.
Reuse these exact scripts/checks in that acceptance, keep the selected model,
effort and AutoSwitch unchanged, and bind actual input/call/rerun receipts.
No new execution is launched merely to obtain a benchmark while all coding
slots are occupied. Existing owners retain producer and release integration.

## Integration boundary

Staging's latest acceptance remains authoritative for production release;
Nightly604d is the only backup/package/schedule owner. Shared private handoffs
carry operational receipts; public GitHub receives source and synthetic data
only. GitHub repository issues are disabled; this work continues in the existing
Vibe Automatic Restart Preflight issue and a dedicated source PR, without
changing repository settings. Production schedule, backup, restart, routing,
credentials, privileges and human-QA cleanup authority are unchanged.
