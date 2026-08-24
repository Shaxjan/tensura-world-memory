from __future__ import annotations

import hashlib
import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from character_agent_contract import (
    CharacterAgentContractError,
    ValidationResult,
    public_observable,
    validate_agent_decision,
)

SHADOW_RECORD_FORMAT = "TENSURA_CHARACTER_AGENT_SHADOW_RECORD"
SHADOW_RECORD_SCHEMA_VERSION = 1
SHADOW_AUTHORITY = "SHADOW_NON_AUTHORITATIVE"
REPLAY_POLICY = "JOURNALED_DECISION_ONLY_NO_PROVIDER_RECALL"


class ShadowDecisionError(RuntimeError):
    pass


class ShadowDecisionValidationError(ShadowDecisionError):
    pass


class ShadowDecisionReplayError(ShadowDecisionError):
    pass


DecisionProvider = Callable[[dict[str, Any]], dict[str, Any]]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def context_digest(context: dict[str, Any]) -> str:
    """Digest the exact causal context without persisting its raw contents."""
    return _digest(context)


def _record_filename(actor_key: str, source_turn_key: str) -> str:
    suffix = hashlib.sha256(f"{actor_key}|{source_turn_key}".encode("utf-8")).hexdigest()
    safe_actor = "".join(ch for ch in actor_key if ch.isalnum() or ch in "-_" ) or "actor"
    return f"{safe_actor}-{suffix}.json"


def build_shadow_record(
    *,
    context: dict[str, Any],
    validation: ValidationResult,
    provider_id: str,
) -> dict[str, Any]:
    if not validation.ok or not isinstance(validation.sanitized, dict) or not validation.decision_digest:
        raise ShadowDecisionValidationError("cannot record an invalid Character Agent decision")
    return {
        "format": SHADOW_RECORD_FORMAT,
        "schema_version": SHADOW_RECORD_SCHEMA_VERSION,
        "authority": SHADOW_AUTHORITY,
        "actor_key": str(context.get("actor_key") or ""),
        "source_turn_key": str(context.get("source_turn_key") or ""),
        "world_minute": int(context.get("world_minute") or 0),
        "context_digest": context_digest(context),
        "decision_digest": validation.decision_digest,
        "decision": deepcopy(validation.sanitized),
        "public_observable": public_observable(validation),
        "generation": {
            "provider_id": str(provider_id or "unspecified"),
            "provider_output_authoritative": False,
            "raw_context_persisted": False,
            "raw_provider_output_persisted": False,
        },
        "replay_policy": REPLAY_POLICY,
    }


def validate_shadow_record(context: dict[str, Any], record: dict[str, Any]) -> ValidationResult:
    if not isinstance(record, dict):
        raise ShadowDecisionReplayError("shadow record must be an object")
    if record.get("format") != SHADOW_RECORD_FORMAT or record.get("schema_version") != SHADOW_RECORD_SCHEMA_VERSION:
        raise ShadowDecisionReplayError("unsupported shadow record format")
    if record.get("authority") != SHADOW_AUTHORITY:
        raise ShadowDecisionReplayError("shadow record has unexpected authority")
    if record.get("replay_policy") != REPLAY_POLICY:
        raise ShadowDecisionReplayError("shadow record has unsafe replay policy")
    if str(record.get("actor_key") or "") != str(context.get("actor_key") or ""):
        raise ShadowDecisionReplayError("shadow record actor mismatch")
    if str(record.get("source_turn_key") or "") != str(context.get("source_turn_key") or ""):
        raise ShadowDecisionReplayError("shadow record source turn mismatch")
    if str(record.get("context_digest") or "") != context_digest(context):
        raise ShadowDecisionReplayError("shadow record context digest mismatch")

    decision = record.get("decision")
    if not isinstance(decision, dict):
        raise ShadowDecisionReplayError("shadow record is missing structured decision")
    validation = validate_agent_decision(context, decision)
    if not validation.ok:
        raise ShadowDecisionReplayError("journaled decision no longer validates: " + "; ".join(validation.errors))
    if validation.decision_digest != record.get("decision_digest"):
        raise ShadowDecisionReplayError("shadow record decision digest mismatch")
    if public_observable(validation) != record.get("public_observable"):
        raise ShadowDecisionReplayError("shadow record public observable mismatch")
    return validation


class CharacterAgentShadowRunner:
    """Development-only first-call/record/replay boundary for Character Agents.

    The provider is untrusted and may be non-deterministic. It is called only for
    a new source turn. Once its proposal passes the Character Agent contract, the
    sanitized decision is written exactly once. Every later replay validates and
    returns that journaled decision without invoking the provider again.

    This class intentionally has no access to the authoritative world database,
    runtime journal, cash, inventory or LIVE pointer.
    """

    def __init__(self, journal_dir: str | Path):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def record_path(self, context: dict[str, Any]) -> Path:
        actor_key = str(context.get("actor_key") or "")
        turn_key = str(context.get("source_turn_key") or "")
        if not actor_key or not turn_key:
            raise ShadowDecisionValidationError("context requires actor_key and source_turn_key")
        return self.journal_dir / _record_filename(actor_key, turn_key)

    @staticmethod
    def _read_record(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ShadowDecisionReplayError(f"cannot read shadow record: {exc}") from exc
        if not isinstance(value, dict):
            raise ShadowDecisionReplayError("shadow record must decode to an object")
        return value

    @staticmethod
    def _write_once(path: Path, record: dict[str, Any]) -> None:
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError as exc:
            raise ShadowDecisionReplayError("shadow record already exists") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
        except Exception:
            try:
                path.unlink(missing_ok=True)
            finally:
                raise

    def replay(self, context: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            path = self.record_path(context)
            if not path.exists():
                raise ShadowDecisionReplayError("no journaled Character Agent decision for this turn")
            record = self._read_record(path)
            validation = validate_shadow_record(context, record)
            return {
                "accepted": True,
                "replayed": True,
                "provider_called": False,
                "decision_digest": validation.decision_digest,
                "decision": deepcopy(validation.sanitized),
                "public_observable": public_observable(validation),
                "record_path": str(path),
            }

    def run(
        self,
        context: dict[str, Any],
        provider: DecisionProvider,
        *,
        provider_id: str = "unspecified",
    ) -> dict[str, Any]:
        with self._lock:
            path = self.record_path(context)
            if path.exists():
                return self.replay(context)

            try:
                raw_decision = provider(deepcopy(context))
            except Exception as exc:
                raise ShadowDecisionValidationError(f"Character Agent provider failed: {exc}") from exc
            if not isinstance(raw_decision, dict):
                raise ShadowDecisionValidationError("Character Agent provider must return an object")

            validation = validate_agent_decision(context, raw_decision)
            if not validation.ok:
                raise ShadowDecisionValidationError("Character Agent proposal rejected: " + "; ".join(validation.errors))

            record = build_shadow_record(context=context, validation=validation, provider_id=provider_id)
            try:
                self._write_once(path, record)
            except ShadowDecisionReplayError:
                # In the normal deployment model turns are serialized by one worker.
                # If another writer nevertheless won the race, never overwrite it;
                # accept only the already-journaled decision after full validation.
                return self.replay(context)

            verified = self._read_record(path)
            verified_validation = validate_shadow_record(context, verified)
            return {
                "accepted": True,
                "replayed": False,
                "provider_called": True,
                "decision_digest": verified_validation.decision_digest,
                "decision": deepcopy(verified_validation.sanitized),
                "public_observable": public_observable(verified_validation),
                "record_path": str(path),
            }
