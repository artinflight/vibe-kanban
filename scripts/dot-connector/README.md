# Explicit Dot steering

This overlay adds `steer_session_prompt` and `get_session_steering_receipt` to
the current connector. Existing `run_session_prompt` and queue semantics stay
unchanged, including the ca3fe817 capacity-queued response correction.

The write tool requires explicit `session_id`, `execution_id`, `request_id` and
`prompt`. Select the running execution from the existing status tools. Generate
one request UUID for one correction and retain it. A receipt with
`status=steered, delivered=true` confirms native admission, not completion of the
requested work. Known rejection has `delivered=false`. Uncertain delivery has
`status=unknown, delivered=null`: inspect that request's receipt and never resend
with a new ID. A repeated matching request reads its receipt without another
POST. Reusing an ID for different text or identity is rejected.

The connector first reads the receipt, then the backend's exact native
thread/turn binding. The backend reserves the request durably before dispatch,
checks ownership/executor/running state and scheduled-work restrictions, and
sends at most one native `turn/steer` with `expectedTurnId`. Missing/replaced
targets and unavailable native clients cannot launch, interrupt or queue a turn.
Native failures, lost responses and interrupted handlers remain uncertain.
Existing queued prompts and current model/effort/permission/routing are untouched.

## Validation

```sh
python3 -B -m unittest discover -s scripts/dot-connector -p 'test_*.py' -v
python3 -B scripts/dot-connector/verify_current_connector.py \
  --source /home/mcp/code/vibe-dot-connector
```

The second command reads current application source and runs its five
capacity-queue and nine Recommend-policy tests against the patched candidate.
It performs no network calls or live file writes. It also verifies discovery,
dispatch and continued rejection of unsupported tools.

Rust fixtures cover durable concurrent duplicate admission, cancellation/error
uncertainty, changed request identities, exact session/executor/running state,
and native turn binding. The isolated-session HTTP fixture runs this Python
handler through the real Rust router and receipt database to a synthetic native
Codex peer; it checks one POST, receipt readback, no extra execution/launch/stop,
and an unchanged pre-existing queue. This is protocol-fixture acceptance, not a
real paid model's behavioral response.

The ignored compiled test
`explicit_steering_real_isolated_native_session` is the separate account-backed
acceptance path. It requires `VK_DOT_STEERING_REAL=1`, a fresh dedicated
`CODEX_HOME` under `/mnt/vk-storage/vk-dot-steering/`, and the exact native binary
in `VK_DOT_STEERING_NATIVE_BIN`. Run it only from a manifest-verified matching
executor test artifact. It starts one read-only/on-request thread, sends one
correction, and verifies the final marker in the same sole native turn. It must
never point at a production home or existing user thread. Native account material
stays private in the dedicated home; no account data belongs in source/artifacts.
The focused `Dot steering acceptance artifact` workflow exports this test binary
with exact commit/tree, all tracked source hashes and binary SHA256. It does not
start a backend or access a native account; normal backend/release checks remain
separate. The harness waits for `turn/started` readiness after `turn/start`, since
the response can arrive before that notification. It never retries a correction.

## Deployment requirements

1. Coordinate the adapter baseline with connector task
   `01a1410f-a73a-70fb-aadc-bd78346060d1`. Do not edit its checkout or overwrite
   live files while that owner may be editing. The implementation lives here as
   an independent reviewed overlay; no live installation is performed.
2. Build and validate the matching backend with migration
   `20261015220000_session_steering_receipts.sql` and its three routes:
   `GET /api/sessions/{id}/steer/target?execution_id=...`,
   `POST /api/sessions/{id}/steer`, and
   `GET /api/sessions/{id}/steer/{request_id}`. No frontend change is needed.
   Follow the established VK backup, compatible rollback, preservation, idle
   admission and separately authorized restart procedure. Do not deploy a public
   artifact over private retained-reader behavior.
3. Under the connector owner's reviewed baseline, prepare a fresh non-live output
   directory with `prepare_connector.py --adapter PATH --expected-sha256 HASH
   --output NEW_DIRECTORY`. The helper checks the exact baseline hash, capacity
   fix and integration anchors; it only writes a candidate adapter and steering
   module. Recheck the actual installed adapter immediately before adoption.
   Any changed hash requires reconciliation rather than force-applying the patch.
4. Preserve the existing connector dependencies, key/tunnel settings, all
   unrelated tools and current queue fix. Adopt only reviewed `adapter.py` and
   `steering.py` as a coordinated connector release, then reload that connector
   alone and refresh cached Dot tool discovery. These steps are release
   requirements, not actions performed by the preparation helper.
5. Confirm the new backend endpoints before using the tool. An old backend
   returns an unsupported/unavailable error; the connector never falls back to
   `/queue` or `/follow-up`. Complete a bounded disposable real-model session
   acceptance after deployment, without targeting unrelated live agents.

Rollback the connector overlay independently if necessary; the old connector
continues using existing APIs. Retain steering receipts across rollback so an
uncertain correction cannot be replayed. An older backend must never be used to
reconstruct delivery from absence of a native reply. No cleanup or access-policy
change is part of this feature.
