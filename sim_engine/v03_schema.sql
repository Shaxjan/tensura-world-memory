PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE regions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'city',
  population INTEGER NOT NULL CHECK(population >= 0),
  security INTEGER NOT NULL DEFAULT 50 CHECK(security BETWEEN 0 AND 100),
  prosperity INTEGER NOT NULL DEFAULT 50 CHECK(prosperity BETWEEN 0 AND 100)
);

CREATE TABLE routes (
  a TEXT NOT NULL REFERENCES regions(id),
  b TEXT NOT NULL REFERENCES regions(id),
  travel_minutes INTEGER NOT NULL CHECK(travel_minutes > 0),
  capacity INTEGER NOT NULL DEFAULT 100 CHECK(capacity > 0),
  risk INTEGER NOT NULL DEFAULT 10 CHECK(risk BETWEEN 0 AND 100),
  PRIMARY KEY(a,b)
);

CREATE TABLE actors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  is_player INTEGER NOT NULL DEFAULT 0 CHECK(is_player IN (0,1)),
  region_id TEXT NOT NULL REFERENCES regions(id),
  cash_copper INTEGER NOT NULL DEFAULT 0 CHECK(cash_copper >= 0),
  status TEXT NOT NULL DEFAULT 'idle'
);

CREATE TABLE actor_inventory (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  commodity_id TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 0 CHECK(qty >= 0),
  PRIMARY KEY(actor_id, commodity_id)
);

CREATE TABLE factions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  home_region_id TEXT NOT NULL REFERENCES regions(id),
  treasury_copper INTEGER NOT NULL DEFAULT 0 CHECK(treasury_copper >= 0),
  policy_json TEXT NOT NULL DEFAULT '{}',
  next_action_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE faction_goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  faction_id TEXT NOT NULL REFERENCES factions(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  target_region_id TEXT REFERENCES regions(id),
  priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 100),
  progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
  status TEXT NOT NULL DEFAULT 'active',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX idx_faction_goals ON faction_goals(faction_id,status,priority DESC);

CREATE TABLE commodities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_price_copper INTEGER NOT NULL CHECK(base_price_copper > 0),
  essential INTEGER NOT NULL DEFAULT 0 CHECK(essential IN (0,1))
);

CREATE TABLE markets (
  region_id TEXT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
  commodity_id TEXT NOT NULL REFERENCES commodities(id) ON DELETE CASCADE,
  supply INTEGER NOT NULL CHECK(supply >= 0),
  target_supply INTEGER NOT NULL CHECK(target_supply > 0),
  demand INTEGER NOT NULL CHECK(demand >= 0),
  production_per_day INTEGER NOT NULL DEFAULT 0 CHECK(production_per_day >= 0),
  consumption_per_day INTEGER NOT NULL DEFAULT 0 CHECK(consumption_per_day >= 0),
  price_copper INTEGER NOT NULL CHECK(price_copper > 0),
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(region_id, commodity_id)
);

CREATE TABLE population_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  region_id TEXT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  count INTEGER NOT NULL CHECK(count >= 0),
  wealth INTEGER NOT NULL DEFAULT 50 CHECK(wealth BETWEEN 0 AND 100),
  unrest INTEGER NOT NULL DEFAULT 0 CHECK(unrest BETWEEN 0 AND 100),
  last_macro_at INTEGER NOT NULL
);

CREATE TABLE facts (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  origin_region_id TEXT REFERENCES regions(id),
  created_at INTEGER NOT NULL,
  significance INTEGER NOT NULL DEFAULT 50 CHECK(significance BETWEEN 0 AND 100)
);

CREATE TABLE actor_knowledge (
  actor_id TEXT NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
  fact_key TEXT NOT NULL REFERENCES facts(key) ON DELETE CASCADE,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
  learned_at INTEGER NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY(actor_id,fact_key)
);

CREATE TABLE region_beliefs (
  region_id TEXT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
  fact_key TEXT NOT NULL REFERENCES facts(key) ON DELETE CASCADE,
  claim_json TEXT NOT NULL,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
  received_at INTEGER NOT NULL,
  source_region_id TEXT REFERENCES regions(id),
  PRIMARY KEY(region_id,fact_key)
);

CREATE TABLE info_packets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fact_key TEXT NOT NULL REFERENCES facts(key) ON DELETE CASCADE,
  from_region_id TEXT NOT NULL REFERENCES regions(id),
  to_region_id TEXT NOT NULL REFERENCES regions(id),
  claim_json TEXT NOT NULL,
  confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
  depart_at INTEGER NOT NULL,
  due_at INTEGER NOT NULL,
  mode TEXT NOT NULL DEFAULT 'rumor',
  status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX idx_packets_due ON info_packets(status,due_at);

CREATE TABLE caravans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  faction_id TEXT REFERENCES factions(id),
  commodity_id TEXT NOT NULL REFERENCES commodities(id),
  qty INTEGER NOT NULL CHECK(qty > 0),
  from_region_id TEXT NOT NULL REFERENCES regions(id),
  to_region_id TEXT NOT NULL REFERENCES regions(id),
  depart_at INTEGER NOT NULL,
  due_at INTEGER NOT NULL,
  purchase_cost_copper INTEGER NOT NULL CHECK(purchase_cost_copper >= 0),
  status TEXT NOT NULL DEFAULT 'traveling'
);
CREATE INDEX idx_caravans_due ON caravans(status,due_at);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_minute INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  region_id TEXT REFERENCES regions(id),
  actor_id TEXT REFERENCES actors(id),
  faction_id TEXT REFERENCES factions(id),
  significance INTEGER NOT NULL DEFAULT 40 CHECK(significance BETWEEN 0 AND 100),
  payload_json TEXT NOT NULL DEFAULT '{}',
  visibility TEXT NOT NULL DEFAULT 'world'
);
CREATE INDEX idx_events_recent ON events(world_minute DESC, significance DESC);

CREATE TABLE metrics (
  key TEXT PRIMARY KEY,
  value INTEGER NOT NULL DEFAULT 0
);
