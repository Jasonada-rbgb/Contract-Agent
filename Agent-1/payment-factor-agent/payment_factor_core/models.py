"""Stable, source-neutral contracts for payment-factor routing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class ProfileConfigurationError(ValueError):
    """Raised when a payment-factor profile is not safe to route."""


@dataclass(frozen=True)
class ContractProfile:
    """A versioned configuration describing one contract evaluation route."""

    profile_id: str
    oem_aliases: tuple[str, ...]
    contract_ids: tuple[str, ...]
    deterministic_plugins: tuple[str, ...]
    grouping_fields: tuple[str, ...]
    asset_refs: Mapping[str, str]
    plugin_settings: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ContractProfile:
        """Build a validated profile from a declarative JSON object."""
        return cls(
            profile_id=_required_text(raw, "profile_id"),
            oem_aliases=_text_tuple(raw, "oem_aliases", uppercase=True),
            contract_ids=_text_tuple(raw, "contract_ids", uppercase=True),
            deterministic_plugins=_text_tuple(raw, "deterministic_plugins", allow_empty=True),
            grouping_fields=_text_tuple(raw, "grouping_fields"),
            asset_refs=_mapping_of_text(raw, "asset_refs"),
            plugin_settings=_mapping_of_mappings(raw, "plugin_settings"),
        )


@dataclass(frozen=True)
class PluginOutcome:
    """A deterministic evaluator outcome before cache or LLM routing."""

    status: str
    factor: float | None
    accepted_quantity: float | None
    reference_cost_only: float | None
    source_reference: str | None
    reason: str


@dataclass(frozen=True)
class EvaluationPlan:
    """An auditable next action for one claim, without invoking an LLM."""

    evaluation_path: str
    profile_id: str | None
    factor: float | None
    accepted_quantity: float | None
    reference_cost_only: float | None
    source_reference: str | None
    reason: str
    group_key: str | None = None
    source_fingerprint: str | None = None


def _required_text(raw: Mapping[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ProfileConfigurationError(f"Profile field {field!r} must be a non-empty string.")
    return value.strip()


def _text_tuple(
    raw: Mapping[str, Any], field: str, *, allow_empty: bool = False, uppercase: bool = False
) -> tuple[str, ...]:
    value = raw.get(field, []) if allow_empty else raw.get(field)
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ProfileConfigurationError(f"Profile field {field!r} must be a list of strings.")
    items = tuple(
        str(item).strip().upper() if uppercase else str(item).strip()
        for item in value
        if str(item).strip()
    )
    if not items and not allow_empty:
        raise ProfileConfigurationError(f"Profile field {field!r} cannot be empty.")
    return items


def _mapping_of_text(raw: Mapping[str, Any], field: str) -> Mapping[str, str]:
    value = raw.get(field, {})
    if not isinstance(value, Mapping):
        raise ProfileConfigurationError(f"Profile field {field!r} must be an object.")
    return {str(key): str(item) for key, item in value.items()}


def _mapping_of_mappings(
    raw: Mapping[str, Any], field: str
) -> Mapping[str, Mapping[str, Any]]:
    value = raw.get(field, {})
    if not isinstance(value, Mapping) or any(not isinstance(item, Mapping) for item in value.values()):
        raise ProfileConfigurationError(f"Profile field {field!r} must be an object of objects.")
    return {str(key): dict(item) for key, item in value.items()}
