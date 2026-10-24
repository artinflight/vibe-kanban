# e3e1 combined capture/consent preparation

Intent: build only reviewed PR236/239 source fixes on actual deployed source,
with hosted validation and artifact/rollback identity. No deployment authorized.
Branch: fix/e3e1-combined-capture-consent.
codeSha: aa11dd6a5707bba400db2f893eebc857633be437 (tested hosted artifact source). Read with
`git log -n 1 --pretty=format:%H -- . ':(exclude)handoffs' ':(exclude)runs'`.

Changed: 21 reviewed source/test files, one combined writer/legacy-reader test,
compiled incumbent reader fixture, source fence, paired artifact builder,
opt-in hosted workflow, and current handoff/release documentation.
Commands/results so far: fresh git fetch; read-only executable/environment/
frontend-source binding; both scoped git apply --check passed; all 577 mapped
live frontend application sources matched; source fence passed; scoped rustfmt.
No local Cargo compilation, production server launch, security or data writes.

Decisions: actual production base overrides routine latest-staging baseline;
keep the live-only frontend overlay, no wider historical merges. Build only
server/assets; retain incumbent support artifacts/settings. Native Codex Cancel
wording remains upstream; no consent bypass. Keep all review/hold safeguards.

Resume: run Test workflow_dispatch on this exact feature head; inspect the
combined acceptance job, correct scoped failures only, download artifact to
Desktop B and verify hashes. Append exact tested source/run/artifact evidence.
Next: normal explicitly authorized release flow after fresh backup/drain gates.
Known issues: no live release acceptance/physical Android QA yet; no actual
report delivery or badge clearing performed; incomplete past captures remain
unverifiable. See VK_COMBINED_CAPTURE_CONSENT_20261010.md.

## Hosted result and immutable artifact

Draft PR: https://github.com/artinflight/vibe-kanban/pull/240.
Combined run: https://github.com/artinflight/vibe-kanban/actions/runs/38009161259
completed SUCCESS 2026-10-10T00:59:43Z; source
`aa11dd6a5707bba400db2f893eebc857633be437`.
64 compiled focused Rust tests (including real HTTP/recovery and full 240 KB
consent context through real capture and exact incumbent strict reader), 20
mounted UI cases, three frontend type checks, all affected Clippy targets,
format/governance/source fence, acceptance-profile server build and Vite build
passed. Hosted builder asserts source identity, protocol versions, disabled
automatic destructive startup behavior, and compiled feature parity before
uploading the hash-bound server/frontend manifest.
Full Test run https://github.com/artinflight/vibe-kanban/actions/runs/38009148723
also passed: 492 workspace tests passed/10 skipped, workspace Clippy, generated
schemas, Tauri and frontend lint/type checks, branch-policy/freshness and
preservation. Separate unchanged legacy scheduled-goal artifact workflow
38009148715 failed its hosted routing-module bwrap namespace prerequisite
(`RTM_NEWADDR: Operation not permitted`); no support worker/security-policy
change is part of this bounded pair. Do not claim every repository check green.

Artifact ID: 11652584455.
Name: combined-capture-consent-aa11dd6a5707bba400db2f893eebc857633be437.
ZIP bytes: 53251749.
ZIP SHA256: 6c7314035e5d6821c9d2317ff54a5a31c7cccf05249048ce5bed241bd58ded8c.
Artifact/source/job receipts are stored under
`/mnt/vk-storage/vk-combined-capture-consent-20261010/evidence/`.
All 2461 tracked incumbent source hashes match c3 (two CLAUDE symlinks resolved
to their AGENTS targets); 577 live mapped application sources and the page's
1384-byte inline bootstrap match 5ce. The fence preserves all 13 live-only code
files byte-for-byte. No historical branch merge was performed.

## Rollback and remaining external verification

Verified actual incumbent pair on Desktop B:
`B:/vk-builds/vk-combined-capture-consent-20261010/rollback`.
924 files matched after copy. Backend SHA256:
2aa884b359d21373e38c49a6e1589a10e5f69f7c384d2be44515fc0fab41b70f.
Frontend canonical manifest tree SHA256:
876c23dadf93e3f207c0ccae740324b50a8da08a62a77d11d5c0f41e850e220d.
Rollback manifest SHA256:
7c9746171acbf56f7a480c1dcb529e0555802715c4d9a5cfb905b4dc059ea8d4.
Current server PID 1254186 and frontend/support hashes were freshly rechecked;
no production drift, restart, deployment, data/read flag or security change.

External candidate verification is now COMPLETE. A temporary MCP DNS REFUSED
incident blocked existing authenticated clients while the hosted build finished.
The supported anonymous archive route returned HTTP401, which was respected.
Normal DNS recovered without any config/security change; existing MCP gh then
streamed the exact pinned archive directly to Desktop B. No credentials were
copied, extracted or reconfigured, and no network grant/proxy was added.
A Windows verifier default cp1252 text-read error was corrected to explicit
UTF-8; the preserved download was reverified instead of downloaded again.

## Verified ready publication pair

Raw hosted ZIP SHA256 (53,251,749 bytes):
6c7314035e5d6821c9d2317ff54a5a31c7cccf05249048ce5bed241bd58ded8c.
766 candidate files matched the manifest. All 577 compiled application sources
matched source aa11dd6a with zero mismatches. Raw candidate manifest SHA256:
ff33e1881dc285268a9221261f9abf00bcc67d75ce531e80b2cfc1c0375c4896.
Server SHA256 (74,626,776 bytes):
7b32f9efa5c092ca77ecd70483427648539ebf778e15a7138d3891f3986dc442.
Raw built frontend canonical tree SHA256:
e1495db0fe362b7de9bef1a0b6fe23ab866d3972f50fa1c6cb20e9f24839119e.

Ready tar, on Desktop B only (no runtime dependency on Desktop after staging):
`B:/vk-builds/vk-combined-capture-consent-20261010/publication-pair-aa11dd6a5707bba400db2f893eebc857633be437.tar.gz`.
69,698,620 bytes; SHA256:
b40e1b6ae111039fe45929f2dceeaa5aa5d9be96d65a901a18ca996c2c60ac09.
Publication manifest SHA256:
655cdc9189a48c37641a8435adcb6b901d315967134d3cf1863eecaaaf86a20a.
Published frontend canonical tree SHA256:
efbe975c3ad2c33f145d86edc66f14735e03fb8332ea73783ab8283935fc1be9.
All 1,029 artifact files and manifest were re-read from the exported tar and
matched; server mode is0755. The pair preserves every fresh CI-built byte,
adds 263 missing incumbent assets for cached clients, and rejects any non-map
hash-named asset collision. 295 duplicate source maps retain the new build's
source maps rather than old environment-specific paths; old maps stay preserved
in the verified rollback. New index/bootstrap/assets remain from the tested
candidate. Packaging occurs only on B; no local Cargo/frontend build was run.
Verifier/packer scripts and immutable receipts are in the named B task folder;
small mirrored JSON receipts are in the MCP evidence folder.

## Narrow publication step (NOT performed)

The release coordinator can now fetch only the verified tar to a new immutable
MCP release directory, verify its SHA256 and all manifest files again, and use
this exact server/frontend pair through the normal release flow. Retain existing
capacity guard, wrapper/module/scanner, runtime identity, authorization/config,
permissions, data, Recommend routing and owner holds. Do not merge wider PR236/
PR239 branches or unrelated staging baselines. Normal full review and explicit
activation authority are still required; this preparation is not a cutover.

Present the exact verified pair/tar/hash to the normal
release coordinator; stage in a new immutable release directory, preserve all
live support/settings/data, complete normal fresh identity/capacity/current-state
backup/restore and writer-drain gates, then obtain explicit activation authority.
No production action is authorized by this preparation. Roll back executable/
assets with current data using the exact incumbent pair; never stale DB state.
Native generic Cancel wording remains upstream. Incomplete historical capture
remains unverified; no fabricated backfill or actual review evidence is seeded.
