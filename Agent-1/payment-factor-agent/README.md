# Payment Factor Agent Technical Review Package

This folder contains the technical review material for separating payment percentage calculation from the main Warranty Contract Agent.

The key point for review: the Contract Agent should determine contract eligibility and route the claim to a payment-factor capability. The payment-factor agents should calculate the payable percentage using contract tables, technical sample outcomes, extrapolation logic, and approved business overrides.

## Proposed Agent Split

| Agent | Responsibility | Current evidence in this package |
| --- | --- | --- |
| Fixed Acceptance Agent | Applies fixed agreed rates by product group, warranty type, year, and market. | BMW `Kostenstand`-based audit outputs and BMW dashboard extraction script |
| Technical Factor Agent | Calculates technical acceptance factors from inspected outcomes. | JLR CAT1 / (CAT1 + CAT2 + CAT3) DMYA logic and STAR enrichment script |
| Extrapolated Technical Factor Agent | Applies a technical factor to a broader claim population with governance checks. | JLR DMYA/PFACC application logic and resampling evidence |

## Current Code Status

This is not yet a finished production subagent implementation. The current logic exists as audit scripts and dashboard extraction scripts:

- `scripts/jlr_full_contract_audit.py` contains the clearest current payment-factor routing implementation.
- `scripts/jlr_databricks_enrichment.py` contains Databricks enrichment logic for STAR technical rates and VIN production model year.
- `scripts/bmw_dashboard_refresh_extract.py` contains BMW fixed-rate audit normalization and final adjusted payable output for dashboard use.
- `scripts/bmw_jlr_dashboard_build.py` combines BMW/JLR dashboard-ready views.

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

- `docs/full.md`: consolidated BMW/JLR audit context and proposed payment-factor architecture.
- `scripts/`: current audit and dashboard scripts that contain the prototype logic.
- `evidence/bmw/`: aggregate BMW audit summaries and decision notes.
- `evidence/jlr/`: aggregate JLR audit summaries, DMYA breakdowns, PFACC/DMYA rate-source extracts, and resampling check.
- `rules/jlr_claims_rules.md`: local JLR data handling rules used during the audit.

## Files Intentionally Excluded

Large row-level claim datasets were not copied into this review folder. They include VINs, claim numbers, and high-volume claim detail, and are not needed for the technical review of the payment-factor architecture.

Excluded examples:

- BMW `final_contract_audit_row_level.csv`
- JLR `jlr_contract_vs_manual_row_level.csv`
- JLR `jlr_normalized_claims.csv`
- 2025 BMW pattern candidate row-level CSVs

If row-level examples are needed later, create a small redacted sample specifically for review.

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
