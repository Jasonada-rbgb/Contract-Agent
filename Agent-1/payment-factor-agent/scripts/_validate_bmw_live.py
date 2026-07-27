"""Validate the BMW live full-population run before trusting the -6.77m figure.
Checks: (1) did the 60mo US/PR/Canada rows flip to in_warranty?
        (2) decision distribution by comparison_bucket / country,
        (3) reconcile live vs frozen by bucket."""
import pandas as pd
import numpy as np
from pathlib import Path

OUT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output\reverify_20260720\02_fixes")
rows = pd.read_csv(OUT / "bmw_live_full_population_full_rows.csv", low_memory=False)
print("ambiguous rows:", len(rows))
print("\n=== live_decision overall ===")
print(rows["live_decision"].value_counts(dropna=False))

# 1) 60mo market rows: US / Puerto Rico / Canada
rows["_ctry"] = rows["country"].astype(str).str.upper()
us_mask = rows["_ctry"].str.contains("US|USA|UNITED STATES|PUERTO|CANADA", na=False, regex=True)
print("\n=== US/PR/Canada rows (should flip OUT->IN under 60mo fix) ===")
print("count:", int(us_mask.sum()))
print(rows.loc[us_mask, "live_decision"].value_counts(dropna=False))

print("\n=== decision by comparison_bucket ===")
print(pd.crosstab(rows["comparison_bucket"], rows["live_decision"]))

print("\n=== decision by audit_bucket ===")
print(pd.crosstab(rows["audit_bucket"], rows["live_decision"]))

# 2) sanity: sample in_warranty and out_of_warranty rows
print("\n=== sample in_warranty rows ===")
iw = rows[rows["live_decision"].astype(str).str.contains("in_warranty", na=False)]
print(iw[["country","part_description","comparison_bucket","manual_payable_final","contract_payable_final","live_payable_final","live_reason"]].head(5).to_string())
print("\n=== sample out_of_warranty rows in the 60mo/5m candidate bucket ===")
oo = rows[(rows["live_decision"].astype(str).str.contains("out_of_warranty", na=False)) &
          (rows["comparison_bucket"].astype(str).str.contains("60_5m", na=False))]
print("count in that bucket OUT:", len(oo))
print(oo[["country","part_description","manual_payable_final","contract_payable_final","live_reason"]].head(5).to_string())
