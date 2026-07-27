"""Estimate the BMW 36->60 month fix impact WITHOUT a live run.

Frozen scored US/Puerto Rico/Canada at 36 months -> many claims 'out_of_warranty'
-> contract paid 0. If those markets are actually 60 months, claims that fall
INSIDE 60mo (and within mileage) flip to in_warranty -> contract should pay.

We measure, from the frozen row-level, how much contract payable would be ADDED
if US/PR/Canada rows currently rejected on the period rule are brought in-warranty.
This SHRINKS the overpayment (contract goes up toward manual).

We do NOT overwrite frozen. This is an estimate band, not a live re-derivation.
"""
import pandas as pd
import numpy as np
from pathlib import Path

FROZEN = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output\bmw_edc_claims_eval_verified_20260701\final_contract_audit\final_contract_audit_row_level.csv")

d = pd.read_csv(FROZEN, low_memory=False)
print("total frozen rows:", len(d))

def num(s): return pd.to_numeric(s, errors="coerce").fillna(0)

# frozen totals (unchanged reference)
frozen_delta = num(d["delta_contract_minus_manual_final"]).sum()
frozen_contract = num(d["contract_payable_final"]).sum()
frozen_manual = num(d["manual_payable_final"]).sum()
print(f"\nFROZEN reference:")
print(f"  contract_payable_final: {frozen_contract:,.2f}")
print(f"  manual_payable_final:   {frozen_manual:,.2f}")
print(f"  delta (contract-manual):{frozen_delta:,.2f}")

# identify US / PR / Canada rows
c = d["country"].astype(str).str.upper()
us = c.str.contains("US|USA|UNITED STATES|PUERTO|CANADA", na=False, regex=True)
print(f"\nUS/PR/Canada rows: {int(us.sum()):,}")

# among those, which are currently rejected on the warranty-period basis?
# frozen out-of-warranty proxy: contract paid 0 but manual paid > 0 (Bosch paid, contract said no)
manual_pay = num(d["manual_payable_final"])
contract_pay = num(d["contract_payable_final"])
gross = num(d["total_cost"])
contract_rate = pd.to_numeric(d["contract_rate"], errors="coerce")

rejected = us & (contract_pay <= 0.005) & (manual_pay > 0)
print(f"US/PR/Canada rows contract=0 but manual>0 (candidate flips): {int(rejected.sum()):,}")
print(f"  their manual value: {manual_pay[rejected].sum():,.2f}")
print(f"  their gross value:  {gross[rejected].sum():,.2f}")

# Estimate contract payable if flipped IN:
#  - upper bound: contract pays at manual level (parity) -> adds manual value
#  - mid: contract pays gross * contract_rate where a rate exists, else manual
#  - lower/none already = frozen
add_parity = manual_pay[rejected].sum()

rate = contract_rate[rejected]
have_rate = rate.notna() & (rate > 0)
rate_norm = np.where(rate > 1.5, rate/100.0, rate)  # normalise percent
est_rate_pay = np.where(have_rate, gross[rejected].values * np.nan_to_num(rate_norm), manual_pay[rejected].values)
est_rate_pay = np.minimum(est_rate_pay, gross[rejected].values)  # cap at gross
add_rated = float(np.nansum(est_rate_pay))

print(f"\n--- ESTIMATED added contract payable if these flip IN-warranty ---")
print(f"  parity assumption (contract == manual): +{add_parity:,.2f}")
print(f"  rate-based (gross*contract_rate, else manual, capped): +{add_rated:,.2f}")

# how many of the rejected have a contract_rate at all?
print(f"  rejected rows WITH a contract_rate: {int(have_rate.sum()):,} / {int(rejected.sum()):,}")

print(f"\n--- RESULTING BMW delta band (contract - manual) ---")
print(f"  frozen delta:                 {frozen_delta:,.2f}")
print(f"  + parity flip:                {frozen_delta + add_parity:,.2f}")
print(f"  + rate-based flip:            {frozen_delta + add_rated:,.2f}")
print("\nNote: NOT all flips are guaranteed in-warranty; some US/PR/Canada rows")
print("may still be beyond 60mo or over mileage. This is an UPPER band on the")
print("shrink. A live run is required to pin the exact figure.")
