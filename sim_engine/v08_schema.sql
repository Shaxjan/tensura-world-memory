PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS financial_account_state (
  account_id TEXT PRIMARY KEY,
  account_type TEXT NOT NULL,
  balance_copper INTEGER,
  known_principal_copper INTEGER,
  certainty TEXT NOT NULL,
  holder_key TEXT,
  status TEXT NOT NULL,
  as_of_version INTEGER NOT NULL,
  source_path TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS money_reconciliation_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL,
  source_version INTEGER,
  source_path TEXT NOT NULL,
  classification TEXT NOT NULL,
  effect_copper INTEGER,
  evidence_json TEXT NOT NULL DEFAULT '{}',
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_money_recon_account
  ON money_reconciliation_evidence(account_id, source_version);

CREATE TABLE IF NOT EXISTS money_reconciliation_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_version INTEGER NOT NULL,
  reconciled_through_version INTEGER NOT NULL,
  baseline_ready INTEGER NOT NULL CHECK(baseline_ready IN (0,1)),
  stale_after_version INTEGER,
  report_json TEXT NOT NULL
);
