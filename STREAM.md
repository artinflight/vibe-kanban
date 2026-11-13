# VK::Run Provenance

Branch `vk/a507-vk-run-provenanc`, based on freshly fetched `fork/staging`
`bc3b89dee`. Add automatic, local file-context observations to normal coding-agent
start/resume/review spawn and exit paths, independent of AutoSwitch. Start from
Media Management's merged context-management record format at `4b2783612ad1a80ce1394d4f168cf0c36fd6cba2`.

Records bind actual workspace/session/execution IDs to version labels and bounded
hashes, detect file changes with native events and end snapshots, and keep mixed,
unknown, inherited context and model-read uncertainty explicit. No prompts,
transcripts, credentials, extra model calls, polling service, DB migration or new
permission layer. Existing jobs, queues, settings, capacity and ownership gates
remain intact.

Address PR #297 review findings: fix backend fixture compilation and exempt
only confirmed-empty scopes from unversioned coverage; retain unknown for real
unversioned or unavailable instructions. Preserve the documented v1 shape for
the independently owned CU PR #56 consumer.

Prepare one focused PR into staging. Do not merge, deploy, restart, or launch
separate before/after agent tests. Activation and CU::Audit contract are in
[VK_RUN_PROVENANCE.md](VK_RUN_PROVENANCE.md). Ordinary implementation usage is
observational evidence only; automatic production coverage awaits authorised
backend activation and future normal work.

Prior stream history: [STREAM history](STREAM_HISTORY_20261017.md) and
[previous record](deployment-history/20261030-before-reconciliation/STREAM.md).
