-- Trinity Intelligence Platform - Event Store Schema

CREATE TABLE IF NOT EXISTS events (
    event_id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(255) NOT NULL,
    event_data TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);

-- Partitioning by month for performance (future optimization)
-- CREATE TABLE events_2025_11 PARTITION OF events FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
