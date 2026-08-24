from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from v06_migration import collect_repo_campaign
from v10_runtime import apply_v10_shadow_cutover, mark_v10_shadow_verified
from v100_handoff import export_portable_checkpoint_v100, import_portable_checkpoint_v100, runtime_state_hash_v100
from v100_repository import build_runtime_pointer
from v100_runtime import activate_v100_runtime, install_v100_runtime, resolve_v100_gate
from v100_seed import seed_world_v100_migration


def git_blob_sha(text: str) -> str:
    raw = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _core(world):
    p = world.actor("player")
    return {"time": world.now, "region": str(p["region_id"]), "cash": int(p["cash_copper"])}


def run(repo_root: str | Path, *, checkpoint_out: str | None = None, manifest_out: str | None = None) -> dict:
    repo = Path(repo_root).resolve()
    package = collect_repo_campaign(repo)
    source_v = int(package.pointer.get("v") or 0)
    pointer_sha = git_blob_sha(package.pointer_doc.text)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        source_db = td / "source.db"
        with seed_world_v100_migration(source_db) as source:
            report = apply_v10_shadow_cutover(source, package, repo)
            if report.get("errors") or not report.get("baseline_ready"):
                return {"source_version": source_v, "actual_cutover_ready": False, "errors": report.get("errors", ["v10_baseline_failed"])}

            # Re-prove v0.10's final shadow gate on an isolated copy; do not advance the real cutover base.
            v10_base = export_portable_checkpoint_v100(source, source_v)
            verify_db = td / "v10_verify.db"
            with seed_world_v100_migration(verify_db) as verify:
                rt = import_portable_checkpoint_v100(verify, v10_base)
                before = _core(verify) if rt.get("ok") else None
                search = verify.process_player_turn("v100-v10-find-borga", "Иду искать Боргу.") if rt.get("ok") else None
                after_search = _core(verify) if rt.get("ok") else None
                pending_nav = int(verify.db.execute(
                    "SELECT COUNT(*) FROM scene_pending_resolution WHERE resolution_kind='local_navigation' AND status='pending'"
                ).fetchone()[0]) if rt.get("ok") else 0
                exec_before = int(verify.db.execute("SELECT COUNT(*) FROM autonomy_execution_log").fetchone()[0]) if rt.get("ok") else 0
                wait = verify.process_player_turn("v100-v10-wait", "жду 15 минут") if rt.get("ok") else None
                exec_after = int(verify.db.execute("SELECT COUNT(*) FROM autonomy_execution_log").fetchone()[0]) if rt.get("ok") else 0
                v10_shadow_ok = bool(
                    rt.get("ok") and search and search.get("accepted") and search.get("status") == "scene_pending"
                    and before == after_search and pending_nav > 0
                    and wait and wait.get("accepted") and wait.get("status") == "executed"
                    and exec_after > exec_before
                    and str(verify.actor("player")["region_id"]) == before["region"]
                    and int(verify.actor("player")["cash_copper"]) == before["cash"]
                )
            if not v10_shadow_ok:
                return {"source_version": source_v, "actual_cutover_ready": False, "errors": ["v10_shadow_reproof_failed"]}
            mark_v10_shadow_verified(source, ["v1.0 isolated reproof", "pending local navigation", "autonomy advanced"])

            install_v100_runtime(source, source_v, package.pointer, pointer_sha)
            candidate = export_portable_checkpoint_v100(source, source_v)

            # Execute three runtime events on a clone: scene action -> typed resolution -> authoritative wait.
            exec_db = td / "journal_exec.db"
            with seed_world_v100_migration(exec_db) as execution:
                imported = import_portable_checkpoint_v100(execution, candidate)
                if not imported.get("ok"):
                    return {"source_version": source_v, "actual_cutover_ready": False, "errors": ["candidate_import_failed"]}
                event1 = execution.execute_runtime_event(1, "v100-probe-find-borga", "player_turn", {"raw_text": "Иду искать Боргу."})
                pending = execution.db.execute(
                    "SELECT id FROM scene_pending_resolution WHERE resolution_kind='local_navigation' AND status='pending' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if pending is None:
                    return {"source_version": source_v, "actual_cutover_ready": False, "errors": ["resolver_probe_missing_pending"]}
                event2 = execution.execute_runtime_event(2, "v100-probe-resolve-borga-search", "scene_resolution", {
                    "pending_id": int(pending[0]),
                    "resolver": "shadow-gm",
                    "payload": {"outcome": "not_found", "note": "Probe resolves the attempt without inventing Borga's location.", "evidence": ["v1.0 typed resolver probe"]},
                })
                event3 = execution.execute_runtime_event(3, "v100-probe-wait", "player_turn", {"raw_text": "жду 15 минут"})
                entries = [event1["journal"], event2["journal"], event3["journal"]]
                execution_hash = runtime_state_hash_v100(execution, source_v)
                resolver_ok = bool(
                    event1.get("accepted") and event2.get("accepted") and event3.get("accepted")
                    and event2.get("result", {}).get("accepted")
                    and event2.get("result", {}).get("outcome") == "not_found"
                    and execution.db.execute("SELECT COUNT(*) FROM scene_resolution_log").fetchone()[0] >= 1
                )

            replay_db = td / "journal_replay.db"
            with seed_world_v100_migration(replay_db) as replay_world:
                imported2 = import_portable_checkpoint_v100(replay_world, candidate)
                replay = replay_world.replay_runtime_entries(entries) if imported2.get("ok") else {"ok": False}
                replay_hash = runtime_state_hash_v100(replay_world, source_v) if imported2.get("ok") else None
                replay_ok = bool(replay.get("ok") and replay_hash == execution_hash and replay.get("replayed") == 3)

            rollback_row = source.db.execute("SELECT legacy_pointer_json,legacy_pointer_blob_sha FROM runtime_cutover WHERE id=1").fetchone()
            rollback_ok = bool(
                rollback_row
                and json.loads(str(rollback_row["legacy_pointer_json"])) == package.pointer
                and str(rollback_row["legacy_pointer_blob_sha"]) == pointer_sha
                and pointer_sha == git_blob_sha(package.pointer_doc.text)
            )
            if not resolver_ok:
                return {"source_version": source_v, "actual_cutover_ready": False, "errors": ["typed_resolution_probe_failed"]}
            if not replay_ok:
                return {"source_version": source_v, "actual_cutover_ready": False, "errors": ["journal_replay_probe_failed"]}
            if not rollback_ok:
                return {"source_version": source_v, "actual_cutover_ready": False, "errors": ["rollback_anchor_failed"]}

            resolve_v100_gate(source, "pending_resolution_executor", "Typed pending-resolution API passed isolated scene-resolution replay probe.", ["local_navigation:not_found", "no invented target location"])
            resolve_v100_gate(source, "append_only_runtime_journal", "Three-event journal replay reproduced the same full portable state hash.", [execution_hash])
            resolve_v100_gate(source, "legacy_v159_rollback_anchor", "Exact legacy live_state pointer and Git blob SHA are embedded in the cutover metadata.", [pointer_sha])
            activate_v100_runtime(source)

            active = [str(r[0]) for r in source.db.execute(
                "SELECT gate_code FROM cutover_gate WHERE status!='resolved' ORDER BY gate_code"
            ).fetchall()]
            final_checkpoint = export_portable_checkpoint_v100(source, source_v)
            source_core = _core(source)
            manifest = build_runtime_pointer(
                source_live_version=source_v,
                base_checkpoint=f"runtime/checkpoints/cutover_v{source_v}.json",
                base_state_hash=final_checkpoint["state_hash"],
                legacy_pointer=package.pointer,
                legacy_pointer_blob_sha=pointer_sha,
                mode="prepared",
                journal_base_seq=0,
                journal_seq=0,
            )

            # One last clean restore of the exact bundle that will be committed.
            final_db = td / "final.db"
            with seed_world_v100_migration(final_db) as restored:
                final_import = import_portable_checkpoint_v100(restored, final_checkpoint)
                final_hash = runtime_state_hash_v100(restored, source_v) if final_import.get("ok") else None
                final_core = _core(restored) if final_import.get("ok") else None
            final_ok = bool(final_import.get("ok") and final_hash == final_checkpoint["state_hash"] and final_core == source_core)

            ready = bool(not active and final_ok and source_v == 159)
            out = {
                "source_version": source_v,
                "baseline_ready": True,
                "cutover_blockers": active,
                "actual_cutover_ready": ready,
                "legacy_pointer_blob_sha": pointer_sha,
                "source_core": source_core,
                "v10_shadow_reproof": v10_shadow_ok,
                "typed_resolution_probe": resolver_ok,
                "journal_replay_probe": {"ok": replay_ok, "events": 3, "execution_hash": execution_hash, "replay_hash": replay_hash},
                "rollback_anchor": rollback_ok,
                "checkpoint": {
                    "schema_version": final_checkpoint["schema_version"],
                    "engine_version": final_checkpoint["engine_version"],
                    "state_hash": final_checkpoint["state_hash"],
                    "byte_count": final_checkpoint["transport_meta"]["byte_count"],
                    "roundtrip_ok": final_ok,
                },
                "runtime_pointer": manifest,
                "errors": [] if ready else ["final_cutover_bundle_not_ready"],
                "technical_success": ready,
            }

            if checkpoint_out:
                Path(checkpoint_out).parent.mkdir(parents=True, exist_ok=True)
                Path(checkpoint_out).write_text(json.dumps(final_checkpoint, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            if manifest_out:
                Path(manifest_out).parent.mkdir(parents=True, exist_ok=True)
                Path(manifest_out).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default="..")
    p.add_argument("--out")
    p.add_argument("--checkpoint-out")
    p.add_argument("--manifest-out")
    a = p.parse_args()
    result = run(a.repo_root, checkpoint_out=a.checkpoint_out, manifest_out=a.manifest_out)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    raise SystemExit(0 if result.get("technical_success") else 2)
