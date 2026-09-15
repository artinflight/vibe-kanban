# Codex Model Selector Regression

The September15 acceptance verified retained model selections and actual GPT-6
submissions, but missed catalog contents and available reasoning controls. The
running backend still advertises GPT5.1-5.6 and omits GPT-6. The preset fallback
adds an unknown model with no reasoning options, leaving only the retained Xhigh
label. This is a separate acceptance gap, not lost conversation history.

The Codex-only frontend adapter filters GPT versions below5.6 after preset
insertion, adds GPT-6 Astra, and supplies Low/Medium/High/Xhigh/Max if its
capabilities are absent. It preserves an already-discovered nonempty capability
list, other executors, custom non-GPT models and stored defaults. No API writes
or migrations happen during normalization. Old chat selections are not reset.
These five efforts are supported by the host native catalog and current VK
ReasoningEffort enum. Native Ultra is intentionally excluded until backend
support exists; this patch does not pretend that enabling a label enables it.

Regression checks cover old-model filtering, the missing/placeholder GPT-6
catalog entry, existing capabilities and other executors. Desktop/mobile browser
acceptance must open the actual reasoning dropdown, not just assert Xhigh is
visible. Future restart acceptance must include these catalog/control checks.

Deployment evidence lives under `/mnt/vk-storage/vk-model-selector-20260915`.
Only a tested frontend release is published; previous assets and Desktop recovery
archive are retained. Green PID1674994 stays running and Blue2150526 stays paused.
Saved messages, profiles and chat drafts are not changed by publication. The
paused Blue cutback frontend must retain this correction, not restore the stale
catalog UI. Integration into staging is required before another release build.
