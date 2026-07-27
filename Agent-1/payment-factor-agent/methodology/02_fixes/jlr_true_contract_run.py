"""JLR TRUE contract run — no manual fallback.

The frozen method's fallback_effective_rate() prefers the workbook manual rate
when an acceptance basis exists, making 91% of value manual-inherited. This
scenario removes that fallback and applies the pipeline's own PFACC/DMYA/STAR
acceptance rates directly. Where no independent rate exists, the row is routed
to requires_review (NOT silently set to manual).

Produces a genuinely independent contract figure to compare against:
  - manual workbook
  - frozen "contract" method (91% manual-inherited)
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
RL = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override" / "jlr_contract_vs_manual_row_level.csv"
OUT = ROOT / "reverify_20260720" / "02_fixes"

DENOM_FLOOR_NOTE = "thin rates (<10) already carry corrected/override where applied; raw sample rates used here as the independent contract rate"


def clean_rate(v):
    v = pd.to_numeric(v, errors="coerce")
    return v


def main() -> int:
    d = pd.read_csv(RL, low_memory=False)
    exp = d[d["market_scope"].eq("export_market")].copy()
    insc = exp["delta_scope"].eq("in_contract_scope")

    gross = pd.to_numeric(exp["gross_cost_eur"], errors="coerce").fillna(0)
    manual = pd.to_numeric(exp["manual_final_recovery_eur"], errors="coerce").fillna(0)
    frozen_contract = pd.to_numeric(exp["contract_payable_eur"], errors="coerce").fillna(0)

    phase = pd.to_numeric(exp["corrected_dmya_phase"], errors="coerce")
    phase = phase.fillna(pd.to_numeric(exp["dmya_phase"], errors="coerce"))

    # Independent rate selection (NO manual fallback):
    #   dmya phase (=1): corrected_dmya_acceptance -> dmya_acceptance -> non_sample_dmya_acceptance
    #   sample phase(=0): final_sample_acceptance -> sample_part_acceptance -> sample_family_acceptance
    def indep_rate(row):
        ph = row["_phase"]
        if ph == 1:
            for col in ("corrected_dmya_acceptance", "dmya_acceptance", "non_sample_dmya_acceptance"):
                r = row.get(col)
                if pd.notna(r):
                    return float(r)
            return None
        for col in ("final_sample_acceptance", "sample_part_acceptance", "sample_family_acceptance"):
            r = row.get(col)
            if pd.notna(r):
                return float(r)
        return None

    exp["_phase"] = phase
    exp["_indep_rate"] = exp.apply(indep_rate, axis=1)

    # rate could be stored as fraction already; some are percentages. Normalize >1.5 as pct.
    exp["_indep_rate"] = exp["_indep_rate"].apply(lambda r: (r / 100.0) if (r is not None and r > 1.5) else r)

    has_rate = exp["_indep_rate"].notna()
    indep_payable = (gross * exp["_indep_rate"].fillna(0)).where(has_rate, other=float("nan"))
    # cap at gross
    indep_payable = indep_payable.where(indep_payable <= gross, gross)

    # rows with no independent rate -> requires_review (excluded from independent total, counted separately)
    review_mask = insc & (~has_rate)

    tot_manual = float(manual[insc].sum())
    tot_frozen = float(frozen_contract[insc].sum())
    tot_indep = float(indep_payable[insc & has_rate].sum())
    review_gross = float(gross[review_mask].sum())

    summary = {
        "scope": "export_market in-scope rows",
        "in_scope_rows": int(insc.sum()),
        "rows_with_independent_rate": int((insc & has_rate).sum()),
        "rows_requires_review_no_indep_rate": int(review_mask.sum()),
        "requires_review_gross_eur": review_gross,
        "totals_eur": {
            "manual": tot_manual,
            "frozen_contract_method_91pct_inherited": tot_frozen,
            "TRUE_independent_contract_rate_only": tot_indep,
        },
        "deltas_vs_manual_eur": {
            "frozen_method": tot_frozen - tot_manual,
            "true_independent": tot_indep - tot_manual,
        },
        "note": "TRUE independent excludes rows with no pipeline rate (routed to review). It applies PFACC/DMYA/STAR acceptance rates directly with NO manual fallback. This is the genuine contract figure.",
        "denominator_note": DENOM_FLOOR_NOTE,
    }
    (OUT / "jlr_true_contract_run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
