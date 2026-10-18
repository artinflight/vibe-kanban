# T63 combined Dot activity release — October 18

The owner explicitly approved this exact package after being told that the three
Dot services would restart while Vibe and running agents stayed up. The approved
release is now active. This receipt supersedes the preparation-only status in
older T63 notes; it authorizes no source merge or unrelated service operation.

Dot activation completed **2026-10-18 01:29:35 UTC**, with measured stop/start
readiness **1.092 seconds**. Frontend activation completed **01:29:53 UTC**.
Only `vibe-dot-browser`, `vibe-dot-connector` and `vibe-dot-sidechat-publisher`
were restarted. Vibe/backend, frontend-static, gateway and notifier process
identities are unchanged. No native agent was started, stopped or prompted.

## Exact installed package

- Application source: `42d4011197fb6fa915e43c6b4e570493c6b5141c`, existing
  [PR268](https://github.com/artinflight/vibe-kanban/pull/268).
- Archive SHA256: `038fcee6528205c50daea25bfcd230d55e7a52f6243027af50d7819a512e8d6d`.
- Manifest SHA256: `dd0e05e2625950d5bac519573039baaf40a9e47fa0247831793c4c4151f5632a`.
- Candidate root: `/mnt/vk-storage/vk-t63-release-20261018/package/candidate`.
  The sidechat and frontend `current` pointers select its corresponding folders.
  Browser override now uses `current/browser_api.py` with original arguments.
- Served entry `/assets/index-C7kRlsb3.js`, CSS `/assets/index-C9c5vx_3.css`;
  actual HTTPS index/new assets/retained old entry/viewer hashes verified.
- Python integrates the current live PR270–272 continuation/context/dispatch
  baseline. Other modules, external CU/Stop imports and unit definitions remain
  pinned. Models/effort and Recommend routing are unchanged. No Rust rebuild.

## Meaningful live acceptance

The actual authenticated HTTPS notifications GET matches independent read-only
metadata queries across **10 affected issues and all 46 linked workspaces**,
including archived siblings. For the AF manager issue, all **31 untargeted
siblings have zero dispatch unread**; the manager retains its **four** legitimate
unread notes. The original nominated note remains unread and attention-null.
Real shared unread remains shared, including three genuine unread replies on
another affected issue. Counts are dated observations, not permanent assertions.
No real note was marked read, deleted or reclassified to obtain this result.

The served frontend renders all **36 non-archived affected workspaces** correctly
at390/1440 using the actual HTTPS metadata readback and unchanged native streams
and summaries. Three real active workspaces remain in Running. A separate live
isolated-owner test confirms an actually running workspace with explicit attention
appears in both Running and Attention at393/1440.

Actual served UI plus live Python at393/1440 passes ordinary read, Mark unread,
Mark read, duplicate clicks/repeated intents, late automatic reads, navigation,
reload and independent attention transitions. Project Dot Chat also passes
manual unread/read and resolved-attention reload at both widths. All stateful
acceptance used short-lived isolated owners; native writes were blocked. Zero QA
wake attempts occurred and coding-agent flags stayed unchanged. Interrupted
project-harness teardown errors were corrected; final tests passed, and its one
orphaned synthetic account was removed. No real owner credential was inspected.

Final read-only preservation checks retain **69 original messages**, **48 original
read/attention states**, original access/session/grant/subscription records,
dispatch receipts and shared plans. Synthetic QA cleanup is complete. Current
registered CU summary and reconciliation tools respond after restart.

## CI, backup and cutback

[Application-head CI39084924573](https://github.com/artinflight/vibe-kanban/actions/runs/39084924573)
passed. Consent-capture and substantive remote-key-dependent checks were skipped.
Full local Rust remains unavailable due to `glib-2.0.pc`; no Rust change/release is
claimed. The combined private Python package separately passed76 sidechat and34
current connector tests; fallback notification tests and copied-data rollback
passed before approval. Viewport checks do not establish physical-phone QA.

Scoped before, boundary, sealed package and latest after material are retained
at `desktop:B:/vk-backups/vk-t63-release-20261018/`. Before/after upload/hash,
download, permissions/SQLite integrity and isolated restore checks passed.
Durable private activation/test/backup receipts are under the preparation root's
`activation/` directory. They are not uploaded to GitHub.

Normal rollback keeps the **same latest SQLite**, never restores an older
snapshot and never drops `manual_unread`. UI-only fallback selects
`package/cutback/frontend` while retaining candidate Python. Combined fallback
selects `package/cutback/sidechat` and restarts only the three Dot units, retaining
the stable browser override. This fallback preserves Mark unread/current tools
but intentionally restores the earlier grouping/dispatch presentation. The
original pre-manual-unread Python is not the normal fallback.

Staging/Preserve retain subsequent source integration ownership. PR268 remains
unmerged; this runtime approval does not authorize a merge. Existing browser tabs
need a normal refresh to load the newly selected frontend.
