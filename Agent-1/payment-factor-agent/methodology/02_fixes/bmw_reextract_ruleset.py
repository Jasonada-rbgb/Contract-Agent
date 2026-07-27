"""Force a fresh BMW ruleset extraction from the contract (bypassing caches).

Verifies the strengthened warranty-terms prompt captures every market variant
(NAS/US/PR 60mo + mileage vs ROW 36mo) with proper attribution — contract-driven,
not hardcoded.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SDK = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\Agent-1\agent-contract\agent-openai-agents-sdk")
sys.path.insert(0, str(SDK))

OUT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output\reverify_20260720\02_fixes")
ENDPOINT = os.getenv("BMW_EDC_MODEL_ENDPOINT", "databricks-claude-opus-4-8")


def main() -> int:
    from agent_server import claims_batch as cb
    from agent_server.agent import _load_contract, _CACHE

    # disable volume ruleset cache so we recompile from the contract
    os.environ["CLAIMS_RULESET_VOLUME_CACHE"] = "false"
    cb._RULESET_CACHE.clear()

    oem, contract_id = "BMW", "BMW"
    print("Loading BMW contract assets...", flush=True)
    assets = cb._load_contract_assets(oem, contract_id)
    print("Compiling warranty ruleset from contract (fresh)...", flush=True)
    ruleset = cb._compile_warranty_ruleset(oem, contract_id, assets)

    rules_out = [
        {
            "rule_id": r.rule_id,
            "market": r.market,
            "component": r.component,
            "months": r.months,
            "mileage_limit": r.mileage_limit,
            "mileage_unit": r.mileage_unit,
            "whichever_sooner": r.whichever_sooner,
            "citation": (r.citation or "")[:160],
        }
        for r in ruleset.rules
    ]
    (OUT / "bmw_ruleset_reextracted.json").write_text(
        json.dumps({"oem": oem, "contract_id": contract_id, "n_rules": len(rules_out), "rules": rules_out}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(rules_out, indent=2))

    # quick market-matcher check on the drift markets
    from agent_server.claims_batch import _select_applicable_rule
    for country in ["USA", "Puerto Rico", "Canada", "Germany", "Thailand", "Korea"]:
        rule, reason = _select_applicable_rule(ruleset, {"country": country, "part_description": "general"})
        m = rule.months if rule else None
        print(f"  {country:14s} -> months={m} reason={reason or 'matched'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
