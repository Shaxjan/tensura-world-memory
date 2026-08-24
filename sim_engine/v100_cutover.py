from __future__ import annotations

from typing import Any

from v03_engine import dumps


def install_v100_runtime(world: Any, source_live_version: int, legacy_pointer: dict[str, Any], legacy_pointer_blob_sha: str) -> None:
    policy = {
        "mode": "append_only",
        "journal_before_pointer": True,
        "checkpoint_every": 25,
        "replay_required": True,
        "unknown_policy": "UNKNOWN stays UNKNOWN",
    }
    with world.db:
        world.db.execute(
            "INSERT OR REPLACE INTO runtime_cutover(id,source_live_version,legacy_pointer_json,legacy_pointer_blob_sha,mode,journal_policy_json,created_at) "
            "VALUES(1,?,?,?,?,?,?)",
            (int(source_live_version), dumps(legacy_pointer), str(legacy_pointer_blob_sha), "candidate", dumps(policy), world.now),
        )
        for code, detail in {
            "pending_resolution_executor": "Typed resolver must close ordinary scene pending outcomes without free-form state mutation.",
            "append_only_runtime_journal": "Every prospective runtime transition must replay from immutable checkpoint with the same state hash.",
            "legacy_v159_rollback_anchor": "The exact pre-cutover LIVE pointer must remain preserved and verifiable.",
        }.items():
            world.db.execute(
                "INSERT OR REPLACE INTO cutover_gate(gate_code,status,classification,detail,evidence_json,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (code, "active", "runtime", detail, "[]", world.now),
            )
        world.db.execute(
            "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
            ("runtime_mode", '"v100_cutover_candidate"', "engine:v1.0"),
        )


def resolve_v100_gate(world: Any, gate_code: str, detail: str, evidence: list[Any]) -> None:
    with world.db:
        world.db.execute(
            "UPDATE cutover_gate SET status='resolved',detail=?,evidence_json=?,updated_at=? WHERE gate_code=?",
            (detail, dumps(evidence), world.now, gate_code),
        )


def activate_v100_runtime(world: Any) -> None:
    active = [str(r[0]) for r in world.db.execute(
        "SELECT gate_code FROM cutover_gate WHERE status!='resolved' ORDER BY gate_code"
    ).fetchall()]
    if active:
        raise RuntimeError("cutover gates still active:" + ",".join(active))
    with world.db:
        world.db.execute("UPDATE runtime_cutover SET mode='engine_authoritative' WHERE id=1")
        world.db.execute(
            "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
            ("runtime_mode", '"v100_engine_authoritative"', "engine:v1.0"),
        )
