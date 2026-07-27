"""Phase 0: Pin the frozen baseline for BMW + JLR re-verification.

Captures immutable frozen totals from the two authoritative runs, records
the row-count reconciliation, and writes a single baseline manifest that all
later scenarios compare against. Read-only against source artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT_ROOT = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output")
BMW_RUN = OUTPUT_ROOT / "bmw_edc_claims_eval_verified_20260701"
JLR_RUN = OUTPUT_ROOT / "jlr_contract_audit_full_20260713_audited_dmya_resample_override"
BASELINE_DIR = OUTPUT_ROOT / "reverify_20260720" / "00_baseline"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    bmw_final = _load(BMW_RUN / "final_contract_audit" / "final_contract_audit_summary.json")
    bmw_ausg = _load(BMW_RUN / "final_contract_audit" / "ausgrenzen_x_corrected_totals.json")
    jlr_final = _load(JLR_RUN / "jlr_final_summary.json")
    jlr_checks = _load(JLR_RUN / "audited_recalculation_checks.json")

    baseline = {
        "pinned_utc": "2026-07-20",
        "authoritative_runs": {
            "bmw": str(BMW_RUN),
            "jlr": str(JLR_RUN),
        },
        "bmw": {
            "rows_evaluated": bmw_final["rows"],
            "manual_comparable_value": bmw_final["manual_comparable_value"],
            "contract_method_payable_value": bmw_final["contract_method_payable_value"],
            "delta_contract_minus_manual_comparable": bmw_final["delta_contract_minus_manual_comparable"],
            "corrected_manual_total_ausgrenzen_x": bmw_ausg["corrected_manual_total_if_x_zero"],
            "corrected_contract_total_ausgrenzen_x": bmw_ausg["corrected_contract_total_if_x_zero"],
            "corrected_delta_ausgrenzen_x": bmw_ausg["corrected_delta_contract_minus_manual_if_x_zero"],
            "row_count_reconciliation": {
                "manifest_rows": 311977,
                "evaluated_rows": 311968,
                "gap": 9,
                "explanation": "8 rows dropped in 2024 MA-100 (Kopie von...Neuschuetz_01.xlsx) + 1 row in 2025 20260505_JEA_Bosch_sent.xlsx during normalization (empty/invalid rows). Immaterial. verification_report.json row_count_mismatches=[].",
            },
            "four_eyes": bmw_final["grouped_llm_four_eyes"],
        },
        "jlr": {
            "rows_loaded": jlr_final["rows_loaded"],
            "workbooks_processed": jlr_final["workbooks_processed"],
            "manual_final_recovery_eur": jlr_final["manual_final_recovery_eur"],
            "contract_method_payable_eur": jlr_final["contract_method_payable_eur"],
            "manual_minus_contract_in_scope_eur": jlr_final["manual_minus_contract_in_scope_eur"],
            "dmtl_override": jlr_checks["dmtl_override"],
            "ngi_status": jlr_checks["ngi_status"],
            "market_scope_manual_eur": jlr_final["market_scope_manual_eur"],
            "market_scope_contract_eur": jlr_final["market_scope_contract_eur"],
        },
        "combined": {
            "manual_payable_eur": bmw_ausg["corrected_manual_total_if_x_zero"] + jlr_final["manual_final_recovery_eur"],
            "contract_payable_eur": bmw_ausg["corrected_contract_total_if_x_zero"] + jlr_final["contract_method_payable_eur"],
        },
    }
    baseline["combined"]["delta_contract_minus_manual_eur"] = (
        baseline["combined"]["contract_payable_eur"] - baseline["combined"]["manual_payable_eur"]
    )

    out = BASELINE_DIR / "frozen_baseline.json"
    out.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(json.dumps(baseline, indent=2))
    print(f"\nWROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
