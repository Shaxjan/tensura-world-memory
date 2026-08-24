from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from v03_engine import loads
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v104_repository import load_repository_runtime_v104
from v105_seed import seed_world_v105_migration


def _scheduler(world):
    row = world.db.execute(
        "SELECT handler,next_due_at,cadence_minutes,tick_count,last_run_at,status,last_outcome_json "
        "FROM autonomy_runtime WHERE commitment_key='task:borga'"
    ).fetchone()
    return dict(row) if row else None


def _run_shadow(snapshot, source_v: int, source_seq: int, old_session: dict, db_path: Path):
    world = seed_world_v105_migration(db_path)
    restored = import_portable_checkpoint_v100(world, snapshot)
    if not restored.get("ok"):
        world.close()
        raise RuntimeError("v1.0.5 shadow import failed")
    seq = source_seq + 1
    event = world.execute_runtime_event(
        seq,
        f"rehearsal-v105-character-autonomy-{seq}",
        "character_autonomy_activation",
        {"reason": "shadow migration rehearsal"},
    )
    entry = event["journal"]
    activation_head = runtime_state_hash_v100(world, source_v)
    scheduler_after_activation = _scheduler(world)
    if scheduler_after_activation is None:
        world.close()
        raise RuntimeError("Borga scheduler missing after shadow activation")
    activation_session = world.build_session_state_v105(
        journal_seq=seq,
        head_state_hash=activation_head,
        last_event=entry,
        preserved_last_turn=old_session.get("last_turn"),
    )
    due = int(scheduler_after_activation["next_due_at"])
    delta = max(0, due - int(world.now))
    decision_minute = int(world.now) + delta
    expected_presence = world._borga_presence103(decision_minute)
    expected_code = (
        "character_work_progressed"
        if (expected_presence or {}).get("plan_block_kind") == "role_duty" and (expected_presence or {}).get("place_key")
        else "character_work_deferred"
    )
    world.advance(delta)
    scheduler_after_tick = _scheduler(world)
    log = world.db.execute(
        "SELECT * FROM autonomy_execution_log WHERE commitment_key='task:borga' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    log = dict(log) if log else None
    outcome = loads(log["outcome_json"], {}) if log else None
    state = world.character_autonomy_v105("borga")
    final_hash = runtime_state_hash_v100(world, source_v)
    return {
        "world": world,
        "seq": seq,
        "entry": entry,
        "activation_head": activation_head,
        "scheduler_after_activation": scheduler_after_activation,
        "scheduler_after_tick": scheduler_after_tick,
        "decision_delta": delta,
        "expected_presence": expected_presence,
        "expected_code": expected_code,
        "log": log,
        "outcome": outcome,
        "autonomy_state": state,
        "session": activation_session,
        "final_hash": final_hash,
    }


def rehearse(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    pointer = json.loads((root / "runtime/runtime_state.json").read_text(encoding="utf-8"))
    if pointer.get("engine_version") != "1.0.4":
        raise RuntimeError("v1.0.5 rehearsal expects current LIVE engine 1.0.4")
    old_session = json.loads((root / "runtime/session_state.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as td:
        source, loaded, _ = load_repository_runtime_v104(root, Path(td) / "source.db")
        try:
            source_seq = int(loaded["journal_seq"])
            source_hash = str(loaded["head_state_hash"])
            source_v = int(pointer["source_live_version"])
            time0 = int(source.now)
            cash0 = int(source.actor("player")["cash_copper"])
            region0 = str(source.actor("player")["region_id"])
            scheduler_before = _scheduler(source)
            if scheduler_before is None:
                raise RuntimeError("current LIVE lacks task:borga scheduler row")
            snapshot = export_portable_checkpoint_v100(source, source_v)
            if snapshot["state_hash"] != source_hash:
                raise RuntimeError("source compact snapshot mismatch")
        finally:
            source.close()

        first = _run_shadow(snapshot, source_v, source_seq, old_session, Path(td) / "shadow1.db")
        try:
            activation_time = int(first["entry"]["world_minute"])
            cash_after = int(first["world"].actor("player")["cash_copper"])
            region_after = str(first["world"].actor("player")["region_id"])
            activation_entry = first["entry"]
        finally:
            first["world"].close()

        second = _run_shadow(snapshot, source_v, source_seq, old_session, Path(td) / "shadow2.db")
        try:
            deterministic_shadow = second["final_hash"] == first["final_hash"] and second["outcome"] == first["outcome"]
        finally:
            second["world"].close()

        verifier = seed_world_v105_migration(Path(td) / "verify.db")
        try:
            check = import_portable_checkpoint_v100(verifier, snapshot)
            if not check.get("ok"):
                raise RuntimeError("verifier base import failed")
            replay = verifier.replay_runtime_entries([activation_entry])
            replay_hash = runtime_state_hash_v100(verifier, source_v)
        finally:
            verifier.close()

    before = scheduler_before
    after_activation = first["scheduler_after_activation"]
    after_tick = first["scheduler_after_tick"]
    outcome = first["outcome"] or {}
    autonomy = first["autonomy_state"] or {}
    report = {
        "source_seq": source_seq,
        "shadow_seq": source_seq + 1,
        "activation_time_preserved": activation_time == time0,
        "cash_preserved": cash_after == cash0,
        "region_preserved": region_after == region0,
        "old_handler": before.get("handler"),
        "new_handler": after_activation.get("handler"),
        "due_preserved": after_activation.get("next_due_at") == before.get("next_due_at"),
        "cadence_preserved": after_activation.get("cadence_minutes") == before.get("cadence_minutes"),
        "tick_count_preserved_on_activation": after_activation.get("tick_count") == before.get("tick_count"),
        "status_preserved": after_activation.get("status") == before.get("status"),
        "decision_delta": first["decision_delta"],
        "decision_outcome": outcome.get("code"),
        "expected_decision_outcome": first["expected_code"],
        "decision_matches_plan": outcome.get("code") == first["expected_code"],
        "decision_hidden": bool(first["log"]) and int(first["log"].get("visible_to_player") or 0) == 0,
        "completion_not_asserted": outcome.get("completion_asserted") is False,
        "tick_advanced_once": int(after_tick.get("tick_count") or 0) == int(before.get("tick_count") or 0) + 1,
        "shared_scheduler": first["session"].get("character_runtime", {}).get("shared_scheduler") is True,
        "session_engine": first["session"].get("engine_version"),
        "last_gameplay_turn_preserved": first["session"].get("last_turn") == old_session.get("last_turn"),
        "autonomy_materialized": autonomy.get("format") == "TENSURA_CHARACTER_AUTONOMY",
        "grounded_workstreams": autonomy.get("grounded_workstreams"),
        "activation_journal_replay_ok": bool(replay.get("ok")) and replay_hash == first["activation_head"],
        "deterministic_shadow": deterministic_shadow,
    }
    report["technical_success"] = all(
        [
            report["activation_time_preserved"],
            report["cash_preserved"],
            report["region_preserved"],
            report["new_handler"] == "character_task_v105",
            report["due_preserved"],
            report["cadence_preserved"],
            report["tick_count_preserved_on_activation"],
            report["status_preserved"],
            report["decision_matches_plan"],
            report["decision_hidden"],
            report["completion_not_asserted"],
            report["tick_advanced_once"],
            report["shared_scheduler"],
            report["session_engine"] == "1.0.5",
            report["last_gameplay_turn_preserved"],
            report["autonomy_materialized"],
            bool(report["grounded_workstreams"]),
            report["activation_journal_replay_ok"],
            report["deterministic_shadow"],
        ]
    )
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default="..")
    ap.add_argument("--out")
    args = ap.parse_args()
    report = rehearse(args.repo_root)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    if not report["technical_success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
