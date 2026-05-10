CREATE TABLE subagent_jobs (
    id                      BLOB PRIMARY KEY,
    session_id              BLOB NOT NULL,
    execution_process_id    BLOB NOT NULL,
    agent_id                TEXT NOT NULL,
    nickname                TEXT,
    status                  TEXT NOT NULL
                            CHECK (status IN ('unresolved','running','completed','not_found','failed')),
    completed_at            TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (execution_process_id) REFERENCES execution_processes(id) ON DELETE CASCADE,
    UNIQUE (execution_process_id, agent_id)
);

CREATE INDEX idx_subagent_jobs_session_id ON subagent_jobs(session_id);
CREATE INDEX idx_subagent_jobs_execution_process_id ON subagent_jobs(execution_process_id);
CREATE INDEX idx_subagent_jobs_status ON subagent_jobs(status);
