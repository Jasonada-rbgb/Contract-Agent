# Rule-Building & Verification Methodology

This folder documents **how the payment-factor rules were built and verified** —
including the deterministic derivation of the BMW ruleset from the Contract Agent
and the JLR contract-led rebuild. It complements `../docs/full.md` (narrative) and
`../rules/` (the resulting rule artifacts) with the actual reproduction pipeline.

The frozen source artifact the rules cite is at `../provenance/bmw_ruleset.json`
(fingerprint `e71bec717be8a433`, compiled 2026-06-15 from `compiled_profile`).

## Staged pipeline (`reverify_20260720`)

| Stage | Contents | Purpose |
| --- | --- | --- |
| `00_baseline/` | `frozen_baseline.json`, `bmw_manifest_frozen.json`, `pin_baseline.py` | Pin the frozen numbers/manifest that everything is reproduced against. |
| `01_reproduced/` | `bmw_scenario_engine.py`, `jlr_scenario_engine.py`, scenario JSON, date-basis + thin-denominator sensitivity | Deterministic scenario engines that reproduce the rulings 1:1 from the frozen intermediates. |
| `02_fixes/` | `bmw_reextract_ruleset.py` (+ `bmw_ruleset_reextracted.json`), `bmw_live_*` live contract-query verification, `jlr_true_contract_run.py`, `jlr_rate_provenance_flag.py`, answer-date-only DMYA rates | Re-extract the BMW ruleset directly from the contract (caches bypassed) to prove rules are contract-driven, not hardcoded; establish JLR rate provenance. |
| `03_comparison/` | `build_ledger.py`, `comparison_ledger.json`, LLM cost notes | Comparison ledger and cost accounting. |
| `04_oem_handoff/` | `METHODOLOGY_FIDELITY_NOTES.md`, `LIVE_CONTRACT_QUERY_VERIFICATION.md`, `MASTER_VERIFICATION_REPORT.md`, BMW/JLR driver dissections | Human-readable verification reports and fidelity disclosures for OEM handoff. |
| `evidence/` | DMTL override + DMYA rate-by-datebasis evidence | Supporting evidence for governed overrides. |

## Key methodology findings

- **BMW rules are independently derived** from the Kostenstand rate table and the
  contract-compiled `bmw_ruleset.json`; re-extraction reproduces every market variant
  (NAS/US/PR 60mo + mileage vs ROW 36mo) with contract attribution.
- **JLR contract method is ~91% manual-inherited** by construction (see
  `04_oem_handoff/METHODOLOGY_FIDELITY_NOTES.md`); only ~9% is genuinely rate-derived.
  This must be disclosed, not presented as independent corroboration.
- **Re-verification is exact 1:1** on frozen vs reproduced scenarios (to the cent).

## Exclusions

Large raw row-level outputs (`bmw_live_full_population_full_rows.csv` ~15.6 MB,
`jlr_contract_led_rebuild_rows.csv` ~42.3 MB) and compiled `__pycache__/*.pyc`
were intentionally omitted to keep this package review-focused and free of
row-level claim detail. A full raw re-run is available on request.
