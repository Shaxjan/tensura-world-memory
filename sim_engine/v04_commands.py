from __future__ import annotations

from typing import Any

from v03_engine import DAY, dumps


DIFFICULTY_DC = {
    "easy": 8,
    "standard": 12,
    "hard": 16,
    "extreme": 20,
}

PLAYER_COMMANDS = {"travel", "buy", "attempt", "attack", "crime", "attend", "wait"}


class CommandTimeContextMixin:
    def _action_log(self, actor_id: str, command: str, params: dict[str, Any], accepted: bool, reason: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO action_log(world_minute,actor_id,command,params_json,accepted,rejection_reason) VALUES(?,?,?,?,?,?)",
            (self.now, actor_id, command, dumps(params), int(accepted), reason),
        )

    @staticmethod
    def _require_exact_keys(params: dict[str, Any], allowed: set[str]) -> None:
        extra = set(params) - allowed
        missing = allowed - set(params)
        if extra or missing:
            raise ValueError(f"invalid parameters; missing={sorted(missing)} extra={sorted(extra)}")

    def submit_player_command(self, player_id: str, command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        actor = self.actor(player_id)
        if not int(actor["is_player"]):
            raise ValueError("command firewall is for player actors")
        if command not in PLAYER_COMMANDS:
            self._action_log(player_id, command, params, False, "command_not_allowed")
            self.db.commit()
            return {"accepted": False, "reason": "command_not_allowed"}

        try:
            if command == "travel":
                self._require_exact_keys(params, {"destination"})
                destination = str(params["destination"])
                if self.db.execute("SELECT 1 FROM regions WHERE id=?", (destination,)).fetchone() is None:
                    raise ValueError("unknown destination")
                result = {"due_at": self.start_actor_travel(player_id, destination)}

            elif command == "buy":
                self._require_exact_keys(params, {"commodity", "qty"})
                qty = int(params["qty"])
                if not 1 <= qty <= 1000:
                    raise ValueError("qty out of range")
                result = {"spent_copper": self.buy_from_market(player_id, str(params["commodity"]), qty), "qty": qty}

            elif command == "attempt":
                self._require_exact_keys(params, {"skill", "difficulty"})
                difficulty = str(params["difficulty"])
                if difficulty not in DIFFICULTY_DC:
                    raise ValueError("invalid difficulty")
                result = self.skill_check(
                    player_id,
                    str(params["skill"]),
                    DIFFICULTY_DC[difficulty],
                    namespace=f"player_attempt:{difficulty}",
                )

            elif command == "attack":
                self._require_exact_keys(params, {"target"})
                result = self.resolve_attack(player_id, str(params["target"]))

            elif command == "crime":
                self._require_exact_keys(params, {"code"})
                result = self.record_crime(player_id, str(params["code"]))

            elif command == "attend":
                self._require_exact_keys(params, {"appointment_id"})
                result = self.attend_appointment(player_id, int(params["appointment_id"]))

            elif command == "wait":
                self._require_exact_keys(params, {"minutes"})
                minutes = int(params["minutes"])
                if not 1 <= minutes <= DAY:
                    raise ValueError("wait out of range")
                self._action_log(player_id, command, params, True)
                self.db.commit()
                self.advance(minutes)
                return {"accepted": True, "result": {"world_minute": self.now}}

            else:
                raise ValueError("unreachable command")

            self._action_log(player_id, command, params, True)
            self.db.commit()
            return {"accepted": True, "result": result}

        except Exception as exc:
            self.db.rollback()
            self._action_log(player_id, command, params, False, str(exc))
            self.db.commit()
            return {"accepted": False, "reason": str(exc)}

    def _next_v04_due(self, target: int) -> int:
        candidates = [target]
        for q in [
            "SELECT MIN(due_at) FROM actor_travel WHERE status='traveling'",
            "SELECT MIN(due_at) FROM canon_events WHERE status='scheduled'",
            "SELECT MIN(due_at) FROM legal_cases WHERE status='pending'",
        ]:
            v = self.db.execute(q).fetchone()[0]
            if v is not None and self.now < int(v) <= target:
                candidates.append(int(v))

        for appt in self.db.execute(
            "SELECT due_at,grace_minutes FROM appointments WHERE status IN ('scheduled','waiting')"
        ).fetchall():
            due = int(appt["due_at"])
            grace = due + int(appt["grace_minutes"])
            if self.now < due <= target:
                candidates.append(due)
            elif self.now < grace <= target:
                candidates.append(grace)

        try:
            mem_due = int(self.get_meta("next_memory_decay_at"))
            if self.now < mem_due <= target:
                candidates.append(mem_due)
        except KeyError:
            pass
        return min(candidates)

    def _process_v04_due(self) -> None:
        self._complete_actor_travel()
        self._process_canon_events()
        self._process_legal_cases()
        self._process_appointments()
        try:
            next_decay = int(self.get_meta("next_memory_decay_at"))
        except KeyError:
            next_decay = self.now + DAY
            self.set_meta("next_memory_decay_at", next_decay)
        while self.now >= next_decay:
            self._decay_memories()
            next_decay += DAY
            self.set_meta("next_memory_decay_at", next_decay)

    def advance(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("time backwards")
        target = self.now + int(minutes)
        self._process_v04_due()
        while self.now < target:
            nxt = self._next_v04_due(target)
            super().advance(nxt - self.now)
            self._process_v04_due()
        self.db.commit()

    def build_context(self, player_id: str = "player", max_events: int = 8) -> dict[str, Any]:
        ctx = super().build_context(player_id, max_events=max_events)
        region = str(ctx["player"]["region"])
        st = self.stats(player_id)
        ctx["player"]["hp"] = int(st["hp"])
        ctx["player"]["max_hp"] = int(st["max_hp"])
        ctx["player"]["alive"] = bool(st["alive"])
        ctx["player"]["status"] = str(self.actor(player_id)["status"])
        ctx["reputation"] = self.reputation(player_id, region)

        ctx["active_injuries"] = [
            {"kind": str(r["kind"]), "severity": int(r["severity"])}
            for r in self.db.execute(
                "SELECT kind,severity FROM injuries WHERE actor_id=? AND status='active' ORDER BY severity DESC LIMIT 5",
                (player_id,),
            )
        ]
        ctx["memories"] = [
            {"key": str(r["memory_key"]), "summary": str(r["summary"]), "salience": int(r["salience"])}
            for r in self.db.execute(
                "SELECT memory_key,summary,salience FROM memories WHERE actor_id=? AND status='active' "
                "ORDER BY salience DESC,last_recalled_at DESC LIMIT 6",
                (player_id,),
            )
        ]
        ctx["upcoming_appointments"] = [
            {
                "id": int(r["id"]),
                "counterpart": str(r["counterpart_id"]),
                "region": str(r["region_id"]),
                "due_at": int(r["due_at"]),
                "purpose": str(r["purpose"]),
            }
            for r in self.db.execute(
                "SELECT * FROM appointments WHERE actor_id=? AND status IN ('scheduled','waiting') AND due_at<=? "
                "ORDER BY due_at LIMIT 5",
                (player_id, self.now + DAY),
            )
        ]
        ctx["legal_status"] = [
            {"code": str(r["code"]), "fine_copper": int(r["fine_copper"]), "status": str(r["status"])}
            for r in self.db.execute(
                "SELECT code,fine_copper,status FROM crimes WHERE actor_id=? AND status IN ('reported','wanted') "
                "ORDER BY occurred_at DESC LIMIT 5",
                (player_id,),
            )
        ]
        return ctx
