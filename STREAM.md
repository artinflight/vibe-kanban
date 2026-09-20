# VK::Chat Scroll Position

Scope: shared frontend conversation scrolling. Reopening/switching chats and
returning from a hidden browser tab or restored page resume at the bottom.
Preserve initial-bottom intent across coalesced history updates, start bottom
following during initial layout, and clear stale smooth-scroll deadlines on an
instant jump. Manual scrolling up remains supported while reading.

Validation: eight Chromium hook-harness scenarios pass via
`scripts/testing/run-chat-scroll-browser.mjs`. The harness exercises real DOM
scrolling and shared hooks; visibility/pageshow events are simulated. Full live
chat navigation and mobile app switching have not been exercised. See HANDOFF.md
for commands and remaining review. Frontend-only deployment is authorized and in preparation; see HANDOFF.md.
The layout observer also handles delayed unvirtualized tail resizing.
