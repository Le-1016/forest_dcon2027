CREATE TABLE IF NOT EXISTS missions (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT UNIQUE NOT NULL,
    mission_type TEXT NOT NULL,
    target_lat DOUBLE PRECISION,
    target_lon DOUBLE PRECISION,
    target_alt DOUBLE PRECISION,
    target_class TEXT,
    priority TEXT,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'REQUESTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS observations (
    id BIGSERIAL PRIMARY KEY,
    observation_id TEXT UNIQUE NOT NULL,
    mission_id TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    camera_angle DOUBLE PRECISION,
    image_path TEXT,
    class TEXT,
    confidence DOUBLE PRECISION,
    ai_model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS drone_status (
    drone_id TEXT PRIMARY KEY,
    online BOOLEAN NOT NULL DEFAULT FALSE,
    battery DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    mode TEXT,
    mission_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO missions (
    mission_id,
    mission_type,
    target_lat,
    target_lon,
    target_alt,
    target_class,
    priority,
    reason,
    status
)
VALUES (
    'MISSION-001',
    'PATROL',
    34.6937,
    135.5023,
    40,
    'FOREST_AREA',
    'NORMAL',
    'INITIAL_DEMO',
    'REQUESTED'
)
ON CONFLICT (mission_id) DO NOTHING;
