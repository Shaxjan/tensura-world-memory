PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  tags_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS location_edges (
  a TEXT NOT NULL REFERENCES locations(id),
  b TEXT NOT NULL REFERENCES locations(id),
  travel_minutes INTEGER NOT NULL CHECK(travel_minutes > 0),
  PRIMARY KEY(a,b)
);

CREATE TABLE IF NOT EXISTS actors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  is_player INTEGER NOT NULL DEFAULT 0 CHECK(is_player IN (0,1)),
  location_id TEXT REFERENCES locations(id),
  home_location_id TEXT REFERENCES locations(id),
  work_location_id TEXT REFERENCES locations(id),
  status TEXT NOT NULL DEFAULT 'idle',
  cash_copper INTEGER NOT NULL DEFAULT 0 CHECK(cash_copper >= 0),
  energy INTEGER NOT NULL DEFAULT 100 CHECK(energy BETWEEN 0 AND 100),
  mood INTEGER NOT NULL DEFAULT 0 CHECK(mood BETWEEN -100 AND 100),
  personality_json TEXT NOT NULL DEFAULT '{}',
  next_action_at INTEGER NOT NULL DEFAULT 0,
  travel_destination TEXT REFERENCES locations(id),
  travel_arrival_at INTEGER
);

CREATE TABLE IF NOT EXISTS needs (
  actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
  hunger INTEGER NOT NULL DEFAULT 0 CHECK(hunger BETWEEN 0 AND 100),
  fatigue INTEGER NOT NULL DEFAULT 0 CHECK(fatigue BETWEEN 0 AND 100),
  loneliness INTEGER NOT NULL DEFAULT 0 CHECK(loneliness BETWEEN 0 AND 100),
  danger INTEGER NOT NULL DEFAULT 0 CHECK(danger BETWEEN 0 AND 100),
  updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS need_accumulators (
  actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
  hunger_minutes INTEGER NOT NULL DEFAULT 0 CHECK(hunger_minutes >= 0),
  fatigue_minutes INTEGER NOT NULL DEFAULT 0 CHECK(fatigue_minutes >= 0),
  loneliness_minutes INTEGER NOT NULL DEFAULT 0 CHECK(loneliness_minutes >= 0),
  danger_minutes INTEGER NOT NULL DEFAULT 0 CHECK(danger_minutes >= 0)
);

CREATE TABLE IF NOT EXISTS preferences (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  weight INTEGER NOT NULL CHECK(weight BETWEEN -100 AND 100),
  PRIMARY KEY(actor_id,tag)
);

CREATE TABLE IF NOT EXISTS relationships (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  affinity INTEGER NOT NULL DEFAULT 0 CHECK(affinity BETWEEN -100 AND 100),
  trust INTEGER NOT NULL DEFAULT 0 CHECK(trust BETWEEN -100 AND 100),
  respect INTEGER NOT NULL DEFAULT 0 CHECK(respect BETWEEN -100 AND 100),
  fear INTEGER NOT NULL DEFAULT 0 CHECK(fear BETWEEN 0 AND 100),
  updated_at INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(actor_id,target_id)
);

CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 100),
  target_json TEXT NOT NULL DEFAULT '{}',
  progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
  status TEXT NOT NULL DEFAULT 'active',
  created_at INTEGER NOT NULL,
  completed_at INTEGER,
  deadline_minute INTEGER,
  source TEXT NOT NULL DEFAULT 'seed'
);
CREATE INDEX IF NOT EXISTS idx_goals_actor ON goals(actor_id,status,priority DESC);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at INTEGER NOT NULL,
  completed_at INTEGER,
  rationale TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plan_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  action TEXT NOT NULL,
  params_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  UNIQUE(plan_id,seq)
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  base_value_copper INTEGER NOT NULL DEFAULT 0 CHECK(base_value_copper >= 0),
  consumable INTEGER NOT NULL DEFAULT 0 CHECK(consumable IN (0,1))
);

CREATE TABLE IF NOT EXISTS inventory (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL REFERENCES items(id),
  qty INTEGER NOT NULL DEFAULT 0 CHECK(qty >= 0),
  PRIMARY KEY(actor_id,item_id)
);

CREATE TABLE IF NOT EXISTS location_resources (
  location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
  resource TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 0 CHECK(qty >= 0),
  capacity INTEGER NOT NULL DEFAULT 0 CHECK(capacity >= 0),
  PRIMARY KEY(location_id,resource)
);

CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id),
  delta_copper INTEGER NOT NULL,
  reason TEXT NOT NULL,
  balance_after INTEGER NOT NULL CHECK(balance_after >= 0)
);

CREATE TABLE IF NOT EXISTS facts (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  fact_key TEXT NOT NULL REFERENCES facts(key) ON DELETE CASCADE,
  learned_at INTEGER NOT NULL,
  source TEXT NOT NULL,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
  PRIMARY KEY(actor_id,fact_key)
);

CREATE TABLE IF NOT EXISTS rumors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fact_key TEXT REFERENCES facts(key) ON DELETE SET NULL,
  origin_actor_id TEXT REFERENCES actors(id),
  origin_claim_json TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rumor_beliefs (
  rumor_id INTEGER NOT NULL REFERENCES rumors(id) ON DELETE CASCADE,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  claim_json TEXT NOT NULL,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
  heard_at INTEGER NOT NULL,
  source_actor_id TEXT REFERENCES actors(id),
  PRIMARY KEY(rumor_id,actor_id)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  actor_id TEXT REFERENCES actors(id),
  target_id TEXT REFERENCES actors(id),
  location_id TEXT REFERENCES locations(id),
  payload_json TEXT NOT NULL DEFAULT '{}',
  visibility TEXT NOT NULL DEFAULT 'hidden_engine'
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(world_minute,event_type);
CREATE INDEX IF NOT EXISTS idx_actor_next ON actors(is_player,next_action_at);
