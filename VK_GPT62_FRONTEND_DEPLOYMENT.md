# GPT-6.2 frontend deployment — 2026-11-18

## Result

GPT-6.2 Sol and GPT-6.2 Astra are live in the public Codex model menu at
`https://vibe.local`. GPT-6.2 Sol is the default for new default-variant executor
configurations. The selector retains explicit current selections and custom
variants, retains GPT versions 5.6 and newer, and exposes Low, Medium, High,
Extra High, and Max for both new models.

The frontend cannot discover future Codex models independently. It consumes the
backend-owned discovered-options stream, whose Codex catalog remains static.
Automatic discovery and automatic latest-Sol defaulting therefore require a
separate backend contract and discovery implementation. `ultra` is not offered
because the current Vibe executor accepts only through `max`.

## Publication

- Branch: `vk/273f-vk-update-codex-frontend-only`
- Implementation commit: `fb8e03406d25d50ee4926f98182741314819c134`
- Prepared branch head: `212d963f5a934fee34f22d48163049031bdddbd4`
- PR: <https://github.com/artinflight/vibe-kanban/pull/298>
- Published: `2026-11-18T22:26:03.820758+00:00`
- Vibe version: `0.1.42`
- Candidate: `/mnt/vk-storage/vk-gpt62-models-20261118/release/paired/candidate`
- Fallback: `/mnt/vk-storage/vk-gpt62-models-20261118/release/paired/fallback`
- Pointer switch: `0.01635185768827796` seconds
- Public assets: `/assets/index-DxHYbG0e.js` and
  `/assets/index-DeUaYq-8.css`
- Activation receipt:
  `/mnt/vk-storage/vk-gpt62-models-20261118/release/activation.json`

The operator explicitly authorized the atomic frontend-only switch. No backend
restart, service restart, profile change, or database mutation was performed.

## Validation

The source passed repository formatting, focused model-selector regressions,
local/remote/web-core/UI TypeScript checks, local/UI lint, unused-i18n, ops
governance, production frontend build, whitespace checks, compiled-bundle marker
checks, and local preview HTTP/API proxy checks. `cargo test --workspace` reached
the host's missing `glib-2.0.pc`; no Rust file changed.

The preservation gate compared 1,327 source inputs and allowed only:

- `packages/web-core/src/shared/hooks/useExecutorConfig.ts`
- `packages/web-core/src/shared/lib/codexModelSelector.ts`

The production artifact contains 417 files. The paired release retains 1,346
assets. The public, mutation-blocked Playwright run verified GPT-6.2 Sol and
GPT-6.2 Astra, all five tiers, Sol selection, no pre-5.6 entry, and zero page
errors. Receipt:
`/mnt/vk-storage/vk-gpt62-models-20261118/release/public-model-browser.json`.

All five systemd service PIDs and invocation IDs were identical before and after
publication. The backend remained PID `2573710` with executable SHA256
`4766246c477fd8d73367969bee9b705586c5b580ddf786515409d977b48ce104`.
The database remained device/inode `2065/15338637` with 99 successful migrations.
Public `/api/health` passed and `/api/info` reported version `0.1.42`.

## Recovery

The fallback is the exact previously active frontend. The 121,726,055-byte
software-only recovery archive has SHA256
`ff21d977334d96a34353998173a4d681c8912384449092525d4f3e86cb953d5b`.
All 4,164 archived files restored byte-for-byte in isolation, and Desktop B
independently read back the archive. No database snapshot or database restore is
part of this frontend-only recovery.
