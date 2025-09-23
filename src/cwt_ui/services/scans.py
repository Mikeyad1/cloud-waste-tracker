# src/cwt_ui/services/scans.py
from __future__ import annotations
from typing import Tuple, Optional, Any, Iterable
import pandas as pd

# Import scanners from the new location: src/scanners
try:
    from scanners import ec2_scanner as _ec2_scanner  # type: ignore
except Exception:
    _ec2_scanner = None  # type: ignore

try:
    from scanners import s3_scanner as _s3_scanner  # type: ignore
except Exception:
    _s3_scanner = None  # type: ignore


# ------------------------------
# Public API (used by app.py)
# ------------------------------

def run_all_scans(region: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run both scans and return normalized (ec2_df, s3_df)."""
    return scan_ec2(region=region), scan_s3(region=region)


def scan_ec2(region: Optional[str] = None) -> pd.DataFrame:
    """
    Run the EC2 scan and return a normalized DataFrame for the UI.
    Recommended columns: instance_id, name, instance_type, region,
    avg_cpu_7d, monthly_cost_usd, recommendation, type
    """
    if _ec2_scanner is None:
        return _empty_ec2_frame()

    # Try several common entry points for backward compatibility
    data = _call_scanner(
        _ec2_scanner,
        preferred=["scan_ec2", "run", "run_ec2", "main"],
        kwargs={"region": region} if region else {},
    )
    df = _to_dataframe(data)
    return _normalize_ec2(df)


def scan_s3(region: Optional[str] = None) -> pd.DataFrame:
    """
    Run the S3 scan and return a normalized DataFrame for the UI.
    Recommended columns: bucket, region, size_total_gb, objects_total,
    standard_cold_gb, standard_cold_objects, lifecycle_defined,
    recommendation, notes, type
    """
    if _s3_scanner is None:
        return _empty_s3_frame()

    data = _call_scanner(
        _s3_scanner,
        preferred=["scan_s3", "run", "run_s3", "main"],
        kwargs={"region": region} if region else {},
    )
    df = _to_dataframe(data)
    return _normalize_s3(df)


# ------------------------------
# Internal utilities
# ------------------------------

def _call_scanner(mod: Any, preferred: list[str], kwargs: dict) -> Any:
    """Call the first available function from `preferred` with kwargs."""
    for name in preferred:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn(**kwargs)
    raise RuntimeError(
        f"No callable scan entry point found. Tried: {', '.join(preferred)}"
    )


def _to_dataframe(data: Any) -> pd.DataFrame:
    """Convert list[dict] / DataFrame / None into a DataFrame."""
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, Iterable):
        try:
            return pd.DataFrame(list(data))
        except Exception:
            pass
    return pd.DataFrame()


def _normalize_ec2(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure expected EC2 columns and types for the UI."""
    if df is None or df.empty:
        return _empty_ec2_frame()

    df = df.copy()

    # Aliases to harmonize different scanner field names
    alias_map = {
        "avg_cpu": "avg_cpu_7d",
        "cpu_avg_7d": "avg_cpu_7d",
        "monthly_usd": "monthly_cost_usd",
        "cost_monthly_usd": "monthly_cost_usd",
        "type_": "type",
    }
    for old, new in alias_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Ensure required columns
    required_defaults = {
        "instance_id": "",
        "name": "",
        "instance_type": "",
        "region": "",
        "avg_cpu_7d": 0.0,
        "monthly_cost_usd": 0.0,
        "recommendation": "",
        "type": "ec2_instance",
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    # Coerce numeric
    df["avg_cpu_7d"] = _coerce_float(df["avg_cpu_7d"])
    df["monthly_cost_usd"] = _coerce_float(df["monthly_cost_usd"])

    # Stable column order
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
    """Ensure expected S3 columns and types for the UI."""
    if df is None or df.empty:
        return _empty_s3_frame()

    df = df.copy()

    # Aliases
    alias_map = {
        "cold_gb": "standard_cold_gb",
        "cold_objects": "standard_cold_objects",
        "size_gb": "size_total_gb",
        "objects": "objects_total",
        "type_": "type",
    }
    for old, new in alias_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # Ensure required columns
    required_defaults = {
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
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    # Coerce numeric
    df["size_total_gb"] = _coerce_float(df["size_total_gb"])
    df["standard_cold_gb"] = _coerce_float(df["standard_cold_gb"])

    # Stable column order
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
