-- Bookmarks are independent of attention/read flags. Keep removal tombstones so
-- an older browser's one-time local import cannot resurrect a removed bookmark.
CREATE TABLE read_later_preferences (
    user_scope TEXT NOT NULL,
    item_kind TEXT NOT NULL CHECK (item_kind IN ('workspace', 'project', 'issue', 'notification')),
    item_id TEXT NOT NULL,
    item_json TEXT NOT NULL,
    saved INTEGER NOT NULL CHECK (saved IN (0, 1)),
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    PRIMARY KEY (user_scope, item_kind, item_id)
);

-- An acknowledged write may have lost its HTTP response. Retrying it after a
-- newer device action must not undo that newer action.
CREATE TABLE read_later_action_receipts (
    user_scope TEXT NOT NULL,
    change_id TEXT NOT NULL,
    PRIMARY KEY (user_scope, change_id)
);
