# Dot Chat until explicitly revoked — prepared, not installed

Seamus requests removal of Dot Chat registration expiry entirely. This supplement
prepares that behavior and supersedes the earlier finite-renewal recommendation.
The recovered execution constraint still requires **explicit action-time user
confirmation of the exact live persistent-access expansion**. Preparation is not
that confirmation. No live module, registration, binding or service changed in
this supplement. The restored finite leases still expire 10 November 2026 at
10:00:51 UTC; the preceding agent-prompt independence fix remains live.

## Exact proposed access change

Convert the two existing, already verified Dot Chat webhook registrations from
finite leases to active-until-revoked registrations:

1. The existing VK Dev project destination.
2. The existing all-projects destination excluding exactly VK Dev, retaining
   coverage of current, archived and future projects under the existing policy.

Keep each registration's own current owner, ID, callback address, secret, filters
and active flag. Do not replace either destination, create a grant or credential,
change project coverage, or merge the two non-overlapping triggers. The change is
**duration**: delivery can continue indefinitely without renewal until explicit
unsubscribe, authorized access revocation, or the existing callback HTTP 410
revocation signal. Security boundaries still apply on every delivery.

For future normal registrations, omitted `ttlMs`, zero, and accepted legacy finite
`ttlMs` values all produce no automatic delivery expiry. Compatibility requests
cannot silently restore a deadline. No automatic promoter runs on reads/startup:
old finite rows remain finite until explicitly converted through normal signed
subscription verification. Browser authentication/pairing, session expiration,
TLS, signing-key rotation, attempt leases, retry limits and permission checks are
outside this change.

## Implementation and exact candidate

`scripts/dot-sidechat/prepare_delivery_expiry.py` prepares a complete source
candidate against five exact module hashes and retains the complete current
package. It never installs, reloads services, invokes a webhook, opens live state
or converts subscriptions. Every unrelated Python/JSON source stays byte-identical.
It returns full package hashes so another owner's later update invalidates the
prepared cutover. It must not replace a newer shared runtime blindly.

The candidate uses the existing numeric `expires=0` storage sentinel; it adds no
schema or background renewal service. Publication is a source/preparation change,
not permission to execute this candidate against live registrations.

| Module | Candidate SHA256 |
| --- | --- |
| `sidechat.py` | `2fde26d9f42e3d847f8d0cba5ee5a85b51767ece24f96f3b17ddeae9b2304bda` |
| `events.py` | `29c492914956702dab07a62dca5504044eb35e4bc0310bda166e997ccb816aef` |
| `scope_migration.py` | `4032d551cf697cf89599f7d406ce114df6c803794423d368d25f62c888994f75` |
| `scope_rollout.py` | `d508e7d8ab9d14a023a73cdb035e552ac6ba24ffb9ba41c64197bb7db69b62ff` |
| `delivery_health.py` | `77e4f9b620aef15118cff2d7901c9b85c2b6481d6c2e062f20d8a90cfbc9fc89` |

The changed methods recognize zero in publisher claims, subscription selection,
issue-linked thread binding, project-scope inventory and existing status readback.
Subscribe returns `refreshBefore: null`. Health reports `lifetime: until_revoked`,
`expires_at: null`, `renewal_due: false`, with `delivery: not_confirmed` retained.
Local registration health does not claim that the platform or owner read a message.
The private adapter, CU/reporting, Stop and issue-linked dispatch fix are unchanged.

## Tests and live verification boundary

Fifteen candidate-specific tests pass both from reproducible public fixtures and
from a generated candidate based on the exact current live source. They prove:

- One accepted delivery after a simulated 40 years, without renewal; legacy
  finite-TTL calls cannot introduce expiry.
- Reopening the store retains no-expiry state and never replays an accepted event.
- Owner/project authorization, failed callback verification, overlap rejection,
  explicit unsubscribe, scope revocation and callback HTTP 410 still fail closed.
- The two disjoint project/all-project routes cover a fixture future project once.
- Signing-key rotation retains its 300-second grace window; browser/auth and other
  source files remain identical; health works on a read-only fixture connection.
- Finite pre-existing rows are not silently promoted and exact baseline mismatch
  prevents preparation before an output is created.

All 84 public sidechat and 48 connector regression tests pass. These include the
new candidate tests plus the unchanged baseline contracts. The legacy finite
expiry contracts remain tests of the currently deployed baseline; the candidate
fixtures define the requested change. No synthetic live chat, validation agent,
owner-message fabrication, grant, authentication change or live cleanup was used.
Ops and whitespace checks pass. Required format is attempted; absent Prettier
blocks frontend formatting as in the preceding repair. No backend/frontend build
or local Cargo test is required for this prepared Python-only overlay. Hosted
exact-head CI remains separate; the prior inherited frontend source-custody
inventory mismatch is documented in the restoration record.

Live no-expiry delivery is **not yet verified**, because doing so requires the
confirmation-gated installation and registration conversion. The existing live
finite registrations and core service identities are read back unchanged after
preparation. Callback protocol support is not inferred solely from a server tools
listing; verify the actual registered status and signed callback acceptance after
activation. If the platform independently retires a callback, report that supported
revocation/platform boundary rather than recreate its credentials or invent a route.

## Proposed guarded activation, only after exact action-time confirmation

1. Recheck full live package hashes, both original registration identities and
   active flags, credentials/filters, no pending cutover by another owner, and
   publisher in-flight state. If shared source or destinations changed, reconcile
   and prepare a fresh exact candidate rather than overwrite them.
2. Take a fresh consistent state/code backup to Desktop B and verify download and
   isolated restore. Preserve every newer accepted message and queued input.
3. At a quiet publisher boundary, switch the complete preserved Python package and
   reload **only** `vibe-dot-browser.service`, `vibe-dot-sidechat-publisher.service`
   and `vibe-dot-connector.service`. These persistent Python consumers all need
   zero-expiry support. This briefly interrupts Dot Chat/connector availability;
   it does not restart Vibe, its backend, frontend, agents, CU or other services.
4. Verify service readiness and unchanged finite registrations **before** live
   conversion. If readiness fails here, return to the old code with no access
   change. The currently running services remain untouched during preparation.
5. Through the existing normal signed `Events.subscribe` verification, convert
   each of the two exact original destinations using its current address, secret
   and filters. Require the same returned IDs and `refreshBefore: null`; synchronize
   existing authorized thread bindings to zero deadlines without replaying events.
6. Read back both active registrations and bindings with no expiry, unchanged
   credentials/scope/history, cached MCP health, unchanged non-Dot services and
   the original request receipt. Verify real retained/new owner-message delivery
   through the signed callback, using the existing event identity. No synthetic
   agent launch or duplicate request. An absence of a new real event must be
   reported as pending acceptance, not invented proof.

After any conversion, do not restore a finite-only runtime or old SQLite over
new writes: that would hide zero-deadline registrations and lose current history.
If one callback verification fails, keep the successfully converted destination
and the compatible runtime, preserve the other finite destination, report the
partial result and reconcile safely. Do not revoke working access or silently
replace destinations as rollback. Future updates must retain zero-expiry support.

The exact confirmation requested is: **apply this no-expiry policy to the two
existing Dot Chat registrations and future normal registrations, with unchanged
scope/credentials, and perform the three Dot-only service reloads above**. This
request exists because the user's recovered execution constraint requires
confirmation at action time for persistent-access expansion; it is not a new
broad restart-approval rule.

Private candidate, exact baseline and review receipt are retained under
`/mnt/vk-storage/dot-no-expiry-20261103/`. Public source and this proposal are
preserved in [PR #289](https://github.com/artinflight/vibe-kanban/pull/289).
