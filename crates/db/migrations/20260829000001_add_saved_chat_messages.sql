CREATE TABLE saved_chat_messages (
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
);

-- Preserve messages written by releases that stored them in the global
-- UI_PREFERENCES scratch payload. Invalid entries are ignored.
INSERT OR IGNORE INTO saved_chat_messages (id, title, content, position)
SELECT
    json_extract(message.value, '$.id'),
    trim(json_extract(message.value, '$.title')),
    json_extract(message.value, '$.content'),
    CAST(message.key AS INTEGER)
FROM scratch, json_each(json_extract(scratch.payload, '$.data.saved_chat_messages')) AS message
WHERE scratch.scratch_type = 'UI_PREFERENCES'
  AND json_type(message.value, '$.id') = 'text'
  AND json_type(message.value, '$.title') = 'text'
  AND json_type(message.value, '$.content') = 'text'
  AND trim(json_extract(message.value, '$.title')) <> ''
  AND trim(json_extract(message.value, '$.content')) <> '';
