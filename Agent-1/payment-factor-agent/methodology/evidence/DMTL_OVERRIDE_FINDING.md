# DMTL MY2023 Override — Live STAR Evidence Finding

Date: 2026-07-20
Source: `bci_rbs_prod.raw.dxq_jlr_stars` (live query via `edocument` profile, warehouse `f9f9ba24a8e2d807`)

## What the frozen baseline assumed

- Raw STAR rate for DMTL MY2023 = 100%, caused by pallet `BBTRVY` (4 CAT1 / 4 denominator).
- A second pallet `BBVDHN` was tested.
- Business-confirmed final rate: **35%**, applied to 3,341 claim rows.
- Financial impact vs raw 100%: contract payable reduced ~EUR 454.2k.

## What the live STAR data actually shows

| Pallet | CAT1 | CAT2 | CAT3 | CAT4 | Denominator (1+2+3) | Pallet rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BBTRVY | 4 | 0 | 0 | 0 | 4 | 100.00% |
| BBVDHN | 3 | 1 | 10 | 2 | 14 | 21.43% |
| BBVPTZ | 0 | 0 | 0 | 23 | 0 | (excluded, all CAT4) |
| **Pooled** | **7** | **1** | **10** | **25** | **18** | **38.89%** |

## The finding (SHAKEY — must go to JLR expert)

The **35% business override is not reproducible from the STAR pallet math**:

- Pooled DMYA across all three MY2023 pallets = **38.89%** (7 / 18).
- BBVDHN-only = **21.43%** (3 / 14).
- BBTRVY-only = 100% (4 / 4) — the acknowledged unrepresentative pallet.
- Applied override = **35.00%** — sits between BBVDHN-only and pooled, matches none.

There is also a **third pallet, BBVPTZ (23 CAT4)**, not mentioned in the original resample narrative. It does not change the DMYA rate (CAT4 excluded) but its existence shows the original two-pallet story was incomplete.

## Recommendation

1. The 35% is a **business-negotiated figure**, not a direct STAR computation. Store it as an explicit `manual_override` with this evidence attached, confidence = `expert_review`.
2. For the re-verification scenarios, compute DMTL MY2023 three ways so JLR can choose:
   - `dmtl_pooled_star` = 38.89%
   - `dmtl_bbvdhn_only` = 21.43%
   - `dmtl_business_override` = 35.00% (frozen baseline)
3. Do not present 35% as STAR-derived. Present it as negotiated, pending JLR expert confirmation.
