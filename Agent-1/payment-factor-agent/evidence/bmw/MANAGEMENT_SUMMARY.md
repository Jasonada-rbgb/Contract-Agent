# BMW EDC Final Contract-Method Audit Summary

## Headline

- Total rows audited: 311,968
- Contract-method payable value: EUR 40,499,031.91
- Manual comparable payable value: EUR 42,984,601.36
- Net contract-vs-manual delta: EUR -2,485,569.45

This means the current Contract method pays EUR 2.49m less than the manual workbook method on comparable rows.
Comparable rows include normal included rows plus the agreed insufficient-info manual fallback. They exclude the separate expert-review contract-exception bucket shown below.

## Confidence Buckets

| Bucket | Rows | Manual EUR | Contract EUR | Delta EUR | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Aligned / no material delta | 267,034 | 37,638,369.15 | 37,638,369.15 | 0.00 | No management issue. |
| Manual fallback insufficient info | 1,114 | 178,606.90 | 178,606.90 | 0.00 | Manual value carried forward by policy. |
| Challengeable status-only delta | 15,891 | 3,145,954.54 | 1,607,208.19 | -1,538,746.35 | Cleanest challenge set, but Opus 4.8 still asks expert to confirm rate-type mapping. |
| Manual reason delta needing expert mapping | 7,774 | 2,021,670.78 | 1,074,847.68 | -946,823.10 | Visible notes exist, mainly deadline/GW text; do not challenge as clean leakage without BMW expert confirmation. |
| Expert review contract exception | 20,155 | 1,630,624.93 | 0.00 | -1,630,624.93 | Legislative/goodwill exception handling remains outside deterministic contract scope until expert confirms clause and rate. |

## Main Drivers

The largest comparable deltas are not simple "do not pay" cases. They are mostly rate classification disputes, especially:

- Standard GW rate used manually vs extended GW rate used by the Contract method in the 37-60 month window.
- Late failure / "Spaetausfall in GW" status text without an explicit visible mapping to the rate table.
- Legal/regulatory rows where the Contract method intentionally moved the row to expert review instead of guessing a payable rate.

Top shopping-cart driver:

- `1351 einspritzpumpe regelungst gemischregler diesel b x`
  - Manual-reason delta: EUR -402,519.15
  - Status-only delta: EUR -321,323.16
  - Main issue: manual standard GW rate 36% vs Contract extended GW rate 18%.

## Opus 4.8 Four-Eyes Review

- Endpoint: `databricks-claude-opus-4-8`
- Groups reviewed: 25 highest-materiality groups
- Result: 25 / 25 returned `needs_bmw_expert`

The four-eyes review did not identify the large deltas as obvious implementation bugs. It also did not confirm them as cleanly contract-supported. The repeated expert question is whether late-failure / in-GW status in months 37-60 should use the full standard GW rate or the lower extended GW rate for each affected shopping-cart group.

## Management Position

Do not present the full EUR 2.49m comparable delta as clean recoverable leakage yet.

Recommended framing before the 2025 missing-exclusion pattern audit:

- EUR 1.54m: strongest challenge set, but still needs expert confirmation on standard-vs-extended GW rate mapping.
- EUR 0.95m: visible manual reason text exists, so needs expert mapping before challenge.
- EUR 1.63m: separate expert-review exception exposure, mainly legislative/goodwill rows; not included as clean Contract-method payable until confirmed.

## 2025 Missing-Exclusion Update

BMW indicated that 2025-folder workbooks may not yet contain the same reason / exclusion annotations that exist in older files. A historical-pattern audit found EUR -805,526.67 of the status-only challenge delta on 2025 rows matching prior-year reason patterns.

Revised high-confidence challenge view:

- Original status-only challenge: EUR -1,538,746.35
- Remove strong historical 2025 matches only: EUR -783,915.45
- Remove all historical 2025 matches: EUR -733,219.68

If those matched 2025 rows are accepted as payable on the prior-year/manual basis, the comparable Contract-method total moves from EUR 40,499,031.91 to:

- EUR 41,253,862.81 using strong matches only
- EUR 41,304,558.58 using all historical matches

Use `2025_MISSING_EXCLUSION_PATTERN_AUDIT.md` and `2025_missing_exclusion_pattern_candidates.csv` for the BMW expert review list.

## Spatausfall / `in GW` Rule Position

For the current Contract-method output, the workbook field `GW / Spaetausfall = in GW` is not treated as binding where the contract timing rule places the claim into the late-failure / extended period.

Current position to take to BMW expert:

- Contract method applies age-derived Spaetausfall / extended rate treatment.
- Manual workbook `in GW` status is recorded as a potential disagreement, not as an automatic override.
- The residual high-confidence delta after 2025 missing-exclusion cleanup remains EUR -733,219.68 and is included in the Contract-vs-manual delta as a clear methodology difference.

See `SPATAUSFALL_CONTRACT_RULE_DECISION.md`.
