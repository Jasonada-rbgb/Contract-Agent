"""Configurable evaluator for approved tabular agreement matrices."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from .models import ContractProfile, PluginOutcome


class TabularAcceptanceMatrixPlugin:
    """Apply a versioned agreement matrix without embedding OEM contract content."""

    name = "tabular_acceptance_matrix"

    def evaluate(
        self,
        profile: ContractProfile,
        claim: Mapping[str, Any],
        assets: Mapping[str, Any],
    ) -> PluginOutcome:
        """Return a deterministic result, a review, or a main-contract fall-through."""
        settings = profile.plugin_settings.get(self.name, {})
        matrix = assets.get(str(settings.get("matrix_asset", "")))
        if not _is_rule_iterable(matrix):
            return PluginOutcome("requires_review", None, None, None, None, "Signed agreement matrix is unavailable.")
        rule, match_basis = _match_rule(claim, matrix, settings)
        if rule is None:
            return PluginOutcome("fall_through", None, None, None, None, "No signed agreement match.")
        rate = _number(rule.get(str(settings.get("rate_field", "acceptance_rate_percent"))))
        if rate is None or not 0 <= rate <= 100:
            return PluginOutcome("requires_review", None, None, None, _reference(rule, settings), "Agreement quote is missing or invalid.")
        temporal = _temporal_outcome(claim, rule, settings)
        if temporal is not None:
            return temporal
        return _settled_outcome(claim, rule, settings, rate, match_basis)


def _is_rule_iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping))


def _match_rule(
    claim: Mapping[str, Any], matrix: Iterable[Mapping[str, Any]], settings: Mapping[str, Any]
) -> tuple[Mapping[str, Any] | None, str]:
    steps = settings.get("match_steps", [])
    if not isinstance(steps, list):
        return None, "invalid_configuration"
    rules = [rule for rule in matrix if isinstance(rule, Mapping)]
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        for rule in rules:
            if _rule_matches(claim, rule, step):
                return rule, str(step.get("name", "matrix"))
    return None, "no_match"


def _rule_matches(
    claim: Mapping[str, Any], rule: Mapping[str, Any], step: Mapping[str, Any]
) -> bool:
    claim_fields = step.get("claim_fields", [])
    rule_fields = step.get("rule_fields", [])
    if not isinstance(claim_fields, list) or not isinstance(rule_fields, list):
        return False
    comparisons = [_matches_field(claim.get(str(left)), rule.get(str(right))) for left, right in zip(claim_fields, rule_fields)]
    if len(comparisons) != len(claim_fields):
        return False
    return any(comparisons) if step.get("mode") == "any" else all(comparisons)


def _matches_field(claim_value: Any, rule_value: Any) -> bool:
    needle = _text(claim_value)
    values = rule_value if isinstance(rule_value, list) else [rule_value]
    return bool(needle) and needle in {_text(value) for value in values}


def _temporal_outcome(
    claim: Mapping[str, Any], rule: Mapping[str, Any], settings: Mapping[str, Any]
) -> PluginOutcome | None:
    gate = settings.get("temporal_gate", {})
    if not isinstance(gate, Mapping):
        return PluginOutcome("requires_review", None, None, None, None, "Agreement temporal-gate configuration is invalid.")
    year = _number(rule.get(str(gate.get("minimum_receipt_year_rule_field", ""))))
    if year is not None:
        receipt_year = _number(claim.get(str(gate.get("receipt_year_claim_field", ""))))
        if receipt_year is None:
            return PluginOutcome("requires_review", None, None, None, None, "Receipt year is required for the agreement gate.")
        if receipt_year < year:
            return PluginOutcome("fall_through", None, None, None, None, "Agreement receipt-year gate blocked.")
        return None
    return _production_gate(claim, rule, gate)


def _production_gate(
    claim: Mapping[str, Any], rule: Mapping[str, Any], gate: Mapping[str, Any]
) -> PluginOutcome | None:
    start = _date_value(rule.get(str(gate.get("production_start_rule_field", ""))))
    end = _date_value(rule.get(str(gate.get("production_end_rule_field", ""))))
    if start is None and end is None:
        return None
    production = _date_value(claim.get(str(gate.get("production_date_claim_field", ""))))
    if production is None:
        return PluginOutcome("requires_review", None, None, None, None, "Production date is required for the agreement gate.")
    if (start and production < start) or (end and production > end):
        return PluginOutcome("fall_through", None, None, None, None, "Agreement production window blocked.")
    return None


def _settled_outcome(
    claim: Mapping[str, Any], rule: Mapping[str, Any], settings: Mapping[str, Any], rate: float, match_basis: str
) -> PluginOutcome:
    quantity_settings = settings.get("quantity", {})
    quantity_field = str(quantity_settings.get("claim_field", "")) if isinstance(quantity_settings, Mapping) else ""
    default_quantity = float(quantity_settings.get("default", 1.0)) if isinstance(quantity_settings, Mapping) else 1.0
    quantity = _number(claim.get(quantity_field)) or default_quantity
    factor = rate / 100.0
    accepted_quantity = round(quantity * factor, 4)
    reference_cost = round(_reference_cost(claim, settings) * accepted_quantity, 2)
    reference = _reference(rule, settings)
    return PluginOutcome("settled", factor, accepted_quantity, reference_cost, reference, f"Signed agreement matrix matched by {match_basis}.")


def _reference_cost(claim: Mapping[str, Any], settings: Mapping[str, Any]) -> float:
    cost_fields = settings.get("reference_cost_fields", [])
    if not isinstance(cost_fields, list):
        return 0.0
    return sum(_number(claim.get(str(field))) or 0.0 for field in cost_fields)


def _reference(rule: Mapping[str, Any], settings: Mapping[str, Any]) -> str | None:
    field = str(settings.get("source_reference_field", "source_filename"))
    value = rule.get(field) or rule.get("rule_id")
    return str(value) if value else None


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
        try:
            day, month, year = (int(part) for part in str(value).split("."))
            return date(year, month, day)
        except (TypeError, ValueError):
            return None
