"""JLR date-basis sensitivity (like-for-like).

Applies DMYA rates derived under three STAR date bases (answer_only, both_dates,
created_only) to the SAME claim population (the frozen dmya_databricks rows), and
reports the contract-payable swing. Isolates purely the date-basis choice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
FROZEN_ROW_LEVEL = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override" / "jlr_contract_vs_manual_row_level.csv"
RATES = ROOT / "reverify_20260720" / "evidence" / "dmya_rate_by_datebasis_2023_2024.csv"
OUT = ROOT / "reverify_20260720" / "01_reproduced" / "jlr_datebasis_sensitivity.json"


def norm_my(v) -> str:
    s = str(v).replace(".0", "").strip().upper()
    return s


def main() -> int:
    df = pd.read_csv(FROZEN_ROW_LEVEL, low_memory=False)
    rates = pd.read_csv(RATES)
    rates["product_family"] = rates["product_family"].astype(str).str.upper()
    rates["model_year"] = rates["model_year"].apply(norm_my)
    rates["rate"] = pd.to_numeric(rates["cat1"], errors="coerce") / pd.to_numeric(rates["denom"], errors="coerce")

    # target population: databricks DMYA rows (the only rows whose rate depends on STAR date basis)
    pop = df[df["contract_reason_bucket"].astype(str).eq("dmya_databricks")].copy()
    pop["fam"] = pop["sqw_product_family"].astype(str).str.upper()
    pop["my"] = pop["corrected_model_year"].apply(norm_my)
    gross = pd.to_numeric(pop["gross_cost_eur"], errors="coerce").fillna(0)

    # baseline contract payable on this population (frozen, incl. DMTL 0.35 override)
    frozen_pop = pd.to_numeric(pop["contract_payable_eur"], errors="coerce").fillna(0).sum()

    out = {"population_rows": int(len(pop)), "frozen_contract_payable_on_population_eur": float(frozen_pop), "bases": {}}

    for basis in ["answer_only", "both_dates", "created_only"]:
        rmap = {
            (r.product_family, r.model_year): r.rate
            for r in rates[rates["basis"].eq(basis)].itertuples()
            if pd.notna(r.rate)
        }
        applied = pop.apply(
            lambda row: gross.loc[row.name] * rmap.get((row["fam"], row["my"]), float("nan")),
            axis=1,
        )
        # rows where this basis has no rate -> fall back to frozen payable (like-for-like keeps them constant)
        applied = applied.fillna(pd.to_numeric(pop["contract_payable_eur"], errors="coerce"))
        total = float(applied.sum())
        out["bases"][basis] = {
            "contract_payable_on_population_eur": total,
            "delta_vs_frozen_eur": total - float(frozen_pop),
            "rate_keys_available": len(rmap),
        }

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
