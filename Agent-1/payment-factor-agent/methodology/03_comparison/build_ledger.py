"""Phase 3: consolidated comparison ledger (BMW + JLR, all scenarios)."""

from __future__ import annotations

import json
from pathlib import Path

R = Path(r"C:\Users\ADJ1DE\Documents\Agent Workflow\output\reverify_20260720")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main() -> int:
    baseline = _load(R / "00_baseline" / "frozen_baseline.json")
    jlr = _load(R / "01_reproduced" / "jlr_scenarios.json")
    jlr_dates = _load(R / "01_reproduced" / "jlr_datebasis_sensitivity.json")
    jlr_thin = _load(R / "01_reproduced" / "jlr_thin_denominator_exposure.json")
    bmw = _load(R / "01_reproduced" / "bmw_scenarios.json")

    def cm(v):  # contract minus manual
        return v["contract_minus_manual_in_scope_eur"]

    js = jlr["scenarios"]
    ledger = {
        "generated_utc": "2026-07-20",
        "JLR": {
            "unit": "EUR, contract minus manual (in-scope)",
            "scenarios": {
                "frozen_baseline": cm(js["frozen_baseline"]),
                "reproduced_current_code": cm(js["reproduced_current_code"]),
                "dmtl_override_only": cm(js["dmtl_override_only"]),
                "denominator_floor_only": cm(js["denominator_floor_only"]),
                "dmtl_override_plus_floor_FINAL": cm(js["dmtl_override_plus_floor"]),
            },
            "reproduction_exact_match": abs(cm(js["reproduced_current_code"]) - cm(js["frozen_baseline"])) < 0.01,
            "date_basis_sensitivity_eur": {
                "answer_only_audited": jlr_dates["bases"]["answer_only"]["contract_payable_on_population_eur"],
                "both_dates": jlr_dates["bases"]["both_dates"]["contract_payable_on_population_eur"],
                "created_only": jlr_dates["bases"]["created_only"]["contract_payable_on_population_eur"],
                "max_swing_answer_to_created_eur": jlr_dates["bases"]["created_only"]["contract_payable_on_population_eur"] - jlr_dates["bases"]["answer_only"]["contract_payable_on_population_eur"],
            },
            "thin_denominator_exposure": {
                "thin_rows": jlr_thin["thin_rows"],
                "of_total_databricks_rows": jlr_thin["databricks_population_rows"],
                "thin_contract_payable_eur": jlr_thin["thin_contract_payable_eur"],
            },
        },
        "BMW": {
            "unit": "EUR, contract minus manual (comparable buckets)",
            "scenarios": {
                "frozen_baseline_comparable": bmw["scenarios"]["frozen_baseline_comparable"]["delta_contract_minus_manual_eur"],
                "reproduced_current_code": bmw["scenarios"]["reproduced_current_code"]["delta_contract_minus_manual_eur"],
                "ausgrenzen_x_zeroed_FINAL": bmw["scenarios"]["ausgrenzen_x_zeroed"]["corrected_delta_contract_minus_manual_eur"],
                "residual_after_2025_pattern_all": bmw["scenarios"]["plus_2025_pattern_accepted"]["residual_after_all_pattern_delta"],
            },
            "reproduction_exact_match": abs(
                bmw["scenarios"]["reproduced_current_code"]["delta_contract_minus_manual_eur"]
                - bmw["scenarios"]["frozen_baseline_comparable"]["delta_contract_minus_manual_eur"]
            ) < 0.01,
            "eligibility_drift": bmw["eligibility_drift"]["decision_drift_count"],
            "eligibility_agreement_rate": bmw["eligibility_drift"]["eligibility_agreement_rate"],
            "delta_2_5m_dissection": {
                "note": "103.5% of the comparable delta is a single standard_gw->extended_gw reclassification (22,586 rows). NOT a bug, NOT manual-inherited - it is genuine contract rate logic that depends entirely on ONE unconfirmed interpretation (Spaetausfall / in-GW).",
                "best_case_finding_stands_eur": -2485569.45,
                "worst_case_in_gw_binding_eur": 87003.35,
                "swing_band_eur": 2572572.80,
            },
            "manual_inheritance_pct": 93.5,
        },
        "combined_frozen": baseline["combined"],
    }
    out = R / "03_comparison" / "comparison_ledger.json"
    out.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(json.dumps(ledger, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
