PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS baseline_sources (
  source_path TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  byte_count INTEGER NOT NULL CHECK(byte_count >= 0),
  kind TEXT NOT NULL,
  authority TEXT NOT NULL,
  loaded_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_baselines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  baseline_key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_sha TEXT NOT NULL,
  authority TEXT NOT NULL,
  status TEXT NOT NULL,
  as_of_version INTEGER,
  UNIQUE(kind, baseline_key, source_path)
);

CREATE TABLE IF NOT EXISTS actor_position_claims (
  actor_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  region_id TEXT,
  location_text TEXT,
  precision TEXT NOT NULL,
  status TEXT NOT NULL,
  as_of_version INTEGER,
  source_path TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS relationship_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_key TEXT NOT NULL,
  target_key TEXT NOT NULL,
  evidence_key TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  source_path TEXT NOT NULL,
  authority TEXT NOT NULL,
  as_of_version INTEGER,
  UNIQUE(actor_key,target_key,evidence_key,source_path)
);

CREATE TABLE IF NOT EXISTS autonomous_commitments (
  commitment_key TEXT PRIMARY KEY,
  owner_key TEXT,
  kind TEXT NOT NULL,
  state_json TEXT NOT NULL,
  status TEXT NOT NULL,
  source_path TEXT NOT NULL,
  as_of_version INTEGER
);

CREATE TABLE IF NOT EXISTS fund_account_audit (
  account_id TEXT PRIMARY KEY,
  balance_copper INTEGER,
  certainty TEXT NOT NULL,
  exact_as_of_version INTEGER,
  later_mentions_json TEXT NOT NULL DEFAULT '[]',
  source_path TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS mechanical_calibrations (
  system_key TEXT NOT NULL,
  actor_key TEXT NOT NULL,
  value_json TEXT NOT NULL DEFAULT '{}',
  authority TEXT NOT NULL DEFAULT 'NON_CANON_MECHANICAL',
  status TEXT NOT NULL DEFAULT 'unrated',
  created_at INTEGER NOT NULL,
  PRIMARY KEY(system_key,actor_key)
);

CREATE TABLE IF NOT EXISTS cutover_worldgen_policy (
  system_key TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  seed_namespace TEXT NOT NULL,
  policy_json TEXT NOT NULL,
  authority TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocker_resolution (
  blocker_code TEXT PRIMARY KEY,
  classification TEXT NOT NULL,
  status TEXT NOT NULL,
  resolution TEXT NOT NULL,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  replacement_blocker TEXT
);
