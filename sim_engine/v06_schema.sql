PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS campaign_archives (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_path TEXT NOT NULL UNIQUE,
  source_version TEXT,
  sha256 TEXT NOT NULL,
  byte_count INTEGER NOT NULL CHECK(byte_count >= 0),
  payload_text TEXT NOT NULL,
  archived_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_metadata (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  source_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_field_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  field_key TEXT NOT NULL,
  status TEXT NOT NULL,
  source_path TEXT,
  source_value_json TEXT,
  engine_target TEXT,
  note TEXT
);

CREATE TABLE IF NOT EXISTS migration_blockers (
  code TEXT PRIMARY KEY,
  detail TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS migration_capabilities (
  command TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
  reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fund_accounts (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  balance_copper INTEGER CHECK(balance_copper >= 0),
  certainty TEXT NOT NULL,
  source_path TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS migration_rehearsal_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  source_version INTEGER,
  rehearsal_ready INTEGER NOT NULL CHECK(rehearsal_ready IN (0,1)),
  live_cutover_ready INTEGER NOT NULL CHECK(live_cutover_ready IN (0,1)),
  report_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gm_turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  turn_key TEXT NOT NULL UNIQUE,
  player_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  raw_text TEXT NOT NULL,
  status TEXT NOT NULL,
  proposal_json TEXT NOT NULL DEFAULT '{}',
  validation_json TEXT NOT NULL DEFAULT '{}',
  engine_result_json TEXT NOT NULL DEFAULT '{}',
  gm_packet_json TEXT NOT NULL DEFAULT '{}',
  narration_contract_json TEXT NOT NULL DEFAULT '{}',
  checkpoint_hash TEXT,
  public_result_json TEXT NOT NULL DEFAULT '{}',
  narration_text TEXT,
  created_at INTEGER NOT NULL,
  completed_at INTEGER
);

CREATE TABLE IF NOT EXISTS checkpoints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  player_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  turn_id INTEGER REFERENCES gm_turns(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
  state_hash TEXT NOT NULL,
  state_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_player ON checkpoints(player_id,id DESC);
