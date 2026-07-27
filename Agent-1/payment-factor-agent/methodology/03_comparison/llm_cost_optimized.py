"""Optimized LLM cost — prompt caching (confirmed working) + other levers.

Confirmed live 2026-07-20: cache write then cache read on the static contract
prefix through the real agent code (_call_llm_cached). Cache read = ~10% of
input price; cache write = ~125% (5m) of input price.

Same model (Opus 4.8), same full context, same accuracy — only the repeated
prefix billing changes.
"""

PRICE_IN = 15.0 / 1_000_000
PRICE_OUT = 75.0 / 1_000_000
PRICE_CACHE_WRITE = 18.75 / 1_000_000   # 1.25x (5m TTL)
PRICE_CACHE_READ = 1.50 / 1_000_000     # 0.10x

CTX = 14465        # cached prefix tokens (contract profile + passages)
CLAIM = 60         # per-signature variable suffix
OUT_COT = 700      # output with chain-of-thought
OUT_LEAN = 250     # output if chain-of-thought trimmed for deterministic-ish groups

BMW_SIGS = 869
JLR_SIGS_LOW, JLR_SIGS_HIGH = 92, 368


def baseline(sigs, out=OUT_COT):
    return sigs * (CTX + CLAIM) * PRICE_IN + sigs * out * PRICE_OUT


def cached(sigs, out=OUT_COT, writes=None):
    # cache warm: 1 write per ~50 calls (conservative for 5m TTL); ~1 for 1h TTL
    writes = writes if writes is not None else max(1, sigs // 50)
    reads = sigs - writes
    ctx = writes * CTX * PRICE_CACHE_WRITE + reads * CTX * PRICE_CACHE_READ
    return ctx + sigs * CLAIM * PRICE_IN + sigs * out * PRICE_OUT


def main() -> int:
    print("=== BMW (869 signatures) ===")
    print(f"  baseline (no cache):            ${baseline(BMW_SIGS):,.2f}")
    print(f"  + prompt cache (5m, ~18 writes): ${cached(BMW_SIGS):,.2f}")
    print(f"  + prompt cache (1h, 1 write):    ${cached(BMW_SIGS, writes=1):,.2f}")
    print(f"  + cache + lean output:           ${cached(BMW_SIGS, out=OUT_LEAN, writes=1):,.2f}")
    print()
    print("=== JLR eligibility (92-368 signatures) ===")
    print(f"  cached low:  ${cached(JLR_SIGS_LOW, writes=1):,.2f}")
    print(f"  cached high: ${cached(JLR_SIGS_HIGH, writes=1):,.2f}")
    print()
    bmw_c = cached(BMW_SIGS, writes=1)
    print("=== COMBINED (cache, 1h TTL) ===")
    print(f"  BMW+JLR: ${bmw_c + cached(JLR_SIGS_LOW, writes=1):,.2f}"
          f"  to  ${bmw_c + cached(JLR_SIGS_HIGH, writes=1):,.2f}")
    print()
    print("=== SAVINGS LADDER (BMW) ===")
    b = baseline(BMW_SIGS)
    c = cached(BMW_SIGS, writes=1)
    cl = cached(BMW_SIGS, out=OUT_LEAN, writes=1)
    print(f"  $235 baseline -> ${c:,.0f} cached ({100*(b-c)/b:.0f}% off) -> ${cl:,.0f} cached+lean ({100*(b-cl)/b:.0f}% off)")
    print("  All at Opus 4.8, full context, no capability reduction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
