--sql/001_init.sql
CREATE SCHEMA IF NOT EXISTS agent;

-- used for initial setup and smoke test
CREATE TABLE IF NOT EXISTS agent.smoke_test (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  note TEXT NOT NULL
);

-- used for initial setup and smoke test
INSERT INTO agent.smoke_test(note) values ('db init ok');

-- Pipelines registry
CREATE TABLE IF NOT EXISTS agent.pipelines (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    owner TEXT,
    slo_runtime_sec INTEGER NOT NULL DEFAULT 300,
    slo_freshness_sec INTEGER NOT NULL DEFAULT 3600,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Individual pipeline runs
CREATE TABLE IF NOT EXISTS agent.pipeline_runs(
    run_id TEXT PRIMARY KEY,
    pipeline_id BIGINT NOT NULL REFERENCES agent.pipelines(id),
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    attempt INTEGER NOT NULL DEFAULT 0,
    watermark TIMESTAMPTZ,
    schema_hash TEXT,
    output_path TEXT,
    error_signature TEXT,
    runtime_sec INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Baselines for verification
CREATE TABLE IF NOT EXISTS agent.baselines (
    pipeline_id BIGINT NOT NULL REFERENCES agent.pipelines(id),
    metric_name TEXT NOT NULL,
    p50 DOUBLE PRECISION,
    p95 DOUBLE PRECISION,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pipeline_id, metric_name)
);

-- Incidents trackers by agent
CREATE TABLE IF NOT EXISTS agent.incidents(
    incident_id BIGSERIAL PRIMARY KEY,
    pipeline_id BIGINT NOT NULL REFERENCES agent.pipelines(id),
    run_id TEXT NULL REFERENCES agent.pipeline_runs(run_id),
    event_type TEXT NOT NULL,
    incident_type TEXT,
    confidence DOUBLE PRECISION,
    error_signature TEXT,
    summary TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'OPEN',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- Actions taken for an incident (audit trail)
CREATE TABLE IF NOT EXISTS agent.actions (
    action_id BIGSERIAL PRIMARY KEY,
    incident_id BIGINT NOT NULL REFERENCES agent.incidents(incident_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_level TEXT NOT NULL DEFAULT 'LOW',
    reuqires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'STARTED',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    outcome_summary TEXT,
    reversible BOOLEAN NOT NULL DEFAULT TRUE,
    rollback_ref TEXT
);

-- Case-based learning table (what worked last time)
CREATE TABLE IF NOT EXISTS agent.case_learning (
    key_hash TEXT PRIMARY KEY,
    incident_type TEXT NOT NULL,
    error_signature TEXT NOT NULL,
    pipeline_id BIGINT NOT NULL REFERENCES agent.pipelines(id),
    dataset TEXT,
    best_action_type TEXT,
    success_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed on piepline so that API works immediately
INSERT INTO agent.pipelines(name, owner, slo_runtime_sec, slo_freshness_sec)
VALUES ('orders_pipeline', 'demo', 300, 3600)
ON CONFLICT (name) DO NOTHING;
