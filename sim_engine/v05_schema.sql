PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS intent_proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  raw_text TEXT NOT NULL,
  status TEXT NOT NULL,
  command TEXT,
  params_json TEXT NOT NULL DEFAULT '{}',
  missing_json TEXT NOT NULL DEFAULT '[]',
  ambiguities_json TEXT NOT NULL DEFAULT '[]',
  grounding_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS power_profiles (
  actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
  threat_rank TEXT NOT NULL DEFAULT 'E',
  magicules INTEGER NOT NULL DEFAULT 0 CHECK(magicules >= 0),
  physical INTEGER NOT NULL DEFAULT 10 CHECK(physical BETWEEN 0 AND 200),
  magic INTEGER NOT NULL DEFAULT 0 CHECK(magic BETWEEN 0 AND 200),
  control INTEGER NOT NULL DEFAULT 10 CHECK(control BETWEEN 0 AND 200),
  durability INTEGER NOT NULL DEFAULT 10 CHECK(durability BETWEEN 0 AND 200),
  regeneration INTEGER NOT NULL DEFAULT 0 CHECK(regeneration BETWEEN 0 AND 100),
  resistances_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS conditions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 100),
  source TEXT NOT NULL,
  applied_at INTEGER NOT NULL,
  expires_at INTEGER,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_conditions_actor ON conditions(actor_id,status,severity DESC);

CREATE TABLE IF NOT EXISTS treatments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  healer_id TEXT NOT NULL REFERENCES actors(id),
  target_id TEXT NOT NULL REFERENCES actors(id),
  method TEXT NOT NULL,
  check_id INTEGER REFERENCES checks(id),
  healed_hp INTEGER NOT NULL DEFAULT 0,
  conditions_removed_json TEXT NOT NULL DEFAULT '[]',
  success INTEGER NOT NULL CHECK(success IN (0,1))
);

CREATE TABLE IF NOT EXISTS social_bonds (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  affinity INTEGER NOT NULL DEFAULT 0 CHECK(affinity BETWEEN -100 AND 100),
  trust INTEGER NOT NULL DEFAULT 0 CHECK(trust BETWEEN -100 AND 100),
  respect INTEGER NOT NULL DEFAULT 0 CHECK(respect BETWEEN -100 AND 100),
  fear INTEGER NOT NULL DEFAULT 0 CHECK(fear BETWEEN 0 AND 100),
  obligation INTEGER NOT NULL DEFAULT 0 CHECK(obligation BETWEEN -100 AND 100),
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(actor_id,target_id)
);

CREATE TABLE IF NOT EXISTS relationship_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  event_key TEXT NOT NULL,
  summary TEXT NOT NULL,
  affinity_delta INTEGER NOT NULL DEFAULT 0,
  trust_delta INTEGER NOT NULL DEFAULT 0,
  respect_delta INTEGER NOT NULL DEFAULT 0,
  fear_delta INTEGER NOT NULL DEFAULT 0,
  obligation_delta INTEGER NOT NULL DEFAULT 0,
  memory_key TEXT
);

CREATE TABLE IF NOT EXISTS crime_witnesses (
  crime_id INTEGER NOT NULL REFERENCES crimes(id) ON DELETE CASCADE,
  witness_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  perception_total INTEGER NOT NULL,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
  willingness INTEGER NOT NULL CHECK(willingness BETWEEN 0 AND 100),
  status TEXT NOT NULL DEFAULT 'observed',
  PRIMARY KEY(crime_id,witness_id)
);

CREATE TABLE IF NOT EXISTS testimonies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crime_id INTEGER NOT NULL REFERENCES crimes(id) ON DELETE CASCADE,
  witness_id TEXT NOT NULL REFERENCES actors(id),
  credibility INTEGER NOT NULL CHECK(credibility BETWEEN 0 AND 100),
  submitted_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS evidence_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crime_id INTEGER NOT NULL REFERENCES crimes(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  strength INTEGER NOT NULL CHECK(strength BETWEEN 0 AND 100),
  decay_per_day INTEGER NOT NULL DEFAULT 5 CHECK(decay_per_day BETWEEN 0 AND 50),
  created_at INTEGER NOT NULL,
  last_decay_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_evidence_crime ON evidence_items(crime_id,status,strength DESC);

CREATE TABLE IF NOT EXISTS npc_routines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  region_id TEXT NOT NULL REFERENCES regions(id),
  start_minute_of_day INTEGER NOT NULL CHECK(start_minute_of_day BETWEEN 0 AND 1439),
  end_minute_of_day INTEGER NOT NULL CHECK(end_minute_of_day BETWEEN 1 AND 1440),
  activity TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 40 CHECK(priority BETWEEN 1 AND 100),
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

CREATE TABLE IF NOT EXISTS npc_travel_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  destination_region_id TEXT NOT NULL REFERENCES regions(id),
  depart_at INTEGER NOT NULL,
  purpose TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 50 CHECK(priority BETWEEN 1 AND 100),
  status TEXT NOT NULL DEFAULT 'planned',
  created_at INTEGER NOT NULL,
  resolution TEXT
);
CREATE INDEX IF NOT EXISTS idx_npc_travel_plans ON npc_travel_plans(status,depart_at);

CREATE TABLE IF NOT EXISTS import_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  source_label TEXT NOT NULL,
  source_version TEXT,
  ready INTEGER NOT NULL CHECK(ready IN (0,1)),
  applied INTEGER NOT NULL DEFAULT 0 CHECK(applied IN (0,1)),
  report_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gm_packet_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  player_id TEXT NOT NULL REFERENCES actors(id),
  chars INTEGER NOT NULL,
  packet_hash TEXT NOT NULL
);
