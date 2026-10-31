-- DOMINIUM Backlog / DataSnap: evolução aditiva do schema privado.
-- Aplicada no Supabase DOMINIUM em 2026-10-31 02:28:26 UTC.
-- Nenhuma coluna ou linha antiga é removida.
-- Nenhum acesso é concedido a anon ou authenticated.
ALTER TABLE backlog_lab.history
  ADD COLUMN IF NOT EXISTS source_profile text,
  ADD COLUMN IF NOT EXISTS source_id_os bigint,
  ADD COLUMN IF NOT EXISTS source_verification text,
  ADD COLUMN IF NOT EXISTS source_status text,
  ADD COLUMN IF NOT EXISTS datasnap_captured_at timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS backlog_history_datasnap_identity_v1
  ON backlog_lab.history (source_profile, source_id_os, activity_date)
  WHERE source_profile IS NOT NULL AND source_id_os IS NOT NULL;
CREATE INDEX IF NOT EXISTS backlog_history_datasnap_filter_v1
  ON backlog_lab.history (source_profile, activity_date, baixa_code)
  WHERE source_profile IS NOT NULL;
CREATE INDEX IF NOT EXISTS backlog_history_datasnap_contract_v1
  ON backlog_lab.history (contract, activity_date);

CREATE TABLE IF NOT EXISTS backlog_lab.datasnap_checkpoints (
  profile text PRIMARY KEY CHECK (profile IN ('natal','fortaleza','mossoro','recife')),
  last_completed_day date NOT NULL,
  rows_written integer NOT NULL DEFAULT 0 CHECK (rows_written >= 0),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS backlog_lab.datasnap_sync_runs (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_mode text NOT NULL CHECK (run_mode IN ('probe','batch','import')),
  status text NOT NULL CHECK (status IN ('running','completed','failed','paused','interrupted')),
  profile text CHECK (profile IS NULL OR profile IN ('natal','fortaleza','mossoro','recife')),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  total_tasks integer NOT NULL DEFAULT 0 CHECK (total_tasks >= 0),
  done_tasks integer NOT NULL DEFAULT 0 CHECK (done_tasks >= 0),
  imported integer NOT NULL DEFAULT 0 CHECK (imported >= 0),
  unconfirmed integer NOT NULL DEFAULT 0 CHECK (unconfirmed >= 0),
  error_kind text
);
CREATE INDEX IF NOT EXISTS backlog_datasnap_runs_recent_v1
  ON backlog_lab.datasnap_sync_runs (started_at DESC);

ALTER TABLE backlog_lab.datasnap_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE backlog_lab.datasnap_sync_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE backlog_lab.history ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE backlog_lab.datasnap_checkpoints, backlog_lab.datasnap_sync_runs
  FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA backlog_lab TO service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE
  backlog_lab.history, backlog_lab.datasnap_checkpoints, backlog_lab.datasnap_sync_runs
  TO service_role;
