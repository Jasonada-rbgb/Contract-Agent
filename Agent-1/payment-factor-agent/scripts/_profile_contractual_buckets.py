"""Profile the BMW challenge population by CONTRACTUAL reason so we can build
expert-clearable buckets (Spaetausfall rate, out-of-warranty 60mo, wear-part
exclusion, deadline, etc.)."""
import pandas as pd
import numpy as np
from pathlib import Path

FROZEN = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output\bmw_edc_claims_eval_verified_20260701\final_contract_audit\final_contract_audit_row_level.csv")
d = pd.read_csv(FROZEN, low_memory=False)
n = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
delta = n(d["delta_contract_minus_manual_final"])

# challenge population = non-aligned, non-legislative, non-insufficient
challenge = d[d["audit_bucket"].isin(["challengeable_status_only_delta", "manual_reason_delta_needs_expert_mapping"])].copy()
print("challenge rows:", len(challenge), "delta:", round(n(challenge['delta_contract_minus_manual_final']).sum(),0))

print("\n=== reason_kind within challenge ===")
g = challenge.groupby("reason_kind").apply(lambda x: pd.Series({"rows": len(x), "delta": round(n(x['delta_contract_minus_manual_final']).sum(),0)}), include_groups=False)
print(g.to_string())

print("\n=== reason_summary top patterns within challenge ===")
rs = challenge.groupby("reason_summary").apply(lambda x: pd.Series({"rows": len(x), "delta": round(n(x['delta_contract_minus_manual_final']).sum(),0)}), include_groups=False).sort_values("delta")
print(rs.head(20).to_string())

print("\n=== warranty_type reclassification (manual -> contract) within challenge ===")
challenge["_reclass"] = challenge["manual_warranty_type"].astype(str) + " -> " + challenge["contract_warranty_type"].astype(str)
rc = challenge.groupby("_reclass").apply(lambda x: pd.Series({"rows": len(x), "delta": round(n(x['delta_contract_minus_manual_final']).sum(),0)}), include_groups=False).sort_values("delta")
print(rc.to_string())

print("\n=== reason_categories within challenge (top) ===")
if "reason_categories" in challenge.columns:
    rcat = challenge.groupby("reason_categories").apply(lambda x: pd.Series({"rows": len(x), "delta": round(n(x['delta_contract_minus_manual_final']).sum(),0)}), include_groups=False).sort_values("delta")
    print(rcat.head(15).to_string())
