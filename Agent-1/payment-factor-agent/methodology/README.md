# Rule-Building Methodology (Code)

This folder contains the **code** that shows how the payment-factor rules are
derived and reproduced from the Contract Agent. It is intentionally limited to
build/derivation logic — output data, evidence, cost analysis, and OEM-handoff
reports are not included here (this package is about how the agent is built and
scaled, not about specific run outputs or cost differences).

The frozen source artifact the BMW rules compile from is
`../provenance/bmw_ruleset.json` (fingerprint `e71bec717be8a433`). Mercedes-Benz
GALA rules are supplied at run time as an approved, fingerprinted matrix from
the Contract Agent; the proprietary source agreements and matrix values do not
belong in this repository.

## Derivation / reproduction engines

| File | Purpose |
| --- | --- |
| `00_baseline/pin_baseline.py` | Pin a frozen baseline so derivations are reproducible. |
| `01_reproduced/bmw_scenario_engine.py` | Deterministic BMW scenario engine (reproduces rulings from rules + inputs). |
| `01_reproduced/jlr_scenario_engine.py` | Deterministic JLR scenario engine. |
| `01_reproduced/jlr_datebasis_sensitivity.py` | DMYA date-basis sensitivity logic. |
| `01_reproduced/jlr_thin_denominator_exposure.py` | Thin-denominator governance exposure logic. |
| `01_reproduced/mbc_gala_scenario_engine.py` | Portable signed-GALA matching, temporal-gate, and quantity-apportionment validation. |
| `02_fixes/bmw_reextract_ruleset.py` | Re-extract the BMW ruleset directly from the contract (caches bypassed) to prove rules are contract-driven, not hardcoded. |
| `02_fixes/bmw_live_contract_query_sample.py` | Sample live contract-query verification against the agent. |
| `02_fixes/bmw_live_full_population.py` | Full-population live contract-query driver. |
| `02_fixes/jlr_rate_provenance_flag.py` | Flag each row as `manual_inherited` vs `rate_derived` (rate provenance logic). |
| `02_fixes/jlr_true_contract_run.py` | Independent contract-rate run (no manual inheritance) for the JLR export population. |

## Related

- `../rules/` — the rule artifacts these engines produce/validate.
- `../scripts/` — the payment-factor agent and audit/rebuild code.
- `../docs/full.md` — methodology narrative and recommended agent architecture.
