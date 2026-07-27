# JLR Contract-Led Rebuild — Technical Factor Agent (DMYA/PFACC), no manual fallback

Date: 2026-07-20
Engine: payment_factor_agents.py (Technical Factor + Extrapolated Technical Factor) + overrides.json + denominator floor <10.

## Method (100% contract-led)
- phase == 1 (no-sample)  -> Technical Factor Agent: STAR DMYA rate.
- phase == 0 (sample)     -> Extrapolated Technical Factor Agent: PFACC/sample rate.
- override table (DMTL 0.35 business-confirmed) applied where present.
- denominator < 10 -> requires_review (NOT applied silently, NOT manual fallback).
- no independent rate / no phase -> requires_review (NOT manual fallback).

## Result (export in-scope, 356,105 rows)

| Population | Rows | Manual EUR | Contract-led EUR | Contract-led − Manual |
| --- | ---: | ---: | ---: | ---: |
| Rated (real contract rate) | 272,506 | 8,570,414.63 | 8,958,936.09 | **+388,521.46** |
| Requires review (no defensible rate) | 83,599 | 791,318.45 | withheld | — |

Action breakdown: contract_rate 268,847 | override 3,659 | requires_review 79,528 | requires_review_thin 4,071.

## Contrast with the frozen (manual-inherited) method

| Method | Delta vs manual (rated rows) | Nature |
| --- | ---: | --- |
| Frozen "contract" method | +32,378.66 | 91% manual-inherited via fallback |
| **Contract-led rebuild** | **+388,521.46** | genuine DMYA/PFACC rates, no fallback |

The genuine contract-led figure is **+EUR 388.5k contract-higher** on rated rows —
an order of magnitude larger than the frozen +27.7k, and in the SAME direction
(contract pays more than manual once real technical factors are applied instead of
copying the manual rate).

## Interpretation for JLR expert

1. When the DMYA/PFACC technical factors are applied directly (not the manual rate),
   the contract would pay JLR ~EUR 388.5k MORE than the workbook did on rated rows.
   This means the manual workbook was UNDER-paying relative to the technical factors
   on the net, once the manual-copy shortcut is removed.
2. 83,599 rows (EUR 791k manual value) have no defensible independent rate and are
   withheld pending: a real STAR/PFACC rate, a workbook-locked fallback decision, or
   expert review. The final full-population number depends on how these resolve.
3. This is the figure to take forward as the CONTRACT-LED result. The frozen +27.7k
   should be retired as a contract finding (it is a manual replay).

## Deliverables
- payment-factor-agent/scripts/jlr_contract_led_rebuild.py
- output/reverify_20260720/02_fixes/jlr_contract_led_rebuild.json
- output/reverify_20260720/02_fixes/jlr_contract_led_rebuild_rows.csv (per-row audit)
