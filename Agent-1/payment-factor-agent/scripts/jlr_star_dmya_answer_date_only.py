"""JLR STAR DMYA rate export — ANSWER-DATE-ONLY basis (authoritative).

Replaces the stale created+answered-date filter in jlr_databricks_enrichment.py.
This is the reproducible query for the DMYA rates used in the final audited output.

Rate = CAT1 / (CAT1 + CAT2 + CAT3); CAT4 excluded.
Date basis: ST_COMPLETED_DATE (answer date) must fall inside the model-year
calendar year. SL_CREATED_DATE is NOT gated (this is the difference vs the old
script).

Also emits a governance flag for denominator < 10 (thin technical factor).
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
MIN_DENOMINATOR_FLOOR = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", default="edocument")
    p.add_argument("--warehouse-id", default=WAREHOUSE_ID)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--report-year-start", type=int, default=2021)
    p.add_argument("--report-year-end", type=int, default=2025)
    p.add_argument("--analysis-year-start", type=int, default=2016)
    p.add_argument("--analysis-year-end", type=int, default=2025)
    return p.parse_args()


def run_statement(sql: str, profile: str, warehouse_id: str) -> pd.DataFrame:
    body = {"warehouse_id": warehouse_id, "statement": sql, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
        json.dump(body, h)
        body_path = Path(h.name)
    try:
        cmd = ["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", profile,
               "--json", f"@{body_path}", "-o", "json"]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        body_path.unlink(missing_ok=True)
    payload = json.loads(result.stdout)
    state = payload.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise RuntimeError(f"Databricks statement did not succeed: {state} {payload.get('status')}")
    cols = [c["name"] for c in payload["manifest"]["schema"]["columns"]]
    rows = payload.get("result", {}).get("data_array", [])
    return pd.DataFrame(rows, columns=cols)


def report_period_values(y0: int, y1: int) -> str:
    vals = [f"({y}, 'Q{q}')" for y in range(y0, y1 + 1) for q in range(1, 5)]
    return ",\n".join(vals)


def build_sql(args: argparse.Namespace) -> str:
    return f"""
WITH base AS (
  SELECT
    upper(trim(s.Product_Name)) AS product_family,
    try_cast(upper(trim(coalesce(p.V_MODEL_YEAR_FULL, s.V_MODEL_YEAR_FULL))) AS INT) AS model_year,
    CAST(s.ST_COMPLETED_DATE AS DATE) AS star_answer_date,
    upper(trim(s.SL_DECISION_CODE)) AS cat
  FROM {STARS_TABLE} s
  LEFT JOIN {PRODUCTION_TABLE} p ON upper(trim(s.V_VIN)) = upper(trim(p.V_VIN))
  WHERE s.Product_Name IS NOT NULL
    AND s.ST_COMPLETED_DATE IS NOT NULL
    AND upper(trim(s.SL_DECISION_CODE)) IN ('CAT1','CAT2','CAT3','CAT4')
), annual_rates AS (
  SELECT product_family, model_year,
    COUNT_IF(cat='CAT1') AS cat1_count,
    COUNT_IF(cat='CAT2') AS cat2_count,
    COUNT_IF(cat='CAT3') AS cat3_count,
    COUNT_IF(cat='CAT4') AS cat4_excluded_count,
    COUNT_IF(cat IN ('CAT1','CAT2','CAT3')) AS denominator_cat123,
    CASE WHEN COUNT_IF(cat IN ('CAT1','CAT2','CAT3'))=0 THEN 0.0
         ELSE COUNT_IF(cat='CAT1') / COUNT_IF(cat IN ('CAT1','CAT2','CAT3')) END AS dmya_rate
  FROM base
  WHERE model_year BETWEEN {args.analysis_year_start} AND {args.analysis_year_end}
    AND star_answer_date >= make_date(model_year,1,1)
    AND star_answer_date <  make_date(model_year+1,1,1)
  GROUP BY product_family, model_year
  HAVING COUNT_IF(cat IN ('CAT1','CAT2','CAT3')) > 0
), report_periods AS (
  SELECT year, quarter FROM VALUES
{report_period_values(args.report_year_start, args.report_year_end)}
  AS t(year, quarter)
)
SELECT rp.year, rp.quarter, ar.product_family, CAST(ar.model_year AS STRING) AS model_year,
  ar.cat1_count, ar.cat2_count, ar.cat3_count, ar.cat4_excluded_count, ar.denominator_cat123, ar.dmya_rate,
  ar.model_year AS analysis_year,
  'ST_COMPLETED_DATE_IN_MODEL_YEAR' AS dmya_rate_basis,
  CASE WHEN ar.denominator_cat123 < {MIN_DENOMINATOR_FLOOR} THEN true ELSE false END AS thin_denominator_flag
FROM annual_rates ar
JOIN report_periods rp ON ar.model_year < rp.year
ORDER BY rp.year, rp.quarter, ar.product_family, ar.model_year
"""


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    df = run_statement(build_sql(args), args.profile, args.warehouse_id)
    out = args.output_dir / "dmya_rates_answer_date_only.csv"
    df.to_csv(out, index=False)
    thin = df[df["thin_denominator_flag"].astype(str).str.lower().eq("true")]
    summary = {
        "rate_rows": int(len(df)),
        "thin_denominator_rows": int(len(thin)),
        "dmya_formula": "CAT1 / (CAT1 + CAT2 + CAT3); CAT4 excluded",
        "date_basis": "ST_COMPLETED_DATE (answer date) inside model-year calendar year; SL_CREATED_DATE NOT gated",
        "min_denominator_floor": MIN_DENOMINATOR_FLOOR,
        "output_csv": str(out),
    }
    (args.output_dir / "dmya_answer_date_only_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
