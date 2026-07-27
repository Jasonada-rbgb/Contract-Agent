# BMW EUR 2.5m Delta — What It Actually Is

Date: 2026-07-20

## Question asked
"For BMW with a EUR 2.5m overpayment, are we saying this is correct?"

## Answer: it is NOT a confirmed overpayment. It is ONE unresolved contract-interpretation choice worth EUR 2.5m.

## The dissection

The comparable delta (contract - manual) = **-EUR 2,485,569.45**.

Broken down by warranty-type reclassification:

| Reclassification | Delta EUR | Rows |
| --- | ---: | ---: |
| **standard_gw -> extended_gw** | **-2,572,572.80** | **22,586** |
| standard_gw -> not_payable | -20,508.76 | 69 |
| not_paid -> extended_gw | +66,436.57 | 807 |
| not_paid -> standard_gw | +40,013.18 | 195 |
| late_failure -> standard_gw | +1,516.55 | 5 |
| others | small | 8 |
| **Net** | **-2,485,569.45** | |

**103.5% of the delta is a single pattern: standard_gw -> extended_gw.**

On those 22,586 rows:
- Manual applied standard GW rate (0.50 or 0.36).
- Contract applied extended / Spaetausfall rate (0.25 or 0.18) - roughly HALF.
- Kostenstand rate matched by exact_key (genuine contract rate, NOT manual-inherited).

## Why it is NOT a bug and NOT manual-inheritance

- These rows are exactly the ~9% where a real contract rate WAS applied (not copied from manual).
- The rate lookup succeeded (rate_match_status=matched, exact_key).
- So the engine did real contract work here.

## Why it is NOT confirmed "correct" either

The delta exists ONLY because the audit made ONE unilateral interpretation choice
(documented in SPATAUSFALL_CONTRACT_RULE_DECISION.md):

> Treat workbook `GW / Spaetausfall = in GW` as NON-binding, and apply the
> age-derived extended/Spaetausfall rate for claims in the 37-60 month window.

- IF BMW confirms age-derived extended rate is correct -> EUR 2.5m is a real
  finding (manual overpaid at full standard rate).
- IF BMW says the workbook `in GW` label is contractually binding for rate
  selection -> those 22,586 rows should be full standard rate, and the
  EUR 2.5m LARGELY DISAPPEARS.

Opus 4.8 four-eyes returned 25/25 `needs_bmw_expert` on exactly these groups.

## Correct way to present to BMW

Do NOT say "BMW overpaid EUR 2.5m."

Say: "EUR 2.5m of delta rests entirely on one rate-classification question -
standard vs extended GW rate for claims in months 37-60 where the workbook says
`in GW`. Range: up to EUR 2.5m recoverable if age-derived extended rate applies;
near zero if the workbook `in GW` status is contractually binding. BMW expert
must confirm which rule governs."

## The range, quantified

| Scenario | Comparable delta (contract - manual) |
| --- | ---: |
| BEST case - age-derived extended rate stands | -EUR 2,485,569.45 (EUR 2.5m recoverable) |
| WORST case - workbook `in GW` is binding | +EUR 87,003.35 (finding vanishes, slight reverse) |

The entire BMW position swings across a ~EUR 2.57m band on ONE interpretation
question. The finding is not "correct" or "incorrect" until BMW rules on it.

## Contrast with the JLR structural issue

- JLR: 91% manual-inherited -> not a genuine independent contract run for most value.
- BMW: also ~91% inherited on the ALIGNED bulk, BUT the EUR 2.5m delta itself is
  100% genuine contract-rate logic (not inherited). The BMW issue is not
  inheritance - it is that the entire delta depends on ONE unconfirmed
  interpretation.
