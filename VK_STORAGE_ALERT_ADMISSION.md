# Storage alert admission (source only)

This implements the narrow native dependency of [Operations storage response](https://github.com/artinflight/Operations/issues/214).
The client requirements are published in [Operations PR215](https://github.com/artinflight/Operations/pull/215)
at `82805b71556d94e22073e5c790bb79d090f409ae`. Its retired speculative protocol
and backend patch are not used. This source starts from fork staging
`5b43524ea35b2eb5dd80d0881dc8445489f4442f`.

No monitor, timer, credential, live owner dispatch, service change, release
bundle replacement or activation is included. The production client remains
disabled until its owner reviews this exact contract and an adapter is tested
against this implementation. Source review/testing and release acceptance are
separate. Staging retains the combined release and compatible rollback.

## Native contract: storage-admission-v2

The existing authenticated/origin-checked native API carries these routes:

- `POST /api/storage-alerts/batches`: submit one batch/attempt.
- `GET /api/storage-alerts/batches/{batch_id}?intent_sha256={hash}`:
  authoritative read-only reconciliation, independent of submission enablement.
- `DELETE` of the same bound URI: explicitly cancel/fence an **unbound**
  admission. It never stops an execution. This is a mutation, not reconciliation.

POST is disabled without `VK_STORAGE_ALERT_OWNER_FILE`. That private JSON
binding must specify exactly `workspace_id`, `session_id`, the complete saved
`executor_config`, and an explicitly reviewed `max_validation_age_seconds`
(1–300). No default owner, model, effort, permissions or freshness is guessed.
Only CODEX DEFAULT with native Recommend (`routing.mode=shadow`) is accepted.
The complete configuration must still equal the latest persisted owner choice
at admission. Reconfiguration does not erase prior receipts. GET/DELETE use the
same native API authentication; they do not need submission enabled.

POST has a 64 KiB limit and rejects unknown fields. The typed JSON body is:

```json
{
  "protocol": "storage-admission-v2",
  "batch_id": "<stable UUID>",
  "attempt_id": "<fresh UUID per possible retry>",
  "intent_sha256": "<lowercase SHA256>",
  "intent": {
    "workspace_id": "<exact configured UUID>",
    "session_id": "<exact configured UUID>",
    "incidents": [{
      "incident_id": "<stable episode UUID>",
      "filesystem_uuid": "<verified filesystem identity>",
      "policy": "<immutable policy identity/version>",
      "opened_at": "<UTC RFC3339>"
    }],
    "receipt_ref": "<private producer evidence reference>",
    "prompt": "<immutable ordinary continuation prompt>",
    "executor_config_sha256": "<hash of exact saved configuration>"
  },
  "validation": {
    "observed_at": "<fresh UTC RFC3339>",
    "eligible_incident_ids": ["<each incident UUID in intent>"],
    "evidence_sha256": "<hash of fresh private producer observations>"
  }
}
```

Hashes use SHA256 of compact UTF-8 JSON, recursively sorted object keys, array
order retained, no ASCII escaping of Unicode. Hash the native typed
serialization: UUIDs lowercase/hyphenated; UTC timestamps end in `Z`, omit a
zero fractional second and use 3/6/9 fractional digits as necessary; optional
executor fields follow `ExecutorConfig` serialization (absent fields omitted).
Use a deterministic incident order and keep it unchanged. No floating-point
fields occur in the intent. Batch and attempt IDs are structured fields,
never prompt parsing. The validation envelope and attempt UUID are outside
immutable intent. The receipt binds the batch ID, exact workspace/session,
intent hash and exact native execution UUID. Native identity/configuration
validation is distinct from the producer's filesystem/pressure validation.
The native backend does not certify the producer's physical observations or
allocation accounting; their authority/freshness needs coordinated review.

## Outcomes and positive proof

A successful protocol response contains `protocol`, `outcome`, `reason`,
`no_admission`, `automatic_launch_queued` (always false), `replay`, `receipt`
and `execution_status`. A receipt includes batch, owner, intent hash, attempt,
state, reason and execution ID. Clients must validate all bindings.

| Outcome | Meaning | Client action |
| --- | --- | --- |
| `accepted` | Receipt and exact execution row committed atomically. `execution_id` is present. A replay returns the same binding with `replay=true` (already pending/handled). | Never submit again. Query execution/receipt read-only. |
| `deferred` | Bound durable proof that this attempt created no execution and no automatic queue entry. Reasons include own busy/user queue, stale observation or native admission hold. | Retry same immutable batch only with a new attempt UUID and strictly newer, still fresh validation after resolving the hold. |
| `rejected` | Bound durable proof of no admission for this intent/attempt, including scope/config drift or cancellation tombstone. Terminal for this batch. | Review/correct intent before making a new batch. |
| `uncertain` | In-flight, not found, identity conflict or otherwise no positive proof. `no_admission=false`. | Do not resend. Reconcile exact identity read-only; explicitly fence an unbound request if cancellation is appropriate. |

An accepted execution can subsequently fail before the native process starts,
fail later, or wait for normal tool approval. `accepted` means durable **execution
admission**, not remediation success or proof that a model ran. Its terminal
native status is returned when retained. Post-binding capacity/spawn/ack errors
never turn an accepted receipt into no-admission/retry authority.
A missing/deleted execution row still leaves the accepted binding intact with
`execution_status=null`; it is not proof of non-execution.

A bare 409/500, disabled route, transport timeout, malformed body, HTTP parser
rejection, empty queue, missing record or bounded history miss gives no durable
no-admission proof. Database failures may return ordinary native API errors:
reconcile, never interpret their HTTP code as resend permission. An identity
conflict returns uncertain without another intent's receipt. The caller should
also query its original immutable identity. A rejected *new* batch whose
incident is already claimed has `reason=incident_already_pending`; it must not
launch or regroup that episode. The producer retains its original stable batch
and reconciles that receipt.

## Replay, restart, cancellation and retention

Same batch + same typed intent returns an accepted/rejected/in-flight receipt
without dispatch. A deferred replay of the same attempt/validation returns its
previous receipt without dispatch; changing a used attempt's validation or
batch conflicts. A fresh deferred attempt must have a newer observation than
the latest attempt. Freshness/eligibility/config/owner/busy/queue/native gates
are checked again; no cached idle check grants admission.

A SQLite immediate transaction reserves an owner and incident IDs before
launch. Competing native execution inserts share a database fence. The normal
native execution insert atomically changes the attempt to accepted in the
same transaction; a lost response after commit is recoverable by GET. Receipts
survive process restart, history trimming, owner deletion and disabling ingress.
An abandoned pre-insert reservation remains in-flight/uncertain, never an
automatically resumed queue item.

DELETE atomically races execution insertion. If insertion won, it returns
accepted and cannot cancel or stop it. If fencing won, it commits a terminal
`cancelled_tombstone` with positive no-admission evidence and releases incident
claims; the old reserved execution UUID can never insert, including a late
handler after cancellation or after a newer attempt. The producer can retain
its local cancelled tombstone and regroup still-eligible incidents into a new
batch after this positive proof. No recovery is inferred for other incidents.
If DELETE loses its response, reconcile by GET before further submission.

No automatic expiration or receipt/attempt tombstone pruning exists. Accepted
incident claims persist indefinitely. Deferred attempts have no claims or
latent launch; rejected attempts are terminal. Retention/database replacement
requires a separately reviewed preservation policy. Never restore an older
receipt database over later writes. Not-found after restart/restore/pruning
remains uncertain. There is no history-based 'safe resend' heuristic.

## Native admission and queue integration

Owner locks cover the workspace, including sibling sessions, ordinary follow-up,
steering/queue mutation, queue consumption and native start. The lock order is
existing shared admission first, workspace second; unrelated owners retain
concurrent admission. SQLite additionally fences native execution creation
against an in-flight or running admitted storage response. Normal user input
blocked by that reservation follows its existing capacity queue path.

The incident route never appends, consumes, cancels or overwrites a user queue
or clears draft scratch. Both in-memory and durable queues and pending durable
user receipts defer admission. Normal capacity-queue consumption rechecks its
selected owner under the same lock. No general queue policy is replaced.

Launch continues the existing native thread using `ContainerService`'s normal
capacity checks, routing, persisted action/coding turn, repository preservation,
LocalContainerService resource checks and interactive approval bridge. It uses the same interrupted-turn recovery query/formatter as ordinary user
follow-up, retaining failed/killed user instructions and partial text in the
persisted native action and coding turn. Recovery augments the effective prompt;
it does not mutate the submitted intent/fingerprint or permit another launch
on accepted replay. The route does
not initialize an agent, reset Git or create/resume a native goal. Own native
unfinished goal records (including budget-limited/paused/first-run) are deferred
for explicit owner-controlled admission. Read errors also defer. Unrelated
native/scheduled goals do not veto the request. Automated input cannot exercise
foreground takeover, revoke grants or stop Nightly. Existing numeric resource
limits and approvals are neither raised nor replaced; no daily cap is added.

## Coordinated adapter source and isolated transport

The T90 owner reviewed the unchanged `storage-admission-v2` contract at native
source `45cffa379d836a553f20bb46d7c96e5953558de0` for adapter source integration.
The coordinated Operations adapter/Store/driver source is published at
`a345ca8dc1c5f50eab3afdc7db214ff3b923e7fd` in PR215. This source review does not
approve release, producer authority or activation; the production Bridge stays
disabled.

The test-only client snapshot under `crates/server/tests/fixtures/storage-alert-client`
contains six unmodified source files with exact commit/path/SHA256 provenance.
This avoids new cross-repository credentials or access on hosted runners. The
explicit hosted integration step verifies those hashes, then runs the otherwise
ignored native adapter test. Missing inputs fail rather than count as a pass.

That test starts the actual Axum admission router under `/api` on an ephemeral
loopback listener with migrated on-disk SQLite, native queue, default launch and
real approval bridge. Its fixture setup routes compile only under `cfg(test)`
and are never mounted in the product. The exact Python Store/NativeAdapter
submits real POST/GET requests. Executor I/O, OS inventory and incident samples
remain synthetic. After the initial phase the listener/pool/deployment/queue
are replaced, reopening the original WAL database; the client reconciles by GET
without a POST or new execution. The driver covers definite queue/busy deferral,
strictly fresh same-intent retry, interrupted-user continuity, lost response
after real commit, competing first deliveries, accepted replay and retained incident identity.
Independent native tests cover competing first deliveries, rejection, in-flight
fences, real capacity/goal holds, cancellation and missing receipt uncertainty.
Exact hosted results are required before claiming this integration passed.

## Validation and release requirements

Exact native commands/results and limitations are recorded in the
[validation checkpoint](STORAGE_ADMISSION_VALIDATION.md) and private integration
handoffs. Isolated tests use migrated
SQLite, native queue/default launch code and the real approval bridge; executor
I/O and OS inventory observations are synthetic. They make no paid model call
and never address a live owner.

Before activation: T90 owner review and exact adapter/backend integration;
complete fresh allocation/physical observation producer evidence; Staging's
combined forward/rollback build recognizing this migration/checksum and
retaining all receipt tables/triggers; isolated migrated-data native queue,
resource/preservation/approval acceptance; exact saved owner/config binding and
minimal existing authenticated ingress/state access; then separate explicit
release and monitor tuning/timer/automatic-response approval. Preserve existing
phone alerts throughout. Source publication is not that approval.
