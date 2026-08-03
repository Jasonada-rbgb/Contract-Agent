# BMW and JLR Contract-vs-Manual Claims Audit

Date prepared: 2026-07-20

## Executive Position

Both BMW and JLR have been recalculated end to end against the current contract-method approach, with separate handling for eligibility decisions and payment-percentage/rate calculation.

Current working totals:

| OEM | Rows | Manual payable | Contract-method payable | Contract minus manual | Position |
| --- | ---: | ---: | ---: | ---: | --- |
| BMW | 311,968 | EUR 42,803,546.35 | EUR 41,154,685.79 | EUR -1,648,860.56 | Contract lower, after 2025 missing-exclusion and `Ausgrenzen = x` corrections |
| JLR | 433,961 | EUR 10,122,393.31 | EUR 10,150,103.08 | EUR +27,709.77 | Contract slightly higher, after DMTL MY2023 resample override |
| Combined | 745,929 | EUR 52,925,939.67 | EUR 51,304,788.87 | EUR -1,621,150.80 | Contract lower overall |

Interpretation:

- BMW remains the material difference: contract-method output is about EUR 1.65m lower than the manual workbook method under the latest working assumptions.
- JLR is broadly aligned: contract-method output is about EUR 27.7k higher than manual, which is only around 0.27% of the JLR manual payable amount.
- The remaining differences are mostly not simple "pay / do not pay" issues. They are rate-basis, warranty-status, exception, and data-methodology questions.

## Payment Percentage Methodology

The audit made clear that payment percentage calculation should not sit inside the main Contract Agent as informal logic. It should be split into dedicated payment-factor agents that receive a contract eligibility decision plus normalized claim data and return the payable percentage with provenance.

Proposed subagents:

| Agent | Purpose | Typical OEM / use case | Example |
| --- | --- | --- | --- |
| Fixed Acceptance Agent | Applies agreed fixed percentages from contract/rate sheets by product group, year, market, and warranty type. | BMW | `Kostenstand` rates by shopping-cart number and warranty classification |
| Technical Factor Agent | Calculates payment factor from technical claim outcomes where the factor is based on actual technical acceptance results. | JLR | CAT1 / (CAT1 + CAT2 + CAT3), CAT4 excluded |
| Extrapolated Technical Factor Agent | Applies a technical factor from a sampled population to a wider population, with sampling/resampling controls and confidence flags. | JLR | DMYA or PFACC factors applied from STAR/sample outcomes to export claims |

The Contract Agent should answer:

- Is the claim in scope for the contract?
- Which warranty period/status applies?
- Is there a contract exception or side-letter/expert-review condition?
- What payment-factor agent should be called?

The payment-factor subagent should answer:

- Which rate source applies?
- Which percentage should be used?
- What data drove the rate?
- Is the rate fixed, technical, extrapolated, overridden, or low confidence?
- What evidence supports the rate?

Recommended output schema for payment-factor agents:

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

## BMW Audit

### Data Scope

- Source: 16 BMW EDC legacy workbooks.
- Rows: 311,968.
- Gross cost total: EUR 117,743,391.96.
- Contract/OEM profile: BMW / BMW.
- Primary claims sheets: selected `Einzelfallnachweis*` sheets.
- Rate source: `Kostenstand` sheets, mapped by year, workbook family, shopping-cart number, and warranty type.

### Core Method

1. Built a workbook manifest.
2. Normalized each selected BMW claim sheet to the Contract Agent claims schema.
3. Mapped canonical fields including country, VIN, repair date, warranty start/production date, mileage, part description, failure code, claim number, gross cost, and manual settlement/payment values.
4. Extracted payment rates from `Kostenstand`.
5. Applied contract timing and status logic:
   - standard GW period,
   - extended GW / goodwill / Spaetausfall period,
   - not payable outside applicable period,
   - expert-review bucket for legislative or contract-exception cases.
6. Used grouped review rather than row-by-row LLM calls.
7. Ran Opus 4.8 four-eyes review on material grouped deltas.

### BMW Raw Contract-Method Audit

Initial comparable result:

| Metric | Value |
| --- | ---: |
| Manual comparable payable | EUR 42,984,601.36 |
| Contract-method payable | EUR 40,499,031.91 |
| Contract minus manual | EUR -2,485,569.45 |

Initial bucket view:

| Bucket | Rows | Manual | Contract | Contract minus manual | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Aligned / no material delta | 267,034 | EUR 37,638,369.15 | EUR 37,638,369.15 | EUR 0.00 | No issue |
| Manual fallback insufficient info | 1,114 | EUR 178,606.90 | EUR 178,606.90 | EUR 0.00 | Manual result carried forward |
| Challengeable status-only delta | 15,891 | EUR 3,145,954.54 | EUR 1,607,208.19 | EUR -1,538,746.35 | Cleanest challenge set before later 2025 pattern audit |
| Manual reason delta needing expert mapping | 7,774 | EUR 2,021,670.78 | EUR 1,074,847.68 | EUR -946,823.10 | Visible manual notes exist |
| Expert review contract exception | 20,155 | EUR 1,630,624.93 | EUR 0.00 | EUR -1,630,624.93 | Legislative/goodwill exception handling not fully deterministic |

### BMW Key Findings

The largest BMW deltas were rate-classification differences, not simple denials.

Main issue:

- Manual workbook often used full standard GW rate.
- Contract method applied extended GW / Spaetausfall reduced rate where the claim age placed it outside the standard warranty period but inside the late-failure/goodwill window.

Top shopping-cart driver:

- `1351 einspritzpumpe regelungst gemischregler diesel b x`
- Main issue: manual standard GW rate 36% vs contract extended/Spaetausfall rate 18%.

### BMW 2025 Missing-Exclusion Pattern Audit

BMW indicated that 2025-folder files may not yet contain the same exclusion/reason annotations already present in older workbooks.

Method:

- Learned visible 2023/2024 reason patterns.
- Matched 2025 rows by shopping-cart/rate key, part description, failure code, country, and warranty-age bucket.

Results:

| Metric | Value |
| --- | ---: |
| 2025 candidate rows checked | 10,169 |
| 2025 rows matching historical reason patterns | 5,627 |
| Manual value on matched rows | EUR 1,629,214.58 |
| Contract value before adjustment | EUR 823,687.91 |
| Delta removed from clean challenge view | EUR -805,526.67 |

Impact:

| Scenario | Contract total | Contract minus manual |
| --- | ---: | ---: |
| Before 2025 pattern adjustment | EUR 40,499,031.91 | EUR -2,485,569.45 |
| Strong historical matches accepted | EUR 41,253,862.81 | EUR -1,730,738.55 |
| All historical matches accepted | EUR 41,304,558.58 | EUR -1,680,042.78 |

Residual high-confidence challenge after accepting all historical-pattern matches:

- EUR -733,219.68.

This is mainly the remaining Spaetausfall / `in GW` disagreement where the workbook status says `in GW`, but the contract method applies the age-derived extended/Spaetausfall rate.

### BMW `Ausgrenzen = x` Adjustment

The 2023 MA-100 workbook contained an `Ausgrenzen` column. Rows with `x` were treated as excluded from payment.

Impact if `Ausgrenzen = x` means zero payable:

| Metric | Value |
| --- | ---: |
| Rows matched | 2,555 |
| Manual value zeroed | EUR 181,055.01 |
| Contract value zeroed | EUR 149,872.79 |
| Corrected manual total | EUR 42,803,546.35 |
| Corrected contract total | EUR 41,154,685.79 |
| Corrected contract minus manual | EUR -1,648,860.56 |

This is the current BMW working total used in the executive position.

### BMW Four-Eyes / Contract-Agent Check

Opus 4.8 grouped review:

- Endpoint: `databricks-claude-opus-4-8`.
- Groups requested: 25.
- Groups reviewed: 25.
- Verdict: 25 / 25 `needs_bmw_expert`.

The four-eyes review did not show these as obvious implementation bugs, but it also did not confirm them as clean recoverable deltas. The key BMW expert question remains:

> Does the contract require age-derived Spaetausfall / extended-rate treatment, or does BMW's workbook `GW / Spaetausfall = in GW` classification contractually force the full standard GW rate?

Backend probe:

- Dynamic market/location logic worked.
- US claims used 60 months / 150,000 miles.
- Non-US/Canada/Puerto Rico claims used the 36-month base rule.
- Part/component-specific warranty evidence remained weak in the probe; sampled rows were classified as `general`.

### BMW Current View

BMW has a material remaining contract-lower position:

- Current working delta: EUR -1.65m contract lower than manual.
- Cleanest high-confidence challenge component after 2025 pattern cleanup: EUR -733k.
- Remaining exposure still needs BMW expert input, especially around Spaetausfall/in-GW rate mapping and legislative/contract-exception treatment.

## JLR Audit

### Data Scope

- Source folders: JLR export warranty workbooks for 2021, 2022, 2023, 2024, and 2025.
- Workbooks processed: 18.
- Rows loaded: 433,961.
- Gross cost total: EUR 68,646,127.79.
- Contract/OEM profile: JLR / JLR_Warranty.
- Markets:
  - UK = sample market.
  - Non-UK = export market.
  - NAS = USA, Canada, Mexico.
  - ROW = all non-UK export markets that are not NAS.

### Core Method

1. Read the lightweight workbook reports.
2. Normalized claims data into row-level contract-audit format.
3. Applied JLR market split:
   - UK sample market from `UKClaims`.
   - Export market from `ClaimsData`.
4. Used workbook/pipeline acceptance logic:
   - PFACC / Product Family Acceptance for export market rows.
   - DMYA for non-sample / older model-year rows.
   - UK CAT logic for sample market rows.
5. Used Databricks enrichment for:
   - VIN-to-production model year from `bci_rbs_prod.raw.dxq_jlr_iqm_production_vehicle_data`.
   - STAR technical outcome rates from `bci_rbs_prod.raw.dxq_jlr_stars`.
6. Applied AA price list duplicate fix:
   - Manual workbook `VLOOKUP` can take the first AAPRICELIST match.
   - Updated method uses the more recent applicable part mapping where available.
7. Applied safe model-year correction:
   - Corrected only where Databricks production model year provided usable evidence.
   - Preserved pre-2023 workbook-locked DMYA behavior.
8. Applied answer-date-only DMYA rate logic:
   - DMYA = CAT1 / (CAT1 + CAT2 + CAT3).
   - CAT4 excluded from denominator.
   - Based on STAR answered date, not STAR created date.
9. Applied DMTL MY2023 resample override:
   - Raw STAR output initially gave DMTL MY2023 = 100%.
   - This was caused by one pallet (`BBTRVY`) being 4 CAT1 / 4 denominator.
   - A second pallet (`BBVDHN`) was tested.
   - Business-confirmed overall DMTL MY2023 factor: 35%.

### JLR Final Result

| Metric | Value |
| --- | ---: |
| Manual paid | EUR 10,122,393.31 |
| Contract-method payable | EUR 10,150,103.08 |
| Contract minus manual | EUR +27,709.77 |

Market split:

| Market | Rows | Manual | Contract | Contract minus manual |
| --- | ---: | ---: | ---: | ---: |
| Export market | 408,385 | EUR 9,361,733.09 | EUR 9,389,442.85 | EUR +27,709.77 |
| UK sample market | 25,576 | EUR 760,660.23 | EUR 760,660.23 | EUR 0.00 |

The UK/sample market is aligned because the corrected method treats UK paid value as the `UKClaims` CAT4/DMYA payment result, rather than applying export PFACC style logic to CAT1/CAT2/CAT3 sample records.

### JLR Delta Drivers

| Driver | Direction | Impact | Cause |
| --- | ---: | ---: | --- |
| Databricks DMYA rates | Contract higher | EUR +35,743.27 | Updated STAR answer-date DMYA factors differ from workbook/manual locked rates |
| RB warranty exclusions | Contract lower | EUR -7,798.83 | Contract method rejects rows marked outside RB warranty |
| Not Bosch / not identified | Contract lower | EUR -234.68 | Contract method rejects non-Bosch or unidentified parts |
| Net | Contract higher | EUR +27,709.77 | DMYA uplift offsets contract rejection buckets |

Main positive DMYA product drivers:

| Product / MY | Rows | Manual | Contract | Contract minus manual | Rate movement |
| --- | ---: | ---: | ---: | ---: | --- |
| GS ECU MY2023 | 1,962 | EUR 51,711.17 | EUR 77,566.75 | EUR +25,855.58 | 26.67% to 40.00% |
| IPB MY2023 | 534 | EUR 88,002.45 | EUR 96,802.69 | EUR +8,800.24 | 31.82% to 35.00% |
| GS Oxygen Sensor [LSF] MY2023 | 448 | EUR 44,463.45 | EUR 52,580.54 | EUR +8,117.09 | 57.56% to 68.18% |
| Wiper Arm MY2023 | 392 | EUR 5,746.24 | EUR 10,671.58 | EUR +4,925.35 | 23.08% to 42.86% |
| Multi Purpose Camera MPC MY2023 | 388 | EUR 41,313.04 | EUR 44,883.30 | EUR +3,570.26 | 40.91% to 44.44% |
| Parking Sensor USS6 MY2023 | 1,361 | EUR 45,335.36 | EUR 48,527.99 | EUR +3,192.63 | 14.47% to 15.49% |
| DMTL MY2023 after override | 3,341 | EUR 244,526.30 | EUR 244,551.81 | EUR +25.51 | 34.99% to 35.00% |

### JLR Model-Year Adjustment

The model-year correction itself was small.

| Scenario | Contract payable | Manual minus contract |
| --- | ---: | ---: |
| Baseline ratefix, no MY adjustment | EUR 10,114,359.81 | EUR 8,033.51 manual higher |
| With safe MY adjustment only | EUR 10,113,915.72 | EUR 8,477.59 manual higher |

Impact:

- Contract payable reduced by EUR 444.09.
- 21 rows financially affected.
- Biggest effect was DMTL rows corrected from MY2023 to MY2024.

Model year still matters to DMYA calculation because the STAR-derived rates are grouped by product family and production model year. However, applying VIN production-MY correction to the claim population had only a EUR 444.09 financial impact.

### JLR Resampling Notes

DMTL:

- Initial raw Databricks rate for DMTL MY2023 was 100%.
- Cause: `BBTRVY` pallet contained 4 CAT1 and no CAT2/CAT3 denominator rows.
- New information confirmed a second pallet (`BBVDHN`) was tested.
- Business-confirmed final rate: 35%.
- Applied override to 3,341 claim rows.
- Contract payable reduced by about EUR 454.2k compared with the raw 100% STAR rate.

NGI:

- There is a similar business note that NGI had a resampling issue in the opposite direction.
- No NGI MY2023+ rows currently use `dmya_databricks` in the final audited output.
- No NGI override was applied because the exact NGI product family/rate/pallet evidence has not yet been provided.

### JLR Current View

JLR is effectively aligned with manual after the DMTL correction.

- Current net difference: EUR +27.7k contract higher.
- Main remaining positive delta is DMYA methodology, not a hard contract-rule disagreement.
- Main direct contract-lower dispute is only about EUR 8.0k from RB warranty and not-Bosch/not-identified exclusions.

## What Is Ruled By Contract vs What Is Disputable

### Ruled By Contract / Deterministic

These are the strongest outputs because they are direct applications of the contract or workbook-defined rate tables:

- BMW fixed percentage rates from `Kostenstand`.
- BMW warranty timing classification, subject to the unresolved `in GW` vs Spaetausfall interpretation.
- BMW `Ausgrenzen = x` exclusion if confirmed as zero payable.
- JLR UK CAT treatment where final CAT rating directly defines outcome.
- JLR RB warranty exclusion.
- JLR not-Bosch / not-identified rejection.
- JLR OTP / side-letter rows excluded from contract delta.

### Disputable / Expert Review

These are not pure code defects; they require business or expert confirmation:

- BMW Spaetausfall / `GW in GW` mapping:
  - Does workbook `in GW` force standard rate?
  - Or should contract age-derived Spaetausfall/extended rate control?
- BMW legislative/government exceptions:
  - Especially emissions/safety or sovereign-rule claims.
  - Contract text supports exception logic, but exact applicability and rate often require expert confirmation.
- BMW 2025 missing exclusion patterns:
  - Pattern match is evidence-based, but final acceptance depends on BMW confirming that 2025 should inherit prior-year annotations.
- JLR DMYA technical factors:
  - STAR answer-date method is mechanically sound, but small denominators and resampling events need governance.
- JLR DMTL override:
  - Applied because business supplied a corrected 35% rate.
  - Should be stored as an override with pallet evidence.
- JLR NGI:
  - Not applied yet.
  - Needs exact product/rate/pallet details before any financial adjustment.

## Recommended Agent Architecture

### 1. Contract Eligibility Agent

Responsible for contract interpretation only.

Inputs:

- OEM, contract ID.
- Normalized claim row.
- Retrieved contract context.
- Market, warranty start, repair date, mileage, part, failure mode.

Outputs:

- `eligible`, `not_payable`, `requires_review`, or `insufficient_info`.
- Warranty status: standard, extended, late failure, legislative exception, side letter, out of scope.
- Contract references.
- Confidence and warnings.
- Routing decision to payment-factor agent.

### 2. Fixed Acceptance Agent

Responsible for fixed agreed percentages.

Best fit:

- BMW.
- Any OEM where product groups have pre-agreed rates by year, basket, warranty type, or commercial table.

Inputs:

- Contract eligibility decision.
- Product/shopping-cart key.
- Claim year/workbook family.
- Warranty type: standard, extended, Spaetausfall, not payable.
- Rate table extract, e.g. BMW `Kostenstand`.

Outputs:

- Fixed payable percentage.
- Rate source row.
- Warning if no rate match.

### 3. Technical Factor Agent

Responsible for actual technical acceptance rates.

Best fit:

- JLR STAR outcome-derived factors.
- Cases where payment factor is based on technical outcome ratios.

Inputs:

- Product family / SQW.
- Model year.
- Technical decisions: CAT1, CAT2, CAT3, CAT4.
- Date basis, e.g. STAR answered date.

Outputs:

- Technical factor.
- Numerator/denominator.
- Excluded categories.
- Minimum-denominator confidence warning.

Example:

```text
DMYA = CAT1 / (CAT1 + CAT2 + CAT3)
CAT4 excluded
```

### 4. Extrapolated Technical Factor Agent

Responsible for taking a sampled or technical factor and applying it to a wider population.

Best fit:

- JLR DMYA / PFACC where sampled STAR outcomes determine payment factor for export claims.
- Cases with resampling, locked annual factors, or product-family extrapolation.

Inputs:

- Technical factor output.
- Claim population to receive the factor.
- Locking rule by year/quarter/model year.
- Resampling or override evidence.

Outputs:

- Applied factor.
- Applied population.
- Financial impact.
- Extrapolation confidence.
- Governance flags:
  - denominator too small,
  - single-pallet dominated,
  - second pallet exists,
  - manual/business override exists,
  - rate differs materially from workbook.

### 5. Payment Orchestrator

The Contract Agent should not perform all percentage calculations itself. It should orchestrate:

```text
Normalized claim
  -> Contract Eligibility Agent
  -> Payment Factor Router
      -> Fixed Acceptance Agent
      -> Technical Factor Agent
      -> Extrapolated Technical Factor Agent
  -> Final payable amount
  -> Row-level audit evidence
```

Final row output should include:

- manual payable,
- contract payable,
- gross cost,
- applied factor,
- factor agent used,
- rate source,
- eligibility decision,
- contract references,
- payment-factor references,
- confidence,
- warnings,
- delta reason.

## Evidence / Artifact Paths

BMW:

- `output/bmw_edc_claims_eval_verified_20260701/final_contract_audit/final_contract_audit_summary.json`
- `output/bmw_edc_claims_eval_verified_20260701/final_contract_audit/MANAGEMENT_SUMMARY.md`
- `output/bmw_edc_claims_eval_verified_20260701/final_contract_audit/2025_MISSING_EXCLUSION_PATTERN_AUDIT.md`
- `output/bmw_edc_claims_eval_verified_20260701/final_contract_audit/ausgrenzen_x_corrected_totals.json`
- `output/bmw_edc_claims_eval_verified_20260701/final_contract_audit/SPATAUSFALL_CONTRACT_RULE_DECISION.md`
- `output/bmw_edc_claims_eval_verified_20260701/final_contract_audit/CONTRACT_AGENT_FINAL_PROBE.md`

JLR:

- `output/jlr_contract_audit_full_20260713_audited_dmya_resample_override/jlr_final_summary.json`
- `output/jlr_contract_audit_full_20260713_audited_dmya_resample_override/audited_recalculation_checks.json`
- `output/jlr_contract_audit_full_20260713_audited_dmya_resample_override/audited_delta_by_reason.csv`
- `output/jlr_contract_audit_full_20260713_audited_dmya_resample_override/audited_databricks_dmya_by_product.csv`
- `output/jlr_contract_audit_full_20260710_databricks_star_answer_enrichment/production_model_year_by_vin.csv`
- `output/jlr_contract_audit_full_20260710_databricks_star_answer_enrichment/dmya_rates_answer_only_hybrid_from_2023.csv`

## Mercedes-Benz GALA Compile-Once Design

Mercedes-Benz is represented as two linked evidence sources: the main MBC
contract decides standard non-GALA eligibility, while signed GALA agreements
are compiled once into a deterministic, per-family quantity-acceptance matrix.

The matrix uses a strict family-first join, a supplier-plus-part fallback, and
agreement-specific temporal gates. A valid Quote sets accepted quantity:

```text
accepted quantity = replaced quantity apportioned × Quote%
```

It does not establish a cost base. Any calculated cost is reference-only and
must not be reported as a settlement or saving; SRS remains the financial
system of record.

GALA no-match, temporal-gate failure, and undetermined Quotes deliberately
return to main-contract handling or review. This avoids manufacturing a rate
from a broad supplier match. Runtime precedence is:

```text
signed GALA matrix -> approved expiring learned rule -> grouped main-contract review
```

The local Luna execution is pending workstation Codex connectivity. No MBC
cost-saving result is published by this package. See
`mbc_gala_methodology.md` for source ownership and validation details.

## Open Items

BMW:

- Confirm whether `Ausgrenzen = x` always means excluded / zero payable.
- Confirm whether workbook `GW / Spaetausfall = in GW` is contractually binding for rate selection or only a manual settlement status.
- Confirm legislative/government exception applicability and rate treatment.
- Confirm whether all 2025 missing-exclusion pattern matches should inherit prior-year treatment.

JLR:

- Confirm NGI resample details: product family, model year, pallet IDs, old rate, corrected rate, and whether it affects the current claim population.
- Governance rule needed for small STAR denominators before accepting recalculated DMYA rates.
- Store DMTL 35% as a formal override with evidence (`BBTRVY`, `BBVDHN`) rather than a manual one-off.

Agent build:

- Implement payment-factor subagents as separate callable units.
- Persist rate-source evidence for every monetary output.
- Add minimum-denominator and resampling flags for technical/extrapolated factors.
- Keep fixed contract rates, technical factors, and business overrides separate in the data model.
