# Production resumption — 2026-11-04

User now explicitly requests production completion through verified recovery and
space reclamation. Preparation-only boundaries below are historical scope. Current
finite execution state is `PRODUCTION_EXECUTION_20261104.private.json` under
`/mnt/vk-storage/vk-log-dedup-20261103-0815/`. It records 66 bounded selections for
3,221 closed/inactive logs (84,557,012,508 logical bytes), starting with four
unchanged sample files. No production conversion yet; preserve all exclusions.

Existing Vibe owner execution62230d3f prepares both readers/rollback/artifacts and
real admission. Nightly execution9fa136d4 retains its existing file/SQL/runtime
phases and is qualifying composed normal restore; no duplicate backup pipeline.
Source087319cc4 has passing hosted Test/Historical recovery. Rebase onto current
stagingee2efee4d retains identical dedup code and latest frontend-preservation rules.
SSD7.5GiB free clears the old capacity observation, subject to fresh owner checks.
Continue implementation/admission/recovery work; do not stop at a dependency list.

---

# Conversation-log reclamation — 2026-11-04

Branch `vk/0815-vk-deduplicate-c`; committed format base `0192b38de`.
Guarded follow-up `52c5ea5bd` and metadata regression `e8d07f01a` are pushed. Draft [PR #291](https://github.com/artinflight/vibe-kanban/pull/291)
targets staging; final-head checks and later deployment-owner receipts govern
readiness. No merge or deployment is authorized by the draft. Final CI/coordination
receipts are in `readiness-source-review.safe.json` beneath the evidence root. Read
`VK_LOG_RECLAMATION_READINESS.md` before further action. The old protected reader
on5650 shares live captures; updating only the main backend is insufficient.
Preserve exact private retained-history inputs and latest live frontend.

New Python tools: `controller.py` loads verified source bytes for a real owner
admission context; `reclaim.py` requires the held existing WriterFence and exact
log-root binding, actual reopened B originals/sidecars, reader/consumer guard and
rollback headroom. Durable objects precede manifests; journal recovery preserves
unknown newer files/inodes. `graph.py` exports/validates complete physical archive
dependencies. `audit.py` measures bounded metadata growth without payloads,
schedules or cleanup. The missing production adapter is not replaced by ready
flags or fixture providers. Actual owner context must recover/retain maintenance
on failure before releasing consumers.

45 focused tests and eight existing fence tests pass; full format/ops and final
integration status are recorded in the readiness evidence. Local full check/lint
fail at absent tsc/eslint; no Node install or Cargo build below capacity floor.
Original six-file archive remains verified and retained. Only previously generated
restore copies were retired. Current four-file subset defers legacy history;
source/sidecar identities and inactive sessions need fresh fence-time checks.

Private plans/graph/growth/tests/coordination receipts:
`/mnt/vk-storage/vk-log-dedup-20261103-0815/`. Current B coverage is not proved by
historical October28 recovery or this local archive. Shared Nightly question is
unresolved; its owner is actively commissioning existing services. Vibe owner
review is durable in Staging's `.restart-preparation` evidence. Disk owner was
asked to recheck admitted preservation, without new deletion authorization. Its
single resumed attempt stopped at memory PSI0.14>0.10; no SSD reclamation cleared.
At23:30UTC free1,943,719,936B leaves a1,277,505,536B build-floor shortfall.
Vibe's later read-only provenance review conditionally identified2,104 exact
regenerable compiler-metadata files /1,811,595,264 allocated bytes;378 other files
remain excluded. `compiler-metadata-retirement-plan.json` is a frozen proposal,
not deletion authority. Existing owned-build/canonical Cargo locks and fresh
resource/consumer/global non-use proof remain mandatory. Inaccessible proc views
and unavailable passwordless sudo prevented global clearance; owner-described
exact-file kernel leases are an unperformed alternative requiring separate action
admission. No compiler metadata was removed. Do not reuse this review as clearance.

Production NOT READY: old main/protected readers, current-B/normal-recall and
fallback proofs missing, no live owner adapter, SSD ~1.9GiB<3GiB build floor.
Required CI/private build, compatible current-data roundtrip, public/protected
history/review/read/send QA and actual drained custody remain. Zero live logs
converted or retired; zero production recovery claimed. Do not invent readiness
or re-enable automatic cleanup. No background retry/monitoring claim is made.

Full historical archive: [HANDOFF_HISTORY_20261017.md](HANDOFF_HISTORY_20261017.md).
