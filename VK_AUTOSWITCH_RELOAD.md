# AutoSwitch updates without recurring VK restarts

## October 7 correction: a real policy boundary

The first reload module was incomplete. VK first classified the prompt itself
and treated that fallback guess as immutable protection. It also repeated the
module's follow-up classification rules in its fixed validator. Consequently,
changing module code could not fix those decisions. The earlier reload test
proved only updates which agreed with the backend's duplicate rules; it did not
prove the failure cases from actual work. That delivery did not meet the
operator's instruction.

Internal protocol **2** corrects this boundary. The selected worker now owns
prompt interpretation, deterministic/reference triage, semantic eligibility,
semantic-result interpretation and inferred historical qualification. The backend
passes its built-in assessment as a fallback, not a floor. The worker recomputes
fresh prompt classification before semantic assessment. Previously manual work
without stored qualification is inferred through the same pinned module, with
native inference disabled, rather than a separate backend keyword classifier.

VK separately reads bounded repository facts. Those facts, reported current/native
risk, input-budget completeness, explicit manual/child floors, exclusions, observed failure, lifecycle safety
and model/effort execution proof remain enforced by the backend. Its history guard
checks uncertainty and native scope provenance; it does not repeat the worker's
phrase interpretation or follow-up policy. Unknown prior qualification, observed
failure and unresolved native continuation cannot be erased. A same-assignment
bounded step requires completed context and a recorded surrounding assignment.
Deterministic history release requires known validation, no unresolved
safety-changing inspection, and cannot claim semantic evidence without native
input. Generic resumes remain conservative in the default worker.

This is a reviewed policy update mechanism, not permission for task instructions
or a semantic model to rewrite safety policy. Adoption runs protected-intent
contract probes for authentication, destructive migration and concurrency, then
checks retention of the resulting current risks. A worker that labels every task
cheap is rejected. These are bounded adoption checks, not another runtime
classifier or model call. Current repository/native facts remain authoritative
regardless of a worker's language interpretation.

## Reloadable contents and safe boundaries

An immutable release contains `worker`, `instructions.txt`, `models.json` and
`manifest.json`. The worker is a stateless local program, not an agent or service.
Code, classifier prompt/model/effort and model preference/qualification policy can
change independently of the backend. Default semantic classifier remains
GPT-5.6 Luna/low, standard service, with existing inference restrictions, capacity
checks, account/model/effort proof and usage attribution. The helper itself uses
zero model inference. There is no new retry loop, scheduler or tool loop.

One module snapshot is pinned for each top-level or controlled child admission.
Changing `current` affects the next execution/follow-up boundary; admitted work
and active turns keep their settings. Manual requests bypass routing. Recommend
shows a recommendation but preserves the actual selected model. Auto remains
unauthorized for live use.

The helper receives at most 6,144 prompt characters, 3,000 characters of the last
completed reply, previous envelope, policy, bounded repository observations and,
when available, the captured native semantic result. It receives no repository
root, broad conversation, credentials or host environment. Repository inspection
uses the existing 768-entry/eight-file/40-ms budget, conventional UI roots and
no source symlinks. Requests exceeding the visible prompt bound retain protection
rather than silently hiding late requirements. Facts can identify protected component references even when
a request contains harmless operational cautions.

## Failure isolation and observability

Bubblewrap isolates each helper with new user/PID/network namespaces, read-only
system libraries/release files, private proc/dev, no host home or repository,
a cleared environment and read-only temporary storage. Bounds remain 512 MiB
address space, one second CPU, 750 ms response and 64 KiB input/output.
Namespace/process-group termination prevents lingering helper descendants.

Manifest, protocol, hashes, model settings and sandboxed contract checks run on
adoption. Rejected updates retain a compatible last-good release. Without one,
built-in routing is used visibly. A per-request helper failure falls back without
retrying. Module version/hash, timings and warnings persist in triage/raw routing
logs; controlled children carry the same classification-source identity. Native
IDs and classifier usage remain authoritative. CU `vk.routing.v1` and its shared
fixture are unchanged; internal module protocol 2 is separate from that wire
contract. No public API/type/schema migration is introduced.

## Required owner adoption and later updates

The current October 5 live backend contains the old vetoes. Publishing a new
worker alone cannot remove those checks. **One backend-owner adoption of protocol
2, its matching validator and initial worker is required.** Do not pass this
package through the old protocol-1 validator or present it as live. The older
`current-step-665d836db-20261007` package is superseded, preserved for evidence.
Development does not install service settings, restart VK, cut over, enable Auto
or contact a staging/deployment agent. VK::Staging owns that adoption.

Prepare a separate root outside worktrees on mounted SSD, with the worker and
validator built from the same source as the candidate server:

1. Build `cargo build --release -p executors --bin vk-routing-module` using the
   shared SSD target and disabled incremental compilation.
2. Run `python3 scripts/vk-autoswitch-module.py prepare --root <new-root>
   --version <unique-version> --worker <built-worker>`. The tool reads protocol
   from the root's pinned backend-matched validator. Optional policy/instructions
   and classifier settings are reviewed inputs.
3. Run `publish --root <new-root> --version <unique-version>` to atomically select
   a verified release, then `render --root <new-root> --output <candidate-drop-in>`.
   The owner adopts `VK_CODEX_ROUTING_MODULE=<new-root>/current` with the candidate.
4. Run `check --root <new-root> --unit <candidate.service>` before adoption and
   `check ... --live` after owner cutover. Confirm exact source/protocol and a
   genuine Recommend decision's release hash; a setting alone proves neither.

After that adoption, ordinary prompt/classification/history-policy corrections
use `prepare` and `publish` in that same root. They do **not** require a backend
restart. Publishing a previous verified version rolls back at the same boundary.
Keep the validator pinned; do not replace it during ordinary policy updates.
Changes to execution lifecycle, hard native/repository enforcement or incompatible
protocols still require normal backend adoption.

## Focused proof and limits

The opt-in local acceptance uses one running process, real sandboxed Rust worker
code and an isolated root. It first reproduces the old negative-deployment and
protected-history biases in a worker, then publishes the corrected worker into
that same process. It tests actual admission/model selection, pinned in-flight
policy, manual/Recommend behavior, exclusions, child floors/escalation, rollback,
invalid/timeout/oversized/missing/unsafe updates and dirty-state preservation.

Run `VK_ROUTING_TEST_ROOT=<private-SSD-directory> cargo test -p executors
--test routing_module_reload -- --ignored --nocapture`. With
`VK_ROUTING_REPLAY_FILE=<private-captured-file>`, the same process also reuses
completed real native assessments through the actual sandbox and core validator.
No native execution or paid inference is generated. Availability fixtures and
historical observation-time selection are not current executable-model evidence
or accepted-task savings. `verify_active_case` is an offline diagnostic of the
pinned helper/validator, not a service endpoint or alternative execution path.

Current evidence is under
`/mnt/vk-storage/vk-autoswitch-module-boundary-20261007`; HANDOFF records the
completed checks, exact source/package and delivery status. Version is 0.1.42.

## October 30 readiness

Useful AutoSwitch must be running before **October 30, 2026**, when the included
allowance falls from **20x to 10x**. Remaining dependencies are passing release CI,
owner adoption once, genuine Recommend decisions proving cheaper resolved work
without lost risk protection, and accepted-task quality/net-usage evidence.
Subsequent policy corrections should use this proven reload path. Recommend stays
required until separate Auto authorization. No broad benchmark or paid synthetic
workload is needed. Count classifier, initial/recovery and children in total cost.
CU's expiring-credit budgeting remains its separate issue; this module does not
change credit settings or claim subscription cost from API prices.
