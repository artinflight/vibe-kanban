# e3e1 historical review compatibility repair

WHAT: repair Staging evidence f2642af3d and PR150's real-log/CI failures in an
isolated feature branch based on combined 2bc909d6375e13d0dd47f370eec0100fae3b2075.
WHY: the pinned SDK predates deployed goal-cleared/sleep notifications, while
MCP-only fixture prerequisites and two oversized ApiError return values fail CI.
CONTEXT: no Staging edit, production deployment, agent launch, credential/routing
change or live read-marker operation is authorized in this repair.
SUCCESS: exact four historical reply identities replay successfully, strict damaged
input/writer closure and receipt races stay fail closed, and relevant CI passes.

The compatibility branch handles only thread/goal/cleared and item/started or
item/completed with type=sleep before the pinned typed SDK parser. Required IDs
are nonempty; duration and lifecycle timestamps are unsigned integral values.
Unknown fields in these explicit parameter/item shapes, missing/invalid fields,
unknown native methods/items and malformed JSON remain rejected. These events
contain no report text/index and do not change normalization output. The normal
UI parser is unchanged. Sanitized notification shapes are checked in; retained
private historical logs remain external and unchanged, with raw hash checks.

The HTTP fixtures use canonical compiled-checkout dev_assets only, assert debug
mode before choosing storage, and require the SSD on the MCP host. The optional
VK_REVIEW_ACCEPTANCE_ROOT must match exactly when supplied. No home/XDG fallback
or Vibe application is constructed. Seven self-contained HTTP tests run normally
in CI; the installed dot-connector test is explicitly ignored by default and run
separately on MCP against a disposable loopback backend/private ledger. It is not
part of any claimed default-CI pass. No test submits genuine delivery evidence.

The reducer returns a boxed ApiError and source validation a small static error;
callers preserve the existing HTTP errors. No Clippy warning is suppressed.

Historical log replay does not populate a successful historical writer fence.
Closure proof is still mandatory before marking; the four live approvals stay
blocked until the release owner has supported closure validation and safe backend
adoption. Root's actual delivered/handled event -> scoped receipt submission is
still needed: cached14 tool metadata/no client delivery callback prevents an
end-to-end automatic-delivery claim. No polling or inferred delivery is added.

Acceptance and final artifact bindings are supplied in the maintenance handoff.

The first compatibility replay passes all native lines and yields all four approved
text hashes unchanged. Full finite replay indices are AutoSwitch236 (approved78),
Visily57, categorization103 (approved92), watcher30. Exact historical receipt
eligibility therefore remains false; no index translation or new source evidence
is invented. The earlier failing exact-index receipt remains retained. Independent
replay acceptance checks the actual full index/hash and production reducer, while
separately asserting/reporting that the original approved identity does not match.

First draft CI exposed assertions_on_constants on the fixture's debug assertion.
The guard is now a compile-time const assertion, as required by Clippy, without
suppression or removal. Release-mode fixture compilation is rejected before any
storage access. Original CI/failure receipts remain in the maintenance evidence.

Full nextest CI then reached the real-writer integration fixture after the earlier
HTTP fail-fast blocker and found its duplicated MCP-only prerequisite. HTTP and
writer fixtures now share the same checkout/debug/SSD isolation guard. Existing
writer closure and damage checks are unchanged; run both suites without the
optional root environment variable to verify CI prerequisites explicitly.
