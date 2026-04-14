# Warranty Contract Agent

**An AI-powered warranty contract analysis platform built on Databricks**

Developed by the Warranty Agent team at Robert Bosch GmbH, this application enables warranty professionals to query, analyze, and evaluate automotive warranty contracts using natural language -- with every answer grounded in the actual contract text.

---

## What It Does

The Warranty Contract Agent is a Streamlit-based web application deployed as a Databricks App. It operates in three modes:

| Mode | Purpose |
|------|---------|
| **Contract Q&A** | Ask natural language questions about any warranty contract and receive cited, evidence-based answers |
| **Claims Evaluator** | Upload a claims dataset (CSV/XLSX) and have each claim evaluated against contract rules automatically |
| **Ingest Contract** | Upload new warranty contract PDFs to make them searchable and queryable |

### Contracts Currently Supported

- **BMW** -- Gewährleistungsvereinbarung (Robert Bosch GmbH)
- **JLR** -- Jaguar Land Rover Warranty Agreement

New contracts can be ingested at any time through the app's upload interface.

---

## Architecture

![Architecture](assets/architecture_diagram.png)

---

## Contract Q&A -- How It Works

When a user asks a question about a warranty contract, the agent follows a structured retrieval-augmented generation (RAG) pipeline:

![Contract Q&A Flow](assets/qa_sequence_diagram.png)

### Key Design Principle: No Content in Code

Every factual answer comes directly from the contract text stored in Databricks Volumes. The application code contains:

- **Retrieval logic** -- how to search and rank passages (BM25, embeddings, reranking)
- **Processing templates** -- what structure to extract (warranty periods, markets, exclusions)
- **Agent instructions** -- workflow rules (always retrieve before answering, cite sources)

The code **never** contains hardcoded warranty periods, market definitions, cost figures, or OEM-specific rules. This means the same codebase works correctly for any contract -- BMW, JLR, or any future OEM -- without code changes.

### Multi-Contract Support

Users can select multiple contracts simultaneously from the sidebar. When querying across contracts, the agent:

1. Retrieves profile and context for **each** contract independently
2. Presents findings **per contract** with separate evidence sections
3. Provides a **comparison summary** highlighting key differences

This enables side-by-side analysis such as: *"Compare the warranty periods for BMW vs. JLR in North America."*

---

## Claims Evaluator -- How It Works

The Claims Evaluator takes a dataset of warranty claims and evaluates each one against the selected contract's rules using a dedicated reasoning model.

![Claims Evaluator Flow](assets/claims_evaluator_flow.png)

### Smart Column Mapping

Claims datasets come in many formats -- English headers, German headers (e.g., *Reparaturdatum*, *Kilometerstand*, *Fahrgestellnummer*), or OEM-specific naming conventions. The system handles this through a two-tier approach:

1. **Deterministic mapping** -- A comprehensive lookup table with 16 canonical fields and their common aliases in English and German
2. **LLM fallback** -- For columns that don't match any known alias, the system sends the column names plus sample data to the LLM, which interprets the meaning and maps accordingly

Before evaluation begins, the user sees a **column mapping preview** showing how each dataset column was interpreted, with warnings for any critical fields that couldn't be mapped.

### Contract-Driven Evaluation

Each claim is evaluated by the OpenAI o3 reasoning model with:

- The full **contract profile** (structured metadata: markets, warranty periods, exclusions, key terms)
- **50 relevant contract passages** covering all warranty categories
- The **claim data** (VIN, country, dates, mileage, part description, costs)

The model returns a structured decision:

| Field | Description |
|-------|-------------|
| `decision` | `in_warranty`, `out_of_warranty`, `insufficient_info`, or `requires_review` |
| `applicable_rule` | Which market category and warranty period applies, and why |
| `time_ok` / `mileage_ok` | Whether the claim falls within time and mileage limits |
| `warranty_end_date` | Calculated end date based on applicable rule |
| `reason` | Step-by-step explanation citing specific contract terms |
| `exclusions_checked` | List of exclusions considered and whether they apply |
| `confidence` | `high`, `medium`, or `low` |
| `contract_references` | Passage numbers from the contract supporting the decision |

---

## Contract Ingestion

New contracts can be added directly through the app without any code changes:

![Contract Ingestion Pipeline](assets/ingestion_pipeline.png)

The ingestion pipeline:

1. **Uploads** PDFs to the staging volume
2. **Extracts text** using a vision-capable model (handles scanned/image-based PDFs)
3. **Chunks** the text into searchable passages
4. **Generates embeddings** for vector search
5. **Writes** the chunk bundle and updates the contract manifest

Once ingested, the new contract appears in the sidebar dropdown and is immediately queryable.

---

## Retrieval Pipeline -- Technical Detail

The retrieval system uses a hybrid approach combining lexical and semantic search for maximum recall:

![Retrieval Pipeline](assets/retrieval_pipeline.png)

### Why Hybrid Search?

| Component | Strength | Weakness |
|-----------|----------|----------|
| **BM25** | Exact keyword matching, handles contract-specific terminology | Misses semantic equivalents |
| **Vector search** | Understands meaning, finds paraphrases | Can miss exact legal terms |
| **Hybrid** | Best of both -- catches exact terms AND semantic equivalents | -- |
| **LLM reranking** | Understands question intent deeply, eliminates false positives | Cost per query (mitigated by batching) |

### Multi-Language Support

Contracts may be in English (JLR) or German (BMW). The system:

1. Detects the contract language from the stored chunks
2. If the question is in a different language, translates it
3. Runs synonym expansion on both the original and translated queries
4. Searches with all query variants for maximum coverage

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit |
| **Agent Framework** | OpenAI Agents SDK (openai-agents) |
| **LLM -- Q&A / Reranking** | Claude Opus 4.6 via Databricks Model Serving |
| **LLM -- Claims Reasoning** | OpenAI o3 via Databricks Model Serving |
| **Embeddings** | GTE Large EN via Databricks Model Serving |
| **Search** | Custom hybrid BM25 + cosine similarity |
| **Storage** | Databricks Unity Catalog Volumes |
| **Tracing / Evaluation** | MLflow 3 |
| **Deployment** | Databricks Apps |
| **Language** | Python 3.11+ |

---

## Accuracy and Evaluation

The agent's accuracy has been verified through a structured testing methodology:

### Verification Process

1. **Source document review** -- The actual contract PDF is read page by page
2. **Targeted prompts** -- 10 test prompts covering core facts, financial details, edge cases, German-language queries, and stress-test scenarios
3. **Cross-referencing** -- Every factual claim in the agent's response is compared against the source document

### BMW Contract Test Results

| Test Category | Result |
|---------------|--------|
| Warranty periods (NA vs. RoW) | Correct |
| High-voltage battery terms | Correct |
| Liability cap (EUR 50M + exceptions) | Correct |
| Pauschalfaktoren (cost multipliers by continent) | Correct |
| Serial defect cost structure (45%, I-Stufe, per-vehicle) | Correct |
| Late failure percentages | Correct |
| Effective date and transitional rules | Correct |
| Goodwill extension (applicability + obligations) | Correct |
| Scenario reasoning (40 months, Germany, standard part) | Correct |
| Fabrication check (unanswerable question) | Correctly refused |

**10/10 test cases passed with fully accurate responses.**

### Regression Testing

A reusable test suite (`eval_test_cases/bmw.json`) captures these verified test cases with expected facts. After any code change, the suite can be re-run to ensure accuracy has not degraded:

```
uv run agent-evaluate           # run all test cases
uv run agent-evaluate --oem BMW # run BMW cases only
```

New contracts are added by dropping a JSON file in the `eval_test_cases/` directory.

---

## Project Structure

```
agent-openai-agents-sdk/
  agent_server/
    agent.py              # Agent logic, retrieval pipeline, tools
    claims_batch.py       # Claims evaluation engine
    evaluate_agent.py     # Regression test runner
    ingest.py             # PDF ingestion pipeline
    start_server.py       # FastAPI server (MLflow integration)
    utils.py              # Shared utilities
  eval_test_cases/
    bmw.json              # BMW verified test cases
  scripts/
    quickstart.py         # One-command setup
    discover_tools.py     # Workspace resource discovery
    start_app.py          # Local app launcher
  streamlit_app.py        # Main application UI
  app.yaml                # Databricks App configuration
  databricks.yml          # Bundle deployment config
  pyproject.toml          # Dependencies and scripts
```

---

## Getting Started

### For Users

1. Navigate to the Databricks App URL
2. Select one or more contracts from the sidebar
3. Choose a mode: Q&A, Claims Evaluator, or Ingest
4. Start asking questions or uploading data

### For Developers

```bash
# Clone and set up
databricks workspace export-dir "/Workspace/Users/.../agent-contract" ./agent-contract
cd agent-contract/agent-openai-agents-sdk

# Install dependencies
uv sync

# Configure authentication
uv run quickstart

# Run locally
uv run start-app

# Deploy
databricks bundle deploy && databricks bundle run agent_openai_agents_sdk

# Run evaluation
uv run agent-evaluate
```

---

*Built with Databricks, OpenAI Agents SDK, and MLflow.*
