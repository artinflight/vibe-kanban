# AutoSwitch updates without recurring VK restarts

Implemented in development on `feat/autoswitch-reload-module`, based on staging
`6af55a461`. Version remains 0.1.42. Recommend/Shadow remains the required live
mode; this work does not authorize Auto activation or change existing defaults.

## What can update

A versioned release contains `worker`, `instructions.txt`, `models.json` and
`manifest.json`. The worker is a stateless local classification program, not an
agent or service. It handles deterministic/reference triage, semantic-result
interpretation and soft follow-up qualification. Its code, classifier prompt and
model/effort preferences/qualifications can be replaced independently of VK.

The stable backend still derives initial bounded repository/risk evidence. The
worker receives that evidence, the current request, previous envelope and up to
3,000 characters of the immediately completed reply. No repository root, broad
conversation, credentials or environment is passed. Its narrow before/after
protocol can request the existing semantic fallback; VK performs that native
call using the release's classifier settings and prompt. Default remains
GPT-5.6 Luna/low, standard service, with the existing inference restrictions,
capacity checks, account/model/effort proof and usage accounting. The helper
itself performs zero inference.

Existing execution and controlled child/follow-up boundaries load one pinned
release snapshot. Model policy and classifier settings use that snapshot too.
Changing `current` takes effect at the next admission; an admitted request and
active turn retain their settings. Native control/resume behavior remains pinned.
Manual requests bypass the module. The default worker preserves existing V2
classification; this release enables subsequent savings corrections without
claiming those additional corrections are already implemented.

## Safety and failure handling

The worker runs through bubblewrap in new user/PID/network namespaces with only
read-only system libraries and release files, private proc/dev, no host home,
no repository mount, a read-only temporary directory and a cleared environment.
Its address space is capped at 512 MiB, CPU time at one second, elapsed response
at 750 ms and input/output at 64 KiB. Process-group/namespace cleanup terminates
obsolete helper descendants. There is no retry loop or background scheduler.

Manifest/schema/asset hashes and a sandboxed protocol probe are checked on
adoption. Immutable releases are prepared separately, then a single pointer is
atomically changed. Invalid updates retain a compatible last-good release; if
none exists, built-in safe routing remains available. Per-request worker failure
uses built-in assessment and does not retry the worker in that admission.
Failures produce warnings and decision evidence. File metadata changes invalidate
cached immutable artifacts. The backend rejects erased current risks/failure
signals, under-floor envelopes and discarded unknown/protected session history.
Reference/diagnostic releases of historical protection still require the existing
strict core guards; the surrounding assignment remains recorded.

The module cannot bypass explicit locks/floors, exclusions, inherited hard child
floors, qualification, experimental-only restrictions, availability, escalation
permission or native confirmation. Registry changes remain reviewed operator
policy, not instructions supplied by a model or task. Protected-path checks,
these hard guards, execution lifecycle and incompatible protocol changes still
require normal backend updates. Changing only soft classification code does not.

## Observability

Top-level persisted triage/raw routing logs include release version, manifest hash,
before/after elapsed milliseconds and fallback warnings. Controlled children carry
the same identity in their existing classification-source telemetry. Native IDs,
routing/execution relationships and classifier token usage stay authoritative.
The CU `vk.routing.v1` contract and shared fixture are unchanged. Replayed policy
selections are not native model execution or evidence of accepted-task savings.

## Prepare and adopt with the next restart

VK::Staging owns candidate installation, restart, cutover and live acceptance.
Development does none of those actions. The next candidate MUST include the new
backend hook, a backend-matched trusted validator and a published initial module;
merging the backend alone is insufficient. Candidate preparation must:

1. Build `cargo build --release -p executors --bin vk-routing-module` with the
   same source/toolchain as the server and the established SSD Cargo target.
2. Run `python3 scripts/vk-autoswitch-module.py prepare --root <module-root>
   --version <unique-version> --worker <built-worker>`. Optional `--models`,
   `--instructions`, `--classifier-model`, `--classifier-effort` configure a
   reviewed release. Root must be on mounted SSD, outside active worktrees.
3. Run the tool's `publish --root <module-root> --version <unique-version>`.
   It validates with the root's pinned trusted validator; update workers are
   executed only inside the sandbox. Publish a previous version to roll back.
4. Run `render --root <module-root> --output <candidate-drop-in>` and have the
   deployment owner install it in the nominated candidate. It sets
   `VK_CODEX_ROUTING_MODULE=<module-root>/current`. The module's registry takes
   precedence over legacy routing-model/classifier environment overrides.
5. Run `check --root <module-root> --unit <candidate.service>` before adoption.
   It must reject a missing setting or invalid release. After authorized cutover,
   use `check ... --live` to confirm the running process adopted that setting.
   Also verify the candidate source/hash includes this hook and inspect the first
   genuine Recommend decision for the expected release hash; environment presence
   alone does not prove an old backend invokes the module.

The tool neither installs service files nor restarts/services or changes routing
mode. Validate updated worker code against existing request fixtures before
publishing. Keep the stable validator matched to the adopted backend; do not
replace it during routine worker updates. New hard-core releases may need a new
module root/validator through normal candidate preparation.

## Focused acceptance and remaining readiness

Run the normal routing regressions plus the zero-inference namespace acceptance:
`VK_ROUTING_TEST_ROOT=<private-SSD-directory> cargo test -p executors
--test routing_module_reload -- --ignored --nocapture`.
The opt-in test is ignored in generic CI because namespace/mount prerequisites
are host-specific. It exercises a real Rust worker, different worker code and
instructions, same-process admission/model-effort changes, pinned snapshots,
last-good timeout/oversized/missing fallback, protected risk, manual/Shadow
behavior, cheap/protected children, escalation and dirty-state preservation.
Availability in this test is synthetic; it does not re-verify account execution.

Local checks passed: 55 routing tests plus the same-process real-worker acceptance,
all-target executor Clippy, formatting/governance and unchanged canonical CU
contract/fixture. The initial measured before/after stages were 33/18 ms; worker
inference usage is zero. These timings are local observations, not a production
latency guarantee. Initial prepared package and logs are under
`/mnt/vk-storage/vk-autoswitch-reload-design-20261005`; generic CI/integration
results must still be recorded before release.
Remaining live readiness: deployment-owner adoption with the module setting;
one genuine complete V2 Recommend task including delegation where eligible;
release/policy/model/native-turn/CU correlation and classifier overhead inspection;
fix observed overclassification using this update path; demonstrate useful lower
recommendations with review/validation intact. Auto needs separate authorization.
No broad historical benchmark or additional paid synthetic workload is required.

## Deadline and ownership

Full useful Model AutoSwitch must be developed and running before **October 30,
2026**, when the included allowance drops from **20x to 10x**. This is a usage
readiness deadline, not permission to lower safety or enable Auto today.
Development owns router corrections, packaging inputs and focused evidence.
VK::Staging independently owns release installation, restarts/cutovers and live
acceptance. Recommend remains required until separately authorized. Track net
accepted-task usage including classifier/initial/recovery/children, not only
cheaper recommendation counts.

CU::Credit-aware overnight agents (`0aeb028e-2856-40c3-943b-aacf32ec4808`) separately
owns bounded expiring-credit budgeting. Native apps have priority for overnight
work while live web work also progresses. This module does not implement that
budgeting or coordinate another agent.
