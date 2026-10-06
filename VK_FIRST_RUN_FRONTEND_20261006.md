# October 6 First-Run Frontend And Candidate Payload

## Result

The real VK frontend is built from exact source
`86f62b2a4a1baff54cde715749b97f283907b8f6`, not placeholder assets. It is packaged
with the previously verified candidate server, compile-disabled v2-compatible
rollback server, guard and CU38 source95e7aea. This is an inert candidate payload,
not a sealed handover, a production deployment, or final rollout approval.

Artifact root: `/mnt/vk-storage/vk-first-run-gates-20261006/`.
Payload: `candidate-release-86f62b2a4a1baff54cde715749b97f283907b8f6.tar.gz`.
SHA256: `8a0ad15b2e36112af072304328af04507ac51aa90bfa98e9990c90a58cd4cf18`.
Size:86,917,322bytes. All772 archive files were streamed back and hash-verified,
including the manifest. The original acceptance bundle is unchanged.

## Source And Build Proof

`frontend-86f62b2/frontend-build.json` binds2371 original source hashes,765 output
files, the installed dependency lock hash and the normal
`pnpm --filter @vibe/local-web run build` command (`tsc && vite build`).
The dependency lock exactly matches the installed tree. A frozen Git archive,
not the concurrently edited development worktree, supplied build inputs. All
tracked hashes were unchanged afterward. Shared paths/dependencies were
read-only, build output was task-local on mounted SSD, and external networking
was isolated. No dependency install or GitHub Actions dispatch occurred.

The first setup attempt lacked the isolated Corepack cache path and failed.
After that was corrected, the build inherited the agent's1.5GiB MemoryHigh and
spent time swapping. Only that unfinished build process group was stopped.
The existing pinned `vk_bulk_job.py` then ran the same build with4GiB MemoryHigh,
6GiB MemoryMax, CPU/IOWeight50 and the disk-space guard. It passed in124.317seconds;
service receipt records2.7GiB peak memory and zero swap. Preparation must use that
existing bulk tool for builds, not repeat the agent-cgroup mistake.

Installed bulk-tool SHA is
`552aa9a9b5fd78f2c0309f755b1d9368abf0547173ceeb5569eef0ed4fea26c1`, matching
October5's published PR142 package. The successful job receipt is beneath
`bulk-build/`. Build logs preserve the stale Browserslist, Tailwind content,
mixed-import/chunk-size and absent Sentry-upload-token warnings. No telemetry
upload or provider call was allowed by the network-isolated build.

## Served Assets And Browser Limits

The actual candidate server served this external directory through
`VK_FRONTEND_DIST_DIR`, inside the existing reviewed synthetic boundary.
At1440px and390px, the loaded JS hash matched the built entry
`/assets/index-DuHXsj1K.js`; CSS is `/assets/index-QO1t6__J.css`. Loaded assets
returned200, with no JavaScript page errors. Screenshots show the real initial
setup and local workspace shell, not the embedded placeholder. This was a fresh
synthetic DB; only synthetic onboarding choices were saved and no agent launched.

Final browser root:
`/mnt/vk-storage/vk-sfr-http-20261006/vk-continuation-http-p65xbu_a`.
Read `frontend-browser.json`, desktop/mobile screenshots, source provenance,
isolation proof and cleanup receipt. Earlier `242mf5ys` and `nl7doc_a` preserve
setup/sign-in observations. `smwh2_fj` failed because the harness matched the
disabled create-workspace Continue button; the corrected selector did not alter
application code. Do not count that attempt as a full pass.

Fresh-account remote auth/relay endpoints returned400 with no configured remote
account. Local-only navigation proceeded through the actual skip-sign-in flow;
external account integration was not tested. This is asset/local-shell smoke,
not all user workflows, real mobile-device QA or full feature acceptance.

One visible pre-existing issue remains for development review: the initial
onboarding screen overflows at390px. `LandingPage.tsx` in
`packages/web-core/src/features/onboarding/ui/` uses an unconditional
`grid-cols-3` at line380. That file is identical between staging8b562265d and
candidate86f62b2; it is not a new scheduled-first-run regression. Main local
workspace layout renders at390px. The issue was not hidden or patched in a
deployment branch, and no broad mobile UX pass is claimed.

## Package And Rollout Boundaries

`deployment-candidate.json` and `deployment-payload-receipt.json` bind exact
backend/frontend/fallback/guard/CU source bytes. At runtime the external frontend
path is required; the old embedded placeholder is not an acceptable fallback.
CU source is packaged, not installed dependencies or a deployed CU service.
Codex0.159.2 remains required. Current launcher/account/home/module/shared-feed
and user choices must be bound in the later fresh handover preparation.

PR147's later516148dc2 adds test/fixture/docs only; inspected production client
code and frontend inputs remain unchanged. Its fresh CI and independent review
are not replaced by the older86f62b2 build receipt. Rebind accepted final source
provenance after review without unnecessarily repeating unchanged broad suites.

The payload's `rolloutAuthorized` and `sealedHandoverReady` remain false. Required
next steps are the stop finding/final review, explicit rollout checkpoint,
compatible CU-first deployment, fresh Desktop-backed preservation/drain and
same-latest-data v2 fallback rehearsal. Then perform one paired VK/frontend switch
and verify routed version plus existing sessions/settings/attachments/dot.

Packaging started with3,370,852,352 SSD bytes available and ended with
3,276,582,912. No archive or staging cleanup was used to create headroom. The
large archive proposal remains conditional as documented in
VK_ARCHIVE_DEPENDENCY_REVIEW_20261006.md. The separate release/review packet
Desktop delivery receipt is `desktop-preservation.json`; it is not a fresh
production-data backup or permission to delete originals.

Desktop delivery completed with full-file SHA256 verification and zero transport
retries at `B:/vk-backups/vk-first-run-gates-20261006/`. The payload hash above
matches. Review packet `review-packet-1791318353033289338.tar.gz` has SHA256
`b2186eabf2a5beb62f4476e80b76d268af071d687c2786e8f6da6700fa45ab1e`.
`final-review-evidence.json` separately records source equivalence, live service
identities and the latest review gates. No service change occurred.
