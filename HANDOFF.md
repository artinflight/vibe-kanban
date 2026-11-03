# Codex resume history duplication fix — 2026-11-03

Current branch: `vk/95c6-vk-duplicate-con`. The only production-code change is
`narrow_resume_supported` in `crates/executors/src/executors/codex/client.rs`:
accept the real Vibe initialize identity alongside the qualified CLI identity at
exact version 0.159.2. The previous guard silently omitted excludeTurns for Vibe.

The fixture now reproduces a full historical response when the flag is absent;
actual-client regressions cover both identities. Seven client tests and 26 adjacent
compatibility/normalization tests pass; one private fixture is ignored. Two
old/new predicate checks, full format, ops and diff checks pass. Full workspace/CI
and production acceptance remain pending. See `VK_DUPLICATE_HISTORY_FIX.md`
for validation, investigation provenance and deployment acceptance requirements.
Evidence: `/mnt/vk-storage/vk-duplicate-con-20261103-95c6/`.

No backend deployment or deletion occurred. Read `LIVE_DEPLOYMENT.json` and obtain
fresh live observations before deployment; preserve the latest frontend, private
history bindings, database and native homes. Do not reuse historical controllers
or interrupt running agents to force installation. Production verification must
measure actual persisted resume size, history readability and ordinary send.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
