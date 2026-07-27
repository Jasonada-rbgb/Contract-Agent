# LLM Cost Estimate — Full BMW + JLR Claims (2023/24/25)

Date: 2026-07-20
Endpoint: databricks-claude-opus-4-8. Measured live: ~14,465 input tokens of
contract context+profile per LLM call.
Pricing assumed (Anthropic list): input $15/1M, output $75/1M tokens.
**Adjust if your negotiated Databricks rate differs — cost scales linearly.**

## Row populations (2023/24/25)
- BMW: 311,968 rows. Deterministic (no LLM): 268,148. Ambiguous (LLM): 43,820.
  Metric-signature groups: **869**.
- JLR: 183,533 rows (2023-25). RATES are technical factors (STAR DMYA/PFACC) —
  NOT contract-LLM. Only ELIGIBILITY-review rows hit the contract LLM.

## Estimated cost (recommended: signature-representative mode)

| Scope | LLM calls | Cost (USD) |
| --- | ---: | ---: |
| BMW (869 signatures) | 869 | **$235** |
| JLR eligibility, low 2% | 92 | $25 |
| JLR eligibility, high 8% | 368 | $100 |
| **Combined BMW+JLR** | ~960-1,240 | **$260 - $334** |

### Alternative: grouped_size100 mode (per-row echo, more robust)
- BMW: $529. Higher because it echoes a decision per row rather than one per signature.

## Why it is cheap
Cost scales with SIGNATURES, not rows. Two mechanisms:
1. Deterministic pre-check settles ~86% of BMW rows with $0 LLM.
2. Metric-signature grouping collapses the ambiguous remainder to hundreds of
   groups (869 for all BMW ambiguous rows).

## What NOT to do
A naive per-row LLM run (no grouping, no deterministic pre-check) over all
~495,501 rows would cost **~$122,000**. The hybrid + signature architecture
reduces this by ~99.8%.

## Caveats
- JLR band is an estimate; JLR eligibility is mostly flag-based (deterministic),
  so real JLR contract-LLM cost is likely near the LOW end.
- Excludes embedding/retrieval cost (retrieval is done once per batch and is
  negligible vs LLM tokens; base_context is pre-compiled).
- Excludes any four-eyes review pass (add ~$50-100 if a grouped review is run).
- Re-runs are cheaper: ruleset + retrieval are cached.

## Bottom line
Full contract-led re-run of BMW + JLR for 2023/24/25 is on the order of
**$260-$530 total**, not thousands — because of deterministic settlement +
metric-signature grouping.
