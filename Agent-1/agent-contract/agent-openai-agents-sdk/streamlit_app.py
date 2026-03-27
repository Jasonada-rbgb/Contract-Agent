"""Warranty Contract Agent -- Streamlit App (single-process).

Four modes:
  1. Contract Q&A     -- chat with the agent (per-user memory, thinking panel, inline feedback)
  2. Claims Evaluator -- upload CSV/XLSX, evaluate claims
  3. Ingest Contract  -- upload PDFs, trigger ingestion pipeline
  4. Feedback         -- submit structured feedback for agent improvement
"""

import asyncio
import concurrent.futures
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient

from agent_server.agent import create_agent, _bundle_base, _staging_bundle_base, _read_volume_file, _call_llm
from agent_server.claims_batch import evaluate_claims_file, _smart_col_lookup, CRITICAL_FIELDS, IMPORTANT_FIELDS
from agent_server.ingest import (
    upload_pdfs,
    ingest_inline,
    read_staging_manifest,
    staging_bundle_base,
    staging_raw_dir,
)
from agents import Runner, set_default_openai_api, set_default_openai_client
from databricks_openai import AsyncDatabricksOpenAI

log = logging.getLogger(__name__)

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)

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
    rating: str | None = None,
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": email,
        "session_id": session_id,
        "contracts": [{"oem": c.get("oem"), "kb_id": c.get("kb_id")} for c in (contracts or [])],
        "question": question,
        "response": response[:5000],
        "tool_calls": [tc.get("name") for tc in tool_calls],
        "rating": rating,
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
    except Exception as e:
        log.debug("Could not save exchange: %s", e)


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
            messages.append({
                "role": "assistant",
                "content": record.get("response", ""),
                "tool_calls": [],
                "rating": record.get("rating"),
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
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": email, "session_id": session_id,
        "question": question, "response_preview": response_preview[:500],
        "contracts": [{"oem": c.get("oem"), "kb_id": c.get("kb_id")} for c in (contracts or [])],
        "rating": rating, "comment": comment,
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


def _append_feedback_md(structured_feedback: str):
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
    except Exception as e:
        log.warning("Could not write feedback.md: %s", e)


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
def _run_agent_with_trace(
    messages: list[dict],
    selected_contracts: list[dict] | None = None,
) -> tuple[str, list[dict], list[str]]:
    async def _go():
        set_default_openai_client(AsyncDatabricksOpenAI())
        set_default_openai_api("chat_completions")
        agent = create_agent(selected_contracts=selected_contracts)
        result = Runner.run_streamed(agent, input=messages)
        trace: list[str] = []
        async for event in result.stream_events():
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
                trace.append(label)
            elif kind == "function_call_output":
                trace.append("Tool completed.")

        text_parts: list[str] = []
        tool_calls: list[dict] = []
        for item in result.new_items:
            d = item.to_input_item()
            kind = d.get("type", "")
            if kind == "message":
                for c in d.get("content", []):
                    if c.get("type") == "output_text":
                        text_parts.append(c.get("text", ""))
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
        return "\n\n".join(text_parts) or "No response.", tool_calls, trace

    future = _EXECUTOR.submit(asyncio.run, _go())
    return future.result(timeout=300)


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
st.sidebar.subheader("Chat History")

if user_email != "unknown":
    user_sessions = _list_user_sessions(user_email)
    if user_sessions:
        session_labels = [f"{s['name']}" for s in user_sessions]
        session_ids = [s["session_id"] for s in user_sessions]

        current_idx = 0
        if st.session_state.session_id in session_ids:
            current_idx = session_ids.index(st.session_state.session_id)

        selected_session_idx = st.sidebar.selectbox(
            "Previous chats",
            range(len(session_labels)),
            index=current_idx,
            format_func=lambda i: session_labels[i],
            key="session_selector",
        )

        col_load, col_new = st.sidebar.columns(2)
        with col_load:
            if st.button("Load", key="load_session"):
                sid = session_ids[selected_session_idx]
                restored = _load_session(user_email, sid)
                if restored:
                    st.session_state.messages = restored
                    st.session_state.session_id = sid
                    st.session_state.session_loaded = True
                    st.rerun()
        with col_new:
            if st.button("New Chat", key="new_chat"):
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()

        rename_val = st.sidebar.text_input(
            "Rename current chat",
            value=user_sessions[current_idx]["name"] if current_idx < len(user_sessions) else "",
            key="rename_input",
        )
        if st.sidebar.button("Rename", key="rename_btn"):
            if rename_val.strip():
                _rename_session(user_email, st.session_state.session_id, rename_val.strip())
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
            st.markdown(msg["content"])

            if msg["role"] == "assistant":
                for tc in msg.get("tool_calls", []):
                    with st.expander(f"\U0001f527 {tc['name']} -- {tc['status']}"):
                        st.code(tc.get("arguments", ""), language="json")
                        if tc.get("output_preview"):
                            st.text(tc["output_preview"])

                existing_rating = msg.get("rating")
                comment_submitted = msg.get("feedback_comment_submitted", False)

                if existing_rating and comment_submitted:
                    icon = "\U0001f44d" if existing_rating == "up" else "\U0001f44e"
                    comment_text = msg.get("feedback_comment", "")
                    st.caption(f"{icon} {'Helpful' if existing_rating == 'up' else 'Flagged'}"
                               + (f" -- \"{comment_text}\"" if comment_text else ""))

                elif existing_rating and not comment_submitted:
                    icon = "\U0001f44d" if existing_rating == "up" else "\U0001f44e"
                    st.caption(f"{icon} {'Helpful' if existing_rating == 'up' else 'Flagged for review'}")
                    comment_val = st.text_input(
                        "Why? (optional)",
                        key=f"fb_comment_{msg_idx}",
                        placeholder="What was good/bad about this response?",
                    )
                    c_submit, c_skip, _ = st.columns([1, 1, 8])
                    with c_submit:
                        if st.button("Submit", key=f"fb_submit_{msg_idx}"):
                            prev_q = st.session_state.messages[msg_idx - 1]["content"] if msg_idx > 0 else ""
                            _save_feedback_rating(
                                user_email, st.session_state.session_id,
                                prev_q, msg["content"], selected_contracts,
                                existing_rating, comment=comment_val or "",
                            )
                            st.session_state.messages[msg_idx]["feedback_comment"] = comment_val or ""
                            st.session_state.messages[msg_idx]["feedback_comment_submitted"] = True
                            st.rerun()
                    with c_skip:
                        if st.button("Skip", key=f"fb_skip_{msg_idx}"):
                            prev_q = st.session_state.messages[msg_idx - 1]["content"] if msg_idx > 0 else ""
                            _save_feedback_rating(
                                user_email, st.session_state.session_id,
                                prev_q, msg["content"], selected_contracts,
                                existing_rating,
                            )
                            st.session_state.messages[msg_idx]["feedback_comment_submitted"] = True
                            st.rerun()

                else:
                    col_up, col_down, _ = st.columns([1, 1, 10])
                    with col_up:
                        if st.button("\U0001f44d", key=f"fb_{msg_idx}_up", help="Helpful"):
                            st.session_state.messages[msg_idx]["rating"] = "up"
                            st.rerun()
                    with col_down:
                        if st.button("\U0001f44e", key=f"fb_{msg_idx}_down", help="Inaccurate or unhelpful"):
                            st.session_state.messages[msg_idx]["rating"] = "down"
                            st.rerun()

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
            with st.status("Thinking...", expanded=True) as status:
                try:
                    text, tool_calls, trace = _run_agent_with_trace(
                        input_items, selected_contracts=selected_contracts,
                    )
                    for step in trace:
                        status.write(step)
                    status.update(label="Done", state="complete", expanded=False)

                    st.markdown(text)
                    for tc in tool_calls:
                        with st.expander(f"\U0001f527 {tc['name']} -- {tc['status']}"):
                            st.code(tc.get("arguments", ""), language="json")
                            if tc.get("output_preview"):
                                st.text(tc["output_preview"])
                    st.session_state.messages.append(
                        {"role": "assistant", "content": text, "tool_calls": tool_calls}
                    )
                    _save_exchange(
                        user_email, st.session_state.session_id,
                        selected_contracts, prompt, text, tool_calls,
                    )
                except Exception as exc:
                    status.update(label="Error", state="error")
                    st.error(f"Error: {exc}")


# ===========================================================================
# MODE 2 -- Claims Evaluator
# ===========================================================================
elif "Claims" in mode:
    st.title("Claims Evaluator")
    if not selected_contracts:
        st.warning("Select a contract in the sidebar.")
        st.stop()
    if len(selected_contracts) > 1:
        st.warning("Claims Evaluator works with one contract at a time.")
        st.stop()
    contract = selected_contracts[0]
    st.caption(f"Evaluating against **{contract['oem']} -- {contract['kb_id']}**")

    EVAL_MODELS = {
        "Gemini 2.5 Flash \u2014 Fast": "gemini_25_flash",
        "Claude Opus \u2014 Accurate": "databricks-claude-opus-4-6",
        "o3 \u2014 Deep reasoning": "openai_o3",
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
    st.markdown("Upload warranty contract PDFs to create a new searchable contract. "
                "PDFs are parsed and indexed directly \u2014 no separate cluster needed.")
    staging = _staging_bundle_base()
    if not staging:
        st.error("Staging volume not configured.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        new_oem = st.text_input("OEM Name", placeholder="e.g. JLR, BMW, Toyota")
    with col2:
        new_kb_id = st.text_input("Contract ID", placeholder="e.g. JLR_Warranty_2025",
                                   help="Unique identifier for this contract bundle")
    pdfs = st.file_uploader("Upload contract PDF(s)", type=["pdf"], accept_multiple_files=True)

    if new_oem and new_kb_id and pdfs:
        st.info(f"Ready to process **{len(pdfs)}** PDF(s) for **{new_oem} / {new_kb_id}**")
        if st.button("\U0001f680 Upload & Process", type="primary"):
            wc = _get_workspace_client()
            files = [(f.name, f.read()) for f in pdfs]
            status_area = st.empty()
            progress_bar = st.progress(0)

            def _update(msg: str):
                status_area.info(msg)

            try:
                _update(f"Uploading {len(files)} PDF(s)...")
                progress_bar.progress(10)
                upload_pdfs(wc, new_oem, new_kb_id, files)
                progress_bar.progress(20)
                result = ingest_inline(wc, oem=new_oem, kb_id=new_kb_id,
                                        pdf_files=files, progress_callback=_update)
                progress_bar.progress(100)
                if result["status"] in ("success", "partial"):
                    st.success(f"Done! {result['chunk_count']} chunks from {result['doc_count']} doc(s). "
                               "Click **Refresh contracts** in the sidebar.")
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
        placeholder="Example: The agent said 96 months for BMW HV batteries but didn't mention the 160,000 km limit.")
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
                "Output markdown with: Status: OPEN, ID: FB-<YYYYMMDD>-<slug>, "
                "Category, Severity, Contract, Reporter, Date, Description, "
                "Steps to Reproduce, Expected Behavior, Actual Behavior, Suggested Fix. "
                "Use ### for the ID heading. Be concise."
            )
            structured = _call_llm(structure_prompt, temperature=0.0)
            if structured:
                _append_feedback_md(structured)
                _save_feedback_rating(user_email, st.session_state.session_id,
                    f"[FEEDBACK] {fb_category}", feedback_text[:500],
                    selected_contracts, "feedback", comment=feedback_text)
                st.success("Feedback submitted. Thank you!")
                st.markdown(structured)
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
