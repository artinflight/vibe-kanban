# Reusable watcher events: source package and integration checklist

Status: **migrated VK Dev source; native adoption and live acceptance blocked**.
Maintained in VK Dev and the Vibe repository, alongside the existing PR277 backend owner.
Disk Space remains the existing cleanup owner.
The October 27 module is not installed. The existing Disk observation/ntfy path
remains installed with both native activation flags false. Never equate the
injected receipt tests below with actual agent execution.

The one delivery chain is:

`existing watcher -> local registry conditions -> PR215 durable Store.dispatch -> NativeAdapter -> PR277 native admission -> existing configured session`

`watch_events.py` generalizes input/conditions/report construction and reuses
`monitor.Store.dispatch`, the SQLite receipt ledger, `native_adapter.py` and
`native_http.LocalNativeHTTP`. It adds no alternate follow-up call, scheduler,
HTTP listener, executor, credential acquisition or browser path. An existing
watcher/timer invokes it. A remote system may stream its saved event over an
already-authorized SSH connection; this package does not create that connection,
install a key or grant a remote account new permissions.

## Native integration and ownership

The module is developed in VK Dev and `artinflight/vibe-kanban` on
`vk/ab88-op-disk-space-wa`, targeting the existing Vibe `staging` branch.
PR277 head `8534a6a655e03e4903e4e517cfea21c3b91c4636` is preserved by merge
ancestry, alongside the migrated Operations PR215/PR217 client. The old
`native-overlay` files are retained migration provenance, not a patch to apply
again. The current implementation is the Vibe route and shared native services.
The original backend owner's branch and all workspace/session history survive.
This workspace now owns completing integration and tests; Staging owns release.
Disk remains the single existing cleanup owner.

The wire protocol remains `storage-admission-v2`, POST
`/api/storage-alerts/batches`, GET exact batch with `intent_sha256`. No second
route, executor or dispatcher is added. Raw JSON is required; an HTTP200 HTML
frontend fallback is not an admission API. Acceptance binds batch, intent hash,
known attempt, existing workspace/session, saved config hash and exact native
execution UUID. Accepted means execution creation committed, not cleanup success.
Lost or ambiguous replies reconcile GET only. Wire protocol v2 alone does not
prove the modular registry or job-lifetime fence is installed: bind the exact
reviewed source/artifact and both migration checksums before enabling delivery.
An unextended PR277 v2 binary is insufficient. The existing gateway access review
and exact saved CODEX DEFAULT Recommend configuration remain required.

Two migrations must be included in forward and compatible latest-data recovery:
`20261018140000_storage_alert_admission.sql` (original SHA256
`791b0b526641d0633ff81a6afdd154285e0ef2d50f86a7905616f96c8721cc41`) and
`20261027153000_watcher_job_leases.sql`. Never modify an adopted checksum or drop
receipts, attempts, incidents or unresolved job leases to pass recovery.

Controlled independent jobs acquire a durable lease before inference under the
same workspace lock and SQLite write transaction as native alert admission.
Parent exit, timeout, cancellation request, future Drop and process restart do
not release a lease. Only confirmed child terminal status or definite refusal
before inference closes it. Stale producers cannot gain authority after parent
exit or another watcher reservation. The 4096 retained-lease quota per workspace (65536 total)
fails closed; it never deletes history to recover capacity. Unrelated workspaces
remain concurrent. These source paths require compiled race/termination/reopen
acceptance before use.

Native POST additionally requires root capture closure, no still-registered
native root client, complete readable Codex descendant state, no unresolved job,
and closed legacy controlled-delegation journals. A completed task on an open
native child edge remains a producer and holds dispatch. Bind
`delegation_journal_dir` to the existing producer's actual directory; when
`VK_CODEX_ROUTING_AVAILABILITY` is set, its adjacent `delegation` directory must
match canonically. Missing custody, corrupt/oversized journals and unconfirmed
interruption hold. Legacy single-owner files still parse; an omitted journal
path holds new dispatch until that existing custody is supplied and reviewed.
The route reads these files without modifying them or gaining new access.
Unmanaged external jobs require their existing authoritative owner/process
inventory; snapshots alone cannot certify an unknown producer as idle.

## One initial backend release, then file configuration

Before initial deployment, Staging must include the integrated PR277/module,
multi-owner registry and job-lease/producer checks with compiled proof in the same source-bound
forward and compatible recovery package. Set a stable
`VK_STORAGE_ALERT_OWNER_FILE` path at that initial release. Changing an environment
variable later would require a restart; changing the file contents does not.

The native owner file has this additive schema (complete saved config, not a
new model selection):

```json
{"version":1,"owners":[
  {"workspace_id":"EXISTING_UUID","session_id":"EXISTING_UUID",
   "executor_config":{"...":"complete exact saved ExecutorConfig"},
   "max_validation_age_seconds":60,
   "delegation_journal_dir":"/private/existing-producer/delegation"}
]}
```

The parser accepts at most16 unique workspace/session pairs and64KiB; duplicate,
unknown-version, missing or malformed selection fails closed. Native submit
still checks the current saved ExecutorConfig and its canonical SHA256, existing
continuation, admission/resource/goal/approval gates and all receipt bindings.
This is a local target allowlist, **not authentication**. The existing gateway
is not proven authenticated direct ingress; its original access-boundary review
is still required. Do not expose the route, add credentials, forge relay headers
or use a browser workaround. A denied request stops that action.

Copy `watchers.example.json` to an approved mounted private state directory,
make it0600 with a0700 parent and replace all example mount/DB/owner-root/hash
values with actual readbacks. Keep activation and target `enabled` false until
native/access/lifetime acceptance is complete. The source code is stdlib Python;
use the same installed seven PR215 modules plus the new `watch_events.py`, and
updated `monitor.py`/`t26_watch.py` together after source review. There is no new
package installation or billing.

Validate a saved registry without network or state writes:

```sh
python3 -B /approved/module/watch_events.py --registry /approved/private/watchers.json --check
```

The JSON schema is intentionally small and fully validated in `Registry`:

| Object | Configurable fields |
| --- | --- |
| source | stable name, enabled, driver (`events-v1` or reserved `disk-existing-v1`), maximum event age1..300s |
| target | existing workspace/session, exact ExecutorConfig SHA256, freshness1..300s, cooldown60..86400s, read-only Vibe DB, owned process roots, enabled |
| rule | source, target, exact resource or `*`, trigger/recovery conditions, recovery count1..10, minimum sample interval and maximum gap, locally authorized instruction |
| condition | scalar field plus `lt`, `le`, `gt`, `ge` (finite numeric values) or type-exact `eq` |

No expressions, shell commands, remote URLs, credentials or instructions supplied
by an event can select a target or execute configuration. Trigger and recovery
must not both match a sample. A dead band preserves the incident and does not
wake it. All source strings/reports are quoted untrusted data in the owner prompt;
local instructions preserve existing authority and approvals.

Update the registry using a same-directory0600 temporary file and atomic rename;
validate it first. Add a new native owner binding before enabling its client
rule. Existing native owner bindings and the client registry are both reread on
submissions/invocations, so source, condition and target edits require no new
Vibe restart. Disable submission while changing an existing target's saved
executor config. Unknown/accepted/pending work must resolve under its original
binding first; do not reassign its target alias. Ingestion also checks retained
ledgers across targets: moving an open rule to a different target or source
cannot evade its old pending/uncertain receipt. Once recovered and settled, a
retargeted rule requires a strictly newer source observation; replaying an old
event cannot create work in the new target. Receipt-only drains remain available. GET reconciliation retains its
original immutable intent binding. A changed open rule fails closed; recover
under its original contract before editing it, or add a distinct rule ID while
retaining the old contract. Never discard unresolved receipts to force a change.

## Event producer contract and cross-system input

The stdin read is capped at64KiB; a validated event is at most16KiB so its
report fits the native prompt/body limits. Source identity is supplied
by the locally authorized invocation, must equal the envelope and must be enabled
in the registry. This is routing validation, not a new per-source security
boundary between processes sharing the existing account. A source must have
existing authorized command access; otherwise stop for that specific access
approval. No new listener, SSH account, authorized key or permission is installed.

```json
{"version":1,"source":"printer-status",
 "event_id":"00000000-0000-4000-8000-000000000101",
 "resource":"mk4","sequence":1,"observed_at":1793100000,
 "values":{"state":"error"},"report":"Read-only printer status changed."}
```

The example timestamp is historical: producers send their actual current UTC
Unix seconds. Keep source clocks synchronized through their existing setup.
Persist the exact event ID/payload in the producer's bounded outbox before send,
and increment a durable sequence for every observation, including unavailable
samples. Sequences are per source/resource, strictly increasing and persistent
across producer restarts. Retries reuse the identical event. Do not reset a
sequence or invent fresh IDs to retry an uncertain delivery. Deliver outbox
entries in order; retain an unacknowledged entry on nonzero exit or unknown SSH
outcome. Skip sequences reset recovery counts. Unavailable readings do not count
as recovery. A missing/old event never becomes fresh merely by retrying delivery.

Local invocation, or the same command reached through the **existing authorized
SSH host alias**, consumes the saved payload without shell-interpolating it:

```sh
python3 -B /approved/module/watch_events.py --registry /approved/private/watchers.json --source printer-status < saved-event.json
```

Success means the event observation was durably received, not that a coding turn
or cleanup completed. The JSON outcome says whether native admission is held,
accepted, unknown, etc. Reinvoke without `--source` from the existing watcher or
its existing timer to reconcile pending receipts/backoff:

```sh
python3 -B /approved/module/watch_events.py --registry /approved/private/watchers.json --quiet
```

There is no new timer here. Do not claim automatic retry until the existing
watcher's periodic invocation and producer outbox retention have been verified.
The unrelated printer connection is a safe status-only acceptance example;
none of its real watchers, timers or printer controls were changed this turn.

## Disk is the first driver, with its existing state

Disk continues through the existing `resource-guard.timer` ExecStartPost and
`t26_watch.py`, its **same** `incidents.sqlite`, exact mount checks, ntfy receipts,
measured growth report, existing owner and original incident UUID. It must never
be fed into a second generic event ledger. `disk-existing-v1` is reserved and
rejects generic stdin ingestion.

After native prerequisites, add this optional field to the existing Disk config:

```json
"event_registry":{"path":"/approved/private/watchers.json","target":"disk-space"}
```

The runner reads that registry each tick. The adapter preserves both existing
false flags using restrictive AND, retains the state file and compares the
registry target with the separately reviewed existing-owner binding in the
private Disk configuration. Public source contains no deployment-owner UUID or
implicit target default; the native saved-owner binding remains authoritative. It validates strict root available<10,000,000,000B
and SSD available<25,000,000,000B, recovery>=12,000,000,000B/27,000,000,000B for3
valid samples60..150s apart, and1800s cooldown. These warning/cleanup-dispatch
thresholds do not change build or safety admission. It retains exact bytes,
decimal GB, mount/device/UUID/maj:min and measured growth. Only confirmed low ntfy
receipts can wake; recovery cannot. Coding turns, independent jobs or owned
processes cover the current incident without a later wake after they finish;
queues and unknown inventories retain pending delivery. Cleanup stays with
workspace `PRIVATE_CONFIGURED_ID` / session
`PRIVATE_CONFIGURED_ID` and its existing per-action rules.

## Durability and bounds

Every target uses the same Store commit-before-POST, immutable batch/intent,
known attempt list, strict native receipt decoder and lookup reconciliation.
Accepted work never resubmits; uncertain/lost/HTML/error/not-found responses hold
and GET only. A positive native capacity/queue no-admission deferral can retry the same batch
with a new attempt only after strictly newer, still eligible observations.
A confirmed native `owner_busy` or active independent-job receipt covers that
incident episode; it does not wake again when the owner later becomes idle.
Unknown/unsettled lifetime evidence keeps delivery pending.
A durable in-flight reservation without execution binding is
`owner_admission_unsettled`, not proof of activity. Controlled child activity is
positive only after a real native thread/turn acknowledgment has been journaled
and while its lease object is still owned by the producer. Drop or backend restart
clears that live projection but retains the durable exclusion. Unsettled leases
are never cleared from history/status guesses; original-owner authoritative
terminal or definite no-execution evidence is required for reviewed recovery.
A config edit or execution failure cannot create a fresh incident to evade that.

The generic runner takes one nonblocking flock for its private state root.
Fresh source data is rechecked after owner inventory, immediately before the
shared dispatcher; source TTL never refreshes on drain. At most8 incidents and a24KiB source/instruction budget enter
one native batch, keeping the native32KiB prompt/64KiB body limits. Pending delivery survives process restart. Backoff is60..3600s;
per-target accepted cooldown survives lost scheduler metadata by reading the
persisted receipt. Clock regression normalizes those waits once. No own log
files are created; `--quiet` suppresses routine and error output, and exit status
still signals failure to the existing caller.

Limits are32 sources,64 rules,16 configured targets and **16 lifetime target DB
files**,128 resource/rule states per DB,64KiB input/config, bounded scalar/string
fields,1000 audit entries and8MiB SQLite pages per DB (plus bounded rollback
journal). Tombstones are retained; reaching a quota holds rather than deleting
uncertain receipts. Repeated source/target renames cannot silently grow unlimited
state. Do not install this on the OS disk or delete existing state to regain
quota. A planned retention/migration needs explicit receipt-preservation review.

## Merge readiness and Staging release acceptance

1. **Source and release identity:** adopt PR277 plus the reviewed multi-owner
   delta and actual independent-job fix. Bind exact client/module hashes and the
   current decimal policies. Run the new Rust parser tests in native CI and the
   current Python/native paired fixture. The old PR215/native hosted pairing is
   historical supporting evidence. Reseal the current combined source/artifact,
   both migration catalogues and compatible latest-data recovery; do not overlay old
   binaries or drop current Staging work. No new generic approval is implied
   where Staging already holds conditional release authority.
2. **One initial deployment:** release owner performs the authorized initial
   backend release, checks its executable hash/PID/start time, migration checksum,
   reviewed owner bindings/access/freshness and actual JSON GET semantics. HTML
   with HTTP200 is a failure. Preserve all active jobs and user execution lanes.
3. **Both Disk conditions:** safe injected source readings in the actual isolated
   native fixture prove equality does not trip, each strict threshold creates
   one incident/report, both low volumes coalesce, exact bytes/mount identities
   appear, and only the existing Disk session is selected. Retain the real
   initial SSD incident rather than reposting it. For live dispatch proof obtain
   actual receipt->execution binding and the owner's readback, within its existing
   authority. Never fake host disk pressure or remove real data for a test.
4. **No overlap or duplicate:** simultaneous duplicate events, two independent
   producers, lost POST acknowledgement, client death before scheduler metadata,
   client reopen and native reopen give at most one execution per incident.
   Assert native receipt/hash/known attempt/owner/execution identities, not just
   a fixture's outcome string. Unknown/not-found may not authorize resend.
5. **Jobs and queues:** coding turn active covers the episode; a real independent
   same-owner job active after its parent turn ends also excludes launch. Inject
   job arrival between preflight and native reservation in **both race orders**;
   authoritative ownership must persist through job lifetime, error/restart and
   cancellation uncertainty. Test memory queues plus durable received/user queues
   arriving during admission. Unrelated owners remain concurrent. Unknown status
   holds. A cached idle snapshot or inventory read alone is not proof.
6. **Recovery/hysteresis:** notification recovery never wakes;3 properly spaced
   recoveries rearm; duplicate samples, gaps, failed observations, replayed/future
   timestamps and clock regression do not accelerate recovery. Stable continued
   low space creates no new incident; rearm plus cooldown permits one later one.
7. **Second unrelated connection without restart:** after the initial backend
   release record backend executable hash, PID and process start ticks. Through
   atomic config replacements add `printer-status` and its existing status-only
   owner (or another already-authorized existing unrelated target), exact saved
   config and local instruction. Send one saved safe event, read the actual
   native receipt and execution, obtain the owner's readback, repeat the event,
   then send recovery. Prove exactly one execution, no recovery wake, correct
   target and unchanged backend PID/start ticks/hash. Verify a rule edit under
   the documented open-incident contract without a restart. A synthetic fixture
   receipt or unchanged Python PID is not this live proof.
8. **Installed readback and documentation:** verify actual module bytes/registry
   revision, current timer/producer invocation, pending state/backoff/log bounds,
   real mount readings and exact live receipts for both connections. Record
   forward/new writes/latest-data cutback preservation. Only then enable the
   existing Disk flags and mark the modular goal complete.
