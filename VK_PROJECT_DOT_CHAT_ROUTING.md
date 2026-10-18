# Project Dot Chat destination and sizing

The Projects layout passes its actual displayed workspace route to Dot Chat.
With a workspace open, history, composer, replies, unread metadata and requests
use that exact workspace. Closing it returns to project chat, even if an issue
detail remains open. Workspace requests retain the existing shared issue thread;
the workspace ID still controls dispatch visibility and the reply/send context.
Shared planning entries remain project-wide.

The sidebar labels the destination immediately. `DotSidechatLive` isolates its
session component by destination kind/ID, including for callers without a key.
Switching aborts the previous lifetime and removes its history immediately.
Late responses cannot update another destination's component. Sends wait for
history loading and retain their original exact target/body/reply/request key.
An uncertain send stays locked to its original destination and retries there;
switching never redirects it or clears a different draft.

Unsent drafts and reply selections are retained per paired browser session and
destination, separately from pending sends. Tab storage supports reload recovery;
an in-memory fallback preserves switching if storage writes fail and reports the
reload limitation. A pending request takes precedence on recovery. Successful
sends clear only their own draft/selection; disconnect clears the session's draft
cache. No anonymous or shared workspace draft key is introduced.

Desktop users can drag the left separator or use Arrow Left/Right, Home and End.
Its accessible value reports the bounded width. Full-width chat hides the board
without unmounting it or the chat; Restore returns to the prior width. Resizing
and toggling retain the composer, reply target and attention selection. The pane
tracks its actual parent size and stays within it. Mobile keeps the existing
full-width sheet, focus trap and Back dismissal, without redundant resize controls.

The outer collaboration layout is extracted from `ProjectKanban` so the actual
layout/sidebar/chat can be exercised together with synthetic project/navigation
providers. The real route adapter passes the same workspace ID used by the middle
workspace panel; no name matching or copied task state determines a destination.

## Validation and coordinated release

Actual-container DOM checks at390/1440 cover delayed history, rapid workspace
switches sharing an issue thread, close/Back, separate drafts/replies and reload,
late successful and failed sends, exact uncertain retries, an ordinary send after
a reply, storage-write failure, keyboard/pointer resizing and full-width state.
Isolated Chromium at390/1440 additionally exercises native pointer capture/drag,
keyboard bounds, full-width/restore geometry, mobile Back/sheet behavior, rapid
route changes, reload and exact workspace versus project POST targets. It uses
synthetic APIs and the incumbent timestamp CSS; no real messages/auth are changed.
Physical-phone or served-live acceptance is not claimed.

Reply, Jump, explicit management, neutral dispatch presentation and independent
unread/attention regressions remain in the existing CI test step. No Python,
storage/API contract, credential, model/effort or Recommend setting changes.
The routing/sizing fixes are frontend-only additions to the already coordinated
Reply/Jump/management/Preserve release. Staging was notified before packaging and
owns the single final hosted frontend build/activation and deployed notice.
This workspace builds no production package and performs no deployment/reload,
backend/agent restart or competing activation. Keep all live timestamp/collapsible,
CU/Stop and private backfill/rollback pins from the existing handoff.
