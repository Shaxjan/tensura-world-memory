from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from v102_activate import activate_v102
from v102_request_processor import process_request


def rehearse(repo_root: str | Path) -> dict:
    source = Path(repo_root).resolve()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "repo"
        shutil.copytree(source, work, ignore=shutil.ignore_patterns(".git"))
        activated = activate_v102(work)
        session = json.loads((work / "runtime/session_state.json").read_text(encoding="utf-8"))
        hud = session["hud"]
        checks = {
            "engine_102": session["engine_version"] == "1.0.2",
            "time_exact": hud["time"]["display"] == "T+131 ~07:54",
            "location_exact": hud["location"]["display"] == "большой тренировочный двор Борги",
            "wallet_exact": hud["money"]["on_person_display"] == "26g 05s 92c",
            "vern_unknown_preserved": any(
                x["account_id"] == "vern_instrument_float" and x["balance_display"] == "UNKNOWN"
                for x in hud["money"]["elsewhere"]
            ),
        }
        seq = int(session["journal_seq"]) + 1
        req_rel = Path("runtime/requests") / f"r{seq:06d}.json"
        req_path = work / req_rel
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(json.dumps({
            "format": "TENSURA_TURN_REQUEST",
            "schema_version": 1,
            "seq": seq,
            "event_key": "v102-rehearsal-kick",
            "event_type": "player_turn",
            "request": {"raw_text": "Киваю."},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        processed = process_request(work, req_rel)
        after = json.loads((work / "runtime/session_state.json").read_text(encoding="utf-8"))
        checks["next_turn_updates_session"] = after["journal_seq"] == seq
        checks["session_compact"] = (work / "runtime/session_state.json").stat().st_size < 12000
        checks["hud_survives_turn"] = set(after["display_contract"]["always_show"]) == {
            "hud.time.display", "hud.location.display", "hud.money.on_person_display", "hud.money.elsewhere_display"
        }
        ok = all(checks.values())
        return {"technical_success": ok, "activation": activated, "checks": checks, "processed": processed, "session": after}


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
