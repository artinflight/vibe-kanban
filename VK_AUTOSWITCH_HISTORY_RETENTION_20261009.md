# Independent inventory history correction — October 9, 2026

## Confirmed defect and narrow correction

The real post-cutover request at 21:16:44 UTC (execution
`4bb75e8a-81af-47ed-8b7d-ce74eabdd0bb`) received a native assessment of bounded,
independent, localized, established work, low ambiguity/uncertainty, short horizon,
text comparison, no risks and no safety-changing inspection. The old worker
rejected `remaining` before reading that evidence, retaining a normal/Workhorse
classification and recommending GPT-6.1 Sol/medium. The actual manually selected
Astra/xhigh remained authoritative in Recommend.

`routing_assessment::independent_request` now considers the same existing positive
semantic evidence before the `remaining` fallback. The other unresolved-reference
checks and generic approvals still run first. Without independent evidence,
`remaining` retains its conservative behavior. This deliberately does not rewrite
pronoun resolution or unrelated classifier policy. Current repository/native risk
and the core validator remain unchanged. No qualifications, preference ranks,
models, reasoning settings, capacity/credit rules, wire types or schema changes.

## Focused validation and artifact

Two executor regressions cover independent inventory/lookup after normal and
protected history, true continuation, ambiguous/unknown/context-only assessments,
inspection/high uncertainty, unresolved references, unknown historical envelopes,
current repository/native risk, failed validation and explicit Workhorse floors.
The existing opt-in same-process sandbox test now checks the inventory's cheaper
Shadow recommendation after worker publication, while continuation/ambiguity stay
protected. Existing rollback/manual/child/dirty-state checks remain in that test.
All model availability is isolated fixture data; zero paid inference is generated.

Hosted `AutoSwitch module acceptance` builds the worker and runs executor tests
plus the existing no-restart acceptance. The MCP SSD remains critically low;
no local Cargo build/test is used. Formatting/governance run without compilation.
Acceptance completed on pushed source
`be34781714e461e13ae8a9ec05e0680f72e1ce00` (fix
`b6d54101348c43f3846fa1cb48b41389ebc4190e`, followed by a reload-test assertion
correction). [Hosted CI](https://github.com/artinflight/vibe-kanban/actions/runs/37998801930)
passed 158 executor tests (seven opt-in tests not run) and the existing same-process
acceptance (one passed, PID3282, 6.64 seconds). Formatting, governance and byte-identical
CU contract/fixture checks pass. No local Cargo compilation or paid inference.
Full workspace/Tauri/frontend checks were not repeated for this worker-only fix.
The first CI run passed all 158 units but found an added test assertion compile error;
the corrected exact source above passed. Failed logs remain retained.

The update uses internal protocol2 and the deployed pinned validator. Preparation completed in a separate private root using copied current
model/instruction bytes and unchanged classifier settings. The live pinned
validator accepts the candidate in its sandbox. An initial preparation attempt
copied a read-only worker which `strip` could not modify; correcting the staging
input's permissions resolved it. No production path was touched. Development will not publish into the live module
root or alter its pointer. VK::Staging owns any later approved adoption at the next
execution boundary; ordinary compatible worker updates require no backend restart.

## Readiness and limits

Recommend remains required. A corrected recommendation is potential savings,
not observed accepted-task savings. Live ordinary requests, relevant protected
continuations and total classifier/initial/recovery/child usage still need observation
following separately authorized owner publication. October 30, 2026 (20x→10x)
remains the deadline. This task does not enable Auto or change selected models.

Evidence before the fix:
`/mnt/vk-storage/vk-autoswitch-adoption-20261009/POST_CUTOVER_ACCEPTANCE_REVIEW_20261009_215815.json`.
Task receipts:
`/mnt/vk-storage/vk-autoswitch-history-retention-20261009`.

## Immutable package and observed correction

Release `inventory-history-be3478171-20261009`:

- Worker SHA256: `699da48e4dfafd7925028b7da92e394fd124a5255ef3d6dadc10d819c8758eb0`.
- Manifest SHA256: `135dfcbd451367a9d923dfdc3d2b6a49ded9106cab260030985458f06198f18c`.
- Required unchanged live validator SHA256:
  `c0478d05803337cad53131ecd8e9c3099cd94e6310c391a7affa75c7be1cac48`.
- Archive: `/mnt/vk-storage/vk-autoswitch-history-retention-20261009/inventory-history-be3478171-20261009.zip`.
- Archive SHA256: `e2c53a4d521bf4bd2e6493f341254871f8927cfeb84ddac3b652d105b931aceb`.

The original 613-character request and its recorded native assessment were replayed
without inference, in the sandbox. The old live worker reproduced normal/Workhorse
with retained history; the candidate returns bounded/Routine with normal or protected
prior history. Continuation, unknown scope and high uncertainty variants remain
protected/Frontier. This replay preserves the actual prompt/classification but does
not reconstruct the complete original repository/runtime context. The sanitized
hosted test also selects GPT-6 Sol/low in Shadow using fixture availability. That
combination remains experimental/Shadow-only; no Auto qualification was added.

`VALIDATION.json`, `ORIGINAL_CASE_REPLAY.json`, `prepare.json`, `BUNDLE.json` and
CI logs are retained in the private task root. The archive contains the worker,
manifest, unchanged policy/instructions and sanitized provenance/validation only;
it excludes private prompts and the pinned validator. The same-process harness
publication is isolated test activity, not deployment. No live module publication
occurred. Live PID1254186 and manifest
`7370c9fb24aae06f4e3bcb8cd21c349229e2fcdc0f4f0242d597ca0618313bc4`
remained unchanged. VK version stays 0.1.42. Candidate preparation is complete;
later owner publication and normal Recommend observation are outside this task.
