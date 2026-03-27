"""Claims evaluation — all rulings derived from the contract via LLM reasoning.

No hardcoded warranty rules. Every decision is made by a reasoning model
(openai_o3) interpreting the actual contract terms, warranty periods,
exclusions, and market definitions extracted from the ingested contract.
"""

import concurrent.futures
import io
import json
import logging
import os
import re
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
from dateutil.relativedelta import relativedelta

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def _parse_date(x) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, date):
        return x
    s = str(x).strip()
    if not s:
        return None
    d = pd.to_datetime(s, dayfirst=True, errors="coerce")
    if pd.isna(d):
        return None
    return d.date()


def _parse_float(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s:
        return None
    s = re.sub(r"[£$€,]", "", s)
    try:
        return float(s)
    except Exception:
        return None


def _read_input_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    fn = (filename or "").lower()
    if fn.endswith(".xlsx") or fn.endswith(".xls"):
        return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    return pd.read_csv(io.BytesIO(file_bytes))


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

CANON_MAP: Dict[str, set] = {
    "vin": {
        "vin", "fahrgestellnummer", "fgst_nr", "fgstnr", "vehicle_id",
        "chassis_number",
    },
    "country": {
        "country", "market", "region", "land", "markt", "absatzmarkt",
        "sendemarkt",
    },
    "warranty_start_date": {
        "warranty_start_date", "warranty_start", "in_service_date",
        "in_service", "retail_sale_date", "sale_date",
        "erstzulassung", "erstzulassungsdatum", "garantiebeginn",
        "retail_date", "delivery_date", "fahrzeugubergabe",
    },
    "repair_date": {
        "repair_date", "claim_date", "repair_dt", "date_of_repair",
        "reparaturdatum", "reparatur_datum", "gutschriftsdatum",
        "credit_date", "claim_dt",
    },
    "mileage": {
        "mileage", "miles", "odometer", "km", "kilometers", "distance",
        "kilometerstand", "laufleistung", "km_stand",
    },
    "part_description": {
        "part_description", "part", "part_desc", "component",
        "fault_description", "defect", "repair_description",
        "teilebeschreibung", "bauteil", "fehlerbeschreibung",
        "sachnummer_text", "part_name",
    },
    "claim_number": {
        "claim_number", "claim", "claim_no", "claim_id",
        "antragsnummer", "beanstandungsnummer", "claim_ref",
    },
    "document_number": {
        "document_number", "doc_number", "document", "doc_no",
        "belegnummer", "dokumentnummer",
    },
    "brand": {
        "brand", "oem", "manufacturer", "marke", "hersteller",
    },
    "dealer": {
        "dealer", "dealer_name", "workshop", "repairer",
        "handler", "werkstatt", "handlercode", "dealer_code",
    },
    "labour_cost": {
        "labour_cost", "labor_cost", "labour", "labor",
        "lohnkosten", "arbeitskosten",
    },
    "parts_cost": {
        "parts_cost", "part_cost", "material_cost",
        "materialkosten", "teilekosten", "ersatzteilkosten",
    },
    "total_cost": {
        "total_cost", "claim_amount", "total", "amount",
        "gesamtkosten", "nettokosten", "gesamtbetrag",
    },
    "model": {
        "model", "vehicle_model", "modell", "baureihe",
        "fahrzeugmodell", "vehicle_line", "model_series",
    },
    "production_date": {
        "production_date", "build_date", "produktionsdatum",
        "herstelldatum", "manufacture_date",
    },
    "failure_code": {
        "failure_code", "error_code", "fehlercode", "fehlerbild",
        "defect_code", "fault_code", "beanstandungscode",
    },
    "part_number": {
        "part_number", "part_no", "sachnummer", "teilenummer",
        "material_number", "sn", "pn",
    },
}

CRITICAL_FIELDS = {"warranty_start_date", "repair_date"}
IMPORTANT_FIELDS = {"country", "mileage", "part_description"}


def _build_col_lookup(df: pd.DataFrame) -> Dict[str, str]:
    cols = list(df.columns)
    normed = {_norm(c): c for c in cols}
    out: Dict[str, str] = {}
    for canon, candidates in CANON_MAP.items():
        for cand in candidates:
            if cand in normed:
                out[canon] = normed[cand]
                break
    return out


def _smart_col_lookup(
    df: pd.DataFrame,
    llm_endpoint: str | None = None,
) -> tuple[Dict[str, str], list[str]]:
    """Map dataset columns to canonical field names.

    First tries the deterministic CANON_MAP. For any unmapped canonical fields,
    falls back to asking the LLM to interpret the column names + sample data.

    Returns (lookup_dict, list_of_warnings).
    """
    lookup = _build_col_lookup(df)

    unmapped_canons = [k for k in CANON_MAP if k not in lookup]
    unmapped_cols = [c for c in df.columns if c not in lookup.values()]
    warnings: list[str] = []

    critical_unmapped = [k for k in unmapped_canons if k in CRITICAL_FIELDS | IMPORTANT_FIELDS]
    if critical_unmapped and unmapped_cols:
        sample = df.head(3).to_dict(orient="records")
        sample_str = json.dumps(sample, indent=2, default=str)[:2000]

        prompt = (
            "You are a data analyst. Map dataset columns to canonical warranty claim fields.\n\n"
            f"Dataset columns: {list(df.columns)}\n\n"
            f"Sample rows (first 3):\n{sample_str}\n\n"
            f"Canonical fields that still need mapping: {unmapped_canons}\n\n"
            "For each unmapped canonical field, identify which dataset column (if any) "
            "corresponds to it based on the column name AND sample data values.\n\n"
            "Return ONLY valid JSON mapping dataset column names to canonical field names.\n"
            'Example: {"Reparaturdatum": "repair_date", "KM-Stand": "mileage"}\n'
            "If a canonical field has no matching column, omit it. Return {} if no matches."
        )

        try:
            from agent_server.agent import _call_llm
            ep = llm_endpoint or _reasoning_endpoint()
            raw = _call_llm(prompt, temperature=0.0, endpoint=ep)
            if raw:
                raw_clean = raw.strip()
                if raw_clean.startswith("```"):
                    raw_clean = re.sub(r"^```(?:json)?\s*", "", raw_clean)
                    raw_clean = re.sub(r"\s*```$", "", raw_clean)
                llm_mapping = json.loads(raw_clean)
                if isinstance(llm_mapping, dict):
                    reverse = {v: k for k, v in llm_mapping.items()
                               if v in CANON_MAP and k in df.columns}
                    for canon, col in reverse.items():
                        if canon not in lookup:
                            lookup[canon] = col
                            log.info("LLM mapped column '%s' -> '%s'", col, canon)
        except Exception as e:
            log.warning("LLM column mapping failed (non-fatal): %s", e)

    for field in CRITICAL_FIELDS:
        if field not in lookup:
            warnings.append(f"CRITICAL: Could not map '{field}' -- claim evaluation may be inaccurate")
    for field in IMPORTANT_FIELDS:
        if field not in lookup:
            warnings.append(f"WARNING: Could not map '{field}' -- some claim details may be missing")

    still_unmapped = [c for c in df.columns if c not in lookup.values()]
    if still_unmapped:
        warnings.append(f"Additional columns (passed to model as-is): {still_unmapped}")

    return lookup, warnings


# ---------------------------------------------------------------------------
# Reasoning endpoint
# ---------------------------------------------------------------------------

def _reasoning_endpoint() -> str:
    """Get the reasoning model endpoint (o3 preferred for multi-step logic)."""
    return (
        os.getenv("REASONING_ENDPOINT")
        or os.getenv("LLM_ENDPOINT")
        or "gpt_41"
    ).strip()


def _fast_endpoint() -> str:
    """Get the fast model endpoint (Claude Opus for initial claim triage)."""
    return (os.getenv("LLM_ENDPOINT") or "databricks-claude-opus-4-6").strip()


# ---------------------------------------------------------------------------
# Contract rule retrieval (cached per contract for the process lifetime)
# ---------------------------------------------------------------------------

_CONTRACT_CTX_CACHE: Dict[tuple, tuple[dict, str]] = {}


def _load_contract_context(
    oem: str, contract_id: str,
) -> tuple[dict, str]:
    """Load contract profile and retrieve comprehensive warranty rule passages.

    Results are cached in-process so repeated evaluations against the same
    contract skip the expensive 15-query retrieval entirely.
    """
    cache_key = (oem, contract_id)
    if cache_key in _CONTRACT_CTX_CACHE:
        log.info("Using cached contract context for %s/%s", oem, contract_id)
        return _CONTRACT_CTX_CACHE[cache_key]

    from agent_server.agent import (
        _load_contract, _CACHE, _extract_contract_profile,
        _hybrid_retrieve, _expand_query, _format_context,
    )

    _load_contract(oem, contract_id)
    cache = _CACHE[(oem, contract_id)]
    rows = cache["rows"]
    bm25 = cache["bm25"]
    embeddings = cache.get("embeddings")

    profile = _extract_contract_profile(oem, contract_id, rows, bm25)

    rule_queries = [
        "warranty period duration months mileage general coverage",
        "powertrain engine transmission drivetrain warranty",
        "paint warranty surface finish defect paintwork",
        "corrosion perforation warranty body rust through",
        "battery warranty electric vehicle EV hybrid high voltage",
        "exclusions not covered limitations exceptions wear tear",
        "claim procedure submission deadline approval documentation",
        "goodwill gesture commercial discretion ex gratia",
        "labour rate labor rate workshop hourly rate",
        "mileage limit distance whichever comes first sooner",
        "reference market home market domestic export market foreign",
        "service parts maintenance consumable wear parts",
        "pre-delivery inspection PDI delivery check",
        "consequential damage indirect loss liability",
        "extended warranty additional coverage premium",
    ]

    all_hits: dict[int, float] = {}
    for query in rule_queries:
        queries = _expand_query(query, profile)
        hits = _hybrid_retrieve(bm25, embeddings, queries, query, k=15)
        for doc_id, score in hits:
            if doc_id not in all_hits or score > all_hits[doc_id]:
                all_hits[doc_id] = score

    sorted_hits = sorted(all_hits.items(), key=lambda x: x[1], reverse=True)[:50]
    ctx, _ = _format_context(rows, sorted_hits, k=50, per_chars=2000)

    log.info(
        "Retrieved %d comprehensive rule passages for %s/%s",
        len(sorted_hits), oem, contract_id,
    )
    _CONTRACT_CTX_CACHE[cache_key] = (profile, ctx)
    return profile, ctx


# ---------------------------------------------------------------------------
# Per-claim LLM evaluation
# ---------------------------------------------------------------------------

_CLAIM_EVAL_PROMPT = """You are an expert warranty claims adjudicator. Evaluate this claim using ONLY the contract rules and passages provided below. Do NOT use any outside knowledge or assumptions about standard warranty terms.

=== CONTRACT PROFILE (structured rules extracted from the contract) ===
{profile_json}

=== RELEVANT CONTRACT PASSAGES ===
{contract_passages}

=== CLAIM TO EVALUATE ===
{claim_json}

=== EVALUATION INSTRUCTIONS ===
1. Identify the correct market category for this claim based on the country/region and the contract's market definitions.
2. Identify the applicable warranty period based on the market AND the component/part type (general, powertrain, paint, corrosion, battery, etc.).
3. Calculate the warranty end date from the warranty start date + applicable months.
4. Check: Is the repair date on or before the warranty end date? (time_ok)
5. Check: Is the mileage at or below the applicable limit? (mileage_ok)
6. Apply "whichever comes first/sooner" if the contract specifies this.
7. Check all listed exclusions — does any exclusion apply to this claim?
8. If any required data is missing, set decision to "insufficient_info".
9. If the claim is borderline or ambiguous, set decision to "requires_review" and explain why.

Return ONLY raw JSON. Do NOT wrap in ```json or any markdown. Keep string values SHORT (under 80 chars each). Be concise.
{{
  "decision": "in_warranty" or "out_of_warranty" or "insufficient_info" or "requires_review",
  "applicable_rule": {{
    "market": "market category name only",
    "component": "component/warranty type name only",
    "months": 36,
    "mileage_limit": 60000,
    "mileage_unit": "miles",
    "whichever_sooner": true
  }},
  "time_ok": true or false or null,
  "mileage_ok": true or false or null,
  "warranty_end_date": "YYYY-MM-DD" or null,
  "reason": "concise 1-2 sentence explanation with passage refs",
  "exclusions_checked": ["exclusion1: no", "exclusion2: no"],
  "confidence": "high" or "medium" or "low",
  "contract_references": ["[1]", "[3]"]
}}"""


def _evaluate_single_claim(
    claim_data: dict,
    profile: dict,
    contract_passages: str,
    endpoint: str,
) -> dict:
    """Evaluate a single claim against contract rules using the reasoning model."""
    from agent_server.agent import _call_llm

    # Build clean profile (strip internal fields)
    profile_clean = {
        k: v for k, v in profile.items()
        if not k.startswith("_")
    }

    prompt = _CLAIM_EVAL_PROMPT.format(
        profile_json=json.dumps(profile_clean, indent=2, default=str),
        contract_passages=contract_passages,
        claim_json=json.dumps(claim_data, indent=2, default=str),
    )

    is_reasoning = "o3" in endpoint or "o1" in endpoint
    raw = _call_llm(
        prompt,
        max_tokens=32000,
        temperature=None if is_reasoning else 0.0,
        endpoint=endpoint,
    )
    if not raw:
        return {
            "decision": "insufficient_info",
            "reason": "Model did not return a response.",
            "confidence": "low",
        }

    # Strip markdown fences (models often wrap JSON despite instructions)
    raw_clean = raw.strip()
    raw_clean = re.sub(r"^```(?:json)?\s*", "", raw_clean)
    raw_clean = re.sub(r"\s*```\s*$", "", raw_clean)

    # Find the outermost JSON object even if there's trailing text
    brace_start = raw_clean.find("{")
    if brace_start >= 0:
        depth = 0
        for i, ch in enumerate(raw_clean[brace_start:], brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw_clean = raw_clean[brace_start:i + 1]
                    break

    try:
        result = json.loads(raw_clean)
    except json.JSONDecodeError:
        return {
            "decision": "requires_review",
            "reason": f"Could not parse reasoning model response: {raw[:300]}",
            "confidence": "low",
        }

    # Validate decision value
    valid_decisions = {"in_warranty", "out_of_warranty", "insufficient_info", "requires_review"}
    if result.get("decision") not in valid_decisions:
        result["decision"] = "requires_review"

    return result


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

def evaluate_claims_table(
    df: pd.DataFrame,
    oem: str,
    contract_id: str,
    progress_callback=None,
    model_endpoint: str | None = None,
) -> tuple[List[Dict[str, Any]], list[str]]:
    """Evaluate every claim row against the actual contract rules.

    model_endpoint: the serving endpoint to use for all claims.
    Falls back to the fast endpoint (Claude) if not specified.
    """
    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)
        log.info(msg)

    endpoint = model_endpoint or _fast_endpoint()
    _progress("Mapping dataset columns...")
    lookup, mapping_warnings = _smart_col_lookup(df, llm_endpoint=endpoint)
    for w in mapping_warnings:
        _progress(w)

    # --- Load contract rules (once for the whole batch) ---
    _progress(f"Loading contract rules for {oem}/{contract_id}...")
    try:
        profile, contract_passages = _load_contract_context(oem, contract_id)
    except Exception as e:
        log.error("Failed to load contract context: %s", e)
        return [{
            "row_index": 0,
            "decision": "insufficient_info",
            "reason": f"Could not load contract rules: {e}",
        }], [f"ERROR: Could not load contract rules: {e}"]

    profile_status = profile.get("_status", "unknown")
    model_label = endpoint.split("-")[-1] if "-" in endpoint else endpoint
    _progress(
        f"Contract profile: {profile_status}. "
        f"Model: {endpoint}. Evaluating {len(df)} claims..."
    )

    # --- Build claim data for all rows up front ---
    claim_rows: list[tuple[int, dict, dict]] = []
    mapped_cols = set(lookup.values())

    for idx, row in df.iterrows():
        def _get(canon: str, default=None):
            col = lookup.get(canon)
            if col is None:
                return default
            val = row.get(col)
            if pd.isna(val):
                return default
            return val

        vin = _get("vin")
        country = _get("country")
        wsd = _parse_date(_get("warranty_start_date"))
        rep = _parse_date(_get("repair_date"))
        mil = _parse_float(_get("mileage"))
        part = _get("part_description")
        claim_no = _get("claim_number")
        doc_no = _get("document_number")
        brand = _get("brand")
        dealer = _get("dealer")
        labour_cost = _parse_float(_get("labour_cost"))
        parts_cost = _parse_float(_get("parts_cost"))
        total_cost = _parse_float(_get("total_cost"))

        claim_data = {
            "vin": str(vin) if vin is not None else None,
            "country": str(country) if country is not None else None,
            "warranty_start_date": str(wsd) if wsd else None,
            "repair_date": str(rep) if rep else None,
            "mileage": mil,
            "part_description": str(part) if part is not None else None,
            "claim_number": str(claim_no) if claim_no is not None else None,
            "brand": str(brand) if brand is not None else None,
            "dealer": str(dealer) if dealer is not None else None,
            "labour_cost": labour_cost,
            "parts_cost": parts_cost,
            "total_cost": total_cost,
        }
        for col in df.columns:
            if col not in mapped_cols:
                val = row.get(col)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    claim_data[col] = str(val) if not isinstance(val, (int, float)) else val
        claim_data = {k: v for k, v in claim_data.items() if v is not None}

        id_fields = {
            "row_index": int(idx),
            "oem": oem,
            "contract_id": contract_id,
            "vin": str(vin) if vin is not None else None,
            "country": str(country) if country is not None else None,
            "warranty_start_date": str(wsd) if wsd else None,
            "repair_date": str(rep) if rep else None,
            "mileage": mil,
            "part_description": str(part) if part is not None else None,
            "claim_number": str(claim_no) if claim_no is not None else None,
            "document_number": str(doc_no) if doc_no is not None else None,
        }
        claim_rows.append((idx, claim_data, id_fields))

    # --- Evaluate each claim (parallel) ---
    total = len(claim_rows)
    max_workers = min(20, total)
    results: List[Optional[Dict[str, Any]]] = [None] * total

    def _eval_one(i: int) -> Dict[str, Any]:
        idx, claim_data, id_fields = claim_rows[i]

        llm_result = _evaluate_single_claim(
            claim_data, profile, contract_passages, endpoint,
        )

        applicable_rule = llm_result.get("applicable_rule") or {}
        return {
            **id_fields,
            "decision": llm_result.get("decision", "requires_review"),
            "reason": llm_result.get("reason", ""),
            "confidence": llm_result.get("confidence", "low"),
            "time_ok": llm_result.get("time_ok"),
            "mileage_ok": llm_result.get("mileage_ok"),
            "end_date": llm_result.get("warranty_end_date"),
            "rule_months": applicable_rule.get("months"),
            "rule_mileage_limit": applicable_rule.get("mileage_limit"),
            "rule_mileage_unit": applicable_rule.get("mileage_unit", ""),
            "applicable_market": applicable_rule.get("market", ""),
            "applicable_component": applicable_rule.get("component", ""),
            "exclusions_checked": "; ".join(
                llm_result.get("exclusions_checked") or []
            ),
            "contract_references": "; ".join(
                str(r) for r in (llm_result.get("contract_references") or [])
            ),
            "evaluated_by": model_label,
        }

    _progress(f"Evaluating {total} claims with {max_workers} parallel workers ({model_label})...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(_eval_one, i): i for i in range(total)}
        done_count = 0
        for future in concurrent.futures.as_completed(future_map):
            i = future_map[future]
            try:
                results[i] = future.result()
            except Exception as e:
                log.warning("Claim %d evaluation failed: %s", i, e)
            done_count += 1
            if done_count % 5 == 0 or done_count == total:
                _progress(f"Evaluated {done_count}/{total} claims ({model_label})...")

    results = [r for r in results if r is not None]
    _progress(f"Done! {len(results)} claims evaluated.")
    return results, mapping_warnings


def evaluate_claims_file(
    file_bytes: bytes,
    filename: str,
    oem: str,
    contract_id: str,
    progress_callback=None,
    model_endpoint: str | None = None,
) -> tuple[List[Dict[str, Any]], list[str]]:
    """Read a claims spreadsheet and evaluate each row against the contract."""
    df = _read_input_bytes(file_bytes, filename)
    df = df.dropna(how="all")
    return evaluate_claims_table(
        df, oem=oem, contract_id=contract_id,
        progress_callback=progress_callback,
        model_endpoint=model_endpoint,
    )
