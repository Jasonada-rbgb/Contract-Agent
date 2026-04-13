# Pallet Pipeline Comparison Report

**Pallet:** BBYGRW (EQ9GE) | **Claims:** 279 | **Date:** 13 April 2026 | **Run ID:** sim_20260413_134943

---

## Summary

| Metric | Count | % |
|--------|------:|--:|
| Total Claims | 279 | 100% |
| Auto-Closed (DMYA) | 184 | 66% |
| Contract Agent Evaluated | 95 | 34% |
| **In Warranty** | **76** | **80% of evaluated** |
| Requires Review | 11 | 12% of evaluated |
| Out of Warranty | 8 | 8% of evaluated |

> **260 of 279 claims (93%) require no human action.** Only 19 claims (7%) need QC creation or human review.

---

## Before vs After

### Before: Manual Process

| Step | Claims |
|------|-------:|
| DMYA claims auto-closed | 184 |
| Claims sent to plant for investigation | 34 |
| DMYA Exceptions sent to plant | 61 |
| **Total needing manual QC creation** | **95** |
| **Estimated human hours (5 min/QC)** | **~8 hours** |

All 95 non-DMYA claims would require a QC to be manually created in the Mendix CRA, regardless of whether the claim is actually within warranty.

### After: Agent Pipeline

| Step | Claims |
|------|-------:|
| DMYA claims auto-closed | 184 |
| In-warranty claims auto-approved | 76 |
| Requires human review | 11 |
| Out-of-warranty (QC needed) | 8 |
| **Total needing manual QC creation** | **19** |
| **Estimated human hours (5 min/QC)** | **~1.5 hours** |

76 claims automatically verified as in-warranty by the Contract Agent. **80% reduction in QCs that need to be created.**

---

## Contract Agent Decision Breakdown

```
Evaluated: 95 claims

in_warranty      ████████████████████████████████████████  76  (80%)
requires_review  ██████                                    11  (12%)
out_of_warranty  ████                                       8  ( 8%)
```

---

## Warranty Rule Applied

| Market | Rule | Condition | Applied To |
|--------|------|-----------|------------|
| United Kingdom (Reference Market) | 36 months / 60,000 miles | Whichever comes sooner | All 95 evaluated claims |

Source: JLR Warranty Agreement Section 1.1.2 -- "3 years or 60,000 miles (whichever is the sooner) for K/F-Europe and Rest-of-World"

---

## Parts Analysis (Evaluated Claims Only)

| Part | Count | In Warranty | Review | Out of Warranty |
|------|------:|------------:|-------:|----------------:|
| PM SENSOR | 68 | 57 | 3 | 8 |
| NOX SENSOR [NX2] | 25 | 17 | 8 | 0 |
| DS ECU | 1 | 0 | 1 | 0 |
| GS ECU | 1 | 1 | 0 | 0 |

---

## Out of Warranty Claims (8)

| VIN | Part | Reason | Time OK | Mileage OK | Confidence |
|-----|------|--------|:-------:|:----------:|:----------:|
| `SALEA6AW1P2182999` | PM SENSOR | Repair 30 days after warranty end | No | Yes | high |
| `SALEA8AW5R2258304` | PM SENSOR | Repair after warranty expiry | No | Yes | medium |
| `SADCA2AN6PA710092` | PM SENSOR | 274,571 miles -- massively over 60k limit | Yes | No | high |
| `SALKA9AW0PA054652` | PM SENSOR | Repair after warranty end | No | Yes | high |
| `SAL1A2AW4PA115701` | PM SENSOR | Warranty expired, DMYA exception | No | Yes | medium |
| `SADCA2AN9PA704223` | PM SENSOR | 37 months in service, expired | No | Yes | medium |
| `SALKA9AW8PA058609` | PM SENSOR | Exactly at 36 months, borderline | No | Yes | medium |
| `SALEAJAW4P2233821` | PM SENSOR | 84,755 miles -- over 60k limit | Yes | No | high |

---

## Requires Review Claims (11)

| VIN | Part | Reason for Review | Confidence |
|-----|------|-------------------|:----------:|
| `SALZA2AN2TH310501` | NOX SENSOR | Water ingress in harness -- external cause? | medium |
| `SALZA2AN4TH310399` | NOX SENSOR | Water ingress in connector caused damage | medium |
| `SALZA2AN3TH312757` | NOX SENSOR | Water ingress -- investigate if defect or external | medium |
| `SALZA2ANXTH312755` | NOX SENSOR | Corrosion in connector requiring cleaning | medium |
| `SALZA2AN2TH298334` | NOX SENSOR | Corrosion in wiring pins/harness | medium |
| `SALCA2AN5TH375119` | NOX SENSOR | Water/corrosion ingress -- external cause? | medium |
| `SALZA2AN0TH291849` | NOX SENSOR | Water ingress -- may indicate external damage | medium |
| `SALZA2AN8TH303200` | NOX SENSOR | Part claimed doesn't match repair description | medium |
| `SALZA2AN1TH300428` | NOX SENSOR | Part claimed doesn't match repair (steering) | low |
| `SALYA2AN7TA831959` | DS ECU | Water ingress in PCM connector, not ECU defect | medium |
| `SALZA2AN8TH304878` | NOX SENSOR | Send to plant for investigation -- Sample Phase | medium |

**Pattern detected:** 8 of 11 review claims involve water ingress / corrosion. The Contract Agent correctly flagged these as potentially caused by external factors rather than part defects, which would affect warranty liability.

---

## Pipeline Processing Statistics

| Metric | Value |
|--------|-------|
| Total processing time | ~10 minutes (591.8s) |
| Average per claim | 6.2 seconds |
| Parallel workers | 20 |
| Reasoning model | Claude Opus 4.5 (`databricks-claude-opus-4-5`) |
| Contract KB | 52 chunks (1 document: JLR Warranty Agreement) |
| Retrieval method | Hybrid BM25 + embeddings with semantic reranking |

---

## Methodology

### Pipeline Stages

1. **Pallet Enrichment** -- SQL enrichment joins STAR label data with vehicle, claims, and MPN tables. Applies DMYA exception rules and model year threshold to assign Status per claim.

2. **Pre-filter** -- Claims with Status "Close at SQW - CAT4 - Covered by DMYA Agreement" or "Not Bosch" are auto-skipped (no contract evaluation needed).

3. **Warranty Term Resolution** -- Deep multi-query retrieval with semantic reranking extracts warranty periods, market definitions, and exclusions from the ingested contract. Results are cached per contract so this only runs once regardless of claim count.

4. **Per-Claim Evaluation** -- Each claim is evaluated by Claude Opus 4.5 against the contract passages: market identification, warranty period calculation, time/mileage checks, exclusion checks, and technician verbatim analysis for root cause indicators.

5. **Decision Output** -- Structured CSV/JSON with decision, confidence, reasoning, and QC-required flag written to UC Volume for downstream consumption by the CRA agent.

### Key Fix Applied

Resolved **retrieval depth asymmetry** between Q&A mode and claims evaluator. The claims evaluator previously used a shallow single-pass retrieval pipeline while the Q&A mode used deep iterative retrieval. The fix adds a warranty term resolution step that performs the same deep multi-query retrieval with semantic reranking, ensuring warranty periods are correctly extracted even from OCR'd scanned contract documents.

### Architecture

```
Pallet arrives (JLR STAR data)
    |
    v
Pallet Agent (Databricks Job)
    - Detect new pallets
    - Enrich via SQL (vehicle joins, Status CASE logic)
    - Generate Excel Main Reports
    |
    v
Pre-filter (claim_router.py)
    - DMYA / Not Bosch --> skip (record only)
    - Send to plant / Exception --> evaluate
    |
    v
Contract Agent (Databricks App)
    - Load contract KB (warranty agreement chunks)
    - Deep warranty term resolution (once per contract)
    - Per-claim: hybrid retrieval + rerank + LLM reasoning
    - Return: decision, confidence, reasoning, rule applied
    |
    v
Decision Output (UC Volume)
    - decision_log_{run_id}.csv
    - decision_log_{run_id}.json
    - Ready for CRA agent consumption
```
