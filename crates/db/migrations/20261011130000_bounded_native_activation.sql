ALTER TABLE bounded_worker_attempts ADD COLUMN input_digest TEXT;
ALTER TABLE bounded_worker_attempts ADD COLUMN activated INTEGER NOT NULL DEFAULT 0 CHECK(activated IN (0,1));

-- Record input admission before native steering or queueing, including failures.
CREATE TABLE bounded_native_input_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id BLOB NOT NULL,
    native_resume INTEGER NOT NULL CHECK(native_resume IN (0,1))
);

-- Coverage is minted by the journaling backend, never by an invocation.
CREATE TABLE bounded_native_input_coverage (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    id BLOB NOT NULL
);
