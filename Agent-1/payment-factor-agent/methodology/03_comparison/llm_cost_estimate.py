"""LLM cost estimate for full BMW + JLR claims (2023/24/25).

Measured inputs (live, 2026-07-20):
- Contract context + profile per LLM call: ~14,465 input tokens (measured).
- Output per call (grouped JSON w/ chain-of-thought): ~600 tokens typical.
- Claude Opus 4.8 pricing (Databricks serving, Anthropic list ~ USD):
    input  $15 / 1M tokens
    output $75 / 1M tokens
  (adjust PRICE_IN / PRICE_OUT if your negotiated Databricks rate differs.)

Two evaluation modes:
- signature_representative: 1 LLM call per metric-signature (max token saver).
- grouped_size100: batches of 100 within a signature (more calls, per-row echo).

Deterministic pre-check settles the bulk with NO LLM cost.
"""

from __future__ import annotations

PRICE_IN = 15.0 / 1_000_000   # USD per input token
PRICE_OUT = 75.0 / 1_000_000  # USD per output token

CONTEXT_TOKENS = 14465        # measured input tokens per call (contract+profile)
CLAIM_TOKENS_PER_ROW = 60     # extra input tokens per claim in a batch
OUTPUT_TOKENS_REP = 700       # representative call output
OUTPUT_TOKENS_PER_ROW = 120   # per-row output in a grouped batch

# ---- populations (2023/24/25 only) ----
# BMW: all 311,968 rows are 2023-25. Ambiguous (LLM) rows and signatures:
BMW_AMBIGUOUS = 43820
BMW_SIGNATURES = 869

# JLR: rates are technical factors (NOT contract LLM). Only ELIGIBILITY-review
# rows would hit the contract LLM. JLR eligibility is overwhelmingly deterministic
# (scope/RB warranty/not-Bosch). Estimate eligibility-review candidates for 2023-25.
# 2023-25 JLR rows = 83744+67143+32646 = 183533. Conservatively assume the same
# ~14% ambiguity as BMW would be a large overestimate for JLR (JLR eligibility is
# mostly flag-based), so model a low and high band.
JLR_2023_25_ROWS = 83744 + 67143 + 32646
JLR_ELIG_REVIEW_LOW = int(JLR_2023_25_ROWS * 0.02)   # 2% need contract LLM
JLR_ELIG_REVIEW_HIGH = int(JLR_2023_25_ROWS * 0.08)  # 8% need contract LLM
JLR_AVG_GROUP = 40  # similar metric-signature compression


def cost_representative(signatures: int) -> float:
    inp = signatures * (CONTEXT_TOKENS + CLAIM_TOKENS_PER_ROW)
    out = signatures * OUTPUT_TOKENS_REP
    return inp * PRICE_IN + out * PRICE_OUT


def cost_grouped(rows: int, group_size: int = 100) -> float:
    import math
    calls = math.ceil(rows / group_size)  # lower bound: one signature
    inp = calls * CONTEXT_TOKENS + rows * CLAIM_TOKENS_PER_ROW
    out = rows * OUTPUT_TOKENS_PER_ROW
    return inp * PRICE_IN + out * PRICE_OUT


def main() -> int:
    print("=== BMW (2023/24/25, 311,968 rows; 268k deterministic = $0 LLM) ===")
    bmw_rep = cost_representative(BMW_SIGNATURES)
    bmw_grp = cost_grouped(BMW_AMBIGUOUS, 100)
    print(f"  ambiguous rows: {BMW_AMBIGUOUS:,} | signatures: {BMW_SIGNATURES:,}")
    print(f"  signature_representative mode:  ${bmw_rep:,.2f}")
    print(f"  grouped_size100 mode:           ${bmw_grp:,.2f}")
    print()

    print("=== JLR (2023/24/25, 183,533 rows; rates = technical factors, NOT contract LLM) ===")
    for label, rows in (("LOW 2%", JLR_ELIG_REVIEW_LOW), ("HIGH 8%", JLR_ELIG_REVIEW_HIGH)):
        import math
        sigs = max(1, math.ceil(rows / JLR_AVG_GROUP))
        rep = cost_representative(sigs)
        print(f"  eligibility-review {label}: {rows:,} rows -> {sigs:,} signatures -> ${rep:,.2f} (representative)")
    print()

    print("=== TOTAL (representative mode, recommended) ===")
    jlr_low_sigs = max(1, JLR_ELIG_REVIEW_LOW // JLR_AVG_GROUP)
    jlr_high_sigs = max(1, JLR_ELIG_REVIEW_HIGH // JLR_AVG_GROUP)
    total_low = bmw_rep + cost_representative(jlr_low_sigs)
    total_high = bmw_rep + cost_representative(jlr_high_sigs)
    print(f"  Combined BMW+JLR: ${total_low:,.2f} (low)  to  ${total_high:,.2f} (high)")
    print()
    print("NOTE: costs scale with SIGNATURES not rows. Deterministic pre-check +")
    print("metric-signature grouping keep this to hundreds of calls, not ~500k.")
    print("If a full per-row LLM run were forced (no grouping, no deterministic):")
    full_rows = 311968 + JLR_2023_25_ROWS
    print(f"  ~{full_rows:,} rows x (14465 in + 400 out) ~= "
          f"${(full_rows*(CONTEXT_TOKENS*PRICE_IN + 400*PRICE_OUT)):,.0f} (DO NOT DO THIS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
