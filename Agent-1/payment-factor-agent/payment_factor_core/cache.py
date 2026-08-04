"""Minimal cache contract; persistence belongs to the hosting application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LearnedRule:
    """A provenance-bound result eligible to bypass repeat model work."""

    profile_id: str
    factor: float
    source_reference: str
    source_fingerprint: str
    expires_on: date

    def is_valid_for(self, profile_id: str, today: date) -> bool:
        """Return true only for the same profile before its expiry date."""
        return self.profile_id == profile_id and self.expires_on >= today


class InMemoryLearnedRuleCache:
    """Test/local implementation of the host-owned learned-rule cache contract."""

    def __init__(self) -> None:
        self._records: dict[str, LearnedRule] = {}

    def get(self, group_key: str, profile_id: str, today: date) -> LearnedRule | None:
        """Return a non-expired record for the requested profile only."""
        record = self._records.get(group_key)
        return record if record and record.is_valid_for(profile_id, today) else None

    def put(self, group_key: str, record: LearnedRule) -> None:
        """Store a new immutable record under the caller's stable group key."""
        self._records[group_key] = record
