PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mechanic_feature_policy (
  feature TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  authority TEXT NOT NULL,
  status TEXT NOT NULL,
  command TEXT,
  reason TEXT NOT NULL,
  activated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cutover_gate (
  gate_code TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  classification TEXT NOT NULL,
  detail TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS portable_checkpoint_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  source_version INTEGER,
  direction TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  table_count INTEGER NOT NULL,
  row_count INTEGER NOT NULL,
  byte_count INTEGER NOT NULL,
  ok INTEGER NOT NULL CHECK(ok IN (0,1)),
  note TEXT
);
