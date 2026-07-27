"""BMW full-population LIVE contract run — signature-representative + prompt cache.

Feeds the full BMW AMBIGUOUS population (every row whose contract/manual
comparison is not 'aligned_no_material_delta') through the real Contract Agent:
  - evaluate_claims_table() with CLAIMS_SIGNATURE_REPRESENTATIVE=true
  - 869 metric-signatures -> 869 live LLM calls (temp 0), prompt-cached
  - the 60-month market fix is active in the ruleset/market matcher
  - each signature verdict is propagated to all its member rows internally

Then recomputes the BMW contract-vs-manual delta on the FULL population:
  aligned rows keep their frozen (manual-equal) payable; ambiguous rows take the
  live contract decision. Writes a per-row audit + summary. Frozen is NOT touched.

Env (set by the launcher):
  CLAIMS_PROMPT_CACHE=true  CLAIMS_CACHE_TTL=1h  CLAIMS_SIGNATURE_REPRESENTATIVE=true
  BMW_EDC_MODEL_ENDPOINT=databricks-claude-opus-4-8
  BMW_LIVE_LIMIT (optional): cap ambiguous rows for a smoke test.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

SDK = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\Agent-1\agent-contract\agent-openai-agents-sdk")
sys.path.insert(0, str(SDK))

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
FROZEN = ROOT / "bmw_edc_claims_eval_verified_20260701" / "final_contract_audit" / "final_contract_audit_row_level.csv"
OUT = ROOT / "reverify_20260720" / "02_fixes"
ENDPOINT = os.getenv("BMW_EDC_MODEL_ENDPOINT", "databricks-claude-opus-4-8")
LIMIT = int(os.getenv("BMW_LIVE_LIMIT", "0"))  # 0 = full population

ALIGNED = "aligned_no_material_delta"


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def main() -> int:
    from agent_server.claims_batch import evaluate_claims_table

    frozen = pd.read_csv(FROZEN, low_memory=False)
    amb = frozen[frozen["audit_bucket"].astype(str) != ALIGNED].copy()
    if LIMIT > 0:
        amb = amb.head(LIMIT).copy()
    print(f"Ambiguous rows to evaluate live: {len(amb):,} "
          f"(of {len(frozen):,} total; {LIMIT or 'no'} limit)", flush=True)

    claim_df = pd.DataFrame({
        "VIN": amb["vin"],
        "Country": amb["country"],
        "Warranty Start Date": amb["warranty_start_date"],
        "Repair Date": amb["repair_date"],
        "Mileage": amb["mileage"],
        "Part Description": amb["part_description"],
        "Claim Number": amb["claim_number"],
    })

    t0 = time.perf_counter()
    print(f"Calling evaluate_claims_table LIVE endpoint={ENDPOINT} "
          f"cache={os.getenv('CLAIMS_PROMPT_CACHE')} ttl={os.getenv('CLAIMS_CACHE_TTL')} "
          f"rep={os.getenv('CLAIMS_SIGNATURE_REPRESENTATIVE')}", flush=True)
    results, warnings = evaluate_claims_table(
        claim_df, oem="BMW", contract_id="BMW", model_endpoint=ENDPOINT,
        progress_callback=lambda m: print("  [agent]", m, flush=True),
    )
    elapsed = time.perf_counter() - t0

    live = pd.DataFrame(results).reset_index(drop=True)
    amb = amb.reset_index(drop=True)
    amb["live_decision"] = live.get("decision", pd.Series([None] * len(amb)))
    amb["live_reason"] = live.get("reason", pd.Series([None] * len(amb)))
    amb["live_group_key"] = live.get("llm_group_key", pd.Series([None] * len(amb)))

    # Recompute payable on ambiguous rows from the LIVE decision.
    # in_warranty / covered  -> contract pays gross-equivalent contract_payable_final
    # out_of_warranty / not covered -> contract pays 0
    # requires_review -> hold at 0 (labelled), reported separately
    gross = _num(amb["total_cost"]).fillna(0)
    contract_rate = _num(amb["contract_rate"]).fillna(0)
    manual_payable = _num(amb["manual_payable_final"]).fillna(0)
    frozen_contract_payable = _num(amb["contract_payable_final"]).fillna(0)

    dec = amb["live_decision"].astype(str).str.lower()
    is_in = dec.str.contains("in_warranty") | dec.str.contains("covered") & ~dec.str.contains("not")
    is_out = dec.str.contains("out_of_warranty") | (dec.str.contains("not") & dec.str.contains("cover"))
    is_review = dec.str.contains("review") | dec.eq("nan") | amb["live_decision"].isna()

    # contract payable under live decision: pay contract_rate*gross when in-warranty, else 0
    live_contract_payable = (gross * contract_rate).where(gross.gt(0) & contract_rate.gt(0),
                                                          other=frozen_contract_payable)
    live_payable = pd.Series(0.0, index=amb.index)
    live_payable = live_payable.where(~is_in, live_contract_payable)
    live_payable = live_payable.where(~is_out, 0.0)
    live_payable = live_payable.where(~is_review, 0.0)
    amb["live_payable_final"] = live_payable

    # aligned rows: contract == manual (no material delta) -> keep frozen payable
    aligned = frozen[frozen["audit_bucket"].astype(str) == ALIGNED]
    aligned_contract = _num(aligned["contract_payable_final"]).fillna(0).sum()
    aligned_manual = _num(aligned["manual_payable_final"]).fillna(0).sum()

    amb_manual = manual_payable.sum()
    amb_live_contract = live_payable.sum()

    total_contract_live = aligned_contract + amb_live_contract
    total_manual = aligned_manual + amb_manual

    summary = {
        "endpoint": ENDPOINT,
        "smoke_limit": LIMIT,
        "elapsed_sec": round(elapsed, 1),
        "warnings": warnings[:10],
        "rows_total": int(len(frozen)),
        "rows_aligned_kept": int(len(aligned)),
        "rows_ambiguous_live": int(len(amb)),
        "live_decision_counts": amb["live_decision"].value_counts(dropna=False).to_dict(),
        "ambiguous_review_rows": int(is_review.sum()),
        "ambiguous_review_manual_value_eur": float(manual_payable[is_review].sum()),
        "full_population_eur": {
            "contract_live": float(total_contract_live),
            "manual": float(total_manual),
            "contract_minus_manual": float(total_contract_live - total_manual),
            "direction": (
                "Bosch UNDERPAID BMW (contract > manual)"
                if total_contract_live > total_manual
                else "Bosch OVERPAID BMW (manual > contract)"
            ),
        },
        "ambiguous_only_eur": {
            "contract_live": float(amb_live_contract),
            "manual": float(amb_manual),
            "contract_minus_manual": float(amb_live_contract - amb_manual),
        },
        "frozen_reference_eur": {
            "frozen_contract_minus_manual_full": float(
                _num(frozen["delta_contract_minus_manual_final"]).fillna(0).sum()),
            "note": "Frozen comparable delta reference; not overwritten.",
        },
    }
    tag = "smoke" if LIMIT else "full"
    (OUT / f"bmw_live_full_population_{tag}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    keep = ["claim_number", "country", "part_description", "audit_bucket", "comparison_bucket",
            "manual_payable_final", "contract_payable_final", "live_decision", "live_group_key",
            "live_payable_final", "live_reason"]
    amb[keep].to_csv(OUT / f"bmw_live_full_population_{tag}_rows.csv", index=False)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
