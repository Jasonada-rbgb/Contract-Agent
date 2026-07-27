"""Add rate-provenance transparency to JLR export rows.

Flags every in-scope export row as manual_inherited vs rate_derived so the
91/9 split is transparent to JLR. Also caps payable at gross (fixes >100% rows).
Writes a per-reason-bucket provenance summary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
RL = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override" / "jlr_contract_vs_manual_row_level.csv"
OUT = ROOT / "reverify_20260720" / "02_fixes"


def main() -> int:
    d = pd.read_csv(RL, low_memory=False)
    exp = d[d["market_scope"].eq("export_market")].copy()
    c = pd.to_numeric(exp["contract_payable_eur"], errors="coerce").fillna(0)
    m = pd.to_numeric(exp["manual_final_recovery_eur"], errors="coerce").fillna(0)
    g = pd.to_numeric(exp["gross_cost_eur"], errors="coerce").fillna(0)
    insc = exp["delta_scope"].eq("in_contract_scope")

    exp["rate_provenance"] = "rate_derived"
    exp.loc[((c - m).abs() < 0.01) & (m > 0), "rate_provenance"] = "manual_inherited"

    # cap at gross (fix >100% payable)
    capped = int(((c > g * 1.0001) & (g > 0)).sum())
    exp["contract_payable_capped_eur"] = c.where(c <= g, g)

    prov = exp[insc].groupby(["contract_reason_bucket", "rate_provenance"]).agg(
        rows=("vin", "size"),
        contract_payable_eur=("contract_payable_eur", "sum"),
    ).reset_index()
    prov.to_csv(OUT / "jlr_rate_provenance_by_bucket.csv", index=False)

    tot = c[insc].sum()
    inh = c[insc & exp["rate_provenance"].eq("manual_inherited")].sum()
    summary = {
        "in_scope_export_contract_payable_eur": float(tot),
        "manual_inherited_eur": float(inh),
        "manual_inherited_pct": round(100 * inh / tot, 1),
        "rate_derived_eur": float(tot - inh),
        "rate_derived_pct": round(100 * (tot - inh) / tot, 1),
        "rows_capped_at_gross": capped,
        "disclosure": "For 91% of in-scope export value the contract method equals the manual workbook rate by construction (fallback_effective_rate prefers manual when acceptance basis present). The contract-vs-manual delta can only arise on the rate_derived portion. Disclose to JLR.",
    }
    (OUT / "jlr_rate_provenance_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
