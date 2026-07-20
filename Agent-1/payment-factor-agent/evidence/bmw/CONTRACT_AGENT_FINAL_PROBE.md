# Contract Agent Final Probe

## Backend/API Status

The deployed Streamlit app URL authenticated with the Databricks CLI token, but `POST /api/evaluate-claims` returned HTTP 405 Method Not Allowed. This URL is serving the Streamlit app path, not the FastAPI claims API route.

A local backend-code probe was then run against the BMW staging KB bundle and `databricks-claude-opus-4-8`.

## Fixes Required For Probe

Two backend evaluator issues were found and fixed locally before the valid probe run:

1. `databricks-claude-opus-4-8` does not support the `temperature` parameter. The shared LLM helper now suppresses temperature for Claude endpoints.
2. ISO dates such as `2025-08-04` were parsed with `dayfirst=True`, causing date flips. The parser now handles `YYYY-MM-DD` with year-first semantics before falling back to day-first parsing.

## Probe Result

Input rows: 6
Mapping warnings: none

| Claim | Country | Decision | Market applied | Component | Months | Mileage limit | Confidence |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| 379664463 | NO | out_of_warranty | all other countries | general | 36 | | high |
| 374824244 | US | out_of_warranty | USA, Canada, Puerto Rico | general | 60 | 150000 miles | high |
| 381129237 | CH | out_of_warranty | all other countries | general | 36 | | high |
| 369747724 | DE | out_of_warranty | all other countries | general | 36 | | high |
| 363931695 | US | in_warranty | USA, Canada, Puerto Rico | general | 60 | 150000 miles | medium |
| 357381804 | NL | in_warranty | all other countries | general | 36 | | medium |

## Audit Interpretation

The Contract Agent is dynamically applying market/location logic:

- US claims use 60 months / 150,000 miles.
- Non-US/Canada/Puerto Rico claims use the 36-month base rule.
- The agent can also recognize the 24-month extended/goodwill window in some non-US rows.

However, in this probe all sampled claims were classified with `applicable_component = general`. The probe does not prove that the Contract Agent is reliably applying part-specific warranty periods. It proves market logic is active, while part/component logic remains weak or not evidenced for these BMW rows.

Output file: `contract_agent_dynamic_rule_probe_output.json`.
