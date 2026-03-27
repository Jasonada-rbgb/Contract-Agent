import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, AsyncGenerator

import litellm
import mlflow
from agents import Agent, ModelSettings, Runner, function_tool, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from databricks.sdk import WorkspaceClient
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.utils import (
    build_mcp_url,
    get_session_id,
    get_user_workspace_client,
    process_agent_stream_events,
)

try:
    set_default_openai_client(AsyncDatabricksOpenAI())
    set_default_openai_api("chat_completions")
    set_trace_processors([])
    mlflow.openai.autolog()
except Exception:
    pass
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
litellm.suppress_debug_info = True

log = logging.getLogger(__name__)


@function_tool
def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().isoformat()


def _require_env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise ValueError(f"Missing required environment variable: {name}")
    return v


# ============================================================================
# Volume / endpoint helpers
# ============================================================================

TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _tok(s: str) -> list[str]:
    return TOKEN_RE.findall((s or "").lower())


def _bundle_base() -> str:
    v = (os.getenv("KB_BUNDLE_BASE") or "").strip().rstrip("/")
    return v


def _staging_bundle_base() -> str:
    v = (os.getenv("STAGING_BUNDLE_BASE") or "").strip().rstrip("/")
    if v:
        return f"{v}/kb_bundle"
    return ""


def _read_volume_file(wc: WorkspaceClient, path: str) -> bytes:
    resp = wc.files.download(path)
    return resp.contents.read()


def _llm_endpoint() -> str:
    """Endpoint used for reranking & profile extraction (strongest available)."""
    return (
        os.getenv("RERANK_ENDPOINT")
        or os.getenv("LLM_ENDPOINT")
        or "gpt_41"
    ).strip()


def _embedding_endpoint() -> str:
    return (os.getenv("EMBEDDING_ENDPOINT") or "databricks-gte-large-en").strip()


def _call_llm(prompt: str, max_tokens: int = 16000, temperature: float | None = 0.0,
              endpoint: str | None = None) -> str | None:
    ep = (endpoint or _llm_endpoint()).strip()
    if not ep:
        return None
    try:
        wc = get_user_workspace_client()
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
        kwargs: dict = {
            "name": ep,
            "messages": [ChatMessage(role=ChatMessageRole.USER, content=prompt)],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = wc.serving_endpoints.query(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("LLM call failed (%s): %s", ep, e)
        return None


# ============================================================================
# Embedding & vector search (in-memory cosine similarity)
# ============================================================================

def _embed_query(text: str) -> list[float] | None:
    """Embed a query string using the embedding serving endpoint."""
    ep = _embedding_endpoint()
    if not ep:
        return None
    try:
        wc = get_user_workspace_client()
        resp = wc.serving_endpoints.query(name=ep, input=[text])
        return resp.data[0].embedding
    except Exception as e:
        log.warning("Embedding call failed (%s): %s", ep, e)
        return None


def _embed_queries(texts: list[str]) -> list[list[float] | None]:
    """Embed multiple query strings in one batch call."""
    ep = _embedding_endpoint()
    if not ep or not texts:
        return [None] * len(texts)
    try:
        wc = get_user_workspace_client()
        resp = wc.serving_endpoints.query(name=ep, input=texts)
        return [item.embedding for item in resp.data]
    except Exception as e:
        log.warning("Batch embedding call failed (%s): %s", ep, e)
        return [None] * len(texts)


def _cosine_topk(
    query_emb: list[float],
    embeddings: list[list[float]],
    k: int = 50,
) -> list[tuple[int, float]]:
    """Return top-k (doc_id, cosine_similarity) from pre-computed embeddings."""
    if not query_emb or not embeddings:
        return []
    # Manual cosine similarity (no numpy dependency in the app)
    q_norm = math.sqrt(sum(x * x for x in query_emb))
    if q_norm == 0:
        return []
    scores: list[tuple[int, float]] = []
    for i, emb in enumerate(embeddings):
        if not emb:
            continue
        dot = sum(a * b for a, b in zip(query_emb, emb))
        e_norm = math.sqrt(sum(x * x for x in emb))
        if e_norm == 0:
            continue
        scores.append((i, dot / (q_norm * e_norm)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:k]


# ============================================================================
# Language detection & translation
# ============================================================================

_DE_STOPWORDS = frozenset(
    "der die das ein eine einer eines einem den dem und oder aber wenn"
    " ist sind war waren hat haben wird werden kann k\u00f6nnen nicht auch"
    " f\u00fcr mit von auf aus bei nach \u00fcber unter durch".split()
)

_CONTRACT_LANG_CACHE: dict[tuple[str, str], str] = {}


def _detect_language(rows: list[dict[str, Any]]) -> str:
    sample_text = " ".join(
        (r.get("text") or "")[:200] for r in rows[:50]
    ).lower()
    tokens = TOKEN_RE.findall(sample_text)
    if not tokens:
        return "en"
    de_count = sum(1 for t in tokens if t in _DE_STOPWORDS)
    return "de" if de_count / len(tokens) > 0.08 else "en"


def _translate_query(question: str, target_lang: str) -> str | None:
    lang_name = {"de": "German", "en": "English", "fr": "French"}.get(target_lang, target_lang)
    prompt = (
        f"Translate the following question into {lang_name}. "
        f"Return ONLY the translated text, nothing else.\n\n{question}"
    )
    translated = _call_llm(prompt)
    if translated and len(translated) >= 3 and translated.lower() != question.lower():
        return translated
    return None


# ============================================================================
# Query expansion: synonym map
# ============================================================================

_SYNONYM_MAP: dict[str, list[str]] = {
    "reference market":     ["home market", "domestic market", "local market",
                             "base market", "reference territory",
                             "heimatmarkt", "referenzmarkt"],
    "export market":        ["foreign market", "overseas market",
                             "non-reference market", "non-domestic market",
                             "exportmarkt", "auslandsmarkt"],
    "goodwill":             ["gesture of goodwill", "commercial gesture",
                             "ex-gratia", "kulanz", "kulanzmassnahme"],
    "wear and tear":        ["wear & tear", "normal wear", "fair wear",
                             "verschleiss", "abnutzung"],
    "warranty period":      ["warranty duration", "coverage period",
                             "warranty term", "garantiezeit",
                             "gew\u00e4hrleistungsfrist"],
    "mileage limit":        ["mileage cap", "distance limit", "mileage threshold",
                             "kilometergrenze", "laufleistung"],
    "service parts":        ["maintenance parts", "consumable parts",
                             "wear parts", "verschleissteile"],
    "production parts":     ["oem parts", "original parts", "genuine parts",
                             "originalteile", "erstauser\u00fcsterteile"],
    "powertrain":           ["drivetrain", "engine and transmission",
                             "motor and gearbox", "antriebsstrang"],
    "paint warranty":       ["paint defect", "paintwork warranty",
                             "surface finish", "lackgarantie"],
    "corrosion warranty":   ["perforation warranty", "rust through",
                             "body corrosion", "korrosionsgarantie",
                             "durchrostungsgarantie"],
    "labour rate":          ["labor rate", "workshop rate", "hourly rate",
                             "stundensatz", "arbeitslohn"],
    "claim submission":     ["claim filing", "claim lodging", "warranty claim",
                             "reklamation", "garantieantrag"],
    "pre-delivery inspection": ["pdi", "pre-delivery check",
                                "auslieferungsinspektion"],
    "whichever comes first": ["whichever sooner", "whichever occurs first",
                              "whichever is earlier"],
    "consequential damage":  ["consequential loss", "indirect damage",
                              "folgeschaden"],
}


def _expand_query(
    question: str,
    profile: dict[str, Any] | None = None,
) -> list[str]:
    queries = [question]
    q_lower = question.lower()

    for canonical, synonyms in _SYNONYM_MAP.items():
        if canonical in q_lower:
            for syn in synonyms[:3]:
                variant = q_lower.replace(canonical, syn)
                if variant != q_lower:
                    queries.append(variant)

    if profile:
        market_defs = profile.get("market_definitions") or {}
        ref_markets = profile.get("reference_market") or []
        key_terms = profile.get("key_terms") or {}

        if "reference market" in q_lower and ref_markets:
            for country in ref_markets[:3]:
                queries.append(q_lower.replace("reference market", country.lower()))

        for term, definition in {**market_defs, **key_terms}.items():
            term_norm = term.replace("_", " ").lower()
            if term_norm in q_lower and definition:
                queries.append(f"{question} {definition[:80]}")

    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q_stripped = q.strip()
        if q_stripped and q_stripped not in seen:
            seen.add(q_stripped)
            unique.append(q_stripped)
    return unique


# ============================================================================
# BM25
# ============================================================================

class _BM25:
    def __init__(self, docs_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.N = len(docs_tokens)
        self.doc_len = [len(t) for t in docs_tokens]
        self.avgdl = sum(self.doc_len) / max(1, self.N)
        self.df = Counter()
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, toks in enumerate(docs_tokens):
            tf = Counter(toks)
            for term, f in tf.items():
                self.df[term] += 1
                self.postings[term].append((i, f))
        self.idf = {
            t: math.log(1 + (self.N - df + 0.5) / (df + 0.5))
            for t, df in self.df.items()
        }

    def topk(self, query: str, k: int = 20) -> list[tuple[int, float]]:
        q = _tok(query)
        scores: dict[int, float] = defaultdict(float)
        for term in q:
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for doc_id, f in self.postings[term]:
                dl = self.doc_len[doc_id]
                denom = f + self.k1 * (1 - self.b + self.b * (dl / max(1e-9, self.avgdl)))
                scores[doc_id] += idf * (f * (self.k1 + 1) / denom)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]


# ============================================================================
# Contract loading & cache
# ============================================================================

_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _load_contract(oem: str, kb_id: str):
    key = (oem, kb_id)
    if key in _CACHE:
        return

    wc = get_user_workspace_client()

    bases: list[str] = []
    prod = _bundle_base()
    if prod:
        bases.append(prod)
    stg = _staging_bundle_base()
    if stg:
        bases.append(stg)

    json_files: list[str] = []
    for base in bases:
        candidate = f"{base}/chunks_json/oem={oem}/kb_id={kb_id}"
        try:
            entries = list(wc.files.list_directory_contents(candidate))
            # Prefer files with embeddings
            emb_files = [
                f.path for f in entries
                if (not f.is_directory) and "with-embeddings" in f.path
            ]
            plain_files = [
                f.path for f in entries
                if (not f.is_directory) and f.path.endswith(".json")
                and "with-embeddings" not in f.path
            ]
            # Use embedding-enriched file if available, else plain
            json_files = emb_files or plain_files
            if json_files:
                break
        except Exception:
            continue

    if not json_files:
        raise RuntimeError(f"No chunk files found for oem={oem}, kb_id={kb_id}")

    rows: list[dict[str, Any]] = []
    embeddings: list[list[float]] = []
    has_embeddings = False

    for p in json_files:
        raw = _read_volume_file(wc, p).decode("utf-8", errors="ignore")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                emb = rec.pop("embedding", None)
                rows.append(rec)
                if emb and isinstance(emb, list) and len(emb) > 100:
                    embeddings.append(emb)
                    has_embeddings = True
                else:
                    embeddings.append([])
            except Exception:
                continue

    if not rows:
        raise RuntimeError(f"Chunk files found but no rows parsed for oem={oem}, kb_id={kb_id}")

    bm25 = _BM25([_tok(r.get("text", "")) for r in rows])
    cache_entry: dict[str, Any] = {"rows": rows, "bm25": bm25}

    if has_embeddings and len(embeddings) == len(rows):
        cache_entry["embeddings"] = embeddings
        log.info("Loaded %d chunks with embeddings for %s/%s", len(rows), oem, kb_id)
    else:
        log.info("Loaded %d chunks (no embeddings) for %s/%s", len(rows), oem, kb_id)

    _CACHE[key] = cache_entry


# ============================================================================
# Contract Profile  (tuned for max accuracy)
# ============================================================================

_PROFILE_CACHE: dict[tuple[str, str], dict[str, Any]] = {}

_PROFILE_PROMPT = """You are a warranty contract analyst. Analyze the following contract excerpts and extract structured metadata.

Return ONLY valid JSON matching this schema (no markdown, no explanation):
{{
  "contract_language": "en or de or fr",
  "oem": "manufacturer name",
  "reference_market": ["country1", "country2"],
  "export_markets": ["region1", "region2"],
  "market_definitions": {{
    "reference_market": "exact quote or paraphrase defining reference/home market",
    "export_market": "exact quote or paraphrase defining export/foreign market"
  }},
  "warranty_periods": [
    {{
      "market": "reference_market or export_market or north_america or ...",
      "component": "general or powertrain or paint or corrosion or battery or ...",
      "months": 36,
      "mileage": 60000,
      "unit": "miles or km",
      "whichever_sooner": true
    }}
  ],
  "key_terms": {{
    "term_name": "contract-specific definition or meaning"
  }},
  "exclusions": ["list of explicitly excluded items or conditions"],
  "claim_procedures": {{
    "submission_deadline_days": null,
    "approval_required": true,
    "documentation_needed": ["list of required documents"]
  }},
  "citations": {{
    "reference_market": [1, 5],
    "warranty_periods": [3, 7, 12]
  }}
}}

Rules:
- Extract ONLY what is explicitly stated in the excerpts
- For citations, use the [n] numbers from the excerpts
- If a field cannot be determined, use null or empty array
- "key_terms" should capture any contract-specific definitions
- Be thorough: include ALL warranty periods, ALL market definitions, ALL key terms

Contract excerpts:
{context}"""


def _extract_contract_profile(
    oem: str, kb_id: str, rows: list[dict[str, Any]], bm25: _BM25,
) -> dict[str, Any]:
    key = (oem, kb_id)
    if key in _PROFILE_CACHE:
        return _PROFILE_CACHE[key]

    persisted = _load_persisted_profile(oem, kb_id)
    if persisted:
        _PROFILE_CACHE[key] = persisted
        return persisted

    # Gather intro chunks (first 15 -- contracts front-load definitions)
    chunk_ids: set[int] = set()
    for i in range(min(15, len(rows))):
        chunk_ids.add(i)

    # Expanded profile queries for thorough extraction
    profile_queries = [
        "reference market home market domestic market",
        "export market foreign market overseas",
        "warranty period duration months mileage kilometers",
        "labour rate labor rate workshop rate",
        "paint warranty corrosion warranty body warranty",
        "powertrain engine transmission drivetrain warranty",
        "definitions terms glossary",
        "exclusions excluded not covered limitations",
        "claim submission procedure process approval",
        "battery warranty electric vehicle EV hybrid",
        "goodwill gesture commercial discretion kulanz",
        "pre-delivery inspection PDI",
    ]
    for pq in profile_queries:
        for doc_id, _ in bm25.topk(pq, k=8):
            chunk_ids.add(doc_id)
            if len(chunk_ids) >= 80:
                break

    selected = sorted(chunk_ids)
    numbered_chunks = []
    for i, cid in enumerate(selected, 1):
        txt = (rows[cid].get("text") or "").strip()[:1200]
        if txt:
            numbered_chunks.append(f"[{i}] {txt}")

    context = "\n\n".join(numbered_chunks)
    prompt = _PROFILE_PROMPT.format(context=context)

    # Use Claude Opus for profile extraction (strongest model)
    raw = _call_llm(prompt, temperature=0.0)
    if not raw:
        profile: dict[str, Any] = {"oem": oem, "_status": "extraction_failed"}
        _PROFILE_CACHE[key] = profile
        return profile

    raw_clean = raw.strip()
    if raw_clean.startswith("```"):
        raw_clean = re.sub(r"^```(?:json)?\s*", "", raw_clean)
        raw_clean = re.sub(r"\s*```$", "", raw_clean)

    try:
        profile = json.loads(raw_clean)
    except json.JSONDecodeError:
        profile = {"oem": oem, "_status": "parse_failed", "_raw": raw[:500]}

    profile.setdefault("oem", oem)
    profile["_kb_id"] = kb_id
    profile["_status"] = "ok"
    _PROFILE_CACHE[key] = profile
    _persist_profile(oem, kb_id, profile)
    return profile


def _persist_profile(oem: str, kb_id: str, profile: dict[str, Any]):
    staging = _staging_bundle_base()
    if not staging:
        return
    path = f"{staging}/profiles/oem={oem}/kb_id={kb_id}/profile.json"
    try:
        wc = get_user_workspace_client()
        import io
        data = json.dumps(profile, indent=2, ensure_ascii=False).encode("utf-8")
        wc.files.upload(path, io.BytesIO(data), overwrite=True)
        log.info("Persisted contract profile to %s", path)
    except Exception as e:
        log.debug("Could not persist profile (non-fatal): %s", e)


def _load_persisted_profile(oem: str, kb_id: str) -> dict[str, Any] | None:
    staging = _staging_bundle_base()
    if not staging:
        return None
    path = f"{staging}/profiles/oem={oem}/kb_id={kb_id}/profile.json"
    try:
        wc = get_user_workspace_client()
        raw = _read_volume_file(wc, path).decode("utf-8", errors="ignore")
        return json.loads(raw)
    except Exception:
        return None


# ============================================================================
# Context formatting
# ============================================================================

def _format_context(
    rows: list[dict[str, Any]],
    hits: list[tuple[int, float]],
    k: int,
    per_chars: int = 2000,
) -> tuple[str, str]:
    """Format retrieved hits into numbered context snippets.

    per_chars=2000 gives the LLM fuller passages for more accurate answers.
    """
    snippets = []
    sources = []
    used = set()
    n = 1
    for doc_id, _score in hits:
        r = rows[doc_id]
        dedup_key = (r.get("source_path"), r.get("element_pos"), r.get("chunk_idx"))
        if dedup_key in used:
            continue
        txt = (r.get("text") or "").strip()
        if not txt:
            continue
        if len(txt) < 40 and not any(c.isdigit() for c in txt):
            continue
        used.add(dedup_key)
        snippets.append(f"[{n}] {txt[:per_chars]}")
        sources.append(
            f"[{n}] {r.get('source_path')} (pos={r.get('element_pos')}, chunk={r.get('chunk_idx')})"
        )
        n += 1
        if n > k:
            break
    return "\n\n".join(snippets), "\n".join(sources)


# ============================================================================
# Semantic reranking  (tuned for max accuracy)
# ============================================================================

def _rerank_snippets(
    question: str,
    rows: list[dict[str, Any]],
    hits: list[tuple[int, float]],
    top_k: int = 20,
) -> list[tuple[int, float]]:
    """LLM-based semantic reranking.

    Uses full candidate pool (up to 120) and 600 chars per passage for
    maximum relevance discrimination.
    """
    if len(hits) <= top_k:
        return hits[:top_k]

    rerank_pool = min(120, len(hits))
    candidates = []
    for doc_id, score in hits[:rerank_pool]:
        txt = (rows[doc_id].get("text") or "")[:600]
        candidates.append({"idx": doc_id, "score": score, "text": txt})

    numbered = "\n".join(
        f"{i+1}. {c['text'][:500]}" for i, c in enumerate(candidates)
    )

    prompt = (
        f"You are an expert warranty contract analyst ranking passages by relevance.\n\n"
        f"Question: {question}\n\n"
        f"Below are {len(candidates)} passages from a warranty contract. "
        f"Rank them by semantic relevance to the question. "
        f"Consider synonyms, paraphrases, related concepts, and indirect relevance "
        f"(e.g. a passage defining a term used in the question).\n\n"
        f"Return a JSON array of the top {top_k} passage numbers (1-indexed), "
        f"most relevant first. Example: [3,1,7,12,5,8,2,15,20,11,6,4,9,14,17,19,16,13,10,18]\n"
        f"Return ONLY the JSON array, no explanation.\n\n{numbered}"
    )

    text = _call_llm(prompt, temperature=0.0)
    if text:
        indices = []
        for tok in re.findall(r"\d+", text):
            idx = int(tok) - 1
            if 0 <= idx < len(candidates):
                indices.append(idx)
        if len(indices) >= top_k // 2:
            seen: set[int] = set()
            reranked: list[tuple[int, float]] = []
            for i in indices:
                c = candidates[i]
                if c["idx"] not in seen:
                    seen.add(c["idx"])
                    reranked.append((c["idx"], c["score"]))
            if reranked:
                return reranked[:top_k]

    return hits[:top_k]


# ============================================================================
# Multi-query BM25 + vector hybrid retrieval  (tuned for max accuracy)
# ============================================================================

def _multi_query_bm25(
    bm25: _BM25, queries: list[str], k: int,
) -> list[tuple[int, float]]:
    combined: dict[int, float] = {}
    for q in queries:
        for doc_id, score in bm25.topk(q, k=k):
            if doc_id not in combined or score > combined[doc_id]:
                combined[doc_id] = score
    return sorted(combined.items(), key=lambda x: x[1], reverse=True)[:k]


def _multi_query_vector(
    queries: list[str],
    embeddings: list[list[float]],
    k: int,
) -> list[tuple[int, float]]:
    """Vector search with multiple query embeddings (multi-query expansion).

    Embeds up to 5 query variants and takes the best cosine similarity
    per document across all query variants.
    """
    if not embeddings:
        return []

    # Limit to 5 query variants to control cost/latency
    query_subset = queries[:5]
    query_embs = _embed_queries(query_subset)

    combined: dict[int, float] = {}
    for q_emb in query_embs:
        if not q_emb:
            continue
        hits = _cosine_topk(q_emb, embeddings, k=k)
        for doc_id, score in hits:
            if doc_id not in combined or score > combined[doc_id]:
                combined[doc_id] = score

    return sorted(combined.items(), key=lambda x: x[1], reverse=True)[:k]


def _hybrid_retrieve(
    bm25: _BM25,
    embeddings: list[list[float]] | None,
    queries: list[str],
    question: str,
    k: int,
) -> list[tuple[int, float]]:
    """Hybrid retrieval: BM25 (multi-query) + vector cosine similarity.

    Scores are normalized to [0,1] and combined with equal weight.
    Multi-query vector search: embeds multiple query variants for broader recall.
    """
    bm25_k = max(200, k * 10)

    # --- BM25 ---
    bm25_hits = _multi_query_bm25(bm25, queries, k=bm25_k)

    # --- Multi-query vector search ---
    vec_hits: list[tuple[int, float]] = []
    if embeddings:
        vec_hits = _multi_query_vector(queries, embeddings, k=bm25_k)
        if vec_hits:
            log.info("Multi-query vector search returned %d hits", len(vec_hits))

    if not vec_hits:
        return bm25_hits

    # --- Normalize + combine ---
    bm25_max = max((s for _, s in bm25_hits), default=1.0) or 1.0
    vec_max = max((s for _, s in vec_hits), default=1.0) or 1.0

    combined: dict[int, float] = {}
    for doc_id, score in bm25_hits:
        combined[doc_id] = combined.get(doc_id, 0.0) + 0.5 * (score / bm25_max)
    for doc_id, score in vec_hits:
        combined[doc_id] = combined.get(doc_id, 0.0) + 0.5 * (score / vec_max)

    return sorted(combined.items(), key=lambda x: x[1], reverse=True)[:bm25_k]


# ============================================================================
# Tools
# ============================================================================

@function_tool
def list_available_contracts(oem: str | None = None) -> list[dict[str, Any]]:
    """List available (oem, kb_id) pairs from bundle manifests."""
    wc = get_user_workspace_client()
    all_contracts: list[dict[str, Any]] = []

    prod_base = _bundle_base()
    if prod_base:
        try:
            raw = _read_volume_file(wc, f"{prod_base}/manifest.json").decode("utf-8", errors="ignore")
            prod = json.loads(raw)
            for c in prod:
                c.setdefault("source", "production")
            all_contracts.extend(prod)
        except Exception as e:
            log.debug("Production manifest unavailable: %s", e)

    staging = _staging_bundle_base()
    if staging:
        try:
            raw = _read_volume_file(wc, f"{staging}/manifest.json").decode("utf-8", errors="ignore")
            stg = json.loads(raw)
            for c in stg:
                c.setdefault("source", "staging")
            all_contracts.extend(stg)
        except Exception:
            pass

    if oem:
        all_contracts = [x for x in all_contracts if str(x.get("oem")) == oem]
    return all_contracts


@function_tool
def get_contract_profile(oem: str, contract_id: str) -> dict[str, Any]:
    """Get or generate a structured profile for a warranty contract.

    The profile contains resolved metadata:
    - reference_market, export_markets, market_definitions
    - warranty_periods (by market/component)
    - key_terms (contract-specific definitions)
    - exclusions, claim_procedures
    - citations

    Generated once via LLM (Claude Opus), then cached/persisted.
    """
    oem = (oem or "").strip()
    contract_id = (contract_id or "").strip()
    if not oem or not contract_id:
        raise ValueError("oem and contract_id are required")

    _load_contract(oem, contract_id)
    rows = _CACHE[(oem, contract_id)]["rows"]
    bm25 = _CACHE[(oem, contract_id)]["bm25"]
    return _extract_contract_profile(oem, contract_id, rows, bm25)


@function_tool
def retrieve_contract_context(
    oem: str, contract_id: str, question: str, k: int = 20,
) -> dict[str, Any]:
    """Retrieve relevant contract snippets using hybrid BM25 + vector search.

    Pipeline: synonym expansion -> multi-query BM25 + multi-query vector search
    -> normalize & combine -> LLM semantic rerank (Claude Opus) -> top-k context.

    Default k=20 for comprehensive coverage. Cost is not a concern.

    Returns:
      { "context": "...", "sources": "...", "retrieved": int,
        "profile_summary": "...", "retrieval_mode": "hybrid|bm25" }
    """
    oem = (oem or "").strip()
    contract_id = (contract_id or "").strip()
    question = (question or "").strip()
    if not oem or not contract_id or not question:
        raise ValueError("oem, contract_id, and question are required")

    _load_contract(oem, contract_id)
    bm25: _BM25 = _CACHE[(oem, contract_id)]["bm25"]
    rows: list[dict[str, Any]] = _CACHE[(oem, contract_id)]["rows"]
    embeddings: list[list[float]] | None = _CACHE[(oem, contract_id)].get("embeddings")

    # --- Load profile (non-blocking) ---
    profile_key = (oem, contract_id)
    profile = _PROFILE_CACHE.get(profile_key)
    if profile is None:
        persisted = _load_persisted_profile(oem, contract_id)
        if persisted:
            _PROFILE_CACHE[profile_key] = persisted
            profile = persisted

    # --- Detect contract language ---
    if profile_key not in _CONTRACT_LANG_CACHE:
        _CONTRACT_LANG_CACHE[profile_key] = _detect_language(rows)
    contract_lang = _CONTRACT_LANG_CACHE[profile_key]

    # --- Build expanded query set ---
    queries = _expand_query(question, profile)
    if contract_lang != "en":
        translated_q = _translate_query(question, contract_lang)
        if translated_q:
            queries.append(translated_q)
            queries.extend(_expand_query(translated_q, profile)[1:])

    # --- Hybrid retrieval (BM25 + multi-query vector) ---
    hits = _hybrid_retrieve(bm25, embeddings, queries, question, k=int(k))
    retrieval_mode = "hybrid" if embeddings else "bm25"

    log.info(
        "%s retrieval: %d queries, %d candidates (lang=%s, profile=%s)",
        retrieval_mode, len(queries), len(hits), contract_lang,
        "yes" if profile and profile.get("_status") == "ok" else "no",
    )

    if not hits:
        return {
            "context": "", "sources": "", "retrieved": 0,
            "retrieval_mode": retrieval_mode,
            "note": "No matching passages found in the contract.",
        }

    # --- Semantic reranking (Claude Opus) ---
    hits = _rerank_snippets(question, rows, hits, top_k=int(k))
    ctx, srcs = _format_context(rows, hits, k=int(k))

    result: dict[str, Any] = {
        "context": ctx,
        "sources": srcs,
        "retrieved": len(hits),
        "retrieval_mode": retrieval_mode,
    }

    if profile and profile.get("_status") == "ok":
        summary_parts = []
        ref = profile.get("reference_market")
        if ref:
            summary_parts.append(f"Reference market: {', '.join(ref)}")
        exp = profile.get("export_markets")
        if exp:
            summary_parts.append(f"Export markets: {', '.join(exp[:5])}")
        wps = profile.get("warranty_periods")
        if wps:
            for wp in wps[:8]:
                parts = [wp.get("market", "?"), wp.get("component", "general")]
                if wp.get("months"):
                    parts.append(f"{wp['months']}mo")
                if wp.get("mileage"):
                    parts.append(f"{wp['mileage']}{wp.get('unit', '')}")
                summary_parts.append(f"  Warranty: {' / '.join(parts)}")
        if summary_parts:
            result["profile_summary"] = "\n".join(summary_parts)

    return result


# ============================================================================
# MCP / Agent
# ============================================================================

async def init_mcp_server(workspace_client: WorkspaceClient):
    return McpServer(
        url=build_mcp_url("/api/2.0/mcp/functions/system/ai", workspace_client=workspace_client),
        name="system.ai UC function MCP server",
        workspace_client=workspace_client,
    )


def create_agent(
    mcp_servers: list[McpServer] | None = None,
    selected_contracts: list[dict[str, str]] | None = None,
) -> Agent:
    llm = os.getenv("LLM_ENDPOINT", "gpt_41")

    contract_context_block = ""
    if selected_contracts and len(selected_contracts) > 1:
        labels = ", ".join(
            f"{c['oem']}/{c['kb_id']}" for c in selected_contracts
        )
        contract_context_block = (
            f"\nACTIVE CONTRACTS: {labels}\n"
            "The user has selected multiple contracts. When asked a question:\n"
            "- Call get_contract_profile and retrieve_contract_context for EACH "
            "contract separately.\n"
            "- Present findings per contract, then a comparison/summary across all.\n"
            "- Clearly label which evidence and answers belong to which contract.\n"
        )
    elif selected_contracts and len(selected_contracts) == 1:
        c = selected_contracts[0]
        contract_context_block = (
            f"\nACTIVE CONTRACT: {c['oem']}/{c['kb_id']}\n"
        )

    return Agent(
        name="Agent",
        instructions=(
            "You are a warranty contract QA assistant with deep expertise in "
            "automotive warranty contracts, terms, and industry standards.\n\n"
            "If the user asks what contracts are available, call list_available_contracts.\n"
            f"{contract_context_block}\n"
            "IMPORTANT WORKFLOW:\n"
            "1. For ANY question about a contract, ALWAYS call get_contract_profile FIRST "
            "to understand the contract's specific terminology, markets, and structure.\n"
            "2. Then call retrieve_contract_context with the user's question to get "
            "relevant passages.\n"
            "3. Use ONLY the returned Context + profile. Do not use outside knowledge.\n\n"
            "ACCURACY RULES:\n"
            "- If the context is empty or retrieve_contract_context returned 0 results, "
            "say 'Not found in provided documents.' Do NOT hallucinate an answer.\n"
            "- When a profile_summary is returned with context, use it to resolve "
            "contract-specific terms (e.g. 'reference market' = specific countries).\n"
            "- Cross-reference profile data with retrieved passages for consistency.\n"
            "- If profile and passages conflict, quote both and note the discrepancy.\n\n"
            "If oem/contract_id are missing, ask the user to provide them.\n\n"
            "Output exactly two sections:\n"
            "Evidence: 3-10 bullet points quoting key phrases from Context; each ends with [n].\n"
            "Answer: thorough answer where every claim includes at least one [n] citation.\n"
            "If the answer is not present: say 'Not found in provided documents.'\n"
        ),
        model=llm,
        model_settings=ModelSettings(),
        tools=[
            get_current_time,
            list_available_contracts,
            get_contract_profile,
            retrieve_contract_context,
        ],
        mcp_servers=mcp_servers or [],
    )


def _extract_selected_contracts(request: ResponsesAgentRequest) -> list[dict[str, str]] | None:
    if request.custom_inputs and isinstance(request.custom_inputs, dict):
        return request.custom_inputs.get("selected_contracts")
    return None


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    contracts = _extract_selected_contracts(request)
    agent = create_agent(selected_contracts=contracts)
    messages = [i.model_dump() for i in request.input]
    result = await Runner.run(agent, messages)
    return ResponsesAgentResponse(output=[item.to_input_item() for item in result.new_items])


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})
    contracts = _extract_selected_contracts(request)
    agent = create_agent(selected_contracts=contracts)
    messages = [i.model_dump() for i in request.input]
    result = Runner.run_streamed(agent, input=messages)
    async for event in process_agent_stream_events(result.stream_events()):
        yield event
