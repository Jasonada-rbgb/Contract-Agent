# True Contract Run — BMW vs JLR (corrected finding)

Date: 2026-07-20

## The question
"Neither of these methods is actually a contract run" — is that true for both?

## Answer: TRUE for JLR, FALSE for BMW. They are structurally different.

I initially said both were ~91% manual-inherited. That was correct for JLR but
WRONG for BMW. Correcting the record with a forced independent-rate test.

---

## BMW = GENUINE contract run (correction)

Test: recompute BMW as gross x Kostenstand_rate with NO manual fallback.

- Frozen contract total: EUR 40,499,031.91
- gross x Kostenstand_rate (independent): EUR 40,499,031.91  ->  **IDENTICAL to the cent**
- Aligned rows: rate_match_method = exact_key on 267,007 / 267,034.

**Conclusion:** BMW's contract_rate is independently looked up from the Kostenstand
rate table (exact_key). On aligned rows it EQUALS the manual rate only because both
legitimately apply the same standard-GW percentage — this is genuine agreement, not
copying. BMW is a real contract calculation.

The apparent "93% inheritance" I reported earlier was coincidental rate agreement,
not a manual fallback. BMW does not substitute manual values.

## JLR = NOT a genuine contract run (confirmed)

Test: recompute JLR export as PFACC/DMYA/STAR rate x gross with NO manual fallback.

| Method | In-scope export payable EUR | Delta vs manual |
| --- | ---: | ---: |
| Manual workbook | 9,361,733.09 | - |
| Frozen "contract" method (91% manual-inherited) | 9,389,442.85 | +27,709.77 |
| **TRUE independent contract (no fallback)** | **9,026,970.39** | **-334,762.69** |

- 79,528 in-scope rows (EUR 12.2m gross) had NO independent pipeline rate -> routed
  to requires_review (not silently set to manual).
- On the 276,577 rows that DO have an independent rate, the genuine contract figure
  is ~EUR 335k BELOW manual, not +27.7k above.

**Conclusion:** JLR's `fallback_effective_rate()` literally substitutes the manual
value when an acceptance basis exists. Removing it moves the result by ~EUR 362k and
flips the sign. The +27.7k "alignment" is an artifact of the fallback. JLR needs a
real contract-rate rebuild before its number can be presented as a contract finding.

---

## Bottom line for the experts

| OEM | Is it a real contract run? | Headline status |
| --- | --- | --- |
| BMW | YES - Kostenstand rates applied independently | EUR 2.5m delta is real contract logic, but 103.5% of it is ONE Spaetausfall/in-GW interpretation (range -2.5m to +0.09m pending BMW ruling) |
| JLR | NO - 91% manual-inherited via fallback | Genuine independent run = -335k on rated rows (vs +27.7k reported); needs rebuild + resolution of 79.5k un-rated rows |

## Required next actions
- JLR: rebuild the contract method without the manual fallback; resolve the 79,528
  un-rated rows (real rate, workbook-locked fallback, or expert review) before quoting
  a contract-vs-manual number.
- BMW: resolve the single Spaetausfall / in-GW interpretation (worth the entire 2.5m band).
