"""Can withheld candidates borrow a STAR/DMYA rate from RATED rows of the same
family (+/- model year)? Build family-level rate map from rated rows and see how
much withheld manual value can be defensibly extended vs must go to expert."""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
RL = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override" / "jlr_contract_vs_manual_row_level.csv"
rows = pd.read_csv(ROOT / "reverify_20260720" / "02_fixes" / "jlr_contract_led_rebuild_rows.csv", low_memory=False)

# rated rows and their applied rate
rated = rows[rows["_action"].isin(["contract_rate", "override"])].copy()
rated["_fam"] = rated["sqw_product_family"].astype(str).str.upper()
rated["_rate"] = pd.to_numeric(rated["_rebuilt_rate"], errors="coerce")

# family-level rate (manual-weighted mean of applied rate), plus coverage
fam_rate = rated.groupby("_fam").apply(
    lambda g: pd.Series({
        "rate_wmean": np.average(g["_rate"], weights=pd.to_numeric(g["gross_cost_eur"],errors="coerce").fillna(1)+1),
        "n_rated": len(g),
    }), include_groups=False)
print("families with a rated rate:", len(fam_rate))

# withheld candidates (non-NGI, no-phase)
rev = rows[rows["_action"].isin(["requires_review","requires_review_thin"])].copy()
rev["_fam"] = rev["sqw_product_family"].astype(str).str.upper()
rev["_manual"] = pd.to_numeric(rev["manual_final_recovery_eur"], errors="coerce").fillna(0)
rev["_gross"] = pd.to_numeric(rev["gross_cost_eur"], errors="coerce").fillna(0)
is_ngi = rev["_fam"].str.contains("NGI", na=False)
cand = rev[~is_ngi].copy()

cand = cand.merge(fam_rate, left_on="_fam", right_index=True, how="left")
has_fam_rate = cand["rate_wmean"].notna()
print("\nwithheld non-NGI rows:", len(cand), "manual:", round(cand['_manual'].sum(),2))
print("  can borrow family rate:", int(has_fam_rate.sum()), "manual:", round(cand.loc[has_fam_rate,'_manual'].sum(),2))
print("  NO family rate (expert):", int((~has_fam_rate).sum()), "manual:", round(cand.loc[~has_fam_rate,'_manual'].sum(),2))

# what would borrowing the family rate add to contract-led payable?
cand["_borrowed_payable"] = (cand["_gross"] * cand["rate_wmean"].fillna(0)).clip(upper=cand["_gross"])
extend_payable = float(cand.loc[has_fam_rate, "_borrowed_payable"].sum())
extend_manual = float(cand.loc[has_fam_rate, "_manual"].sum())
print("\nIF we extend family rates to borrowable withheld rows:")
print("  added contract-led payable:", round(extend_payable,2))
print("  their manual value:", round(extend_manual,2))
print("  contract - manual on these rows:", round(extend_payable - extend_manual,2))

# persist the family rate map for the rebuild
fam_rate.reset_index().to_csv(ROOT / "reverify_20260720" / "02_fixes" / "jlr_family_rate_map.csv", index=False)
print("\nwrote jlr_family_rate_map.csv")
