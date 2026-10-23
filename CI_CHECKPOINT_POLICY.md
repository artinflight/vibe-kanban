# Checkpoint backup and final CI proposal

This is preparation for **artinflight/vibe-kanban only**. No active workflow,
repository setting, preservation policy, runtime or deployment is changed.
The proposed workflows render outside `.github`; the renderer refuses to install
them. Keep the PR draft until the protection and independent-review decisions
below are resolved. Checkpoint publication is not merge validation.

## Checkpoint and validation behavior

Retain the existing end-of-turn Git-preservation mechanism, its original-history
and publication checks, ordinary checkpoint pushes and one draft PR per concern.
Do not introduce another publisher, worker, sync prompt, empty commit or PR.
The existing [automatic sync](VK_AUTOMATIC_GITHUB_SYNC.md) and
[preservation](VK_TURN_GIT_PRESERVATION.md) owners retain their responsibilities.
This proposal does not change commit messages or introduce skip trailers.

After separately approved protections are installed and read back, the proposed
workflow set permits expensive jobs only for ready PRs. Drafts still receive
small, **failing** merge gates: they never receive a passing final-validation
receipt. Returning to draft invalidates readiness. Continue checkpoints in draft;
mark ready only when the source is ready for its final tests.

All seven final suites run for ready PRs into either `staging` or `main`, without
path-filter omissions. Each required gate uses `always()` and accepts only
`success` from every required job, rejecting skipped, cancelled, missing, neutral
or failed jobs. Missing private dependency access fails the remote job instead
of reporting success without tests. Fork PRs cannot satisfy the remote suite
without a separately authorized, reviewed same-repository validation path.
There is no automatic credential/access grant or privileged target-PR execution.

Tests use the PR test merge tree. The final verifier freshly reads the PR, the
current base branch and the tested Git commit. It checks the original event's
source/base SHAs, current source/base SHAs, current merge SHA and both merge
parents. A source or base change during a run fails validation. Strict protected
branch checks prevent a branch behind the current base from merging; update
the branch and rerun all final suites after source/base movement. Manual and
post-merge runs use different gate names, so their skipped/successful jobs cannot
substitute for PR checks. No old green, dispatch artifact or local fixture pass
is accepted as final merge evidence.

The initial conservative policy runs all suites once ready, including desktop
and remote checks. It trades higher final-run cost for an explicit complete
validation boundary. Path-sensitive final-suite reduction would need a separate
review and is outside this proposal. Superseded PR runs retain cancellation.
Existing push/manual artifact inputs, release and deployment triggers are kept.
The branch-policy step passes branch names as quoted environment variables,
removing its inherited inline-expression shell-injection risk.

## Seven PR workflows inspected

Reviewed staging source: `5b43524ea35b2eb5dd80d0881dc8445489f4442f`.
The manifest retains exact SHA-256 hashes and all original workflow bytes in
`scripts/ci/checkpoint_policy/baseline/`; generation refuses unreviewed drift.
Baselines are inert fixtures, not registered workflows.

| Workflow | Existing PR scope | Proposed required check context |
| --- | --- | --- |
| `test.yml` | main/staging; ignores other workflow-only edits | `CI policy / Test` |
| `dot-steering-acceptance.yml` | staging; Codex client, connector, own workflow | `CI policy / Dot steering acceptance artifact` |
| `historical-response-recovery.yml` | path-filtered recovery/chat changes | `CI policy / Historical response recovery` |
| `large-history-verification.yml` | staging; original-worker/verifier changes | `CI policy / Large history verification` |
| `native-final-repair.yml` | path-filtered repair CLI changes | `CI policy / Bounded native final repair` |
| `native-review-compatibility.yml` | staging; Codex/reviewer changes | `CI policy / Native reviewer compatibility` |
| `scheduled-goal-artifacts.yml` | main/staging; capacity/Codex/artifact changes | `CI policy / Scheduled goal acceptance artifacts` |

All seven already permit manual dispatch. Test also handles main/staging pushes
and has a separate dispatch-only combined artifact job. That operator-only job
is retained and cannot satisfy a PR's required checks. No workflow is dispatched
by this preparation. The six artifact suites build/upload artifacts; they do not
install them into a running instance.

## External triggers and evidence boundaries

The October 23 read-only audit inspected actual workflow sources on both main
and staging, not only GitHub's workflow registry. Main contains nine workflow
files; staging contains fifteen, seven of which have PR triggers. Registered
legacy AutoSwitch/backup/report entries absent from those source trees are not
evidence of active PR triggers.

Outside the seven PR workflows:

- Remote/relay development workflows require a **main push** matching remote/web
  or relay paths, or an explicit manual dispatch. They dispatch to the upstream
  deployment repository. A checkpoint branch push does not match.
- Remote/relay production deployment and prerelease workflows require explicit
  manual dispatch. Release workflows respond to their named deployment-success
  repository-dispatch events; publishing responds to release/manual events.
- Prerelease jobs publish release assets and uploads; this policy never invokes
  those release paths. There is no PR-triggered deploy/preview step in the
  inspected source and no source configuration for Vercel/Netlify/Firebase/
  Cloudflare preview publication was found.
- Live hooks: empty. Environments: zero. Deployment records: empty. Pages lookup:
  404. Observed staging checks come from GitHub Actions app **15368**; no external
  commit statuses were present on that staging SHA.

These observations do **not** prove absence of an independently installed GitHub
App. Both installation-list reads were unavailable with the current credential
type (401/403); no alternate credential or access expansion was attempted.
The owner must verify external App preview/deployment subscriptions before
activation. No external integration is disabled or modified here.

## Live settings and exact proposed changes

Fresh October 23 audit: both `main` and `staging` report `protected: false`;
their protection endpoints return **404 Branch not protected**. Repository
rulesets including parents and effective branch rules are all empty. There are
no required contexts, strictness, enforced review rules, admin enforcement or
force-push/deletion protection to rely on today.

| Setting | Observed | Proposal |
| --- | --- | --- |
| Required checks, main and staging | none | all seven contexts above, expected app 15368 |
| Current-base strictness | off | `strict: true` |
| Admin enforcement | absent | `enforce_admins: true` |
| PR review | absent | one independent approval; code owner review; dismiss stale approvals; last-push approval |
| Review bypass actors | no protection | empty users/teams/apps |
| Force pushes / deletions | no protection | both false |
| Conversation resolution | absent | true |
| Default Actions token | write | read |
| Actions approval of PR reviews | true | false |
| Allowed Actions / SHA pinning | all / false | unchanged |
| Secret scanning / push protection | enabled / enabled | unchanged |
| Non-provider patterns / validity checks | disabled / disabled | unchanged |
| Dependabot security updates | disabled | unchanged |
| Auto-merge | false | unchanged |
| Merge, squash, rebase methods | all enabled | unchanged |
| Delete branch on merge / web signoff | false / false | unchanged |

Exact reviewable REST bodies, **not applied**:

- `scripts/ci/checkpoint_policy/proposed-branch-protection.json`: proposed body
  for each of `PUT /repos/artinflight/vibe-kanban/branches/main/protection` and
  `PUT /repos/artinflight/vibe-kanban/branches/staging/protection`.
- `scripts/ci/checkpoint_policy/proposed-actions-permissions.json`: proposed body
  for `PUT /repos/artinflight/vibe-kanban/actions/permissions/workflow`.
- `scripts/ci/checkpoint_policy/proposed-CODEOWNERS`: proposed `.github/CODEOWNERS`
  coverage for workflow/action and CI-policy code, owned by `@artinflight`.

An eligible independent reviewer must exist: the PR author cannot approve their
own PR. If that is unavailable, protection/activation remains blocked; do not
remove review requirements, create a bypass, or grant access automatically.
The proposal uses classic branch protection, available for this public repo;
it does not depend on an organization-only merge queue or a paid plan change.

GitHub accepts skipped required jobs and ignores old-source green results.
That is why this design requires explicit always-running result gates, distinct
PR/non-PR names, strict base freshness and independent review of gate changes.
See [required-check semantics](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks),
[strict branch protections](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
[PR events and merge SHAs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request),
and [protection API fields](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection).

## Preparation, tests and later activation boundary

With Python 3 and PyYAML 6.0.1 available:

```sh
python3 -B -m unittest discover -s scripts/ci/checkpoint_policy -p 'test_*.py' -v
python3 -B scripts/ci/checkpoint_policy/render.py --output /tmp/vk-ci-policy-candidate
python3 -B scripts/ci/checkpoint_policy/audit_protection.py
```

The auditor issues GETs only and fails closed for missing/unreadable protection,
missing contexts, wrong expected App, loose freshness, bypass allowances, absent
review/admin/conversation rules or write/approval-capable default Actions tokens.
Its present live failure is expected, not activation approval. The renderer
accepts only the reviewed originals or the exact generated candidate. A changed
workflow needs a fresh review and manifest, including after a base update.

**Later, only with owner confirmation:** reconcile current settings without
weakening any intervening stronger rules; install/read back both complete
protections and the approved token/review defaults; independently review
CODEOWNERS and external integrations; then review and stage the rendered seven
workflow files together. Missing contexts deliberately block merging during
bootstrap. Do not temporarily remove required checks to bootstrap the policy.
Verify their exact published names/App on a ready test PR, including draft,
source-change and base-change rejection. No hosted negative probes or protected
branch writes have been attempted by this preparation. Activate no subset.

Fixtures cover draft transitions, missing/skipped/cancelled tests, source/base
movement, stale merge parents, retargeting, missing protections, wrong expected
App, review/admin bypass and workflow drift. They also render all seven real
workflows and preserve their test commands. They do not replace application
compilation, final hosted suites, current-base validation or human QA. This draft
is preparation only, not merge or deployment readiness.

Preparation validation on this branch: **14/14 offline tests pass**; all seven
rendered files pass **actionlint 1.7.12** (shellcheck/pyflakes integrations
disabled). Ops governance, branch policy and whitespace checks pass. The live
protection auditor exits 1 for both unprotected branches, as expected. The
required broad commands were attempted: `pnpm run check` stops at missing `tsc`,
`pnpm run lint` stops at missing `eslint`, and `pnpm run format` completes Rust
formatting then stops at missing `prettier`. No dependencies were installed in
the source tree. Full workspace Rust tests were not run; no local compiler or
application build was launched. Final hosted application validation remains
mandatory on the eventual latest source/current base.
