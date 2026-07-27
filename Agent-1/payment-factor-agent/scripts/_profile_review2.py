"""Deeper profile: separate NGI (governed-open) from recoverable model-year gaps,
and check whether the frozen row-level carries a usable rate/phase we can restore."""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
RL = ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override" / "jlr_contract_vs_manual_row_level.csv"
rows = pd.read_csv(ROOT / "reverify_20260720" / "02_fixes" / "jlr_contract_led_rebuild_rows.csv", low_memory=False)

rev = rows[rows["_action"].isin(["requires_review", "requires_review_thin"])].copy()
rev["_fam"] = rev["sqw_product_family"].astype(str).str.upper()
manual = pd.to_numeric(rev["manual_final_recovery_eur"], errors="coerce").fillna(0)

# NGI governed-open
is_ngi = rev["_fam"].str.contains("NGI", na=False)
print("NGI governed-open rows:", int(is_ngi.sum()), "manual:", round(manual[is_ngi].sum(), 2))

nan_my = rev["corrected_model_year"].astype(str).str.replace(".0","",regex=False).isin(["nan","", "NaN"])
print("review rows with nan model_year:", int(nan_my.sum()), "manual:", round(manual[nan_my].sum(),2))
print("review rows with a real model_year:", int((~nan_my).sum()), "manual:", round(manual[~nan_my].sum(),2))

# non-NGI, nan-MY  -> candidate for model-year recovery
cand = (~is_ngi) & nan_my
print("\nnon-NGI + nan-MY (model-year recovery candidates):", int(cand.sum()), "manual:", round(manual[cand].sum(),2))

# What columns in the FROZEN row-level might carry model year / phase for these claims?
print("\n=== inspecting frozen row-level source columns ===")
src = pd.read_csv(RL, low_memory=False, nrows=5)
cols = list(src.columns)
print("total cols:", len(cols))
for c in cols:
    lc = c.lower()
    if any(k in lc for k in ["year","phase","dmya","accept","sample","star","cat","model","build","date"]):
        print("  ", c)
