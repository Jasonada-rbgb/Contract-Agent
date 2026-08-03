"""Unit tests for the portable MBC GALA compile-once scenario engine."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "methodology" / "01_reproduced" / "mbc_gala_scenario_engine.py"
SCRIPTS_PATH = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))
SPEC = importlib.util.spec_from_file_location("mbc_gala_scenario_engine", MODULE_PATH)
assert SPEC and SPEC.loader
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)


RULE = {
    "part_family_numbers": ["AA-EXAMPLE-1"],
    "supplier_numbers": ["123"],
    "part_numbers": ["A0001"],
    "acceptance_rate_percent": 20,
    "anfallsjahr_from": 2024,
}


def test_family_rule_settles_by_quantity_not_cost() -> None:
    result = ENGINE.apply_signed_gala_matrix(
        {
            "part_family_number": "AA-EXAMPLE-1",
            "receipt_date_year": 2024,
            "replaced_quantity_apportioned": 2,
            "material_price_invoicing": 100,
            "labor_cost_average": 50,
        },
        [RULE],
    )

    assert result.status == "settled"
    assert result.match_basis == "part_family_number"
    assert result.accepted_quantity == 0.4
    assert result.reference_cost_only == 60.0
    assert result.cost_is_reference_only is True


def test_supplier_part_is_only_a_fallback_match() -> None:
    result = ENGINE.apply_signed_gala_matrix(
        {"supplier_number": "123", "part_number": "A0001", "receipt_date_year": 2024},
        [RULE],
    )

    assert result.status == "settled"
    assert result.match_basis == "supplier_part_number"


def test_temporal_block_routes_back_to_main_contract() -> None:
    result = ENGINE.apply_signed_gala_matrix(
        {"part_family_number": "AA-EXAMPLE-1", "receipt_date_year": 2023}, [RULE]
    )

    assert result.status == "fall_through"
    assert "temporal gate blocked" in result.reason


def test_undetermined_quote_requires_review() -> None:
    null_quote_rule = {**RULE, "acceptance_rate_percent": None}
    result = ENGINE.apply_signed_gala_matrix(
        {"part_family_number": "AA-EXAMPLE-1", "receipt_date_year": 2024}, [null_quote_rule]
    )

    assert result.status == "requires_review"


def test_quote_agent_returns_a_quantity_factor_not_a_cost_rate() -> None:
    from payment_factor_agents import GalaQuoteAcceptanceAgent

    result = GalaQuoteAcceptanceAgent().factor(
        acceptance_rate_percent=20, source_ref="GALA matrix rule fingerprint"
    )

    assert result.rate == 0.2
    assert result.rate_source == "GALA_signed_matrix"
    assert "quantity apportionment" in result.rate_basis
    assert "not a monetary payment rate" in result.warnings[0]
