CREATE TABLE project_navigation_order (
    id INTEGER PRIMARY KEY NOT NULL CHECK (id = 1),
    project_ids TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(project_ids)),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
);

INSERT INTO project_navigation_order (id, project_ids)
SELECT
    1,
    COALESCE(json_extract(payload, '$.data.local_project_order'), '[]')
FROM scratch
WHERE scratch_type = 'UI_PREFERENCES'
ORDER BY updated_at DESC
LIMIT 1
ON CONFLICT(id) DO NOTHING;

INSERT OR IGNORE INTO project_navigation_order (id, project_ids)
VALUES (1, '[]');

CREATE TABLE project_navigation_order_history (
    revision INTEGER PRIMARY KEY NOT NULL,
    project_ids TEXT NOT NULL CHECK (json_valid(project_ids)),
    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
);

INSERT INTO project_navigation_order_history (revision, project_ids)
SELECT revision, project_ids FROM project_navigation_order;

CREATE TABLE workspace_card_colors (
    workspace_id TEXT PRIMARY KEY NOT NULL,
    color TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
);

INSERT OR IGNORE INTO workspace_card_colors (workspace_id, color)
SELECT colors.key, colors.value
FROM scratch,
     json_each(json_extract(scratch.payload, '$.data.workspace_colors')) AS colors
WHERE scratch.scratch_type = 'UI_PREFERENCES'
  AND json_type(colors.value) = 'text';

CREATE TABLE workspace_card_color_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    color TEXT,
    revision INTEGER NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
);

INSERT INTO workspace_card_color_history (workspace_id, color, revision)
SELECT workspace_id, color, revision FROM workspace_card_colors;

ALTER TABLE saved_chat_messages ADD COLUMN revision INTEGER NOT NULL DEFAULT 1;

CREATE TABLE saved_chat_message_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    position INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec'))
);

INSERT INTO saved_chat_message_history (
    message_id, title, content, position, revision
)
SELECT id, title, content, position, revision FROM saved_chat_messages;

CREATE TRIGGER saved_chat_messages_history_after_update
AFTER UPDATE ON saved_chat_messages
BEGIN
    INSERT INTO saved_chat_message_history (
        message_id, title, content, position, revision
    ) VALUES (
        NEW.id, NEW.title, NEW.content, NEW.position, NEW.revision
    );
END;

CREATE TRIGGER saved_chat_messages_history_after_insert
AFTER INSERT ON saved_chat_messages
BEGIN
    INSERT INTO saved_chat_message_history (
        message_id, title, content, position, revision
    ) VALUES (
        NEW.id, NEW.title, NEW.content, NEW.position, NEW.revision
    );
END;

CREATE TRIGGER saved_chat_messages_history_before_delete
BEFORE DELETE ON saved_chat_messages
BEGIN
    INSERT INTO saved_chat_message_history (
        message_id, title, content, position, revision, deleted
    ) VALUES (
        OLD.id, OLD.title, OLD.content, OLD.position, OLD.revision + 1, 1
    );
END;
