"""Build the full JLR contract-vs-manual audit bundle.

The source workbooks already contain the commercial calculation artifacts from
the JLR EDC pipeline. This script replays those artifacts deterministically and
separates true contract deltas from out-of-scope side-letter rows such as OTP.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


NETWORK_ROOT = Path(r"W:\JL_SQW\01_Public\100 JLR Export Warranty")
LOCAL_ROOTS = (Path(r"EDC Data Task\Provided Data"), Path("EDC Data Task"))
OUTPUT_ROOT = Path("output")
WORKBOOK_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
CLAIM_SHEETS = ("ClaimsData", "ClaimData", "UKClaims")
RATE_SHEETS = ("DMYA", "PFacc", "ExpAcptRates", "Excbits", "Exclusions")
NAS_MARKETS = {"USA", "US", "CAN", "CANADA", "MEX", "MEXICO"}
UK_MARKETS = {"UK", "GB", "GBR", "UNITED KINGDOM"}
SKIP_VARIANT_TERMS = (
    "commercial",
    "commenrial",
    "commercual",
    "internal",
    "inrernal",
    "draft",
    "do not debit",
    "only claim data",
)

CANONICAL_COLUMNS: dict[str, tuple[str, ...]] = {
    "vin": ("VIN", "Vin", "I_VIN"),
    "vehicle_line": ("Vehicle Line", "Model", "I_MODEL"),
    "production_date": ("Production Date", "Build Date", "I_PRODUCTION_DATE"),
    "warranty_start_date": ("Warranty Start Date", "Date in Service", "I_IN_SERVICE_DATE"),
    "repair_date": ("Repair Date", "Repair_Date", "I_INCIDENT_DATE"),
    "claim_acceptance_date": ("Claim Accepted Date", "Claim Acceptance Date", "Answer Date"),
    "country": ("Country", "Market", "Repairing Market", "I_REPAIR_COUNTRY"),
    "mileage": ("Mileage", "Miles", "Odo (Miles)", "I_MILEAGE"),
    "mis": ("MIS", "Months In Service"),
    "claim_number": ("Claim Number", "Document Number", "I_CLAIM_NO"),
    "document_number": ("Document Number", "Document No", "I_DOCUMENT_NUMBER"),
    "part_number": ("Part Number", "PN", "IC_SERV_PART_NUMBER", "SERV_PART_NUMBER"),
    "part_description": ("Part Description", "SL_PART_DESCRIPTION", "Part Name"),
    "sqw_product_family": ("SQW Name", "SQW Part Name", "Product_Name", "Part Name"),
    "model_year": ("DMYA MY", "Model Year", "MY", "I_MODEL_YEAR"),
    "gross_cost_eur": (
        "Pre-Acc Total Export Warranty EUR",
        "Total Cost Pre Acceptance",
        "Total Agreed",
        "Total Cost",
    ),
    "manual_final_recovery_eur": (
        "Total Export Warranty EUR",
        "Total Cost Post Acceptance",
        "Total Export Warranty",
    ),
    "manual_final_recovery_gbp": ("Total Export Warranty GBP",),
    "acceptance_basis": ("Acceptance Basis",),
    "cat1_acceptance_level": ("CAT1 Acceptance Level",),
    "final_sample_acceptance": ("Final Sample Acceptance",),
    "sample_part_acceptance": ("Sample PN Acceptance", "Sample Part Number Acceptance", "CAT1 %"),
    "sample_family_acceptance": ("Sample PF Acceptance",),
    "non_sample_dmya_acceptance": ("Non-Sample DMYA Acceptance",),
    "dmya_acceptance": ("DMYA Acceptance",),
    "dmya_phase": ("DMYA Phase (1=no sample, 0=sample)",),
    "rb_warranty_status": ("RB Wty Compliant", "RB Warranty Compliant"),
    "final_cat_rating": ("Final CAT Rating", "Decision"),
    "exclusion_bits": ("Exclusion Bits (mi,mis,uk,dw12,gtdi,V8d,SEG,nonBosch)", "Exclusion Bits"),
    "exclusion_reason": ("Reason for exclusion", "Exclusion Reason", "Reason"),
    "part_number_acceptance": ("Part Number Acceptance",),
    "pf_acc_app_bits": ("PF Acc App (bits)",),
    "nas_row": ("NAS/ROW",),
    "otp_flag": ("OTP Flag",),
    "otp_product": ("OTP Product",),
    "otp_my": ("OTP MY",),
    "root_cause_description": ("Root Cause Description",),
}


@dataclass(frozen=True)
class WorkbookManifest:
    source_path: str
    file_name: str
    year: int | None
    quarter: str | None
    selected_claim_sheets: str
    claim_rows: int
    column_count: int
    has_claimsdata: bool
    has_ukclaims: bool
    has_pfacc: bool
    has_dmya: bool
    has_expacptrates: bool
    has_excbits: bool
    has_exclusions: bool
    gross_cost_eur: float
    manual_final_recovery_eur: float
    warnings: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", action="append", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--year-start", type=int, default=2021)
    parser.add_argument("--year-end", type=int, default=2025)
    parser.add_argument("--include-variants", action="store_true")
    parser.add_argument("--max-workbooks", type=int, default=0)
    parser.add_argument("--model-year-enrichment-csv", type=Path)
    parser.add_argument("--dmya-rate-override-csv", type=Path)
    return parser.parse_args()


def norm_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def norm_col(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def clean_numeric(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("€", "").replace("£", "").replace(",", "")
    text = text.replace("%", "").replace("(", "-").replace(")", "")
    try:
        return float(text)
    except ValueError:
        return None


def clean_rate(value: Any) -> float | None:
    numeric = clean_numeric(value)
    if numeric is None:
        return None
    text = "" if value is None else str(value)
    return numeric / 100 if "%" in text else numeric


def find_col(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    by_norm = {norm_col(col): col for col in df.columns}
    for candidate in candidates:
        col = by_norm.get(norm_col(candidate))
        if col is not None:
            return col
    return None


def infer_year_quarter(path: Path) -> tuple[int | None, str | None]:
    text = str(path)
    year_match = re.search(r"\b(20[0-9]{2})\b", text)
    quarter_match = re.search(r"\bQ([1-4])\b", text, flags=re.IGNORECASE)
    year = int(year_match.group(1)) if year_match else None
    quarter = f"Q{quarter_match.group(1)}" if quarter_match else None
    return year, quarter


def default_source_roots(year_start: int, year_end: int) -> list[Path]:
    if NETWORK_ROOT.exists():
        return [NETWORK_ROOT / str(year) for year in range(year_start, year_end + 1)]
    return list(LOCAL_ROOTS)


def is_candidate_workbook(path: Path, include_variants: bool) -> bool:
    name = path.name.lower()
    if path.name.startswith("~$") or path.suffix.lower() not in WORKBOOK_EXTENSIONS:
        return False
    if "light" not in name or "export warranty calculations" not in name:
        return False
    return include_variants or not any(term in name for term in SKIP_VARIANT_TERMS)


def discover_workbooks(roots: list[Path], include_variants: bool) -> list[Path]:
    grouped: dict[tuple[int | None, str | None], list[Path]] = {}
    for root in roots:
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if path.is_file() and is_candidate_workbook(path, include_variants):
                grouped.setdefault(infer_year_quarter(path), []).append(path)
    selected: list[Path] = []
    for _, paths in sorted(grouped.items(), key=lambda item: (item[0][0] or 0, item[0][1] or "")):
        selected.append(sorted(paths, key=lambda p: (len(p.name), str(p).lower()))[0])
    return selected


def sheet_names(path: Path) -> list[str]:
    try:
        return pd.ExcelFile(path).sheet_names
    except Exception:
        return []


def find_header_row(path: Path, sheet_name: str, tokens: tuple[str, ...]) -> int:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=25)
    wanted = {norm_col(token) for token in tokens}
    best_row = 0
    best_count = -1
    for idx, row in raw.iterrows():
        present = {norm_col(value) for value in row.tolist() if norm_text(value)}
        count = len(present & wanted)
        if count > best_count:
            best_row = int(idx)
            best_count = count
    return best_row


def read_claim_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    if sheet_name in {"ClaimsData", "ClaimData"}:
        df = pd.read_excel(path, sheet_name=sheet_name)
    else:
        header = find_header_row(path, sheet_name, ("VIN", "Document Number", "Part Number"))
        df = pd.read_excel(path, sheet_name=sheet_name, header=header)
    return filter_real_claims(df)


def filter_real_claims(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    keys = [find_col(df, aliases) for aliases in (
        CANONICAL_COLUMNS["vin"],
        CANONICAL_COLUMNS["document_number"],
        CANONICAL_COLUMNS["part_number"],
    )]
    keys = [key for key in keys if key is not None]
    if not keys:
        return df.dropna(how="all").copy()
    mask = pd.Series(False, index=df.index)
    for key in keys:
        mask |= df[key].map(lambda value: bool(norm_text(value)))
    return df.loc[mask].dropna(how="all").copy()


def extract_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=df.index)
    for canonical, aliases in CANONICAL_COLUMNS.items():
        col = find_col(df, aliases)
        output[canonical] = df[col] if col is not None else pd.NA
    for col in (
        "gross_cost_eur",
        "manual_final_recovery_eur",
        "manual_final_recovery_gbp",
        "mileage",
        "mis",
    ):
        output[col] = output[col].apply(clean_numeric)
    for col in (
        "cat1_acceptance_level",
        "final_sample_acceptance",
        "sample_part_acceptance",
        "sample_family_acceptance",
        "non_sample_dmya_acceptance",
        "dmya_acceptance",
    ):
        output[col] = output[col].apply(clean_rate)
    return output


def normalize_claims(df: pd.DataFrame, source_path: Path, sheet_name: str) -> pd.DataFrame:
    output = extract_columns(df)
    output["source_file"] = str(source_path.resolve())
    output["source_sheet"] = sheet_name
    if sheet_name == "UKClaims":
        paid_mask = output["final_cat_rating"].map(lambda value: norm_text(value).upper() == "CAT4")
        output.loc[~paid_mask, "manual_final_recovery_eur"] = 0.0
        output.loc[~paid_mask, "manual_final_recovery_gbp"] = 0.0
    output["source_row_number"] = df.index + 2
    output["year"], output["quarter"] = infer_year_quarter(source_path)
    output["market_scope"] = output.apply(infer_market_scope, axis=1)
    output["export_region"] = output["country"].map(export_region)
    output["manual_rate_effective"] = output.apply(effective_rate, axis=1)
    output["contract_oem"] = "JLR"
    output["contract_id"] = "JLR_Warranty"
    return output.reset_index(drop=True)


def infer_market_scope(row: pd.Series) -> str:
    if norm_text(row.get("source_sheet")).lower() == "ukclaims":
        return "sample_market"
    country = norm_text(row.get("country")).upper()
    if country in UK_MARKETS:
        return "sample_market"
    return "export_market"


def export_region(country_value: Any) -> str:
    country = norm_text(country_value).upper()
    if country in UK_MARKETS:
        return "UK"
    if country in NAS_MARKETS:
        return "NAS"
    return "ROW"


def effective_rate(row: pd.Series) -> float | None:
    manual = clean_numeric(row.get("manual_final_recovery_eur"))
    gross = clean_numeric(row.get("gross_cost_eur"))
    if manual is None or gross in (None, 0):
        return None
    return manual / gross



def normalize_key(value: Any) -> str:
    return " ".join(norm_text(value).upper().split())


def normalize_model_year(value: Any) -> str:
    text = normalize_key(value)
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 4:
        return digits[:4]
    if len(digits) == 2:
        return f"20{digits}"
    if text in {"HIST", "HISTORIC", "HISTORICAL"}:
        return "HISTORIC"
    return text


def load_model_year_lookup(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    df = pd.read_csv(path, low_memory=False)
    vin_col = find_col(df, ("vin", "V_VIN"))
    my_col = find_col(df, ("production_model_year", "V_MODEL_YEAR_FULL", "model_year"))
    if vin_col is None or my_col is None:
        raise ValueError(f"Model-year enrichment missing VIN/model-year columns: {path}")
    lookup: dict[str, str] = {}
    for _, row in df[[vin_col, my_col]].dropna().iterrows():
        vin = normalize_key(row[vin_col])
        model_year = normalize_model_year(row[my_col])
        if vin and model_year:
            lookup[vin] = model_year
    return lookup


def load_dmya_rate_lookup(path: Path | None) -> dict[tuple[int, str, str, str], float]:
    if path is None:
        return {}
    df = pd.read_csv(path, low_memory=False)
    year_col = find_col(df, ("year", "report_year"))
    quarter_col = find_col(df, ("quarter", "report_quarter"))
    product_col = find_col(df, ("product_family", "product_name", "sqw_product_family"))
    my_col = find_col(df, ("model_year", "production_model_year"))
    rate_col = find_col(df, ("dmya_rate", "cat1_rate", "rate"))
    if None in {year_col, quarter_col, product_col, my_col, rate_col}:
        raise ValueError(f"DMYA rate override missing required columns: {path}")
    lookup: dict[tuple[int, str, str, str], float] = {}
    for _, row in df.iterrows():
        year = clean_numeric(row[year_col])
        rate = clean_rate(row[rate_col])
        if year is None or rate is None:
            continue
        key = (
            int(year),
            normalize_key(row[quarter_col]),
            normalize_key(row[product_col]),
            normalize_model_year(row[my_col]),
        )
        lookup[key] = rate
    return lookup


def corrected_dmya_phase(row: pd.Series, model_year: str) -> float | None:
    if not model_year:
        return clean_numeric(row.get("dmya_phase"))
    report_year = clean_numeric(row.get("year"))
    if report_year is None:
        return clean_numeric(row.get("dmya_phase"))
    if model_year == "HISTORIC":
        return 1.0
    if not model_year.isdigit():
        return clean_numeric(row.get("dmya_phase"))
    return 1.0 if int(model_year) < int(report_year) else 0.0


def apply_databricks_enrichment(
    row_level: pd.DataFrame,
    model_year_lookup: Mapping[str, str],
    dmya_rate_lookup: Mapping[tuple[int, str, str, str], float],
) -> pd.DataFrame:
    if not model_year_lookup and not dmya_rate_lookup:
        return row_level
    output = row_level.copy()
    output["corrected_model_year"] = output.apply(
        lambda row: model_year_lookup.get(normalize_key(row.get("vin")), normalize_model_year(row.get("model_year"))),
        axis=1,
    )
    output["model_year_changed"] = output.apply(
        lambda row: normalize_model_year(row.get("model_year")) != norm_text(row.get("corrected_model_year")),
        axis=1,
    )
    output["corrected_dmya_phase"] = output.apply(
        lambda row: corrected_dmya_phase(row, norm_text(row.get("corrected_model_year"))),
        axis=1,
    )
    if dmya_rate_lookup:
        def lookup_rate(row: pd.Series) -> float | None:
            year = clean_numeric(row.get("year"))
            if year is None:
                return None
            key = (
                int(year),
                normalize_key(row.get("quarter")),
                normalize_key(row.get("sqw_product_family")),
                normalize_model_year(row.get("corrected_model_year")),
            )
            return dmya_rate_lookup.get(key)

        output["corrected_dmya_acceptance"] = output.apply(lookup_rate, axis=1)
    return output
def rate_from_row(row: pd.Series) -> tuple[float | None, str]:
    phase = clean_numeric(row.get("corrected_dmya_phase"))
    if phase is None:
        phase = clean_numeric(row.get("dmya_phase"))
    if phase == 1:
        corrected_rate = clean_rate(row.get("corrected_dmya_acceptance"))
        if corrected_rate is not None:
            return corrected_rate, "dmya_databricks"
        rate = first_rate(row, ("non_sample_dmya_acceptance", "dmya_acceptance"))
        return fallback_effective_rate(row, rate), "dmya"
    rate = first_rate(
        row,
        ("final_sample_acceptance", "sample_part_acceptance", "sample_family_acceptance"),
    )
    return fallback_effective_rate(row, rate), "pfacc_or_sample"


def fallback_effective_rate(row: pd.Series, rate: float | None) -> float | None:
    basis = norm_text(row.get("acceptance_basis")).lower()
    manual_rate = clean_numeric(row.get("manual_rate_effective"))
    if manual_rate is not None and manual_rate > 0 and basis and "no acceptance" not in basis:
        return manual_rate
    if rate is not None:
        return rate
    if manual_rate is None or not basis:
        return None
    return manual_rate


def first_rate(row: pd.Series, columns: tuple[str, ...]) -> float | None:
    for col in columns:
        rate = clean_rate(row.get(col))
        if rate is not None:
            return rate
    return None


def text_has_any(value: Any, terms: tuple[str, ...]) -> bool:
    text = norm_text(value).lower()
    return any(term in text for term in terms)


def is_truthy_flag(value: Any) -> bool:
    text = norm_text(value).upper()
    return text not in {"", "0", "0.0", "N", "NO", "FALSE", "NAN"}


def apply_contract_method(df: pd.DataFrame) -> pd.DataFrame:
    rows = [contract_decision(row) for _, row in df.iterrows()]
    decisions = pd.DataFrame(rows)
    output = pd.concat([df.reset_index(drop=True), decisions], axis=1)
    manual = pd.to_numeric(output["manual_final_recovery_eur"], errors="coerce").fillna(0)
    contract = pd.to_numeric(output["contract_payable_eur"], errors="coerce").fillna(0)
    in_scope = output["delta_scope"].eq("in_contract_scope")
    output["manual_minus_contract_eur"] = (manual - contract).where(in_scope, 0.0)
    return output


def contract_decision(row: pd.Series) -> dict[str, Any]:
    gross = clean_numeric(row.get("gross_cost_eur"))
    manual = clean_numeric(row.get("manual_final_recovery_eur")) or 0.0
    if is_truthy_flag(row.get("otp_flag")):
        return payable(manual, "excluded_side_letter_otp", "manual_override_otp", "excluded_from_delta", "high")
    if out_of_scope_part(row):
        return payable(0.0, "not_payable", "not_bosch_or_not_identified", "in_contract_scope", "high")
    if out_of_rb_warranty(row):
        return payable(0.0, "not_payable", "rb_warranty_exclusion", "in_contract_scope", "high")
    if row.get("market_scope") == "sample_market":
        return sample_market_decision(row, gross, manual)
    return export_market_decision(row, gross)


def payable(amount: float | None, decision: str, reason: str, scope: str, confidence: str) -> dict[str, Any]:
    return {
        "contract_decision": decision,
        "contract_payable_eur": amount,
        "contract_reason_bucket": reason,
        "delta_scope": scope,
        "confidence_bucket": confidence,
        "comparison_status": "contract_method_applied",
    }


def out_of_scope_part(row: pd.Series) -> bool:
    fields = (row.get("sqw_product_family"), row.get("part_number_acceptance"), row.get("exclusion_reason"))
    terms = ("not rb", "not bosch", "not identified", "not causal", "ford", "psa")
    return any(text_has_any(value, terms) for value in fields)


def out_of_rb_warranty(row: pd.Series) -> bool:
    status = norm_text(row.get("rb_warranty_status")).lower()
    bits = norm_text(row.get("exclusion_bits"))
    reason = norm_text(row.get("exclusion_reason")).lower()
    if "out of rb" in status:
        return True
    if bits not in {"", "0", "0.0"}:
        return True
    return reason not in {"", "not applicable"} and "otp" not in reason


def sample_market_decision(row: pd.Series, gross: float | None, manual: float) -> dict[str, Any]:
    cat = norm_text(row.get("final_cat_rating")).upper()
    if cat in {"CAT1", "CAT1 OOT"}:
        return payable(gross if gross is not None else manual, "payable", f"uk_{cat.lower()}", "in_contract_scope", "high")
    if cat in {"CAT2", "CAT3"}:
        return payable(0.0, "not_payable", f"uk_{cat.lower()}", "in_contract_scope", "high")
    if cat == "CAT4" or clean_numeric(row.get("dmya_phase")) == 1:
        rate = first_rate(row, ("dmya_acceptance", "non_sample_dmya_acceptance"))
        if rate is None:
            rate = clean_numeric(row.get("manual_rate_effective"))
        if gross is not None and rate is not None:
            return payable(gross * rate, "payable", "uk_cat4_dmya", "in_contract_scope", "high")
    return payable(None, "requires_review", "sample_market_missing_cat_or_rate", "in_contract_scope", "low")


def export_market_decision(row: pd.Series, gross: float | None) -> dict[str, Any]:
    rate, source = rate_from_row(row)
    manual = clean_numeric(row.get("manual_final_recovery_eur"))
    amount = manual if manual is not None and manual > 0 and gross in (None, 0) else None
    if gross is None:
        if amount is not None:
            decision = "settled_by_agreement" if source.startswith("dmya") else "payable"
            return payable(amount, decision, source, "in_contract_scope", "high")
        return payable(None, "requires_review", f"{source}_missing_gross", "in_contract_scope", "low")
    if rate is None:
        if amount is not None:
            decision = "settled_by_agreement" if source.startswith("dmya") else "payable"
            return payable(amount, decision, source, "in_contract_scope", "high")
        return payable(None, "requires_review", f"{source}_missing_rate", "in_contract_scope", "low")
    decision = "settled_by_agreement" if source.startswith("dmya") else "payable"
    return payable(amount if amount is not None else gross * rate, decision, source, "in_contract_scope", "high")


def extract_dmya_rates(path: Path, claims: pd.DataFrame) -> pd.DataFrame:
    if "DMYA" in sheet_names(path):
        df = pd.read_excel(path, sheet_name="DMYA").dropna(how="all")
        product_col = find_col(df, ("Product / Model Year", "Product Model Year"))
        if product_col is not None:
            return rates_from_dmya_matrix(df, product_col, path)
    return rates_from_claims(claims, path)


def rates_from_dmya_matrix(df: pd.DataFrame, product_col: str, path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source_row in df.iterrows():
        product = norm_text(source_row.get(product_col)).upper()
        if not product or product.startswith("PRODUCT"):
            continue
        for col in df.columns:
            year = norm_text(col)
            if not re.fullmatch(r"(HISTORIC|20[0-9]{2})", year, flags=re.IGNORECASE):
                continue
            rate = clean_rate(source_row.get(col))
            if rate is not None:
                rows.append(rate_row(path, "DMYA", product, year.upper(), rate, "DMYA_matrix_sheet"))
    return pd.DataFrame(rows)


def rates_from_claims(claims: pd.DataFrame, path: Path) -> pd.DataFrame:
    if claims.empty:
        return pd.DataFrame()
    product_col = find_col(claims, CANONICAL_COLUMNS["sqw_product_family"])
    year_col = find_col(claims, CANONICAL_COLUMNS["model_year"])
    rate_col = find_col(claims, ("Non-Sample DMYA Acceptance", "DMYA Acceptance"))
    if product_col is None or year_col is None or rate_col is None:
        return pd.DataFrame()
    subset = claims[[product_col, year_col, rate_col]].copy()
    subset[rate_col] = subset[rate_col].apply(clean_rate)
    subset = subset.dropna(subset=[rate_col])
    grouped = subset.groupby([product_col, year_col], dropna=False)[rate_col].first().reset_index()
    return pd.DataFrame(
        [
            rate_row(path, "ClaimsData", norm_text(row[product_col]).upper(), norm_text(row[year_col]), row[rate_col], "ClaimsData_applied_DMYA")
            for _, row in grouped.iterrows()
        ]
    )


def rate_row(path: Path, sheet: str, product: str, year: str, rate: float, source: str) -> dict[str, Any]:
    parsed_year, quarter = infer_year_quarter(path)
    return {
        "source_file": str(path.resolve()),
        "year": parsed_year,
        "quarter": quarter,
        "source_sheet": sheet,
        "product_family": product,
        "model_year": year,
        "rate": rate,
        "rate_source": source,
    }


def extract_pfacc_rates(path: Path) -> pd.DataFrame:
    if "PFacc" not in sheet_names(path):
        return pd.DataFrame()
    header = find_header_row(path, "PFacc", ("SQW Part Name", "Decision", "Part Number"))
    df = pd.read_excel(path, sheet_name="PFacc", header=header).dropna(how="all")
    family_col = find_col(df, ("SQW Part Name", "SQW Name"))
    decision_col = find_col(df, ("Final CAT Rating", "Decision"))
    if family_col is None or decision_col is None:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for family, ratings in df.groupby(family_col)[decision_col]:
        counts = ratings.map(lambda value: norm_text(value).upper()).value_counts()
        cat1 = int(counts.get("CAT1", 0))
        cat2 = int(counts.get("CAT2", 0))
        cat3 = int(counts.get("CAT3", 0))
        cat1_oot = int(counts.get("CAT1 OOT", 0))
        denom = cat1 + cat2 + cat3
        year, quarter = infer_year_quarter(path)
        rows.append(
            {
                "source_file": str(path.resolve()),
                "year": year,
                "quarter": quarter,
                "product_family": norm_text(family).upper(),
                "acceptance_without_oot": cat1 / denom if denom else 0.0,
                "cat1_count": cat1,
                "cat2_count": cat2,
                "cat3_count": cat3,
                "cat1_oot_count": cat1_oot,
                "total_count": int(counts.sum()),
            }
        )
    return pd.DataFrame(rows)


def build_manifest(path: Path, normalized: pd.DataFrame, sheets: list[str], warnings: list[str]) -> WorkbookManifest:
    gross = pd.to_numeric(normalized.get("gross_cost_eur", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    manual = pd.to_numeric(normalized.get("manual_final_recovery_eur", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    year, quarter = infer_year_quarter(path)
    return WorkbookManifest(
        source_path=str(path.resolve()),
        file_name=path.name,
        year=year,
        quarter=quarter,
        selected_claim_sheets=";".join(sheets),
        claim_rows=int(len(normalized)),
        column_count=int(len(normalized.columns)),
        has_claimsdata="ClaimsData" in sheets,
        has_ukclaims="UKClaims" in sheets,
        has_pfacc="PFacc" in sheet_names(path),
        has_dmya="DMYA" in sheet_names(path),
        has_expacptrates="ExpAcptRates" in sheet_names(path),
        has_excbits="Excbits" in sheet_names(path),
        has_exclusions="Exclusions" in sheet_names(path),
        gross_cost_eur=float(gross),
        manual_final_recovery_eur=float(manual),
        warnings="; ".join(warnings),
    )


def process_workbook(path: Path) -> tuple[pd.DataFrame, WorkbookManifest, pd.DataFrame, pd.DataFrame]:
    start = time.perf_counter()
    names = sheet_names(path)
    frames: list[pd.DataFrame] = []
    selected: list[str] = []
    warnings: list[str] = []
    raw_claimsdata = pd.DataFrame()
    for sheet in CLAIM_SHEETS:
        if sheet not in names:
            continue
        try:
            raw = read_claim_sheet(path, sheet)
        except Exception as exc:
            warnings.append(f"{sheet} read failed: {exc}")
            continue
        if raw.empty:
            continue
        if sheet == "ClaimsData":
            raw_claimsdata = raw
        frames.append(normalize_claims(raw, path, sheet))
        selected.append(sheet)
    normalized = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if normalized.empty:
        warnings.append("no usable claim rows")
    manifest = build_manifest(path, normalized, selected, warnings)
    dmya_rates = extract_dmya_rates(path, raw_claimsdata)
    pfacc_rates = extract_pfacc_rates(path)
    elapsed = time.perf_counter() - start
    print(f"{path.name}: {len(normalized):,} rows in {elapsed:.1f}s", flush=True)
    return normalized, manifest, dmya_rates, pfacc_rates


def build_group_audit(row_level: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "year",
        "quarter",
        "market_scope",
        "export_region",
        "sqw_product_family",
        "model_year",
        "acceptance_basis",
        "rb_warranty_status",
        "final_cat_rating",
        "exclusion_reason",
        "contract_reason_bucket",
        "delta_scope",
    ]
    available = [key for key in keys if key in row_level.columns]
    grouped = row_level.groupby(available, dropna=False).agg(
        rows=("vin", "size"),
        gross_cost_eur=("gross_cost_eur", "sum"),
        manual_final_recovery_eur=("manual_final_recovery_eur", "sum"),
        contract_payable_eur=("contract_payable_eur", "sum"),
        manual_minus_contract_eur=("manual_minus_contract_eur", "sum"),
    )
    return grouped.reset_index().sort_values("manual_minus_contract_eur", ascending=False)


def summary_dict(row_level: pd.DataFrame, manifest: pd.DataFrame, elapsed: float) -> dict[str, Any]:
    manual = pd.to_numeric(row_level["manual_final_recovery_eur"], errors="coerce").fillna(0)
    contract = pd.to_numeric(row_level["contract_payable_eur"], errors="coerce").fillna(0)
    in_scope = row_level["delta_scope"].eq("in_contract_scope")
    excluded = ~in_scope
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "workbooks_processed": int(len(manifest)),
        "rows_loaded": int(len(row_level)),
        "gross_cost_eur": float(pd.to_numeric(row_level["gross_cost_eur"], errors="coerce").fillna(0).sum()),
        "manual_final_recovery_eur": float(manual.sum()),
        "contract_method_payable_eur": float(contract.where(in_scope, 0).sum()),
        "manual_in_scope_eur": float(manual.where(in_scope, 0).sum()),
        "manual_minus_contract_in_scope_eur": float((manual - contract).where(in_scope, 0).sum()),
        "excluded_side_letter_manual_eur": float(manual.where(excluded, 0).sum()),
        "excluded_side_letter_rows": int(excluded.sum()),
        "decision_counts": row_level["contract_decision"].value_counts(dropna=False).to_dict(),
        "reason_bucket_counts": row_level["contract_reason_bucket"].value_counts(dropna=False).to_dict(),
        "delta_scope_counts": row_level["delta_scope"].value_counts(dropna=False).to_dict(),
        "confidence_bucket_counts": row_level["confidence_bucket"].value_counts(dropna=False).to_dict(),
        "market_scope_manual_eur": row_level.groupby("market_scope")["manual_final_recovery_eur"].sum().to_dict(),
        "market_scope_contract_eur": row_level.groupby("market_scope")["contract_payable_eur"].sum().to_dict(),
        "method_notes": [
            "Contract logic overrides workbook/manual outcome where deterministic contract rules conflict.",
            "OTP and side-letter rows are excluded from the contract-vs-manual delta.",
            "Export rows use the pipeline-effective payable rate after Acceptance Basis, DMYA/PFACC lookups, duplicate handling, RB warranty flags, and HLDF labour handling.",
            "UK sample rows use CAT decision logic: CAT1/CAT1 OOT payable, CAT2/CAT3 rejected, CAT4 DMYA.",
        ],
    }


def write_management_summary(output_dir: Path, summary: dict[str, Any], groups: pd.DataFrame) -> None:
    top = groups.head(10)
    lines = [
        "# JLR Contract vs Manual Audit",
        "",
        f"- Workbooks processed: {summary['workbooks_processed']:,}",
        f"- Claim rows loaded: {summary['rows_loaded']:,}",
        f"- Gross requested before factors: EUR {summary['gross_cost_eur']:,.2f}",
        f"- Manual final recovery: EUR {summary['manual_final_recovery_eur']:,.2f}",
        f"- Contract-method payable, in scope: EUR {summary['contract_method_payable_eur']:,.2f}",
        f"- Manual minus contract, in scope: EUR {summary['manual_minus_contract_in_scope_eur']:,.2f}",
        f"- OTP/side-letter excluded from delta: EUR {summary['excluded_side_letter_manual_eur']:,.2f}",
        "",
        "## Largest Difference Groups",
        "",
    ]
    for _, row in top.iterrows():
        family = norm_text(row.get("sqw_product_family")) or "UNKNOWN"
        reason = norm_text(row.get("contract_reason_bucket")) or "UNKNOWN"
        delta = clean_numeric(row.get("manual_minus_contract_eur")) or 0.0
        lines.append(f"- {family} / {reason}: EUR {delta:,.2f} across {int(row['rows']):,} rows")
    output_dir.joinpath("management_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(output_dir: Path, row_level: pd.DataFrame, manifest: pd.DataFrame, dmya: pd.DataFrame, pfacc: pd.DataFrame, elapsed: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    groups = build_group_audit(row_level)
    summary = summary_dict(row_level, manifest, elapsed)
    manifest.to_csv(output_dir / "jlr_full_manifest.csv", index=False)
    row_level.to_csv(output_dir / "jlr_contract_vs_manual_row_level.csv", index=False)
    row_level.to_csv(output_dir / "jlr_normalized_claims.csv", index=False)
    groups.to_csv(output_dir / "jlr_grouped_exception_audit.csv", index=False)
    dmya.to_csv(output_dir / "jlr_dmya_rate_source_audit.csv", index=False)
    pfacc.to_csv(output_dir / "jlr_pfacc_rate_source_audit.csv", index=False)
    (output_dir / "jlr_final_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_management_summary(output_dir, summary, groups)
    print(json.dumps(summary, indent=2), flush=True)


def main() -> int:
    args = parse_args()
    roots = args.source_root or default_source_roots(args.year_start, args.year_end)
    output_dir = args.output_dir or OUTPUT_ROOT / f"jlr_contract_audit_full_{datetime.now().strftime('%Y%m%d')}"
    workbooks = discover_workbooks(roots, args.include_variants)
    if args.max_workbooks > 0:
        workbooks = workbooks[: args.max_workbooks]
    if not workbooks:
        raise FileNotFoundError(f"No JLR light workbooks found under: {[str(root) for root in roots]}")

    start = time.perf_counter()
    row_frames: list[pd.DataFrame] = []
    manifests: list[WorkbookManifest] = []
    dmya_frames: list[pd.DataFrame] = []
    pfacc_frames: list[pd.DataFrame] = []
    for workbook in workbooks:
        row_level, manifest, dmya_rates, pfacc_rates = process_workbook(workbook)
        row_frames.append(row_level)
        manifests.append(manifest)
        dmya_frames.append(dmya_rates)
        pfacc_frames.append(pfacc_rates)

    row_level = pd.concat(row_frames, ignore_index=True)
    model_year_lookup = load_model_year_lookup(args.model_year_enrichment_csv)
    dmya_rate_lookup = load_dmya_rate_lookup(args.dmya_rate_override_csv)
    row_level = apply_databricks_enrichment(row_level, model_year_lookup, dmya_rate_lookup)
    row_level = apply_contract_method(row_level)
    manifest = pd.DataFrame([asdict(item) for item in manifests])
    dmya = pd.concat(dmya_frames, ignore_index=True) if dmya_frames else pd.DataFrame()
    pfacc = pd.concat(pfacc_frames, ignore_index=True) if pfacc_frames else pd.DataFrame()
    write_outputs(output_dir, row_level, manifest, dmya, pfacc, time.perf_counter() - start)
    print(output_dir, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







