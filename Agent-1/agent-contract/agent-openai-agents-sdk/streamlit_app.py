"""Warranty Contract Agent -- Streamlit App (single-process).

Four modes:
  1. Contract Q&A     -- chat with the agent (per-user memory, thinking panel, inline feedback)
  2. Claims Evaluator -- upload CSV/XLSX, evaluate claims
  3. Ingest Contract  -- upload PDFs, trigger ingestion pipeline
  4. Feedback         -- submit structured feedback for agent improvement
"""

import asyncio
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient

from agent_server.agent import create_agent, _bundle_base, _staging_bundle_base, _read_volume_file, _call_llm
from agent_server.claims_batch import evaluate_claims_file, _smart_col_lookup, CRITICAL_FIELDS, IMPORTANT_FIELDS
from agent_server.council import is_council_enabled, run_council
from agent_server.ingest import (
    upload_files,
    ingest_inline,
    read_staging_manifest,
    staging_bundle_base,
    staging_raw_dir,
)
from agents import Runner, set_default_openai_api, set_default_openai_client
from databricks_openai import AsyncDatabricksOpenAI

log = logging.getLogger(__name__)

_SESSION_VOLUME = "/Volumes/mdna_dev/warranty_agent_staging/user_sessions"
_FEEDBACK_VOLUME = "/Volumes/mdna_dev/warranty_agent_staging/feedback"
_FEEDBACK_MD_PATH = (
    "/Workspace/Users/adj1de@bosch.com/databricks_apps/"
    "agent-contract_2026_03_06-13_15/feedback.md"
)

_TOOL_LABELS = {
    "get_contract_profile": "Retrieving contract profile...",
    "retrieve_contract_context": "Searching relevant passages...",
    "list_available_contracts": "Listing available contracts...",
    "get_current_time": "Getting current time...",
}

_THINKING_PATTERNS = [
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reflection>.*?</reflection>", re.DOTALL | re.IGNORECASE),
    re.compile(r"\[thinking\].*?\[/thinking\]", re.DOTALL | re.IGNORECASE),
    re.compile(r"\[reasoning\].*?\[/reasoning\]", re.DOTALL | re.IGNORECASE),
    re.compile(r"\*\*(?:Thinking|Reasoning|Internal reasoning|Reflection):\*\*.*?(?=\n##|\Z)", re.DOTALL | re.IGNORECASE),
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<scratchpad>.*?</scratchpad>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<chain_of_thought>.*?</chain_of_thought>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<inner_monologue>.*?</inner_monologue>", re.DOTALL | re.IGNORECASE),
    re.compile(r"\[think\].*?\[/think\]", re.DOTALL | re.IGNORECASE),
    re.compile(r"\*\*(?:Think|Internal analysis|Internal|Chain of thought|Scratchpad):\*\*.*?(?=\n##|\Z)", re.DOTALL | re.IGNORECASE),
    re.compile(r"<(?:think|reason|reflect)\w*>.*?</(?:think|reason|reflect)\w*>", re.DOTALL | re.IGNORECASE),
]

_TOOL_ARTIFACT_PATTERNS = [
    re.compile(r'^[ \t]*\{"(?:name|function)":\s*"[^"]+",\s*"arguments":.*?\}[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*(?:Tool|Function) (?:output|result|response):\s*\{.*?\}[ \t]*$', re.MULTILINE | re.DOTALL),
    re.compile(r'^[ \t]*(?:tool_call_id|function_call)\s*[:=].*$', re.MULTILINE),
    re.compile(r'^[ \t]*(?:get_contract_profile|retrieve_contract_context|list_available_contracts|get_current_time)\s*\(.*?\)[ \t]*$', re.MULTILINE),
    re.compile(r'^[ \t]*\{"(?:context|_status|retrieved|profile_summary)":.*$', re.MULTILINE),
    re.compile(r'<tool_call>.*?</tool_call>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<tool_result>.*?</tool_result>', re.DOTALL | re.IGNORECASE),
    re.compile(r'<function=\w+>.*?</function>', re.DOTALL | re.IGNORECASE),
    re.compile(r'^[ \t]*Action\s*:\s*\w+.*?(?:^[ \t]*Observation\s*:.*?)(?=\n\n|\Z)', re.MULTILINE | re.DOTALL),
]

_ANSWER_CONTENT_TYPES = {"output_text"}
_TRACE_CONTENT_TYPES = {"thinking", "reasoning", "refusal", "model_reasoning"}
_AGENT_TIMEOUT_S = int(os.getenv("AGENT_TIMEOUT_SECONDS", "420"))
_AGENT_WARN_THRESHOLD_S = int(os.getenv("AGENT_WARN_THRESHOLD_S", "120"))


def _strip_internal_content(text: str, trace: list[str]) -> str:
    """Remove model thinking tokens and tool call artifacts from answer text.

    Extracted thinking content is routed to the trace list for display
    in the thinking panel.
    """
    if not text:
        return text
    cleaned = text
    thinking_detected = False
    for pat in _THINKING_PATTERNS:
        for match in pat.finditer(cleaned):
            content = match.group(0)
            if content.strip() and len(content.strip()) > 10:
                thinking_detected = True
        cleaned = pat.sub("", cleaned)
    if thinking_detected:
        trace.append("Internal reasoning was captured and kept out of the final answer.")
    for pat in _TOOL_ARTIFACT_PATTERNS:
        cleaned = pat.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _render_assistant_md(text: str) -> None:
    """Centralized assistant markdown rendering.

    All assistant output passes through here so presentation policy
    (e.g. HTML allowlisting, CSS wrappers) can evolve in one place.
    Applies a safety-net strip to catch any thinking tokens that
    survived earlier filtering (e.g. from history replay).
    """
    cleaned = _strip_internal_content(text, [])
    st.markdown(cleaned)

st.set_page_config(
    page_title="Warranty Contract Agent",
    page_icon="\U0001f4cb",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Workspace client
# ---------------------------------------------------------------------------
def _get_workspace_client() -> WorkspaceClient:
    try:
        token = st.context.headers.get("X-Forwarded-Access-Token", "")
        if token:
            return WorkspaceClient(token=token)
    except Exception:
        pass
    return WorkspaceClient()


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------
def _get_user_email() -> str:
    if "user_email" in st.session_state:
        return st.session_state.user_email
    try:
        wc = _get_workspace_client()
        me = wc.current_user.me()
        email = me.user_name or me.display_name or "unknown"
    except Exception:
        email = "unknown"
    st.session_state.user_email = email
    return email


def _sanitize_email(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", email)


# ---------------------------------------------------------------------------
# Session persistence + metadata (chat history)
# ---------------------------------------------------------------------------
def _session_path(email: str, session_id: str) -> str:
    return f"{_SESSION_VOLUME}/{_sanitize_email(email)}/{session_id}.jsonl"


def _meta_path(email: str) -> str:
    return f"{_SESSION_VOLUME}/{_sanitize_email(email)}/sessions_meta.json"


def _load_sessions_meta(email: str) -> dict:
    try:
        wc = _get_workspace_client()
        raw = _read_volume_file(wc, _meta_path(email)).decode("utf-8", errors="ignore")
        return json.loads(raw)
    except Exception:
        return {"sessions": {}}


def _save_sessions_meta(email: str, meta: dict):
    try:
        wc = _get_workspace_client()
        data = json.dumps(meta, indent=2, ensure_ascii=False).encode("utf-8")
        wc.files.upload(_meta_path(email), io.BytesIO(data), overwrite=True)
    except Exception as e:
        log.debug("Could not save sessions meta: %s", e)


def _ensure_session_meta(email: str, session_id: str, name: str | None = None):
    meta = _load_sessions_meta(email)
    if session_id not in meta.get("sessions", {}):
        meta.setdefault("sessions", {})[session_id] = {
            "name": name or f"Chat {datetime.now(timezone.utc).strftime('%b %d %H:%M')}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta["sessions"][session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_sessions_meta(email, meta)


def _rename_session(email: str, session_id: str, new_name: str):
    meta = _load_sessions_meta(email)
    if session_id in meta.get("sessions", {}):
        meta["sessions"][session_id]["name"] = new_name.strip()
        meta["sessions"][session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_sessions_meta(email, meta)


def _list_user_sessions(email: str) -> list[dict]:
    try:
        wc = _get_workspace_client()
        user_dir = f"{_SESSION_VOLUME}/{_sanitize_email(email)}"
        files = list(wc.files.list_directory_contents(user_dir))
        meta = _load_sessions_meta(email)
        out = []
        for f in files:
            if not f.path.endswith(".jsonl"):
                continue
            sid = f.path.split("/")[-1].replace(".jsonl", "")
            row = meta.get("sessions", {}).get(sid, {})
            out.append({
                "session_id": sid,
                "name": row.get("name") or sid[:8],
                "last_modified": str(f.last_modified or ""),
            })
        out.sort(key=lambda x: x["last_modified"], reverse=True)
        return out
    except Exception:
        return []


def _save_exchange(
    email: str, session_id: str, contracts: list[dict],
    question: str, response: str, tool_calls: list[dict],
    rating: str | None = None, comment: str = "",
    exchange_id: str | None = None,
    elapsed_ms: int | None = None,
    retrieval_trace: list[dict] | None = None,
) -> bool:
    record = {
        "exchange_id": exchange_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": email,
        "session_id": session_id,
        "contracts": [{"oem": c.get("oem"), "kb_id": c.get("kb_id")} for c in (contracts or [])],
        "question": question,
        "response": response[:5000],
        "tool_calls": [tc.get("name") for tc in tool_calls],
        "rating": rating,
        "feedback_comment": comment,
        "elapsed_ms": elapsed_ms,
        "retrieval_trace": retrieval_trace or [],
    }
    try:
        wc = _get_workspace_client()
        path = _session_path(email, session_id)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            wc.files.upload(path, io.BytesIO(line.encode("utf-8")), overwrite=False)
        except Exception:
            existing = _read_volume_file(wc, path).decode("utf-8", errors="ignore")
            wc.files.upload(path, io.BytesIO((existing + line).encode("utf-8")), overwrite=True)
        _ensure_session_meta(email, session_id, name=question[:40] if question else None)
        return True
    except Exception as e:
        log.debug("Could not save exchange: %s", e)
        return False


def _update_saved_exchange_feedback(
    email: str,
    session_id: str,
    exchange_id: str,
    rating: str,
    comment: str = "",
) -> bool:
    try:
        wc = _get_workspace_client()
        path = _session_path(email, session_id)
        raw = _read_volume_file(wc, path).decode("utf-8", errors="ignore")
        updated_lines: list[str] = []
        found = False
        for line in raw.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("exchange_id") == exchange_id:
                record["rating"] = rating
                record["feedback_comment"] = comment
                found = True
            updated_lines.append(json.dumps(record, ensure_ascii=False))
        if not found:
            return False
        wc.files.upload(
            path,
            io.BytesIO(("\n".join(updated_lines) + "\n").encode("utf-8")),
            overwrite=True,
        )
        return True
    except Exception as e:
        log.debug("Could not update exchange feedback: %s", e)
        return False


def _load_session(email: str, session_id: str) -> list[dict]:
    try:
        wc = _get_workspace_client()
        raw = _read_volume_file(wc, _session_path(email, session_id)).decode("utf-8", errors="ignore")
        messages = []
        for line in raw.strip().split("\n"):
            if not line.strip():
                continue
            record = json.loads(line)
            messages.append({"role": "user", "content": record.get("question", "")})
            fb_comment = record.get("feedback_comment", "")
            has_rating = record.get("rating") is not None
            messages.append({
                "role": "assistant",
                "content": record.get("response", ""),
                "tool_calls": [],
                "exchange_id": record.get("exchange_id"),
                "elapsed_ms": record.get("elapsed_ms"),
                "retrieval_trace": record.get("retrieval_trace") or [],
                "rating": record.get("rating"),
                "feedback_comment": fb_comment,
                "feedback_comment_submitted": has_rating,
            })
        return messages
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Feedback persistence
# ---------------------------------------------------------------------------
def _save_feedback_rating(
    email: str, session_id: str, question: str, response_preview: str,
    contracts: list[dict], rating: str, comment: str = "",
    message_index: int | None = None,
    related_contract: str = "",
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": email, "session_id": session_id,
        "question": question, "response_preview": response_preview[:500],
        "contracts": [{"oem": c.get("oem"), "kb_id": c.get("kb_id")} for c in (contracts or [])],
        "rating": rating, "comment": comment,
        "message_index": message_index,
        "related_contract": related_contract,
    }
    try:
        wc = _get_workspace_client()
        log_path = f"{_FEEDBACK_VOLUME}/feedback_log.jsonl"
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            existing = _read_volume_file(wc, log_path).decode("utf-8", errors="ignore")
            line = existing + line
        except Exception:
            pass
        wc.files.upload(log_path, io.BytesIO(line.encode("utf-8")), overwrite=True)
    except Exception as e:
        log.debug("Could not save feedback: %s", e)


def _append_feedback_md(structured_feedback: str) -> bool:
    try:
        wc = _get_workspace_client()
        try:
            existing = wc.workspace.export(_FEEDBACK_MD_PATH, format="AUTO").content or b""
            if isinstance(existing, bytes):
                existing = existing.decode("utf-8", errors="ignore")
        except Exception:
            existing = "# Agent Feedback Log\n\n"
        import base64
        updated = existing + structured_feedback + "\n\n"
        wc.workspace.import_(
            _FEEDBACK_MD_PATH,
            content=base64.b64encode(updated.encode("utf-8")).decode("ascii"),
            format="AUTO", language=None, overwrite=True,
        )
        return True
    except Exception as e:
        log.warning("Could not write feedback.md: %s", e)
        return False


# ---------------------------------------------------------------------------
# Contract manifest
# ---------------------------------------------------------------------------
def _fetch_contracts() -> list[dict]:
    wc = _get_workspace_client()
    all_contracts: list[dict] = []
    prod_base = _bundle_base()
    if prod_base:
        try:
            raw = _read_volume_file(wc, f"{prod_base}/manifest.json").decode("utf-8", errors="ignore")
            for c in json.loads(raw):
                c.setdefault("source", "production")
                all_contracts.append(c)
        except Exception:
            pass
    staging = _staging_bundle_base()
    if staging:
        try:
            raw = _read_volume_file(wc, f"{staging}/manifest.json").decode("utf-8", errors="ignore")
            for c in json.loads(raw):
                c.setdefault("source", "staging")
                all_contracts.append(c)
        except Exception:
            pass
    return all_contracts


# ---------------------------------------------------------------------------
# Agent execution with streaming trace
# ---------------------------------------------------------------------------
_POLL_INTERVAL_S = 0.05


def _run_agent_streaming(
    messages: list[dict],
    selected_contracts: list[dict] | None,
    status_widget,
) -> tuple[str, list[dict], list[str], dict[str, Any]]:
    """Run agent and stream trace events to the status widget in real time."""
    trace_events: list[str] = []
    result_holder: dict = {}
    error_holder: dict = {}
    run_started_at = time.perf_counter()
    partial_text_lock = threading.Lock()
    partial_text_parts: list[str] = []
    cancel_event = threading.Event()

    async def _go():
        set_default_openai_client(AsyncDatabricksOpenAI())
        set_default_openai_api("chat_completions")
        agent = create_agent(selected_contracts=selected_contracts)
        result = Runner.run_streamed(agent, input=messages)

        t_agent_start = time.perf_counter()
        async for event in result.stream_events():
            if cancel_event.is_set():
                break
            item = getattr(event, "item", None) or {}
            if isinstance(item, dict):
                d = item
            elif hasattr(item, "to_input_item"):
                d = item.to_input_item()
            else:
                continue
            kind = d.get("type", "")
            if kind == "function_call":
                name = d.get("name", "")
                label = _TOOL_LABELS.get(name, f"Calling {name}...")
                try:
                    args_raw = d.get("arguments", "{}")
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    if not isinstance(args, dict):
                        raise TypeError("expected dict")
                    if name == "get_contract_profile" and args.get("oem"):
                        label = f"Retrieving profile for **{args['oem']}**..."
                    elif name == "retrieve_contract_context" and args.get("question"):
                        q_preview = args["question"][:80]
                        label = f'Searching: "{q_preview}"...'
                    elif name == "list_available_contracts":
                        oem_filter = args.get("oem")
                        label = f"Listing contracts{f' for {oem_filter}' if oem_filter else ''}..."
                except (json.JSONDecodeError, TypeError):
                    pass
                trace_events.append(label)
            elif kind == "function_call_output":
                out_raw = d.get("output", "")
                detail = ""
                try:
                    out = json.loads(out_raw) if isinstance(out_raw, str) else out_raw
                    if isinstance(out, dict):
                        if out.get("retrieved"):
                            detail = f" ({out['retrieved']} passages, {out.get('retrieval_mode', 'hybrid')})"
                        elif out.get("_status") == "ok" and out.get("oem"):
                            detail = f" (profile loaded for {out['oem']})"
                except (json.JSONDecodeError, TypeError):
                    pass
                trace_events.append(f"Tool completed.{detail}")
            elif kind in ("thinking", "reasoning"):
                evt_text = d.get("text", d.get("content", ""))
                if evt_text:
                    preview = evt_text.strip()[:200]
                    if preview:
                        trace_events.append(f"[thinking]{preview}")
            if kind == "message":
                for c in d.get("content", []):
                    if c.get("type") in _ANSWER_CONTENT_TYPES:
                        raw_text = c.get("text", "")
                        if raw_text.strip():
                            with partial_text_lock:
                                partial_text_parts.append(raw_text)

        t_stream_done = time.perf_counter()
        if cancel_event.is_set():
            return
        log.info("Agent stream completed in %.1fs", t_stream_done - t_agent_start)
        trace_events.append("Generating answer...")

        text_parts: list[str] = []
        tool_calls: list[dict] = []
        evidence_parts: list[str] = []
        profile_parts: list[str] = []
        retrieval_traces: list[dict[str, Any]] = []
        for item in result.new_items:
            d = item.to_input_item()
            kind = d.get("type", "")
            if kind == "message":
                for c in d.get("content", []):
                    ctype = c.get("type", "")
                    if ctype in _ANSWER_CONTENT_TYPES:
                        raw = c.get("text", "")
                        cleaned = _strip_internal_content(raw, trace_events)
                        if cleaned.strip():
                            text_parts.append(cleaned)
                    elif ctype in _TRACE_CONTENT_TYPES:
                        thinking_text = c.get("text", "")
                        if thinking_text.strip():
                            preview = thinking_text.strip()[:200]
                            trace_events.append(f"[thinking]{preview}")
                    elif ctype:
                        log.warning("Unrecognized content type %r routed to trace", ctype)
                        fallback_text = c.get("text", c.get("content", ""))
                        if fallback_text and str(fallback_text).strip():
                            trace_events.append(f"{ctype} event received.")
            elif kind == "function_call":
                tool_calls.append({
                    "name": d.get("name", "?"),
                    "arguments": d.get("arguments", "{}"),
                    "status": "called",
                })
            elif kind == "function_call_output":
                if tool_calls:
                    tool_calls[-1]["status"] = "completed"
                    tool_calls[-1]["output_preview"] = d.get("output", "")[:300]
                raw_output = d.get("output", "")
                try:
                    parsed = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
                    if isinstance(parsed, dict):
                        if parsed.get("context"):
                            evidence_parts.append(str(parsed["context"]))
                        if parsed.get("profile_summary"):
                            profile_parts.append(str(parsed["profile_summary"]))
                        if isinstance(parsed.get("retrieval_trace"), dict):
                            retrieval_traces.append(parsed["retrieval_trace"])
                except (json.JSONDecodeError, TypeError):
                    pass

        answer = "\n\n".join(text_parts) or "No response."
        answer = _strip_internal_content(answer, trace_events)
        answer = answer.strip() or "No response."

        if is_council_enabled() and evidence_parts:
            user_question = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    content = m.get("content", "")
                    if content.startswith("[Contracts:"):
                        content = content.split("\n", 1)[-1] if "\n" in content else content
                    user_question = content
                    break
            if user_question:
                combined_evidence = "\n\n".join(evidence_parts)
                combined_profile = "\n".join(profile_parts)
                trace_events.append("Running council synthesis...")
                answer = run_council(
                    question=user_question,
                    evidence=combined_evidence,
                    profile_summary=combined_profile,
                )
                answer = _strip_internal_content(answer, trace_events)

        t_total = time.perf_counter() - run_started_at
        log.info("Total agent run completed in %.1fs", t_total)
        result_holder["value"] = (
            answer,
            tool_calls,
            list(trace_events),
            {
                "elapsed_ms": int((time.perf_counter() - run_started_at) * 1000),
                "retrieval_traces": retrieval_traces,
                "tool_names": [tc.get("name") for tc in tool_calls],
            },
        )

    def _background():
        try:
            asyncio.run(_go())
        except Exception as e:
            error_holder["exc"] = e

    thread = threading.Thread(target=_background, daemon=True)
    thread.start()

    rendered = 0
    last_time_update = 0
    warned_level = 0
    while thread.is_alive():
        while rendered < len(trace_events):
            evt = trace_events[rendered]
            if evt.startswith("[thinking]"):
                status_widget.markdown(f"*{evt[10:]}*")
            else:
                status_widget.write(f"\u2022 {evt}")
            rendered += 1
        elapsed = time.perf_counter() - run_started_at
        elapsed_int = int(elapsed)
        if elapsed_int >= _AGENT_TIMEOUT_S:
            cancel_event.set()
            with partial_text_lock:
                accumulated = "\n\n".join(partial_text_parts)
            if accumulated.strip():
                cleaned = _strip_internal_content(accumulated, trace_events)
                if cleaned.strip():
                    partial_answer = (
                        cleaned.strip()
                        + "\n\n---\n\n"
                        "\u26a0\ufe0f *This response was cut short due to a timeout. "
                        "The information above may be incomplete.*"
                    )
                else:
                    partial_answer = (
                        "The response could not be completed within the time limit. "
                        "Please try rephrasing your question or selecting fewer contracts."
                    )
            else:
                partial_answer = (
                    "The response could not be completed within the time limit. "
                    "Please try rephrasing your question or selecting fewer contracts."
                )
            trace_events.append(f"Response timed out after {elapsed_int}s.")
            result_holder["value"] = (
                partial_answer,
                [],
                list(trace_events),
                {"elapsed_ms": int(elapsed * 1000), "timed_out": True},
            )
            break
        if warned_level == 0 and elapsed_int >= _AGENT_WARN_THRESHOLD_S:
            status_widget.write("\u23f3 Still processing \u2014 complex queries may take longer")
            warned_level = 1
        elif warned_level == 1 and elapsed_int >= _AGENT_WARN_THRESHOLD_S * 2:
            status_widget.write("\u26a0\ufe0f Response is taking longer than usual")
            warned_level = 2
        if elapsed_int >= 5 and elapsed_int - last_time_update >= 5:
            last_time_update = elapsed_int
            status_widget.write(f"\u23f1\ufe0f **{elapsed_int}s** elapsed")
        time.sleep(_POLL_INTERVAL_S)

    while rendered < len(trace_events):
        evt = trace_events[rendered]
        if evt.startswith("[thinking]"):
            status_widget.markdown(f"*{evt[10:]}*")
        else:
            status_widget.write(f"\u2022 {evt}")
        rendered += 1

    if "exc" in error_holder:
        raise error_holder["exc"]

    if "value" not in result_holder:
        raise RuntimeError("Agent completed but produced no result")

    return result_holder["value"]


# ---------------------------------------------------------------------------
# Inline feedback helper (used in history replay AND fresh response)
# ---------------------------------------------------------------------------
def _render_inline_feedback(msg: dict, msg_idx: int) -> None:
    """Render thumbs-up/down + comment + Send for a single assistant message."""
    existing_rating = msg.get("rating")
    comment_submitted = msg.get("feedback_comment_submitted", False)

    if existing_rating and comment_submitted:
        icon = "\U0001f44d" if existing_rating == "up" else "\U0001f44e"
        label = "Helpful" if existing_rating == "up" else "Flagged"
        comment_text = msg.get("feedback_comment", "")
        st.caption(f"{icon} {label}"
                   + (f" -- \"{comment_text}\"" if comment_text else ""))

    else:
        fb_key = f"fb_{msg_idx}"
        col_up, col_down, col_why, col_send = st.columns(
            [0.5, 0.5, 6, 1], vertical_alignment="bottom",
        )
        rating_key = f"fb_rating_{msg_idx}"
        if rating_key not in st.session_state:
            st.session_state[rating_key] = existing_rating

        with col_up:
            up_type = "primary" if st.session_state[rating_key] == "up" else "secondary"
            if st.button("\U0001f44d", key=f"{fb_key}_up", help="Helpful", type=up_type):
                st.session_state[rating_key] = "up"
                st.rerun()
        with col_down:
            dn_type = "primary" if st.session_state[rating_key] == "down" else "secondary"
            if st.button("\U0001f44e", key=f"{fb_key}_down", help="Inaccurate or unhelpful", type=dn_type):
                st.session_state[rating_key] = "down"
                st.rerun()
        with col_why:
            comment_val = st.text_input(
                "Feedback", key=f"{fb_key}_comment",
                placeholder="Why? (optional)",
                label_visibility="collapsed",
            )
        with col_send:
            if st.button("Send", key=f"{fb_key}_send", type="primary"):
                chosen_rating = st.session_state.get(rating_key)
                if not chosen_rating:
                    st.toast("\u26a0\ufe0f Select thumbs up or down first.", icon="\u26a0\ufe0f")
                else:
                    prev_q = st.session_state.messages[msg_idx - 1]["content"] if msg_idx > 0 else ""
                    _save_feedback_rating(
                        user_email, st.session_state.session_id,
                        prev_q, msg["content"], selected_contracts,
                        chosen_rating, comment=comment_val or "",
                        message_index=msg_idx,
                    )
                    st.session_state.messages[msg_idx]["rating"] = chosen_rating
                    st.session_state.messages[msg_idx]["feedback_comment"] = comment_val or ""
                    st.session_state.messages[msg_idx]["feedback_comment_submitted"] = True
                    exchange_id = msg.get("exchange_id")
                    if exchange_id:
                        _update_saved_exchange_feedback(
                            user_email,
                            st.session_state.session_id,
                            exchange_id,
                            chosen_rating,
                            comment_val or "",
                        )
                    st.rerun()


# ===========================================================================
# Sidebar
# ===========================================================================
user_email = _get_user_email()

st.sidebar.title("\U0001f4cb Warranty Agent")
if user_email and user_email != "unknown":
    st.sidebar.caption(f"Logged in as **{user_email}**")
st.sidebar.divider()

if "contracts" not in st.session_state:
    st.session_state.contracts = _fetch_contracts()
contracts = st.session_state.contracts

if st.sidebar.button("\U0001f504 Refresh contracts"):
    st.session_state.contracts = _fetch_contracts()
    contracts = st.session_state.contracts
    st.rerun()

if contracts:
    labels = [
        f"{c['oem']} -- {c['kb_id']}"
        + (" \U0001f7e2" if c.get("source") == "staging" else "")
        for c in contracts
    ]
    sel_indices = st.sidebar.multiselect(
        "Select contract(s)",
        range(len(labels)),
        default=[0] if labels else [],
        format_func=lambda i: labels[i],
    )
    selected_contracts = [contracts[i] for i in sel_indices]
else:
    st.sidebar.warning("No contracts available.")
    selected_contracts = []

st.sidebar.divider()
mode = st.sidebar.radio(
    "Mode",
    ["\U0001f4ac Contract Q&A", "\U0001f4ca Claims Evaluator",
     "\U0001f4e5 Ingest Contract", "\U0001f4dd Feedback"],
)

# ---- session state ----
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_loaded" not in st.session_state:
    st.session_state.session_loaded = False

# ---- chat history browser ----
st.sidebar.divider()
st.sidebar.subheader("Saved chats")

if user_email != "unknown":
    user_sessions = _list_user_sessions(user_email)
    if user_sessions:
        session_labels = [f"{s['name']}" for s in user_sessions]
        session_ids = [s["session_id"] for s in user_sessions]

        current_idx = 0
        if st.session_state.session_id in session_ids:
            current_idx = session_ids.index(st.session_state.session_id)

        _active_sid = st.session_state.session_id

        selected_session_idx = st.sidebar.selectbox(
            "Saved chats",
            range(len(session_labels)),
            index=current_idx,
            format_func=lambda i: (
                f"\u25b6 {session_labels[i]}" if session_ids[i] == _active_sid
                else f"  {session_labels[i]}"
            ),
            key="session_selector",
        )
        selected_session_id = session_ids[selected_session_idx]
        selected_session_name = session_labels[selected_session_idx]
        active_session_name = (
            user_sessions[current_idx]["name"]
            if _active_sid in session_ids and current_idx < len(user_sessions)
            else "Current unsaved chat"
        )

        _is_selected_active = selected_session_id == _active_sid

        st.sidebar.markdown(f"\u2705 **Active:** {active_session_name}")
        if not _is_selected_active:
            st.sidebar.caption(f"Selected: **{selected_session_name}**")

        col_load, col_new = st.sidebar.columns(2)
        with col_load:
            if st.button(
                "Open selected",
                key="load_session",
                disabled=_is_selected_active,
            ):
                sid = session_ids[selected_session_idx]
                restored = _load_session(user_email, sid)
                if restored:
                    st.session_state.messages = restored
                    st.session_state.session_id = sid
                    st.session_state.session_loaded = True
                    st.rerun()
        with col_new:
            if st.button("Start new chat", key="new_chat"):
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()

        rename_disabled = _active_sid not in session_ids
        rename_seed = active_session_name if not rename_disabled else ""
        if st.session_state.get("rename_target_session_id") != _active_sid:
            st.session_state["rename_input"] = rename_seed
            st.session_state["rename_target_session_id"] = _active_sid
        _rename_label = (
            f'Rename active chat ("{active_session_name}")'
            if not rename_disabled
            else "Rename active chat"
        )
        rename_val = st.sidebar.text_input(
            _rename_label,
            key="rename_input",
            disabled=rename_disabled,
        )
        if rename_disabled:
            st.sidebar.caption("Rename becomes available after the first saved answer.")
        if st.sidebar.button("Rename", key="rename_btn", disabled=rename_disabled):
            if rename_val.strip():
                _rename_session(user_email, _active_sid, rename_val.strip())
                st.rerun()
    else:
        st.sidebar.caption("No saved chats yet.")

        if not st.session_state.session_loaded:
            st.session_state.session_loaded = True
else:
    st.sidebar.caption("Log in to see chat history.")


# ===========================================================================
# MODE 1 -- Contract Q&A
# ===========================================================================
if "Q&A" in mode:
    st.title("Contract Q&A")
    if not selected_contracts:
        st.warning("Select at least one contract in the sidebar.")
        st.stop()

    if len(selected_contracts) == 1:
        st.caption(f"Querying **{selected_contracts[0]['oem']} -- {selected_contracts[0]['kb_id']}**")
    else:
        labels_str = ", ".join(f"**{c['oem']} -- {c['kb_id']}**" for c in selected_contracts)
        st.caption(f"Querying {labels_str}")

    for msg_idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                _render_assistant_md(msg["content"])
            else:
                st.markdown(msg["content"])

            if msg["role"] == "assistant":
                for tc in msg.get("tool_calls", []):
                    with st.expander(f"\U0001f527 {tc['name']} -- {tc['status']}"):
                        st.code(tc.get("arguments", ""), language="json")
                        if tc.get("output_preview"):
                            st.text(tc["output_preview"])

                _render_inline_feedback(msg, msg_idx)

    if prompt := st.chat_input("Ask about the warranty contract(s)..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        contract_tag = ", ".join(
            f"OEM={c['oem']} contract_id={c['kb_id']}" for c in selected_contracts
        )
        input_items: list[dict] = []
        for i, msg in enumerate(st.session_state.messages):
            content = msg["content"]
            if msg["role"] == "user" and i == len(st.session_state.messages) - 1:
                content = f"[Contracts: {contract_tag}]\n{content}"
            input_items.append({"role": msg["role"], "content": content})

        with st.chat_message("assistant"):
            text = ""
            tool_calls: list[dict] = []
            trace: list[str] = []
            run_meta: dict[str, Any] = {}
            run_ok = False
            exchange_id = str(uuid.uuid4())
            with st.status("Thinking...", expanded=True) as status:
                try:
                    text, tool_calls, trace, run_meta = _run_agent_streaming(
                        input_items,
                        selected_contracts=selected_contracts,
                        status_widget=status,
                    )
                    timed_out = run_meta.get("timed_out", False)
                    elapsed_s = run_meta.get("elapsed_ms", 0) / 1000
                    done_label = f"Thought for {elapsed_s:.0f}s" if elapsed_s > 0 else "Done"
                    status.update(
                        label="Timed out" if timed_out else done_label,
                        state="error" if timed_out else "complete",
                        expanded=timed_out,
                    )
                    run_ok = True
                except Exception as exc:
                    status.update(label="Error", state="error")
                    st.error(f"Error: {exc}")

            if run_ok:
                answer_area = st.container()
                with answer_area:
                    _render_assistant_md(text)
                    st.markdown(
                        (
                            f'<div data-qa="qa-response-complete" '
                            f'data-exchange-id="{exchange_id}" '
                            'style="height:0;overflow:hidden;opacity:0;">Done</div>'
                        ),
                        unsafe_allow_html=True,
                    )
                    for tc in tool_calls:
                        with st.expander(f"\U0001f527 {tc['name']} -- {tc['status']}"):
                            st.code(tc.get("arguments", ""), language="json")
                            if tc.get("output_preview"):
                                st.text(tc["output_preview"])
                    if trace:
                        with st.expander("View process trace", expanded=False):
                            for i, step in enumerate(trace, 1):
                                st.markdown(f"**Step {i}** \u2014 {step}")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": text,
                        "tool_calls": tool_calls,
                        "exchange_id": exchange_id,
                        "elapsed_ms": run_meta.get("elapsed_ms"),
                        "retrieval_trace": run_meta.get("retrieval_traces") or [],
                    }
                )
                saved = _save_exchange(
                    user_email, st.session_state.session_id,
                    selected_contracts, prompt, text, tool_calls,
                    exchange_id=exchange_id,
                    elapsed_ms=run_meta.get("elapsed_ms"),
                    retrieval_trace=run_meta.get("retrieval_traces") or [],
                )
                if saved:
                    st.toast("Chat auto-saved", icon="\U0001f4be")
                msg_idx = len(st.session_state.messages) - 1
                _render_inline_feedback(st.session_state.messages[msg_idx], msg_idx)


# ===========================================================================
# MODE 2 -- Claims Evaluator
# ===========================================================================
elif "Claims" in mode:
    st.title("Claims Evaluator")
    if not contracts:
        st.warning("No contracts available. Refresh the sidebar.")
        st.stop()
    _claims_labels = [
        f"{c['oem']} -- {c['kb_id']}" for c in contracts
    ]
    _claims_default = 0
    if selected_contracts:
        for _ci, _cc in enumerate(contracts):
            if (
                _cc.get("oem") == selected_contracts[0].get("oem")
                and _cc.get("kb_id") == selected_contracts[0].get("kb_id")
            ):
                _claims_default = _ci
                break
    contract_idx = st.selectbox(
        "Contract for claims evaluation",
        range(len(_claims_labels)),
        index=_claims_default,
        format_func=lambda i: _claims_labels[i],
    )
    contract = contracts[contract_idx]
    st.caption(f"Evaluating against **{contract['oem']} -- {contract['kb_id']}**")

    EVAL_MODELS = {
        "Claude Opus 4.6 \u2014 Accurate": "databricks-claude-opus-4-6",
        "GPT-4.1 \u2014 Balanced": "gpt_41",
        "Gemini 2.5 Flash \u2014 Fast": "gemini_25_flash",
    }
    model_label = st.selectbox("Evaluation model", list(EVAL_MODELS.keys()))
    selected_model_ep = EVAL_MODELS[model_label]

    uploaded = st.file_uploader("Upload claims file", type=["csv", "xlsx", "xls"])
    if uploaded:
        try:
            uploaded.seek(0)
            if uploaded.name.lower().endswith((".xlsx", ".xls")):
                preview_df = pd.read_excel(uploaded, engine="openpyxl")
            else:
                preview_df = pd.read_csv(uploaded)
            st.subheader(f"Preview ({len(preview_df)} rows)")
            st.dataframe(preview_df.head(10), width="stretch")

            col_lookup, col_warnings = _smart_col_lookup(preview_df)
            st.subheader("Column Mapping")
            mapping_rows = []
            for canon, col in sorted(col_lookup.items()):
                status = "Critical" if canon in CRITICAL_FIELDS else (
                    "Important" if canon in IMPORTANT_FIELDS else "Optional")
                mapping_rows.append({"Dataset Column": col, "Mapped To": canon, "Priority": status})
            if mapping_rows:
                st.dataframe(pd.DataFrame(mapping_rows), width="stretch", hide_index=True)
            else:
                st.error("No columns could be mapped.")
            for w in col_warnings:
                if "CRITICAL" in w: st.error(w)
                elif "WARNING" in w: st.warning(w)
                else: st.info(w)
            uploaded.seek(0)
        except Exception as exc:
            st.error(f"Could not read file: {exc}")
            preview_df = None

        if preview_df is not None and st.button("Evaluate Claims", type="primary"):
            raw = uploaded.read()
            status_area = st.empty()
            progress_bar = st.progress(0)

            def _claims_progress(msg: str):
                status_area.info(msg)
                if "Loading contract" in msg or "Mapping" in msg:
                    progress_bar.progress(10)
                elif "claim" in msg and "/" in msg:
                    m = re.search(r"(\d+)/(\d+)", msg)
                    if m:
                        pct = 10 + int(85 * int(m.group(1)) / max(1, int(m.group(2))))
                        progress_bar.progress(min(pct, 95))
                elif "Done" in msg:
                    progress_bar.progress(100)

            try:
                rows, eval_warnings = evaluate_claims_file(
                    file_bytes=raw, filename=uploaded.name,
                    oem=contract["oem"], contract_id=contract["kb_id"],
                    progress_callback=_claims_progress, model_endpoint=selected_model_ep,
                )
                progress_bar.progress(100)
                if rows:
                    df = pd.DataFrame(rows)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("In Warranty", int((df["decision"] == "in_warranty").sum()))
                    c2.metric("Out of Warranty", int((df["decision"] == "out_of_warranty").sum()))
                    c3.metric("Needs Review", int(
                        (df["decision"] == "requires_review").sum()
                        + (df["decision"] == "insufficient_info").sum()))
                    if "confidence" in df.columns:
                        c4.metric("High Confidence", int((df["confidence"] == "high").sum()))
                    st.subheader("Results")
                    st.dataframe(df, width="stretch")
                    st.download_button("Download Results (CSV)", df.to_csv(index=False),
                                       file_name="claims_results.csv", mime="text/csv")
                else:
                    st.info("No claims processed.")
            except Exception as exc:
                st.error(f"Evaluation failed: {exc}")


# ===========================================================================
# MODE 3 -- Ingest Contract
# ===========================================================================
elif "Ingest" in mode:
    st.title("Ingest New Contract")
    st.markdown("Upload warranty contract documents to create a new searchable contract. "
                "Supported formats: PDF, Outlook email (.msg), PowerPoint, Excel, HTML, and images.")
    st.caption("Large or scanned documents can take several minutes to process. Keep this tab open until the summary appears.")
    staging = _staging_bundle_base()
    if not staging:
        st.error("Staging volume not configured.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        new_oem = st.text_input("OEM Name", placeholder="e.g. JLR, BMW, Toyota")
    with col2:
        new_kb_id = st.text_input("Contract ID", placeholder="e.g. JLR_Warranty_2025",
                                   help="Unique identifier for this staging contract bundle")
    uploaded_docs = st.file_uploader(
        "Upload contract documents",
        type=["pdf", "msg", "pptx", "xlsx", "xls", "htm", "html", "mht", "png", "bmp", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    clean_oem = (new_oem or "").strip()
    clean_kb_id = (new_kb_id or "").strip()
    oem_valid = not clean_oem or bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}", clean_oem))
    kb_id_valid = not clean_kb_id or bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", clean_kb_id))

    staging_exists = False
    production_exists = False
    if clean_oem and clean_kb_id:
        for contract_row in contracts:
            same_key = contract_row.get("oem") == clean_oem and contract_row.get("kb_id") == clean_kb_id
            if not same_key:
                continue
            if contract_row.get("source") == "staging":
                staging_exists = True
            else:
                production_exists = True

    if clean_oem and not oem_valid:
        st.error("OEM Name may contain letters, numbers, spaces, periods, underscores, and hyphens only.")
    if clean_kb_id and not kb_id_valid:
        st.error("Contract ID may contain letters, numbers, periods, underscores, and hyphens only.")
    if clean_kb_id:
        st.caption("Contract ID should be stable and path-safe, for example `JLR_Warranty_2025`.")
    if production_exists:
        st.info("A production contract with this OEM and Contract ID already exists. This upload creates a staging copy only.")
    if staging_exists:
        st.warning("A staging contract with this OEM and Contract ID already exists and will be replaced.")

    overwrite_ok = True
    if staging_exists:
        overwrite_ok = st.checkbox(
            "I understand the existing staging contract will be replaced.",
            value=False,
        )

    can_submit = bool(clean_oem and clean_kb_id and uploaded_docs and oem_valid and kb_id_valid and overwrite_ok)

    if clean_oem and clean_kb_id and uploaded_docs:
        st.info(f"Ready to process **{len(uploaded_docs)}** file(s) for **{clean_oem} / {clean_kb_id}**")
        if st.button("\U0001f680 Upload & Process", type="primary", disabled=not can_submit):
            wc = _get_workspace_client()
            files = [(f.name, f.read()) for f in uploaded_docs]
            status_area = st.empty()
            progress_bar = st.progress(0)

            def _update(msg: str):
                status_area.info(msg)

            try:
                _update(f"Uploading {len(files)} file(s)...")
                progress_bar.progress(10)
                upload_files(wc, clean_oem, clean_kb_id, files)
                progress_bar.progress(20)
                result = ingest_inline(wc, oem=clean_oem, kb_id=clean_kb_id,
                                        files=files, progress_callback=_update)
                progress_bar.progress(100)
                if result["status"] in ("success", "partial"):
                    st.success(
                        f"Contract processed: {result['doc_count']} document(s), {result['chunk_count']} chunks, staging entry updated."
                    )
                    st.markdown(
                        "\n".join([
                            f"- Contract: `{clean_oem} / {clean_kb_id}`",
                            f"- Raw upload path: `{staging_raw_dir(clean_oem, clean_kb_id)}`",
                            f"- Staging manifest: `{staging}/manifest.json`",
                            "- Next step: click **Refresh contracts** in the sidebar and confirm the contract appears.",
                        ])
                    )
                    if result.get("failed_docs"):
                        st.warning("Failed: " + ", ".join(result["failed_docs"]))
                else:
                    st.error(f"Failed: {result.get('message', 'Unknown error')}")
            except Exception as exc:
                st.error(f"Processing failed: {exc}")
    elif not new_oem or not new_kb_id:
        st.info("Enter an OEM name and contract ID to get started.")


# ===========================================================================
# MODE 4 -- Feedback
# ===========================================================================
elif "Feedback" in mode:
    st.title("Feedback")
    st.markdown("Help us improve the agent. Describe issues, inaccuracies, or suggestions below.")

    feedback_text = st.text_area("Describe the issue or suggestion", height=200,
        placeholder="Example: The answer missed an important mileage limit and the supporting citation.")
    fb_col1, fb_col2 = st.columns(2)
    with fb_col1:
        fb_category = st.selectbox("Category",
            ["Inaccuracy / Hallucination", "Missing Information", "Slow Response",
             "UI Issue", "Feature Request", "Other"])
    with fb_col2:
        fb_severity = st.selectbox("Severity", ["Critical", "High", "Medium", "Low"])
    fb_contract = st.text_input("Related contract (if applicable)", placeholder="e.g. BMW, JLR_Warranty")

    if feedback_text and st.button("Submit Feedback", type="primary"):
        with st.spinner("Structuring feedback..."):
            structure_prompt = (
                "You are a QA analyst. Structure this feedback into markdown.\n\n"
                f"Category: {fb_category}\nSeverity: {fb_severity}\n"
                f"Contract: {fb_contract or 'Not specified'}\nUser: {user_email}\n"
                f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"Feedback:\n{feedback_text}\n\n"
                "Use ONLY details explicitly provided above. Do NOT invent steps, expectations, actual behavior, or suggested fixes. "
                "If a section is not supported by the feedback text, write 'Not provided'.\n\n"
                "Output markdown with: Status: OPEN, ID: FB-<YYYYMMDD>-<slug>, "
                "Category, Severity, Contract, Reporter, Date, Description, "
                "Steps to Reproduce, Expected Behavior, Actual Behavior, Suggested Fix. "
                "Use ### for the ID heading. Be concise."
            )
            structured = _call_llm(structure_prompt, temperature=0.0)
            if structured:
                saved = _append_feedback_md(structured)
                _save_feedback_rating(user_email, st.session_state.session_id,
                    f"[FEEDBACK] {fb_category}", feedback_text[:500],
                    selected_contracts, "feedback", comment=feedback_text,
                    related_contract=fb_contract or "")
                if saved:
                    st.success("Feedback submitted. Thank you!")
                    st.markdown(structured)
                else:
                    st.error("Feedback was structured, but writing feedback.md failed. Check Databricks workspace permissions.")
            else:
                st.error("Could not structure feedback. Please try again.")

    st.divider()
    st.subheader("Recent Feedback")
    try:
        wc = _get_workspace_client()
        raw = _read_volume_file(wc, f"{_FEEDBACK_VOLUME}/feedback_log.jsonl").decode("utf-8", errors="ignore")
        entries = [json.loads(l) for l in raw.strip().split("\n") if l.strip()]
        if entries:
            for entry in reversed(entries[-20:]):
                ts = entry.get("timestamp", "")[:16].replace("T", " ")
                icon = "\U0001f44d" if entry.get("rating") == "up" else (
                    "\U0001f44e" if entry.get("rating") == "down" else "\U0001f4dd")
                st.caption(f"{icon} **{ts}** | {entry.get('user', '?')} | "
                           f"{entry.get('rating', '')} | {entry.get('question', '')[:80]}")
        else:
            st.info("No feedback yet.")
    except Exception:
        st.info("No feedback log found yet.")
