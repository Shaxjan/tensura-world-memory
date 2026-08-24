PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scene_resolution_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pending_id INTEGER NOT NULL REFERENCES scene_pending_resolution(id) ON DELETE CASCADE,
  world_minute INTEGER NOT NULL,
  resolution_kind TEXT NOT NULL,
  outcome TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  resolver TEXT NOT NULL,
  authority TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_journal (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  world_minute INTEGER NOT NULL,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  before_hash TEXT NOT NULL,
  after_hash TEXT NOT NULL,
  committed_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_cutover (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  source_live_version INTEGER NOT NULL,
  legacy_pointer_json TEXT NOT NULL,
  legacy_pointer_blob_sha TEXT NOT NULL,
  mode TEXT NOT NULL,
  journal_policy_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
