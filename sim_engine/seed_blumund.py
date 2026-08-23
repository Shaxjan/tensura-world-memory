from __future__ import annotations

import argparse
from pathlib import Path

from sim import Simulation, format_world_minute


def seed_blumund(db_path: str | Path) -> None:
    root = Path(__file__).resolve().parent
    start = 117 * 1440 + 8 * 60  # T+117 08:00
    with Simulation.create(db_path, root / "schema.sql", seed=117031, start_minute=start) as sim:
        # Small spatial graph. Distances are explicit and therefore enforce travel time.
        for loc_id, name, kind in [
            ("south_gate", "Южные ворота Блюмунда", "gate"),
            ("central_square", "Центральная площадь", "square"),
            ("free_guild", "Свободная гильдия", "guild"),
            ("east_inn", "Гостиница восточного квартала", "inn"),
            ("west_yard", "Старый тренировочный двор", "yard"),
            ("market", "Утренний рынок", "market"),
            ("workshop", "Мастерская Орена", "workshop"),
            ("print_room", "Рабочая комната Лиссы", "workshop"),
        ]:
            sim.add_location(loc_id, name, kind)

        for a, b, minutes in [
            ("south_gate", "central_square", 12),
            ("central_square", "free_guild", 5),
            ("central_square", "market", 7),
            ("market", "east_inn", 8),
            ("central_square", "west_yard", 16),
            ("free_guild", "workshop", 9),
            ("free_guild", "print_room", 6),
            ("east_inn", "free_guild", 13),
        ]:
            sim.connect(a, b, minutes)

        sim.add_actor(
            "char_arlequino", "Маэстро Арлекино",
            location_id="east_inn", is_player=True,
            home_location_id="east_inn",
            cash_copper=21 * 10_000 + 66 * 100 + 41,
            personality={"curiosity": 90, "sociability": 85, "discipline": 35},
            goals=["travel", "music", "cultural projects"],
        )
        sim.add_actor(
            "rena", "Рена",
            location_id="west_yard", home_location_id="east_inn",
            cash_copper=4_000, energy=86, mood=4,
            personality={"curiosity": 70, "sociability": 45, "discipline": 75},
            goals=["train", "independence", "travel"],
        )
        sim.add_actor(
            "lissa", "Лисса",
            location_id="print_room", home_location_id="east_inn", work_location_id="print_room",
            cash_copper=5_500, energy=82, mood=8,
            personality={"curiosity": 68, "sociability": 55, "discipline": 90},
            goals=["publish", "organize"],
        )
        sim.add_actor(
            "oren", "Орен",
            location_id="workshop", home_location_id="east_inn", work_location_id="workshop",
            cash_copper=8_000, energy=88, mood=0,
            personality={"curiosity": 50, "sociability": 38, "discipline": 92},
            goals=["instrument production", "logistics"],
        )
        sim.add_actor(
            "merchant", "Торговец Эрд",
            location_id="market", home_location_id="east_inn", work_location_id="market",
            cash_copper=32_000, energy=78, mood=-3,
            personality={"curiosity": 32, "sociability": 72, "discipline": 80},
            goals=["profit", "family"],
        )
        sim.add_actor(
            "guard", "Стражник Дален",
            location_id="south_gate", home_location_id="east_inn", work_location_id="south_gate",
            cash_copper=9_000, energy=73, mood=1,
            personality={"curiosity": 25, "sociability": 40, "discipline": 95},
            goals=["duty", "security"],
        )

        # Different tastes => different reactions to the same stimulus.
        for actor, prefs in {
            "rena": {"music": 50, "martial": 75, "romantic": 15, "showmanship": -15},
            "lissa": {"music": 45, "martial": 5, "romantic": 20, "showmanship": -5},
            "oren": {"music": 30, "martial": 0, "romantic": -20, "showmanship": -30},
            "merchant": {"music": 10, "martial": 20, "romantic": -5, "showmanship": 30},
            "guard": {"music": -5, "martial": 55, "romantic": -35, "showmanship": -40},
        }.items():
            for tag, weight in prefs.items():
                sim.set_preference(actor, tag, weight)

        sim.set_relationship("rena", "char_arlequino", affinity=60, trust=45, respect=35)
        sim.set_relationship("lissa", "char_arlequino", affinity=35, trust=55, respect=60)
        sim.set_relationship("oren", "char_arlequino", affinity=20, trust=65, respect=55)

        # Objective truth is separate from who knows it.
        sim.set_fact("departure.eurazania.time", {"day": "T+117", "time": "18:00"}, source="contract")
        sim.set_fact("departure.eurazania.destination", "Eurazania", source="contract")
        sim.teach_fact("char_arlequino", "departure.eurazania.time", source="signed_contract")
        sim.teach_fact("char_arlequino", "departure.eurazania.destination", source="signed_contract")

        sim.event("world_seeded", payload={"scenario": "blumund_v0.1"})
        sim.db.commit()

        print(f"Created {db_path} at {format_world_minute(sim.now)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="blumund_demo.db")
    args = parser.parse_args()
    seed_blumund(args.db)
