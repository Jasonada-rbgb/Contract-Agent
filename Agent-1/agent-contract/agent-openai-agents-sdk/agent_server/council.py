"""Hidden Q&A council -- fan-out synthesis across multiple models.

The council receives a shared evidence packet (context + profile from one
retrieval pass) and fans out final-answer generation to multiple proven-working
endpoints.  A chair model then synthesizes the drafts into one cohesive
markdown answer.

Feature-flagged via COUNCIL_ENABLED env var (default: off).

Design decision (FB-20260407-council-entrypoint-parity):
    The council is intentionally a Streamlit UI-only enhancement.  The base
    agent server ``invoke`` / ``stream`` handlers in ``agent.py`` remain
    single-model.  This is by design: the council adds latency and cost that
    are appropriate for interactive Q&A but not for programmatic API callers.
    Callers using the agent server / API path receive single-model answers.
    If parity is later needed, move ``run_council`` into the shared execution
    path behind the same ``COUNCIL_ENABLED`` flag.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

COUNCIL_ENDPOINTS: list[str] = [
    "gemini_25_pro",
    "gpt_41",
    "databricks-claude-opus-4-8",
]

CHAIR_ENDPOINT = "gemini_25_pro"

_COUNCIL_LOG_VOLUME = "/Volumes/mdna_dev/warranty_agent_staging/council_logs"


def is_council_enabled() -> bool:
    return os.getenv("COUNCIL_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _draft_prompt(question: str, evidence: str, profile_summary: str) -> str:
    return (
        "You are a warranty contract QA expert.\n\n"
        "Using ONLY the evidence below, answer the question in well-structured "
        "GitHub-flavored Markdown. Use ## headings, **bold**, bullet lists, and "
        "pipe tables where appropriate. Every factual claim must include an "
        "inline citation [n] referencing the evidence.\n\n"
        "If the answer is not present in the evidence, say "
        "'Not found in provided documents.'\n\n"
        f"PROFILE:\n{profile_summary}\n\n"
        f"EVIDENCE:\n{evidence}\n\n"
        f"QUESTION:\n{question}\n"
    )


def _chair_prompt(question: str, drafts: list[dict[str, str]], evidence: str) -> str:
    numbered = "\n\n".join(
        f"--- DRAFT {i+1} (model: {d['model']}) ---\n{d['text']}"
        for i, d in enumerate(drafts)
        if d.get("text")
    )
    return (
        "You are a senior warranty contract analyst acting as chair of an "
        "internal review council.\n\n"
        "Multiple models have independently answered the same question using "
        "identical evidence. Your job is to synthesize one final, authoritative "
        "answer in well-structured GitHub-flavored Markdown.\n\n"
        "RULES:\n"
        "- Preserve ONLY claims that are supported by the shared evidence.\n"
        "- When drafts disagree, prefer the narrower, citation-backed wording.\n"
        "- Keep all inline citations [n] from the evidence.\n"
        "- Use ## Evidence, ## Answer, and ## Comparison (when comparative) sections.\n"
        "- Use pipe tables for comparisons (max 5 columns); bullets when wider.\n"
        "- If no draft found an answer, say 'Not found in provided documents.'\n"
        "- Do NOT mention that multiple models were consulted.\n\n"
        f"EVIDENCE:\n{evidence}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"DRAFTS:\n{numbered}\n"
    )


def _call_model(prompt: str, endpoint: str) -> str | None:
    """Call a single model endpoint via the shared LLM helper."""
    try:
        from agent_server.agent import _call_llm
        return _call_llm(prompt, temperature=0.0, endpoint=endpoint)
    except Exception as exc:
        log.warning("Council draft failed (%s): %s", endpoint, exc)
        return None


def _log_council_run(
    question: str,
    drafts: list[dict[str, str]],
    final_text: str,
    chair_endpoint: str,
) -> None:
    """Best-effort log of council run to staging volume."""
    try:
        from agent_server.utils import get_user_workspace_client
        import io

        wc = get_user_workspace_client()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in question[:40])
        path = f"{_COUNCIL_LOG_VOLUME}/{ts}_{slug}.json"
        not_found_flags = [
            "not found in provided documents" in (d.get("text") or "").lower()
            for d in drafts if d.get("text")
        ]
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question,
            "drafts": drafts,
            "chair_endpoint": chair_endpoint,
            "final_answer_length": len(final_text),
            "models_responded": len([d for d in drafts if d.get("text")]),
            "models_total": len(drafts),
            "all_agree_not_found": all(not_found_flags) if not_found_flags else False,
            "any_disagree_not_found": (
                any(not_found_flags) and not all(not_found_flags)
            ) if not_found_flags else False,
        }
        data = json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8")
        wc.files.upload(path, io.BytesIO(data), overwrite=True)
    except Exception as exc:
        log.debug("Council log write failed (non-fatal): %s", exc)


def run_council(
    question: str,
    evidence: str,
    profile_summary: str = "",
    endpoints: list[str] | None = None,
    chair: str | None = None,
) -> str:
    """Fan out answer synthesis and return a chair-synthesized final answer.

    Returns the chair synthesis, or falls back to the best single draft
    if the chair call fails.
    """
    eps = endpoints or COUNCIL_ENDPOINTS
    chair_ep = chair or CHAIR_ENDPOINT
    prompt = _draft_prompt(question, evidence, profile_summary)

    drafts: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(eps)) as pool:
        futures = {pool.submit(_call_model, prompt, ep): ep for ep in eps}
        for future in concurrent.futures.as_completed(futures):
            ep = futures[future]
            try:
                text = future.result()
                drafts.append({"model": ep, "text": text or ""})
            except Exception as exc:
                log.warning("Council endpoint %s raised: %s", ep, exc)
                drafts.append({"model": ep, "text": ""})

    valid_drafts = [d for d in drafts if d.get("text")]
    if not valid_drafts:
        return "Not found in provided documents."

    if len(valid_drafts) == 1:
        final = valid_drafts[0]["text"]
        _log_council_run(question, drafts, final, chair_ep)
        return final

    not_found_count = sum(
        1 for d in valid_drafts
        if "not found in provided documents" in d["text"].lower()
    )
    all_agree_not_found = not_found_count == len(valid_drafts)

    if all_agree_not_found:
        final = "Not found in provided documents."
        _log_council_run(question, drafts, final, chair_ep)
        return final

    chair_p = _chair_prompt(question, valid_drafts, evidence)
    final = _call_model(chair_p, chair_ep)

    if not final:
        final = max(valid_drafts, key=lambda d: len(d["text"]))["text"]

    _log_council_run(question, drafts, final, chair_ep)
    return final
