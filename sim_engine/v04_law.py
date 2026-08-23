from __future__ import annotations

from typing import Any


class LawAppointmentsMixin:
    def set_law(self, region_id: str, code: str, severity: int, fine_copper: int, jail_minutes: int = 0) -> None:
        self.db.execute(
            "INSERT INTO laws(region_id,code,severity,fine_copper,jail_minutes) VALUES(?,?,?,?,?) "
            "ON CONFLICT(region_id,code) DO UPDATE SET severity=excluded.severity,"
            "fine_copper=excluded.fine_copper,jail_minutes=excluded.jail_minutes",
            (region_id, code, severity, fine_copper, jail_minutes),
        )

    def ensure_reputation(self, actor_id: str, region_id: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO reputation(actor_id,region_id,public,authority,underworld) VALUES(?,?,0,0,0)",
            (actor_id, region_id),
        )

    def reputation(self, actor_id: str, region_id: str) -> dict[str, int]:
        self.ensure_reputation(actor_id, region_id)
        r = self.db.execute(
            "SELECT public,authority,underworld FROM reputation WHERE actor_id=? AND region_id=?",
            (actor_id, region_id),
        ).fetchone()
        return {k: int(r[k]) for k in ("public", "authority", "underworld")}

    def _change_reputation(self, actor_id: str, region_id: str, **deltas: int) -> None:
        self.ensure_reputation(actor_id, region_id)
        for field, delta in deltas.items():
            if field not in {"public", "authority", "underworld"}:
                raise ValueError(field)
            self.db.execute(
                f"UPDATE reputation SET {field}=MAX(-100,MIN(100,{field}+?)) WHERE actor_id=? AND region_id=?",
                (int(delta), actor_id, region_id),
            )

    def record_crime(self, actor_id: str, code: str, *, witnessed: bool | None = None) -> dict[str, Any]:
        actor = self.actor(actor_id)
        region = str(actor["region_id"])
        law = self.db.execute("SELECT * FROM laws WHERE region_id=? AND code=?", (region, code)).fetchone()
        if law is None:
            raise ValueError(f"no such law in {region}: {code}")

        if witnessed is None:
            security = int(self.db.execute("SELECT security FROM regions WHERE id=?", (region,)).fetchone()[0])
            rng = self._rng(f"witness:{actor_id}:{code}:{region}")
            witnessed = rng.randint(1, 100) <= min(95, 15 + security)
            evidence = rng.randint(35, 100) if witnessed else rng.randint(0, 20)
        else:
            evidence = 80 if witnessed else 0

        fine = int(law["fine_copper"]) if witnessed else 0
        status = "reported" if witnessed else "unreported"
        cur = self.db.execute(
            "INSERT INTO crimes(actor_id,region_id,code,witnessed,evidence,fine_copper,status,occurred_at) VALUES(?,?,?,?,?,?,?,?)",
            (actor_id, region, code, int(witnessed), evidence, fine, status, self.now),
        )
        crime_id = int(cur.lastrowid)

        if witnessed:
            severity = int(law["severity"])
            self._change_reputation(
                actor_id,
                region,
                authority=-max(1, severity // 4),
                public=-max(0, severity // 10),
                underworld=max(0, severity // 12),
            )
            guard = self.db.execute(
                "SELECT id FROM factions WHERE kind='guard' AND home_region_id=? ORDER BY id LIMIT 1",
                (region,),
            ).fetchone()
            security = int(self.db.execute("SELECT security FROM regions WHERE id=?", (region,)).fetchone()[0])
            delay = max(20, 240 - security * 2)
            self.db.execute(
                "INSERT INTO legal_cases(crime_id,authority_faction_id,due_at,status) VALUES(?,?,?,'pending')",
                (crime_id, str(guard["id"]) if guard else None, self.now + delay),
            )
            self.event(
                "crime_reported",
                region=region,
                actor=actor_id,
                faction=str(guard["id"]) if guard else None,
                significance=max(50, severity),
                payload={"crime_id": crime_id, "code": code, "evidence": evidence},
            )
        else:
            self.event(
                "crime_unobserved",
                region=region,
                actor=actor_id,
                significance=20,
                payload={"crime_id": crime_id, "code": code},
                visibility="hidden_engine",
            )
        return {"crime_id": crime_id, "witnessed": bool(witnessed), "evidence": evidence, "fine_copper": fine, "status": status}

    def _process_legal_cases(self) -> None:
        rows = self.db.execute(
            "SELECT * FROM legal_cases WHERE status='pending' AND due_at<=? ORDER BY due_at,id",
            (self.now,),
        ).fetchall()
        for case in rows:
            crime = self.db.execute("SELECT * FROM crimes WHERE id=?", (case["crime_id"],)).fetchone()
            self.db.execute(
                "UPDATE legal_cases SET status='summons_issued',resolution='awaiting_actor' WHERE id=?",
                (case["id"],),
            )
            self.db.execute("UPDATE crimes SET status='wanted' WHERE id=?", (crime["id"],))
            self.event(
                "legal_summons",
                region=str(crime["region_id"]),
                actor=str(crime["actor_id"]),
                faction=case["authority_faction_id"],
                significance=75,
                payload={"crime_id": int(crime["id"]), "code": str(crime["code"]), "fine_copper": int(crime["fine_copper"])},
            )

    def schedule_appointment(
        self,
        actor_id: str,
        counterpart_id: str,
        region_id: str,
        due_at: int,
        *,
        grace_minutes: int = 30,
        purpose: str,
    ) -> int:
        if due_at <= self.now:
            raise ValueError("appointment must be in the future")
        self.actor(actor_id)
        self.actor(counterpart_id)
        cur = self.db.execute(
            "INSERT INTO appointments(actor_id,counterpart_id,region_id,due_at,grace_minutes,status,purpose,created_at) "
            "VALUES(?,?,?,?,?,'scheduled',?,?)",
            (actor_id, counterpart_id, region_id, due_at, grace_minutes, purpose, self.now),
        )
        return int(cur.lastrowid)

    def _process_appointments(self) -> None:
        rows = self.db.execute(
            "SELECT * FROM appointments WHERE status IN ('scheduled','waiting') AND due_at<=? ORDER BY due_at,id",
            (self.now,),
        ).fetchall()
        for appt in rows:
            a = self.actor(str(appt["actor_id"]))
            b = self.actor(str(appt["counterpart_id"]))
            region = str(appt["region_id"])
            grace_end = int(appt["due_at"]) + int(appt["grace_minutes"])
            involves_player = bool(int(a["is_player"]) or int(b["is_player"]))

            if involves_player:
                if self.now >= grace_end:
                    self.db.execute("UPDATE appointments SET status='missed' WHERE id=?", (appt["id"],))
                    self.event(
                        "appointment_missed",
                        region=region,
                        actor=str(appt["actor_id"]),
                        significance=55,
                        payload={"appointment_id": int(appt["id"]), "counterpart": str(appt["counterpart_id"]), "purpose": str(appt["purpose"])},
                    )
                elif str(appt["status"]) == "scheduled":
                    self.db.execute("UPDATE appointments SET status='waiting' WHERE id=?", (appt["id"],))
                    self.event(
                        "appointment_due",
                        region=region,
                        actor=str(appt["actor_id"]),
                        significance=45,
                        payload={"appointment_id": int(appt["id"]), "counterpart": str(appt["counterpart_id"]), "purpose": str(appt["purpose"])},
                    )
                continue

            if str(a["region_id"]) == region and str(b["region_id"]) == region and self.now <= grace_end:
                self.db.execute("UPDATE appointments SET status='met' WHERE id=?", (appt["id"],))
                self.event(
                    "appointment_met",
                    region=region,
                    actor=str(appt["actor_id"]),
                    significance=45,
                    payload={"appointment_id": int(appt["id"]), "counterpart": str(appt["counterpart_id"]), "purpose": str(appt["purpose"])},
                )
            elif self.now >= grace_end:
                self.db.execute("UPDATE appointments SET status='missed' WHERE id=?", (appt["id"],))
                self.event(
                    "appointment_missed",
                    region=region,
                    actor=str(appt["actor_id"]),
                    significance=55,
                    payload={"appointment_id": int(appt["id"]), "counterpart": str(appt["counterpart_id"]), "purpose": str(appt["purpose"])},
                )

    def attend_appointment(self, player_id: str, appointment_id: int) -> dict[str, Any]:
        appt = self.db.execute(
            "SELECT * FROM appointments WHERE id=? AND status IN ('scheduled','waiting')",
            (int(appointment_id),),
        ).fetchone()
        if appt is None:
            raise ValueError("appointment is not attendable")
        if player_id not in {str(appt["actor_id"]), str(appt["counterpart_id"])}:
            raise ValueError("player is not part of appointment")
        if self.now < int(appt["due_at"]):
            raise ValueError("appointment is not due yet")
        if self.now > int(appt["due_at"]) + int(appt["grace_minutes"]):
            raise ValueError("appointment grace period has expired")

        other_id = str(appt["counterpart_id"]) if str(appt["actor_id"]) == player_id else str(appt["actor_id"])
        player = self.actor(player_id)
        other = self.actor(other_id)
        region = str(appt["region_id"])
        if str(player["region_id"]) != region or str(other["region_id"]) != region:
            raise ValueError("participants are not co-located at appointment region")

        self.db.execute("UPDATE appointments SET status='met' WHERE id=?", (appt["id"],))
        self.event(
            "appointment_met",
            region=region,
            actor=player_id,
            significance=45,
            payload={"appointment_id": int(appt["id"]), "counterpart": other_id, "purpose": str(appt["purpose"])},
        )
        return {"appointment_id": int(appt["id"]), "status": "met", "counterpart": other_id}
