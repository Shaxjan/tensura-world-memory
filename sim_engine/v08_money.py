from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v03_engine import dumps
from v07_baseline import FUND_TOKENS, parse_loose_money, scan_late_mentions, apply_v07_baseline_rehearsal
from v06_migration import RepoCampaignPackage


RECON_PATH = "memory/money_reconciliation_v159.json"


def _load_json(root: Path, rel: str) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def _verify_anchors(root: Path, audit: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in audit.get("verified_anchors", []):
        rel = str(item["path"])
        p = root / rel
        if not p.exists():
            errors.append(f"missing_evidence:{rel}")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for needle in item.get("must_contain", []):
            if str(needle) not in text:
                errors.append(f"evidence_anchor_missing:{rel}:{needle}")
    return errors


def _legacy_mentions(world: Any, account_id: str) -> list[int]:
    row = world.db.execute(
        "SELECT later_mentions_json FROM fund_account_audit WHERE account_id=?", (account_id,)
    ).fetchone()
    if row is None:
        return []
    try:
        return [int(x) for x in json.loads(row["later_mentions_json"])]
    except Exception:
        return []


def _insert_account(world: Any, account_id: str, item: dict[str, Any], as_of: int) -> dict[str, Any]:
    balance = parse_loose_money(item.get("balance"))
    principal = parse_loose_money(item.get("known_principal"))
    certainty = str(item.get("certainty", "UNKNOWN"))
    if item.get("balance") == "UNKNOWN":
        balance = None
    world.db.execute(
        "INSERT OR REPLACE INTO financial_account_state("
        "account_id,account_type,balance_copper,known_principal_copper,certainty,holder_key,status,"
        "as_of_version,source_path,note) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            account_id,
            str(item["account_type"]),
            balance,
            principal,
            certainty,
            item.get("holder"),
            str(item["status"]),
            as_of,
            str(item["source_path"]),
            str(item.get("note", "")),
        ),
    )
    return {
        "balance_copper": balance,
        "known_principal_copper": principal,
        "certainty": certainty,
        "status": str(item["status"]),
    }


def _record_evidence(world: Any, audit: dict[str, Any]) -> int:
    n = 0
    for item in audit.get("evidence", []):
        account = str(item["account"])
        versions = item.get("versions") or [None]
        for v in versions:
            source = f"live_v{int(v)}/delta.json" if v is not None else RECON_PATH
            world.db.execute(
                "INSERT INTO money_reconciliation_evidence("
                "account_id,source_version,source_path,classification,effect_copper,evidence_json,note"
                ") VALUES(?,?,?,?,?,?,?)",
                (
                    account,
                    int(v) if v is not None else None,
                    source,
                    str(item["classification"]),
                    item.get("effect_copper"),
                    dumps(item),
                    str(item.get("note", "")),
                ),
            )
            n += 1
    return n


def _validate_conservation(root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    spec = audit.get("conservation_check")
    if not spec:
        return {"ok": True, "skipped": True}
    rel = str(spec["path"])
    data = _load_json(root, rel)
    before = parse_loose_money(data.get("cash_before"))
    after = parse_loose_money(data.get("cash_after"))
    alloc = data.get("economy", {}).get("allocation", [])
    amounts = [parse_loose_money(x.get("amount")) for x in alloc]
    expected_before = parse_loose_money(spec.get("expected_cash_before"))
    expected_after = parse_loose_money(spec.get("expected_cash_after"))
    expected_allocated = parse_loose_money(spec.get("expected_allocated"))
    if before is None or after is None or any(x is None for x in amounts):
        return {"ok": False, "reason": f"{rel}:money_not_parseable"}
    total = sum(int(x) for x in amounts if x is not None)
    ok = before - after == total
    if expected_before is not None:
        ok = ok and before == expected_before
    if expected_after is not None:
        ok = ok and after == expected_after
    if expected_allocated is not None:
        ok = ok and total == expected_allocated
    return {
        "ok": ok,
        "source_path": rel,
        "cash_before_copper": before,
        "cash_after_copper": after,
        "allocated_copper": total,
    }


def _future_staleness(root: Path, through: int, pointer_v: int) -> dict[str, list[int]]:
    if pointer_v <= through:
        return {}
    out: dict[str, list[int]] = {}
    for account, tokens in FUND_TOKENS.items():
        hits = scan_late_mentions(root, through, tokens, pointer_v)
        if hits:
            out[account] = hits
    extra = {
        "family_purse": ("family_budget", "family purse", "семейн"),
        "lissa_outreach_enclosure": ("lissa", "лисс", "guild_publicity", "guild publicity"),
        "dwargon_outreach_enclosure": ("dwargon", "дваргон", "каменн"),
        "queen_enclosure": ("queen", "королев"),
    }
    for account, tokens in extra.items():
        hits = scan_late_mentions(root, through, tokens, pointer_v)
        if hits:
            out[account] = hits
    return out


def apply_v08_money_reconciliation(
    world: Any, package: RepoCampaignPackage, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    v07 = apply_v07_baseline_rehearsal(world, package, root)
    if v07.get("v06", {}).get("rehearsal_ready") is False or v07.get("errors"):
        return {
            "source_version": package.pointer.get("v"),
            "baseline_ready": False,
            "live_cutover_ready": False,
            "errors": ["v07_rehearsal_not_usable", *v07.get("errors", [])],
        }

    audit_path = root / RECON_PATH
    if not audit_path.exists():
        return {
            "source_version": package.pointer.get("v"),
            "baseline_ready": False,
            "live_cutover_ready": False,
            "errors": [f"missing_source:{RECON_PATH}"],
        }
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    through = int(audit["reconciled_through_live_version"])
    pointer_v = int(package.pointer.get("v") or 0)
    errors = _verify_anchors(root, audit)

    reviewed = audit.get("reviewed_mentions", {})
    for account in FUND_TOKENS:
        actual = _legacy_mentions(world, account)
        expected = [int(x) for x in reviewed.get(account, [])]
        actual_through = [v for v in actual if v <= through]
        if actual_through != expected:
            errors.append(
                f"reviewed_mentions_mismatch:{account}:actual={actual_through}:expected={expected}"
            )

    conservation = _validate_conservation(root, audit)
    if not conservation.get("ok"):
        errors.append(f"money_conservation_failed:{conservation}")

    stale = _future_staleness(root, through, pointer_v)
    if pointer_v < through:
        errors.append(f"live_pointer_older_than_reconciliation:{pointer_v}<{through}")

    account_rows: dict[str, Any] = {}
    with world.db:
        if not errors:
            for account_id, item in audit.get("accounts", {}).items():
                account_rows[account_id] = _insert_account(world, str(account_id), item, through)

            _record_evidence(world, audit)

            exact_legacy = {
                "promo": ("reconciled_exact_current", parse_loose_money(audit["accounts"]["promo"]["balance"])),
                "lissa_project": ("reconciled_exact_current", parse_loose_money(audit["accounts"]["lissa_project"]["balance"])),
                "oren_project": ("reconciled_exact_current", parse_loose_money(audit["accounts"]["oren_project"]["balance"])),
                "meira_obligation": ("reconciled_exact_outstanding", parse_loose_money(audit["accounts"]["meira_obligation"]["balance"])),
                "vern_instrument_float": ("entrusted_principal_current_balance_unknown", parse_loose_money(audit["accounts"]["vern_instrument_float"]["known_principal"])),
            }
            for account, (certainty, legacy_amount) in exact_legacy.items():
                world.db.execute(
                    "UPDATE fund_account_audit SET balance_copper=?,certainty=?,exact_as_of_version=?,"
                    "source_path=?,note=? WHERE account_id=?",
                    (
                        legacy_amount,
                        certainty,
                        through,
                        RECON_PATH,
                        "v0.8 reconciliation applied; see financial_account_state for current-balance semantics.",
                        account,
                    ),
                )

            world.db.execute(
                "UPDATE migration_blockers SET status='resolved' "
                "WHERE code IN ('separate_project_funds_not_fully_normalized','project_fund_reconciliation_pending')"
            )
            world.db.execute(
                "INSERT OR REPLACE INTO blocker_resolution("
                "blocker_code,classification,status,resolution,evidence_json,replacement_blocker"
                ") VALUES(?,?,?,?,?,NULL)",
                (
                    "project_fund_reconciliation_pending",
                    "historical_integrity",
                    "resolved",
                    "All reviewed v125-v159 money mentions are classified. Exact accounts are carried forward; "
                    "Vern's float is represented as an entrusted 50s principal with UNKNOWN current unused balance.",
                    dumps([RECON_PATH, "live_v151/delta.json", "live_v158/delta.json", "live_v159/delta.json"]),
                ),
            )

            if stale:
                world.db.execute(
                    "INSERT OR REPLACE INTO migration_blockers(code,detail,status) VALUES(?,?,?)",
                    ("money_reconciliation_stale_after_checkpoint", dumps(stale), "active"),
                )
            else:
                world.db.execute(
                    "INSERT OR REPLACE INTO migration_blockers(code,detail,status) VALUES(?,?,?)",
                    ("money_reconciliation_stale_after_checkpoint", "no relevant later mentions", "resolved"),
                )

            world.db.execute(
                "UPDATE migration_capabilities SET enabled=0,reason='v08_mechanical_calibration_pending'"
            )
            world.db.execute(
                "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
                ("runtime_mode", '"v08_money_reconciled_rehearsal"', "engine:v08"),
            )

    historical = []
    if errors:
        historical.append("money_reconciliation_validation_failed")
    if stale:
        historical.append("money_reconciliation_stale_after_checkpoint")

    result = {
        "source_version": pointer_v,
        "reconciled_through_version": through,
        "baseline_ready": not historical,
        "live_cutover_ready": False,
        "historical_integrity_blockers": historical,
        "feature_calibration_pending": list(v07.get("feature_calibration_pending", [])),
        "accepted_degradation": list(v07.get("accepted_degradation", [])),
        "errors": errors,
        "stale_after_reconciliation": stale,
        "accounts": account_rows,
        "conservation": conservation,
        "money_evidence_rows": world.db.execute(
            "SELECT COUNT(*) FROM money_reconciliation_evidence"
        ).fetchone()[0] if not errors else 0,
    }
    with world.db:
        cur = world.db.execute(
            "INSERT INTO money_reconciliation_runs("
            "source_version,reconciled_through_version,baseline_ready,stale_after_version,report_json"
            ") VALUES(?,?,?,?,?)",
            (
                pointer_v,
                through,
                int(result["baseline_ready"]),
                min((min(vs) for vs in stale.values()), default=None),
                dumps(result),
            ),
        )
        result["run_id"] = int(cur.lastrowid)
        world.db.execute(
            "INSERT OR REPLACE INTO campaign_metadata(key,value_json,source_path) VALUES(?,?,?)",
            ("v08_report", dumps(result), "engine:v08"),
        )
    world.db.commit()
    return result
