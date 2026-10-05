ALTER TABLE observations
    ADD COLUMN IF NOT EXISTS area_id TEXT,
    ADD COLUMN IF NOT EXISTS site_id TEXT,
    ADD COLUMN IF NOT EXISTS drone_id TEXT,
    ADD COLUMN IF NOT EXISTS parent_observation_id TEXT;

CREATE INDEX IF NOT EXISTS idx_observations_area_site_time
    ON observations (area_id, site_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_observations_mission
    ON observations (mission_id);
