PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scene_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  turn_key TEXT NOT NULL UNIQUE,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL,
  action_kind TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  components_json TEXT NOT NULL DEFAULT '[]',
  resolution_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  effect_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scene_pending_resolution (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_action_id INTEGER NOT NULL REFERENCES scene_actions(id) ON DELETE CASCADE,
  resolution_kind TEXT NOT NULL,
  target_key TEXT,
  target_text TEXT,
  state_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at INTEGER NOT NULL,
  resolved_at INTEGER
);

CREATE TABLE IF NOT EXISTS scene_objects (
  object_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  holder_key TEXT,
  state_json TEXT NOT NULL DEFAULT '{}',
  certainty TEXT NOT NULL,
  source_path TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scene_local_state (
  actor_id TEXT PRIMARY KEY,
  place_text TEXT,
  certainty TEXT NOT NULL,
  source_path TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS autonomy_runtime (
  commitment_key TEXT PRIMARY KEY REFERENCES autonomous_commitments(commitment_key) ON DELETE CASCADE,
  handler TEXT NOT NULL,
  next_due_at INTEGER NOT NULL,
  cadence_minutes INTEGER NOT NULL CHECK(cadence_minutes > 0),
  tick_count INTEGER NOT NULL DEFAULT 0 CHECK(tick_count >= 0),
  last_run_at INTEGER,
  status TEXT NOT NULL,
  last_outcome_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS autonomy_execution_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  commitment_key TEXT NOT NULL,
  owner_key TEXT,
  handler TEXT NOT NULL,
  outcome_code TEXT NOT NULL,
  outcome_json TEXT NOT NULL,
  visible_to_player INTEGER NOT NULL DEFAULT 0 CHECK(visible_to_player IN (0,1))
);
