from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "output" / "bmw_edc_claims_eval_verified_20260701"
FINAL_DIR = AUDIT_DIR / "final_contract_audit"
BMW_ROW_LEVEL = FINAL_DIR / "final_contract_audit_row_level.csv"
SOURCE_DASHBOARD = AUDIT_DIR / "dashboard_source_lakeview.json"
OUT_DIR = AUDIT_DIR / "databricks_dashboard"
EXCHANGE_RATE_GBP_TO_EUR = 1.1776262295082


def _read_source_dashboard() -> dict[str, Any]:
    outer = json.loads(SOURCE_DASHBOARD.read_text(encoding="utf-8-sig"))
    return json.loads(outer["serialized_dashboard"])


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def build_bmw_normalized_csv() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
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
        "reason_summary",
    ]
    df = pd.read_csv(BMW_ROW_LEVEL, usecols=cols, low_memory=False)
    out = pd.DataFrame(
        {
            "oem": "BMW",
            "brand": "BMW",
            "source_year": _to_numeric(df["bmw_source_year"]).astype("Int64"),
            "source_family": df["bmw_workbook_family"].fillna("Unknown"),
            "source_folder": df["source_folder"],
            "claim_number": df["claim_number"].astype("string"),
            "document_number": df["document_number"].astype("string"),
            "vin": df["vin"].astype("string"),
            "country": df["country"].astype("string"),
            "repair_date": pd.to_datetime(df["repair_date"], errors="coerce").dt.date,
            "warranty_start_date": pd.to_datetime(df["warranty_start_date"], errors="coerce").dt.date,
            "warranty_basis_months": _to_numeric(df["warranty_basis_months"]),
            "mileage": _to_numeric(df["mileage"]),
            "part_number": df["part_number"].astype("string"),
            "part_name": df["part_description"].astype("string"),
            "part_description": df["part_description"].astype("string"),
            "failure_code": df["failure_code"].astype("string"),
            "sqw_name": df["claim_rate_key"].fillna(df["Warenkorb"]).astype("string"),
            "division_new": df["bmw_workbook_family"].fillna("BMW"),
            "oem_claims_eur": _to_numeric(df["total_cost"]),
            "manual_payable_eur": _to_numeric(df["manual_payable_final"]),
            "contract_payable_eur": _to_numeric(df["contract_payable_final"]),
            "delta_contract_minus_manual_eur": _to_numeric(df["delta_contract_minus_manual_final"]),
            "gap_vs_oem_claim_eur": _to_numeric(df["total_cost"]) - _to_numeric(df["contract_payable_final"]),
            "manual_rate": _to_numeric(df["manual_rate"]),
            "contract_rate": _to_numeric(df["contract_rate"]),
            "audit_bucket": df["audit_bucket"].astype("string"),
            "reason_kind": df["reason_kind"].astype("string"),
            "reason_categories": df["reason_categories"].astype("string"),
            "reason_summary": df["reason_summary"].astype("string"),
            "manual_status": df["manual_status"].astype("string"),
            "manual_warranty_type": df["manual_warranty_type"].astype("string"),
            "contract_warranty_type": df["contract_warranty_type"].astype("string"),
            "agent_decision": df["ai_decision"].astype("string"),
        }
    )
    out["recovery_rate_percent"] = (
        out["contract_payable_eur"] / out["oem_claims_eur"].where(out["oem_claims_eur"].ne(0))
    ) * 100
    out["contract_lower_than_manual_eur"] = (
        out["manual_payable_eur"] - out["contract_payable_eur"]
    ).clip(lower=0)
    out["confidence_bucket"] = "standard"
    mask_high_confidence = (
        out["audit_bucket"].isin(["challengeable_status_only_delta", "manual_reason_delta_needs_expert_mapping"])
        & out["contract_warranty_type"].eq("extended_gw")
        & out["manual_warranty_type"].eq("standard_gw")
        & ~out["reason_categories"].fillna("").str.contains("legal|gesetz|hoheit|emission", case=False, regex=True)
    )
    out.loc[mask_high_confidence, "confidence_bucket"] = "high_confidence_half_rate"
    out.loc[out["audit_bucket"].eq("expert_review_contract_exception"), "confidence_bucket"] = "expert_review"

    output_path = OUT_DIR / "bmw_claims_dashboard_normalized.csv"
    out.to_csv(output_path, index=False)
    return output_path


def build_sql() -> Path:
    sql = f"""
CREATE TABLE IF NOT EXISTS bci_rbs_prod.exploratory.bmw_claims_dashboard_normalized
USING CSV
OPTIONS (
  path '/Volumes/bci_rbs_prod/exploratory/einzelfallnachweis_bmw/raw/bmw_claims_dashboard_normalized.csv',
  header 'true',
  inferSchema 'true',
  mode 'PERMISSIVE'
);

CREATE OR REPLACE VIEW bci_rbs_prod.exploratory.claims_data_oem_unified AS
SELECT
  'JLR' AS oem,
  COALESCE(Brand, brand) AS brand,
  CAST(NULL AS INT) AS source_year,
  CAST(NULL AS STRING) AS source_family,
  CAST(NULL AS STRING) AS source_folder,
  CAST(claim_number AS STRING) AS claim_number,
  CAST(document_number AS STRING) AS document_number,
  vin,
  country,
  TO_DATE(repair_date) AS repair_date,
  TO_DATE(warranty_start_date) AS warranty_start_date,
  CAST(mis AS DOUBLE) AS warranty_basis_months,
  CAST(mileage AS DOUBLE) AS mileage,
  part_number,
  COALESCE(Part_Name, part_name, part_description) AS part_name,
  part_description,
  CAST(NULL AS STRING) AS failure_code,
  sqw_name,
  Division_New AS division_new,
  CAST(total_agreed AS DOUBLE) * {EXCHANGE_RATE_GBP_TO_EUR} AS oem_claims_eur,
  CAST(NULL AS DOUBLE) AS manual_payable_eur,
  CAST(Total_Export_Warranty_EUR AS DOUBLE) AS contract_payable_eur,
  CAST(NULL AS DOUBLE) AS delta_contract_minus_manual_eur,
  (CAST(total_agreed AS DOUBLE) * {EXCHANGE_RATE_GBP_TO_EUR}) - CAST(Total_Export_Warranty_EUR AS DOUBLE) AS gap_vs_oem_claim_eur,
  CAST(NULL AS DOUBLE) AS manual_rate,
  CAST(NULL AS DOUBLE) AS contract_rate,
  CAST(NULL AS STRING) AS audit_bucket,
  CAST(NULL AS STRING) AS reason_kind,
  CAST(reason_for_exclusion AS STRING) AS reason_categories,
  CAST(reason_for_exclusion AS STRING) AS reason_summary,
  CAST(NULL AS STRING) AS manual_status,
  CAST(NULL AS STRING) AS manual_warranty_type,
  CAST(NULL AS STRING) AS contract_warranty_type,
  CAST(NULL AS STRING) AS agent_decision,
  (CAST(Total_Export_Warranty_EUR AS DOUBLE) / NULLIF(CAST(total_agreed AS DOUBLE) * {EXCHANGE_RATE_GBP_TO_EUR}, 0)) * 100 AS recovery_rate_percent,
  CAST(NULL AS DOUBLE) AS contract_lower_than_manual_eur,
  'jlr_existing_tc_output' AS confidence_bucket
FROM bci_rbs_prod.exploratory.claims_data_jlr_unified
UNION ALL
SELECT
  oem,
  brand,
  source_year,
  source_family,
  source_folder,
  claim_number,
  document_number,
  vin,
  country,
  TO_DATE(repair_date) AS repair_date,
  TO_DATE(warranty_start_date) AS warranty_start_date,
  warranty_basis_months,
  mileage,
  part_number,
  part_name,
  part_description,
  failure_code,
  sqw_name,
  division_new,
  oem_claims_eur,
  manual_payable_eur,
  contract_payable_eur,
  delta_contract_minus_manual_eur,
  gap_vs_oem_claim_eur,
  manual_rate,
  contract_rate,
  audit_bucket,
  reason_kind,
  reason_categories,
  reason_summary,
  manual_status,
  manual_warranty_type,
  contract_warranty_type,
  agent_decision,
  recovery_rate_percent,
  contract_lower_than_manual_eur,
  confidence_bucket
FROM bci_rbs_prod.exploratory.bmw_claims_dashboard_normalized;

CREATE OR REPLACE VIEW bci_rbs_prod.exploratory.claims_data_oem_unified_summary AS
SELECT
  oem,
  source_year,
  source_family,
  division_new,
  sqw_name,
  country,
  audit_bucket,
  confidence_bucket,
  COUNT(DISTINCT claim_number) AS claim_count,
  COUNT(*) AS row_count,
  SUM(oem_claims_eur) AS oem_claims_eur,
  SUM(manual_payable_eur) AS manual_payable_eur,
  SUM(contract_payable_eur) AS contract_payable_eur,
  SUM(delta_contract_minus_manual_eur) AS delta_contract_minus_manual_eur,
  SUM(gap_vs_oem_claim_eur) AS gap_vs_oem_claim_eur,
  SUM(contract_lower_than_manual_eur) AS contract_lower_than_manual_eur,
  (SUM(contract_payable_eur) / NULLIF(SUM(oem_claims_eur), 0)) * 100 AS recovery_rate_percent
FROM bci_rbs_prod.exploratory.claims_data_oem_unified
GROUP BY
  oem,
  source_year,
  source_family,
  division_new,
  sqw_name,
  country,
  audit_bucket,
  confidence_bucket;
"""
    path = OUT_DIR / "create_oem_unified_views.sql"
    path.write_text(sql.strip() + "\n", encoding="utf-8")
    return path


def _replace_table_refs(text: str) -> str:
    return (
        text.replace("bci_rbs_prod.exploratory.claims_data_jlr_unified", "bci_rbs_prod.exploratory.claims_data_oem_unified")
        .replace("claims_data_jlr_unified", "claims_data_oem_unified")
    )


def build_cloned_dashboard_payload() -> Path:
    dash = _read_source_dashboard()
    dash["pages"] = [dash["pages"][0]]
    dash["pages"][0]["displayName"] = "OEM Compare"
    for dataset in dash.get("datasets", []):
        query = "".join(dataset.get("queryLines", []))
        if "claims_data_jlr_unified" in query:
            dataset["queryLines"] = [_replace_table_refs(line) for line in dataset["queryLines"]]
            dataset["displayName"] = dataset.get("displayName", "").replace("JLR", "OEM").replace("jlr", "oem")
        if dataset.get("name") == "dataset1":
            dataset["displayName"] = "claims_data_oem_unified"
            dataset["queryLines"] = ["SELECT * FROM bci_rbs_prod.exploratory.claims_data_oem_unified"]
    payload = {
        "display_name": "BMW + JLR EDC Dashboard",
        "warehouse_id": "f9f9ba24a8e2d807",
        "serialized_dashboard": json.dumps(dash, ensure_ascii=False),
    }
    path = OUT_DIR / "lakeview_create_bmw_jlr_dashboard.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    csv_path = build_bmw_normalized_csv()
    sql_path = build_sql()
    dashboard_path = build_cloned_dashboard_payload()
    print(json.dumps({
        "bmw_csv": str(csv_path),
        "sql": str(sql_path),
        "dashboard_payload": str(dashboard_path),
    }, indent=2))


if __name__ == "__main__":
    main()
