# PR229 inherited triage timing failure

## Diagnosis

Exact failing head: `47d4293fe95191363eeef509d6b0e78b772ab946`.
[CI job](https://github.com/artinflight/vibe-kanban/actions/runs/37837612498/job/113518716508)
failed `simple_language_and_discovered_protected_context_raise_the_floor` at
`routing_triage.rs:509`: expected Frontier, got Workhorse. The individual test
took 134 ms. All nine other jobs passed; backend-test stopped after 170 passes,
one failure and seven skips already configured by the existing suite.

The entire executors tree is unchanged between this head and its staging base.
The triage file has Git blob `c4bc0a957c71dd4ab9b9b0bad1eb8ca48161dda8` in this
head, staging base `5a887abf8bbedfbfb01ce7f8898fed07102fa1e3`, and prerequisite
PR149 `49cf82d603b765b4ceaf5a8b4462f046e6181c0f`. It originated in `5c96c9d37`
on September 30. This is not a direct-to-B interaction or shared fixture race.

Repository inspection has a real 40 ms deadline. A scheduler/I/O delay before
the permissions-bearing component is read returns incomplete evidence and the
existing unknown-context Workhorse floor. The fixture previously assumed it
would always discover that file within 40 ms. The CI log does not record its
internal elapsed value, but this exact failure is deterministically reproduced:
the unchanged test passes normally, and fails at the same assertion when its
own directory reads receive a 50 ms delay through `strace` fault injection.
No production process was traced or delayed.

## Minimal correction

Production still imports `std::time::Instant`. All production structs/functions,
including protected-context detection, capability floors, symlink/read limits
and both 40 ms checks, are byte-identical. Test builds have a scoped thread-local
clock, restored on drop and used by the private repository fixture. The original
Frontier assertions remain; none were removed, relaxed, retried or skipped.

Two additional tests explicitly verify exhausted inspection remains incomplete
and cannot qualify a task as Routine, explicit protected intent still requires
Frontier, and clock overrides are nested, thread-local and restored. This changes
test scheduling dependence, not routing/security policy or a production timeout.

## Local evidence and limits

The nearly full SSD cannot accommodate a full new executors build. A small
`rustc --test` harness compiles the actual checked-out triage, assessment and
context modules against existing dependency libraries read-only. Only unrelated
product type dependencies are represented in the harness (the identical floor
enum and a decision holder); it is not a claim of full-crate integration.
Source, baseline/fixed binaries and harness are retained under
`/mnt/vk-storage/vk-direct-b-stream-20261008/`.

- Unchanged baseline exact test: passed normally in 0.02 s; failed with delayed
  directory reads, reproducing Workhorse versus Frontier at line 509.
- Fixed actual-source harness: 13 routing/assessment/context tests passed.
- All seven triage tests passed with the same injected 50 ms directory-read
  delays and four test threads (1.26 s). Explicit expiry coverage also passed.
- All 215 private backup operational tests passed again in 38.481 s; the eight
  original source-bound direct-to-B hashes remain unchanged.
- Narrow rustfmt and `ops:check` pass. `pnpm run format` remains blocked by the
  intentionally sparse checkout's absent `crates/capacity-guard/Cargo.toml`;
  full application checks belong to the exact-head CI run.

SHA256 receipts:

- Corrected `routing_triage.rs`: `9c29e6f59c92f6470422b16601dab772721c2532e04684f697fa9dec42242a9e`
- Local harness source: `378188332e26906d2396da73bccb15d3f244687585d2c92972ea43acf32f9d89`
- Baseline test binary: `659281ed9d9d1904e2ae19f64cf46b45efe403e39bbf28b6ccc07c11f9c94f72`
- Corrected test binary: `d37d61a77baeab279992704bad3cac6a9cd1903893bfb4550b6e37143f52254e`

Reproduction commands (the `strace` command is identical except binary name):

```sh
TMPDIR=/mnt/vk-storage/vk-direct-b-stream-20261008/tests \
  /mnt/vk-storage/vk-direct-b-stream-20261008/routing-baseline-tests \
  --exact routing_triage::tests::simple_language_and_discovered_protected_context_raise_the_floor

TMPDIR=/mnt/vk-storage/vk-direct-b-stream-20261008/tests \
  strace -f -qq -e trace=getdents64 -e inject=getdents64:delay_enter=50ms \
  /mnt/vk-storage/vk-direct-b-stream-20261008/routing-fixed-tests \
  routing_triage::tests --test-threads=4
```

## Release status

Do not reuse the red head's CI result as acceptance. The corrected commit must
complete its own existing CI run; terminal results will be attached to PR229.
No workflow, routing policy, backup source, credential, production service,
cleanup or deployment changes are included. Direct-to-B integration remains
Root-coordinated and subject to the separate restore/readiness/human-QA gates.
