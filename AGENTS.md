# Warranty Contract Agent -- Repo Overview

## What This Repo Contains

| Directory | Purpose |
|-----------|---------|
| `Agent-1/agent-contract/agent-openai-agents-sdk/` | **Primary app** -- Warranty Contract Agent (Q&A, Claims Evaluator, Ingest) |
| `Agent-1/agent-contract-checker/` | **General-purpose clone** -- Contract Checker (Q&A + Upload only, no claims) |
| `complaint-agent/` | Separate complaint agent (independent project) |

## Architecture

- **Frontend**: Streamlit (deployed as Databricks Apps)
- **Agent Framework**: OpenAI Agents SDK via `databricks-openai`
- **LLM**: Claude Opus 4.6 (Q&A, reranking, OCR), Gemini 2.5 Flash (fast claims), o3 (deep reasoning)
- **Embeddings**: GTE Large EN
- **Storage**: Databricks Unity Catalog Volumes
- **Retrieval**: Custom hybrid BM25 + vector cosine similarity + LLM semantic reranking

## Key Principle: No Content in Code

All factual answers come from contract text stored in Databricks Volumes. The code contains retrieval logic, processing templates, and agent instructions -- never hardcoded warranty periods, market definitions, or OEM-specific rules.

## Standard Dev Entry Points

```powershell
# Start sync (local -> Databricks workspace, one-way)
.\scripts\agent-dev-up.ps1

# Deploy the app
.\scripts\agent-deploy.ps1

# Pull app logs
.\scripts\agent-capture-logs.ps1

# Run browser QA smoke test
.\scripts\agent-e2e-smoke.ps1
```

## Databricks App URLs

| App | URL | Status |
|-----|-----|--------|
| agent-contract | https://agent-contract-2236441816741128.8.azure.databricksapps.com | Production |
| agent-contract-checker | https://agent-contract-checker-2236441816741128.8.azure.databricksapps.com | Testing |

## Databricks Workspace Paths

| Resource | Path |
|----------|------|
| agent-contract source | `/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk` |
| agent-contract-checker source | `/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract-checker/agent-contract-checker` |
| Production KB bundles | `/Volumes/bci_rbs_prod/exploratory/warranty_agent/kb_store/kb_bundle_v1` |
| Staging uploads | `/Volumes/mdna_dev/warranty_agent_staging/uploads` |
| Checker contracts | `/Volumes/mdna_dev/warranty_agent_staging/contracts` |
| User sessions | `/Volumes/mdna_dev/warranty_agent_staging/user_sessions/` |
| Feedback log | `/Volumes/mdna_dev/warranty_agent_staging/feedback/` |

## Serving Endpoints

| Endpoint | Model | Used For |
|----------|-------|----------|
| `databricks-claude-opus-4-6` | Claude Opus 4.6 | Q&A, reranking, profile extraction, OCR |
| `databricks-gte-large-en` | GTE Large EN | Embeddings |
| `openai_o3` | OpenAI o3 | Deep claims reasoning |
| `gemini_25_flash` | Gemini 2.5 Flash | Fast claims evaluation |

## Contracts Currently Ingested

- **BMW** -- Gewährleistungsvereinbarung (German, Robert Bosch GmbH)
- **JLR** -- Jaguar Land Rover Warranty Agreement (English)

## Critical User Flows

1. **Contract Q&A**: Select contract(s) -> ask question -> agent retrieves context -> cited answer
2. **Claims Evaluator**: Select contract -> choose model -> upload CSV/XLSX -> parallel evaluation -> results table + CSV download
3. **Ingest Contract**: Enter OEM + Contract ID -> upload PDFs -> OCR + chunk + embed -> contract appears in sidebar
4. **Multi-contract comparison**: Select 2+ contracts -> ask comparative question -> per-contract evidence + comparison summary

## Definition of Done

- Backend Python files pass `py -m py_compile`
- App deploys successfully (`databricks apps deploy` returns SUCCEEDED)
- Q&A returns cited answers for BMW and JLR test prompts
- Claims Evaluator produces decisions (not all `requires_review`)
- No blocker console errors in app logs
- If UI changed: screenshot evidence attached
- feedback.md updated if fixing a reported issue

## Cursor Cloud Agent Instructions (Databricks Native)

Cloud Agents connect directly to Databricks -- no GitHub required.

**Secrets required** (set in Cursor Settings > Cloud > Secrets):
- `DATABRICKS_HOST` = `https://adb-2236441816741128.8.azuredatabricks.net`
- `DATABRICKS_TOKEN` = Databricks PAT

**Bootstrap** (run at the start of every Cloud Agent session):
```bash
echo -e "[DEFAULT]\nhost = ${DATABRICKS_HOST}\ntoken = ${DATABRICKS_TOKEN}" > ~/.databrickscfg
pip install databricks-sdk databricks-cli 2>/dev/null
databricks workspace export-dir "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk" ./agent-contract
```

**Push changes back**:
```bash
databricks workspace import-dir ./agent-contract "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk" --overwrite
databricks apps deploy agent-contract --source-code-path "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk"
```

## Local Cursor Instructions

- **Proxy**: `http://rb-proxy-de.bosch.com:8080` for all `databricks` CLI commands
- **Sync**: `databricks sync --watch` for real-time local -> workspace sync
- **Deploy**: `databricks apps deploy agent-contract --source-code-path <path>`
- **Python**: Use `py` launcher (not `python`) on Windows
- **Dependencies**: Pinned in `pyproject.toml`

## Automations

Three scheduled automations run as Cloud Agents (see `.cursor/automations/`):

| Automation | Trigger | Purpose |
|------------|---------|---------|
| Feedback Loop | Daily | Read feedback.md, fix OPEN issues, deploy, verify |
| Nightly Regression | Nightly | Full browser QA of all critical flows |
| Deploy QA | On-demand / hourly | Quick smoke test after deployments |

All automations use the Databricks CLI bootstrap -- no GitHub connection needed.

## Orchestrator CLI

Use the repo-native orchestrator for checkpointed multi-agent runs:

```powershell
py -m ai.orchestrator.run --task "<feedback_id|prompt>" --root "Agent-1/agent-contract/agent-openai-agents-sdk"
py -m ai.orchestrator.resume --run-id "<run_id>"
py -m ai.orchestrator.status --run-id "<run_id>"
py -m ai.orchestrator.memory --query "<text>"
```

### Cursor-Native Role Execution

The orchestrator can execute role nodes through Cursor's native subagent system instead of external model-provider prompt emulation.

- Set `ORCHESTRATOR_ROLE_PROVIDER=cursor_cli`
- Ensure the standalone Cursor Agent CLI is installed so the `agent` command exists, or set `ORCHESTRATOR_CURSOR_AGENT_COMMAND` to the full executable path
- On Windows, the desktop `cursor.exe` wrapper is not a drop-in replacement for the standalone headless `agent` CLI in non-interactive orchestrator runs

## Key Files

| File | Purpose |
|------|---------|
| `agent_server/agent.py` | Agent logic, retrieval pipeline, tools, LLM calls |
| `agent_server/claims_batch.py` | Claims evaluation engine (parallel, multi-model) |
| `agent_server/ingest.py` | PDF ingestion pipeline (OCR, chunking, embeddings) |
| `streamlit_app.py` | Main Streamlit UI (Q&A, Claims, Ingest modes) |
| `app.yaml` | Databricks App config (env vars, resources) |
| `pyproject.toml` | Dependencies and scripts |
| `eval_test_cases/bmw.json` | BMW regression test cases |
| `feedback.md` | AI-structured user feedback (synced to local) |

## Subagents

Use `@planner`, `@frontend-builder`, `@backend-builder`, `@browser-qa`, or `@reviewer` to invoke specialized agents. See `.cursor/agents/` for definitions.

## Skills

See `.cursor/skills/` for procedural know-how: `dev-up`, `seed-demo`, `e2e-smoke`, `inspect-logs`, `ui-rubric`.
