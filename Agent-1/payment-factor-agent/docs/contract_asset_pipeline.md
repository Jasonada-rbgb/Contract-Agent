# Contract Asset Pipeline for Large Agreement Sets

## Purpose

This is the reusable ingestion method for a large set of short, structured
agreements that supplement a main warranty contract. It is designed for any
OEM or agreement type; Mercedes-Benz GALA is the first proven implementation.

It is separate from ordinary PDF ingestion because a table-driven agreement
must become a versioned, deterministic asset—not be rediscovered by an LLM for
every claim.

## When to use it

Use the pipeline when contracts are numerous and share a predictable,
structured decision pattern: rate schedules, part-family agreements, model
eligibility lists, technical-factor tables, or commercial side agreements.

Use ordinary Contract Agent ingestion for narrative main contracts and
unstructured reference documents. A profile can use both: a main-contract
bundle for eligibility and a compiled agreement asset for deterministic rules.

## Pipeline

```text
approved source manifest
  -> extract/OCR bundle
  -> constrained structured compiler
  -> validation and human approval
  -> versioned governed asset
  -> deterministic runtime evaluator
```

### 1. Source manifest

Create an immutable inventory before extraction. Each item needs a stable
source ID, filename, OEM, contract/agreement ID, document status, source URI,
and source checksum. Record missing files and OCR failures; do not silently
drop them.

### 2. Extract/OCR bundle

Extract native PDF text first and use approved OCR only when native text is
empty or unusable. For short table-driven agreements, preserve one complete
document per bundle item rather than splitting tables across generic chunks.
Store text with its manifest metadata and extraction provenance. This
intermediate bundle is not a production rule asset and does not itself imply
that source PDFs were uploaded or embedded.

### 3. Constrained structured compiler

Compile each usable bundle item with an agreement-type-specific schema and a
low-temperature structured-output prompt. The compiler must:

- extract every table across every page;
- emit one rule per logical table row;
- keep identifier types separate (for example family, supplier and part IDs);
- normalise numbers and dates while retaining raw values where interpretation
  matters;
- represent unknown values as `null`, never invented defaults;
- retain source filename, source ID, compiler version and document status on
  each emitted rule.

The prompt/schema belongs to a versioned compiler profile. Do not copy an
OEM-specific prompt into the shared Contract Agent code.

### 4. Validate and approve

Validation is mandatory before publication:

- reconcile manifest count, extracted count, skipped count, error count and
  compiled row count;
- reject invalid rates, impossible date ranges and mixed identifier types;
- surface unknown/null decision values for review;
- sample-check source rows against the original agreements;
- record assumptions that need business approval;
- fingerprint the approved output and retain the compiler/profile version.

Only an approved, fingerprinted output can become a runtime deterministic
asset.

### 5. Publish governed assets

Keep source PDFs, OCR bundle, compiler logs and compiled matrix in governed
storage. The application profile references approved asset URIs and versions;
Git contains code, schemas and provenance rules only. Refreshing an agreement
set creates a new version—it must not overwrite a live asset in place.

## Runtime rule

The Contract Agent/payment-factor service resolves the active contract profile
first. It applies a matching signed matrix before learned cache or LLM work. If
no agreement rule matches, or an agreement gate does not apply, the claim
returns to the main-contract route. A missing decision-critical value returns
`requires_review` or `insufficient_info`; it must not be grouped into an LLM
call or receive an inferred agreement rate.

## Handover implementation checklist

1. Add a contract-asset profile registry in the host environment.
2. Store manifests, bundles, compiler outputs and approval fingerprints in
   governed Unity Catalog storage.
3. Implement a reusable compiler profile interface for structured agreement
   types.
4. Integrate approved deterministic assets through `payment_factor_core`
   profiles and plugins.
5. Add reconciliation and regression fixtures before onboarding a new OEM.

The original MBC batch scripts are reference material only: they contain local
paths and a GALA-specific extraction schema. Reuse this pipeline contract, not
those deployment details verbatim.
