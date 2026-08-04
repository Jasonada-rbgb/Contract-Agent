"""Loading and resolving declarative payment-factor contract profiles."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .models import ContractProfile, ProfileConfigurationError


class ProfileRegistry:
    """Resolve an OEM/contract pair without OEM conditions in the core engine."""

    def __init__(self, profiles: Iterable[ContractProfile]) -> None:
        self._profiles = tuple(profiles)
        if not self._profiles:
            raise ProfileConfigurationError("At least one contract profile is required.")
        self._assert_unique_routes()

    @classmethod
    def from_directory(cls, directory: Path) -> ProfileRegistry:
        """Load all JSON profile files from a trusted package directory."""
        try:
            paths = sorted(directory.glob("*.json"))
            profiles = [ContractProfile.from_mapping(_read_json(path)) for path in paths]
        except OSError as exc:
            raise ProfileConfigurationError("Could not read payment-factor profiles.") from exc
        return cls(profiles)

    def resolve(self, oem: str, contract_id: str) -> ContractProfile | None:
        """Return the uniquely matching profile, or None for an unsupported route."""
        normalized_oem = oem.strip().upper()
        normalized_contract = contract_id.strip().upper()
        for profile in self._profiles:
            if normalized_oem in profile.oem_aliases and normalized_contract in profile.contract_ids:
                return profile
        return None

    def _assert_unique_routes(self) -> None:
        seen: set[tuple[str, str]] = set()
        for profile in self._profiles:
            for oem in profile.oem_aliases:
                for contract_id in profile.contract_ids:
                    route = (oem, contract_id)
                    if route in seen:
                        raise ProfileConfigurationError("Profiles contain a duplicate OEM/contract route.")
                    seen.add(route)


def _read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileConfigurationError("A payment-factor profile is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ProfileConfigurationError("A payment-factor profile must be a JSON object.")
    return data
