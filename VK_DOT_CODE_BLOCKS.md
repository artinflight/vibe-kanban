# Dot Chat fenced code

The shared `DotMessageBody` renderer is used by project and workspace chats.
Only backtick/tilde fenced blocks are formatted; ordinary text, raw HTML-like
text and reply excerpts keep their existing readable plain-text presentation.
Opening fences accept up to three spaces. Closing fences must use the same
character and at least the opening length. Unclosed fences extend to the message
end, including updated history. Content inside fences is never trimmed, dedented
or newline-normalized for display or Copy; CRLF, tabs and trailing blanks remain.

Syntax coloring reuses the workspace editor's `@lexical/code` Prism tokenizer
and `CODE_HIGHLIGHT_CLASSES`. React renders token text/spans, never raw HTML.
Unknown/missing languages remain plain. Blocks over 50,000 characters also remain
plain to bound synchronous highlighting while retaining full content and Copy.
Long lines scroll inside the block; vertical content remains in message flow so
existing end-of-message read detection is retained. Code and ordinary message
text retain the pending workspace-matched 1rem sizing; mobile inputs stay16px.

Each block has an always-visible, keyboard-accessible Copy button, a focusable
code region and a live success/failure announcement. Mobile controls have44px
minimum targets. Copy uses `navigator.clipboard.writeText` with the original
content (including empty code), shows success only after resolution and reports
rejection/unavailable API with retry/manual-copy guidance. Updating/unmounting a
block invalidates an earlier in-flight copy result. No conversation mutation is
part of Copy. No persistent state, permission, backend or dependency changes.

`test-code-blocks-ui.mjs` exercises the real container/renderer in both scopes,
fence boundaries/CRLF, escaping, exact copied text, empty/unknown blocks,
clipboard rejection/retry, updated messages and unchanged reply/read/attention
state. Resource-admitted browser acceptance additionally checks390/1440 layout,
computed text/token colors, long lines, reload and destination drafts/replies.
Formatting, hosted frontend checks and artifact identity are separate evidence.

Bundle with pending typography source3cd0a6e63. This request authorizes preparation
and tests only: frontend activation is explicitly blocked until separate owner
approval. Staging retains release coordination; no services, current assets,
conversation state, settings, model/effort or Recommend routing may be changed.
Exact operational resource and candidate receipts stay in private handoffs.
