# Manifest

This package contains the **payment-factor agent code and rule artifacts** — how
the agent is built and how it can be scaled. Run outputs, aggregate evidence,
cost-difference analysis, and OEM-handoff reports are intentionally excluded.

## Documentation

- `README.md` - technical review guide for this package.
- `docs/full.md` - methodology narrative, open items, and payment-factor agent proposal / recommended architecture.

## Rules Artifacts

- `rules/payment_factor_rules.json` - formal payment-factor rules (BMW fixed-acceptance timing rules with clause provenance; JLR technical/extrapolated factors). Cites `provenance/bmw_ruleset.json`.
- `rules/overrides.json` - governed override table (e.g. OVR-JLR-DMTL-MY2023).
- `rules/jlr_claims_rules.md` - JLR data rules used by the agent.

## Provenance

- `provenance/bmw_ruleset.json` - frozen BMW ruleset the rules compile from (fingerprint `e71bec717be8a433`, compiled 2026-06-15 from `compiled_profile`). The exact source artifact `rules/payment_factor_rules.json` references.

## Agent Scripts (`scripts/`)

- `payment_factor_agents.py` - payment-factor agent prototype.
- `denominator_governance.py` - denominator / thin-sample governance logic.
- `jlr_full_contract_audit.py` - JLR workbook normalization, PFACC/DMYA routing, CAT logic, contract decision. Key functions: `rate_from_row`, `contract_decision`, `sample_market_decision`, `export_market_decision`, `extract_dmya_rates`, `extract_pfacc_rates`.
- `jlr_contract_led_rebuild.py` - JLR contract-led rebuild logic.
- `jlr_star_dmya_answer_date_only.py` - STAR-derived DMYA rate logic (answer-date-only basis).
- `jlr_databricks_enrichment.py` - Databricks enrichment for VIN production model year and STAR-derived DMYA rates.
- `bmw_contractual_buckets.py` - BMW contractual bucketing logic.
- `bmw_review_reconcile.py` - BMW review reconciliation logic.

## Rule-Derivation Code (`methodology/`)

Code that shows how the rules are derived and reproduced from the Contract Agent
(no output data or reports — see `methodology/README.md`):

- `00_baseline/pin_baseline.py` - reproducible baseline pinning.
- `01_reproduced/bmw_scenario_engine.py`, `jlr_scenario_engine.py` - deterministic scenario engines.
- `01_reproduced/jlr_datebasis_sensitivity.py`, `jlr_thin_denominator_exposure.py` - date-basis and thin-denominator logic.
- `02_fixes/bmw_reextract_ruleset.py` - re-extract the BMW ruleset from the contract (caches bypassed) to prove rules are contract-driven, not hardcoded.
- `02_fixes/bmw_live_contract_query_sample.py`, `bmw_live_full_population.py` - live contract-query verification drivers.
- `02_fixes/jlr_rate_provenance_flag.py` - `manual_inherited` vs `rate_derived` provenance logic.
- `02_fixes/jlr_true_contract_run.py` - independent contract-rate run (no manual inheritance).

## Skills & Subagents (`skills/`)

CLI-side skills and subagents used to build the agent (see `skills/SKILLS_USED.md`):

- `skills/warranty-agent/` - core domain skill (agent architecture, hybrid retrieval, claims pipeline, routing).
- `skills/databricks-pipeline/`, `python-patterns/`, `search-first/`, `security-review/`, `verification-loop/`, `continuous-learning/`, `dev-up/` - engineering/process skills applied during the build.
- `skills/subagents/` - `planner`, `backend-builder`, `reviewer`, `verifier` role definitions.
- `skills/SKILLS_USED.md` - which skills/subagents were used in which sessions and why, plus notes on adapting for GitHub Copilot.

## Exclusions

Deliberately not included: run outputs and aggregate summaries (`evidence/`, output `*.json`/`*.csv`), row-level claim files, cost-difference analysis and LLM cost estimates, OEM-handoff verification reports, ad-hoc profiling/validation helper scripts, dashboard-build scripts, and compiled `__pycache__/*.pyc`. This keeps the package focused on how the agent is built and scaled. Outputs and a full raw re-run are available on request.
