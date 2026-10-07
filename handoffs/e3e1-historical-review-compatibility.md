# e3e1 historical review compatibility

Intent/WHAT: fix f2642af3d real-data replay and PR150 lint/fixture setup failures.
WHY: native deployed events outpace the pinned SDK; default CI lacks MCP storage.
CONTEXT: isolated branch fix/e3e1-review-log-integrity from combined2bc909d6375e13d0dd47f370eec0100fae3b2075.
SUCCESS: compatible exact historical identities, fail-closed damaged/closure checks,
compiled HTTP/recovery coverage and relevant CI green. No live mutation/deployment.

codeSha: determine exact commit with `git log -n 1 --pretty=format:%H -- . ':(exclude)handoffs' ':(exclude)runs'`.

Files: codex normalize_logs validator + sanitized fixtures; log_history reducer error
boxing; receipt source small error; HTTP fixture isolation/default-vs-MCP execution;
STATE/STREAM/HANDOFF and VK_CONNECTOR_COMPATIBILITY_20261007.md.

Executed: Codex normalizer10/10 passes; rustfmt and Ops Playbook pass. Full pnpm
format stops at missing frontend prettier (frontend inputs untouched). Shared build
cache reused a Staging-compiled asset path; HTTP guard rejected before fixture creation.
Dedicated SSD cargo-target-compat is now rebuilding. Failed receipts retained.

Acceptance logs and versioned patch bindings will be delivered through the root
maintenance handoff, not a claim that a draft PR is ready for deployment.
Resume: use /mnt/vk-storage/vk-connector-repair-20261007/check_compat.py and isolated
historical-compat harness. Never use shared cache to certify compiled fixture paths.
Do not create historical closure fences, consume live approvals or infer delivery.
Remaining: exact four historical replays, compiled suite and relevant CI; root owns
integration/backend adoption and actual caller delivery signal. No user decision.
