PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'place'
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
  energy INTEGER NOT NULL DEFAULT 100 CHECK(energy BETWEEN 0 AND 100),
  mood INTEGER NOT NULL DEFAULT 0 CHECK(mood BETWEEN -100 AND 100),
  cash_copper INTEGER NOT NULL DEFAULT 0 CHECK(cash_copper >= 0),
  personality_json TEXT NOT NULL DEFAULT '{}',
  goals_json TEXT NOT NULL DEFAULT '[]',
  travel_destination TEXT REFERENCES locations(id),
  travel_arrival_at INTEGER,
  next_action_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS preferences (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  weight INTEGER NOT NULL CHECK(weight BETWEEN -100 AND 100),
  PRIMARY KEY(actor_id, tag)
);

CREATE TABLE IF NOT EXISTS relationships (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  affinity INTEGER NOT NULL DEFAULT 0 CHECK(affinity BETWEEN -100 AND 100),
  trust INTEGER NOT NULL DEFAULT 0 CHECK(trust BETWEEN -100 AND 100),
  fear INTEGER NOT NULL DEFAULT 0 CHECK(fear BETWEEN 0 AND 100),
  respect INTEGER NOT NULL DEFAULT 0 CHECK(respect BETWEEN -100 AND 100),
  updated_at INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(actor_id, target_id)
);

CREATE TABLE IF NOT EXISTS facts (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  source TEXT NOT NULL DEFAULT 'world'
);

CREATE TABLE IF NOT EXISTS knowledge (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  fact_key TEXT NOT NULL REFERENCES facts(key) ON DELETE CASCADE,
  learned_at INTEGER NOT NULL,
  source TEXT NOT NULL,
  confidence INTEGER NOT NULL DEFAULT 100 CHECK(confidence BETWEEN 0 AND 100),
  PRIMARY KEY(actor_id, fact_key)
);

CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id),
  delta_copper INTEGER NOT NULL,
  reason TEXT NOT NULL,
  balance_after INTEGER NOT NULL CHECK(balance_after >= 0)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  actor_id TEXT REFERENCES actors(id),
  target_id TEXT REFERENCES actors(id),
  location_id TEXT REFERENCES locations(id),
  payload_json TEXT NOT NULL DEFAULT '{}',
  visibility TEXT NOT NULL DEFAULT 'world'
);

CREATE TABLE IF NOT EXISTS scheduled_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  due_minute INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  actor_id TEXT REFERENCES actors(id),
  target_id TEXT REFERENCES actors(id),
  location_id TEXT REFERENCES locations(id),
  payload_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_scheduled_due ON scheduled_events(status, due_minute);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(world_minute);
CREATE INDEX IF NOT EXISTS idx_actors_next ON actors(is_player, next_action_at);
