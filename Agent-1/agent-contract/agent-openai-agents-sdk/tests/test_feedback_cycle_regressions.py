"""Focused regressions for feedback-cycle fixes."""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_server import claims_batch


def _load_symbols_from_source(path: str, symbol_names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    selected_nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in symbol_names:
            selected_nodes.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in symbol_names:
                selected_nodes.append(node)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(name in symbol_names for name in targets):
                selected_nodes.append(node)
    module = ast.Module(body=selected_nodes, type_ignores=[])
    exec(compile(module, path, "exec"), namespace)
    return namespace


_AGENT_NS = _load_symbols_from_source(
    os.path.join(os.path.dirname(__file__), "..", "agent_server", "agent.py"),
    {"_HIGH_IMPACT_PROFILE_DEFAULTS", "_coerce_citation_numbers", "_ground_contract_profile"},
    {"Any": Any, "re": re},
)
_ground_contract_profile = _AGENT_NS["_ground_contract_profile"]

_START_SERVER_NS = _load_symbols_from_source(
    os.path.join(os.path.dirname(__file__), "..", "agent_server", "start_server.py"),
    {"_serialize_claims_response"},
    {"Any": Any, "Dict": Dict},
)
_serialize_claims_response = _START_SERVER_NS["_serialize_claims_response"]


def test_ground_contract_profile_drops_uncited_high_impact_fields():
    profile = {
        "reference_market": ["USA", "Canada"],
        "market_definitions": {"reference_market": "USA and Canada"},
        "warranty_periods": [{"market": "reference_market", "months": 48}],
        "key_terms": {"goodwill": "commercial discretion"},
        "citations": {"key_terms": [4]},
    }

    grounded = _ground_contract_profile(profile)

    assert grounded["reference_market"] == []
    assert grounded["market_definitions"] == {}
    assert grounded["warranty_periods"] == []
    assert grounded["key_terms"] == {"goodwill": "commercial discretion"}
    assert grounded["verification"]["reference_market"]["supported"] is False
    assert grounded["verification"]["key_terms"]["supported"] is True


def test_build_claim_retrieval_queries_uses_row_specific_fields():
    queries = claims_batch._build_claim_retrieval_queries(
        {
            "country": "Germany",
            "part_description": "wiper blades",
            "mileage": 8200,
            "warranty_start_date": "2024-01-01",
            "repair_date": "2024-08-01",
        },
        {"verification": {"reference_market": {"supported": False}}},
    )

    assert any("Germany" in query for query in queries)
    assert any("wiper blades" in query for query in queries)
    assert any("mileage limit" in query for query in queries)
    assert len(queries) <= 4


def test_evaluate_claims_table_uses_row_specific_passages(monkeypatch):
    df = pd.DataFrame([
        {"country": "Germany", "part_description": "wiper blades"},
        {"country": "USA", "part_description": "battery"},
    ])

    monkeypatch.setattr(
        claims_batch,
        "_smart_col_lookup",
        lambda data, llm_endpoint=None: (
            {"country": "country", "part_description": "part_description"},
            [],
        ),
    )

    load_calls = []
    retrieve_calls = []

    def fake_load(oem, contract_id):
        load_calls.append((oem, contract_id))
        return {
            "profile": {"_status": "ok"},
            "rows": [],
            "bm25": None,
            "embeddings": None,
            "base_hits": [],
            "base_context": "",
        }

    def fake_retrieve(contract_assets, claim_data):
        retrieve_calls.append((claim_data["country"], claim_data["part_description"]))
        return (
            f"context for {claim_data['country']} {claim_data['part_description']}",
            {
                "scope": "row_aware",
                "queries": [claim_data["country"], claim_data["part_description"]],
            },
        )

    def fake_eval(claim_data, profile, contract_passages, endpoint):
        return {
            "decision": "requires_review",
            "reason": contract_passages,
            "confidence": "medium",
            "contract_references": ["[1]"],
            "applicable_rule": {},
        }

    monkeypatch.setattr(claims_batch, "_load_contract_assets", fake_load)
    monkeypatch.setattr(claims_batch, "_retrieve_claim_passages", fake_retrieve)
    monkeypatch.setattr(claims_batch, "_evaluate_single_claim", fake_eval)

    rows, warnings = claims_batch.evaluate_claims_table(
        df,
        oem="JLR",
        contract_id="JLR_Warranty",
        model_endpoint="openai_o3",
    )

    assert warnings == []
    assert load_calls == [("JLR", "JLR_Warranty")]
    assert retrieve_calls == [
        ("Germany", "wiper blades"),
        ("USA", "battery"),
    ]
    assert rows[0]["retrieval_scope"] == "row_aware"
    assert rows[1]["retrieval_scope"] == "row_aware"
    assert rows[0]["reason"] == "context for Germany wiper blades"
    assert rows[1]["reason"] == "context for USA battery"


def test_serialize_claims_response_separates_rows_and_mapping_warnings():
    rows = [{"row_index": 0, "decision": "requires_review"}]
    mapping_warnings = ["WARNING: missing mileage column"]

    payload = _serialize_claims_response("JLR", "JLR_Warranty", rows, mapping_warnings)

    assert payload["oem"] == "JLR"
    assert payload["contract_id"] == "JLR_Warranty"
    assert payload["rows"] == rows
    assert payload["mapping_warnings"] == mapping_warnings


def test_feedback_placeholder_is_generic():
    app_src = Path(os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")).read_text(encoding="utf-8")
    assert "96 months for BMW HV batteries" not in app_src
    assert "160,000 km limit" not in app_src


def test_feedback_prompt_forbids_invented_sections():
    app_src = Path(os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")).read_text(encoding="utf-8")
    assert "Do NOT invent steps, expectations, actual behavior, or suggested fixes" in app_src
    assert "write 'Not provided'" in app_src
