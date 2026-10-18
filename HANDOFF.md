# Pickup

Current stream: [Dot dispatch notes](DOT_DISPATCH_NOTES.md), preserving
[PR271's issue/error contract](DOT_WORKSPACE_ISSUE_CONTEXT.md).

Notes are driven by known accepted executions, scoped against native read-only
execution/session/workspace/issue state and existing owner grants. The explicit
internal note writer creates no owner message/event/reply authorization. Journal
and chat uniqueness prevent duplicate notes; the existing publisher recovers note
failures without sending another prompt. Bodies contain fixed safe purpose and
execution ID only. Native/manual prompts do not enter this connector path.

34 connector tests, 66 sidechat tests and full private-adapter mocked acceptance
pass, including the unchanged PR271 cases. Connector/publisher adoption from
8c5b505df is live (00:18:09 UTC); cached registered status adds dispatch_notes
with every original field unchanged. PR272 targets staging; full CI remains
separate. Exact pins and private receipt provenance are in the protocol doc.
No validation agent or live negative-start probe. Do not touch voice routing or the separate backend release.

Backend queue/setup-to-execution correlation and backend-response loss without a
captured execution ID remain unsupported; see exact limits in the protocol doc.
Full previous pickup remains in [HANDOFF history](HANDOFF_HISTORY_20261017.md).
