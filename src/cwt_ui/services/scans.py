# cwt_ui/services/scans.py
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Optional, Callable, Any

import pandas as pd

# Try to import your core scanners from the app package
try:
    from cloud_waste_tracker.scanners import ec2_scanner as _ec2_scanner
except Exception:
    _ec2_scanner = None  # type: ignore

try:
    from cloud_waste_tracker.scanners import s3_scanner as _s3_scanner
except Exception:
    _s3_scanner = None  # type: ignore


# ------------------------------
# Public API (used by app.py)
# ------------------------------

def scan_ec2() -> pd.DataFrame:
    """
    Run the EC2 scan using your core scanner if available.
    Expected columns (flexible, but recommended):
      - instance_id, name, instance_type, region
      - avg_cpu_7d (float)
      - monthly_cost_usd (float)
      - recommendation (e.g., "OK", "Stop or downsize")
      - type (e.g., "idle_instance")
    """
    if _ec2_scanner is None:
        raise RuntimeError("cloud_waste_tracker.scanners.ec2_scanner is not importable.")
    if not hasattr(_ec2_scanner, "scan_ec2"):
        raise RuntimeError("ec2_scanner.scan_ec2() not found.")
    df: pd.DataFrame = _ec2_scanner.scan_ec2()  # type: ignore[attr-defined]
    return _normalize_ec2(df)


def scan_s3() -> pd.DataFrame:
    """
    Run the S3 scan using your core scanner if available.
    Expected columns (flexible, but recommended):
      - bucket, region
      - size_total_gb (float), objects_total (int)
      - standard_cold_gb (float), standard_cold_objects (int)
      - lifecycle_defined (bool)
      - recommendation (e.g., "OK", "Move old logs to Glacier")
      - notes (str)
      - type (e.g., "s3_bucket_summary")
    """
    if _s3_scanner is None:
        raise RuntimeError("cloud_waste_tracker.scanners.s3_scanner is not importable.")
    if not hasattr(_s3_scanner, "scan_s3"):
        raise RuntimeError("s3_scanner.scan_s3() not found.")
    df: pd.DataFrame = _s3_scanner.scan_s3()  # type: ignore[attr-defined]
    return _normalize_s3(df)


def scan_all() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience wrapper that returns (ec2_df, s3_df).
    """
    return scan_ec2(), scan_s3()


def load_from_csv(ec2_csv: Path, s3_csv: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load EC2/S3 results from CSV files (if they exist).
    Missing files return empty DataFrames.
    The data is normalized to the expected schema.
    """
    ec2_df = _read_csv_safe(ec2_csv)
    s3_df = _read_csv_safe(s3_csv)
    return _normalize_ec2(ec2_df), _normalize_s3(s3_df)


# ------------------------------
# Optional helpers (export)
# ------------------------------

def save_to_csv(
    ec2_df: Optional[pd.DataFrame],
    s3_df: Optional[pd.DataFrame],
    ec2_csv: Path,
    s3_csv: Path,
) -> None:
    """
    Save EC2/S3 DataFrames to CSV (if provided).
    """
    if isinstance(ec2_df, pd.DataFrame) and not ec2_df.empty:
        _ensure_parent(ec2_csv)
        ec2_df.to_csv(ec2_csv, index=False)
    if isinstance(s3_df, pd.DataFrame) and not s3_df.empty:
        _ensure_parent(s3_csv)
        s3_df.to_csv(s3_csv, index=False)


# ------------------------------
# Internal utilities
# ------------------------------

def _read_csv_safe(p: Path) -> pd.DataFrame:
    if not isinstance(p, Path):
        p = Path(p)
    if p.exists():
        try:
            return pd.read_csv(p)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _normalize_ec2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make EC2 data consistent for the UI:
    - Ensure expected columns exist (filled with defaults when missing).
    - Coerce numeric types.
    - Keep a stable column order for display.
    """
    if df is None or df.empty:
        return _empty_ec2_frame()

    df = df.copy()

    # Column mapping aliases (in case your scanner used slightly different names)
    alias_map = {
        "avg_cpu": "avg_cpu_7d",
        "cpu_avg_7d": "avg_cpu_7d",
        "monthly_usd": "monthly_cost_usd",
        "cost_monthly_usd": "monthly_cost_usd",
    }
    for old, new in alias_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Ensure required columns exist
    for col, default in {
        "instance_id": "",
        "name": "",
        "instance_type": "",
        "region": "",
        "avg_cpu_7d": 0.0,
        "monthly_cost_usd": 0.0,
        "recommendation": "",
        "type": "ec2_instance",
    }.items():
        if col not in df.columns:
            df[col] = default

    # Coerce dtypes
    df["avg_cpu_7d"] = _coerce_float(df["avg_cpu_7d"])
    df["monthly_cost_usd"] = _coerce_float(df["monthly_cost_usd"])

    # Preferred column order
    cols = [
        "instance_id",
        "name",
        "instance_type",
        "region",
        "avg_cpu_7d",
        "monthly_cost_usd",
        "recommendation",
        "type",
    ]
    cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
    return df[cols]


def _normalize_s3(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make S3 data consistent for the UI:
    - Ensure expected columns exist (filled with defaults when missing).
    - Coerce numeric types.
    - Keep a stable column order for display.
    """
    if df is None or df.empty:
        return _empty_s3_frame()

    df = df.copy()

    # Column mapping aliases
    alias_map = {
        "cold_gb": "standard_cold_gb",
        "cold_objects": "standard_cold_objects",
        "size_gb": "size_total_gb",
        "objects": "objects_total",
    }
    for old, new in alias_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Ensure required columns exist
    for col, default in {
        "bucket": "",
        "region": "",
        "size_total_gb": 0.0,
        "objects_total": 0,
        "standard_cold_gb": 0.0,
        "standard_cold_objects": 0,
        "lifecycle_defined": False,
        "recommendation": "",
        "notes": "",
        "type": "s3_bucket_summary",
    }.items():
        if col not in df.columns:
            df[col] = default

    # Coerce dtypes
    df["size_total_gb"] = _coerce_float(df["size_total_gb"])
    df["standard_cold_gb"] = _coerce_float(df["standard_cold_gb"])

    # Preferred column order
    cols = [
        "bucket",
        "region",
        "size_total_gb",
        "objects_total",
        "standard_cold_gb",
        "standard_cold_objects",
        "lifecycle_defined",
        "recommendation",
        "notes",
        "type",
    ]
    cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
    return df[cols]


def _empty_ec2_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "instance_id",
            "name",
            "instance_type",
            "region",
            "avg_cpu_7d",
            "monthly_cost_usd",
            "recommendation",
            "type",
        ]
    )


def _empty_s3_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "bucket",
            "region",
            "size_total_gb",
            "objects_total",
            "standard_cold_gb",
            "standard_cold_objects",
            "lifecycle_defined",
            "recommendation",
            "notes",
            "type",
        ]
    )


def _coerce_float(series: pd.Series) -> pd.Series:
    try:
        return pd.to_numeric(series, errors="coerce").fillna(0.0)
    except Exception:
        return series

