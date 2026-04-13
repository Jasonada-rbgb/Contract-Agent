# Pallet Pipeline Comparison Report

**Pallet:** BBYGRW (EQ9GE) | **Claims:** 279 | **Date:** 13 April 2026 | **Run ID:** sim_20260413_134943

---

## Summary

| Metric | Count | % |
|--------|------:|--:|
| Total Claims | 279 | 100% |
| DMYA (closed at SQW) | 184 | 66% |
| Sent to Plant | 34 | 12% |
| DMYA Exceptions | 61 | 22% |
| **Contract Agent: In Warranty** | **76** | **80% of 95 evaluated** |
| **Contract Agent: Requires Review** | **11** | **12% of 95 evaluated** |
| **Contract Agent: Out of Warranty** | **8** | **8% of 95 evaluated** |

---

## Before vs After

### Before: Manual Process

Every claim in the pallet requires a QC to be created in the Mendix CRA, regardless of status. There are three manual tasks per pallet:

| Task | Claims | Time per QC | Total Time |
|------|-------:|------------:|-----------:|
| Create 279 QCs in Mendix CRA | 279 | 10 min | **46.5 hours** |
| Ship 95 parts to plant for investigation | 95 | 10 min | **15.8 hours** |
| Assign DMYA status to 184 QCs | 184 | 10 min | **30.7 hours** |
| **Total manual effort per pallet** | | | **93.0 hours** |

All 279 complaints are registered as QCs. 95 parts are physically shipped to the plant. The remaining 184 are closed as DMYA in the system.

### After: Agent Pipeline

The agent pipeline automates QC creation, contract evaluation, and DMYA assignment. Only claims that genuinely need human attention require manual work.

| Task | Claims | Time per QC | Total Time |
|------|-------:|------------:|-----------:|
| Agent creates 279 QCs in Mendix CRA | 279 | ~30 sec (automated) | **~2.3 hours** |
| Agent assigns DMYA status to 184 QCs | 184 | ~5 sec (automated) | **~15 min** |
| Agent evaluates 95 claims via Contract Agent | 95 | ~6 sec (automated) | **~10 min** |
| Human reviews 11 flagged claims | 11 | 10 min | **1.8 hours** |
| Human processes 8 out-of-warranty rejections | 8 | 10 min | **1.3 hours** |
| Ship 19 parts to plant (review + out-of-warranty) | 19 | 10 min | **3.2 hours** |
| **Total effort per pallet** | | | **~8.9 hours** |

Of which only **6.3 hours** is human effort -- the rest is automated.

### Time Savings

| Metric | Before (Manual) | After (Agent Pipeline) | Saving |
|--------|----------------:|-----------------------:|-------:|
| Human effort per pallet | 93.0 hours | 6.3 hours | **86.7 hours (93%)** |
| QCs created manually | 279 | 0 | **100% automated** |
| Parts shipped to plant | 95 | 19 | **80% reduction** |
| Claims needing human review | 279 | 19 | **93% reduction** |

> **93% reduction in human effort.** 76 claims that would have been shipped to the plant for investigation are automatically confirmed as in-warranty by the Contract Agent, saving unnecessary shipping and plant investigation costs.

---

## Contract Agent Decision Breakdown

Of the 95 claims that needed contract evaluation:

```
in_warranty      ████████████████████████████████████████  76  (80%)
requires_review  ██████                                    11  (12%)
out_of_warranty  ████                                       8  ( 8%)
```

| Decision | Count | What happens | Shipped to plant? |
|----------|------:|-------------|:-----------------:|
| In warranty (high confidence) | 76 | QC created, closed automatically -- no plant investigation | No |
| Requires review | 11 | QC created, flagged for human review | Yes |
| Out of warranty | 8 | QC created, rejected -- invoice dispute or charge back | Yes |

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

## Full Pallet Breakdown (All 279 Claims)

| Status | Count | QC Created | Shipped to Plant | Human Action |
|--------|------:|:----------:|:----------------:|:------------:|
| DMYA (covered by agreement) | 184 | Yes (automated) | No | None |
| In warranty (contract verified) | 76 | Yes (automated) | No | None |
| Requires review (flagged) | 11 | Yes (automated) | Yes | Review needed |
| Out of warranty (rejected) | 8 | Yes (automated) | Yes | Process rejection |
| **Total** | **279** | **279 (all automated)** | **19** | **19 claims** |

---

## Pipeline Processing Statistics

| Metric | Value |
|--------|-------|
| Total processing time | ~10 minutes (591.8s) |
| Average per claim evaluation | 6.2 seconds |
| Estimated CRA form fill time | ~30 seconds per QC |
| Estimated total CRA automation | ~2.3 hours for 279 QCs |
| Parallel evaluation workers | 20 |
| Reasoning model | Claude Opus 4.5 (`databricks-claude-opus-4-5`) |
| Contract KB | 52 chunks (1 document: JLR Warranty Agreement) |
| Retrieval method | Hybrid BM25 + embeddings with semantic reranking |

---

## Methodology

### Pipeline Stages

1. **Pallet Enrichment** -- SQL enrichment joins STAR label data with vehicle, claims, and MPN tables. Applies DMYA exception rules and model year threshold to assign Status per claim.

2. **Contract Evaluation** -- Non-DMYA claims are sent to the Contract Agent for warranty verification. Deep multi-query retrieval with semantic reranking extracts warranty periods from the ingested contract. Each claim is evaluated by Claude Opus 4.5: market identification, warranty period calculation, time/mileage checks, exclusion checks, and technician verbatim analysis.

3. **QC Creation (CRA)** -- All 279 claims get a QC created in the Mendix CRA via the headless CRA API app. DMYA claims are auto-assigned DMYA status. In-warranty claims are auto-closed. Out-of-warranty and review claims are flagged for human attention.

4. **Decision Output** -- Structured CSV/JSON decision log written to UC Volume with decision, confidence, reasoning, and QC reference for audit trail.

### Key Fix Applied

Resolved **retrieval depth asymmetry** between Q&A mode and claims evaluator. The claims evaluator previously used a shallow single-pass retrieval pipeline while the Q&A mode used deep iterative retrieval. The fix adds a warranty term resolution step that performs the same deep multi-query retrieval with semantic reranking, ensuring warranty periods are correctly extracted even from OCR'd scanned contract documents.

### Architecture

```
Pallet arrives (JLR STAR data)
    |
    v
Pallet Agent (Databricks Job -- daily 08:00)
    - Detect new pallets (skip already processed)
    - Enrich via SQL (vehicle joins, Status CASE logic)
    - Generate Excel Main Reports to UC Volume
    |
    v
Claim Router (claim_router.py)
    - ALL claims --> CRA API for QC creation
    - DMYA claims --> auto-assign DMYA status in QC
    - Non-DMYA claims --> Contract Agent evaluation
    |
    v
Contract Agent (Databricks App API)
    - Load contract KB (warranty agreement chunks)
    - Deep warranty term resolution (cached per contract)
    - Per-claim: hybrid retrieval + rerank + LLM reasoning
    - Return: in_warranty / out_of_warranty / requires_review
    |
    v
CRA App (Databricks App -- headless API)
    - Playwright + Chromium automation
    - Fill Mendix CRA form (Customer/Material/Vehicle/Complaint)
    - Create QC, return reference number
    |
    v
Decision Output (UC Volume)
    - decision_log_{run_id}.csv / .json
    - Full audit trail with contract reasoning
```
