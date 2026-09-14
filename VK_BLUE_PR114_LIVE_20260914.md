# PR114 Blue Live: September 14

## Production Authority

The explicitly approved cutover completed at approximately20:38UTC in29.54s:
29.09s fencing/final capture and0.45s activation. New Blue
`vibe-kanban-blue-pr114-production-20260914.service`, PID2150526, is enabled and
serving5031/5032. Gateway4720 and https://vibe.local route to it. Source is exact
staging75276e79fe64d112c8e85492aad32cadb5e83cc4, version0.1.42, including PR114.
The new backend SHA256 is
b7985984e455346a8de594dbbd57a0c983b2a808e31097c086009e4c50c28124.
The unchanged frontend and all retained old hashed assets are preserved.

Green PID2778969 remains loaded and frozen, boot-disabled, for same-latest-data
cutback. Historical Blue PID2590517 also remains frozen/disabled and is NOT the
fallback target. Never thaw it. Production retains the same Green-named DB,
Codex home, attachment and worktree paths. No old database was restored.

## Acceptance

- Original maintenance native thread01a03e74-2c1a-72f0-9e00-8e4293fe910d resumed
  in VK session75bc68d4-aa55-4914-a695-f20c46a13e4c with its preserved
  gpt-6-astra/xhigh/AUTO configuration. No replacement maintenance thread exists.
- Frozen IDs remain:40projects,904tasks,918workspaces,63repos,953sessions,
  38792executions,12278coding turns and782attachments. DB integrity passed.
- All5906native index paths match the final backup. All238available attachment
  hashes match. Historical missing files are retained exceptions, not recovered.
- All12saved messages match the boundary exactly and appear in both settings
  and the chat picker at desktop and390px mobile sizes. HTTPS/API/WebSockets and
  attachment upload/retrieval passed. Retained test attachment:
  e951c3a6-f702-40fc-8415-2bffe713d420. Physical-phone QA was not performed.
- All209non-test saved draft/executor payloads match exactly. The existing
  labeled acceptance session consumed its empty draft through its authorized
  follow-up, using the exact preserved executor configuration. No nonempty user
  draft was removed or normalized for testing.
- Real Turn Steer kept execution719affc7-f25d-4c47-a14e-b1d2ba0504b5, and its
  native goal completed. Separate Stop execution8bd2acbd-9e9d-4952-9885-109a662292ff
  remains correctly killed. Existing test session4eefa404-cac8-446a-8bf6-2ff35e65a4a7
  and native01a09568-dff2-7b53-8ac1-2c48d9a1a625 were reused.
- Only the maintenance execution36f61ec0-091d-4812-a50d-83a6a15d81bb was
  interrupted by the handover; it remains killed, not falsely completed.
  Idle external native processes613308,1468335,2136204 were identity-checked,
  temporarily paused and resumed. No other VK execution or queue was active.

Existing July attachment0fa37354... and unknown native-item warnings also occur
in the pre-cutover Green journal. They were not newly introduced or waived.
The known duplicate draft-delete warning and historical recovery gaps remain.
Preparation included68executor,5guard,8renderer and3binding tests, original
thread/model tests and actual latest-data cutback rehearsal. Full workspace
tests were not rerun; two opt-in native unit fixtures and one doctest were ignored.

## Recovery Evidence

Task root: `/mnt/vk-storage/vk-blue-pr114-20260914`.
Consumed attempt: `cutover-20260914T203727Z`; read status.json, boundary.json,
live-preservation.json, live-drafts.json and live-execution.json there.
Final acceptance and Desktop receipt are published as
`live-acceptance-complete.json` and `live-acceptance-desktop-receipt.json`.

Desktop directory: `B:/vk-backups/vk-blue-pr114-20260914/`.
Final frozen archive `final-boundary-20260914T203735Z.tar.zst` is verified,
SHA256 d8323ab1ee8832269b4d6ff89dd484d8b936ae760567736c60dd008baca3265f.
Its parent online catch-up `final-delta-rehearsal-20260914T203604Z.tar.zst`
(historical filename, not a rehearsal) is also verified,
SHA256332aa9e8369bf2f199f0d5160d28ff92412000bccb932fc411bb3ff646fce965.
Retain its baseline record, earlier online refresh, software package, and the
September11 preservation AND recovery-metadata archives. Never restore any of
these over newer production data.

Do not repeat the consumed controller or reuse its approval. A cutback must
account for new work, fence new Blue, and thaw original Green on the latest DB
while refreshing its cached settings before routing back. The rehearsal proved
this behavior; do not invoke it casually after new work starts.

The isolated5011preview is stopped and its18467test entrypoint removed. Its
copied state and evidence remain intact. Old unrelated previews were not changed.
The separate CodexUsage/capacity activation remains outside this deployment and
must be rebound to the new production service/port before its own activation.
