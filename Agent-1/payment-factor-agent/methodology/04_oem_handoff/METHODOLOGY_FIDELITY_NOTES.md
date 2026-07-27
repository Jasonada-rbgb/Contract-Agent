# Methodology Fidelity Notes — Is the Re-Verification 1:1?

Date: 2026-07-20

## Short answer

- **Numbers: exact 1:1.** frozen and reproduced scenarios match to the cent (BMW −2,485,569.45 / −1,648,860.56; JLR +27,709.77).
- **Method: reproduced faithfully, with the original method's own characteristics preserved.** Governance fixes were added only as SEPARATE scenarios, never overwriting.
- **One reproduction shortcut:** replayed from the frozen normalized row-level (and BMW's frozen `bmw_ruleset.json`) rather than re-ingesting raw Excel + a fresh Contract Agent pass. This proves internal consistency and reproducibility from the frozen intermediate; it does not independently re-derive from raw source. A full raw re-run is available on request.

## Material methodology finding (the part that is NOT "100% correct")

### JLR contract method is ~91% manual-inherited

`jlr_full_contract_audit.py :: fallback_effective_rate()` (lines 448-457) prefers the
workbook MANUAL rate whenever an acceptance basis is present. Measured on live data:

- Export rows where contract_payable == manual exactly: **79,721 / 408,385**.
- In-scope export contract payable = EUR 9,389,442.85, of which:
  - **manual-inherited: EUR 8,544,160.51 (91.0%)**
  - genuinely rate-derived (PFACC/DMYA/STAR): EUR 845,282.34 (9.0%)

**Implication:** the +27.7k "contract vs manual" delta is not a fully independent
comparison. For 91% of value the contract method equals manual by construction, so a
delta can only arise on the ~9% that uses real rates. The close alignment is partly
self-fulfilling. Defensible as conservative, but must be DISCLOSED to JLR — not
presented as independent corroboration of the manual workbook.

This differs from BMW, where rates come independently from the Kostenstand table.

## Minor items (checked, not material)

| Item | Finding | Verdict |
| --- | --- | --- |
| UK CAT1 = full gross (line 534) | No CAT1 rows exist in UK sample (only CAT4/CAT2). Branch never fires. | Non-issue |
| RB warranty exclusion aggressiveness | Zeroes only EUR 7,798.83 across 13,407 rows | Immaterial |
| not-Bosch/not-identified rejection | Zeroes only EUR 234.68 | Immaterial |
| contract payable > gross (rate >100%) | 243 rows | Minor data-quality note; recommend cap at 100% |

## DMTL 35% — RESOLVED

JLR confirmed a DMTL manual update explains the 35%. It is a legitimate manual/business
update, not an unexplained figure. Keep it stored as a governed override (OVR-JLR-DMTL-MY2023)
with pallet evidence, confidence downgraded from expert_review to business_confirmed.

## Recommended methodology adjustments (optional, available now)

1. **Disclose or reduce manual-inheritance:** add a flag `rate_provenance = manual_inherited | rate_derived`
   to every export row so the 91/9 split is transparent. Optionally add a scenario that applies
   PFACC/DMYA rates even when a manual rate exists, to show a truly independent contract figure.
2. **Cap payable at gross** (fix the 243 >100% rows).
3. These are NOT yet applied — flagged for your decision.
