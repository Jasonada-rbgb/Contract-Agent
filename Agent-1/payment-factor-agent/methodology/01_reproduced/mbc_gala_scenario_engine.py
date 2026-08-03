"""Reproduce MBC GALA compile-once settlement from a supplied signed matrix.

The matrix is intentionally an input, not a package artifact: it is compiled
from approved GALA agreements and retained in the Contract Agent / UC storage.
This module contains no agreement rate, raw contract text, claim data, or cost
of record.  It is a portable verification implementation of the published
matrix schema and routing semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class GalaSettlement:
    """A deterministic GALA routing result with non-authoritative cost metadata."""

    status: str
    match_basis: str
    acceptance_rate_percent: float | None
    accepted_quantity: float | None
    reference_cost_only: float | None
    cost_is_reference_only: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Return the portable result contract used by scenario tests."""
        return asdict(self)


def apply_signed_gala_matrix(
    claim: Mapping[str, Any], matrix: Iterable[Mapping[str, Any]]
) -> GalaSettlement:
    """Apply a supplied matrix rule or route the claim to main-contract review."""
    rule, basis = _match_rule(claim, matrix)
    if rule is None:
        return _fall_through("no signed GALA agreement match")
    rate = _number(rule.get("acceptance_rate_percent"))
    if rate is None:
        return GalaSettlement(
            "requires_review", basis, None, None, None, True,
            "GALA rule has an undetermined Quote; analyst review is required.",
        )
    if not 0 <= rate <= 100:
        return GalaSettlement(
            "requires_review", basis, rate, None, None, True,
            "GALA Quote is outside the accepted 0-100 percent range.",
        )
    temporal_ok, temporal_reason = _temporal_gate(claim, rule)
    if not temporal_ok:
        return _fall_through(f"GALA temporal gate blocked: {temporal_reason}", basis)
    replaced_quantity = _number(claim.get("replaced_quantity_apportioned")) or 1.0
    accepted_quantity = round(replaced_quantity * rate / 100.0, 4)
    reference_cost = round(_reference_unit_cost(claim) * accepted_quantity, 2)
    return GalaSettlement(
        "settled", basis, rate, accepted_quantity, reference_cost, True,
        f"Signed GALA Quote applied after {temporal_reason}.",
    )


def _match_rule(
    claim: Mapping[str, Any], matrix: Iterable[Mapping[str, Any]]
) -> tuple[Mapping[str, Any] | None, str]:
    family = _text(claim.get("part_family_number"))
    rules = list(matrix)
    if family:
        for rule in rules:
            if family in {_text(value) for value in rule.get("part_family_numbers", [])}:
                return rule, "part_family_number"
    supplier = _text(claim.get("supplier_number"))
    part_number = _text(claim.get("part_number"))
    for rule in rules:
        suppliers = {_text(value) for value in rule.get("supplier_numbers", [])}
        parts = {_text(value) for value in rule.get("part_numbers", [])}
        if supplier and part_number and supplier in suppliers and part_number in parts:
            return rule, "supplier_part_number"
    return None, "no_match"


def _temporal_gate(claim: Mapping[str, Any], rule: Mapping[str, Any]) -> tuple[bool, str]:
    anfallsjahr = _number(rule.get("anfallsjahr_from"))
    if anfallsjahr is not None:
        receipt_year = _number(claim.get("receipt_date_year"))
        if receipt_year is None:
            return False, "receipt_date_year is required"
        return receipt_year >= anfallsjahr, "inclusive Anfallsjahr gate"
    production_date = _date_value(claim.get("vehicle_origin_production_date"))
    start = _date_value(rule.get("production_start"))
    end = _date_value(rule.get("production_end"))
    if not start and not end:
        return True, "no agreement temporal gate"
    if production_date is None:
        return False, "vehicle_origin_production_date is required"
    return (not start or production_date >= start) and (not end or production_date <= end), "production window"


def _fall_through(reason: str, basis: str = "no_match") -> GalaSettlement:
    return GalaSettlement("fall_through", basis, None, None, None, True, reason)


def _reference_unit_cost(claim: Mapping[str, Any]) -> float:
    fields = ("material_price_invoicing", "labor_cost_average", "incidental_costs_aqua", "mobility_costs_aqua")
    return sum(_number(claim.get(field)) or 0.0 for field in fields)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip().upper()


def _date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        pass
    try:
        day, month, year = (int(part) for part in str(value).split("."))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None
