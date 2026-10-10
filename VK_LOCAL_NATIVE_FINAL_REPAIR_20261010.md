# Exact original final repair through the service UID

This continues PR241 for the two reviewed October10 incident executions. The
signed HTTP writer remains unchanged. No paired caller exists; the bounded
`repair_native_final` CLI uses the existing non-root service UID instead of a
signing credential. It never initializes a deployment, migrates a database,
creates a listener, or accepts reply text or an evidence filename.

The only targets are T18 `3ce20433-f984-4c33-800f-d4987145fa4a` and MM
`c64a7b0c-9c34-43e0-b70d-7e05f93751ef`. Their exact workspace, session,
revision, native session/turn, source-prefix, original capture, prompt and final
hashes are pinned in the two reviewed request JSON files. Paths are fixed to the
existing Green data and Codex roots; arbitrary targets and paths fail closed.

The CLI checks its effective UID against the live server's non-root UID, verifies
that PID owns the selected loopback listener, and retains its Linux start ticks
to reject PID reuse/restart. Existing database/evidence/output paths must belong
to that UID; symlink evidence is rejected. SQLite opens with `read_only(true)`
and `create_if_missing(false)`. Existing model lookups run without migrations.

`GET /api/execution-processes/{original}/native-recovery-status` is a read-only
server endpoint limited to the two exact reviewed completed originals. It
returns server identity, original revision/session/workspace, hashes of canonical
storage locations and the server's authoritative capture-owner state. The CLI
requires inactive, incomplete capture proof before and after native verification.
An empty standalone capture registry is never treated as server proof. A missing
endpoint, changed PID/revision/storage, active writer or unavailable status fails
closed. HTTP import still requires its existing verified relay signature.

PR241's native/parser/prompt/revision/capture/hash/binding validators and
mode0600 fsync/atomic no-clobber publication are reused directly. A final model
and server recheck follows native parsing, with a capture hash check before
publication. Verify-only also refuses a conflicting existing sidecar. Only the
separate recovered-final sidecar can be published; no raw/native/closure evidence,
database row, timestamp, unread/review flag or later execution is rewritten.

## Invocation after matching owner publication

Use the fresh actual loopback server PID/port; do not use an obsolete service
unit's PID. These are argument shapes, not commands already run against live
data. Run without sudo as the existing service user.

```text
repair_native_final --target 3ce20433-f984-4c33-800f-d4987145fa4a --server-pid PID --port PORT
repair_native_final --target c64a7b0c-9c34-43e0-b70d-7e05f93751ef --server-pid PID --port PORT
```

The default is verify-only. Publication additionally requires
`--apply SAME_EXACT_ORIGINAL_EXECUTION`; boolean apply flags, another target,
unknown/duplicate arguments or replacement paths are rejected. Receipts contain
only target/native-turn/final timestamp/hash, verify-only/created, read-only DB,
inactive writer, incomplete capture and uncertified review facts. A successful
apply is not itself normal reader/UI restoration acceptance.

## Integration boundary

Staging alone owns review, combined build and publication. Deliver this bounded
continuation with PR241's reader/warning patch and only required PR240 capture
queue/ownership/drain and pending/error handling dependencies over actual
production. Do not wholesale deploy604 or include unrelated assignment, consent,
mobile, scheduler, notifier or policy changes. Do not send Staging repair prompts,
edit its checkout, restart backend/connector, or alter the approval watcher.

The current production reader cannot display these sidecars, and it lacks the
authoritative status endpoint. Matching backend and recovery-warning frontend
publication is a required dependency before live verify/apply. Once available,
record sanitized before/after preservation evidence, apply the two exact originals,
verify idempotence and read each through normal APIs and its actual existing
conversation UI under its original prompt. Preserve incomplete-capture notices
and unread/review state. Neither conversation is restored by a patch or verifier.

## Validation scope

Retain the existing51 hosted Rust tests,20 mounted conversation tests,
type/lint checks and both actual-native-source verifications at codeab547620.
Only the added CLI/status tests need a fresh run. They cover exact pins and
explicit apply, UID/root/path/listener refusal, read-only database creation/write
refusal, actual server capture ownership, revision mutation, missing protocol,
real HTTP status and the shared CLI core's verify/apply/duplicate/conflict paths.
Disposable apply checks preserve database/raw/native/closure bytes and mode0600.
Compiled results and exact source binding belong in the delivery receipt; live
API and original-conversation UI remain separate required acceptance.

Validated code: `ae263d4730bf8cca33050bde85b1c3de305acec0`.
[Focused hosted run38057745525](https://github.com/artinflight/vibe-kanban/actions/runs/38057745525)
passes all8 new tests, CLI build, affected-target Clippy with `-D warnings` and
Rustfmt. Hosted checkout `63d76b9134417a7439070c536c4c2e17fa570f82`
has the identical full source tree. `pnpm run format` (existing SSD-hosted
Prettier), `pnpm run ops:check`, and patch/format checks pass. Standard CI still
fails the unchanged c4 staging-ancestry gate; this is not waived. Initial
fixture failures were corrected without changing read-only or closure rules.

The sealed delivery uses the actual c3 backend and already-live cdad frontend;
ordered capture-dependencies/reader-recovery/local-cli patches apply in an
isolated index and every selected file equals tested source. Staging's checkout
and real index are untouched. The downloaded CLI hash is
`52b0b82e48f894dd743278d3cb2f84f921407ff5764a0d4c43a60dcda26c3068`.
Both actual verify-only probes exit1 on the absent authoritative JSON protocol
(the live endpoint returns HTTP200 HTML). Neither apply was attempted. See
`LOCAL_REPAIR_DELIVERY.safe.json` and
`local-repair-compiled-and-live-gate.safe.json` under the agreed SSD task root.
Matching publication, exact applies and original normal API/UI verification
remain unfinished. No recovery-complete or independent-review claim is made.

After verify-only refusal, both exact execution/session rows, session execution
inventories, raw capture and closure hashes match the before snapshot; neither
sidecar exists and normal histories still have zero entries. T18's aggregate
workspace-row hash changed during the observation interval; its cause is not
established by the aggregate baseline. Do not claim unread/review or full live
preservation acceptance. Rebaseline exact target flags/rows immediately before
future apply and verify them afterward, including UI readback without review
acknowledgement. The restoration preservation requirement remains open.
