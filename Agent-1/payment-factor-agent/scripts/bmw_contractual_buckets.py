"""Decompose the BMW recoverable/challenge population into CONTRACTUAL buckets,
each tied to a clause/ruling so BMW experts can judge 'legitimate or not'.

Frozen is READ-ONLY. Prints the clause-bucket table for sign-off.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path

FROZEN = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output\bmw_edc_claims_eval_verified_20260701\final_contract_audit\final_contract_audit_row_level.csv")


def n(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def eur(x):
    return f"EUR {x:,.0f}"


# Map raw reason tokens to a plain contractual-basis label + the clause it implicates.
TOKEN_TO_CLAUSE = {
    "status_in_gw": ("Status: 'in GW' (standard warranty asserted)", "Rate-selection clause: standard vs extended GW rate for in-warranty claims"),
    "status_late_failure": ("Status: Spaetausfall (late failure)", "Late-failure (Spaetausfall) rate clause (37-60 month window)"),
    "late_failure_reason": ("Late-failure reasoning present", "Late-failure (Spaetausfall) rate clause"),
    "extended_gw_or_goodwill_reason": ("Extended GW / goodwill reason", "Extended-warranty / goodwill coverage clause"),
    "manual_deadlines_met": ("Manual states deadlines met", "Warranty-period / deadline clause"),
    "legal_regulatory": ("Legal / regulatory (government-legislated)", "Statutory / government-legislated coverage -> full rate"),
    "explicit_exclusion_or_settlement": ("Explicit exclusion / settlement", "Exclusion or prior-settlement clause (Ausgrenzen)"),
    "prior_agreement": ("Prior agreement", "Prior-agreement / settlement clause"),
    "cost_adjustment": ("Cost adjustment / cap", "Cost cap (Deckelung) clause"),
    "duplicate_or_data_adjustment": ("Duplicate / data adjustment", "Data-quality / duplicate handling (not a contract clause)"),
    "status_not_justified": ("Status not justified", "Status-justification clause"),
    "other_manual_reason_text": ("Other manual reason (unmapped)", "Requires expert mapping to a clause"),
}

# Priority order: the single governing clause for a row = highest-priority token present.
PRIORITY = [
    "legal_regulatory",
    "explicit_exclusion_or_settlement",
    "prior_agreement",
    "status_late_failure",
    "late_failure_reason",
    "extended_gw_or_goodwill_reason",
    "cost_adjustment",
    "manual_deadlines_met",
    "status_not_justified",
    "status_in_gw",
    "other_manual_reason_text",
    "duplicate_or_data_adjustment",
]


def governing_clause(cats: str) -> str:
    toks = set(str(cats).split("|"))
    for p in PRIORITY:
        if p in toks:
            return p
    return "other_manual_reason_text"


def main() -> int:
    d = pd.read_csv(FROZEN, low_memory=False)
    d["delta"] = n(d["delta_contract_minus_manual_final"])

    # Focus on the population that actually carries a delta (the challengeable + needs-mapping + legislative)
    challenge = d[d["audit_bucket"].isin([
        "challengeable_status_only_delta",
        "manual_reason_delta_needs_expert_mapping",
        "expert_review_contract_exception",
    ])].copy()

    challenge["governing_token"] = challenge["reason_categories"].map(governing_clause)
    challenge["contractual_basis"] = challenge["governing_token"].map(lambda t: TOKEN_TO_CLAUSE[t][0])
    challenge["clause"] = challenge["governing_token"].map(lambda t: TOKEN_TO_CLAUSE[t][1])

    print("=" * 90)
    print("BMW CONTRACTUAL BUCKETS - challenge population grouped by governing clause")
    print("=" * 90)
    g = challenge.groupby(["contractual_basis", "clause"]).agg(
        rows=("delta", "size"),
        delta_eur=("delta", "sum"),
    ).reset_index().sort_values("delta_eur")
    total = 0.0
    for _, r in g.iterrows():
        total += r["delta_eur"]
        print(f"  {r['contractual_basis'][:42]:42s} rows={int(r['rows']):6,d}  {eur(r['delta_eur']):>14}")
        print(f"      -> clause: {r['clause']}")
    print("-" * 90)
    print(f"  TOTAL challenge population: {eur(total)}  ({len(challenge):,} rows)")
    print()

    # Also split each clause bucket by audit_bucket so hi-conf vs to-check is visible per clause
    print("=" * 90)
    print("SAME, split by confidence (audit_bucket)")
    print("=" * 90)
    piv = pd.pivot_table(challenge, values="delta", index="contractual_basis",
                         columns="audit_bucket", aggfunc="sum", fill_value=0)
    print(piv.round(0).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
