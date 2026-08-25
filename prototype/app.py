from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SIM_ENGINE = REPO_ROOT / "sim_engine"
if str(SIM_ENGINE) not in sys.path:
    sys.path.insert(0, str(SIM_ENGINE))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_lite import rena_agent_lite  # noqa: E402
from character_agent_engine_routing import (  # noqa: E402
    build_engine_owned_rena_context_v113,
    install_candidate_reciprocal_fixture,
)
from v100_handoff import runtime_state_hash_v100  # noqa: E402
from v113_repository import load_repository_runtime_v113_candidate  # noqa: E402


HTML = r'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tensura Playable Alpha</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark}
*{box-sizing:border-box} body{margin:0;background:#111318;color:#edf0f6;min-height:100vh}
main{max-width:860px;margin:0 auto;padding:18px}.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.badge{font-size:12px;font-weight:700;letter-spacing:.08em;padding:6px 9px;border:1px solid #7e8798;border-radius:999px}
.hud{font-size:13px;color:#b7bfce;line-height:1.55;margin-bottom:14px}.panel{border:1px solid #2d3440;border-radius:14px;background:#171b22;overflow:hidden}
.scene{padding:14px 16px;border-bottom:1px solid #2d3440;color:#c9d0dc;font-size:14px}.chat{height:min(58vh,560px);overflow:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:82%;padding:10px 12px;border-radius:12px;white-space:pre-wrap;line-height:1.45}.you{align-self:flex-end;background:#263142}.rena{align-self:flex-start;background:#20242c}.name{font-size:11px;opacity:.65;margin-bottom:3px}
form{display:flex;gap:8px;padding:12px;border-top:1px solid #2d3440}input{flex:1;border:1px solid #3a4351;background:#11151b;color:#fff;border-radius:10px;padding:12px;font-size:15px;outline:none}
button{border:1px solid #465164;background:#222935;color:#fff;border-radius:10px;padding:10px 14px;cursor:pointer}button:disabled{opacity:.45;cursor:default}.meta{font-size:12px;color:#8f98a8;margin-top:10px;display:flex;gap:14px;flex-wrap:wrap}
.error{color:#ffb8b8}.actions{margin-left:auto}
</style>
</head>
<body><main>
<div class="top"><span class="badge">SANDBOX · PLAYABLE ALPHA</span><strong>Tensura World Memory</strong><div class="actions"><button id="reset">Сбросить сцену</button></div></div>
<div id="hud" class="hud"></div>
<div class="panel"><div class="scene">Это изолированная тестовая сцена. Текущий LIVE не меняется. В этом вертикальном срезе Рена присутствует рядом, а каждое сообщение считается прямым обращением к ней.</div><div id="chat" class="chat"></div>
<form id="form"><input id="input" autocomplete="off" placeholder="Скажи что-нибудь Рене…"><button id="send">Отправить</button></form></div>
<div id="meta" class="meta"></div>
</main>
<script>
const chat=document.getElementById('chat'), input=document.getElementById('input'), form=document.getElementById('form'), send=document.getElementById('send'), meta=document.getElementById('meta');
function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function msg(name,text,cls){const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=`<div class="name">${esc(name)}</div>${esc(text)}`;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
async function state(){const r=await fetch('/api/state');const x=await r.json();document.getElementById('hud').textContent=`Время: ${x.hud.time} | Место: ${x.hud.location} | При мне: ${x.hud.money} | Мои деньги вне кошелька: ${x.hud.elsewhere}`;meta.textContent=`Ходов: ${x.turn_count} · Agent: ${x.agent} · replay: ${x.replay_ok?'OK':'—'} · LIVE source seq: ${x.live_source_seq}`}
form.onsubmit=async e=>{e.preventDefault();const text=input.value.trim();if(!text)return;msg('Арлекино',text,'you');input.value='';send.disabled=true;try{const r=await fetch('/api/turn',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});const x=await r.json();if(!r.ok)throw new Error(x.error||'turn failed');msg('Рена',x.response,'rena');await state()}catch(e){msg('Система',e.message,'rena');meta.classList.add('error')}finally{send.disabled=false;input.focus()}};
document.getElementById('reset').onclick=async()=>{await fetch('/api/reset',{method:'POST'});chat.innerHTML='';msg('Рена','Ну? Я слушаю.','rena');await state();input.focus()};
msg('Рена','Ну? Я слушаю.','rena');state();input.focus();
</script></body></html>'''


def _display_time(world_minute: int) -> str:
    day, minute = divmod(int(world_minute), 1440)
    hour, minute = divmod(minute, 60)
    return f"T+{day} ~{hour:02d}:{minute:02d}"


def _money(copper: int) -> str:
    gold, rem = divmod(int(copper), 10_000)
    silver, copper = divmod(rem, 100)
    return f"{gold:02d}g {silver:02d}s {copper:02d}c"


def _explicit_target(text: str) -> str:
    if re.search(r"(?:^|\W)рен(?:а|ы|е|у|ой|ою)?(?:\W|$)", text.casefold().replace("ё", "е")):
        return text.strip()
    return "Рена, " + text.strip()


class PrototypeSession:
    """In-process playable sandbox derived from current authoritative LIVE.

    Nothing here writes repository runtime files. Every reset creates a fresh temp
    database from the current v1.0.12 LIVE checkpoint+journal, prospectively activates
    v1.0.13 candidate state, and uses deterministic fixture visibility/awareness only
    inside that temp database.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.lock = threading.RLock()
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self.world = None
        self.pointer: dict[str, Any] = {}
        self.source_session: dict[str, Any] = {}
        self.turn_log: list[dict[str, Any]] = []
        self.next_seq = 0
        self.last_replay_ok = True
        self.reset()

    def _open_fresh(self, db_path: Path):
        return load_repository_runtime_v113_candidate(self.repo_root, db_path)

    def reset(self) -> None:
        with self.lock:
            if self.world is not None:
                self.world.close()
            if self._tmp is not None:
                self._tmp.cleanup()
            self._tmp = tempfile.TemporaryDirectory(prefix="tensura-playable-alpha-")
            db_path = Path(self._tmp.name) / "prototype.db"
            self.world, self.pointer, _ = self._open_fresh(db_path)
            self.source_session = json.loads((self.repo_root / "runtime/session_state.json").read_text(encoding="utf-8"))
            activation_seq = int(self.pointer["journal_seq"]) + 1
            self.world.execute_runtime_event(
                activation_seq,
                "prototype-v113-activation",
                "character_agent_v113_activation",
                {"reason": "local_playable_alpha_sandbox"},
            )
            self.next_seq = activation_seq + 1
            self.turn_log = []
            self.last_replay_ok = True

    def _hud(self) -> dict[str, str]:
        place = self.world._place103("player") or {}
        player = self.world.actor("player")
        elsewhere = (((self.source_session.get("hud") or {}).get("money") or {}).get("elsewhere_display") or "UNKNOWN")
        return {
            "time": _display_time(int(self.world.now)),
            "location": str(place.get("name") or ((self.source_session.get("hud") or {}).get("location") or {}).get("display") or "UNKNOWN"),
            "money": _money(int(player["cash_copper"])),
            "elsewhere": str(elsewhere),
        }

    def state(self) -> dict[str, Any]:
        with self.lock:
            state = self.world.character_agent_state_v113("rena") or {}
            return {
                "ok": True,
                "mode": "SANDBOX_NON_AUTHORITATIVE",
                "hud": self._hud(),
                "turn_count": len(self.turn_log),
                "agent": "Rena Agent Lite v1",
                "replay_ok": bool(self.last_replay_ok),
                "live_source_seq": int(self.pointer["journal_seq"]),
                "memory_count": len(state.get("episodic_memories") or []),
                "private_state_exposed": False,
            }

    def turn(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            raise ValueError("empty player text")
        if len(text) > 2000:
            raise ValueError("player text too long")
        with self.lock:
            number = len(self.turn_log) + 1
            turn_key = f"prototype-turn-{number:04d}"
            raw_text = _explicit_target(text)
            install_candidate_reciprocal_fixture(
                self.world,
                source_turn_key=turn_key,
                raw_text=raw_text,
            )
            routed = build_engine_owned_rena_context_v113(
                self.world,
                source_turn_key=turn_key,
                raw_text=raw_text,
                allow_candidate_fixture=True,
            )
            if not routed.eligible or not isinstance(routed.context, dict):
                raise RuntimeError(f"Character Agent routing rejected prototype turn: {routed.reason}")
            before_state = self.world.character_agent_state_v113("rena") or {}
            memory_count = len(before_state.get("episodic_memories") or [])
            decision = rena_agent_lite(routed.context, memory_count=memory_count)
            seq = self.next_seq
            event_key = f"prototype-character-decision-{number:04d}"
            committed = self.world.execute_runtime_event(
                seq,
                event_key,
                "character_agent_decision_v113",
                {
                    "mode": "candidate_rehearsal_fixture",
                    "context": routed.context,
                    "decision": decision,
                },
            )
            result = committed.get("result") or {}
            npc = result.get("npc_response") or {}
            surface = npc.get("surface_text")
            if not isinstance(surface, str) or not surface:
                raise RuntimeError("prototype committed no public Rena response")
            self.turn_log.append(
                {
                    "number": number,
                    "seq": seq,
                    "event_key": event_key,
                    "turn_key": turn_key,
                    "raw_text": raw_text,
                    "decision": decision,
                }
            )
            self.next_seq += 1
            self.last_replay_ok = self._verify_replay()
            if not self.last_replay_ok:
                raise RuntimeError("prototype deterministic replay mismatch")
            return {
                "ok": True,
                "response": surface,
                "speech_act": npc.get("speech_act"),
                "hud": self._hud(),
                "turn_count": len(self.turn_log),
                "replay_ok": True,
                "private_state_exposed": False,
                "production_live_changed": False,
            }

    def _verify_replay(self) -> bool:
        replay_path = Path(self._tmp.name) / "replay.db"
        if replay_path.exists():
            replay_path.unlink()
        replay, pointer, _ = self._open_fresh(replay_path)
        try:
            activation_seq = int(pointer["journal_seq"]) + 1
            replay.execute_runtime_event(
                activation_seq,
                "prototype-v113-activation",
                "character_agent_v113_activation",
                {"reason": "local_playable_alpha_sandbox"},
            )
            for row in self.turn_log:
                install_candidate_reciprocal_fixture(
                    replay,
                    source_turn_key=row["turn_key"],
                    raw_text=row["raw_text"],
                )
                routed = build_engine_owned_rena_context_v113(
                    replay,
                    source_turn_key=row["turn_key"],
                    raw_text=row["raw_text"],
                    allow_candidate_fixture=True,
                )
                if not routed.eligible or not isinstance(routed.context, dict):
                    return False
                replay.execute_runtime_event(
                    int(row["seq"]),
                    str(row["event_key"]),
                    "character_agent_decision_v113",
                    {
                        "mode": "candidate_rehearsal_fixture",
                        "context": routed.context,
                        "decision": row["decision"],
                    },
                )
            source_v = int(pointer["source_live_version"])
            return runtime_state_hash_v100(replay, source_v) == runtime_state_hash_v100(self.world, source_v)
        finally:
            replay.close()

    def close(self) -> None:
        with self.lock:
            if self.world is not None:
                self.world.close()
                self.world = None
            if self._tmp is not None:
                self._tmp.cleanup()
                self._tmp = None


class Handler(BaseHTTPRequestHandler):
    session: PrototypeSession

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"prototype http {self.address_string()} {fmt % args}")

    def _json(self, status: int, data: dict[str, Any]) -> None:
        body = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 20_000:
            raise ValueError("invalid request size")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def do_GET(self) -> None:
        if self.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/state":
            self._json(HTTPStatus.OK, self.session.state())
            return
        self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        try:
            if self.path == "/api/reset":
                self.session.reset()
                self._json(HTTPStatus.OK, self.session.state())
                return
            if self.path == "/api/turn":
                data = self._body()
                text = data.get("text")
                if not isinstance(text, str):
                    raise ValueError("text required")
                self._json(HTTPStatus.OK, self.session.turn(text))
                return
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
        except Exception as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Tensura local Playable Alpha sandbox")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    session = PrototypeSession(Path(args.repo_root))
    Handler.session = session
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({
        "ok": True,
        "mode": "SANDBOX_NON_AUTHORITATIVE",
        "open": f"http://{args.host}:{args.port}/",
        "live_source_seq": session.pointer.get("journal_seq"),
        "agent": "Rena Agent Lite v1",
    }, ensure_ascii=False))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        session.close()


if __name__ == "__main__":
    main()
