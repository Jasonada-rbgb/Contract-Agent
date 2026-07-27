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

## Rules Artifacts

- `rules/payment_factor_rules.json` - formal payment-factor rules (BMW fixed-acceptance timing rules with clause provenance; JLR technical/extrapolated factors). Cites `provenance/bmw_ruleset.json`.
- `rules/overrides.json` - governed override table (e.g. OVR-JLR-DMTL-MY2023) with evidence references.

## Provenance

- `provenance/bmw_ruleset.json` - frozen BMW ruleset the rules were compiled from (fingerprint `e71bec717be8a433`, compiled 2026-06-15 from `compiled_profile`). This is the exact source artifact `rules/payment_factor_rules.json` references.

## Methodology (How The Rules Were Built & Verified)

See `methodology/README.md` for the full index. Staged reproduction pipeline (`methodology/reverify_20260720` structure):

- `00_baseline/` - frozen baseline + manifest + pinning script.
- `01_reproduced/` - deterministic BMW/JLR scenario engines reproducing the rulings 1:1, plus date-basis and thin-denominator sensitivity.
- `02_fixes/` - BMW ruleset re-extraction from the contract (caches bypassed, proving rules are contract-driven not hardcoded), live contract-query verification, JLR contract-led rebuild, and rate-provenance flagging.
- `03_comparison/` - comparison ledger and LLM cost notes.
- `04_oem_handoff/` - verification reports and methodology fidelity disclosures (including the JLR ~91% manual-inheritance finding).
- `evidence/` - DMTL override and DMYA rate-by-datebasis evidence.

## Scripts (Full Set)

In addition to the four scripts noted above, `scripts/` contains the payment-factor agent prototype (`payment_factor_agents.py`), denominator governance, JLR contract-led rebuild and STAR answer-date logic, BMW contractual bucketing and review reconciliation, plus `_profile_*`/`_validate_*` helpers used during the audit.

## Exclusions

No row-level claim files were included (e.g. `*_rows.csv` up to ~42 MB), and compiled `__pycache__/*.pyc` were omitted. This keeps the package focused on technical review and avoids unnecessary VIN/claim-level detail. A full raw re-run is available on request.
