# JLR Phase 1 Reproduction + Sensitivity — Summary

Date: 2026-07-20
Method: deterministic replay from frozen normalized row-level (433,961 rows) + live STAR queries for evidence and date-basis sensitivity.

## Reproduction result

| Scenario | Contract in-scope EUR | Contract − Manual EUR |
| --- | ---: | ---: |
| frozen_baseline | 10,150,103.08 | +27,709.77 |
| reproduced_current_code | 10,150,103.08 | **+27,709.77** (exact match) |
| dmtl_override_only | 10,150,103.08 | +27,709.77 |
| denominator_floor_only | 10,154,679.74 | +32,286.42 |
| dmtl_override_plus_floor (default final) | 10,154,705.25 | **+32,311.94** |

**JLR reproduces exactly.** The +27,709.77 headline is confirmed from source.

## DMTL override impact (validated)

- Raw-100% STAR counterfactual contract payable: EUR 10,604,270.74
- With 35% override (frozen): EUR 10,150,103.08
- Override removed vs raw 100%: **−EUR 454,167.66** (matches plan "~454.2k").

## DMTL live STAR evidence (NEW — see evidence/DMTL_OVERRIDE_FINDING.md)

Pallet-level from `dxq_jlr_stars`:
- BBTRVY: 4 CAT1 / 4 = 100%
- BBVDHN: 3 CAT1 / 14 = 21.43%
- BBVPTZ: 23 CAT4 (excluded) — third pallet not in original narrative
- Pooled: 7 CAT1 / 18 = **38.89%**

The applied **35% is negotiated, not reproducible from STAR math** (pooled=38.89%, BBVDHN-only=21.43%). Must be labelled `manual_override`, confidence `expert_review`.

## Date-basis sensitivity (like-for-like, databricks population 22,158 rows, raw STAR rates)

| Basis | Contract payable on population | vs answer_only |
| --- | ---: | ---: |
| answer_only (audited choice) | 1,626,732.66 | — |
| both_dates | 1,634,270.71 | +7,538.06 |
| created_only | 1,668,100.20 | +41,367.54 |

Basis choice swings payable by up to **EUR 41,368** — material vs the +27.7k headline. The audited answer_only basis is the **lowest** (most conservative) of the three.

## Thin-denominator exposure (<10 STAR samples)

- 7,383 of 22,158 databricks rows (33%) use thin rates.
- Contract payable resting on thin rates: **EUR 306,554**.
- Contract−manual net on thin rows: −EUR 4,576.66 (= the denominator-floor swing).

## Open item
- NGI: no adjustment applied; reported as known possible resampling issue pending pallet/rate evidence.
