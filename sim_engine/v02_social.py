from __future__ import annotations

import random
from typing import Any

from v02_base import dumps, loads


class SocialMixin:
    def set_preference(self, actor_id: str, tag: str, weight: int) -> None:
            self.db.execute(
                "INSERT INTO preferences(actor_id,tag,weight) VALUES(?,?,?) ON CONFLICT(actor_id,tag) DO UPDATE SET weight=excluded.weight",
                (actor_id, tag, max(-100, min(100, int(weight)))),
            )

    def set_relationship(self, actor_id: str, target_id: str, *, affinity: int = 0, trust: int = 0, respect: int = 0, fear: int = 0) -> None:
            vals = (
                max(-100, min(100, int(affinity))),
                max(-100, min(100, int(trust))),
                max(-100, min(100, int(respect))),
                max(0, min(100, int(fear))),
            )
            self.db.execute(
                """INSERT INTO relationships(actor_id,target_id,affinity,trust,respect,fear,updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(actor_id,target_id) DO UPDATE SET affinity=excluded.affinity,
                   trust=excluded.trust,respect=excluded.respect,fear=excluded.fear,updated_at=excluded.updated_at""",
                (actor_id, target_id, *vals, self.now),
            )

    def set_fact(self, key: str, value: Any, source: str = "world") -> None:
            self.db.execute(
                "INSERT INTO facts(key,value_json,created_at,source) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,source=excluded.source",
                (key, dumps(value), self.now, source),
            )

    def teach_fact(self, actor_id: str, fact_key: str, source: str, confidence: int = 100) -> None:
            if self.db.execute("SELECT 1 FROM facts WHERE key=?", (fact_key,)).fetchone() is None:
                raise KeyError(fact_key)
            self.db.execute(
                "INSERT INTO knowledge(actor_id,fact_key,learned_at,source,confidence) VALUES(?,?,?,?,?) ON CONFLICT(actor_id,fact_key) DO UPDATE SET learned_at=excluded.learned_at,source=excluded.source,confidence=excluded.confidence",
                (actor_id, fact_key, self.now, source, max(0, min(100, confidence))),
            )

    def known_fact(self, actor_id: str, fact_key: str) -> Any | None:
            row = self.db.execute(
                "SELECT f.value_json FROM knowledge k JOIN facts f ON f.key=k.fact_key WHERE k.actor_id=? AND k.fact_key=?",
                (actor_id, fact_key),
            ).fetchone()
            return loads(row["value_json"], None) if row else None

    def seed_rumor(self, origin_actor_id: str, claim: dict[str, Any], fact_key: str | None = None, confidence: int = 80) -> int:
            cur = self.db.execute(
                "INSERT INTO rumors(fact_key,origin_actor_id,origin_claim_json,created_at) VALUES(?,?,?,?)",
                (fact_key, origin_actor_id, dumps(claim), self.now),
            )
            rumor_id = int(cur.lastrowid)
            self.db.execute(
                "INSERT INTO rumor_beliefs(rumor_id,actor_id,claim_json,confidence,heard_at,source_actor_id) VALUES(?,?,?,?,?,?)",
                (rumor_id, origin_actor_id, dumps(claim), max(0, min(100, confidence)), self.now, None),
            )
            return rumor_id

    def rumor_beliefs(self, actor_id: str):
            return self.db.execute(
                "SELECT * FROM rumor_beliefs WHERE actor_id=? ORDER BY heard_at DESC,rumor_id", (actor_id,)
            ).fetchall()

    def _mutate_claim(self, claim: dict[str, Any], rng: random.Random) -> dict[str, Any]:
            out = dict(claim)
            if "count_estimate" in out and isinstance(out["count_estimate"], int):
                drift = rng.randint(-15, 20)
                out["count_estimate"] = max(1, int(round(out["count_estimate"] * (100 + drift) / 100)))
            if "severity" in out and isinstance(out["severity"], int):
                out["severity"] = max(0, min(100, out["severity"] + rng.randint(-8, 10)))
            return out

    def _share_rumor(self, source: str, target: str, rng: random.Random) -> bool:
            rows = self.rumor_beliefs(source)
            if not rows or rng.random() > 0.35:
                return False
            belief = rng.choice(rows)
            existing = self.db.execute(
                "SELECT confidence,claim_json FROM rumor_beliefs WHERE rumor_id=? AND actor_id=?",
                (belief["rumor_id"], target),
            ).fetchone()
            if existing is not None and int(existing["confidence"]) >= int(belief["confidence"]) - 8:
                return False
            old_conf = int(belief["confidence"])
            new_conf = max(15, old_conf - rng.randint(4, 14))
            claim = self._mutate_claim(loads(belief["claim_json"], {}), rng)
            self.db.execute(
                "INSERT INTO rumor_beliefs(rumor_id,actor_id,claim_json,confidence,heard_at,source_actor_id) VALUES(?,?,?,?,?,?) ON CONFLICT(rumor_id,actor_id) DO UPDATE SET claim_json=excluded.claim_json,confidence=MAX(rumor_beliefs.confidence,excluded.confidence),heard_at=excluded.heard_at,source_actor_id=excluded.source_actor_id",
                (belief["rumor_id"], target, dumps(claim), new_conf, self.now, source),
            )
            self.event("rumor_shared", actor_id=source, target_id=target, location_id=self.actor(source)["location_id"], payload={"rumor_id": int(belief["rumor_id"]), "confidence": new_conf, "claim": claim})
            return True

    def resolve_reaction(self, observer_id: str, *, source_actor_id: str | None, tags: list[str], intensity: int = 50, novelty: int = 50, disruption: int = 0, local_norm: int = 0, crowd_sentiment: int = 0) -> dict[str, Any]:
            observer = self.actor(observer_id)
            p = loads(observer["personality_json"], {})
            n = self.needs(observer_id)
            pref_rows = self.db.execute(
                f"SELECT tag,weight FROM preferences WHERE actor_id=? AND tag IN ({','.join('?' for _ in tags)})", (observer_id, *tags)
            ).fetchall() if tags else []
            pref_map = {str(r["tag"]): int(r["weight"]) for r in pref_rows}
            pref = sum(pref_map.get(tag, 0) for tag in tags) / max(1, len(tags))
            curiosity = int(p.get("curiosity", 50)); sociability = int(p.get("sociability", 50)); discipline = int(p.get("discipline", 50)); conformity = int(p.get("conformity", 35))
            affinity = trust = respect = fear = 0
            if source_actor_id:
                rel = self.db.execute("SELECT * FROM relationships WHERE actor_id=? AND target_id=?", (observer_id, source_actor_id)).fetchone()
                if rel:
                    affinity = int(rel["affinity"]); trust = int(rel["trust"]); respect = int(rel["respect"]); fear = int(rel["fear"])
            rng = self._rng(f"reaction:{observer_id}:{source_actor_id}:{','.join(sorted(tags))}:{intensity}:{novelty}:{disruption}")
            fatigue_penalty = int(n["fatigue"]) * 0.22 + int(n["hunger"]) * 0.10
            attention = round(max(0, min(100, intensity * 0.38 + novelty * curiosity / 200 + sociability * 0.10 - fatigue_penalty + rng.randint(-14, 14))))
            score = round(max(-100, min(100, pref * 0.48 + affinity * 0.16 + trust * 0.08 + respect * 0.10 - fear * 0.08 + local_norm * 0.12 + crowd_sentiment * conformity / 500 - disruption * discipline / 250 + int(observer["mood"]) * 0.08 + rng.randint(-16, 16))))
            if attention < 20: category = "ignore"
            elif score <= -55: category = "hostile"
            elif score <= -20: category = "annoyed"
            elif score < 10: category = "indifferent"
            elif score < 35: category = "curious"
            elif score < 65: category = "approving"
            else: category = "enthusiastic"
            reasons = []
            if pref > 25: reasons.append("likes_stimulus_tags")
            if pref < -25: reasons.append("dislikes_stimulus_tags")
            if affinity > 30: reasons.append("likes_source")
            if affinity < -30: reasons.append("dislikes_source")
            if disruption > 50 and discipline > 65: reasons.append("dislikes_disruption")
            if int(n["fatigue"]) > 65: reasons.append("tired")
            if novelty > 65 and curiosity > 65: reasons.append("novelty_interest")
            if abs(crowd_sentiment) > 50 and conformity > 55: reasons.append("crowd_pressure")
            if not reasons: reasons.append("mixed_or_weak_factors")
            result = {"observer_id": observer_id, "attention": attention, "score": score, "category": category, "reasons": reasons, "factors": {"preference": round(pref,1), "affinity": affinity, "trust": trust, "respect": respect, "fear": fear, "fatigue": int(n["fatigue"]), "hunger": int(n["hunger"]), "local_norm": local_norm, "crowd_sentiment": crowd_sentiment}}
            self.event("reaction_resolved", actor_id=observer_id, target_id=source_actor_id, location_id=observer["location_id"], payload=result)
            return result
