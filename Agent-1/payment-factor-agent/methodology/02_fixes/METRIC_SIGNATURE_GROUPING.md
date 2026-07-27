# Metric-Signature Grouping — implemented + validated

Date: 2026-07-20
File changed: agent_server/claims_batch.py (`_claim_group_key`, `_market_class`,
`_mileage_band`, `_age_months_band`, `_component_class`, signature-representative mode).

## What changed (matches the original intended method)

OLD group key: `ambiguity_reason | country | part_description[:40]`
  -> fragmented by free-text part; small groups; per-row LLM reasoning.

NEW group key: `ambiguity_reason | market_class | age_band | mileage_band | component_class`
  - market_class: NAS / DE / ROW:<cc>
  - age_band: age_le_24m / 36m / 60m / 96m / 120m (from MIS or warranty_start->repair)
  - mileage_band: mi_le_30000 / 60000 / 100000 / 150000 / 160000 / 200000
  - component_class: comp_hv_battery / comp_wear / comp_general

Claims sharing this signature get the SAME warranty eligibility decision, so one
LLM decision covers the whole group. Shopping-cart/Warenkorb is deliberately
EXCLUDED from the eligibility key (it drives the PAYMENT factor, not in/out-of-
warranty) — including it fragmented groups.

## Compression achieved (BMW ambiguous population)

- 23,665 ambiguous claims -> **553 signature groups** (avg 42.8 claims/group).
- Top groups: DE|age<=60m|mi<=100k|general = 2,182 claims; DE|<=60m|<=60k = 1,769; GB|<=60m|<=60k = 1,125.

## Signature-representative mode (CLAIMS_SIGNATURE_REPRESENTATIVE=true)

One LLM call per signature (evaluate a representative, apply verdict to all members).
- Full ambiguous population would need ~553 LLM calls total (vs 23,665 per-row).

### Live validation (120-row diverse sample)
- 120 claims decided with **53 LLM calls** (one per signature); 67 calls avoided.
- Agreement with frozen: 105/120 = 87.5%.

## Drift finding (reproducible, systematic — NOT noise)

All 15 drift rows are the SAME issue: live applies the **60-month** window where
frozen used **36 months**. Every drift is frozen out_of_warranty -> live in_warranty,
citing "within 60 months" (incl. Puerto Rico 60mo/150k rule R004).

-> This is a market->rule mapping question (60mo US/PR/NAS vs 36mo ROW), exactly
   the dynamic-market weakness flagged in the original plan. It is deterministic,
   not judgement -> BMW expert must confirm which markets get 60 vs 36 months, and
   the bmw_ruleset.json market matcher (R001/R002/R004/R005) should be hardened so
   the deterministic pre-check resolves these instead of the LLM guessing.

## Net effect
- Token cost: massively reduced (553 calls for the whole ambiguous set vs tens of
  thousands per-row).
- Surfaced a real, systematic eligibility drift the smaller grouping had masked.
