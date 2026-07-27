"""JLR thin-denominator (<10) exposure.

Quantifies how much of the frozen databricks-DMYA contract payable rests on STAR
rates with denominator < 10, by joining the thin-denominator evidence keys onto
the frozen row-level population.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
FROZEN = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override"
ROW_LEVEL = FROZEN / "jlr_contract_vs_manual_row_level.csv"
THIN = FROZEN / "audited_thin_dmya_rate_denominators_lt10.csv"
OUT = ROOT / "reverify_20260720" / "01_reproduced" / "jlr_thin_denominator_exposure.json"


def norm_my(v) -> str:
    return str(v).replace(".0", "").strip().upper()


def main() -> int:
    df = pd.read_csv(ROW_LEVEL, low_memory=False)
    thin = pd.read_csv(THIN)
    thin_keys = {
        (str(r.product_family).upper(), norm_my(r.model_year))
        for r in thin.itertuples()
    }

    pop = df[df["contract_reason_bucket"].astype(str).eq("dmya_databricks")].copy()
    pop["fam"] = pop["sqw_product_family"].astype(str).str.upper()
    pop["my"] = pop["corrected_model_year"].apply(norm_my)
    pop["is_thin"] = pop.apply(lambda r: (r["fam"], r["my"]) in thin_keys, axis=1)

    contract = pd.to_numeric(pop["contract_payable_eur"], errors="coerce").fillna(0)
    manual = pd.to_numeric(pop["manual_final_recovery_eur"], errors="coerce").fillna(0)

    thin_mask = pop["is_thin"]
    out = {
        "databricks_population_rows": int(len(pop)),
        "thin_rows": int(thin_mask.sum()),
        "thin_contract_payable_eur": float(contract[thin_mask].sum()),
        "thin_manual_eur": float(manual[thin_mask].sum()),
        "thin_contract_minus_manual_eur": float((contract - manual)[thin_mask].sum()),
        "non_thin_contract_payable_eur": float(contract[~thin_mask].sum()),
        "note": "Thin = STAR DMYA rate with denominator<10 per audited_thin_dmya_rate_denominators_lt10.csv. DMTL MY2023 (4/14 denom) is included in thin set.",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
