# src/cwt_ui/services/scans.py
from __future__ import annotations
from typing import Tuple, Optional, Any, Iterable, Mapping
import os
from contextlib import contextmanager
import pandas as pd
import boto3

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

def run_all_scans(
    region: Optional[str] = None,
    *,
    aws_credentials: Optional[Mapping[str, str]] = None,
    aws_auth_method: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run both scans and return normalized (ec2_df, s3_df).

    If ``aws_credentials`` is provided, it is applied temporarily for the
    duration of this call via process environment variables only (in-memory).
    
    Args:
        region: AWS region to scan
        aws_credentials: Credential mapping for IAM User auth
        aws_auth_method: "user" or "role" - determines how credentials are used
    
    For IAM User auth, keys supported: "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION", "AWS_SESSION_TOKEN" (optional).
    
    For IAM Role auth, keys supported: "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION", "AWS_ROLE_ARN", "AWS_EXTERNAL_ID", "AWS_ROLE_SESSION_NAME".
    """
    if aws_credentials and aws_auth_method == "role":
        # Handle role-based authentication
        role_credentials = _assume_role(aws_credentials)
        if role_credentials:
            with _temporary_env(role_credentials):
                return scan_ec2(region=region), scan_s3(region=region)
        else:
            # Fallback to regular credentials if role assumption fails
            with _temporary_env(aws_credentials):
                return scan_ec2(region=region), scan_s3(region=region)
    elif aws_credentials:
        # Handle user-based authentication
        with _temporary_env(aws_credentials):
            return scan_ec2(region=region), scan_s3(region=region)
    
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

def _assume_role(credentials: Mapping[str, str]) -> Optional[dict[str, str]]:
    """Assume an IAM role and return temporary credentials.
    
    Args:
        credentials: Dictionary containing role assumption parameters
        
    Returns:
        Dictionary with temporary credentials or None if assumption fails
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Extract role parameters
        role_arn = credentials.get("AWS_ROLE_ARN", "").strip()
        external_id = credentials.get("AWS_EXTERNAL_ID", "").strip()
        session_name = credentials.get("AWS_ROLE_SESSION_NAME", "CloudWasteTracker").strip()
        region = credentials.get("AWS_DEFAULT_REGION", "us-east-1").strip()
        
        if not role_arn:
            return None
            
        # Create STS client with base credentials
        sts_client = boto3.client(
            'sts',
            aws_access_key_id=credentials.get("AWS_ACCESS_KEY_ID", ""),
            aws_secret_access_key=credentials.get("AWS_SECRET_ACCESS_KEY", ""),
            region_name=region
        )
        
        # Prepare assume role parameters
        assume_role_kwargs = {
            'RoleArn': role_arn,
            'RoleSessionName': session_name,
            'DurationSeconds': 3600  # 1 hour
        }
        
        # Add external ID if provided
        if external_id:
            assume_role_kwargs['ExternalId'] = external_id
        
        # Assume the role
        response = sts_client.assume_role(**assume_role_kwargs)
        
        # Extract temporary credentials
        creds = response['Credentials']
        return {
            'AWS_ACCESS_KEY_ID': creds['AccessKeyId'],
            'AWS_SECRET_ACCESS_KEY': creds['SecretAccessKey'],
            'AWS_SESSION_TOKEN': creds['SessionToken'],
            'AWS_DEFAULT_REGION': region
        }
        
    except ClientError as e:
        # Log the error but don't raise - let the caller handle gracefully
        print(f"Failed to assume role {role_arn}: {e}")
        return None
    except Exception as e:
        # Handle any other errors
        print(f"Unexpected error during role assumption: {e}")
        return None

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


@contextmanager
def _temporary_env(new_values: Mapping[str, str]):
    """Temporarily set environment variables, then restore originals.

    Only affects the current process memory; nothing is written to disk.
    """
    keys = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_SESSION_TOKEN",
    ]
    old: dict[str, Optional[str]] = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            if k in new_values and new_values[k]:
                os.environ[k] = new_values[k]  # type: ignore[index]
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ------------------------------
# Cost Explorer helpers
# ------------------------------

def get_cost_explorer_client(region: Optional[str] = None):
    # Cost Explorer is us-east-1 endpoint regardless of resources region
    return boto3.client("ce", region_name=region or "us-east-1")


def fetch_spend_summary(ce_client, *, days_7: bool = True, month_to_date: bool = True) -> dict:
    from datetime import datetime, timedelta, timezone

    out: dict[str, float | None] = {"last_7_days": None, "month_to_date": None}

    try:
        if days_7:
            end = datetime.now(timezone.utc).date()
            start = end - timedelta(days=7)
            resp = ce_client.get_cost_and_usage(
                TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": end.strftime("%Y-%m-%d")},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
            )
            total = 0.0
            for p in resp.get("ResultsByTime", []) or []:
                try:
                    total += float(p["Total"]["UnblendedCost"]["Amount"])  # type: ignore[index]
                except Exception:
                    pass
            out["last_7_days"] = total

        if month_to_date:
            end = datetime.now(timezone.utc).date()
            start = end.replace(day=1)
            resp = ce_client.get_cost_and_usage(
                TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": end.strftime("%Y-%m-%d")},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            total = 0.0
            for p in resp.get("ResultsByTime", []) or []:
                try:
                    total += float(p["Total"]["UnblendedCost"]["Amount"])  # type: ignore[index]
                except Exception:
                    pass
            out["month_to_date"] = total
    except Exception:
        # Surface as None; UI can show N/A
        pass

    return out


def fetch_credit_balance(ce_client) -> float | None:
    # Credits are not exposed uniformly; attempt to extract via Dimension/Filter if available
    # Placeholder: return None so UI shows N/A; extend later when credit APIs are available to you
    try:
        return None
    except Exception:
        return None
