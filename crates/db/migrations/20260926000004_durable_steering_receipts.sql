-- Steering uses the same delivery ledger, but it must never be consumed by the
-- follow-up queue or retried after an uncertain external acknowledgement.
ALTER TABLE agent_deliveries ADD COLUMN delivery_mode TEXT NOT NULL DEFAULT 'queue'
    CHECK (delivery_mode IN ('queue','steer'));
ALTER TABLE agent_deliveries ADD COLUMN steering_acknowledged_at TEXT;
