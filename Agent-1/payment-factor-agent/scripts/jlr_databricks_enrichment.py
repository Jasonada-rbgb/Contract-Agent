"""Export JLR Databricks enrichment inputs for the contract audit.

Outputs:
- production_model_year_by_vin.csv: VIN -> production model year from IQM production data.
- dmya_rates_from_stars.csv: locked annual CAT1 / (CAT1 + CAT2 + CAT3) DMYA rates by SQW product and production MY.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

WAREHOUSE_ID = "f9f9ba24a8e2d807"
STARS_TABLE = "bci_rbs_prod.raw.dxq_jlr_stars"
PRODUCTION_TABLE = "bci_rbs_prod.raw.dxq_jlr_iqm_production_vehicle_data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="edocument")
    parser.add_argument("--warehouse-id", default=WAREHOUSE_ID)
    parser.add_argument("--row-level-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year-start", type=int, default=2021)
    parser.add_argument("--year-end", type=int, default=2025)
    parser.add_argument("--analysis-year-start", type=int, default=2016)
    parser.add_argument("--analysis-year-end", type=int)
    parser.add_argument("--vin-chunk-size", type=int, default=5000)
    return parser.parse_args()


def run_statement(sql: str, profile: str, warehouse_id: str) -> tuple[list[str], list[list[Any]]]:
    body = {
        "warehouse_id": warehouse_id,
        "statement": sql,
        "wait_timeout": "50s",
        "on_wait_timeout": "CONTINUE",
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(body, handle)
        body_path = Path(handle.name)
    try:
        cmd = [
            "databricks",
            "api",
            "post",
            "/api/2.0/sql/statements",
            "--profile",
            profile,
            "--json",
            f"@{body_path}",
            "-o",
            "json",
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        body_path.unlink(missing_ok=True)
    payload = json.loads(result.stdout)
    state = payload.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise RuntimeError(f"Databricks statement did not succeed: {state} {payload.get('status')}")
    columns = [item["name"] for item in payload["manifest"]["schema"]["columns"]]
    rows = payload.get("result", {}).get("data_array", [])
    return columns, rows


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_vins(path: Path) -> list[str]:
    usecols = ["vin"]
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    vins = df["vin"].dropna().astype(str).str.strip().str.upper()
    return sorted(vin for vin in vins.unique() if vin and vin != "NAN")


def export_model_years(args: argparse.Namespace, vins: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for start in range(0, len(vins), args.vin_chunk_size):
        chunk = vins[start : start + args.vin_chunk_size]
        values = ",".join(sql_quote(vin) for vin in chunk)
        sql = f"""
SELECT
  upper(trim(V_VIN)) AS vin,
  upper(trim(V_MODEL_YEAR_FULL)) AS production_model_year,
  V_PROD_DATE_EVENT AS production_date,
  V_WARR_DATE_EVENT AS warranty_date,
  V_SALE_DATE_EVENT AS sale_date
FROM {PRODUCTION_TABLE}
WHERE upper(trim(V_VIN)) IN ({values})
"""
        columns, rows = run_statement(sql, args.profile, args.warehouse_id)
        frames.append(pd.DataFrame(rows, columns=columns))
        print(f"model-year chunk {start + len(chunk):,}/{len(vins):,}", flush=True)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def report_period_values(year_start: int, year_end: int) -> str:
    values = []
    for year in range(year_start, year_end + 1):
        for quarter in range(1, 5):
            values.append(f"({year}, 'Q{quarter}')")
    return ",\n".join(values)


def export_dmya_rates(args: argparse.Namespace) -> pd.DataFrame:
    analysis_year_end = args.analysis_year_end or args.year_end
    sql = f"""
WITH base AS (
  SELECT
    upper(trim(s.Product_Name)) AS product_family,
    try_cast(upper(trim(coalesce(p.V_MODEL_YEAR_FULL, s.V_MODEL_YEAR_FULL))) AS INT) AS model_year,
    CAST(s.SL_CREATED_DATE AS DATE) AS star_created_date,
    CAST(s.ST_COMPLETED_DATE AS DATE) AS star_answer_date,
    upper(trim(s.SL_DECISION_CODE)) AS cat
  FROM {STARS_TABLE} s
  LEFT JOIN {PRODUCTION_TABLE} p
    ON upper(trim(s.V_VIN)) = upper(trim(p.V_VIN))
  WHERE s.Product_Name IS NOT NULL
    AND s.SL_CREATED_DATE IS NOT NULL
    AND s.ST_COMPLETED_DATE IS NOT NULL
    AND upper(trim(s.SL_DECISION_CODE)) IN ('CAT1','CAT2','CAT3','CAT4')
), annual_rates AS (
  SELECT
    product_family,
    model_year,
    COUNT_IF(cat = 'CAT1') AS cat1_count,
    COUNT_IF(cat = 'CAT2') AS cat2_count,
    COUNT_IF(cat = 'CAT3') AS cat3_count,
    COUNT_IF(cat = 'CAT4') AS cat4_excluded_count,
    COUNT_IF(cat IN ('CAT1','CAT2','CAT3')) AS denominator_cat123,
    CASE WHEN COUNT_IF(cat IN ('CAT1','CAT2','CAT3')) = 0 THEN 0.0
         ELSE COUNT_IF(cat = 'CAT1') / COUNT_IF(cat IN ('CAT1','CAT2','CAT3'))
    END AS dmya_rate
  FROM base
  WHERE model_year BETWEEN {args.analysis_year_start} AND {analysis_year_end}
    AND star_created_date >= make_date(model_year, 1, 1)
    AND star_created_date < make_date(model_year + 1, 1, 1)
    AND star_answer_date >= make_date(model_year, 1, 1)
    AND star_answer_date < make_date(model_year + 1, 1, 1)
  GROUP BY product_family, model_year
  HAVING COUNT_IF(cat IN ('CAT1','CAT2','CAT3')) > 0
), report_periods AS (
  SELECT year, quarter FROM VALUES
{report_period_values(args.year_start, args.year_end)}
  AS t(year, quarter)
)
SELECT
  rp.year,
  rp.quarter,
  ar.product_family,
  CAST(ar.model_year AS STRING) AS model_year,
  ar.cat1_count,
  ar.cat2_count,
  ar.cat3_count,
  ar.cat4_excluded_count,
  ar.denominator_cat123,
  ar.dmya_rate,
  ar.model_year AS analysis_year,
  'SL_CREATED_DATE_AND_ST_COMPLETED_DATE_IN_MODEL_YEAR' AS dmya_rate_basis
FROM annual_rates ar
JOIN report_periods rp
  ON ar.model_year < rp.year
ORDER BY rp.year, rp.quarter, ar.product_family, ar.model_year
"""
    columns, rows = run_statement(sql, args.profile, args.warehouse_id)
    return pd.DataFrame(rows, columns=columns)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    vins = load_vins(args.row_level_csv)
    model_years = export_model_years(args, vins)
    dmya_rates = export_dmya_rates(args)
    model_years.to_csv(args.output_dir / "production_model_year_by_vin.csv", index=False)
    dmya_rates.to_csv(args.output_dir / "dmya_rates_from_stars.csv", index=False)
    summary = {
        "distinct_input_vins": len(vins),
        "model_year_rows": int(len(model_years)),
        "dmya_rate_rows": int(len(dmya_rates)),
        "dmya_formula": "CAT1 / (CAT1 + CAT2 + CAT3); CAT4 excluded",
        "dmya_date_basis": "SL_CREATED_DATE and ST_COMPLETED_DATE must both fall inside the model-year calendar year",
        "analysis_year_start": args.analysis_year_start,
        "analysis_year_end": args.analysis_year_end or args.year_end,
        "report_year_start": args.year_start,
        "report_year_end": args.year_end,
    }
    (args.output_dir / "databricks_enrichment_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
