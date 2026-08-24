from __future__ import annotations

from v03_engine import dumps
from v103_runtime import SCENE_VALID_MINUTES, NAMED_SEARCH_MINUTES, PROFILES, _stable


class V103ProductionSchemaMixin:
    """Production-schema adapter for v1.0.3 living-scene state.

    The operational database uses the v0.3 facts/actor_knowledge/events layout,
    not the older prototype columns from schema.sql. Keep v1.0.3 state inside
    those existing tables so compacted v1.0.2 checkpoints retain their exact hash.
    """

    def _put_fact103(self, key, value, source, *, significance=30, origin_region_id=None):
        value = dict(value)
        value.setdefault("provenance", source)
        raw = dumps(value)
        if origin_region_id is None:
            origin_region_id = value.get("region_id")
        if origin_region_id is None:
            try:
                origin_region_id = str(self.actor("player")["region_id"])
            except Exception:
                origin_region_id = None
        if self.db.execute("SELECT 1 FROM facts WHERE key=?", (key,)).fetchone():
            self.db.execute(
                "UPDATE facts SET value_json=?,origin_region_id=?,created_at=?,significance=? WHERE key=?",
                (raw, origin_region_id, self.now, int(significance), key),
            )
        else:
            self.db.execute(
                "INSERT INTO facts(key,value_json,origin_region_id,created_at,significance) VALUES(?,?,?,?,?)",
                (key, raw, origin_region_id, self.now, int(significance)),
            )

    def _knowledge103(self, turn_key, payload, confidence):
        key = "v103:player_observation:" + turn_key
        self._put_fact103(key, payload, "local_search_v103", significance=55)
        self.db.execute(
            "INSERT OR REPLACE INTO actor_knowledge(actor_id,fact_key,confidence,learned_at,source) VALUES(?,?,?,?,?)",
            ("player", key, int(confidence), self.now, "local_search_v103"),
        )

    def ensure_living_scene_v103(self, player_id="player"):
        place = self._place103(player_id)
        if not place:
            return None
        fact_key = "v103:living_scene:" + place["key"]
        old = self._get_fact103(fact_key)
        if old and int(old.get("valid_until", -1)) >= self.now:
            return old
        templates = PROFILES.get(place["key"], [])
        seed = f"v103-scene|{place['key']}|{self.now // 15}|{self._source_live_version_v100()}"
        offset = _stable(seed, len(templates)) if templates else 0
        population = []
        for i in range(len(templates)):
            descriptor, activity, size, knows_borga = templates[(offset + i) % len(templates)]
            population.append({
                "entity_key": f"{place['key']}:ambient:{self.now}:{i+1}:{_stable(seed+'|'+str(i),99991)}",
                "kind": "anonymous_local",
                "descriptor": descriptor,
                "activity": activity,
                "group_size": size,
                "knowledge_tags": ["borga_work_routine"] if knows_borga else [],
                "identity_status": "not_materialized_named_npc",
            })
        scene = {
            "model": "v103_prospective_ambient_population",
            "authority": "NON_CANON_MECHANICAL_PROSPECTIVE",
            "region_id": place["region_id"],
            "place_key": place["key"],
            "place_text": place["name"],
            "generated_at": self.now,
            "valid_until": self.now + SCENE_VALID_MINUTES,
            "population": population,
            "does_not_assert": ["historical identity", "named NPC presence", "private knowledge"],
        }
        self._put_fact103(
            fact_key, scene, "engine:v103_living_scene",
            significance=25, origin_region_id=place["region_id"],
        )
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                self.now, "living_scene_generated", place["region_id"], None, None, 25,
                dumps({"place_key": place["key"], "population_count": len(population)}), "world",
            ),
        )
        self.db.commit()
        return scene

    def _finalize_search103(self, turn_key, raw_text, player_id, action_id, turn_id, pending_id=None):
        place = self._place103(player_id)
        scene = self.ensure_living_scene_v103(player_id)
        target = self._named_target103(raw_text)
        if not place or not scene or not target:
            raise RuntimeError("living named search lacks grounded place/target")
        start = self.now
        outcome = self._outcome103(target, place, scene, start)
        minutes = 0 if outcome["outcome"] == "guarded_unknown" else NAMED_SEARCH_MINUTES
        if minutes:
            self.advance(minutes)
        outcome.update({"search_started_at": start, "search_finished_at": self.now, "search_minutes": minutes})
        if outcome["outcome"] in {"found", "lead", "not_found_no_lead"}:
            self._knowledge103(
                turn_key, outcome,
                100 if outcome["outcome"] == "found" else 78 if outcome["outcome"] == "lead" else 65,
            )
        if pending_id is not None:
            self.db.execute(
                "UPDATE scene_pending_resolution SET status='resolved',state_json=?,resolved_at=? WHERE id=?",
                (dumps(outcome), self.now, pending_id),
            )
        self.db.execute(
            "UPDATE scene_actions SET status='resolved',resolution_mode='engine_living_scene_search',effect_json=? WHERE id=?",
            (dumps(outcome), action_id),
        )
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,region_id,actor_id,faction_id,significance,payload_json,visibility) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (self.now, "living_named_search", place["region_id"], player_id, None, 55, dumps(outcome), "player"),
        )
        self.db.execute(
            "UPDATE gm_turns SET status='executed',engine_result_json=?,completed_at=? WHERE id=?",
            (dumps(outcome), self.now, turn_id),
        )
        self.db.commit()
        packet = self.build_gm_packet(player_id)
        contract = self._search_contract103(raw_text)
        checkpoint = self.write_checkpoint(player_id, turn_id=turn_id, kind="v103_living_search")
        public = {
            "status": "executed", "accepted": True, "turn_key": turn_key,
            "scene_action_id": action_id, "resumed_from_pending": pending_id is not None,
            "result": outcome, "gm_packet": packet,
            "narration_contract": contract, "checkpoint": checkpoint,
        }
        self.db.execute(
            "UPDATE gm_turns SET gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=? WHERE id=?",
            (dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), turn_id),
        )
        self.db.commit()
        return public
