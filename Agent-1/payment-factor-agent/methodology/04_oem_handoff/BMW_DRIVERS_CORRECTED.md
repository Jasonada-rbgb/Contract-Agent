# BMW Delta Drivers — Corrected (more than one cause)

Date: 2026-07-20

## Correction to my earlier "single clause" claim

I earlier said "103.5% of the delta is one standard_gw->extended_gw reclassification."
That was too narrow. The MECHANISM is one thing, but it is NOT a single contract term
or a single component. Corrected below.

## Two SEPARATE exposure pools (they were never one number)

The BMW audit produced TWO distinct delta pools that must not be conflated:

### Pool A — Comparable delta: EUR -2,485,569 (the "2.5m")
- Mechanism: extended/Spaetausfall reduced rate = exactly HALF the manual rate.
  Ratio contract/manual = 0.50 on 22,586 rows (confirmed exact).
- BUT spread across:
  - **62 distinct shopping-carts (Warenkorb)**
  - **3 source years** (2023: -0.21m, 2024: -1.20m, 2025: -1.07m)
  - multiple component families (injection pumps, EME control units, PDC sensors,
    combi-instruments, injectors, nozzles...)
- Top carts: 1351 injection pump (-736k), 1236 EME ECU (-432k), TPV Kombi (-288k),
  PDC/ULS sensors (-136k), petrol injectors (-104k).

### Pool B — Expert-review contract exception: EUR -1,630,625 (SEPARATE, not in the 2.5m)
- 20,155 rows where contract method paid 0.
- reason_kind mix: 12,516 other manual reason, 5,351 status-only, **1,919 legal/regulatory**,
  308 exclusion/settlement, 45 deadline.
- This is a DIFFERENT driver: legislative/goodwill/exclusion exceptions, NOT the
  Spaetausfall halving.

## So the drivers are (at least) THREE things

1. **Spaetausfall/extended-rate halving** (Pool A, EUR 2.5m) - one mechanism, but
   applied across 62 carts x 3 years. This is where "BMW expert likely has a reason":
   the 0.50 halving is almost certainly a real, agreed extended-warranty supplier-share
   rule - which SUPPORTS your instinct that the expert has a basis for it.
2. **Legislative / regulatory exceptions** (Pool B subset, ~1,919 rows) - separate clause.
3. **Exclusion / settlement / manual-deadline reasons** (Pool B remainder) - separate again.

## Why your instinct is right

You said "if 2.5m rests entirely on a single contract term, the BMW expert likely has
a reason." Correct - and the data supports it:
- The reduction is a CLEAN 0.50 factor (not noise), consistent with a documented
  extended-warranty supplier-liability share (contract clause R006: supplier reimburses
  BMW for up to 24 months AFTER the 36-month primary period - a partial/extended share).
- It is applied consistently across 62 carts, which is what you'd expect from a
  GENERAL contract rule, not a data artifact.

So Pool A is most likely a LEGITIMATE contract rule (extended-period supplier share =
half rate), meaning the manual workbook - which paid FULL rate - may be the one that is
wrong, OR the workbook `in GW` status legitimately keeps those in full-rate. Either way
it is a real contract question with a real basis, exactly as you suspected.

## Revised expert framing

Do NOT present as "one clause, 2.5m." Present as:
- Pool A (2.5m): extended-period 50% supplier-share rate vs manual full rate, across
  62 carts / 3 years. Ask BMW: is the 0.50 extended share correct, and does workbook
  `in GW` override it?
- Pool B (1.63m): separate legislative/exclusion exceptions - distinct expert questions.
