--sql/001_init.sql
CREATE SCHEMA IF NOT EXISTS agent;

CREATE TABLE IF NOT EXISTS agent.smoke_test (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  note TEXT NOT NULL
);

INSERT INTO agent.smoke_test(note) values ('db init ok');
