# Warranty Contract Agent

An AI-powered warranty contract analysis platform built on Databricks, enabling warranty professionals to query, analyze, and evaluate automotive warranty contracts using natural language.

## What It Does

| Mode | Description |
|------|-------------|
| **Contract Q&A** | Ask natural language questions about any warranty contract and receive cited, evidence-based answers |
| **Claims Evaluator** | Upload a claims dataset (CSV/XLSX) and have each claim evaluated against contract rules automatically |
| **Ingest Contract** | Upload contract documents (PDF, MSG, PPTX, XLSX, HTML, images) to make them searchable |
| **Feedback** | Submit structured feedback to improve agent accuracy over time |

## Key Features

- **No hardcoded content** -- every answer comes from the actual contract text, not code
- **Multi-contract support** -- query and compare multiple contracts simultaneously
- **Hybrid retrieval** -- BM25 keyword search + vector cosine similarity + LLM semantic reranking
- **Multi-language** -- handles English and German contracts with automatic translation
- **Multi-format ingestion** -- PDF, Outlook email (.msg), PowerPoint, Excel, HTML/MHT, and images
- **Per-row claims retrieval** -- each claim is evaluated with row-specific contract evidence
- **Profile grounding** -- contract profiles are citation-verified before use in reasoning
- **Model selection** -- choose between Claude Opus 4.8 (accurate), GPT-4.1 (balanced), or Gemini Flash (fast) for claims
- **Parallel evaluation** -- evaluates claims concurrently for speed
- **Per-user memory** -- chat history persists across sessions with browsable history
- **Inline feedback** -- thumbs up/down with optional comments on every response
- **Thinking panel** -- live reasoning text and tool activity during Q&A, with "Thought for Xs" elapsed time

## Contracts Supported

- **BMW** -- Gewährleistungsvereinbarung (Robert Bosch GmbH)
- **JLR** -- Jaguar Land Rover Warranty Agreement

New contracts can be ingested at any time through the app.

## Architecture

- **Frontend**: Streamlit (deployed as Databricks Apps)
- **Agent Framework**: OpenAI Agents SDK via `databricks-openai`
- **LLM (Q&A / Reranking / Profile)**: Claude Opus 4.8 via Databricks Model Serving
- **LLM (Claims)**: Claude Opus 4.8 / GPT-4.1 / Gemini 2.5 Flash (user selectable)
- **Embeddings**: GTE Large EN via Databricks Model Serving
- **Storage**: Databricks Unity Catalog Volumes
- **Deployment**: Databricks Apps

## File Reference

### Core Application

| File | Purpose |
|------|---------|
| `streamlit_app.py` | Main Streamlit UI -- Q&A chat, Claims Evaluator, Ingest, Feedback modes, chat history, inline feedback, thinking panel |
| `app.yaml` | Databricks App config -- LLM endpoints, environment variables, resource permissions |
| `pyproject.toml` | Python dependencies and project scripts |
| `requirements.txt` | Pip-format dependency list |
| `databricks.yml` | Databricks bundle config for resource permissions |

### Backend (`agent_server/`)

| File | Lines | Purpose |
|------|-------|---------|
| `agent.py` | ~1440 | Core agent logic: retrieval pipeline (BM25 + vector + rerank), contract profile extraction with citation grounding, query expansion, LLM calls with timeout/retry, tool definitions (`retrieve_contract_context`, `get_contract_profile`, `list_available_contracts`), session-scoped retrieval trace persistence |
| `claims_batch.py` | ~700 | Claims evaluation engine: shared contract context loading, per-row retrieval queries, parallel claim evaluation via ThreadPoolExecutor, column auto-mapping, multi-model support |
| `council.py` | ~190 | Hidden Q&A council (feature-flagged off): fans out answer synthesis to multiple models, chair model synthesizes final answer. Intentionally UI-only, not applied to API path |
| `ingest.py` | ~850 | Document ingestion pipeline: multi-format text extraction (PDF/MSG/PPTX/XLSX/HTML/images), vision OCR for scanned docs, sentence-aware chunking, embedding computation, staging manifest management |
| `start_server.py` | ~110 | FastAPI server: `/api/contracts` (list contracts), `/api/evaluate-claims` (batch claims evaluation), MLflow integration |
| `evaluate_agent.py` | ~100 | Regression test runner using MLflow scorers against eval fixtures |
| `utils.py` | ~80 | Shared utilities: workspace client factory, OBO auth helpers |
| `__init__.py` | 1 | Package marker |

### Evaluation & Testing

| File | Purpose |
|------|---------|
| `eval_test_cases/bmw.json` | BMW Q&A regression fixtures (10 test cases covering warranty periods, liability, costs, edge cases) |
| `eval_test_cases/jlr.json` | JLR Q&A regression fixtures (warranty periods, powertrain, exclusions, markets, claims process) |
| `eval_test_cases/claims_golden.json` | Claims evaluation golden dataset (expected decisions for in-warranty, out-of-warranty, edge cases) |
| `tests/test_feedback_cycle_regressions.py` | Feedback cycle regression tests |
| `tests/test_markdown_council.py` | Council markdown output tests |

### Setup Scripts (`scripts/`)

| File | Purpose |
|------|---------|
| `quickstart.py` | One-command setup: auth, profile config, workspace discovery |
| `discover_tools.py` | Scan Databricks workspace for available serving endpoints, UC functions, volumes |
| `start_app.py` | Local app launcher (`uv run start-app`) |
| `grant_lakebase_permissions.py` | Grant Lakebase permissions for memory features |

### Config & Meta

| File | Purpose |
|------|---------|
| `AGENTS.md` | Databricks agent development guide (template-provided) |
| `.env.example` | Example environment variables for local development |
| `.gitignore` | Git exclusions |
| `feedback.md` | Structured user feedback log with lifecycle tracking (OPEN -> VERIFIED) |

## Environment Variables

Configured in `app.yaml`:

| Variable | Current Value | Purpose |
|----------|---------------|---------|
| `LLM_ENDPOINT` | `databricks-claude-opus-4-8` | Primary LLM for Q&A reasoning, reranking, profile extraction |
| `RERANK_ENDPOINT` | `databricks-claude-opus-4-8` | Semantic reranker (same as LLM for max accuracy) |
| `VISION_ENDPOINT` | `databricks-claude-opus-4-8` | Vision model for OCR of scanned PDFs and images |
| `REASONING_ENDPOINT` | `databricks-claude-opus-4-8` | Reasoning model for claims evaluation |
| `EMBEDDING_ENDPOINT` | `databricks-gte-large-en` | Embedding model for vector search |
| `KB_BUNDLE_BASE` | `/Volumes/bci_rbs_prod/.../kb_bundle_v1` | Production knowledge base location |
| `STAGING_BUNDLE_BASE` | `/Volumes/mdna_dev/.../uploads` | Staging volume for new contracts |
| `COUNCIL_ENABLED` | `false` | Multi-model Q&A council (off by default) |

## Serving Endpoints Used

| Endpoint | Status | Used For |
|----------|--------|----------|
| `databricks-claude-opus-4-8` | Active | Q&A, reranking, profile, vision OCR, claims reasoning |
| `databricks-gte-large-en` | Active | Embeddings |
| `gpt_41` | Active | Claims evaluation (user selectable) |
| `gemini_25_flash` | Active | Claims evaluation (user selectable), fast triage |
| `gemini_25_pro` | Available | Council member (when enabled) |

## Databricks Volumes

| Volume | Path | Purpose |
|--------|------|---------|
| Production KB | `/Volumes/bci_rbs_prod/exploratory/warranty_agent/kb_store/kb_bundle_v1` | Ingested contract chunks + embeddings |
| Staging uploads | `/Volumes/mdna_dev/warranty_agent_staging/uploads` | New contract uploads, staging bundles |
| User sessions | `/Volumes/mdna_dev/warranty_agent_staging/user_sessions` | Per-user chat history (JSONL) |
| Contracts | `/Volumes/mdna_dev/warranty_agent_staging/contracts` | Contract checker files |

## Getting Started

### For Users
1. Navigate to the [Databricks App](https://agent-contract-2236441816741128.8.azure.databricksapps.com)
2. Select one or more contracts from the sidebar
3. Choose a mode: Q&A, Claims Evaluator, Ingest, or Feedback
4. Start asking questions or uploading data

### For Developers
```bash
# Install dependencies
cd Agent-1/agent-contract/agent-openai-agents-sdk
uv sync

# Run locally
uv run start-app

# Deploy to Databricks
databricks workspace import-dir . "/Workspace/Users/<you>/databricks_apps/agent-contract_*/agent-openai-agents-sdk" --overwrite
databricks apps deploy agent-contract --source-code-path "/Workspace/Users/<you>/databricks_apps/agent-contract_*/agent-openai-agents-sdk"

# Run evaluation
uv run agent-evaluate
```
