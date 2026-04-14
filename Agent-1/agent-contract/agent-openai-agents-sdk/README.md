# Warranty Contract Agent

An AI-powered warranty contract analysis platform built on Databricks, enabling warranty professionals to query, analyze, and evaluate automotive warranty contracts using natural language.

## What It Does

| Mode | Description |
|------|-------------|
| **Contract Q&A** | Ask natural language questions about any warranty contract and receive cited, evidence-based answers |
| **Claims Evaluator** | Upload a claims dataset (CSV/XLSX) and have each claim evaluated against contract rules automatically |
| **Ingest Contract** | Upload new warranty contract PDFs to make them searchable and queryable |
| **Feedback** | Submit structured feedback to improve agent accuracy over time |

## Key Features

- **No hardcoded content** -- every answer comes from the actual contract text, not code
- **Multi-contract support** -- query and compare multiple contracts simultaneously
- **Hybrid retrieval** -- BM25 keyword search + vector cosine similarity + LLM semantic reranking
- **Multi-language** -- handles English and German contracts with automatic translation
- **Model selection** -- choose between Gemini Flash (fast), Claude Opus (accurate), or o3 (deep reasoning) for claims evaluation
- **Parallel evaluation** -- evaluates claims concurrently for speed
- **Per-user memory** -- chat history persists across sessions with browsable history
- **Inline feedback** -- thumbs up/down with optional comments on every response
- **AI thinking panel** -- see the agent's retrieval and reasoning steps in real-time

## Contracts Supported

- **BMW** -- Gewahrleistungsvereinbarung (Robert Bosch GmbH)
- **JLR** -- Jaguar Land Rover Warranty Agreement

New contracts can be ingested at any time through the app.

## Architecture

- **Frontend**: Streamlit
- **Agent Framework**: OpenAI Agents SDK
- **LLM (Q&A/Reranking)**: Claude Opus 4.6 via Databricks Model Serving
- **LLM (Claims)**: Gemini 2.5 Flash / Claude Opus / OpenAI o3 (user selectable)
- **Embeddings**: GTE Large EN via Databricks Model Serving
- **Storage**: Databricks Unity Catalog Volumes
- **Deployment**: Databricks Apps

## Project Structure

```
agent_server/
  agent.py              # Agent logic, retrieval pipeline, tools
  claims_batch.py       # Claims evaluation engine (parallel, multi-model)
  ingest.py             # PDF ingestion pipeline (OCR, chunking, embeddings)
  evaluate_agent.py     # Regression test runner
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
pyproject.toml          # Dependencies and scripts
feedback.md             # User feedback log
```

## Getting Started

### For Users

1. Navigate to the Databricks App URL
2. Select one or more contracts from the sidebar
3. Choose a mode: Q&A, Claims Evaluator, Ingest, or Feedback
4. Start asking questions or uploading data

### For Developers

```bash
# Pull app files from Databricks workspace
databricks workspace export-dir "/Workspace/Users/<you>/databricks_apps/agent-contract_*/agent-openai-agents-sdk" ./agent-contract

# Install dependencies
cd agent-contract
uv sync

# Run locally
uv run start-app

# Deploy
databricks apps deploy agent-contract --source-code-path "/Workspace/Users/<you>/databricks_apps/agent-contract_*/agent-openai-agents-sdk"

# Run evaluation
uv run agent-evaluate
```

### Multi-Agent Orchestrator (Repo Root)

From `c:\Users\ADJ1DE\Documents\Agent Workflow`:

```powershell
py -m ai.orchestrator.run --task "<feedback_id|prompt>" --root "Agent-1/agent-contract/agent-openai-agents-sdk"
py -m ai.orchestrator.resume --run-id "<run_id>"
py -m ai.orchestrator.status --run-id "<run_id>"
py -m ai.orchestrator.memory --query "<text>"
```

## Environment Variables

Configured in `app.yaml`:

| Variable | Purpose |
|----------|---------|
| `LLM_ENDPOINT` | Primary LLM for Q&A and reranking |
| `RERANK_ENDPOINT` | Semantic reranker endpoint |
| `VISION_ENDPOINT` | Vision model for OCR of scanned PDFs |
| `REASONING_ENDPOINT` | Reasoning model for claims evaluation |
| `EMBEDDING_ENDPOINT` | Embedding model for vector search |
| `KB_BUNDLE_BASE` | Production knowledge base location |
| `STAGING_BUNDLE_BASE` | Staging volume for new contracts |

## Accuracy

Verified through structured testing with 10 BMW contract test cases covering warranty periods, liability caps, cost structures, edge cases, and fabrication checks. 10/10 passed with fully accurate responses.

Regression test suite available in `eval_test_cases/`.
