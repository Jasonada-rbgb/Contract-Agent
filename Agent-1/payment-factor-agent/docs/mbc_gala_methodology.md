# Mercedes-Benz GALA Compile-Once Methodology

## Purpose

Mercedes-Benz GALA agreements are a signed payment-factor overlay, not a
standalone replacement for the Mercedes-Benz main warranty contract. The
Contract Eligibility Agent first determines whether a claim matches a signed
GALA rule. Matched, temporally valid rules are settled deterministically;
unmatched or gate-blocked claims return to main-contract eligibility.

This keeps three decisions separate:

1. **Eligibility** — what the main MBC contract says about a claim.
2. **Agreement applicability** — whether a signed GALA rule applies.
3. **Quantity acceptance** — the agreement Quote that determines accepted
   quantity, not an independently calculated monetary payment rate.

## Approved source pattern

| Layer | Approved source | Role |
| --- | --- | --- |
| Main-contract bundle | Mercedes-Benz contract chunks in the Contract Agent knowledge store | Standard, non-GALA eligibility and evidence retrieval. |
| GALA agreements | Source PDFs in approved storage | Legal/operational source for GALA terms. |
| GALA matrix | Compiler output with source filename and fingerprint | Runtime deterministic settlement. |
| Claim extract | Authorized SRS/warehouse input | Supplies join keys, date gates, quantities, and reference-cost metadata. |
| Learned cache | Approved, expiring outcome store | Optional reuse after the signed matrix; never replaces it. |

The GitHub package contains the process and portable validation code only. It
does **not** contain the PDFs, full matrix values, raw claim extracts, claim
identifiers, or settlement/cost outputs.

## Compile once, apply deterministically

The GALA compiler converts approved agreement text into a flat per-family rule
matrix. A rule records family/supplier/part joins, Quote percentage (or an
undetermined value), applicable year or production window, source filename,
and compiler provenance. Every compilation is integrity checked before the
matrix is promoted.

Runtime precedence is fixed:

```text
signed GALA matrix
  -> approved, non-expired learned rule
  -> grouped main-contract review
```

The first match key is `part_family_number`. Only when no family match exists
may the engine use the combined `supplier_number + part_number` fallback. It
must not broaden a supplier match because that can fabricate a rate for a
different family.

Rules with an `Anfallsjahr` use the receipt-year gate inclusively pending
business confirmation. Rules that specify a production window use
`vehicle_origin_production_date`. A missing required gate value, an
undetermined Quote, or an ambiguous rule produces review/fall-through rather
than an inferred payment factor.

## Settlement semantics

GALA Quote is a **quantity apportionment**:

```text
accepted_quantity = replaced_quantity_apportioned × Quote%
```

Missing `replaced_quantity_apportioned` defaults to `1.0`. Any calculated
reference cost may be useful for prioritisation, but it is explicitly
non-authoritative. The downstream SRS process owns the actual financial
settlement and cost base.

## Scalable non-GALA handling

Non-GALA claims retain the main-contract route. Claims with the same
family-independent eligibility dimensions can be evaluated once and reused:

```text
contract type + technical warranty type + division + production-to-repair cap
```

Before any grouped model evaluation, the engine filters deterministic GALA
matches and insufficient-date claims. Prompts contain only de-identified
decision inputs and cited contract passages; they never include claim IDs,
VINs, supplier identifiers, or monetary values. Candidate learned rules need
expiry, source evidence, and explicit approval before promotion.

## Portable verification

`methodology/01_reproduced/mbc_gala_scenario_engine.py` reproduces matrix
matching, temporal gates, quantity apportionment, and reference-only cost
metadata from a supplied matrix. Its tests demonstrate the safe cases:

- family match wins over supplier/part fallback;
- a blocked temporal gate returns to main-contract handling;
- an undetermined Quote is review-only; and
- Quote changes accepted quantity, never the true settlement cost base.
