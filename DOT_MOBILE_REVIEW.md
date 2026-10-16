> Preserved from original UI commit `c71c2ee7d`. This describes prepared work,
> not completion of the separately owned mobile task. See
> [the reconciled handoff](DOT_INTEGRATION_HANDOFF.md).

# Dot on Android: verification and remaining acceptance

## Existing live behavior

At widths <=767px, WorkspacesLayout mounts RightSidebar in the mobile Git tab,
without the desktop width wrapper. Dot is below Notes. The separate Chat tab is
the coding agent. The shared mobile viewport hook responds to visualViewport
resize/scroll and input focus, including textarea and pairing input.
Pairing uses standard same-origin Fetch and Secure/HttpOnly/SameSite cookies.
The phone requires its own single-use pairing code; desktop pairing is not
transferred. VK Dev project scope and indefinite-until-revocation sessions remain
unchanged. The phone must already reach and trust https://vibe.local. No network,
certificate, access or security changes were made for this review.

## Prepared responsive corrections

At mobile widths only: 44px minimum action targets, 16px inputs, wrapped scope
labels, compact gutters, no desktop keyboard-shortcut hint, safe-area composer
padding, and outer chat scrolling when the keyboard leaves insufficient room.
Desktop CSS and request/idempotency/session code remain unchanged.

## Acceptance boundary

No browser or phone is exposed through computer-use inventory (apps=[],
browsers=[]). DOM checks can exercise pairing/composer/retry logic but cannot
verify rendered dimensions or Android keyboard behavior. Do not call this
phone-tested or activate this candidate until a mobile visual check is available.
Test 360/390/412px portrait and landscape, keyboard open, long scope/error text,
Notes expanded/collapsed, pairing, send, history scrolling and retry. Do not
send synthetic events or reuse a consumed pairing code. Preserve tab storage.

## Checks completed

Repository format passed after adding the installed Rust runtime to PATH.
Existing DOM-only live UI tests passed: pairing gate, workspace transport,
lost-response/reload idempotency, receipt distinction, and logout. Local-web
TypeScript, ops check, and diff whitespace checks passed. These are not rendered
mobile geometry tests. No external messages, browser grants or subscriptions
were created during this review.
