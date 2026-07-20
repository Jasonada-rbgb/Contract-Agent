from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = ROOT / "output" / "bmw_edc_claims_eval_verified_20260701"
FINAL_DIR = AUDIT_ROOT / "final_contract_audit"
OUT_DIR = AUDIT_ROOT / "databricks_dashboard"


def _clean_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .fillna("")
        .str.replace("\r", " ", regex=False)
        .str.replace("\n", " ", regex=False)
        .str.replace("\t", " ", regex=False)
        .str.slice(0, 500)
    )


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _first_numeric(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    values = pd.Series(pd.NA, index=df.index, dtype="Float64")
    for column in columns:
        if column in df.columns:
            values = values.fillna(_num(df[column]))
    return values.astype("float64")


def _load_bmw_cost_components(row_offsets: dict[str, int]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in AUDIT_ROOT.glob("*/normalized_claims.csv"):
        source_folder = path.parent.name
        df = pd.read_csv(path, low_memory=False)
        component = pd.DataFrame(
            {
                "source_folder": source_folder,
                "row_id": pd.Series(range(row_offsets.get(source_folder, 0), row_offsets.get(source_folder, 0) + len(df)), dtype="int64"),
                "parts_cost_eur": _first_numeric(df, ["parts_cost", "Teilekosten", "Teile-Nettokosten", "Teilenetto-kosten (EUR)"]),
                "labour_cost_eur": _first_numeric(
                    df,
                    ["labour_cost", "Lohnkosten final", "Lohnkosten", "Lohnkosten (EUR)"],
                ),
                "handling_cost_eur": _first_numeric(
                    df,
                    ["Handling Charge final", "Handling Charge.1", "Handling Charge", "Handling Charge (EUR)"],
                ),
                "landing_cost_eur": _first_numeric(
                    df,
                    ["Bezugskosten-Zuschlag", "Bezugskosten", "Zuschlag Bezugs-kosten", "bezugskosten_zuschlag"],
                ),
                "logistics_cost_eur": pd.Series(0.0, index=df.index),
                "sundry_cost_eur": _first_numeric(
                    df,
                    ["Sonstige Kosten final", "Sonstige Kosten", "Sontige Kosten.1", "Sontige Kosten", "Sonstige Kosten (EUR)"],
                ),
                "associated_cost_eur": _first_numeric(
                    df,
                    ["Mitausbaukosten final", "Mitausbaukosten", "Mitausbau-kosten gesamt (EUR)"],
                ),
                "vat_cost_eur": pd.Series(0.0, index=df.index),
            }
        )
        frames.append(component)
    if not frames:
        raise FileNotFoundError(f"No normalized_claims.csv files found under {AUDIT_ROOT}")
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    row_path = FINAL_DIR / "final_contract_audit_row_level.csv"
    candidates_path = FINAL_DIR / "2025_missing_exclusion_pattern_candidates.csv"

    cols = [
        "bmw_source_year",
        "bmw_workbook_family",
        "source_folder",
        "claim_number",
        "document_number",
        "vin",
        "country",
        "repair_date",
        "warranty_start_date",
        "warranty_basis_months",
        "mileage",
        "part_number",
        "part_description",
        "failure_code",
        "total_cost",
        "Warenkorb",
        "claim_rate_key",
        "manual_status",
        "manual_warranty_type",
        "contract_warranty_type",
        "ai_decision",
        "manual_rate",
        "contract_rate",
        "manual_payable_final",
        "contract_payable_final",
        "delta_contract_minus_manual_final",
        "audit_bucket",
        "reason_kind",
        "reason_categories",
        "row_id",
    ]
    df = pd.read_csv(row_path, usecols=cols, low_memory=False)
    row_offsets = df.groupby("source_folder")["row_id"].min().astype(int).to_dict()
    cost_components = _load_bmw_cost_components(row_offsets)
    df = df.merge(cost_components, on=["source_folder", "row_id"], how="left", validate="one_to_one")
    manual = _num(df["manual_payable_final"])
    contract = _num(df["contract_payable_final"])

    adjusted_contract = contract.copy()
    pattern_ids = set(pd.read_csv(candidates_path, usecols=["row_id"])["row_id"].dropna().astype(int))
    row_ids = _num(df["row_id"]).astype("Int64")
    pattern_mask = row_ids.isin(pattern_ids)
    adjusted_contract.loc[pattern_mask] = manual.loc[pattern_mask]

    prompt2_mask = (
        df["audit_bucket"].eq("challengeable_status_only_delta")
        & df["manual_warranty_type"].eq("standard_gw")
        & df["contract_warranty_type"].eq("not_payable")
        & df["claim_rate_key"].astype("string").str.startswith("1236 steuergeraet eme", na=False)
    )
    adjusted_contract.loc[prompt2_mask] = manual.loc[prompt2_mask] * 0.5

    adjusted_delta = adjusted_contract - manual

    confidence = pd.Series("standard", index=df.index, dtype="string")
    confidence.loc[pattern_mask] = "matched_2025_historical_manual_pattern"
    confidence.loc[df["audit_bucket"].eq("expert_review_contract_exception")] = "expert_review_legal"

    emission_prefixes = ("1178 ", "1362 ", "1351 ", "1353 ", "1364 ")
    key = df["claim_rate_key"].astype("string").str.lower().fillna("")
    meta6_mask = (
        df["audit_bucket"].eq("manual_reason_delta_needs_expert_mapping")
        & df["reason_kind"].eq("visible_manual_deadline_reason")
        & df["manual_warranty_type"].eq("standard_gw")
        & df["contract_warranty_type"].eq("extended_gw")
    )
    meta6_emission_mask = meta6_mask & key.str.startswith(emission_prefixes)
    confidence.loc[meta6_emission_mask] = "bmw_expert_legal_extension_review"

    high_confidence_mask = (
        (
            df["audit_bucket"].eq("challengeable_status_only_delta")
            & df["manual_warranty_type"].eq("standard_gw")
            & df["contract_warranty_type"].eq("extended_gw")
            & ~pattern_mask
        )
        | (meta6_mask & ~meta6_emission_mask)
        | prompt2_mask
    )
    confidence.loc[high_confidence_mask] = "high_confidence_half_rate"

    oem_claims = _num(df["total_cost"])
    out = pd.DataFrame(
        {
            "oem": "BMW",
            "brand": "BMW",
            "source_year": _num(df["bmw_source_year"]).astype("Int64"),
            "source_family": _clean_text(df["bmw_workbook_family"]),
            "source_folder": _clean_text(df["source_folder"]),
            "claim_number": _clean_text(df["claim_number"]),
            "document_number": _clean_text(df["document_number"]),
            "vin": _clean_text(df["vin"]),
            "country": _clean_text(df["country"]),
            "repair_date": pd.to_datetime(df["repair_date"], errors="coerce").dt.date,
            "warranty_start_date": pd.to_datetime(df["warranty_start_date"], errors="coerce").dt.date,
            "warranty_basis_months": _num(df["warranty_basis_months"]),
            "mileage": _num(df["mileage"]),
            "part_number": _clean_text(df["part_number"]),
            "part_name": _clean_text(df["part_description"]),
            "part_description": _clean_text(df["part_description"]),
            "failure_code": _clean_text(df["failure_code"]),
            "sqw_name": _clean_text(df["claim_rate_key"].fillna(df["Warenkorb"])),
            "division_new": _clean_text(df["bmw_workbook_family"].fillna("BMW")),
            "oem_claims_eur": oem_claims,
            "manual_payable_eur": manual,
            "contract_payable_eur": adjusted_contract,
            "delta_contract_minus_manual_eur": adjusted_delta,
            "gap_vs_oem_claim_eur": oem_claims - adjusted_contract,
            "manual_rate": _num(df["manual_rate"]),
            "contract_rate": _num(df["contract_rate"]),
            "audit_bucket": _clean_text(df["audit_bucket"]),
            "reason_kind": _clean_text(df["reason_kind"]),
            "reason_categories": _clean_text(df["reason_categories"]),
            "reason_summary": _clean_text(df["reason_categories"]),
            "manual_status": _clean_text(df["manual_status"]),
            "manual_warranty_type": _clean_text(df["manual_warranty_type"]),
            "contract_warranty_type": _clean_text(df["contract_warranty_type"]),
            "agent_decision": _clean_text(df["ai_decision"]),
            "confidence_bucket": confidence,
            "parts_cost_eur": _num(df["parts_cost_eur"]),
            "labour_cost_eur": _num(df["labour_cost_eur"]),
            "handling_cost_eur": _num(df["handling_cost_eur"]),
            "landing_cost_eur": _num(df["landing_cost_eur"]),
            "logistics_cost_eur": _num(df["logistics_cost_eur"]),
            "sundry_cost_eur": _num(df["sundry_cost_eur"]),
            "associated_cost_eur": _num(df["associated_cost_eur"]),
            "vat_cost_eur": _num(df["vat_cost_eur"]),
        }
    )
    out["recovery_rate_percent"] = (
        out["contract_payable_eur"] / out["oem_claims_eur"].where(out["oem_claims_eur"].ne(0))
    ) * 100
    out["contract_lower_than_manual_eur"] = (
        out["manual_payable_eur"] - out["contract_payable_eur"]
    ).clip(lower=0)

    tsv_path = OUT_DIR / "bmw_claims_dashboard_normalized.tsv"
    out.to_csv(tsv_path, sep="\t", index=False, lineterminator="\n")
    component_columns = [
        "parts_cost_eur",
        "labour_cost_eur",
        "handling_cost_eur",
        "landing_cost_eur",
        "logistics_cost_eur",
        "sundry_cost_eur",
        "associated_cost_eur",
        "vat_cost_eur",
    ]
    summary = {
        "rows": int(len(out)),
        "oem_claims_eur": float(out["oem_claims_eur"].sum()),
        "manual_payable_eur": float(out["manual_payable_eur"].sum()),
        "contract_payable_eur": float(out["contract_payable_eur"].sum()),
        "delta_contract_minus_manual_eur": float(out["delta_contract_minus_manual_eur"].sum()),
        "high_confidence_lower_than_manual_eur": float(
            out.loc[out["confidence_bucket"].eq("high_confidence_half_rate"), "contract_lower_than_manual_eur"].sum()
        ),
        "component_costs_eur": {column: float(out[column].fillna(0).sum()) for column in component_columns},
    }
    (OUT_DIR / "bmw_claims_dashboard_normalized_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"tsv": str(tsv_path), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()


