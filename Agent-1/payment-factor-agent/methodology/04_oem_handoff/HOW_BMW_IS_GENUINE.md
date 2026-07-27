# How can BMW be "93% manual" AND a genuine contract run?

Date: 2026-07-20

## The apparent contradiction

Earlier I said BMW was ~93% manual-inherited, then said it is a genuine contract run.
Both statements used the word "manual" but measured DIFFERENT things. Resolved below
with the only test that distinguishes them.

## Two different measurements

- **"93%"** = share of rows where contract_payable EQUALS manual_payable.
  This is AGREEMENT. It cannot tell you whether the value was COMPUTED or COPIED,
  because when the contract rate and manual rate are the same, the payable is
  identical either way.

- **"Genuine contract run"** = on rows where the contract rate DIFFERS from the
  manual rate, does the payable follow the CONTRACT rate (computed) or the MANUAL
  value (copied)? This is the only discriminating test.

## The discriminating test (rows where the two rates disagree)

### BMW
- Rows where contract_rate != manual_rate: **22,595**
- contract_payable follows gross x CONTRACT rate: **22,595 (100.0%)**
- contract_payable follows manual: 4 (0.0%)

-> BMW COMPUTES from the Kostenstand contract rate. It equals manual on the other
   ~93% only because both legitimately apply the same standard-GW percentage there.
   That is genuine agreement, not copying. **BMW is a real contract run.**

### JLR (same test, for contrast)
- Rows where independent rate != manual rate: **12,147**
- contract_payable follows gross x INDEPENDENT rate: 8,062 (66.4%)
- contract_payable follows MANUAL value: **4,085 (33.6%)**

-> JLR's fallback substitutes the manual value on a third of the rows where the
   rates disagree (via fallback_effective_rate preferring manual when an
   acceptance basis exists). That is why forcing an independent run moved JLR by
   ~EUR 362k (from +27.7k to -335k). **JLR is partly a manual replay.**

## Plain-English answer

BMW going from "93% manual" to "genuine contract run" is not a reversal — the 93%
was measuring coincidental rate AGREEMENT, and the genuine-run test proves BMW
independently computes from the contract rate table (100% follow-through where
rates differ).

JLR fails the same test (34% follow manual where rates differ), which is why it is
correctly described as NOT a genuine contract run.

## One-line summary for each OEM

- **BMW:** Real contract calculation. Agrees with manual on the bulk because the
  contract standard-GW rate genuinely equals the manual standard-GW rate there.
  The EUR 2.5m delta is real contract logic (one Spaetausfall interpretation).
- **JLR:** Manual replay with a contract overlay. Substitutes manual on ~1/3 of
  disagreeing rows. Genuine independent run = -EUR 335k, not +27.7k.
