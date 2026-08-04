"""Behaviour tests for the additive, profile-driven payment-factor core."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
TODAY = datetime.now(timezone.utc).date()

from payment_factor_core import (
    InMemoryLearnedRuleCache,
    LearnedRule,
    PaymentFactorEngine,
    ProfileRegistry,
)


@pytest.fixture
def engine() -> PaymentFactorEngine:
    registry = ProfileRegistry.from_directory(ROOT / "profiles")
    return PaymentFactorEngine(registry)


@pytest.fixture
def mbc_claim() -> dict[str, object]:
    return {
        "claim_id": "claim-1",
        "part_family_number": "AA100",
        "supplier_number": "123",
        "part_number": "A100",
        "receipt_date_year": 2025,
        "vehicle_origin_production_date": "2024-01-15",
        "replaced_quantity_apportioned": 10,
        "material_price_invoicing": 10,
        "labor_cost_average": 5,
        "incidental_costs_aqua": 0,
        "mobility_costs_aqua": 0,
        "contract_type": "standard",
        "technical_warranty_type_tga": "TGA",
        "division": "PC",
        "production_to_repair_cap": "within_cap",
        "warranty_start_date": "2024-01-01",
        "repair_date": "2025-01-01",
    }


@pytest.fixture
def matrix_assets() -> dict[str, object]:
    return {
        "signed_gala_matrix": [
            {
                "rule_id": "agreement-1-row-1",
                "source_filename": "agreement-1.pdf",
                "part_family_numbers": ["AA100"],
                "supplier_numbers": ["123"],
                "part_numbers": ["A100"],
                "acceptance_rate_percent": 20,
                "anfallsjahr_from": 2024,
                "production_start": None,
                "production_end": None,
            }
        ]
    }


def test_matrix_profile_resolves_alias_and_applies_deterministic_factor(
    engine: PaymentFactorEngine, mbc_claim: dict[str, object], matrix_assets: dict[str, object]
) -> None:
    result = engine.plan("Mercedes-Benz", "AUTO", mbc_claim, matrix_assets)

    assert result.evaluation_path == "deterministic:tabular_acceptance_matrix"
    assert result.factor == 0.2
    assert result.accepted_quantity == 2.0
    assert result.source_reference == "agreement-1.pdf"


def test_signed_matrix_wins_over_a_valid_learned_rule(
    engine: PaymentFactorEngine, mbc_claim: dict[str, object], matrix_assets: dict[str, object]
) -> None:
    profile = engine.registry.resolve("MBC", "AUTO")
    assert profile is not None
    cache = InMemoryLearnedRuleCache()
    cache.put(
        engine.group_key_for(profile, mbc_claim),
        LearnedRule(
            profile_id=profile.profile_id,
            factor=0.99,
            source_reference="old-grouped-decision",
            source_fingerprint="old-fingerprint",
            expires_on=TODAY + timedelta(days=1),
        ),
    )

    result = engine.plan("MBC", "AUTO", mbc_claim, matrix_assets, cache)

    assert result.evaluation_path == "deterministic:tabular_acceptance_matrix"
    assert result.factor == 0.2


def test_non_matching_claim_uses_valid_learned_rule_after_matrix_fallthrough(
    engine: PaymentFactorEngine, mbc_claim: dict[str, object], matrix_assets: dict[str, object]
) -> None:
    claim = {
        **mbc_claim,
        "part_family_number": "AA999",
        "part_number": "A999",
        "claim_id": "claim-2",
    }
    profile = engine.registry.resolve("MBC", "AUTO")
    assert profile is not None
    cache = InMemoryLearnedRuleCache()
    cache.put(
        engine.group_key_for(profile, claim),
        LearnedRule(
            profile_id=profile.profile_id,
            factor=0.4,
            source_reference="grouped-main-contract-decision",
            source_fingerprint="main-contract-v1",
            expires_on=TODAY + timedelta(days=1),
        ),
    )

    result = engine.plan("MBC", "AUTO", claim, matrix_assets, cache)

    assert result.evaluation_path == "learned_rule"
    assert result.factor == 0.4


def test_expired_learned_rule_falls_to_grouped_contract_review(
    engine: PaymentFactorEngine, mbc_claim: dict[str, object], matrix_assets: dict[str, object]
) -> None:
    claim = {**mbc_claim, "part_family_number": "AA999", "part_number": "A999"}
    profile = engine.registry.resolve("MBC", "AUTO")
    assert profile is not None
    cache = InMemoryLearnedRuleCache()
    cache.put(
        engine.group_key_for(profile, claim),
        LearnedRule(
            profile_id=profile.profile_id,
            factor=0.4,
            source_reference="expired-decision",
            source_fingerprint="main-contract-v1",
            expires_on=TODAY - timedelta(days=1),
        ),
    )

    result = engine.plan("MBC", "AUTO", claim, matrix_assets, cache)

    assert result.evaluation_path == "grouped_contract_review"
    assert result.group_key is not None


def test_missing_grouping_field_requires_review_instead_of_llm(
    engine: PaymentFactorEngine, mbc_claim: dict[str, object], matrix_assets: dict[str, object]
) -> None:
    claim = {**mbc_claim, "part_family_number": "AA999", "part_number": "A999"}
    claim.pop("repair_date")

    result = engine.plan("MBC", "AUTO", claim, matrix_assets)

    assert result.evaluation_path == "requires_review"
    assert "repair_date" in result.reason


def test_unknown_oem_does_not_fall_back_to_another_profile(
    engine: PaymentFactorEngine, mbc_claim: dict[str, object], matrix_assets: dict[str, object]
) -> None:
    result = engine.plan("UNKNOWN", "AUTO", mbc_claim, matrix_assets)

    assert result.evaluation_path == "requires_review"
    assert result.factor is None
