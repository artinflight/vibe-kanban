# Private Dot dispatch notes

Branch `feat/dot-dispatch-notes`, stacked on preserved PR271 source. The new
[dispatch-note protocol](DOT_DISPATCH_NOTES.md) records accepted Dot-origin
execution receipts and writes one safe note into the existing private workspace
conversation, including a first thread with no owner message.

Scope: connector post-dispatch hooks/journal, explicit internal note writer,
read-only status, recovery through the existing publisher, tests and handoff.
Preserve PR271's deployed issue/error contract, PR270, all chats/access/history,
CU/Stop, current sidebar/mobile/frontend, models and permissions. No voice routing,
backend restart, actor launch or denied live negative-start probe.

34 public connector and 66 sidechat tests pass. Full private-adapter mocked
start/follow-up notes and PR271's 28 rejection vectors/27 incumbent controls pass.
Scoped connector/publisher adoption is live; actual cached status readback
preserves all prior fields. PR272 targets staging. Backend POST response loss
without an execution receipt, capacity queue IDs and sequential setup-to-agent correlation remain
explicit unsupported boundaries; never infer acceptance or resend prompts.

Full previous stream history remains in [STREAM history](STREAM_HISTORY_20261017.md).
