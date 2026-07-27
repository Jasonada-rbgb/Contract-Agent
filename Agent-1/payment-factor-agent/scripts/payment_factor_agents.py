"""Callable payment-factor subagents.

Three factor agents implementing the README output schema. Each takes a
contract eligibility decision + normalized claim data and returns a payable
percentage with provenance. Rates come from structured sources (Kostenstand,
STAR/DMYA, PFACC) plus governance + overrides — never hardcoded content.

    Fixed Acceptance Agent          -> BMW Kostenstand fixed rates
    Technical Factor Agent          -> JLR STAR CAT1/(CAT1+CAT2+CAT3)
    Extrapolated Technical Factor   -> JLR DMYA/PFACC applied to wider population

Output schema (per README):
    factor_type, rate, rate_source, rate_basis, source_reference, confidence, warnings
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from denominator_governance import govern_technical_factor


@dataclass
class FactorResult:
    factor_type: str
    rate: Optional[float]
    rate_source: str
    rate_basis: str
    source_reference: str
    confidence: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_type": self.factor_type,
            "rate": self.rate,
            "rate_source": self.rate_source,
            "rate_basis": self.rate_basis,
            "source_reference": self.source_reference,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


class FixedAcceptanceAgent:
    """BMW: fixed agreed percentages by product group, warranty type, year, market."""

    def __init__(self, rate_table: dict[tuple, float]):
        # key: (warenkorb_key, warranty_type) -> rate
        self._rates = rate_table

    def factor(self, *, warenkorb_key: str, warranty_type: str, source_ref: str) -> FactorResult:
        rate = self._rates.get((warenkorb_key, warranty_type))
        if rate is None:
            return FactorResult(
                "fixed_acceptance", None, "Kostenstand", warranty_type, source_ref,
                "expert_review", [f"No Kostenstand rate match for {warenkorb_key}/{warranty_type}"],
            )
        return FactorResult(
            "fixed_acceptance", rate, "Kostenstand", warranty_type, source_ref, "high", [],
        )


class TechnicalFactorAgent:
    """JLR: technical acceptance factor from STAR outcomes, with denominator governance."""

    def factor(self, *, cat1: int, cat2: int, cat3: int, product_family: str, model_year: str,
               source_ref: str, fallback_rate: Optional[float] = None) -> FactorResult:
        denom = cat1 + cat2 + cat3
        computed = (cat1 / denom) if denom else None
        gov = govern_technical_factor(
            computed_rate=computed, denominator=denom,
            product_family=product_family, model_year=model_year, fallback_rate=fallback_rate,
        )
        return FactorResult(
            "technical_factor", gov.rate, gov.rate_source, "CAT1/(CAT1+CAT2+CAT3)",
            source_ref, gov.confidence, gov.warnings,
        )


class ExtrapolatedTechnicalFactorAgent:
    """JLR: apply a sampled/technical factor to a wider population, honouring overrides."""

    def __init__(self, overrides: dict[tuple, dict]):
        # key: (product_family, model_year) -> override dict
        self._overrides = overrides

    def factor(self, *, cat1: int, cat2: int, cat3: int, product_family: str, model_year: str,
               source_ref: str, fallback_rate: Optional[float] = None) -> FactorResult:
        denom = cat1 + cat2 + cat3
        computed = (cat1 / denom) if denom else None
        ov = self._overrides.get((product_family.upper(), str(model_year)))
        gov = govern_technical_factor(
            computed_rate=computed, denominator=denom,
            product_family=product_family, model_year=model_year, fallback_rate=fallback_rate,
            override_rate=(ov.get("applied_rate") if ov else None),
            override_id=(ov.get("override_id") if ov else None),
        )
        return FactorResult(
            "extrapolated_technical_factor", gov.rate, gov.rate_source,
            "DMYA CAT1/(CAT1+CAT2+CAT3) extrapolated", source_ref, gov.confidence, gov.warnings,
        )


def load_overrides(path: Path) -> dict[tuple, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple, dict] = {}
    for ov in data.get("overrides", []):
        if ov.get("applied_rate") is not None:
            out[(str(ov["product_family"]).upper(), str(ov["model_year"]))] = ov
    return out


if __name__ == "__main__":
    ov_path = Path(__file__).resolve().parent.parent / "rules" / "overrides.json"
    overrides = load_overrides(ov_path)

    tech = TechnicalFactorAgent()
    ext = ExtrapolatedTechnicalFactorAgent(overrides)

    print("GS ECU 2023 (denom=10, apply):")
    print(json.dumps(tech.factor(cat1=4, cat2=3, cat3=3, product_family="GS ECU", model_year="2023",
                                  source_ref="STAR:answer_date").to_dict(), indent=2))
    print("\nDMTL 2023 (override):")
    print(json.dumps(ext.factor(cat1=4, cat2=0, cat3=0, product_family="DMTL", model_year="2023",
                                 source_ref="STAR:BBTRVY+BBVDHN").to_dict(), indent=2))
    print("\nWiper Arm 2023 (thin denom=7, fallback):")
    print(json.dumps(tech.factor(cat1=3, cat2=4, cat3=0, product_family="WIPER ARM", model_year="2023",
                                 source_ref="STAR:answer_date", fallback_rate=0.25).to_dict(), indent=2))
