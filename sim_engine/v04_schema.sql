PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS actor_stats (
  actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
  hp INTEGER NOT NULL CHECK(hp >= 0),
  max_hp INTEGER NOT NULL CHECK(max_hp > 0),
  armor INTEGER NOT NULL DEFAULT 0 CHECK(armor BETWEEN 0 AND 20),
  power INTEGER NOT NULL DEFAULT 0 CHECK(power BETWEEN -5 AND 20),
  alive INTEGER NOT NULL DEFAULT 1 CHECK(alive IN (0,1))
);

CREATE TABLE IF NOT EXISTS actor_skills (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  bonus INTEGER NOT NULL DEFAULT 0 CHECK(bonus BETWEEN -10 AND 30),
  PRIMARY KEY(actor_id, skill)
);

CREATE TABLE IF NOT EXISTS action_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  command TEXT NOT NULL,
  params_json TEXT NOT NULL DEFAULT '{}',
  accepted INTEGER NOT NULL CHECK(accepted IN (0,1)),
  rejection_reason TEXT
);

CREATE TABLE IF NOT EXISTS checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  dc INTEGER NOT NULL CHECK(dc BETWEEN 1 AND 40),
  roll INTEGER NOT NULL CHECK(roll BETWEEN 1 AND 20),
  bonus INTEGER NOT NULL,
  total INTEGER NOT NULL,
  success INTEGER NOT NULL CHECK(success IN (0,1)),
  namespace TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS injuries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 100),
  applied_at INTEGER NOT NULL,
  healed_at INTEGER,
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS actor_travel (
  actor_id TEXT PRIMARY KEY REFERENCES actors(id) ON DELETE CASCADE,
  from_region_id TEXT NOT NULL REFERENCES regions(id),
  to_region_id TEXT NOT NULL REFERENCES regions(id),
  started_at INTEGER NOT NULL,
  due_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'traveling'
);

CREATE TABLE IF NOT EXISTS laws (
  region_id TEXT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 100),
  fine_copper INTEGER NOT NULL DEFAULT 0 CHECK(fine_copper >= 0),
  jail_minutes INTEGER NOT NULL DEFAULT 0 CHECK(jail_minutes >= 0),
  PRIMARY KEY(region_id, code)
);

CREATE TABLE IF NOT EXISTS reputation (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  region_id TEXT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
  public INTEGER NOT NULL DEFAULT 0 CHECK(public BETWEEN -100 AND 100),
  authority INTEGER NOT NULL DEFAULT 0 CHECK(authority BETWEEN -100 AND 100),
  underworld INTEGER NOT NULL DEFAULT 0 CHECK(underworld BETWEEN -100 AND 100),
  PRIMARY KEY(actor_id, region_id)
);

CREATE TABLE IF NOT EXISTS crimes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  region_id TEXT NOT NULL REFERENCES regions(id),
  code TEXT NOT NULL,
  witnessed INTEGER NOT NULL CHECK(witnessed IN (0,1)),
  evidence INTEGER NOT NULL CHECK(evidence BETWEEN 0 AND 100),
  fine_copper INTEGER NOT NULL DEFAULT 0 CHECK(fine_copper >= 0),
  status TEXT NOT NULL,
  occurred_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crime_id INTEGER NOT NULL REFERENCES crimes(id) ON DELETE CASCADE,
  authority_faction_id TEXT REFERENCES factions(id),
  due_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  resolution TEXT
);
CREATE INDEX IF NOT EXISTS idx_legal_due ON legal_cases(status, due_at);

CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  counterpart_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  region_id TEXT NOT NULL REFERENCES regions(id),
  due_at INTEGER NOT NULL,
  grace_minutes INTEGER NOT NULL DEFAULT 30 CHECK(grace_minutes >= 0),
  status TEXT NOT NULL DEFAULT 'scheduled',
  purpose TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_appointments_due ON appointments(status, due_at);

CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  memory_key TEXT NOT NULL,
  summary TEXT NOT NULL,
  salience INTEGER NOT NULL CHECK(salience BETWEEN 0 AND 100),
  emotional INTEGER NOT NULL DEFAULT 0 CHECK(emotional BETWEEN 0 AND 100),
  decay_per_day INTEGER NOT NULL DEFAULT 1 CHECK(decay_per_day BETWEEN 0 AND 20),
  created_at INTEGER NOT NULL,
  last_recalled_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  UNIQUE(actor_id, memory_key)
);
CREATE INDEX IF NOT EXISTS idx_memories_actor ON memories(actor_id, status, salience DESC);

CREATE TABLE IF NOT EXISTS canon_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  origin_region_id TEXT NOT NULL REFERENCES regions(id),
  due_at INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  significance INTEGER NOT NULL CHECK(significance BETWEEN 1 AND 100),
  spread_mode TEXT NOT NULL DEFAULT 'courier',
  status TEXT NOT NULL DEFAULT 'scheduled'
);
CREATE INDEX IF NOT EXISTS idx_canon_due ON canon_events(status, due_at);
