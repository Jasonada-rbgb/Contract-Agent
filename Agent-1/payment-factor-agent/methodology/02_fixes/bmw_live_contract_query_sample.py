"""GENUINE contract query — BMW sample through the real Contract Agent.

Unlike the frozen-replay scenario engines, this actually calls
evaluate_claims_table(), which:
  - loads BMW contract assets (KB),
  - retrieves contract passages per claim,
  - calls the LLM (temp 0) against the contract text.

Runs a small sample (default 20 rows) drawn from the Spaetausfall dispute
population, then compares live decisions to the frozen row-level decisions.
This is the true test of whether the contract is being queried.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

SDK = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\Agent-1\agent-contract\agent-openai-agents-sdk")
sys.path.insert(0, str(SDK))

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
FROZEN = ROOT / "bmw_edc_claims_eval_verified_20260701" / "final_contract_audit" / "final_contract_audit_row_level.csv"
OUT = ROOT / "reverify_20260720" / "02_fixes"

SAMPLE_N = int(os.getenv("BMW_SAMPLE_N", "20"))
ENDPOINT = os.getenv("BMW_EDC_MODEL_ENDPOINT", "databricks-claude-opus-4-8")


def main() -> int:
    from agent_server.claims_batch import evaluate_claims_table

    frozen = pd.read_csv(FROZEN, low_memory=False)
    # sample from the Spaetausfall dispute rows (challengeable bucket, standard->extended)
    disp = frozen[
        (frozen["audit_bucket"] == "challengeable_status_only_delta")
        & (frozen["manual_warranty_type"].astype(str) == "standard_gw")
        & (frozen["contract_warranty_type"].astype(str) == "extended_gw")
    ].copy()
    if os.getenv("BMW_SAMPLE_DIVERSE", "false").strip().lower() in {"1", "true", "yes"}:
        # spread the sample across markets so multiple signatures are exercised
        sample = disp.groupby("country", group_keys=False).head(max(1, SAMPLE_N // 8)).head(SAMPLE_N).copy()
    else:
        sample = disp.head(SAMPLE_N).copy()
    print(f"Sample rows: {len(sample)} from Spaetausfall dispute population", flush=True)

    # build the input the evaluator expects (canonical claim columns)
    claim_df = pd.DataFrame({
        "VIN": sample["vin"],
        "Country": sample["country"],
        "Warranty Start Date": sample["warranty_start_date"],
        "Repair Date": sample["repair_date"],
        "Mileage": sample["mileage"],
        "Part Description": sample["part_description"],
        "Claim Number": sample["claim_number"],
    })

    print(f"Calling evaluate_claims_table (LIVE contract query) endpoint={ENDPOINT} ...", flush=True)
    results, warnings = evaluate_claims_table(
        claim_df, oem="BMW", contract_id="BMW", model_endpoint=ENDPOINT,
        progress_callback=lambda m: print("  [agent]", m, flush=True),
    )

    live = pd.DataFrame(results)
    # compare decision vs frozen ai_decision
    sample = sample.reset_index(drop=True)
    comp = pd.DataFrame({
        "claim_number": sample["claim_number"],
        "frozen_ai_decision": sample["ai_decision"],
        "frozen_contract_warranty_type": sample["contract_warranty_type"],
        "live_decision": live.get("decision", pd.Series([None] * len(sample))),
        "live_reason": live.get("reason", pd.Series([None] * len(sample))),
    })
    comp.to_csv(OUT / "bmw_live_vs_frozen_sample.csv", index=False)

    agree = (comp["frozen_ai_decision"].astype(str) == comp["live_decision"].astype(str)).sum()
    summary = {
        "sample_n": len(sample),
        "endpoint": ENDPOINT,
        "live_query_performed": True,
        "warnings": warnings[:10],
        "decision_agreement_with_frozen": int(agree),
        "agreement_rate": round(agree / len(sample), 3) if len(sample) else None,
        "live_decision_counts": comp["live_decision"].value_counts(dropna=False).to_dict(),
    }
    (OUT / "bmw_live_vs_frozen_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
