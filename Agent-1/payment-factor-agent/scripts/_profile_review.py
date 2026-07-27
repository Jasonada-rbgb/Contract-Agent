"""Profile the JLR withheld review rows to identify ratable subsets."""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
rows = pd.read_csv(ROOT / "reverify_20260720" / "02_fixes" / "jlr_contract_led_rebuild_rows.csv", low_memory=False)
print("total rows:", len(rows))
print("\naction counts:")
print(rows["_action"].value_counts())

rev = rows[rows["_action"].isin(["requires_review", "requires_review_thin"])].copy()
print("\n=== review rows:", len(rev), "===")
manual = pd.to_numeric(rev["manual_final_recovery_eur"], errors="coerce").fillna(0)
gross = pd.to_numeric(rev["gross_cost_eur"], errors="coerce").fillna(0)
print("manual value withheld:", round(manual.sum(), 2))
print("gross withheld:", round(gross.sum(), 2))

print("\nphase breakdown of review rows:")
print(rev["_phase"].value_counts(dropna=False))

print("\n_indep populated among review rows (had a rate but still withheld):")
print(rev["_indep"].notna().value_counts())

print("\nreview rows WITH a phase (1 or 0):", int(rev["_phase"].isin([0, 1]).sum()))
print("review rows with NO phase (NaN):", int(rev["_phase"].isna().sum()))

# thin rows specifically
thin = rev[rev["_action"].eq("requires_review_thin")]
print("\n=== thin rows:", len(thin), "manual:", round(pd.to_numeric(thin['manual_final_recovery_eur'],errors='coerce').fillna(0).sum(),2), "===")

# families/MYs in review rows -- how concentrated?
rev["_key"] = rev["sqw_product_family"].astype(str).str.upper() + "|" + rev["corrected_model_year"].astype(str).str.replace(".0", "", regex=False)
top = rev.groupby("_key").agg(n=("_key", "size"), manual=("manual_final_recovery_eur", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum())).sort_values("manual", ascending=False)
print("\ntop 20 review keys by withheld manual value:")
print(top.head(20).to_string())
print("\ndistinct review keys:", len(top))
