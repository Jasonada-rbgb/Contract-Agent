---
name: warranty-agent
description: Warranty agent development patterns for contract evaluation, claims processing, and CRA integration. Covers OpenAI Agents SDK, hybrid retrieval (BM25 + embeddings), claims batch evaluation, and Mendix CRA automation. Use when building or modifying warranty handling agents.
---

# Warranty Agent Development

## Agent Architecture (OpenAI Agents SDK)

```python
from openai_agents import Agent, function_tool

@function_tool
def retrieve_contract_context(oem: str, contract_id: str, question: str) -> dict:
    """Hybrid BM25 + vector search with LLM rerank."""
    ...

agent = Agent(
    name="ContractAgent",
    instructions="You are a warranty contract expert...",
    tools=[retrieve_contract_context, list_contracts, get_contract_profile],
)
```

## Claims Evaluation Pipeline

```
Enriched claims CSV/XLSX
    → Column mapping (CANON_MAP auto-detection + LLM fallback)
    → Load contract assets (chunks, profile, base retrieval)
    → Per-claim: shared context + row-aware retrieval
    → LLM reasoning (structured JSON decision)
    → Return: decision, confidence, contract_references
```

Decision values: `in_warranty`, `out_of_warranty`, `requires_review`, `insufficient_info`

## Contract Agent API

```
POST /api/evaluate-claims
  Body: { oem, contract_id, filename, file_base64 }
  Returns: { rows: [{decision, reason, confidence, ...}], mapping_warnings }

GET  /api/contracts?oem=JLR
  Returns: [{oem, kb_id, source}]

POST /invocations  (MLflow AgentServer chat proxy)
  Body: { input: [{role: "user", content: "..."}] }
```

## Complaint Agent API

```
POST /api/complaints/draft        -- Agent 1 handoff (ContractDecisionPayload)
POST /api/complaints/submit       -- Trigger SAP/CRA submission
POST /api/complaints/{id}/validate -- Run field validation
GET  /api/complaints/{id}          -- Draft status + next_steps
GET  /api/complaints               -- List all drafts
```

## ContractDecisionPayload (handoff schema)

```python
{
    "oem": "JLR",
    "contract_id": "jlr",
    "complaint_mode": "BA_40",
    "complaint_category": "FIELD",
    "commercial_decision": "out_of_warranty",
    "decision_reason": "Mileage exceeds 60,000 mile limit",
    "evidence_refs": ["[1]", "[3]"],
    "confidence": "high",
    "customer_data": {"customer_name": "JLR", "country": "GB"},
    "vehicle_data": {"vin": "...", "mileage_km": 120000},
    "part_data": {"customer_part_number": "LR...", "part_description": "..."},
}
```

## Mendix CRA Integration

The Complaint Agent submits to the Mendix CRA via Playwright:
- `MendixHarness` handles login, modal, section expansion, validation
- `field_registry.py` maps all ~100 fillable CRA fields
- `helpers.py` provides fill functions per input type (textbox, combobox, date, etc.)
- `PlaywrightBrowserConnector` maps `SapSubmissionPayload` to CRA fields

## Claim Routing Logic

```
Enriched claim → Status check
  ├─ "DMYA" / "Not Bosch" → skip (record only, no QC)
  └─ "Send to plant" / "Exception" → Contract Agent evaluation
      ├─ in_warranty (high confidence) → record only
      ├─ out_of_warranty → create QC in Mendix CRA
      └─ requires_review → flag for human review
```

## Key Environment Variables

```
CONTRACT_AGENT_URL    -- Base URL of Contract Agent Databricks App
COMPLAINT_AGENT_URL   -- Base URL of Complaint Agent Databricks App
AGENT1_BASE_URL       -- Contract Agent URL (from Complaint Agent's perspective)
SAP_CONNECTOR_MODE    -- mock | browser | desktop_bridge
MENDIX_USER / MENDIX_PASS -- CRA login credentials
KB_BUNDLE_BASE        -- UC Volume path for contract knowledge base chunks
```
