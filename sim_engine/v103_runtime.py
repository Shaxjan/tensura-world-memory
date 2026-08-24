from __future__ import annotations

import hashlib
from v03_engine import dumps, loads
from v100_handoff import runtime_state_hash_v100
from v101_runtime import EURAZANIA_PLACES, _norm
from v102_runtime import V102RuntimeMixin

ENGINE_VERSION_V103 = "1.0.3"
SCENE_VALID_MINUTES = 45
OBSERVE_MINUTES = 1
NAMED_SEARCH_MINUTES = 6

PROFILES = {
    "eurazania_borga_big_training_yard": [
        ("помощник инструктора", "проверяет тренировочные пары", 1, True),
        ("двое бойцов", "отрабатывают связку ударов", 2, False),
        ("небольшая тренировочная группа", "разминается у края площадки", 4, False),
        ("рабочий при дворе", "переносит тренировочный инвентарь", 1, False),
        ("трое бойцов", "по очереди работают с учебным оружием", 3, False),
    ],
    "eurazania_small_training_yard": [
        ("помощник инструктора", "наблюдает за коротким спаррингом", 1, True),
        ("двое бойцов", "спаррингуют без зрителей", 2, False),
        ("молодой боец", "повторяет стойки", 1, False),
        ("рабочий", "собирает инвентарь у стены", 1, False),
    ],
    "eurazania_west_training_field": [
        ("старший помощник на поле", "распределяет тренировочные пары", 1, True),
        ("четверо бойцов", "работают в двух спарринговых парах", 4, False),
        ("небольшая группа", "отрабатывает рывки по краю поля", 5, False),
        ("рабочий при поле", "проверяет стойки и разметку", 1, False),
        ("боец", "делает короткую передышку у воды", 1, False),
    ],
    "eurazania_carrion_palace": [
        ("пара дворцовых стражей", "держит пост у прохода", 2, False),
        ("посыльный", "ждёт допуска дальше", 1, False),
        ("дворцовый служащий", "несёт связку документов", 1, False),
        ("двое посетителей", "тихо переговариваются в стороне", 2, False),
    ],
    "eurazania_trade_street": [
        ("торговец", "раскладывает товар", 1, False),
        ("двое грузчиков", "переносят ящики", 2, False),
        ("пара ранних покупателей", "останавливается у прилавка", 2, False),
        ("ремесленник", "готовит рабочее место", 1, False),
        ("несколько прохожих", "идут по своим делам", 3, False),
    ],
    "eurazania_evening_market_square": [
        ("двое работников", "готовят место под торговлю", 2, False),
        ("грузчик", "тащит сложенные корзины", 1, False),
        ("торговка", "проверяет привезённый товар", 1, False),
        ("несколько прохожих", "пересекают площадь", 3, False),
    ],
    "eurazania_hotel_district": [
        ("работник гостиницы", "выносит воду к входу", 1, False),
        ("двое постояльцев", "собираются в дорогу", 2, False),
        ("работник двора", "занимается поклажей у повозки", 1, False),
        ("посыльный", "ищет нужный двор", 1, False),
        ("несколько прохожих", "идут вдоль гостиничных дворов", 3, False),
    ],
}

BORGA_ROUTINE = (
    ("eurazania_borga_big_training_yard", 30),
    ("eurazania_west_training_field", 35),
    ("eurazania_small_training_yard", 20),
    (None, 15),
)


def _stable(text: str, modulo: int) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16) % modulo


def _match_place(place_text):
    current = _norm(place_text)
    if not current:
        return None
    for key, meta in EURAZANIA_PLACES.items():
        name = _norm(meta["name"])
        if current == name or name in current or current in name:
            return key, meta
    return None


class V103RuntimeMixin(V102RuntimeMixin):
    """Persistent causal ambient scenes and finite Borga search."""

    def _get_fact103(self, key):
        row = self.db.execute("SELECT value_json FROM facts WHERE key=?", (key,)).fetchone()
        value = loads(row[0], None) if row else None
        return value if isinstance(value, dict) else None

    def _put_fact103(self, key, value, source):
        raw = dumps(value)
        if self.db.execute("SELECT 1 FROM facts WHERE key=?", (key,)).fetchone():
            self.db.execute("UPDATE facts SET value_json=?,created_at=?,source=? WHERE key=?",
                            (raw, self.now, source, key))
        else:
            self.db.execute("INSERT INTO facts(key,value_json,created_at,source) VALUES(?,?,?,?)",
                            (key, raw, self.now, source))

    def _place103(self, player_id="player"):
        row = self.db.execute("SELECT place_text FROM scene_local_state WHERE actor_id=?", (player_id,)).fetchone()
        matched = _match_place(str(row[0]) if row and row[0] is not None else None)
        if not matched:
            return None
        key, meta = matched
        return {"key": key, "name": meta["name"], "region_id": str(self.actor(player_id)["region_id"])}

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
                "kind": "anonymous_local", "descriptor": descriptor, "activity": activity,
                "group_size": size, "knowledge_tags": ["borga_work_routine"] if knows_borga else [],
                "identity_status": "not_materialized_named_npc",
            })
        scene = {
            "model": "v103_prospective_ambient_population", "authority": "NON_CANON_MECHANICAL_PROSPECTIVE",
            "place_key": place["key"], "place_text": place["name"], "generated_at": self.now,
            "valid_until": self.now + SCENE_VALID_MINUTES, "population": population,
            "does_not_assert": ["historical identity", "named NPC presence", "private knowledge"],
        }
        self._put_fact103(fact_key, scene, "engine:v103_living_scene")
        self.db.execute(
            "INSERT INTO events(world_minute,event_type,actor_id,target_id,location_id,payload_json,visibility) VALUES(?,?,?,?,?,?,?)",
            (self.now, "living_scene_generated", None, None, None,
             dumps({"place_key": place["key"], "population_count": len(population)}), "world"))
        self.db.commit()
        return scene

    def _scene103(self, player_id="player"):
        place = self._place103(player_id)
        if not place:
            return None
        scene = self._get_fact103("v103:living_scene:" + place["key"])
        return scene if scene and int(scene.get("valid_until", -1)) >= self.now else None

    def _named_target103(self, raw_text):
        low = _norm(raw_text)
        if not any(x in low for x in ("ищ", "где", "осматрива", "разыскива", "спрашива")):
            return None
        rows = self.db.execute("SELECT actor_key,display_name FROM actor_position_claims ORDER BY LENGTH(display_name) DESC").fetchall()
        for row in rows:
            name = str(row["display_name"])
            stem = _norm(name[:-1] if name.endswith("а") else name)
            if _norm(name) in low or (stem and stem in low):
                return {"actor_key": str(row["actor_key"]), "name": name}
        return None

    def _borga_presence103(self, start_minute):
        slot = (int(start_minute) // 60) * 60
        key = f"v103:named_presence:borga:{slot}"
        old = self._get_fact103(key)
        if old:
            return old
        roll = _stable(f"v103-borga|{slot}|{self._source_live_version_v100()}", 100)
        cursor, chosen = 0, None
        for place_key, weight in BORGA_ROUTINE:
            cursor += weight
            if roll < cursor:
                chosen = place_key
                break
        state = {
            "actor_key": "borga", "display_name": "Борга", "slot_start": slot, "slot_end": slot + 60,
            "region_id": "eurazania", "place_key": chosen,
            "place_text": EURAZANIA_PLACES[chosen]["name"] if chosen else None,
            "certainty": "prospective_hidden_schedule_exact" if chosen else "prospective_hidden_region_only",
            "authority": "NON_CANON_MECHANICAL_PROSPECTIVE", "historical_claim": False,
        }
        self._put_fact103(key, state, "engine:v103_named_presence")
        self.db.commit()
        return state

    def _informant103(self, scene):
        people = list(scene.get("population") or [])
        for person in people:
            if "borga_work_routine" in list(person.get("knowledge_tags") or []):
                return person
        return people[0] if people else None

    def _knowledge103(self, turn_key, payload, confidence):
        key = "v103:player_observation:" + turn_key
        self._put_fact103(key, payload, "local_search_v103")
        self.db.execute("INSERT OR REPLACE INTO knowledge(actor_id,fact_key,learned_at,source,confidence) VALUES(?,?,?,?,?)",
                        ("player", key, self.now, "local_search_v103", confidence))

    def _visible_set103(self, actor_key, name, place):
        self._put_fact103("v103:visible_named:" + actor_key,
                          {"actor_key": actor_key, "name": name, "place_key": place["key"], "place_text": place["name"],
                           "observed_at": self.now, "valid_until": self.now + 20},
                          "engine:v103_direct_observation")

    def _visible_named103(self, player_id="player"):
        place = self._place103(player_id)
        if not place:
            return []
        rows = self.db.execute("SELECT value_json FROM facts WHERE key LIKE 'v103:visible_named:%'").fetchall()
        out = []
        for row in rows:
            value = loads(row[0], {})
            if isinstance(value, dict) and value.get("place_key") == place["key"] and int(value.get("valid_until", -1)) >= self.now:
                out.append({"actor": value.get("actor_key"), "name": value.get("name"), "status": "visible", "place": place["name"]})
        return out

    def _outcome103(self, target, place, scene, start):
        if target["actor_key"] != "borga":
            return {"outcome": "guarded_unknown", "target_key": target["actor_key"], "target_name": target["name"],
                    "reason": "named_routine_not_calibrated_v103"}
        presence = self._borga_presence103(start)
        informant = self._informant103(scene)
        if presence.get("place_key") == place["key"]:
            self._visible_set103("borga", "Борга", place)
            return {"outcome": "found", "target_key": "borga", "target_name": "Борга",
                    "place_key": place["key"], "place_text": place["name"], "observation": "direct_local_search",
                    "does_not_assert": ["what Borga will say", "Borga consent", "Borga private knowledge"]}
        if presence.get("place_key") and informant:
            return {"outcome": "lead", "target_key": "borga", "target_name": "Борга", "not_at_current_visible_area": True,
                    "informant": {"entity_key": informant.get("entity_key"), "descriptor": informant.get("descriptor"),
                                   "knowledge_basis": "works_at_training_site"},
                    "lead": {"kind": "recent_local_testimony", "destination_key": presence["place_key"],
                             "destination_text": presence["place_text"], "confidence": "credible_not_omniscient"},
                    "does_not_assert": ["Borga remains there until player arrives", "exact route geometry"]}
        return {"outcome": "not_found_no_lead", "target_key": "borga", "target_name": "Борга",
                "not_at_current_visible_area": True, "reason": "no_causal_exact_lead_available"}

    def _search_contract103(self, raw_text):
        return {"state_authority": "engine_v1.0.3_living_scene", "player_text_verbatim": raw_text,
                "must_preserve": ["visible ambient scene", "causal named-NPC evidence", "engine search time", "HUD money/time/location"],
                "may_add": ["sensory description consistent with scene", "natural wording of engine-provided testimony"],
                "forbidden": ["invent extra named NPCs", "upgrade testimony to certainty", "invent Borga dialogue before interaction", "change player intent"]}

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
            self._knowledge103(turn_key, outcome, 100 if outcome["outcome"] == "found" else 78 if outcome["outcome"] == "lead" else 65)
        if pending_id is not None:
            self.db.execute("UPDATE scene_pending_resolution SET status='resolved',state_json=?,resolved_at=? WHERE id=?",
                            (dumps(outcome), self.now, pending_id))
        self.db.execute("UPDATE scene_actions SET status='resolved',resolution_mode='engine_living_scene_search',effect_json=? WHERE id=?",
                        (dumps(outcome), action_id))
        self.db.execute("INSERT INTO events(world_minute,event_type,actor_id,target_id,location_id,payload_json,visibility) VALUES(?,?,?,?,?,?,?)",
                        (self.now, "living_named_search", player_id, None, None, dumps(outcome), "player"))
        self.db.execute("UPDATE gm_turns SET status='executed',engine_result_json=?,completed_at=? WHERE id=?",
                        (dumps(outcome), self.now, turn_id))
        self.db.commit()
        packet = self.build_gm_packet(player_id)
        contract = self._search_contract103(raw_text)
        checkpoint = self.write_checkpoint(player_id, turn_id=turn_id, kind="v103_living_search")
        public = {"status": "executed", "accepted": True, "turn_key": turn_key, "scene_action_id": action_id,
                  "resumed_from_pending": pending_id is not None, "result": outcome, "gm_packet": packet,
                  "narration_contract": contract, "checkpoint": checkpoint}
        self.db.execute("UPDATE gm_turns SET gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=? WHERE id=?",
                        (dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), turn_id))
        self.db.commit()
        return public

    def _new_search103(self, turn_key, raw_text, player_id):
        cur = self.db.execute("INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",
                              (turn_key, player_id, raw_text, "received", self.now))
        action = self.db.execute("INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) VALUES(?,?,?,?,?,'[]','engine_living_scene_search','in_progress','{}',?)",
                                 (turn_key, self.now, player_id, "living_named_search", raw_text, self.now))
        self.db.commit()
        return self._finalize_search103(turn_key, raw_text, player_id, int(action.lastrowid), int(cur.lastrowid))

    def resume_living_scene_pending_v103(self, pending_id):
        row = self.db.execute("SELECT p.id,p.resolution_kind,p.target_key,p.status,a.id action_id,a.turn_key,a.actor_id,a.raw_text,g.id turn_id FROM scene_pending_resolution p JOIN scene_actions a ON a.id=p.scene_action_id JOIN gm_turns g ON g.turn_key=a.turn_key WHERE p.id=?", (pending_id,)).fetchone()
        if not row or str(row["status"]) not in {"pending", "deferred"}:
            raise ValueError("pending resolution unavailable")
        if str(row["resolution_kind"]) != "local_navigation" or str(row["target_key"] or "") != "borga":
            raise ValueError("v103 resume supports the current Borga local search only")
        return self._finalize_search103(str(row["turn_key"]), str(row["raw_text"]), str(row["actor_id"]),
                                        int(row["action_id"]), int(row["turn_id"]), int(row["id"]))

    def _observe103(self, turn_key, raw_text, player_id):
        cur = self.db.execute("INSERT INTO gm_turns(turn_key,player_id,raw_text,status,created_at) VALUES(?,?,?,?,?)",
                              (turn_key, player_id, raw_text, "received", self.now))
        action = self.db.execute("INSERT INTO scene_actions(turn_key,world_minute,actor_id,action_kind,raw_text,components_json,resolution_mode,status,effect_json,created_at) VALUES(?,?,?,?,?,'[]','engine_living_scene_observe','in_progress','{}',?)",
                                 (turn_key, self.now, player_id, "living_scene_observe", raw_text, self.now))
        scene = self.ensure_living_scene_v103(player_id)
        start = self.now
        self.advance(OBSERVE_MINUTES)
        effect = {"outcome": "observed", "observation_minutes": OBSERVE_MINUTES, "started_at": start,
                  "finished_at": self.now, "ambient_count": len((scene or {}).get("population") or [])}
        self.db.execute("UPDATE scene_actions SET status='resolved',effect_json=? WHERE id=?", (dumps(effect), int(action.lastrowid)))
        self.db.execute("UPDATE gm_turns SET status='executed',engine_result_json=?,completed_at=? WHERE id=?",
                        (dumps(effect), self.now, int(cur.lastrowid)))
        self.db.commit()
        packet = self.build_gm_packet(player_id)
        contract = {"state_authority": "engine_v1.0.3_living_scene", "player_text_verbatim": raw_text,
                    "must_preserve": ["visible ambient scene", "HUD"],
                    "forbidden": ["invent named NPC presence", "invent hidden conversations"]}
        checkpoint = self.write_checkpoint(player_id, turn_id=int(cur.lastrowid), kind="v103_scene_observe")
        public = {"status": "executed", "accepted": True, "turn_key": turn_key, "scene_action_id": int(action.lastrowid),
                  "result": effect, "gm_packet": packet, "narration_contract": contract, "checkpoint": checkpoint}
        self.db.execute("UPDATE gm_turns SET gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=? WHERE id=?",
                        (dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), int(cur.lastrowid)))
        self.db.commit()
        return public

    def _arrival_scene103(self, turn_key, public, player_id):
        if not self.ensure_living_scene_v103(player_id):
            return public
        packet = self.build_gm_packet(player_id)
        public = dict(public)
        public["gm_packet"] = packet
        contract = dict(public.get("narration_contract") or {})
        must = list(contract.get("must_preserve") or [])
        if "visible ambient scene" not in must:
            must.append("visible ambient scene")
        contract["must_preserve"] = must
        public["narration_contract"] = contract
        turn = self.db.execute("SELECT id FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if turn:
            checkpoint = self.write_checkpoint(player_id, turn_id=int(turn[0]), kind="v103_arrival_scene")
            public["checkpoint"] = checkpoint
            self.db.execute("UPDATE gm_turns SET gm_packet_json=?,narration_contract_json=?,checkpoint_hash=?,public_result_json=? WHERE id=?",
                            (dumps(packet), dumps(contract), checkpoint["state_hash"], dumps(public), int(turn[0])))
            self.db.commit()
        return public

    def process_player_turn(self, turn_key, raw_text, *, player_id="player", external_intent=None):
        old = self.db.execute("SELECT * FROM gm_turns WHERE turn_key=?", (turn_key,)).fetchone()
        if old:
            return self._load_turn_public(old, replayed=True)
        place = self._place103(player_id)
        target = self._named_target103(raw_text)
        if place and target and external_intent is None:
            return self._new_search103(turn_key, raw_text, player_id)
        low = _norm(raw_text)
        if place and not target and external_intent is None and any(x in low for x in ("осматрива", "оглядыва", "кто здесь", "кто тут")):
            return self._observe103(turn_key, raw_text, player_id)
        public = super().process_player_turn(turn_key, raw_text, player_id=player_id, external_intent=external_intent)
        result = public.get("result") if isinstance(public, dict) else None
        if isinstance(result, dict) and result.get("outcome") in {"arrived", "already_at_destination"}:
            public = self._arrival_scene103(turn_key, public, player_id)
        return public

    def build_gm_packet(self, player_id="player"):
        base = super().build_gm_packet(player_id)
        scene = self._scene103(player_id)
        base.setdefault("scene", {})
        base["scene"]["ambient"] = list((scene or {}).get("population") or [])[:10]
        base["scene"]["named_observations"] = self._visible_named103(player_id)
        base["scene"]["living_scene_status"] = {"present": scene is not None,
                                                        "generated_at": (scene or {}).get("generated_at"),
                                                        "valid_until": (scene or {}).get("valid_until")}
        base.setdefault("constraints", {})
        base["constraints"]["living_scene"] = "Narrate engine-provided anonymous ambient people naturally; do not turn them into old named canon."
        base["constraints"]["named_presence"] = "Named NPC position requires direct observation or causal testimony; UNKNOWN is not an empty world."
        base["runtime"] = {"engine": ENGINE_VERSION_V103}
        return base

    def build_session_state_v103(self, *, journal_seq, head_state_hash, last_event=None):
        state = super().build_session_state_v102(journal_seq=journal_seq, head_state_hash=head_state_hash, last_event=last_event)
        state["engine_version"] = ENGINE_VERSION_V103
        packet = None
        if isinstance(last_event, dict):
            result = last_event.get("result") if isinstance(last_event.get("result"), dict) else {}
            packet = result.get("gm_packet") if isinstance(result.get("gm_packet"), dict) else None
        packet = packet or self.build_gm_packet("player")
        scene = packet.get("scene") or {}
        state["scene"] = {"ambient": list(scene.get("ambient") or []),
                          "named_observations": list(scene.get("named_observations") or []),
                          "pending_resolutions": list(scene.get("pending_resolutions") or [])}
        state["display_contract"]["scene_rule"] = "If ambient is non-empty, describe the place as populated; do not answer 'nobody confirmed'."
        return state

    def execute_runtime_event(self, seq, event_key, event_type, request):
        if event_type != "living_scene_resume":
            return super().execute_runtime_event(seq, event_key, event_type, request)
        old = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))).fetchone()
        if old:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}
        pending_id = request.get("pending_id")
        if not isinstance(pending_id, int):
            raise ValueError("living_scene_resume requires pending_id")
        source_v = self._source_live_version_v100()
        before = runtime_state_hash_v100(self, source_v)
        result = self.resume_living_scene_pending_v103(pending_id)
        after = runtime_state_hash_v100(self, source_v)
        self.db.execute("INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before, after, self.now))
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}
