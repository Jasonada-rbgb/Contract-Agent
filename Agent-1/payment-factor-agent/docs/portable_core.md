# Portable Payment-Factor Core

## Why this exists

The BMW, JLR and Mercedes-Benz work proved three different payment-factor
patterns, but their original implementations are audit/reproduction code.  This
additive core separates the reusable routing mechanics from OEM-specific
evidence and evaluators without changing any proven legacy scenario engine.

It is intentionally small, dependency-free and does not contain contract text,
raw matrices, claim data, credentials, or monetary payment authority.

## Components

| Location | Responsibility |
| --- | --- |
| `payment_factor_core/` | Profile resolution, deterministic-before-cache routing, cache contract and stable group signatures. |
| `payment_factor_core/matrix_plugin.py` | Generic tabular agreement-matrix evaluator. It is configured by field names and rules; it has no Mercedes-specific content. |
| `profiles/` | Versioned starter profiles for BMW, JLR and MBC. |
| `methodology/` and `scripts/` | Existing OEM-specific evidence, reproduction and audit code; retained unchanged. |

## Runtime order

```text
approved deterministic evaluator
  -> non-expired learned rule with matching profile/fingerprint
  -> one grouped main-contract evaluation
  -> review when decision-critical fields/profile are missing
```

The deterministic evaluator always runs first.  This prevents a learned result
or an LLM response from overriding a signed agreement rule.

## Current migration state

- **MBC** is the first functional portable adapter.  Its profile supplies the
  matrix asset key, match order, temporal gates, quantity factor and safe group
  fields.  The host application supplies the approved GALA matrix at runtime.
- **BMW** and **JLR** are registered as profiles with their source references
  and safe fallback grouping.  Their validated legacy factor/rate logic remains
  the source of truth until equivalent fixed-rate and technical-outcome plugins
  are migrated with OEM regression data.

This is deliberate: a profile must never claim deterministic support merely
because a legacy script exists elsewhere.

## Host integration

The CM Tool or Contract Agent owns storage and calls the core with the resolved
profile, canonical claim values and approved assets.  For example:

```python
registry = ProfileRegistry.from_directory(Path("profiles"))
engine = PaymentFactorEngine(registry)
plan = engine.plan("MBC", "AUTO", claim, {"signed_gala_matrix": matrix}, cache)
```

`plan` makes no model or Databricks call.  A hosting service executes a
`grouped_contract_review` once per `group_key`, stores an approved learned rule
with provenance/expiry, and returns `requires_review` to a human queue.

## Extending to another OEM

1. Ingest contracts into governed storage and create a source manifest.
2. Choose a tested generic evaluator or add a narrowly scoped plugin.
3. Add a profile with asset references, canonical fields, grouping dimensions,
   approved plugin configuration and regression fixtures.
4. Validate the profile against a masked sample before enabling cache or LLM
   fallback.

Do not add OEM checks to `PaymentFactorEngine`.  OEM-specific differences belong
in a profile or an evidence-linked evaluator plugin.
