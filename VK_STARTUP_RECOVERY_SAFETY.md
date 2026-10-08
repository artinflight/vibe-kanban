# October 8 startup and recovery-verification repair

## Scope and authority

This branch starts at fork staging `8b562265d25a3f8ee6d4fa602144e71caddfbc85`.
It is separate from the clean `vk/4e18-vk-staging-check` maintenance workspace,
PR149 recovery tools, PR150 candidate, and PR152 incident review. Nothing is
merged or deployed by this repair. Deployment, restart, route changes and cutover
remain outside its authority. The source continuity packet remains at
`/home/mcp/code/worktrees/4e18-vk-staging-check/_vibe_kanban_repo/VK_STAGING_CONTINUITY_PACKET_20261008.md`.

On October 7 an unsupported `--vk-build-info` invocation reached ordinary server
startup, opened the legacy database, and deleted shared worktrees through orphan
cleanup. Authenticated Desktop-backed recovery placed missing baseline paths
without replacing surviving work. That did not establish preservation of all
post-backup edits. The consumed placement/cleanup programs are not dependencies
of this repair and must not be replayed.

## Prevention contract

The standalone server accepts exactly zero arguments for startup, or one of
`--help`/`-h`, `--version`/`-V`, and `--build-info` for read-only inspection.
Unknown arguments, positional arguments, non-UTF8 arguments and trailing arguments
fail before telemetry, directory creation, database access or deployment creation.
Inspection returns before runtime identity validation and starts no server.

`--build-info` reports this branch's version, optional build-source commit,
identity protocol and absence of automatic workspace deletion. It does not
invent capacity-ledger compatibility. Staging has no `--capacity-build-info`
handler; integration into PR150 must retain that candidate's actual capacity
metadata behind the same strict whole-invocation gate. Never use a null source
commit as proof of artifact provenance.

Ordinary startup requires `VK_RUNTIME_IDENTITY_FILE`. The six-line Unix receipt
pins both the canonical selected database path/device/inode and the configured
workspace root path/device/inode. It also binds an intrinsic dataset ID checked through a read-only SQLite connection before any migration or writer opens. Its format is:

```text
vk-runtime-identity-v1
database=/absolute/canonical/path/db.v2.sqlite
database_id=device:inode
workspace_root=/absolute/canonical/workspaces
workspace_root_id=device:inode
dataset_id=32-lowercase-hex-digits
```

The receipt is explicit, reviewed deployment input. Startup never discovers,
creates or repairs it. The selected database and root must already exist, the
receipt must be a small regular file, and the database must have a SQLite header plus exactly one matching intrinsic dataset token.
Missing/empty receipts, relative runtime paths, empty/non-SQLite databases,
path substitutions, changed filesystem identities, missing/empty identity tables, and in-place replacement with another dataset token fail closed. Configuration
migration must preserve the selected workspace root. Validation also occurs at
the reusable server initializer and directly at LocalDeployment construction,
before log migration or configuration writes. Asset-path resolution now has a
side-effect-free function.

`scripts/vk_runtime_identity.py` reads explicitly supplied paths and their
existing dataset token, then emits this receipt to stdout. It is not proof that the caller selected the authoritative
dataset, a recovery audit, or permission to enroll production. A later reviewed
controller must obtain provenance first and bind a new receipt to its actual
runtime paths. Database replacement/restoration requires a newly reviewed
receipt; routine SQLite writes preserve its inode and intrinsic dataset token. No receipt for production was
created during this task.

This is a deliberate startup compatibility change: implicit first-run database
creation and old-database copying cannot pass the gate. Development/private
instances need a seeded private SQLite database and namespace. Their explicit
bootstrap must provision a `vk_runtime_identity` table with a singleton row:
`singleton INTEGER PRIMARY KEY CHECK (singleton = 1)` and
`dataset_id TEXT NOT NULL UNIQUE`, with one new random UUID expressed as32 hex
digits for that distinct dataset. Bootstrap is a separate reviewed action;
startup and the receipt producer never provision it. Identity v1 uses
Unix filesystem identity; other platforms fail closed and require a separately
reviewed identity implementation before adopting this repair.

Automatic workspace deletion is removed rather than granting ownership from a
row's absence, database size, an environment-only path override or file age.
Startup/periodic expired-workspace deletion and requested-cleanup reconciliation
are no longer spawned. Status-triggered cleanup returns disabled, including its
post-execution retry. Existing requests/records are retained. Orphan inspection
reports only the configured root, skips linked directory entries, and preserves
untracked paths. Explicit user-requested deletion remains a separate API action;
this repair does not add automatic legacy workspace enrollment or cleanup.

The retention change means archived/expired workspaces can consume storage until
an explicit reviewed deletion. Reintroducing automatic cleanup requires positive
per-workspace ownership evidence and tests, not removal of this gate.

## Recovery verification contract

`scripts/verify_recovered_tree.py` is a read-only verifier with no extraction,
placement, deletion, executable launch or incident-script imports. Its manifest
SHA-256 must match an independently retained expected hash. It verifies file
content, type and mode; directory type/mode; literal symlink targets without
following them; and hardlink inode relationships plus content/mode. It rejects
parent links, unsafe paths, duplicate paths and empty manifests. A changed file,
unsupported type or missing metadata cannot become a passing audit. It detects
changes during hashing and avoids blocking on substituted FIFOs.

The manifest contains `version: 1`, `entries`, optional `observed_names`, and
`journal_coverage` with capture-start `instance`, `scope_sha256` and
`sequence_start`. Journal readiness, instance, scope, monotonic sequence and
absence of errors are necessary for coverage. Name existence alone never proves
content preservation. Even complete name-event coverage does not retain the
previous bytes of edited files, so the verifier always keeps post-backup content,
new-file preservation and zero-loss proof unresolved.

The new read-only incident adapter authenticates the retained private-recovery
receipt against the retained incident manifest. It does not import or replay
consumed programs, extract archives, or refresh Desktop stream authentication.
Its current audit is scoped to recorded regular-file evidence. Directory/link
names lacking authenticated metadata remain explicitly uncovered.

## October 8 evidence

Evidence root: `/mnt/vk-storage/vk-startup-recovery-safety-20261008`.
The fresh read-only regular-file audit checked 116,402 entries: 116,352 matched
content and mode, 47 differed in content, 3 lacked mode evidence, and none were
missing. Another 14,382 names from the original missing-baseline list lacked
metadata in the authenticated regular-file receipt; all currently exist, which
is not a verification of their type/mode/link target. No survivor was modified.

The journal retains both `coverage_lost: 16384` errors and `ready: false`.
Baseline and journal coverage are therefore **not certified**, and zero loss is
not claimed. Differences include later Git-registration changes and reconstructed
owner edits; they are not automatically classified as losses. A separate check
of all 15 recorded owner reconstructions found 14 current hashes matching their
reconstruction receipts. HANDOFF.md has a later difference. That is narrower
than proving all post-backup edits across other workspaces survived.

All 41 files in the retained incident evidence manifest reverified their sizes
and SHA-256 hashes. The original placement result is incomplete; its separate
63-operation resume result is completed. Both are retained. The new audit's
SHA-256 is `3b87711216971a96a2b9ecb71d28493481b564a667526d7a2723db0d07e99908`.
No historical exception or journal gap was removed.

Production was observed read-only as service
`vibe-kanban-green-production-20261005.service`, PID3027197, started October5,
HTTP version0.1.42. The unversioned green service is an old failed service and is
not current production. The maintenance workspace remains clean and unchanged.
No agent was interrupted and no shared application data was written.

## Validation and adoption boundaries

Local validation:

- `cargo check -p server --locked` passed.
- `cargo clippy -p server --all-targets --locked -- -D warnings` passed after the
  removed cleanup task's unused state/return binding was corrected.
- Five std-only Rust invocation/identity tests passed against the actual safety
  module, with private sentinels.
- Thirteen Python recovery/assembly regressions passed.
- The namespace harness passed all 14 cases using a small std-only probe built
  from the safety module. This validates containment and the harness, not real VK
  startup. The real-binary integration test is wired into hosted Cargo tests.
- `pnpm run format` passed with temporary SSD-installed Prettier3.6.1 (the locked
  version); no frontend files changed. Ops governance and diff checks passed.

`pnpm run check` and `pnpm run lint` were attempted and stopped at absent frontend
TypeScript/ESLint dependencies. The cold focused WorkspaceManager test build hit
bounded time/space limits before completion. Its test is compiled/checked by the
all-target Clippy check but not claimed as executed. Full workspace tests and
real VK binary startup/HTTP acceptance have not run locally. Hosted CI and
independent review remain required; a draft review is not incident closure.

All build output was task-local on the mounted SSD. Only this task's newly
generated Cargo cache was retired after checking for active compiler/service
consumers and attachment storage; source, logs, fixtures/probe and recovery
evidence remain. No existing archive or worktree was removed. After retirement,
about5.44GiB free remained, still below the full recovery rehearsal's8GiB floor.

Before later release preparation adopts this repair, reviewers must assess the
startup contract and retention behavior, run the real isolated server tests and
full relevant CI, and integrate the candidate-specific inspection handler without
weakening argument validation. Later controller/v2 rollback compatibility,
B-backed capture/restoration, full handover rehearsal, frontend/module/runtime
binding and actual inactivity remain separate requirements. They authorize no
production switch in this assignment.

## Draft review and first hosted run

Draft [PR153](https://github.com/artinflight/vibe-kanban/pull/153) contains this
repair. Its first hosted run at84d1d2a passed governance, freshness/policy,
frontend, schema, Clippy and Tauri checks. Cargo executed404 tests:403 passed,
7 skipped, one real-binary isolation test failed before launching the executable.
The fresh WorkspaceManager preservation test and all five identity tests passed.
The runner denied bubblewrap's loopback setup (`RTM_NEWADDR`); the test correctly
failed rather than falling back to host execution.

CI setup now installs and loads Ubuntu's packaged `bwrap-userns-restrict` profile
and probes the namespace boundary before running Cargo. This follows Ubuntu's
[purpose-built profile guidance](https://discourse.ubuntu.com/t/understanding-apparmor-user-namespace-restriction/58007)
and its [packaged profile inventory](https://packages.ubuntu.com/noble-updates/all/apparmor-profiles/filelist).
Only the ephemeral GitHub runner is configured; the MCP host's policies and all
server isolation mounts/namespaces are unchanged. The corrected hosted run and
independent review remain required.

The source84d1d2a evidence packet is fully hash-verified on Desktop at
`B:/vk-backups/vk-startup-recovery-safety-20261008/startup-recovery-safety-evidence.tar.gz`,
128,289bytes, SHA256
`903b83edd3c1169515374b75f3e73eca2987cd02dc7dcf50e6afd07504a6b4f5`.
It retains the source patch, current audit, owner comparison, local validation
logs and the exact generated-cache retirement inventory. Later evidence must use
a distinct bundle, preserving this first packet and the failed CI result.

## Intrinsic dataset identity correction

Review against the hard requirements found that filesystem identity alone cannot
detect a database rewritten in place. The receipt now also requires an intrinsic
dataset token. The preflight reads only that token through a read-only connection
with creation disabled; missing, empty, duplicate or mismatched token evidence
fails before migration or writer construction. Regressions include a token
removed/changed in place without changing the database inode. The real-binary
harness now has16 cases; its final hosted acceptance remains required.
