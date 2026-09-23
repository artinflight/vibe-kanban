# Ownership-Capable Blue Deployment

## Authorization And Scope

After ownership implementation, the operator authorized the complete cutover
while stepping away. This supersedes the previous preparation-only instruction.
PR124 merges the lock barrier and explicit ownership handover into staging
1b31e18748ea347c7303688deb9eb1704a764550. Build source f9dac41e4 has the same
application tree; frontend remains the previously validated staging package.
No GitHub Actions are used.

## Initial Legacy Transition

Running Green1674994 has no release/acquire endpoints. This first transition
therefore stops that legacy process after draining work, rather than freezing
its lifetime capacity lock. Its original release and configuration are retained;
recovery starts that software against the same latest production data. This is
not a same-PID paused fallback. The limitation was disclosed before production
actions. Future handovers between ownership-capable builds can use explicit
release, pause, acquire and same-process latest-state return.

The actual one-time switch and recovery implementation is initial_transition.py
under /mnt/vk-storage/vk-blue-refresh-20260921. It rejects outstanding grants and
executions, preserves goal choices and issued grant history, and never restores
an older database or controller state. Recovery refuses to interrupt new work.
Historical frozen generations, missing histories and attachments are unchanged.

## Evidence And Continuation

The September23T154246Z attempt is consumed and preserved under its original
folder. Its marker and prior preparation records are archived in
before-ownership-transition-20260923T183659Z. This is a new separately authorized
attempt, not a retry of that controller state.

The old change journal was invalidated by a moved Python cache directory. A
fresh journal-ownership-20260923.sock and fresh online baseline replace it.
The final boundary must still be captured and verified on Desktop. Production
must not use replica data. All backup payloads stay on mounted SSD/Desktop.

Read cutover-attempt.json and its status.json before any action after an
interruption. Never repeat a consumed handover. Resume only the original
maintenance conversation. Complete live preservation, model menus, saved
messages, attachment round-trip, Turn Steer/Stop/goals, desktop/mobile and CU
reconciliation checks before one final report. This document alone is not
evidence that activation or acceptance succeeded.
