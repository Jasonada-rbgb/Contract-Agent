# Warranty Contract Agent -- Skills Reference

This document describes the capabilities ("skills") that the Warranty Contract Agent uses to answer questions, evaluate claims, and ingest new contracts. Each skill is a self-contained function with defined inputs, processing logic, and outputs.

---

## Agent Skills (LLM-invoked tools)

These skills are registered with the OpenAI Agents SDK and invoked by the LLM during Contract Q&A conversations. The agent decides when and how to call them based on the user's question and its system instructions.

### 1. List Available Contracts

| Property | Value |
|----------|-------|
| **Function** | `list_available_contracts` |
| **File** | `agent_server/agent.py` |
| **Trigger** | User asks "what contracts are available?" or similar |
| **Inputs** | `oem` (optional filter) |
| **Outputs** | List of `{oem, kb_id, source, chunk_count}` dicts |

Reads the manifest files from both the production KB bundle and the staging volume, merges them, and returns all available contracts. Optionally filters by OEM name.

---

### 2. Get Contract Profile

| Property | Value |
|----------|-------|
| **Function** | `get_contract_profile` |
| **File** | `agent_server/agent.py` |
| **Trigger** | Called automatically before every Q&A retrieval (per agent instructions) |
| **Inputs** | `oem`, `contract_id` |
| **Outputs** | Structured profile dict with `reference_market`, `export_markets`, `warranty_periods`, `market_definitions`, `key_terms`, `exclusions`, `claim_procedures`, `citations`, `verification` |

Extracts a structured profile from the contract text using an LLM, then grounds every high-impact field against cited passages. Fields that are not citation-supported are reset to safe defaults. The profile is cached in memory and persisted to Databricks Volumes for reuse.

**Sub-skills used internally:**
- **Profile excerpt selection** -- BM25 queries across fixed profile-related topics to gather the most relevant chunks
- **LLM extraction** -- Sends excerpts to Claude Opus 4.6 with a structured JSON schema prompt
- **Citation grounding** -- `_ground_contract_profile` verifies each field value against the text of its cited passages using substring matching; stores a `verification` dict per field

---

### 3. Retrieve Contract Context

| Property | Value |
|----------|-------|
| **Function** | `retrieve_contract_context` |
| **File** | `agent_server/agent.py` |
| **Trigger** | Called for every user question to find relevant contract passages |
| **Inputs** | `oem`, `contract_id`, `question`, `k` (default 20) |
| **Outputs** | `{context, sources, retrieved, retrieval_mode, profile_summary, retrieval_trace}` |

The core retrieval pipeline. Finds the most relevant contract passages for a given question using a multi-stage approach:

**Stage 1 -- Query Expansion**
- Starts with the original question
- Applies synonym expansion from a built-in map of warranty/automotive terminology (e.g. "warranty period" -> "coverage duration", "Gewährleistungsfrist")
- If the contract is non-English, translates the query and expands the translation too
- Uses profile data to inject market-specific terms (e.g. "reference market" -> "United Kingdom, Germany")

**Stage 2 -- Hybrid Retrieval**
- **BM25** (keyword): Multi-query BM25 search across all contract chunks, keeping the best score per document
- **Vector** (semantic): Multi-query cosine similarity against pre-computed GTE embeddings, keeping the best score per document
- **Combination**: Normalizes both score sets to [0,1] and combines with 50/50 weighting

**Stage 3 -- LLM Semantic Reranking**
- Pools the top 40-60 candidates
- Sends them to Claude Opus 4.6 with the original question
- Model returns a relevance-ordered ranking
- Budget-aware: skips reranking if less than 15 seconds remain in the retrieval timeout

**Stage 4 -- Output Formatting**
- Formats top-k passages with numbered citations
- Attaches profile summary (markets, warranty periods) for context
- Persists retrieval trace to session storage for auditability

**Timeout management**: The entire pipeline runs under a configurable wall-clock budget (default 180s). Each stage checks elapsed time and degrades gracefully if the budget is exceeded.

---

### 4. Get Current Time

| Property | Value |
|----------|-------|
| **Function** | `get_current_time` |
| **File** | `agent_server/agent.py` |
| **Trigger** | When the agent needs to calculate dates or check current time |
| **Inputs** | None |
| **Outputs** | Current UTC datetime string |

---

## Claims Evaluation Skills (direct code path)

These skills are not invoked by the LLM agent. They run as direct Python code when the user uploads a claims file in the Claims Evaluator mode.

### 5. Shared Contract Context Loading

| Property | Value |
|----------|-------|
| **Function** | `_load_contract_assets` |
| **File** | `agent_server/claims_batch.py` |
| **Trigger** | Once per claims batch, when evaluation starts |
| **Inputs** | `oem`, `contract_id` |
| **Outputs** | Cached `{profile, rows, bm25, embeddings, base_hits, base_context}` |

Loads the contract into memory, extracts and grounds the profile, then runs 15 fixed rule queries (warranty period, powertrain, paint, corrosion, battery/EV, exclusions, claim procedure, goodwill, labour rate, mileage limit, market definitions, service parts, PDI, consequential damage, extended warranty) to build a shared evidence base. This shared context is reused across all claim rows for efficiency.

---

### 6. Per-Row Claim Retrieval

| Property | Value |
|----------|-------|
| **Function** | `_retrieve_claim_passages` |
| **File** | `agent_server/claims_batch.py` |
| **Trigger** | Once per claim row during evaluation |
| **Inputs** | `contract_assets`, `claim_data` |
| **Outputs** | `(context_string, {scope, queries, hit_count})` |

Builds up to 4 row-specific queries from the claim's country, part description, mileage, and dates, then blends these with the shared base context using boosted scoring. Reports whether the retrieval scope was `row_aware` (targeted queries generated) or `shared_contract` (no row-specific data available).

---

### 7. Single Claim Evaluation

| Property | Value |
|----------|-------|
| **Function** | `_evaluate_single_claim` |
| **File** | `agent_server/claims_batch.py` |
| **Trigger** | Once per claim row (runs in parallel via ThreadPoolExecutor) |
| **Inputs** | `claim_data`, `profile`, `contract_passages`, `endpoint` |
| **Outputs** | `{decision, confidence, reason, rule_reference, ...}` |

Sends the claim data and contract passages to the selected evaluation model with a structured prompt. The model determines: `in_warranty`, `out_of_warranty`, `requires_review`, or `insufficient_info`, with confidence level and cited rule references. No hardcoded warranty rules -- every decision comes from the model interpreting the actual contract text.

---

### 8. Column Auto-Mapping

| Property | Value |
|----------|-------|
| **Function** | `_smart_col_lookup` |
| **File** | `agent_server/claims_batch.py` |
| **Trigger** | When a claims file is uploaded |
| **Inputs** | DataFrame columns |
| **Outputs** | `{canonical_name: actual_column}` mapping + warnings |

Maps user-provided column names (which vary across OEMs and internal systems) to canonical field names (e.g. "Repair Date", "Reparaturdatum", "repair_dt" all map to `repair_date`). Uses a fuzzy matching approach with a built-in synonym map covering English and German variants.

---

## Ingestion Skills (direct code path)

These skills run when the user uploads documents in the Ingest Contract mode.

### 9. Multi-Format Text Extraction

| Property | Value |
|----------|-------|
| **Function** | `_extract_text_by_format` |
| **File** | `agent_server/ingest.py` |
| **Trigger** | For each uploaded file during ingestion |
| **Inputs** | `file_bytes`, `filename` |
| **Outputs** | `list[{page, text}]` |

Routes each file to the appropriate extractor based on extension:

| Format | Extractor | Method |
|--------|-----------|--------|
| PDF | `_extract_text_smart` | pypdf text extraction, falls back to PyMuPDF rendering + vision OCR for scanned pages |
| MSG | `_extract_text_msg` | Subject, sender, date, body via `extract-msg`; recursively extracts attachments |
| PPTX | `_extract_text_pptx` | Slide text, table content, speaker notes via `python-pptx` |
| XLSX/XLS | `_extract_text_xlsx` | All sheets as pipe-delimited rows via `openpyxl` (max 5000 rows per sheet) |
| HTML/HTM/MHT | `_extract_text_html` | Visible text via `BeautifulSoup`; MHT MIME envelope stripped first |
| PNG/BMP/JPG | `_extract_text_image` | Vision OCR via Claude Opus 4.6; BMP converted to PNG first |

All extractors produce the same output shape: a list of `{page: int, text: str}` dicts, one per logical "page" (PDF page, email, slide, sheet, or image).

---

### 10. Sentence-Aware Chunking

| Property | Value |
|----------|-------|
| **Function** | `_chunk_text` |
| **File** | `agent_server/ingest.py` |
| **Trigger** | After text extraction, for each page of each document |
| **Inputs** | `text`, `max_chars` (default 1000), `overlap` (default 200) |
| **Outputs** | List of chunk strings |

Splits extracted text into overlapping chunks at sentence boundaries. Handles long sentences by falling back to word-level splitting. The overlap ensures that context is not lost at chunk boundaries.

---

### 11. Embedding Computation

| Property | Value |
|----------|-------|
| **Function** | `_compute_embeddings` |
| **File** | `agent_server/ingest.py` |
| **Trigger** | After chunking, for all chunks in a batch |
| **Inputs** | List of text chunks |
| **Outputs** | List of embedding vectors |

Sends chunks to the GTE Large EN embedding endpoint in batches of 50. Empty texts are replaced with "empty" to avoid API errors. Failed batches produce empty vectors (graceful degradation).

---

## Council Skill (feature-flagged)

### 12. Multi-Model Answer Synthesis

| Property | Value |
|----------|-------|
| **Function** | `run_council` |
| **File** | `agent_server/council.py` |
| **Status** | Feature-flagged off (`COUNCIL_ENABLED=false`) |
| **Trigger** | After Q&A retrieval, if council is enabled |
| **Inputs** | `question`, `evidence`, `profile_summary` |
| **Outputs** | Synthesized markdown answer |

Fans out answer generation to multiple models (Gemini 2.5 Pro, GPT-4.1, Claude Opus 4.6) in parallel using a shared evidence packet from one retrieval pass. A chair model (Gemini 2.5 Pro) then synthesizes the drafts into one final answer, preserving only citation-backed claims and preferring narrower wording when drafts disagree. This is intentionally a UI-only feature -- the API path always uses single-model answers.

---

## Skill Orchestration

In Contract Q&A, the agent's system prompt instructs it to follow this workflow:

```
1. get_contract_profile (always first)
      |
2. retrieve_contract_context (with the user's question)
      |
3. Synthesize answer using ONLY the returned context
      |
4. [Optional] Council synthesis if COUNCIL_ENABLED=true
```

In Claims Evaluation, the orchestration is hardcoded:

```
1. _load_contract_assets (once per batch)
      |
2. For each claim row (parallel):
   a. _build_claim_retrieval_queries (row-specific queries)
   b. _retrieve_claim_passages (blend with shared context)
   c. _evaluate_single_claim (LLM ruling)
      |
3. Aggregate results + CSV export
```

In Ingestion, the pipeline is sequential:

```
1. For each uploaded file:
   a. _extract_text_by_format (route to correct extractor)
   b. _chunk_text (per page)
      |
2. _compute_embeddings (all chunks)
      |
3. Write JSONL to staging volume
      |
4. Update manifest
```
