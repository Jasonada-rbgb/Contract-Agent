# Payment Factor Agent Technical Review Package

This folder contains the technical review material for separating payment percentage calculation from the main Warranty Contract Agent.

The key point for review: the Contract Agent should determine contract eligibility and route the claim to a payment-factor capability. The payment-factor agents should calculate the payable percentage using contract tables, technical sample outcomes, extrapolation logic, and approved business overrides.

## Proposed Agent Split

| Agent | Responsibility | Current logic in this package |
| --- | --- | --- |
| Fixed Acceptance Agent | Applies fixed agreed rates by product group, warranty type, year, and market. | BMW `Kostenstand`-based contractual bucketing (`scripts/bmw_contractual_buckets.py`) |
| GALA Quote Acceptance Agent | Applies a signed agreement Quote to replaced quantity after deterministic agreement routing. | Mercedes-Benz GALA compiled matrix; true cost remains in SRS. |
| Technical Factor Agent | Calculates technical acceptance factors from inspected outcomes. | JLR CAT1 / (CAT1 + CAT2 + CAT3) DMYA logic and STAR enrichment (`scripts/jlr_databricks_enrichment.py`, `scripts/jlr_star_dmya_answer_date_only.py`) |
| Extrapolated Technical Factor Agent | Applies a technical factor to a broader claim population with governance checks. | JLR DMYA/PFACC application + denominator governance (`scripts/denominator_governance.py`) |

## Current Code Status

This is not yet a finished production subagent implementation. The original
logic remains prototype/audit code, now alongside an additive portable core:

- `payment_factor_core/` - profile-driven routing, deterministic agreement-matrix evaluation, learned-rule cache contract and safe grouping. It does not contain OEM contract content.
- `profiles/` - MBC, BMW and JLR starter profiles. MBC is the first functional portable evaluator; BMW/JLR continue to use their validated legacy logic pending adapter migration.
- `docs/portable_core.md` - current migration boundary and host-integration contract.

- `scripts/payment_factor_agents.py` - payment-factor agent prototype.
- `docs/mbc_gala_methodology.md` - Mercedes-Benz main-contract/GALA routing, compile-once, grouping, and cache governance.
- `docs/contract_asset_pipeline.md` - reusable ingestion and compile-once method for large structured agreement sets.
- `methodology/01_reproduced/mbc_gala_scenario_engine.py` - portable deterministic GALA validation engine.
- `scripts/jlr_full_contract_audit.py` - clearest current payment-factor routing implementation.
- `scripts/jlr_contract_led_rebuild.py` - JLR contract-led rebuild logic.
- `scripts/jlr_databricks_enrichment.py` - Databricks enrichment for STAR technical rates and VIN production model year.
- `scripts/denominator_governance.py` - thin-sample / denominator governance.
- `methodology/` - rule-derivation engines (see `methodology/README.md`), including re-extracting the BMW ruleset directly from the contract to prove rules are contract-driven, not hardcoded.

## Important Limitation

The payment-factor "agents" cannot rely only on contract text.

They also need structured external sources:

- fixed rate sheets such as BMW `Kostenstand`,
- JLR workbook DMYA/PFACC tables,
- STAR technical outcomes,
- IQM production model year,
- workbook flags such as OTP, RB warranty status, exclusion bits,
- approved business overrides and resampling decisions.

For Mercedes-Benz, the main contract selects standard eligibility while signed
GALA agreements provide an additional deterministic quantity-acceptance source.
Claims not covered by a valid GALA rule return to the main-contract route; they
must not receive an inferred GALA Quote.

This is why the future design should treat payment factors as separate audited services/subagents with explicit source provenance.

## Contents

- `docs/full.md`: consolidated BMW/JLR context and proposed payment-factor architecture.
- `scripts/`: payment-factor agent prototype and audit/rebuild code.
- `methodology/`: rule-derivation code (scenario engines, ruleset re-extraction, provenance flagging). See `methodology/README.md`.
- `payment_factor_core/` and `profiles/`: portable core and declarative contract profiles. See `docs/portable_core.md`.
- `docs/contract_asset_pipeline.md`: source-neutral ingestion, compilation, validation and asset-publication methodology for large agreement sets.
- `provenance/bmw_ruleset.json`: frozen ruleset the rules compile from.
- `rules/`: payment-factor rules, overrides, and JLR data-handling rules used by the agent.
- `skills/`: CLI-side skills and subagents used to build the agent, with a `SKILLS_USED.md` log and Copilot-adaptation notes.

## Files Intentionally Excluded

This package is limited to how the agent is built and scaled. The following are deliberately not included: run outputs and aggregate summaries (`evidence/`, output `*.json`/`*.csv`), row-level claim datasets (VINs, claim numbers, high-volume detail), cost-difference and LLM cost analysis, OEM-handoff verification reports, ad-hoc profiling/validation helper scripts, dashboard-build scripts, and compiled `__pycache__/*.pyc`.

If outputs or redacted row-level samples are needed later, they are available on request.

## Suggested Build Direction

Create a reusable package with this flow:

```text
Normalized claim
  -> Contract Eligibility Agent
  -> Payment Factor Router
      -> Fixed Acceptance Agent
      -> GALA Quote Acceptance Agent (when signed agreement matches)
      -> Technical Factor Agent
      -> Extrapolated Technical Factor Agent
  -> Final payable amount with rate provenance
```

Minimum output contract for each factor agent:

```json
{
  "factor_type": "fixed_acceptance | technical_factor | extrapolated_technical_factor",
  "rate": 0.35,
  "rate_source": "Kostenstand | GALA_signed_matrix | PFACC | DMYA | STAR | side_letter | manual_override",
  "rate_basis": "standard_gw | extended_gw | quantity apportionment | CAT1/(CAT1+CAT2+CAT3)",
  "source_reference": "workbook/sheet/table/query/pallet/rate-row",
  "confidence": "high | medium | low | expert_review",
  "warnings": []
}
```
