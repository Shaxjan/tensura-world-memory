from __future__ import annotations

from typing import Any

from v03_engine import dumps, loads
from v100_handoff import runtime_state_hash_v100


class V100JournalMixin:
    def _source_live_version_v100(self) -> int:
        row = self.db.execute("SELECT source_live_version FROM runtime_cutover WHERE id=1").fetchone()
        if row is None:
            raise RuntimeError("v1.0 runtime not installed")
        return int(row[0])

    def execute_runtime_event(self, seq: int, event_key: str, event_type: str, request: dict[str, Any]) -> dict[str, Any]:
        if int(seq) < 1:
            raise ValueError("journal seq must be positive")
        if not event_key or len(event_key) > 160:
            raise ValueError("invalid event_key")
        if not isinstance(request, dict):
            raise ValueError("request must be object")
        old = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=? OR seq=?", (event_key, int(seq))).fetchone()
        if old is not None:
            if str(old["event_key"]) != event_key or int(old["seq"]) != int(seq):
                raise RuntimeError("journal sequence collision")
            return {"accepted": True, "replayed": True, "journal": self.export_runtime_journal_entry(event_key)}
        source_v = self._source_live_version_v100()
        before_hash = runtime_state_hash_v100(self, source_v)
        if event_type == "player_turn":
            raw = request.get("raw_text")
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("player_turn raw_text required")
            result = self.process_player_turn(event_key, raw)
        elif event_type == "scene_resolution":
            pending_id, payload, resolver = request.get("pending_id"), request.get("payload"), request.get("resolver", "gm")
            if not isinstance(pending_id, int) or not isinstance(payload, dict):
                raise ValueError("scene_resolution requires pending_id and payload")
            result = self.resolve_scene_pending(pending_id, payload, resolver=str(resolver))
        elif event_type == "narration":
            turn_key, text = request.get("turn_key"), request.get("text")
            if not isinstance(turn_key, str) or not isinstance(text, str):
                raise ValueError("narration requires turn_key and text")
            result = self.record_narration(turn_key, text)
        else:
            raise ValueError("unsupported runtime event type")
        after_hash = runtime_state_hash_v100(self, source_v)
        self.db.execute(
            "INSERT INTO runtime_journal(seq,event_key,event_type,world_minute,request_json,result_json,before_hash,after_hash,committed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (int(seq), event_key, event_type, self.now, dumps(request), dumps(result), before_hash, after_hash, self.now),
        )
        self.db.commit()
        return {"accepted": True, "replayed": False, "result": result, "journal": self.export_runtime_journal_entry(event_key)}

    def export_runtime_journal_entry(self, event_key: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM runtime_journal WHERE event_key=?", (event_key,)).fetchone()
        if row is None:
            raise ValueError("unknown runtime journal event")
        return {
            "format": "TENSURA_RUNTIME_EVENT", "schema_version": 1, "seq": int(row["seq"]),
            "event_key": str(row["event_key"]), "event_type": str(row["event_type"]),
            "world_minute": int(row["world_minute"]), "request": loads(row["request_json"], {}),
            "result": loads(row["result_json"], {}), "before_hash": str(row["before_hash"]),
            "after_hash": str(row["after_hash"]),
        }

    def replay_runtime_entries(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        expected_seq, replayed = None, 0
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("format") != "TENSURA_RUNTIME_EVENT" or entry.get("schema_version") != 1:
                return {"ok": False, "reason": "bad_journal_entry", "replayed": replayed}
            seq = entry.get("seq")
            if not isinstance(seq, int):
                return {"ok": False, "reason": "bad_seq", "replayed": replayed}
            if expected_seq is None:
                expected_seq = seq
            if seq != expected_seq:
                return {"ok": False, "reason": "journal_gap", "expected": expected_seq, "got": seq, "replayed": replayed}
            before = runtime_state_hash_v100(self, self._source_live_version_v100())
            if before != str(entry.get("before_hash")):
                return {"ok": False, "reason": "before_hash_mismatch", "seq": seq, "replayed": replayed}
            self.execute_runtime_event(seq, str(entry.get("event_key", "")), str(entry.get("event_type", "")), dict(entry.get("request") or {}))
            after = runtime_state_hash_v100(self, self._source_live_version_v100())
            if after != str(entry.get("after_hash")):
                return {"ok": False, "reason": "after_hash_mismatch", "seq": seq, "replayed": replayed, "actual": after}
            replayed += 1
            expected_seq += 1
        return {"ok": True, "replayed": replayed, "head_hash": runtime_state_hash_v100(self, self._source_live_version_v100())}
