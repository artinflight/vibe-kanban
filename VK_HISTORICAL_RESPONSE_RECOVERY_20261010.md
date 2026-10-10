# Genuine native reply recovery

WHAT: Restore a missing assistant final beneath its original Vibe prompt without
replaying the task, rewriting its capture or certifying that capture complete.
WHY: Seamus can see his original T18/MM prompts but no responses. Saving their
final text in an incident report did not restore either conversation.
CONTEXT: This bounded patch is based on accepted joint
`604285afbe9a8889aeff2c6a681bd3df998d3770`, retaining PR240 capture/consent,
cdad mobile and assignment. Staging owns integration/publication. No production
restart, session prompt, approval setting, credential or badge write is performed.
SUCCESS: Signed import verifies the original identities and native evidence,
persists a distinct recovered-response record, and the normal conversation reader
renders the authentic final with its original timestamp and a visible warning.

## API and storage

`POST /api/execution-processes/{original-execution}/recover-native-final` accepts
only workspace/session IDs, expected execution revision, native session/turn IDs,
native prefix byte length/SHA-256, original capture SHA-256, original prompt
SHA-256 and final UTF-8 SHA-256. It accepts no text, filename, command or URL.
Body limit is8192bytes. It requires the existing verified relay-signature
context; unsigned local/remote calls return401. Use the existing authenticated
paired client and normal signed request path. No new keys or auth grants.

The backend derives the native filename under the configured Codex home. It
rejects symlink files/directories, collisions, wrong execution/native/prompt/turn
identities, revision changes, dropped/running/reset executions, ambiguous finals,
missing native completion, damaged JSONL (including preceding history), hash
changes and oversized evidence. All records in the pinned prefix are parsed;
the final must equal that exact native turn's task_complete message. Source cap
256MiB; individual entry16MiB; final128000UTF-8bytes. Verification is serialized.

Only the separate `{execution}.recovered-final.json` sidecar is written, mode0600,
next to the preserved original capture. Publication uses fsync and atomic
no-clobber hard-link; identical retries are idempotent, conflicting retries
fail closed. Interrupted staging files cannot become visible responses.
No DB migrations/rows/flags, raw logs or capture closure sidecars are changed.

`GET /api/execution-processes/{original-execution}/log-history` revalidates the
persisted record against the execution and native source, then returns the final
as a normal assistant entry for that original execution. Metadata retains native
turn/message identity (when present), source line and exact hash. The timestamp
is the native final timestamp, not recovery time. A pinned prefix remains valid
after later append-only native work. Other executions/sessions are unaffected.
The frontend shows the reply and keeps an incomplete-capture notice. It does
not silently declare the raw history complete. Strict review verification still
reads the original raw log and fails; recovery does not create mark eligibility.

## Next restart and recovery procedure

1. Staging applies only the bounded diff over604285af and validates the reconciled
   source. Package the matching backend and web-core frontend. The existing dot
   connector and normal reply tools need no new tool/allowlist or MCP executable.
2. Publish through the owner's next-restart flow; this patch does not authorize
   restart/cutover. Include session-sidecar storage in the existing state backup.
   The old backend safely ignores this optional sidecar; it cannot display it.
3. Through the existing signed client, submit ONLY the separately retained T18
   and MM identity/hash-bound request artifacts after fresh source checks. Native
   append-only activity is allowed; edits, missing identities or captures fail.
4. Read each original execution via log-history and existing get_latest_agent_reply.
   Refresh/open its existing conversation; check exact original prompt, reply,
   native timestamp and warning. Check subsequent work and badges unchanged.
   Do not mark read or infer completion from recovered text.

The reviewed request artifacts and authentic private finals stay outside Git in
`/mnt/vk-storage/vibe-dot-connector-maintenance/runs/e3e1-missing-replies-20261010`.
Do not put private transcripts or credentials in CI/artifacts/PRs. Hosted tests
use sanitized real historical formats and disposable sources/databases only.

## Prevention and causality

T18's strict recorder stopped at11:00:37.548374Z on broadcastLag358 messages;
MM stopped at11:07:40.898518Z on broadcastLag1, about10–16seconds after launch.
These thread-resume bursts preceded later ENOSPC. Authentic native finals remain
intact. PR240's existing AA changes separate lossless bounded durable pipe
capture from lossy UI broadcast, claim ownership before spawning and drain to
actual EOF/metadata Finished. Queue/burst/UTF-8/early-exit/map-removal and real
HTTP recovery tests cover that failure mechanism. Do not claim an unproven
change introduced it. Future prevention does not reconstruct historical logs.

## Validation

Hosted workflow `historical-response-recovery.yml` compiles/tests recovery,
real Axum HTTP import/reader, existing signing argument/nonce binding, duplicate
and concurrent retries, restart readback, subsequent native append, damaged
records, identity mismatches, symlinks/collisions and resource limits. Existing
strict review, closure/lifecycle and mounted-history regressions also run.
Mounted frontend regressions prove original execution/timestamp/content display
and persistence of its warning across another execution's successful fetch.
Passing results and exact source SHA are recorded in the Staging receipt once
available. No local Cargo build or real user review is fabricated.
