# BMW / JLR Cost Value — End-to-End Re-Verification Report

Date: 2026-07-20
Compute: Databricks (`edocument` profile, warehouse `f9f9ba24a8e2d807`, proxy `rb-proxy-de.bosch.com:8080`) + deterministic local replay.
Method: reproduce frozen audit from source, apply governance fixes as isolated scenarios, quantify sensitivity, produce OEM handoff.

---

## 1. Headline verdict

Both OEM headline cost values **reproduce exactly** from source:

| OEM | Frozen | Reproduced | Match |
| --- | ---: | ---: | :---: |
| BMW comparable delta (contract − manual) | −2,485,569.45 | −2,485,569.45 | EXACT |
| BMW Ausgrenzen-corrected (working total) | −1,648,860.56 | −1,648,860.56 | EXACT |
| JLR (contract − manual, in-scope) | +27,709.77 | +27,709.77 | EXACT |
| Combined frozen delta | −1,621,150.80 | −1,621,150.80 | EXACT |

BMW eligibility engine is deterministic (frozen `bmw_ruleset.json`, 9 clause-cited timing rules) → **0 drift by construction** on the reproducibility run.

## 2. Scenario ledger

### JLR (contract − manual, EUR)
| Scenario | Value |
| --- | ---: |
| frozen_baseline | +27,709.77 |
| reproduced_current_code | +27,709.77 |
| dmtl_override_only | +27,709.77 |
| denominator_floor_only | +32,286.42 |
| **dmtl_override_plus_floor (FINAL)** | **+32,311.94** |

### BMW (contract − manual, EUR)
| Scenario | Value |
| --- | ---: |
| frozen_baseline_comparable | −2,485,569.45 |
| reproduced_current_code | −2,485,569.45 |
| **ausgrenzen_x_zeroed (FINAL working total)** | **−1,648,860.56** |
| residual after 2025-pattern (all) | −733,219.68 |

## 3. What changed under governance fixes

- **JLR final moves from +27.7k to +32.3k** (+4.6k) once thin (<10 denominator) STAR rates are floored to workbook fallback instead of applied silently. This is a legitimate methodology improvement, labelled as a new scenario — it does not overwrite the frozen result.
- **BMW unaffected by denominator floor** (fixed Kostenstand rates, not sampled factors).

## 4. Shakey items — NOW QUANTIFIED for OEM experts

### JLR
1. **DMTL MY2023 35% override is NOT reproducible from STAR math.** Live pallet data:
   - BBTRVY 4 CAT1/4 = 100% (the acknowledged unrepresentative pallet)
   - BBVDHN 3 CAT1/14 = 21.43% (retest)
   - BBVPTZ 23 CAT4 = excluded (third pallet, not in original narrative)
   - Pooled = 38.89%. Applied 35% matches none → **negotiated figure, confidence = expert_review**.
   - Override impact vs raw 100%: −454,167.66 (matches plan).
2. **Date basis is material.** Answer-only (audited) is the lowest of three bases; created-only would raise payable by up to **+41,368** on the databricks population. Confirm answer-date-only is the agreed JLR basis.
3. **Thin denominators:** 7,383 / 22,158 databricks rows (33%) rest on <10-sample STAR rates, carrying EUR 306,554 of contract payable. Now governed by the floor.
4. **NGI:** open item, **no adjustment applied**.

### BMW
1. **Spätausfall / `in GW`** rate mapping (R005 vs R006 boundary): the largest challenge component (−733k residual). Contract-method applies age-derived extended rate; workbook says `in GW`. Expert must confirm which controls.
2. **Legislative/government exceptions** (20,155 rows, −1.63m) zeroed by contract method → expert confirmation of clause + rate.
3. **`Ausgrenzen = x`** = zero payable — confirm always true (basis of the working total).
4. **2025 missing-exclusion pattern** — confirm 2025 should inherit prior-year annotations.
5. Opus 4.8 four-eyes returned **25/25 `needs_bmw_expert`** — no independently-confirmed BMW delta yet.

## 5. Deliverables produced (this run)

Fixes (in `payment-factor-agent/`):
- `rules/payment_factor_rules.json` — BMW clause-cited rules + JLR factor defs
- `rules/overrides.json` — formal DMTL override + NGI open item, with pallet evidence
- `scripts/jlr_star_dmya_answer_date_only.py` — reproducible answer-date-only query (validated live: reproduces GS ECU 0.40, DMTL 1.0-raw)
- `scripts/denominator_governance.py` — <10 floor (validated)
- `scripts/payment_factor_agents.py` — 3 callable subagents (validated, README schema)

Evidence (in `output/reverify_20260720/`):
- `00_baseline/frozen_baseline.json` + `bmw_manifest_*` (16/16 BMW + 18/18 JLR resolve)
- `evidence/dmtl_my2023_pallet_star_evidence.csv` + `DMTL_OVERRIDE_FINDING.md`
- `evidence/dmya_rate_by_datebasis_2023_2024.csv`
- `01_reproduced/` JLR + BMW scenario engines & summaries
- `03_comparison/comparison_ledger.json`

## 6. Recommendation for management vs experts
- **Management view:** frozen −1.65m (BMW) / +27.7k (JLR) vs recommended-final. JLR final +32.3k with governance.
- **Expert view:** isolated scenarios + the 5 BMW + 4 JLR open questions above, each with euro exposure.
