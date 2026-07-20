# Manifest

## Documentation

- `README.md` - technical review guide for this package.
- `docs/full.md` - consolidated audit context, methodology, current totals, open items, and payment-factor agent proposal.
- `rules/jlr_claims_rules.md` - JLR data rules used during the audit.

## Scripts

- `scripts/jlr_full_contract_audit.py`
  - Current JLR prototype for workbook normalization, PFACC/DMYA routing, CAT logic, contract-vs-manual comparison, and output writing.
  - Key functions: `rate_from_row`, `contract_decision`, `sample_market_decision`, `export_market_decision`, `extract_dmya_rates`, `extract_pfacc_rates`.

- `scripts/jlr_databricks_enrichment.py`
  - Databricks enrichment prototype for VIN production model year and STAR-derived DMYA rates.
  - Note: this file still shows the older created+answered-date filter; the final reviewed output used answer-date-only rates from an artifact.

- `scripts/bmw_dashboard_refresh_extract.py`
  - BMW dashboard-ready extraction and adjustment logic from the BMW final audit output.
  - Shows fixed-rate output columns such as manual rate, contract rate, warranty type, and adjusted contract payable.

- `scripts/bmw_jlr_dashboard_build.py`
  - Combined BMW/JLR dashboard data build logic.

## BMW Aggregate Evidence

- `evidence/bmw/final_contract_audit_summary.json`
- `evidence/bmw/final_contract_audit_by_bucket.csv`
- `evidence/bmw/latest_adjusted_delta_reason_breakdown.json`
- `evidence/bmw/latest_adjusted_delta_by_reason.csv`
- `evidence/bmw/2025_missing_exclusion_revised_challenge_summary.json`
- `evidence/bmw/ausgrenzen_x_corrected_totals.json`
- `evidence/bmw/MANAGEMENT_SUMMARY.md`
- `evidence/bmw/SPATAUSFALL_CONTRACT_RULE_DECISION.md`
- `evidence/bmw/CONTRACT_AGENT_FINAL_PROBE.md`

## JLR Aggregate Evidence

- `evidence/jlr/jlr_final_summary.json`
- `evidence/jlr/audited_recalculation_checks.json`
- `evidence/jlr/audited_delta_by_reason.csv`
- `evidence/jlr/audited_databricks_dmya_by_product.csv`
- `evidence/jlr/audited_thin_dmya_rate_denominators_lt10.csv`
- `evidence/jlr/jlr_dmya_rate_source_audit.csv`
- `evidence/jlr/jlr_pfacc_rate_source_audit.csv`

## Exclusions

No row-level claim files were included. This keeps the package focused on technical review and avoids unnecessary VIN/claim-level detail.
