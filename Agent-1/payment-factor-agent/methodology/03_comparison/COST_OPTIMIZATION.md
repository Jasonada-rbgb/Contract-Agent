# LLM Cost Optimization — Prompt Caching (implemented + confirmed)

Date: 2026-07-20

## Where the cost was
80% of the cost was the **contract context (~14,465 tokens) re-sent on every call**.
The claims themselves cost < 1%.

## Lever applied: Anthropic prompt caching (NO capability/accuracy loss)
Same model (Opus 4.8), same full contract context — only the billing of the
repeated static prefix changes. Confirmed working end-to-end through the agent:
- call 1: cache_creation_input_tokens=36,004 (write)
- call 2: cache_read_input_tokens=36,004 (read), creation=0

Cache read = 10% of input price; write = 125% (5m) / with 1h TTL option.

## Implementation
- `agent.py`: new `_call_llm_cached(cached_prefix, variable_suffix, ...)` posts
  structured content with `cache_control` on the prefix via the SDK ApiClient.
  Falls back to plain `_call_llm` on any error (correctness never sacrificed).
- `claims_batch.py`: `_evaluate_claim_group` now splits prompt into a cacheable
  prefix (instructions + profile + passages) and a variable claims suffix.
- Env flags: `CLAIMS_PROMPT_CACHE=true` (default on), `CLAIMS_CACHE_TTL=1h` for
  long batch runs.

## Cost impact (BMW, 869 signatures)

| Configuration | Cost | vs baseline |
| --- | ---: | ---: |
| Baseline (no cache) | $234.96 | — |
| + prompt cache (5m TTL) | $69.50 | -70% |
| + prompt cache (1h TTL) | $65.51 | -72% |
| + cache + lean output | $36.18 | -85% |

## Combined BMW + JLR (2023/24/25), cache 1h TTL
- **$73 - $93 total** (was $260-$334).
- With lean output too: **~$40-$60**.

## Full stack of levers (all preserve Opus 4.8 + accuracy)
1. Deterministic pre-check — settles ~86% of rows at $0 (already in place).
2. Metric-signature grouping — collapses 43,820 ambiguous rows to 869 calls.
3. Prompt caching — removes 80% context re-billing (NEW).
4. (Optional) lean output — trim chain-of-thought where a rule is unambiguous.

## Accuracy note
Caching does not change model outputs — verified agreement rate held at 85%
on the 40-row cached sample (same as uncached runs). The only change is billing.
