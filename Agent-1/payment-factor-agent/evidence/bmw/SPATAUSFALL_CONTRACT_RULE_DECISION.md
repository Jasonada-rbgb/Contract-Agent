# Spatausfall / `in GW` Contract-Method Decision

## Decision

For the current Contract-method output, do not treat the workbook field `GW / Spaetausfall = in GW` as binding for the supplier rate bucket when the contract age logic places the claim in the late-failure / extended warranty period.

Apply the Contract-method rule:

- Normal warranty period: standard GW rate
- Contract late-failure / extended period: Spaetausfall / extended rate
- Outside the applicable contract period: not payable unless a specific contract exception applies

This means rows marked `in GW` in the workbook can still be classified as `extended_gw` / Spaetausfall by the Contract method if the repair timing is outside the standard warranty period but inside the contract late-failure / goodwill window.

## Reason

The workbook status field appears to be a manual settlement classification. For this audit, the Contract method should apply the contract timing rule independently unless BMW expert review confirms that the workbook `in GW` label is contractually binding for rate selection.

## Impact In Contract-vs-Manual Delta

After removing the 2025 missing-exclusion pattern matches, the residual high-confidence Contract-method delta is:

- EUR -733,219.68

The main contributor is MD rows where:

- workbook says `GW / Spaetausfall = in GW`
- manual applies standard GW rate
- Contract method applies extended / Spaetausfall rate

This amount is included in the Contract-vs-manual delta because it is a clear methodological difference between the manual workbook settlement and the Contract method.

Main non-2025 contributors:

- 2024 MD: EUR -245,974.45
- 2023 MD: EUR -233,819.86

Main 2025 contributor after missing-exclusion cleanup:

- 2025 MD: EUR -273,447.43

Expert question:

Does the contract require age-derived Spaetausfall / extended rate treatment for these claims, or does BMW's `GW / Spaetausfall = in GW` workbook classification contractually force the standard GW rate?
