"""Recoverability check done correctly: read frozen source with ALL needed cols,
filter to the same export in-scope population, and profile directly (no lossy join)."""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
RL = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override" / "jlr_contract_vs_manual_row_level.csv"

d = pd.read_csv(RL, low_memory=False)
exp = d[(d["market_scope"].eq("export_market")) & (d["delta_scope"].eq("in_contract_scope"))].copy()
print("export in-scope rows:", len(exp))

fam = exp["sqw_product_family"].astype(str).str.upper()
cmy = exp["corrected_model_year"].astype(str).str.replace(".0","",regex=False)
phase = pd.to_numeric(exp["corrected_dmya_phase"], errors="coerce").fillna(pd.to_numeric(exp["dmya_phase"], errors="coerce"))

is_ngi = fam.str.contains("NGI", na=False)
nan_my = cmy.isin(["nan","","NaN"])
# review = no phase (nan) OR thin; approximate withheld = phase is NaN (matches 79,528) + thin handled separately
withheld = phase.isna()
manual = pd.to_numeric(exp["manual_final_recovery_eur"], errors="coerce").fillna(0)

cand = withheld & (~is_ngi) & nan_my
print("non-NGI + nan-MY + no-phase candidates:", int(cand.sum()), "manual:", round(manual[cand].sum(),2))

def frac(mask_full, base):
    m = mask_full & base
    return f"{int(m.sum())} ({100*m.sum()/max(base.sum(),1):.1f}% of candidates)"

c = cand
print("\n--- recoverability WITHIN candidates ---")
print("raw model_year present:", frac(pd.to_numeric(exp['model_year'],errors='coerce').notna(), c))
print("production_date present:", frac(exp['production_date'].notna(), c))
print("warranty_start_date present:", frac(exp['warranty_start_date'].notna(), c))

anyrate_cols = ["dmya_acceptance","corrected_dmya_acceptance","non_sample_dmya_acceptance",
                "final_sample_acceptance","sample_part_acceptance","sample_family_acceptance"]
anyrate = np.zeros(len(exp), dtype=bool)
for col in anyrate_cols:
    if col in exp.columns:
        anyrate |= pd.to_numeric(exp[col], errors="coerce").notna().values
anyrate = pd.Series(anyrate, index=exp.index)
print("has SOME acceptance rate in source:", frac(anyrate, c))

mval = manual.values
cmask = c.values
arr = anyrate.values
print("\ncandidates WITH a usable rate already present:", int((cmask & arr).sum()),
      "manual:", round(mval[cmask & arr].sum(),2))
print("candidates with NO rate anywhere (true unknown -> expert):", int((cmask & ~arr).sum()),
      "manual:", round(mval[cmask & ~arr].sum(),2))
