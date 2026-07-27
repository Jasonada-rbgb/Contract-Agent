# Live Contract Query Verification — "Are we actually querying the contract?"

Date: 2026-07-20

## Your challenge
"The JLR one is running too quick — are we actually querying the contract on some
of these claims? BMW also, or is it just using the output from the last method?"

## Honest answer: you were RIGHT about the replays

The scenario engines I ran first (jlr_scenario_engine, bmw_scenario_engine,
jlr_contract_led_rebuild) did NOT query the contract. They replayed frozen
row-level columns (contract_rate, dmya_acceptance, contract_warranty_type) that
the ORIGINAL run had already computed. That is why they ran in seconds. They are
valid arithmetic re-checks, but they are NOT contract queries.

## So I ran a GENUINE live contract query (BMW sample)

Called the real `evaluate_claims_table()` which:
- loaded BMW contract assets from the KB volume,
- ran hybrid retrieval over contract passages,
- called Opus 4.8 (temp 0) on the LLM-review claims.

### Result
- Sample: 8 rows from the Spaetausfall dispute population.
- Live query performed: YES (34.9s, real retrieval + LLM).
- **Decision agreement with frozen: 8 / 8 = 100%.**
- All 8 live-classified out_of_warranty, matching frozen.

This confirms the frozen BMW output IS reproducible by a genuine contract query,
not just by replaying its own numbers.

## TWO important facts this surfaced

### 1. BMW contract is NOT in the production KB
- Prod volume `kb_bundle_v1/chunks_json` contains ONLY `oem=JLR`.
- BMW contract lives in STAGING: `/Volumes/mdna_dev/warranty_agent_staging/uploads/kb_bundle` (oem=BMW).
- The live query only works when KB_BUNDLE_BASE points at staging.
- Governance flag: BMW is not promoted to prod KB. Confirm this is intended before
  presenting BMW as a production contract result.

### 2. The BMW method IS genuinely contract-driven
- bmw_ruleset.json (source=compiled_profile) is the extracted rule set, but the
  live evaluate_claims_table still retrieves + LLM-reasons over contract passages
  and agreed 100% on the sample. So BMW eligibility is contract-queried, not copied.

## JLR nuance (important distinction)
For JLR, the CONTRACT governs ELIGIBILITY only (in/out of scope, RB warranty,
not-Bosch). The PAYMENT RATES (DMYA/PFACC/STAR technical factors) are NOT in the
contract text at all - they come from STAR inspection outcomes. So "querying the
contract" for JLR rate calculation is a category error: the rate is a technical
factor, not a contract term. The contract query applies to JLR eligibility; the
Technical Factor Agent owns rates. This is exactly the architecture split the plan
proposes.

## What still needs a full live run (not yet done)
- BMW: full 311,968-row live contract query (only an 8-row sample done here).
- JLR: full live ELIGIBILITY query (scope/RB warranty) — separate from rate calc.
Both are heavy Opus/retrieval runs. Sample proves the path works and agrees;
full run is the remaining compute.
