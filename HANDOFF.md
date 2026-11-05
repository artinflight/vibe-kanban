# Read Later pickup — 2026-11-05

VK Dev T91 is deployed at <https://vibe.local>. Latest feature `449819b1e` on
`vk/f57c-read-later` was published 2026-11-05T10:18:22.737137+00:00; reload open tabs.
Local commits only; no push/PR, main promotion, agent launch or backend restart.

Current behavior:
- Attention → Read Later → Running → Completed/idle history. Read Later initially
  folded; desktop/phone and accordion/flat layouts preserve the same grouping.
- All ordinary workspace rows offer an accessible inline bookmark, including
  already-read workspaces. Saving preserves read/unread state. A saved workspace
  stays through reading/polling/reload until explicitly removed; read workspaces
  then return to Completed. Saved items survive idle-history pagination.
- Removal tooltip/keyboard label: "Remove from Read Later", translated in all
  seven locales. Existing issue/project/inbox actions use the same icon/label;
  their unread eligibility is unchanged.
- Preferences remain browser-local, scoped by host/user/kind/ID. No cross-device
  synchronization, backend/API/schema/generated-type change or implicit read.
- VITE_DOT_SIDECHAT=0 is preserved. The first deployment accidentally enabled it
  and exposed stored notices; the earlier correction restored disabled polling.
  Never infer unchanged runtime flags from unchanged source hashes alone.

Validation:
- Required format/ops/diff checks; UI/web-core/local-web types; focused ESLint.
- Exact composed source: 15 Read Later, 15 conversation-read and 10 notice tests;
  additionally 12 pagination/Dot and five preservation regressions.
- Candidate/public browser at 1440 and 393 px, each with read/unread workspaces:
  inline icon, save, reload, remove, no overflow/errors, zero Dot polls and zero
  read/application writes. Five scrolling layouts pass candidate/public.
- Bounded production tsc/Vite build; all 1,324 source inputs and 417 outputs
  hashed, only 11 reviewed production files changed. Paired roots retain
  1,137 assets. Full isolated software restore and independent
  Desktop B readback verified before a 0.016386s atomic switch.
- Five service identities, backend hash and DB inode/99 migrations unchanged.
  No physical-device, provider-inference or full Rust/hosted PR baseline run.

Current evidence: `/mnt/vk-storage/vk-read-later-20261104-f57c/save-read-fixed`. See STATE.md, LIVE_DEPLOYMENT.json and
VK_READ_LATER_DEPLOYMENT.md for exact manifests/recovery. Existing preview routes
are preserved. The fallback retains the immediately prior inline-icon frontend;
any fallback/publication requires fresh pointer ownership and preservation checks.
The previously blocked Desktop B copy completed and passed independent readback
on November 5 before publication; no backup waiver was used. Fresh source/output
and 5,071 restored-file hashes passed again in readiness-20261105.json.
No deployment remains pending. Optional staging integration still requires branch
freshness and the full hosted/repository baseline; user acceptance follows reload.

Prior continuity: [pre-reconciliation record](deployment-history/20261030-before-reconciliation/HANDOFF.md)
and [full historical archive](HANDOFF_HISTORY_20261017.md).
