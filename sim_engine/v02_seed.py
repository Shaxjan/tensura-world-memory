from __future__ import annotations

import argparse
from pathlib import Path

from v02_engine import SimulationV02, format_world_minute


def seed_blumund_v02(db_path: str | Path) -> None:
    root = Path(__file__).resolve().parent
    start = 117 * 1440 + 8 * 60
    with SimulationV02.create(db_path, root / "v02_schema.sql", seed=117032, start_minute=start) as sim:
        locations = [
            ("south_gate", "Южные ворота Блюмунда", "gate", ["security", "traffic"]),
            ("central_square", "Центральная площадь", "square", ["social", "performance"]),
            ("free_guild", "Свободная гильдия", "guild", ["jobs", "rumors"]),
            ("east_inn", "Гостиница восточного квартала", "inn", ["food_service", "sleep"]),
            ("west_yard", "Старый тренировочный двор", "yard", ["training"]),
            ("market", "Утренний рынок", "market", ["food_service", "trade"]),
            ("workshop", "Мастерская Орена", "workshop", ["craft"]),
            ("print_room", "Рабочая комната Лиссы", "workshop", ["publishing"]),
        ]
        for row in locations:
            sim.add_location(*row)

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

        sim.add_item("food_ration", "Дорожный паёк", "food", 16, True)
        sim.add_item("guitar", "Гитара", "instrument", 900, False)
        sim.add_item("violin", "Скрипка", "instrument", 1200, False)

        sim.add_actor(
            "char_arlequino", "Маэстро Арлекино", location_id="east_inn", is_player=True,
            home_location_id="east_inn", cash_copper=21 * 10000 + 66 * 100 + 41,
            personality={"role": "player", "curiosity": 90, "sociability": 85, "discipline": 35},
            needs={"hunger": 18, "fatigue": 22, "loneliness": 15, "danger": 0},
        )
        sim.add_actor(
            "rena", "Рена", location_id="west_yard", home_location_id="east_inn", cash_copper=4000,
            personality={"role": "traveler", "curiosity": 70, "sociability": 45, "discipline": 75, "conformity": 25},
            needs={"hunger": 30, "fatigue": 25, "loneliness": 34, "danger": 4},
        )
        sim.add_actor(
            "lissa", "Лисса", location_id="print_room", home_location_id="east_inn", work_location_id="print_room",
            cash_copper=5500, personality={"role": "publisher", "curiosity": 68, "sociability": 55, "discipline": 90, "conformity": 40},
            needs={"hunger": 28, "fatigue": 30, "loneliness": 24, "danger": 2},
        )
        sim.add_actor(
            "oren", "Орен", location_id="workshop", home_location_id="east_inn", work_location_id="workshop",
            cash_copper=8000, personality={"role": "craftsman", "curiosity": 50, "sociability": 38, "discipline": 92, "conformity": 20},
            needs={"hunger": 32, "fatigue": 20, "loneliness": 18, "danger": 1},
        )
        sim.add_actor(
            "merchant", "Торговец Эрд", location_id="market", home_location_id="east_inn", work_location_id="market",
            cash_copper=32000, personality={"role": "merchant", "curiosity": 32, "sociability": 72, "discipline": 80, "conformity": 65},
            needs={"hunger": 24, "fatigue": 26, "loneliness": 32, "danger": 3},
        )
        sim.add_actor(
            "guard", "Стражник Дален", location_id="south_gate", home_location_id="east_inn", work_location_id="south_gate",
            cash_copper=9000, personality={"role": "guard", "curiosity": 25, "sociability": 40, "discipline": 95, "conformity": 55},
            needs={"hunger": 35, "fatigue": 35, "loneliness": 20, "danger": 20},
        )
        sim.add_actor(
            "courier", "Курьер Мель", location_id="market", home_location_id="east_inn",
            cash_copper=6500, personality={"role": "civilian", "curiosity": 78, "sociability": 75, "discipline": 70, "conformity": 50},
            needs={"hunger": 20, "fatigue": 18, "loneliness": 48, "danger": 4},
        )

        sim.adjust_item("rena", "guitar", 1)
        sim.adjust_item("char_arlequino", "violin", 1)
        sim.adjust_item("guard", "food_ration", 1)
        sim.adjust_item("courier", "food_ration", 2)

        for loc, resource, qty, cap in [
            ("market", "food", 14, 40),
            ("east_inn", "food", 18, 30),
            ("workshop", "wood", 18, 30),
            ("workshop", "string", 9, 20),
            ("workshop", "instrument", 0, 10),
            ("print_room", "paper", 12, 24),
            ("print_room", "ink", 8, 16),
            ("print_room", "publication", 0, 12),
        ]:
            sim.set_resource(loc, resource, qty, cap)

        for actor, prefs in {
            "rena": {"music": 55, "martial": 80, "romantic": 15, "showmanship": -20},
            "lissa": {"music": 45, "martial": 5, "romantic": 20, "showmanship": -5},
            "oren": {"music": 30, "martial": 0, "romantic": -20, "showmanship": -35},
            "merchant": {"music": 10, "martial": 15, "romantic": -5, "showmanship": 35},
            "guard": {"music": -10, "martial": 60, "romantic": -35, "showmanship": -45},
            "courier": {"music": 35, "martial": 10, "romantic": 5, "showmanship": 25},
        }.items():
            for tag, weight in prefs.items():
                sim.set_preference(actor, tag, weight)

        sim.set_relationship("rena", "char_arlequino", affinity=60, trust=45, respect=35)
        sim.set_relationship("lissa", "char_arlequino", affinity=35, trust=55, respect=60)
        sim.set_relationship("oren", "char_arlequino", affinity=20, trust=65, respect=55)
        sim.set_relationship("merchant", "guard", affinity=5, trust=20, respect=30)
        sim.set_relationship("courier", "merchant", affinity=12, trust=15, respect=5)

        sim.add_goal("rena", "train", 72, {"location_id": "west_yard"}, source="seed_character_goal")
        sim.add_goal("lissa", "publish", 84, {}, source="seed_project")
        sim.add_goal("oren", "produce_instrument", 82, {}, source="seed_project")
        sim.add_goal("merchant", "profit", 68, {}, source="seed_livelihood")
        sim.add_goal("guard", "security", 80, {"location_id": "south_gate"}, source="seed_duty")

        sim.set_fact(
            "jura.orc_tracks",
            {"location_id": "south_gate", "count_estimate": 45, "severity": 72, "organized": True},
            source="world_truth",
        )
        sim.teach_fact("guard", "jura.orc_tracks", source="guard_report", confidence=88)
        rumor = sim.seed_rumor(
            "courier",
            {"location_id": "south_gate", "count_estimate": 60, "severity": 66, "organized": "maybe"},
            fact_key="jura.orc_tracks",
            confidence=67,
        )
        sim.event("world_seeded", payload={"scenario": "blumund_v0.2", "rumor_id": rumor}, visibility="world")
        sim.db.commit()
        print(f"Created {db_path} at {format_world_minute(sim.now)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="blumund_v02.db")
    args = parser.parse_args()
    seed_blumund_v02(args.db)
