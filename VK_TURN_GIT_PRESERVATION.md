# Automatic turn Git preservation — development contract

This feature is opt-in development work on `feat/turn-git-preservation`, based on
fork/staging `8b562265d25a3f8ee6d4fa602144e71caddfbc85`. It is not installed or
active in production. No Staging workspace, service, restart/cutover controller,
routing mode, or cleanup policy was operated. Recommend-only remains required.
Seamus owns the separate Staging integration and deployment boundary.

Tracking: VK Dev T48, issue `783c983a-416e-43f5-9754-8c2f619e9918`, linked to
workspace `c31ac191-d4cf-4ab9-b3e8-9c1a7d7c3b73` (VK::Git Sync Enforcement).
The fork disables GitHub issues. The development PR is recorded in HANDOFF.md.

## Behavior and boundaries

The local-deployment hook is disabled unless an operator sets
`VK_TURN_GIT_PRESERVATION_CONFIG` to an absolute external policy file. The helper
is embedded in the backend, so adoption requires a matching backend package,
Linux, Python 3.10+, Git, GitHub CLI authentication, an approved Gitleaks executable and
its SHA-256, external receipt storage, and reviewed repository policies. An
invalid configured policy blocks admission; it does not fall back to broad
legacy commits. No settings are installed by this change.

Before a coding-agent or configured cleanup-script execution launches, the
helper writes a durable pending turn record and a latest-turn pointer. An absent
end callback, failed launch, interrupted host, or newer pending turn cannot be
certified using an earlier successful receipt. Coding-agent and cleanup-script
completion invoke preservation for successful, failed and killed outcomes.
Executor success/failure remains separate from Git coverage. A closed completion
channel is treated as failure when this feature is enabled.

At completion the backend checks known executions sharing the repositories,
terminates the owned process group, and verifies its Linux `/proc` members are
quiescent. The helper uses a common-repository lock, an exclusive Git index lock,
repeated byte/mode/index/status fingerprints, and a compare-and-swap branch
update. A private temporary index commits the current eligible working bytes,
including untracked source and deletions, then updates the real index. The
working files are not rewritten. No hooks, force pushes, merges, resets,
auto-merges, permission/visibility changes or empty commits are used.

Outgoing intermediate commit paths/blobs are reviewed against the policy. Raw
`cat-file` blob bytes and original commit messages are scanned through Gitleaks
`stdin`, including deleted secrets, unchanged lines in changed blobs and merge
revisions. Scanning does not consume rendered Git diffs or filename-based skips.
Existing agent-created commits retain their original ancestry. A normal explicit-ref push targets the
approved existing destination, with tag following, mirror pushes and recursive
submodule publication disabled. The helper reuses one open PR with the correct
repository/head/base, or creates and independently confirms a new draft. A
read-only clean turn creates no commit, branch or PR. An unchanged branch at the
reviewed base can use the base's exact remote witness. Pre-existing unsynced
commits on a read-only turn remain blocked rather than producing artifacts.

Coverage requires live `ls-remote` equality, a fresh fetch into an independent
object store, matching commit/tree IDs and a complete Git object graph. The PR
head must independently match. A matching remote-tracking ref, a local push exit
code, or an old receipt alone is insufficient. Schema 2 retains an append-only
per-repository original-commit ledger. All affected heads are durably observed
before policy/snapshot admission and before preservation starts; generated
commits are recorded before branch compare-and-swap. Retries union observations
and later turns inherit the ledger even after empty, partial or failed admissions.
An omitted original repository or an unverifiable head observation stays blocked.
Replacing a withheld original history with a source checkpoint cannot clear those
obligations. Every original must be an ancestor of the exact remote witness.

Pending and blocked states carry the workspace, turn, repository paths and
reason. Completion emits visible system/error entries and appends preservation
status to the durable coding-turn summary, including remote SHA/PR links when
available. Blocked preservation withholds chained actions, ordinary completion
notifications, queued continuation consumption and the existing completion-time
archive-cleanup retry. Executor status is retained; the separate Git status is
explicit. A summary-persistence failure invalidates the controller receipt.

## Privacy and publication policy

There is no default publication permission. Policies contain explicit reviewed
repository-relative filenames; globs and unknown files are rejected. New source
filenames need classification before admission. A filename's extension alone is
not evidence that it is safe for the repository audience. Customer content in a
source-looking file must be excluded by the operator's policy review; a secret
scanner cannot classify all private customer information.

Built-in exclusions reject credentials/environment files, runtime/upload and
customer/client/account/financial paths, private databases, common document/data
exports and binary artifacts even if mistakenly allowlisted. Symlinks, gitlinks,
special files, non-text outgoing blobs, large files, sparse/hidden index flags,
shallow histories and unresolved conflicts require separate review. Transforming
Git filters can leave a snapshot dirty; that fails closed rather than claiming
coverage. Clean status alone is insufficient: raw working blob IDs and executable
modes must match the preserved tree, so clean filters, CRLF conversion or disabled
filemode tracking cannot certify unpreserved bytes/modes. The approved Gitleaks binary is hashed and runs with explicit default
rules and repository ignore files/comments disabled. Git and scanner subprocesses
share one environment that strips inherited `GIT_*` and `GITLEAKS_*`, disables
replacement objects and legacy grafts, and enforces literal pathspecs. Raw-object
scanning bypasses attributes, binary diff classification, diff drivers and
textconv. Binary/non-UTF-8 blobs still block; they are never scanner exclusions.
Scanner/subprocess output is never copied into errors.
Receipts contain hashes/metadata, never source contents, and are mode 0600.

Ignored files are never staged or uploaded. A changed ignored-file inventory
blocks the turn and states that it is outside Git protection. Unchanged ignored
files are listed as `ignored_not_git_protected`; their metadata is not an exact
content backup. A caller requiring an ignored/private file can name it in
`required_files`; that remains blocked. Git preservation is not backup or removal
permission for excluded files, uploads, databases, session stores or attachments.

Publication review is an explicit operator assessment of GitHub Actions and
external automation, bound to the integration base, the default/automation
source commit and `.github` digests, with an operator-selected review expiry.
Moved review refs or changed automation fail closed. The code does not infer that
draft PRs suppress deployment, and cannot infer external provider configuration
changes; refresh the review when those change. Do not enable publication for a
repository whose push/draft events would deploy without separate authorization.

The development PR's workflow review found Test on PRs into staging/main and
pushes to protected integration branches. Deploy-dev workflows require a main
push with remote/relay paths; release/publish workflows use explicit dispatch or
release events. The new Test job runs disposable local Git fixtures only. No
workflow is dispatched by this task. This is a bounded source/configuration
review, not a universal assertion about unobserved external systems.

## Policy example (not an installed configuration)

Replace placeholders with reviewed full IDs/digests and actual external paths.
The receipt root must already exist on approved mounted storage; the helper checks the configured mount and filesystem identity before writing. Keep policy,
scanner and receipt state outside agent-writable source/workspace roots, and
protect them through the deployment owner's native permissions and packaging.
The config-path check rejects policies inside repositories; that alone is not an
OS security boundary against a malicious same-user process.

```json
{
  "storage_mount": "/mnt/vk-storage",
  "state_root": "/mnt/vk-storage/approved-turn-receipts",
  "scanner": "/approved-tools/gitleaks",
  "scanner_sha256": "REVIEWED_BINARY_SHA256",
  "repositories": {
    "VK_REPO_UUID": {
      "common_dir": "/approved/repository/.git",
      "remote": "fork",
      "url": "git@github.com:artinflight/vibe-kanban.git",
      "repository": "artinflight/vibe-kanban",
      "base_branch": "staging",
      "base_commit": "REVIEWED_FULL_BASE_COMMIT",
      "allowed": ["src/approved-source.rs"],
      "workflow_digest": "SHA256_OF_BASE_GIT_LS_TREE_R_DOT_GITHUB",
      "automation_branch": "main",
      "automation_commit": "REVIEWED_FULL_AUTOMATION_COMMIT",
      "automation_workflow_digest": "SHA256_OF_AUTOMATION_GIT_LS_TREE_R_DOT_GITHUB",
      "publication_review": "Named reviewer and evidence for push/draft automation",
      "review_expires": 1792000000,
      "protected_branches": ["release"]
    }
  }
}
```

The digest is SHA-256 of raw `git ls-tree -r COMMIT -- .github` output. The built-in
protected branches also include main and staging. Multiple push URLs, changed
remote destinations, absent remotes or unavailable authentication block. New
repositories/remotes are never created automatically.

## Independently consumable controller contract

Run only against isolated fixtures during this development task. Production
adoption belongs to Seamus; no live controller calls this check yet.

```bash
python3 -I -B scripts/preservation/turn_git.py check-all \
  --config /external/reviewed-policy.json < /external/affected-work.json
```

Input is an explicit complete inventory of the latest affected turn for each
workspace, obtained from authoritative VK execution/repository state:

```json
{
  "writers_fenced": true,
  "turns": [{
    "workspace": "WORKSPACE_UUID",
    "turn": "LATEST_EXECUTION_UUID",
    "repositories": [{
      "id": "VK_REPO_UUID",
      "path": "/isolated/workspace/repository",
      "required_commits": ["OPTIONAL_REQUIRED_FULL_ORIGINAL_COMMIT_ID"],
      "required_files": ["src/approved-source.rs"]
    }]
  }]
}
```

Optional requirements belong to the admitted inventory. Adding or omitting them
later does not reuse a mismatched receipt. Required originals must exist and be
ancestors of the freshly fetched witness; a missing original cannot be replaced
with a source checkpoint. The helper retains all observed original commit
obligations across retries and earlier turns in that workspace, including failed
admissions. An unavailable original observation cannot be erased by a retry.

Exit 0 **and** JSON `{ "version": 2, "state": "verified", ... }` are required.
Exit 2 / `blocked`, any other nonzero exit, timeout, malformed/unsupported output,
empty inventory, missing receipt/obligation ledger, pending/failed receipt,
identity mismatch,
newer turn, missing original, changed source/index/ignored inventory, remote
mismatch, unavailable remote/fresh objects, or a closed/mismatched PR blocks.
`check` handles one workspace with the same fields and `writers_fenced: true`.
Schema-1 receipts are unsupported in both `end` and `check`; they cannot be
automatically upgraded into exact-original proof because earlier observations
may already have been lost. The rollout owner must reconcile original history
explicitly before adopting a new protected receipt namespace. Fresh checks
rescan outgoing original objects with the approved binary. The batch check
compares the complete durable receipt digest after checking all turns; any
version, policy or original-ledger mutation invalidates the result.
`check` and `check-all` never repair, commit, push or create PRs. Temporary fetched
objects/locks are their only Git/storage effects. Their verified scope is
`eligible-repository-work-only`, never excluded-file or backup coverage.

The controller owns inventory completeness and the real writer fence (including
external/detached writers and preservation subprocesses). `writers_fenced` is a
caller assertion, not a self-certifying mutex. Hold that fence while running the
fresh batch check and through the destructive action's boundary. A cached success
must never authorize a later restart/cutover after the fence is released.
Repeated fingerprints detect concurrent changes but cannot prevent an uncooperative
writer from editing after the check returns. The check does not itself authorize
restart, deployment, cleanup or deletion. Explicit affected exclusions need their
own authorized backup/reconciliation evidence and cannot be called Git-protected.

Pending/blocked receipts and any created Git objects remain diagnostic evidence on failure; temporary indexes are removed.
Retried `end` verifies prior successful repo receipts, reconciles an existing PR
before creating another, and never creates a duplicate empty commit. Failed/uncertain
push or PR creation is not silently treated as protection. There is no background
retry loop or automatic removal of locks belonging to another Git writer.
`block` is the backend's receipt-invalidation callback for a visibility/persistence
failure; controllers consume only `check`/`check-all`.

## Retrospective provenance

Operations issue16 / draft PR198, final receipt
`53f645a95973aaf30f1f4e2cceb6425c3c748621`, documented 661 publication records across
39 repositories. Its 2,899-original accounting distinguished 2,473 exact histories,
262 source-only checkpoints, 145 missing originals and 19 private-history
exclusions. Those are historical evidence categories, not inputs accepted as new
schema-2 exact-history receipts. No retrospective source checkpoint proves all
intermediate original versions or excluded bytes. This feature does not sweep,
repair or certify that historical inventory. Required missing originals and
excluded private histories remain explicit blockers when included in affected work.

The correction also documented Caspian Firebase preview deployment and an OSTP
Cloudflare preview upload triggered by preservation drafts. That is why this
feature requires a publication review and does not equate draft status with
absence of automation.

## Validation and rollout handoff

Fixtures use real disposable local repositories and bare remotes, with deterministic
GitHub adapters; they make no GitHub publication or live VK/runtime calls. The real
Gitleaks acceptance uses a constructed synthetic token. Regressions exercise
replacement refs, local binary attributes/custom diff drivers, legacy grafts,
repository/environment configuration and allow comments, removed intermediate
secrets, unchanged secret lines in changed blobs, commit messages, long text
lines, binary/non-UTF-8 rejection and fresh-check rescanning. A positive real-
scanner test preserves clean tracked/untracked work and freshly verifies it. Disposable fixture
rewrites reproduce lost-history retries; no real work is reset or rewritten.

```bash
VK_PRESERVATION_TEST_ROOT=/mnt/vk-storage/turn-git-preservation-review-20261008 \
VK_TEST_GITLEAKS=/path/to/approved/gitleaks \
  python3 scripts/preservation/test_turn_git.py
TMPDIR=/mnt/vk-storage/turn-git-preservation-review-20261008 \
CARGO_TARGET_DIR=/mnt/vk-storage/cargo-target CARGO_INCREMENTAL=0 \
  cargo test -p local-deployment turn_preservation --offline
```

CI runs the isolated fixture contract in Test. Gitleaks acceptance is optional
there unless an approved executable is supplied; it was run locally. The embedded
helper's Rust test persists pending state in a real disposable Git repository and
rejects its unfinished receipt. A separate process-group test checks only a
spawned sleep fixture. See HANDOFF.md for actual final counts and broader-check
limits. No provider inference or production UI acceptance was performed.

Seamus's remaining deployment outcomes are a backend/config/scanner package with
protected receipt storage, a complete authoritative affected-work inventory and
writer fence in the restart/cutover controller, and copied-data end-to-end
acceptance showing visible pending/blocked/success states for genuine execution,
cleanup and stop timing. Resolve the generic CI desktop-library checks on the
appropriate runner. Re-review automation before any automated publication policy
is enabled. Live install, activation, Staging integration and restart/cutover need
their own authorized delivery; this branch and draft PR do not provide it.
