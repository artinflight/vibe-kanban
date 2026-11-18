# GPT-6.2 frontend model update

Branch `vk/273f-vk-update-codex-frontend-only`, based on current `fork/staging`
`dbcbfbe4e`, adds GPT-6.2 Sol and GPT-6.2 Astra to the frontend Codex picker and
makes Sol the default for the default Codex variant.

Scope is limited to frontend model normalization, default resolution, focused
validation, and continuity documentation. Do not edit the backend catalog or
reasoning enum, mutate live profiles/data, restart a service, or deploy from this
feature-preparation branch. Preserve custom variants, explicit selections, and
all streamed GPT models at version 5.6 or newer.

Automatic future-model discovery remains a backend follow-up because the browser
only consumes the backend discovery WebSocket. Latest-Sol defaulting can become
automatic once that dynamic catalog is available to executor-default resolution.

Prior stream history: [STREAM history](STREAM_HISTORY_20261017.md) and
[previous record](deployment-history/20261030-before-reconciliation/STREAM.md).
