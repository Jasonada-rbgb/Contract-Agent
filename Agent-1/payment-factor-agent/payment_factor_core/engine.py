"""Profile-driven routing that keeps deterministic rules ahead of model work."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .cache import InMemoryLearnedRuleCache
from .matrix_plugin import TabularAcceptanceMatrixPlugin
from .models import ContractProfile, EvaluationPlan, PluginOutcome
from .profiles import ProfileRegistry


class PaymentFactorEngine:
    """Resolve profiles, evaluate approved rules, then route safe LLM groups."""

    def __init__(self, registry: ProfileRegistry) -> None:
        self.registry = registry
        self._plugins = {TabularAcceptanceMatrixPlugin.name: TabularAcceptanceMatrixPlugin()}

    def plan(
        self,
        oem: str,
        contract_id: str,
        claim: Mapping[str, Any],
        assets: Mapping[str, Any],
        cache: InMemoryLearnedRuleCache | None = None,
    ) -> EvaluationPlan:
        """Return the safe next action without making an LLM call."""
        profile = self.registry.resolve(oem, contract_id)
        if profile is None:
            return _review(None, "No approved payment-factor profile matches this OEM and contract.")
        outcome = self._evaluate_deterministic(profile, claim, assets)
        if outcome is not None and outcome.status != "fall_through":
            return _from_outcome(profile, outcome)
        missing = _missing_fields(profile, claim)
        if missing:
            return _review(profile.profile_id, f"Missing grouping fields: {', '.join(missing)}.")
        group_key = self.group_key_for(profile, claim)
        today = datetime.now(timezone.utc).date()
        learned = cache.get(group_key, profile.profile_id, today) if cache else None
        if learned is not None:
            return EvaluationPlan("learned_rule", profile.profile_id, learned.factor, None, None, learned.source_reference, "Non-expired learned rule matched after deterministic fall-through.", group_key, learned.source_fingerprint)
        return EvaluationPlan("grouped_contract_review", profile.profile_id, None, None, None, None, "No deterministic or learned rule matched; evaluate one representative claim for this safe group.", group_key)

    def group_key_for(self, profile: ContractProfile, claim: Mapping[str, Any]) -> str:
        """Hash only the configured decision-changing fields for a profile."""
        payload = {"profile_id": profile.profile_id, "fields": {field: claim.get(field) for field in profile.grouping_fields}}
        encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _evaluate_deterministic(
        self, profile: ContractProfile, claim: Mapping[str, Any], assets: Mapping[str, Any]
    ) -> PluginOutcome | None:
        for plugin_name in profile.deterministic_plugins:
            plugin = self._plugins.get(plugin_name)
            if plugin is None:
                return PluginOutcome("requires_review", None, None, None, None, "Configured deterministic evaluator is not installed.")
            outcome = plugin.evaluate(profile, claim, assets)
            if outcome.status != "fall_through":
                return outcome
        return None


def _missing_fields(profile: ContractProfile, claim: Mapping[str, Any]) -> list[str]:
    return [field for field in profile.grouping_fields if claim.get(field) in (None, "")]


def _review(profile_id: str | None, reason: str) -> EvaluationPlan:
    return EvaluationPlan("requires_review", profile_id, None, None, None, None, reason)


def _from_outcome(profile: ContractProfile, outcome: PluginOutcome) -> EvaluationPlan:
    path = "deterministic:tabular_acceptance_matrix" if outcome.status == "settled" else "requires_review"
    return EvaluationPlan(path, profile.profile_id, outcome.factor, outcome.accepted_quantity, outcome.reference_cost_only, outcome.source_reference, outcome.reason)
