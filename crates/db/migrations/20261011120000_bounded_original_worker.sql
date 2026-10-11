CREATE TABLE bounded_worker_grants (
    id BLOB PRIMARY KEY NOT NULL,
    contract_digest TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('active','suspended','revoked','ready')),
    reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE bounded_worker_attempts (
    id BLOB PRIMARY KEY NOT NULL,
    grant_id BLOB NOT NULL REFERENCES bounded_worker_grants(id),
    caller BLOB NOT NULL,
    invocation TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reserved','dispatching','completed','uncertain')),
    execution BLOB,
    UNIQUE(grant_id,caller,invocation)
);
CREATE UNIQUE INDEX bounded_worker_one_pending ON bounded_worker_attempts(grant_id)
    WHERE state IN ('reserved','dispatching','uncertain');
