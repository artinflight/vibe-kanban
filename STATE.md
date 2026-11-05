# Current frontend — save read workspaces for later, 2026-11-05

Read Later now accepts already-read and unread workspaces at <https://vibe.local>.
Published 2026-11-05T10:18:22.737137+00:00; reload existing tabs. Version stays 0.1.42.
Entry assets: JS `index-B2rzzhh-.js` and CSS `index-C9CeMCZN.css`.

The inline bookmark is available on ordinary workspace rows regardless of read
state. A saved workspace stays in Read Later through reading, polling and reload;
only explicit removal removes its bookmark. Removing a read workspace returns it
to Completed/idle history; unread/running work follows its existing grouping.
Read/unread flags are never changed by bookmarking. The removal label is now
"Remove from Read Later" in all seven supported locales. Issue/inbox eligibility
is otherwise unchanged; preferences remain browser-local and host/user-scoped.

Feature `449819b1e` changes 11 reviewed production inputs among 1,324 pinned
files from the exact prior live source; every other input matches. The 417-file
build and paired roots retain 1,137 assets. Current pointer:
`/mnt/vk-storage/vk-read-later-20261104-f57c/save-read-fixed/paired/candidate`.
VITE_DOT_SIDECHAT=0 remains preserved; this does not re-enable Dot polling or
modify stored acknowledgements. Prior flag correction history remains in
VK_READ_LATER_DEPLOYMENT.md and LIVE_DEPLOYMENT.json.

UI/web-core/local-web types, focused lint, format/ops, 15 Read Later interactions,
15 conversation-read, 10 notice, 12 pagination/Dot and five preservation tests
pass. Candidate and public browser checks pass four desktop/phone × read/unread
cases: inline icons, save/reload/remove, no overflow/errors, zero read/application
writes and no Dot polling. Five scrolling layouts pass in both phases.
Recovery (116,678,639 bytes, 5,071 files) passed full
isolated restore and independent Desktop B readback before activation. Services,
backend hash, database inode and 99 migrations are unchanged. No service restart,
DB restore, provider inference, physical-device QA or full Rust/hosted baseline.

[LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json) and
[Read Later deployment](VK_READ_LATER_DEPLOYMENT.md) hold exact provenance and
recovery. Local commits only; no push, PR or main promotion. Historical IDs below
remain immutable.

# Previous source integration and production — 2026-11-03

The operator accepted the restored scrolling projects menu ("Good") and requested
[PR #292](https://github.com/artinflight/vibe-kanban/pull/292) into staging with rebase merge. This branch is rebased onto fork/staging
`c3c1dc9d6738f936635e40a9f7019bc2028f7689`; the three scrolling package files
remain byte-identical to the accepted d0496eb1d feature. Main promotion remains
separate. Git integration does not deploy code or restart services.

The previous public frontend was the workspace-visibility composition under
`/mnt/vk-storage/vk-invisible-workspaces-20261103-75db/paired/candidate`:
JS index-CM79W1F0.js, CSS index-BDlsFLgm.css. Its source preserves all three accepted
scrolling files exactly. Current [LIVE_DEPLOYMENT.json](LIVE_DEPLOYMENT.json)
retains that newer release and its provenance; preserve this runtime and existing
preview routes during source integration.

The scrolling correction was published at 09:59:20 UTC after a later unread
publication omitted its three source changes. Fresh public reproduction found a
1134 px document with 19 real projects in a 600 px window; the corrected document
stays 600 px while the menu scrolls, including at the bottom boundary. Five
candidate/public long-list viewport cases and real desktop/phone-layout tests
passed with all application mutations intercepted. 27 preserved-feature tests
and five preservation-gate tests pass. The gate is required by the publication
workflow/runbook and its regressions now run in recovery CI. Operator acceptance
is recorded; physical-device testing is not claimed.

Scrolling restoration receipts remain under
`/mnt/vk-storage/vk-scrolling-projects-20261103-9cb7-correction`. The paired fallback,
926 retained assets and independently restored/Desktop-B-verified 88,674,581-byte
software recovery archive are retained. Current publication has its own later
recovery evidence in the manifest. Never restore an old DB over new writes.

Backend remains source 9a4179e8b, executable SHA256
137d6cd7b6475f47f9b92455a879b5fd23d3b3a5374743c77d0c694f3f1257d2;
writer service vibe-kanban-native-review-20261015.service on 5621. Public gateway
4720 routes through protected history proxy 5640. DB resolves to
`/mnt/vk-storage/vk-original-access-recovery-20261025T1748/working90.sqlite`, with
99 migrations. Preserve current native homes, private history bindings, protected
reader, attachments, review state, queues and saved settings. Blue is retired.
The eight-execution guardrail, supervised permissions, disabled failover and
existing executor/capacity controls remain. Four Antigravity acceptance turns are
spent; no new provider turn or production conversation is authorized by QA history.

Staging also contains the duplicate-log Codex resume correction from PR #290;
it has not been deployed to the backend. See
[duplicate-history evidence](VK_DUPLICATE_HISTORY_FIX.md) for qualification limits.
The recovery/source reconciliation in PR #284, explicit-read/settled-turn fixes in
PR #288, and workspace filter/unread integrations #286/#287 remain historical
source records. Original deployed IDs stay immutable after Git rebase integration.

Local Rust check/lint/workspace tests cannot resolve offline serde; less than
2 GiB SSD capacity precludes dependency downloading or large local rebuilds.
Full validation is recorded by
[hosted baseline](https://github.com/artinflight/vibe-kanban/actions/runs/41740959926)
and [recovery contracts](https://github.com/artinflight/vibe-kanban/actions/runs/41741243530).
PR #292 final checks and merge event govern integration status/rebased IDs;
private remote dependency checks retain their existing credential limits. Read the [deployment runbook](VK_AGENT_DEPLOYMENT_RUNBOOK.md)
and [backend handoff](BACKEND_DEPLOYMENT_HANDOFF.md) before any runtime action.

Full pre-integration pickup: [scrolling history](STATE_SCROLLING_HISTORY_20261103.md).
[Scrolling deployment record](VK_SCROLLING_PROJECTS_DEPLOYMENT.md) retains failure,
recovery and source identities. Prior topic map:
[previous index](deployment-history/20261030-before-reconciliation/STATE.md).
[STATE history](STATE_HISTORY_20261017.md) remains indexed by
[CONTINUITY_ARCHIVE.json](CONTINUITY_ARCHIVE.json).
