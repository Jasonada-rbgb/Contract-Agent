# BMW Eligibility Drift — Live Contract Query vs Frozen

Date: 2026-07-20
Sample: 60 rows from the Spaetausfall dispute population (challengeable_status_only_delta, standard->extended).
Config: evaluation_strategy=hybrid, CLAIMS_LLM_GROUP_SIZE=100, per-row fallback on, endpoint=databricks-claude-opus-4-8, temp 0.

## Result
- Agreement with frozen: 57 / 60 = 95.0%
- Endpoint calls avoided by hybrid grouping: 48 (12 LLM groups for 60 ambiguous rows — grouping dominated by country|part signature, not the size cap).

## The 3 drifted rows (live said in_warranty, frozen said out_of_warranty)

| Claim | Frozen | Live | Live reason |
| --- | --- | --- | --- |
| 373157536 | out_of_warranty | in_warranty | within 60 months + mileage ok [1][2][3] |
| 382570267 | out_of_warranty | in_warranty | Puerto Rico 60mo/150,000mi rule; ~36mo, 30,203mi |
| 381773992 | out_of_warranty | in_warranty | within 60 months + mileage ok [1][2][3] |

## Assessment against agreed thresholds

- Threshold: "any drift in high-confidence deterministic bucket = defect."
- These 3 rows flipped OUT->IN on the **60-month US/Puerto-Rico rule (R004)** vs the
  36-month base rule. This is the DYNAMIC MARKET logic the plan already flagged as weak
  ("sampled rows classified as general"; "part/component-specific evidence weak").
- Direction: live is MORE generous (pays more) than frozen on these 3.

### Classification: DEFECT SIGNAL, not benign ambiguity
The drift is not random LLM noise — it is a systematic market-rule application
difference (60mo vs 36mo). Either:
  (a) frozen wrongly applied 36 months to US/PR claims that qualify for 60 months, OR
  (b) live wrongly applies 60 months to non-US claims.
Both are deterministic rule questions, not judgement calls -> route to BMW expert +
harden the market->rule mapping in bmw_ruleset.json (R001/R002/R004/R005 boundaries).

## Cost/scale note
- 60 ambiguous rows -> 118.6s. The full 311,968-row run is mostly DETERMINISTIC
  (original run: ~all rows deterministic), so only the ambiguous remainder hits the LLM.
- Larger group size helps only within a single country|part signature; the real lever
  is the deterministic pre-check catching the bulk.
