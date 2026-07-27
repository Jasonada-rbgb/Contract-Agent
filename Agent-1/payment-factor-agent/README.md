# Payment Factor Agent Technical Review Package

This folder contains the technical review material for separating payment percentage calculation from the main Warranty Contract Agent.

The key point for review: the Contract Agent should determine contract eligibility and route the claim to a payment-factor capability. The payment-factor agents should calculate the payable percentage using contract tables, technical sample outcomes, extrapolation logic, and approved business overrides.

## Proposed Agent Split

| Agent | Responsibility | Current logic in this package |
| --- | --- | --- |
| Fixed Acceptance Agent | Applies fixed agreed rates by product group, warranty type, year, and market. | BMW `Kostenstand`-based contractual bucketing (`scripts/bmw_contractual_buckets.py`) |
| Technical Factor Agent | Calculates technical acceptance factors from inspected outcomes. | JLR CAT1 / (CAT1 + CAT2 + CAT3) DMYA logic and STAR enrichment (`scripts/jlr_databricks_enrichment.py`, `scripts/jlr_star_dmya_answer_date_only.py`) |
| Extrapolated Technical Factor Agent | Applies a technical factor to a broader claim population with governance checks. | JLR DMYA/PFACC application + denominator governance (`scripts/denominator_governance.py`) |

## Current Code Status

This is not yet a finished production subagent implementation. The current logic exists as prototype/audit code:

- `scripts/payment_factor_agents.py` - payment-factor agent prototype.
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

This is why the future design should treat payment factors as separate audited services/subagents with explicit source provenance.

## Contents

- `docs/full.md`: consolidated BMW/JLR context and proposed payment-factor architecture.
- `scripts/`: payment-factor agent prototype and audit/rebuild code.
- `methodology/`: rule-derivation code (scenario engines, ruleset re-extraction, provenance flagging). See `methodology/README.md`.
- `provenance/bmw_ruleset.json`: frozen ruleset the rules compile from.
- `rules/`: payment-factor rules, overrides, and JLR data-handling rules used by the agent.

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
      -> Technical Factor Agent
      -> Extrapolated Technical Factor Agent
  -> Final payable amount with rate provenance
```

Minimum output contract for each factor agent:

```json
{
  "factor_type": "fixed_acceptance | technical_factor | extrapolated_technical_factor",
  "rate": 0.35,
  "rate_source": "Kostenstand | PFACC | DMYA | STAR | side_letter | manual_override",
  "rate_basis": "standard_gw | extended_gw | spatausfall | CAT1/(CAT1+CAT2+CAT3)",
  "source_reference": "workbook/sheet/table/query/pallet/rate-row",
  "confidence": "high | medium | low | expert_review",
  "warnings": []
}
```
