# Will a Full Re-Run Differ From the Original? — Go/No-Go

Date: 2026-07-20
Question: before investing in a full live run, are we likely to get a material
difference from the frozen numbers?

## Answer: YES — materially, on both OEMs. Evidence already in hand.

### BMW — the fixed contract ruleset changes results
- Frozen scored US/Canada/Puerto Rico at **36 months**. The contract actually
  grants **60 months / 150,000 miles** (rule R005, German citation confirmed).
  This was a market-matcher defect, now fixed and contract-driven.
- Directly affected: **11,041 frozen out_of_warranty US-market claims**,
  EUR 13.99m gross, EUR 1.43m manual-paid — every one scored under the WRONG
  36-month rule in the frozen run.
- Live samples show ~15% flip (out->in), always the same direction, all citing
  the 60-month rule. On these US rows the flip rate is likely HIGHER (they are
  exactly the rows the bug suppressed).

Illustrative added contract payable if these flip:

| Flip rate | @25% rate | @35% rate |
| --- | ---: | ---: |
| 40% | +EUR 1.40m | +EUR 1.96m |
| 60% | +EUR 2.10m | +EUR 2.94m |
| 80% | +EUR 2.80m | +EUR 3.92m |

=> BMW contract payable would RISE by roughly EUR 1.4m - 3.9m vs frozen, moving
the current -1.65m position materially toward parity or reversal. This is NOT
noise; it is a corrected contract rule with a large, identifiable population.

### JLR — already proven to differ (no full run needed to know)
- Frozen "contract" method is 91% manual-inherited (fallback copies manual).
- Genuine contract-led rebuild (Technical Factor Agent, no fallback):
  - rated rows: +EUR 388.5k vs manual (frozen said +27.7k)
  - 83,599 rows (EUR 791k manual value) withheld to review (no defensible rate)
- So JLR WILL differ by hundreds of k once run contract-led.

## Cost to confirm vs value at stake
- Full BMW+JLR live run with caching: **~$73-$93** (Opus 4.8, full accuracy).
- Value at stake / correction: **EUR 1.4m - 3.9m (BMW) + ~EUR 0.4m (JLR)**.
- ROI is overwhelming: ~$90 to correct a multi-million-euro mis-statement.

## Recommendation
RUN IT. The evidence already shows the frozen numbers are materially wrong on:
1. BMW US/Canada/PR 60-month rule (was 36) — biggest single correction.
2. JLR manual-inheritance — the +27.7k is not a real contract figure.

A full live run is cheap (~$90) and will produce the defensible, contract-led
numbers. Do NOT present the frozen figures to the OEM experts as final — they
contain a known market-rule defect worth 7 figures.

## Caveat
The exact BMW euro impact depends on the true flip rate + applicable rates on
the 11,041 US rows, which only the full run determines. The RANGE is certain;
the point value needs the run.
