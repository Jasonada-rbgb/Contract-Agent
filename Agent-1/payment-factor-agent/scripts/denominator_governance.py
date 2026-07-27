"""Denominator-floor governance for technical/extrapolated payment factors.

Governance rule (agreed 2026-07-20):
  denominator < 10  -> thin-rate: route to expert_review OR workbook-locked
                       fallback OR explicit business override (never apply silently)
  denominator >= 10 -> acceptable unless other red flags exist

This module is the single decision point for whether a STAR-derived technical
factor may be applied at face value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

MIN_DENOMINATOR_FLOOR = 10


@dataclass
class FactorGovernanceResult:
    rate: Optional[float]
    rate_source: str
    confidence: str
    action: str  # "apply" | "fallback" | "override" | "expert_review"
    warnings: list[str] = field(default_factory=list)


def govern_technical_factor(
    *,
    computed_rate: Optional[float],
    denominator: Optional[int],
    product_family: str,
    model_year: str,
    fallback_rate: Optional[float] = None,
    override_rate: Optional[float] = None,
    override_id: Optional[str] = None,
) -> FactorGovernanceResult:
    """Decide whether a computed technical factor may be applied.

    Precedence: explicit override > denominator floor > apply computed.
    """
    warnings: list[str] = []

    # 1. Explicit business/expert override always wins, but is flagged.
    if override_rate is not None:
        warnings.append(
            f"Business override {override_rate} applied for {product_family} MY{model_year}"
            + (f" (override_id={override_id})" if override_id else "")
        )
        return FactorGovernanceResult(
            rate=override_rate, rate_source="manual_override",
            confidence="expert_review", action="override", warnings=warnings,
        )

    # 2. Missing rate or denominator -> cannot apply.
    if computed_rate is None or denominator is None:
        warnings.append("Missing computed rate or denominator; routed to expert review.")
        return FactorGovernanceResult(
            rate=fallback_rate, rate_source="workbook_locked_fallback" if fallback_rate is not None else "none",
            confidence="low", action="fallback" if fallback_rate is not None else "expert_review",
            warnings=warnings,
        )

    # 3. Thin denominator -> do not apply silently.
    if denominator < MIN_DENOMINATOR_FLOOR:
        warnings.append(
            f"Thin denominator {denominator} < {MIN_DENOMINATOR_FLOOR} for {product_family} MY{model_year}."
        )
        if fallback_rate is not None:
            warnings.append("Applied workbook-locked fallback rate instead of thin STAR rate.")
            return FactorGovernanceResult(
                rate=fallback_rate, rate_source="workbook_locked_fallback",
                confidence="low", action="fallback", warnings=warnings,
            )
        return FactorGovernanceResult(
            rate=None, rate_source="none", confidence="expert_review",
            action="expert_review", warnings=warnings,
        )

    # 4. Acceptable.
    return FactorGovernanceResult(
        rate=computed_rate, rate_source="STAR",
        confidence="high", action="apply", warnings=warnings,
    )


if __name__ == "__main__":
    # smoke test with the DMTL MY2023 case
    r = govern_technical_factor(
        computed_rate=1.0, denominator=4, product_family="DMTL", model_year="2023",
        fallback_rate=None, override_rate=0.35, override_id="OVR-JLR-DMTL-MY2023",
    )
    print(r)
    r2 = govern_technical_factor(
        computed_rate=0.4, denominator=10, product_family="GS ECU", model_year="2023",
    )
    print(r2)
    r3 = govern_technical_factor(
        computed_rate=0.4286, denominator=7, product_family="WIPER ARM", model_year="2023",
        fallback_rate=0.25,
    )
    print(r3)
